"""
Who owns what. Every resource belongs to a course and every course to a user,
so each function walks from the resource to its course and returns the
course's user_id (None when the resource does not exist).
"""

import uuid

from sqlalchemy import Select, select

from .database import SessionLocal
from .models import (
    Course,
    CourseRebuild,
    Document,
    PendingRegeneration,
    Task,
    TaskAttempt,
    Topic,
    TopicDeletion,
)


def _owner(statement: Select) -> uuid.UUID | None:
    with SessionLocal() as session:
        return session.scalar(statement)


def _via_topic() -> Select:
    return select(Course.user_id).join(Topic, Topic.course_id == Course.id)


def course_owner(course_id: uuid.UUID) -> uuid.UUID | None:
    return _owner(select(Course.user_id).where(Course.id == course_id))


def topic_owner(topic_id: uuid.UUID) -> uuid.UUID | None:
    return _owner(_via_topic().where(Topic.id == topic_id))


def task_owner(task_id: uuid.UUID) -> uuid.UUID | None:
    return _owner(
        _via_topic().join(Task, Task.topic_id == Topic.id).where(Task.id == task_id)
    )


def attempt_owner(attempt_id: int) -> uuid.UUID | None:
    return _owner(
        _via_topic()
        .join(Task, Task.topic_id == Topic.id)
        .join(TaskAttempt, TaskAttempt.task_id == Task.id)
        .where(TaskAttempt.id == attempt_id)
    )


def regeneration_owner(regeneration_id: uuid.UUID) -> uuid.UUID | None:
    return _owner(
        _via_topic()
        .join(PendingRegeneration, PendingRegeneration.topic_id == Topic.id)
        .where(PendingRegeneration.id == regeneration_id)
    )


def document_owner(document_id: uuid.UUID) -> uuid.UUID | None:
    return _owner(
        select(Course.user_id)
        .join(Document, Document.course_id == Course.id)
        .where(Document.id == document_id)
    )


def topic_deletion_owner(deletion_id: uuid.UUID) -> uuid.UUID | None:
    return _owner(
        select(Course.user_id)
        .join(TopicDeletion, TopicDeletion.course_id == Course.id)
        .where(TopicDeletion.id == deletion_id)
    )


def course_rebuild_owner(rebuild_id: uuid.UUID) -> uuid.UUID | None:
    return _owner(
        select(Course.user_id)
        .join(CourseRebuild, CourseRebuild.course_id == Course.id)
        .where(CourseRebuild.id == rebuild_id)
    )
