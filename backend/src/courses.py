import logging
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, delete, exists, func, select, update

from .database import SessionLocal
from .models import Course, Document, Task, TaskAttempt, Topic
from .openrouter import OpenRouterError, generate_topic_explanation
from .schemas import (
    CourseOut,
    CourseProgress,
    CourseSummary,
    TopicDetail,
    TopicLink,
    TopicMap,
    TopicNode,
    TopicOut,
)
from .vectorstore import add_document

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


def _build_tree(rows: Sequence[Any]) -> list[TopicOut]:
    """
    Builds a nested topic tree from flat topic rows.

    Rows need id, parent_id, title, description, has_explanation, tasks_total
    and tasks_solved attributes and must be ordered by position.
    """

    nodes = {
        row.id: TopicOut(
            id=row.id,
            title=row.title,
            description=row.description,
            has_explanation=row.has_explanation,
            tasks_total=row.tasks_total,
            tasks_solved=row.tasks_solved,
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
    Counts all topics in the tree and the completed ones (with all tasks solved).
    """

    total = 0
    completed = 0
    for topic in topics:
        children = _course_progress(topic.children)
        total += 1 + children.topics_total
        completed += children.topics_completed
        if topic.tasks_total > 0 and topic.tasks_solved == topic.tasks_total:
            completed += 1

    return CourseProgress(topics_total=total, topics_completed=completed)


class TopicPlacementError(Exception):
    """Raised when new topics cannot be placed where requested."""


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
        if parent_id is not None:
            parent = session.get(Topic, parent_id)
            if parent is None or parent.course_id != course_id:
                raise TopicPlacementError("parent topic not found in this course")

        siblings = and_(
            Topic.course_id == course_id,
            Topic.parent_id == parent_id
            if parent_id is not None
            else Topic.parent_id.is_(None),
        )

        if after_topic_id is not None:
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
            .values(position=Topic.position + len(nodes))
        )

        topics = _flatten_topics(nodes, course_id, parent_id, start_position=start)
        titles = [topic.title for topic in topics]
        session.add_all(topics)

    return titles


def save_course(initial_prompt: str, topic_map: TopicMap) -> uuid.UUID:
    """
    Saves a course and its whole topic tree in one transaction.

    Returns:
        uuid.UUID: id of the created course
    """

    course_id = uuid.uuid4()
    course = Course(
        id=course_id, title=topic_map.course_title, initial_prompt=initial_prompt
    )
    topics = _flatten_topics(topic_map.topics, course_id)

    with SessionLocal() as session, session.begin():
        session.add(course)
        session.flush()
        session.add_all(topics)

    return course_id


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
            )
            .outerjoin(task_counts, task_counts.c.topic_id == Topic.id)
            .where(Topic.course_id == course_id)
            .order_by(Topic.position)
        ).all()

        tree = _build_tree(topics)

        return CourseOut(
            id=course.id,
            title=course.title,
            initial_prompt=course.initial_prompt,
            created_at=course.created_at,
            topics=tree,
            progress=_course_progress(tree),
        )


def list_courses() -> list[CourseSummary]:
    """
    Returns all courses without topics, newest first.
    """

    statement = select(Course.id, Course.title, Course.created_at).order_by(
        Course.created_at.desc()
    )

    with SessionLocal() as session:
        rows = session.execute(statement).all()

    return [
        CourseSummary(id=row.id, title=row.title, created_at=row.created_at)
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

        return TopicDetail(
            id=topic.id,
            course_id=course.id,
            course_title=course.title,
            path=path,
            title=topic.title,
            description=topic.description,
            explanation=topic.explanation,
            subtopics=subtopics,
        )


def create_explanation(topic_id: uuid.UUID) -> TopicDetail | None:
    """
    Generates and saves an explanation for a topic, unless it already has one.

    Returns:
        TopicDetail | None: the topic with explanation, or None if it does not exist
    """

    topic = get_topic(topic_id)
    if topic is None:
        return None
    if topic.explanation is not None:
        return topic

    explanation = generate_topic_explanation(
        course_title=topic.course_title,
        path=[link.title for link in topic.path],
        title=topic.title,
        description=topic.description,
        subtopics=[link.title for link in topic.subtopics],
    )

    with SessionLocal() as session, session.begin():
        session.execute(
            update(Topic).where(Topic.id == topic_id).values(explanation=explanation)
        )

    try:
        index_lesson(topic_id)
    except OpenRouterError:
        logger.warning("Could not index lesson %s for RAG", topic_id, exc_info=True)

    return topic.model_copy(update={"explanation": explanation})


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
