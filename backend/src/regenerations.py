import uuid
from typing import Literal

from sqlalchemy import delete, select

from .courses import create_explanation
from .database import SessionLocal
from .models import PendingRegeneration, Topic
from .openrouter import OpenRouterError
from .schemas import PendingRegenerationOut
from .tasks import LessonMissingError, create_tasks


def _out(row: PendingRegeneration) -> PendingRegenerationOut:
    return PendingRegenerationOut(
        id=row.id,
        topic_id=row.topic_id,
        kind=row.kind,
        instructions=row.instructions,
        use_files=row.use_files,
    )


def propose_regeneration(
    topic_id: uuid.UUID,
    kind: Literal["lesson", "tasks"],
    instructions: str | None,
    use_files: bool,
) -> PendingRegenerationOut:
    """
    Saves a pending regeneration of the lesson or the tasks of a topic,
    replacing an older one of the same kind. Nothing is generated yet.

    Raises:
        ValueError: if the topic does not exist
        LessonMissingError: if tasks are proposed for a topic without a lesson
    """

    with SessionLocal() as session, session.begin():
        topic = session.get(Topic, topic_id)
        if topic is None:
            raise ValueError("topic not found")
        if kind == "tasks" and topic.explanation is None:
            raise LessonMissingError()

        session.execute(
            delete(PendingRegeneration).where(
                PendingRegeneration.topic_id == topic_id,
                PendingRegeneration.kind == kind,
            )
        )
        row = PendingRegeneration(
            topic_id=topic_id, kind=kind, instructions=instructions, use_files=use_files
        )
        session.add(row)
        session.flush()
        return _out(row)


def list_regenerations(topic_id: uuid.UUID) -> list[PendingRegenerationOut]:
    """Returns pending regenerations of a topic, oldest first."""

    with SessionLocal() as session:
        rows = session.scalars(
            select(PendingRegeneration)
            .where(PendingRegeneration.topic_id == topic_id)
            .order_by(PendingRegeneration.created_at)
        ).all()
        return [_out(row) for row in rows]


def confirm_regeneration(regeneration_id: uuid.UUID) -> PendingRegenerationOut | None:
    """
    Runs a pending regeneration. The proposal is removed before generating, so
    a second click cannot start a second (paid) generation; if generating
    fails, the proposal is saved again so the learner can retry.

    Returns:
        PendingRegenerationOut | None: the confirmed proposal, or None if it
            does not exist

    Raises:
        OpenRouterError: if generating fails
        LessonMissingError: if tasks are regenerated for a topic without a lesson
    """

    with SessionLocal() as session, session.begin():
        row = session.get(PendingRegeneration, regeneration_id)
        if row is None:
            return None
        proposal = _out(row)
        session.delete(row)

    try:
        if proposal.kind == "lesson":
            create_explanation(
                proposal.topic_id, True, proposal.instructions, proposal.use_files
            )
        else:
            create_tasks(
                proposal.topic_id, True, proposal.instructions, proposal.use_files
            )
    except (OpenRouterError, LessonMissingError):
        with SessionLocal() as session, session.begin():
            session.add(PendingRegeneration(**proposal.model_dump()))
        raise

    return proposal


def cancel_regeneration(regeneration_id: uuid.UUID) -> PendingRegenerationOut | None:
    """
    Removes a proposal without generating anything.

    Returns:
        PendingRegenerationOut | None: the removed proposal, or None if it
            does not exist
    """

    with SessionLocal() as session, session.begin():
        row = session.get(PendingRegeneration, regeneration_id)
        if row is None:
            return None
        proposal = _out(row)
        session.delete(row)

    return proposal
