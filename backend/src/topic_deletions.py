import uuid
from collections import defaultdict

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Task, TaskAttempt, Topic, TopicDeletion
from .schemas import TopicDeletionOut


def _subtree_ids(session: Session, topic: Topic) -> list[uuid.UUID]:
    """Returns ids of the topic and all its descendants."""

    rows = session.execute(
        select(Topic.id, Topic.parent_id).where(Topic.course_id == topic.course_id)
    ).all()
    children = defaultdict(list)
    for row in rows:
        children[row.parent_id].append(row.id)

    ids, queue = [], [topic.id]
    while queue:
        current = queue.pop()
        ids.append(current)
        queue.extend(children[current])
    return ids


def _deletion_out(session: Session, deletion: TopicDeletion) -> TopicDeletionOut:
    """Describes a proposed deletion with live counts of what would be lost."""

    topic = session.get(Topic, deletion.topic_id)
    ids = _subtree_ids(session, topic)

    def count(statement: Select) -> int:
        return session.scalar(select(func.count()).select_from(statement.subquery()))

    return TopicDeletionOut(
        id=deletion.id,
        topic_id=topic.id,
        topic_title=topic.title,
        subtopics=len(ids) - 1,
        lessons=count(
            select(Topic.id).where(Topic.id.in_(ids), Topic.explanation.is_not(None))
        ),
        tasks=count(
            select(Task.id).where(Task.topic_id.in_(ids), Task.archived_at.is_(None))
        ),
        attempts=count(select(TaskAttempt.id).join(Task).where(Task.topic_id.in_(ids))),
    )


def propose_topic_deletion(
    course_id: uuid.UUID, topic_id: uuid.UUID
) -> TopicDeletionOut | None:
    """
    Saves a pending deletion of a topic, or returns the existing one.
    Nothing is deleted until the learner confirms it.

    Returns:
        TopicDeletionOut | None: the proposal, or None if the topic is not in
            this course
    """

    with SessionLocal() as session, session.begin():
        topic = session.get(Topic, topic_id)
        if topic is None or topic.course_id != course_id:
            return None

        deletion = session.scalar(
            select(TopicDeletion).where(TopicDeletion.topic_id == topic_id)
        )
        if deletion is None:
            deletion = TopicDeletion(course_id=course_id, topic_id=topic_id)
            session.add(deletion)
            session.flush()

        return _deletion_out(session, deletion)


def list_topic_deletions(course_id: uuid.UUID) -> list[TopicDeletionOut]:
    """Returns pending deletions of a course, oldest first, with live counts."""

    with SessionLocal() as session:
        deletions = session.scalars(
            select(TopicDeletion)
            .where(TopicDeletion.course_id == course_id)
            .order_by(TopicDeletion.created_at)
        ).all()
        return [_deletion_out(session, deletion) for deletion in deletions]


def confirm_topic_deletion(deletion_id: uuid.UUID) -> tuple[uuid.UUID, str] | None:
    """
    Deletes the proposed topic with its whole subtree. The database deletes
    lessons, tasks, attempts, lesson chats and the proposal itself (CASCADE).

    Returns:
        tuple[uuid.UUID, str] | None: course id and title of the deleted topic,
            or None if the proposal does not exist
    """

    with SessionLocal() as session, session.begin():
        deletion = session.get(TopicDeletion, deletion_id)
        if deletion is None:
            return None

        topic = session.get(Topic, deletion.topic_id)
        result = (topic.course_id, topic.title)
        session.execute(delete(Topic).where(Topic.id == topic.id))

    return result


def cancel_topic_deletion(deletion_id: uuid.UUID) -> tuple[uuid.UUID, str] | None:
    """
    Removes a proposal without deleting the topic.

    Returns:
        tuple[uuid.UUID, str] | None: course id and title of the kept topic,
            or None if the proposal does not exist
    """

    with SessionLocal() as session, session.begin():
        deletion = session.get(TopicDeletion, deletion_id)
        if deletion is None:
            return None

        topic = session.get(Topic, deletion.topic_id)
        result = (topic.course_id, topic.title)
        session.delete(deletion)

    return result
