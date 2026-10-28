import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIMENSIONS = 1536


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "pk": "%(table_name)s_pkey",
            "fk": "%(table_name)s_%(column_0_name)s_fkey",
            "uq": "%(table_name)s_%(column_0_name)s_key",
            "ix": "ix_%(column_0_label)s",
        }
    )


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    initial_prompt: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    position: Mapped[int]
    explanation: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    question: Mapped[str] = mapped_column(Text)
    grading_notes: Mapped[str] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Spaced repetition: correct answers in a row and when the task is due
    # again (None until the task has its first graded attempt).
    review_streak: Mapped[int] = mapped_column(server_default=text("0"))
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The attempt this task was made for ("Practice this"); one per attempt.
    source_attempt_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_attempts.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TaskAttempt(Base):
    __tablename__ = "task_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    answer: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str | None] = mapped_column(String(32))
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index(
            "uq_conversations_course_chat",
            "course_id",
            unique=True,
            postgresql_where=text("topic_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), unique=True
    )
    # Summary of the older messages sent to the model instead of them, and the
    # id of the last message it covers.
    summary: Mapped[str | None] = mapped_column(Text)
    summary_until_id: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TopicDeletion(Base):
    __tablename__ = "topic_deletions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CourseRebuild(Base):
    __tablename__ = "course_rebuilds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), unique=True
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PendingRegeneration(Base):
    __tablename__ = "pending_regenerations"
    __table_args__ = (UniqueConstraint("topic_id", "kind"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(16))  # "lesson" or "tasks"
    instructions: Mapped[str | None] = mapped_column(Text)
    use_files: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), unique=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    # Only for uploaded images: the original image, shown in the UI and sent
    # to the model; its text (transcription) is stored as chunks like any file.
    media_type: Mapped[str | None] = mapped_column(String(64))
    # Only for uploaded files: a short description of the whole file.
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))

    document: Mapped["Document"] = relationship(back_populates="chunks")


class LearnerSettings(Base):
    """
    Settings of the (single) learner: one row with id 1. With users and login,
    this moves to the users table.
    """

    __tablename__ = "learner_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    about: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TopicLink(Base):
    """
    A prerequisite across the topic tree: from_topic requires to_topic, so the
    learner should know to_topic before from_topic.
    """

    __tablename__ = "topic_links"
    __table_args__ = (
        UniqueConstraint("from_topic_id", "to_topic_id"),
        CheckConstraint("from_topic_id <> to_topic_id", name="not_self"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    to_topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16), server_default="requires")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
