import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import and_, delete, exists, func, select, true, update
from sqlalchemy.orm import Session

from .database import SessionLocal
from .file_parsing import ParsedFile
from .learner_profile import format_learner_profile
from .learner_settings import get_about
from .models import Course, Document, Task, TaskAttempt, Topic
from .openrouter import (
    OpenRouterError,
    StatusCallback,
    generate_topic_explanation,
    generate_topic_links,
    generate_topic_map,
)
from .outline import (
    format_course_outline,
    format_outline_with_progress,
    required_titles,
)
from .schemas import (
    CourseOut,
    CourseProgress,
    CourseSummary,
    LinkPlan,
    Source,
    TopicDetail,
    TopicLink,
    TopicMap,
    TopicNode,
    TopicOut,
    TopicPrerequisites,
)
from .topic_links import Placed, links_by_topic, replace_course_links, resolve_links
from .vectorstore import (
    add_document,
    format_course_files,
    format_fragments,
    get_course_document_ids,
    retrieve_chunks,
)

logger = logging.getLogger(__name__)


def _flatten_topics(
    nodes: list[TopicNode],
    course_id: uuid.UUID,
    parent_id: uuid.UUID | None = None,
    start_position: int = 0,
) -> list[Topic]:
    """
    Converts a nested topic tree into a flat list of Topic rows,
    parents always before their children. Top-level nodes get positions
    starting at start_position.
    """

    topics = []

    for index, node in enumerate(nodes):
        topic = Topic(
            id=uuid.uuid4(),
            course_id=course_id,
            parent_id=parent_id,
            title=node.title,
            description=node.description,
            position=start_position + index,
        )
        topics.append(topic)
        topics.extend(_flatten_topics(node.children, course_id, topic.id))

    return topics


def due_condition(now: datetime):
    """Active tasks whose review date has come."""

    return and_(Task.archived_at.is_(None), Task.review_due_at <= now)


def _build_tree(
    rows: Sequence[Any], requires: dict[uuid.UUID, list[uuid.UUID]] | None = None
) -> list[TopicOut]:
    """
    Builds a nested topic tree from flat topic rows.

    Rows need id, parent_id, title, description, has_explanation, tasks_total,
    tasks_solved and reviews_due attributes and must be ordered by position.
    """

    nodes = {
        row.id: TopicOut(
            id=row.id,
            title=row.title,
            description=row.description,
            has_explanation=row.has_explanation,
            tasks_total=row.tasks_total,
            tasks_solved=row.tasks_solved,
            reviews_due=row.reviews_due,
            requires=(requires or {}).get(row.id, []),
            children=[],
        )
        for row in rows
    }

    roots = []
    for row in rows:
        node = nodes[row.id]
        if row.parent_id is None:
            roots.append(node)
        else:
            nodes[row.parent_id].children.append(node)

    return roots


def _course_progress(topics: list[TopicOut]) -> CourseProgress:
    """
    Counts all topics in the tree, the completed ones (with all tasks solved)
    and the tasks due for review.
    """

    total = 0
    completed = 0
    reviews = 0
    for topic in topics:
        children = _course_progress(topic.children)
        total += 1 + children.topics_total
        completed += children.topics_completed
        reviews += topic.reviews_due + children.reviews_due
        if topic.tasks_total > 0 and topic.tasks_solved == topic.tasks_total:
            completed += 1

    return CourseProgress(
        topics_total=total, topics_completed=completed, reviews_due=reviews
    )


class TopicPlacementError(Exception):
    """Raised when topics cannot be placed where requested."""


FIRST = "first"


def _make_room(
    session: Session,
    course_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    after_topic_id: uuid.UUID | Literal["first"] | None,
    count: int,
    exclude_id: uuid.UUID | None = None,
) -> int:
    """
    Validates the place in the tree and shifts the following siblings to make
    room for `count` topics. `after_topic_id` "first" places them at the start,
    None at the end.

    Returns:
        int: position of the first inserted topic

    Raises:
        TopicPlacementError: if the parent or the sibling is not valid
    """

    if parent_id is not None:
        parent = session.get(Topic, parent_id)
        if parent is None or parent.course_id != course_id:
            raise TopicPlacementError("parent topic not found in this course")

    siblings = and_(
        Topic.course_id == course_id,
        Topic.parent_id == parent_id
        if parent_id is not None
        else Topic.parent_id.is_(None),
        Topic.id != exclude_id if exclude_id is not None else true(),
    )

    if after_topic_id == FIRST:
        start = 0
    elif after_topic_id is not None:
        after = session.get(Topic, after_topic_id)
        if after is None or after.course_id != course_id:
            raise TopicPlacementError("sibling topic not found in this course")
        if after.parent_id != parent_id:
            raise TopicPlacementError("sibling topic has a different parent")
        start = after.position + 1
    else:
        last = session.scalar(select(func.max(Topic.position)).where(siblings))
        start = 0 if last is None else last + 1

    session.execute(
        update(Topic)
        .where(siblings, Topic.position >= start)
        .values(position=Topic.position + count)
    )
    return start


def add_topics(
    course_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    after_topic_id: uuid.UUID | None,
    nodes: list[TopicNode],
) -> list[str]:
    """
    Adds new topics (with their subtopics) to a course, under the given parent
    and after the given sibling, shifting the following siblings.

    Returns:
        list[str]: titles of all created topics

    Raises:
        TopicPlacementError: if the parent or the sibling is not valid
    """

    with SessionLocal() as session, session.begin():
        start = _make_room(session, course_id, parent_id, after_topic_id, len(nodes))
        topics = _flatten_topics(nodes, course_id, parent_id, start_position=start)
        titles = [topic.title for topic in topics]
        session.add_all(topics)

    return titles


def move_topic(
    course_id: uuid.UUID,
    topic_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    after_topic_id: uuid.UUID | Literal["first"] | None,
) -> tuple[str, list[str]]:
    """
    Moves a topic with its whole subtree under a new parent, after the given
    sibling ("first" for the start, None for the end).

    Returns:
        tuple[str, list[str]]: the title of the moved topic and the
            prerequisite links removed because they no longer fit the order

    Raises:
        TopicPlacementError: if the topic, the parent or the sibling is not
            valid, or the move would put the topic inside itself
    """

    with SessionLocal() as session, session.begin():
        topic = session.get(Topic, topic_id)
        if topic is None or topic.course_id != course_id:
            raise TopicPlacementError("topic not found in this course")
        if after_topic_id == topic_id:
            raise TopicPlacementError("a topic cannot be placed after itself")

        ancestor_id = parent_id
        while ancestor_id is not None:
            if ancestor_id == topic_id:
                raise TopicPlacementError("a topic cannot be moved inside itself")
            ancestor = session.get(Topic, ancestor_id)
            ancestor_id = ancestor.parent_id if ancestor else None

        topic.position = _make_room(
            session, course_id, parent_id, after_topic_id, 1, exclude_id=topic_id
        )
        topic.parent_id = parent_id
        title = topic.title

    return title, drop_broken_links(course_id)


def rename_topic(
    course_id: uuid.UUID, topic_id: uuid.UUID, title: str, description: str | None
) -> str | None:
    """
    Renames a topic and its lesson document used for RAG.

    Returns:
        str | None: the old title, or None if the topic is not in this course
    """

    with SessionLocal() as session, session.begin():
        topic = session.get(Topic, topic_id)
        if topic is None or topic.course_id != course_id:
            return None

        old_title = topic.title
        topic.title = title
        if description is not None:
            topic.description = description

        session.execute(
            update(Document).where(Document.topic_id == topic_id).values(filename=title)
        )

    return old_title


def save_course(
    initial_prompt: str,
    topic_map: TopicMap,
    sources: list[dict[str, Any]] | None = None,
) -> uuid.UUID:
    """
    Saves a course and its whole topic tree in one transaction, with the
    sources used to plan it.

    Returns:
        uuid.UUID: id of the created course
    """

    course_id = uuid.uuid4()

    with SessionLocal() as session, session.begin():
        course = Course(id=course_id, initial_prompt=initial_prompt)
        session.add(course)
        _add_topic_map(session, course, topic_map, sources)

    return course_id


def _add_topic_map(
    session: Session,
    course: Course,
    topic_map: TopicMap,
    sources: list[dict[str, Any]] | None,
) -> None:
    """Gives the course its title and sources and adds its whole topic tree."""

    course.title = topic_map.course_title
    course.sources = sources or None
    session.flush()
    topics = _flatten_topics(topic_map.topics, course.id)
    session.add_all(topics)
    session.flush()  # links point to the new topics
    replace_course_links(
        session, course.id, resolve_links(_placed(topic_map.topics, topics))
    )


def _placed(nodes: list[TopicNode], topics: list[Topic]) -> list[Placed]:
    """Pairs map nodes with the topics made from them (both in outline order)."""

    rows = iter(topics)
    placed: list[Placed] = []

    def walk(nodes: list[TopicNode], ancestors: tuple[uuid.UUID, ...]) -> None:
        for node in nodes:
            topic = next(rows)
            placed.append((node.title, topic.id, node.requires, ancestors))
            walk(node.children, (*ancestors, topic.id))

    walk(nodes, ())
    return placed


def create_course_with_files(
    initial_prompt: str,
    files: list[tuple[str, ParsedFile]],
    on_status: StatusCallback | None = None,
) -> uuid.UUID:
    """
    Creates a course from the prompt and the texts of uploaded files: the files
    are saved as course documents first, so their relevant fragments can be
    used to generate the map. If anything fails, the course is deleted with
    its documents.

    Returns:
        uuid.UUID: id of the created course

    Raises:
        OpenRouterError: if embeddings or the model request fail
        DocumentTooLargeError: if a file has too much text
    """

    course_id = uuid.uuid4()
    with SessionLocal() as session, session.begin():
        session.add(
            Course(
                id=course_id, title=initial_prompt[:255], initial_prompt=initial_prompt
            )
        )

    try:
        if on_status:
            on_status("Indexing your files…")
        for filename, parsed in files:
            add_document(
                parsed.text,
                filename,
                course_id,
                media_type=parsed.media_type,
                content=parsed.content,
                summary=parsed.summary,
            )
        materials, file_sources = get_file_materials(
            course_id, initial_prompt, with_summaries=True
        )
        topic_map, web_sources = generate_topic_map(
            initial_prompt, materials, on_status=on_status, about=get_about()
        )

        with SessionLocal() as session, session.begin():
            course = session.get(Course, course_id)
            _add_topic_map(
                session, course, topic_map, merge_sources(web_sources, file_sources)
            )
    except Exception:
        delete_course(course_id)
        raise

    return course_id


def update_course_goal(course_id: uuid.UUID, goal: str) -> CourseOut | None:
    """
    Changes the course goal (the prompt the course was created from), so that
    new lessons, tasks and chat answers follow it.

    Returns:
        CourseOut | None: the course, or None if it does not exist
    """

    with SessionLocal() as session, session.begin():
        course = session.get(Course, course_id)
        if course is None:
            return None
        course.initial_prompt = goal
    return get_course(course_id)


def get_course(course_id: uuid.UUID) -> CourseOut | None:
    """
    Loads a course with all its topics and builds the topic tree.

    Returns:
        CourseOut | None: the course, or None if it does not exist
    """

    with SessionLocal() as session:
        course = session.get(Course, course_id)
        if course is None:
            return None

        solved_task_ids = (
            select(TaskAttempt.task_id)
            .where(TaskAttempt.verdict == "correct")
            .distinct()
        )
        task_counts = (
            select(
                Task.topic_id,
                func.count().label("tasks_total"),
                func.count().filter(Task.id.in_(solved_task_ids)).label("tasks_solved"),
                func.count()
                .filter(Task.review_due_at <= datetime.now(UTC))
                .label("reviews_due"),
            )
            .where(Task.archived_at.is_(None))
            .group_by(Task.topic_id)
            .subquery()
        )

        topics = session.execute(
            select(
                Topic.id,
                Topic.parent_id,
                Topic.title,
                Topic.description,
                Topic.explanation.is_not(None).label("has_explanation"),
                func.coalesce(task_counts.c.tasks_total, 0).label("tasks_total"),
                func.coalesce(task_counts.c.tasks_solved, 0).label("tasks_solved"),
                func.coalesce(task_counts.c.reviews_due, 0).label("reviews_due"),
            )
            .outerjoin(task_counts, task_counts.c.topic_id == Topic.id)
            .where(Topic.course_id == course_id)
            .order_by(Topic.position)
        ).all()

        tree = _build_tree(topics, links_by_topic(session, course_id))

        return CourseOut(
            id=course.id,
            title=course.title,
            initial_prompt=course.initial_prompt,
            created_at=course.created_at,
            topics=tree,
            progress=_course_progress(tree),
            sources=course.sources or [],
        )


def list_courses() -> list[CourseSummary]:
    """
    Returns all courses without topics, newest first.
    """

    reviews = (
        select(Topic.course_id, func.count().label("reviews_due"))
        .join(Task, Task.topic_id == Topic.id)
        .where(due_condition(datetime.now(UTC)))
        .group_by(Topic.course_id)
        .subquery()
    )
    statement = (
        select(
            Course.id,
            Course.title,
            Course.created_at,
            func.coalesce(reviews.c.reviews_due, 0).label("reviews_due"),
        )
        .outerjoin(reviews, reviews.c.course_id == Course.id)
        .order_by(Course.created_at.desc())
    )

    with SessionLocal() as session:
        rows = session.execute(statement).all()

    return [
        CourseSummary(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            reviews_due=row.reviews_due,
        )
        for row in rows
    ]


def delete_course(course_id: uuid.UUID) -> bool:
    """
    Deletes a course. Its topics and documents are deleted
    by the database (ON DELETE CASCADE).

    Returns:
        bool: True if deleted, False if the course does not exist
    """

    with SessionLocal() as session, session.begin():
        result = session.execute(delete(Course).where(Course.id == course_id))

    return result.rowcount > 0


def get_topic(topic_id: uuid.UUID) -> TopicDetail | None:
    """
    Loads a topic with its course title, path of parent topics and subtopics.

    Returns:
        TopicDetail | None: the topic, or None if it does not exist
    """

    with SessionLocal() as session:
        topic = session.get(Topic, topic_id)
        if topic is None:
            return None

        course = session.get(Course, topic.course_id)
        course_topics = session.scalars(
            select(Topic)
            .where(Topic.course_id == topic.course_id)
            .order_by(Topic.position)
        ).all()

        topics_by_id = {t.id: t for t in course_topics}

        path = []
        parent_id = topic.parent_id
        while parent_id is not None:
            parent = topics_by_id[parent_id]
            path.insert(0, TopicLink(id=parent.id, title=parent.title))
            parent_id = parent.parent_id

        subtopics = [
            TopicLink(id=t.id, title=t.title)
            for t in course_topics
            if t.parent_id == topic.id
        ]
        requires = [
            TopicLink(id=required_id, title=topics_by_id[required_id].title)
            for required_id in links_by_topic(session, course.id).get(topic.id, [])
        ]

        return TopicDetail(
            id=topic.id,
            course_id=course.id,
            course_title=course.title,
            path=path,
            title=topic.title,
            description=topic.description,
            explanation=topic.explanation,
            subtopics=subtopics,
            requires=requires,
            sources=topic.sources or [],
        )


def get_file_materials(
    course_id: uuid.UUID, query: str, with_summaries: bool = False
) -> tuple[str | None, list[dict[str, Any]]]:
    """
    Returns fragments of the course's uploaded files relevant to the query,
    formatted for a prompt (None if there are none), optionally preceded by the
    summaries of all files, and the files the fragments come from as sources.
    """

    fragments = retrieve_chunks(
        query=query,
        file_uuids=get_course_document_ids(course_id, files_only=True),
    )
    if not fragments:
        return None, []
    names = dict.fromkeys(fragment["metadata"]["filename"] for fragment in fragments)
    sections = [format_fragments(fragments)]
    if with_summaries and (files := format_course_files(course_id)):
        sections.insert(0, files)
    return "\n\n".join(sections), [{"kind": "file", "title": name} for name in names]


def merge_sources(*lists: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    Joins source lists, keeping the first of duplicates (same kind and the same
    url, or title for files).
    """

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for sources in lists:
        for source in sources or []:
            key = (source["kind"], source.get("url") or source["title"])
            merged.setdefault(key, source)
    return list(merged.values())


def create_explanation(
    topic_id: uuid.UUID,
    regenerate: bool = False,
    instructions: str | None = None,
    use_files: bool = False,
) -> TopicDetail | None:
    """
    Generates and saves an explanation for a topic. Without regenerate returns
    the existing explanation if there is one. With regenerate replaces it.
    Optionally follows the learner's instructions and uses fragments of the
    course's uploaded files.

    Returns:
        TopicDetail | None: the topic with explanation, or None if it does not exist
    """

    topic = get_topic(topic_id)
    if topic is None:
        return None
    if topic.explanation is not None and not regenerate:
        return topic

    materials, file_sources = (
        get_file_materials(topic.course_id, f"{topic.title}\n{topic.description}")
        if use_files
        else (None, [])
    )

    course = get_course(topic.course_id)
    explanation, web_sources = generate_topic_explanation(
        course_title=topic.course_title,
        path=[link.title for link in topic.path],
        title=topic.title,
        description=topic.description,
        subtopics=[link.title for link in topic.subtopics],
        instructions=instructions,
        materials=materials,
        goal=course.initial_prompt if course else None,
        outline=format_course_outline(course.topics, topic.id) if course else None,
        about=get_about(),
        learner_profile=format_learner_profile(topic.course_id),
        requires=required_titles(course.topics, topic.id) if course else None,
    )

    sources = merge_sources(web_sources, file_sources)

    with SessionLocal() as session, session.begin():
        session.execute(
            update(Topic)
            .where(Topic.id == topic_id)
            .values(explanation=explanation, sources=sources or None)
        )

    try:
        index_lesson(topic_id)
    except OpenRouterError:
        logger.warning("Could not index lesson %s for RAG", topic_id, exc_info=True)

    return topic.model_copy(
        update={
            "explanation": explanation,
            "sources": [Source.model_validate(source) for source in sources],
        }
    )


def index_lesson(topic_id: uuid.UUID) -> bool:
    """
    (Re)indexes the lesson of a topic for RAG: replaces its lesson document
    with fresh chunks and embeddings.

    Returns:
        bool: False if the topic does not exist or has no lesson

    Raises:
        OpenRouterError: if generating embeddings fails
    """

    with SessionLocal() as session:
        topic = session.get(Topic, topic_id)
        if topic is None or topic.explanation is None:
            return False
        course_id, title, explanation = topic.course_id, topic.title, topic.explanation

    with SessionLocal() as session, session.begin():
        session.execute(delete(Document).where(Document.topic_id == topic_id))

    add_document(explanation, title, course_id, topic_id=topic_id)
    return True


def index_missing_lessons() -> int:
    """
    Indexes all lessons that have no lesson document yet. Lessons whose
    embeddings fail are skipped and stay missing for the next run.

    Returns:
        int: number of indexed lessons
    """

    has_document = exists().where(Document.topic_id == Topic.id)
    with SessionLocal() as session:
        topic_ids = list(
            session.scalars(
                select(Topic.id).where(Topic.explanation.is_not(None), ~has_document)
            )
        )

    indexed = 0
    for topic_id in topic_ids:
        try:
            if index_lesson(topic_id):
                indexed += 1
        except OpenRouterError:
            logger.warning("Could not index lesson %s for RAG", topic_id, exc_info=True)

    return indexed


def course_exists(course_id: uuid.UUID) -> bool:
    with SessionLocal() as session:
        return session.get(Course, course_id) is not None


def topic_exists(topic_id: uuid.UUID) -> bool:
    with SessionLocal() as session:
        return session.get(Topic, topic_id) is not None


def _placed_from_plan(topics: list[TopicOut], plan: LinkPlan) -> list[Placed]:
    """
    The course topics in outline order with the prerequisites the model found,
    turned from ids into titles; unknown ids are skipped.
    """

    order: list[tuple[TopicOut, tuple[uuid.UUID, ...]]] = []

    def walk(nodes: list[TopicOut], ancestors: tuple[uuid.UUID, ...]) -> None:
        for topic in nodes:
            order.append((topic, ancestors))
            walk(topic.children, (*ancestors, topic.id))

    walk(topics, ())
    titles = {str(topic.id): topic.title for topic, _ in order}
    requires: dict[str, list[str]] = {}
    for item in plan.topics:
        for required in item.requires:
            if required in titles:
                requires.setdefault(item.topic_id, []).append(titles[required])
            else:
                logger.warning("Skipped link to unknown topic id %s", required)
    return [
        (topic.title, topic.id, requires.get(str(topic.id), []), ancestors)
        for topic, ancestors in order
    ]


def _plan_with_requires(
    topics: list[TopicOut], topic_id: uuid.UUID | None, required_ids: list[str]
) -> LinkPlan:
    """
    The current links of a course, with new prerequisites for one topic
    (unchanged links if topic_id is None).
    """

    items: list[TopicPrerequisites] = []

    def walk(nodes: list[TopicOut]) -> None:
        for topic in nodes:
            requires = (
                required_ids
                if topic.id == topic_id
                else [str(required) for required in topic.requires]
            )
            if requires:
                items.append(
                    TopicPrerequisites(topic_id=str(topic.id), requires=requires)
                )
            walk(topic.children)

    walk(topics)
    return LinkPlan(topics=items)


def set_topic_requires(
    course_id: uuid.UUID, topic_id: uuid.UUID, required_ids: list[str]
) -> tuple[str, list[str], list[str], list[tuple[str, str]]] | None:
    """
    Replaces the prerequisites of one topic. All links of the course go through
    resolve_links again, so the rules are the same as for planned links.

    Returns:
        tuple | None: the topic title, titles of the saved prerequisites, of the
            removed earlier ones and (title, reason) of the skipped ones, or None
            if the topic is not in this course
    """

    course = get_course(course_id)
    if course is None:
        return None
    removed_ids = _requires_by_topic(course.topics).get(topic_id, [])
    placed = _placed_from_plan(
        course.topics, _plan_with_requires(course.topics, topic_id, required_ids)
    )
    titles = {str(placed_id): title for title, placed_id, _, _ in placed}
    if str(topic_id) not in titles:
        return None

    pairs = resolve_links(placed)
    kept = [titles[str(to_id)] for from_id, to_id in pairs if from_id == topic_id]
    removed = [
        titles[str(old)]
        for old in removed_ids
        if str(old) in titles and titles[str(old)] not in kept
    ]
    skipped = [
        (titles.get(required, required), _skip_reason(placed, topic_id, required))
        for required in required_ids
        if titles.get(required) not in kept
    ]
    with SessionLocal() as session, session.begin():
        replace_course_links(session, course_id, pairs)
    return titles[str(topic_id)], kept, removed, skipped


def _skip_reason(placed: list[Placed], topic_id: uuid.UUID, required: str) -> str:
    """Says which link rule a skipped prerequisite of topic_id broke."""

    index = {str(placed_id): i for i, (_, placed_id, _, _) in enumerate(placed)}
    if required not in index:
        return "not a topic of this course"
    position = index[str(topic_id)]
    required_id = placed[index[required]][1]
    if required_id == topic_id:
        return "the topic itself"
    if required_id in placed[position][3]:
        return "a module that contains this topic"
    if index[required] > position:
        return "comes later in the outline, so it must be moved earlier first"
    return "comes right before it in the same module, so the order already says it"


def _requires_by_topic(topics: list[TopicOut]) -> dict[uuid.UUID, list[uuid.UUID]]:
    requires = {}
    for topic in topics:
        requires[topic.id] = topic.requires
        requires.update(_requires_by_topic(topic.children))
    return requires


def drop_broken_links(course_id: uuid.UUID) -> list[str]:
    """
    Checks all links of a course again after its order changed and removes the
    ones that no longer follow the rules, e.g. a prerequisite moved after the
    topic.

    Returns:
        list[str]: the removed links as "topic ← prerequisite"
    """

    course = get_course(course_id)
    if course is None:
        return []
    placed = _placed_from_plan(
        course.topics, _plan_with_requires(course.topics, None, [])
    )
    titles = {placed_id: title for title, placed_id, _, _ in placed}
    current = {
        (placed_id, required_id)
        for placed_id, required_ids in _requires_by_topic(course.topics).items()
        for required_id in required_ids
    }
    pairs = resolve_links(placed)
    dropped = current - set(pairs)
    if not dropped:
        return []

    with SessionLocal() as session, session.begin():
        replace_course_links(session, course_id, pairs)
    return [f"{titles[from_id]} ← {titles[to_id]}" for from_id, to_id in dropped]


def infer_course_links(course_id: uuid.UUID) -> int | None:
    """
    Finds prerequisite links for an existing course with the planning model and
    replaces the course's links with the ones that pass the checks.

    Returns:
        int | None: number of saved links, or None if the course does not exist

    Raises:
        OpenRouterError: if the model request fails
    """

    course = get_course(course_id)
    if course is None:
        return None

    plan = generate_topic_links(
        course.title,
        course.initial_prompt,
        format_outline_with_progress(
            course.topics, include_ids=True, include_descriptions=True
        ),
    )
    pairs = resolve_links(_placed_from_plan(course.topics, plan))
    with SessionLocal() as session, session.begin():
        replace_course_links(session, course_id, pairs)
    return len(pairs)
