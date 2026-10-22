import uuid
from typing import Any, NamedTuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .courses import get_course, get_file_materials, merge_sources
from .database import SessionLocal
from .models import Course, CourseRebuild, Document, Task, TaskAttempt, Topic
from .openrouter import generate_rebuild_plan
from .outline import format_outline_with_progress
from .schemas import (
    CourseRebuildOut,
    RebuildDeletedTopic,
    RebuildPlan,
    RebuildPreviewNode,
    RebuildTopicNode,
    TopicOut,
)

MAX_DEPTH = 3


class RebuildError(Exception):
    """Raised when a rebuild plan cannot be used."""


def _normalize_id(value: str | None, valid_ids: set[str]) -> str | None:
    """Returns the id in canonical form if it is a topic of the course."""

    if value is None:
        return None
    try:
        normalized = str(uuid.UUID(value))
    except ValueError:
        return None
    return normalized if normalized in valid_ids else None


def sanitize_plan(
    nodes: list[RebuildTopicNode],
    valid_ids: set[str],
    used: set[str] | None = None,
    depth: int = 1,
) -> list[RebuildTopicNode]:
    """
    Repairs topic ids of a plan: unknown ids and ids used for the second time
    become new topics (None).

    Raises:
        RebuildError: if the plan is deeper than MAX_DEPTH levels
    """

    used = set() if used is None else used
    if nodes and depth > MAX_DEPTH:
        raise RebuildError(f"the plan is deeper than {MAX_DEPTH} levels")

    sanitized = []
    for node in nodes:
        topic_id = _normalize_id(node.existing_topic_id, valid_ids)
        if topic_id in used:
            topic_id = None
        if topic_id is not None:
            used.add(topic_id)
        sanitized.append(
            node.model_copy(
                update={
                    "existing_topic_id": topic_id,
                    "children": sanitize_plan(
                        node.children, valid_ids, used, depth + 1
                    ),
                }
            )
        )
    return sanitized


def propose_course_rebuild(
    course_id: uuid.UUID, instructions: str | None, use_files: bool
) -> uuid.UUID | None:
    """
    Generates a new map of the course and saves it as the course's pending
    rebuild, replacing an older one. Nothing in the course changes yet.

    Returns:
        uuid.UUID | None: id of the rebuild, or None if the course does not exist

    Raises:
        OpenRouterError: if the model or embeddings request fails
        RebuildError: if the plan has no topics or is too deep
    """

    course = get_course(course_id)
    if course is None:
        return None

    materials, file_sources = (
        get_file_materials(
            course_id, f"{course.title}\n{course.initial_prompt}\n{instructions or ''}"
        )
        if use_files
        else (None, [])
    )
    plan, web_sources = generate_rebuild_plan(
        course_title=course.title,
        initial_prompt=course.initial_prompt,
        outline=format_outline_with_progress(
            course.topics, include_ids=True, include_descriptions=True
        ),
        instructions=instructions,
        materials=materials,
    )

    with SessionLocal() as session:
        valid_ids = {
            str(topic_id)
            for topic_id in session.scalars(
                select(Topic.id).where(Topic.course_id == course_id)
            )
        }
    topics = sanitize_plan(plan.topics, valid_ids)
    if not topics:
        raise RebuildError("the plan has no topics")

    with SessionLocal() as session, session.begin():
        session.execute(
            delete(CourseRebuild).where(CourseRebuild.course_id == course_id)
        )
        rebuild = CourseRebuild(
            course_id=course_id,
            plan={
                **RebuildPlan(topics=topics).model_dump(),
                "sources": merge_sources(web_sources, file_sources),
            },
        )
        session.add(rebuild)
        session.flush()
        return rebuild.id


def _flatten(topics: list[TopicOut]) -> dict[uuid.UUID, TopicOut]:
    """Returns all topics of a tree by id, in outline order."""

    result = {}
    for topic in topics:
        result[topic.id] = topic
        result.update(_flatten(topic.children))
    return result


def _kept_ids(nodes: list[RebuildTopicNode]) -> set[str]:
    ids = set()
    for node in nodes:
        if node.existing_topic_id is not None:
            ids.add(node.existing_topic_id)
        ids |= _kept_ids(node.children)
    return ids


def _count_nodes(nodes: list[RebuildTopicNode]) -> int:
    return sum(1 + _count_nodes(node.children) for node in nodes)


def _preview(
    nodes: list[RebuildTopicNode], current: dict[uuid.UUID, TopicOut]
) -> list[RebuildPreviewNode]:
    preview = []
    for node in nodes:
        existing = (
            current[uuid.UUID(node.existing_topic_id)]
            if node.existing_topic_id is not None
            else None
        )
        preview.append(
            RebuildPreviewNode(
                topic_id=existing.id if existing else None,
                title=node.title,
                description=node.description,
                old_title=(
                    existing.title
                    if existing and existing.title != node.title
                    else None
                ),
                has_explanation=existing.has_explanation if existing else False,
                tasks_total=existing.tasks_total if existing else 0,
                tasks_solved=existing.tasks_solved if existing else 0,
                children=_preview(node.children, current),
            )
        )
    return preview


def _attempt_counts(topic_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Counts all attempts (also of archived tasks) per topic."""

    if not topic_ids:
        return {}
    with SessionLocal() as session:
        rows = session.execute(
            select(Task.topic_id, func.count(TaskAttempt.id))
            .join(TaskAttempt, TaskAttempt.task_id == Task.id)
            .where(Task.topic_id.in_(topic_ids))
            .group_by(Task.topic_id)
        ).all()
    return dict(rows)


def _plan_sources(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Returns the sources saved with a plan ([] for plans saved without a list)."""

    sources = plan.get("sources")
    return sources if isinstance(sources, list) else []


def get_course_rebuild(course_id: uuid.UUID) -> CourseRebuildOut | None:
    """
    Returns the pending rebuild of a course compared with the current course:
    the new tree with kept and new topics, and the topics that would be deleted.

    Returns:
        CourseRebuildOut | None: the preview, or None if there is no pending rebuild
    """

    with SessionLocal() as session:
        rebuild = session.scalar(
            select(CourseRebuild).where(CourseRebuild.course_id == course_id)
        )
        if rebuild is None:
            return None
        rebuild_id = rebuild.id
        sources = _plan_sources(rebuild.plan)
        plan = RebuildPlan.model_validate({"topics": rebuild.plan["topics"]})

    current = _flatten(get_course(course_id).topics)
    nodes = sanitize_plan(plan.topics, {str(topic_id) for topic_id in current})
    kept = _kept_ids(nodes)
    deleted_ids = [topic_id for topic_id in current if str(topic_id) not in kept]
    attempts = _attempt_counts(deleted_ids)

    return CourseRebuildOut(
        id=rebuild_id,
        topics=_preview(nodes, current),
        deleted=[
            RebuildDeletedTopic(
                topic_id=topic_id,
                title=current[topic_id].title,
                has_explanation=current[topic_id].has_explanation,
                tasks=current[topic_id].tasks_total,
                attempts=attempts.get(topic_id, 0),
            )
            for topic_id in deleted_ids
        ],
        kept_count=len(kept),
        new_count=_count_nodes(nodes) - len(kept),
        sources=sources,
    )


class RebuildResult(NamedTuple):
    course_id: uuid.UUID
    kept: int
    added: int
    deleted: int


def _apply_nodes(
    session: Session,
    course_id: uuid.UUID,
    nodes: list[RebuildTopicNode],
    parent_id: uuid.UUID | None,
    topics: dict[uuid.UUID, Topic],
) -> int:
    """
    Places kept topics and creates new ones following the plan, level by level.

    Returns:
        int: number of created topics
    """

    added = 0
    for position, node in enumerate(nodes):
        title = node.title[:255]
        if node.existing_topic_id is not None:
            topic = topics[uuid.UUID(node.existing_topic_id)]
            if topic.title != title:
                session.execute(
                    update(Document)
                    .where(Document.topic_id == topic.id)
                    .values(filename=title)
                )
            topic.title = title
            topic.description = node.description
            topic.parent_id = parent_id
            topic.position = position
        else:
            topic = Topic(
                id=uuid.uuid4(),
                course_id=course_id,
                parent_id=parent_id,
                title=title,
                description=node.description,
                position=position,
            )
            session.add(topic)
            added += 1
        added += _apply_nodes(session, course_id, node.children, topic.id, topics)
    return added


def apply_course_rebuild(rebuild_id: uuid.UUID) -> RebuildResult | None:
    """
    Rebuilds the course following the plan in one transaction: kept topics get
    their new title, description and place, new topics are created, and only
    then topics left out of the plan are deleted (with their lessons, tasks and
    attempts), so no kept topic is deleted together with its old parent.

    Returns:
        RebuildResult | None: what changed, or None if the rebuild does not exist
    """

    with SessionLocal() as session, session.begin():
        rebuild = session.get(CourseRebuild, rebuild_id)
        if rebuild is None:
            return None
        course_id = rebuild.course_id
        plan = RebuildPlan.model_validate({"topics": rebuild.plan["topics"]})

        topics = {
            topic.id: topic
            for topic in session.scalars(
                select(Topic).where(Topic.course_id == course_id)
            )
        }
        nodes = sanitize_plan(plan.topics, {str(topic_id) for topic_id in topics})
        kept = {uuid.UUID(topic_id) for topic_id in _kept_ids(nodes)}

        added = _apply_nodes(session, course_id, nodes, None, topics)
        session.flush()

        deleted = [topic_id for topic_id in topics if topic_id not in kept]
        if deleted:
            session.execute(delete(Topic).where(Topic.id.in_(deleted)))
        course = session.get(Course, course_id)
        course.sources = (
            merge_sources(course.sources, _plan_sources(rebuild.plan)) or None
        )
        session.delete(rebuild)

    return RebuildResult(course_id, len(kept), added, len(deleted))


def discard_course_rebuild(rebuild_id: uuid.UUID) -> uuid.UUID | None:
    """
    Removes a pending rebuild without changing the course.

    Returns:
        uuid.UUID | None: the course id, or None if the rebuild does not exist
    """

    with SessionLocal() as session, session.begin():
        rebuild = session.get(CourseRebuild, rebuild_id)
        if rebuild is None:
            return None
        course_id = rebuild.course_id
        session.delete(rebuild)

    return course_id
