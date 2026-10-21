import uuid
from collections import defaultdict

from sqlalchemy import func, select, update

from .courses import get_topic
from .database import SessionLocal
from .models import Task, TaskAttempt
from .openrouter import generate_tasks, grade_answer
from .schemas import AttemptOut, TaskOut


class LessonMissingError(Exception):
    """Raised when tasks are requested for a topic without a lesson."""


def _attempt_out(attempt: TaskAttempt) -> AttemptOut:
    return AttemptOut(
        id=attempt.id,
        answer=attempt.answer,
        verdict=attempt.verdict,
        feedback=attempt.feedback,
        created_at=attempt.created_at,
    )


def get_tasks(topic_id: uuid.UUID) -> list[TaskOut]:
    """
    Returns active (not archived) tasks of a topic, in order, with their attempts.
    """

    with SessionLocal() as session:
        tasks = session.scalars(
            select(Task)
            .where(Task.topic_id == topic_id, Task.archived_at.is_(None))
            .order_by(Task.position)
        ).all()

        attempts = defaultdict(list)
        task_ids = [task.id for task in tasks]
        if task_ids:
            for attempt in session.scalars(
                select(TaskAttempt)
                .where(TaskAttempt.task_id.in_(task_ids))
                .order_by(TaskAttempt.id)
            ):
                attempts[attempt.task_id].append(_attempt_out(attempt))

        return [
            TaskOut(
                id=task.id,
                position=task.position,
                question=task.question,
                attempts=attempts[task.id],
            )
            for task in tasks
        ]


def create_tasks(topic_id: uuid.UUID, regenerate: bool = False) -> list[TaskOut] | None:
    """
    Generates tasks for a topic. Without regenerate returns the existing active
    tasks if there are any. With regenerate archives the current tasks first.

    Returns:
        list[TaskOut] | None: active tasks, or None if the topic does not exist

    Raises:
        LessonMissingError: if the topic has no lesson yet
        OpenRouterError: if the model request fails
    """

    topic = get_topic(topic_id)
    if topic is None:
        return None
    if topic.explanation is None:
        raise LessonMissingError()

    if not regenerate:
        existing = get_tasks(topic_id)
        if existing:
            return existing

    generated = generate_tasks(
        course_title=topic.course_title,
        path=[link.title for link in topic.path],
        title=topic.title,
        lesson=topic.explanation,
    )

    with SessionLocal() as session, session.begin():
        session.execute(
            update(Task)
            .where(Task.topic_id == topic_id, Task.archived_at.is_(None))
            .values(archived_at=func.now())
        )
        session.add_all(
            Task(
                topic_id=topic_id,
                position=position,
                question=task.question,
                grading_notes=task.grading_notes,
            )
            for position, task in enumerate(generated.tasks)
        )

    return get_tasks(topic_id)


def submit_attempt(task_id: uuid.UUID, answer: str) -> AttemptOut | None:
    """
    Saves the learner's answer and grades it. If grading fails, the attempt
    stays saved without a verdict.

    Returns:
        AttemptOut | None: the graded attempt, or None if the task does not exist
            or is archived

    Raises:
        OpenRouterError: if grading fails
    """

    with SessionLocal() as session, session.begin():
        task = session.get(Task, task_id)
        if task is None or task.archived_at is not None:
            return None

        attempt = TaskAttempt(task_id=task_id, answer=answer)
        session.add(attempt)
        session.flush()
        attempt_id = attempt.id

    return grade_attempt(attempt_id)


def grade_attempt(attempt_id: int) -> AttemptOut | None:
    """
    Grades an attempt that has no verdict yet. Already graded attempts are
    returned unchanged.

    Returns:
        AttemptOut | None: the attempt, or None if it does not exist

    Raises:
        OpenRouterError: if grading fails
    """

    with SessionLocal() as session:
        row = session.execute(
            select(TaskAttempt, Task.question, Task.grading_notes)
            .join(Task, TaskAttempt.task_id == Task.id)
            .where(TaskAttempt.id == attempt_id)
        ).first()
        if row is None:
            return None

        attempt, question, grading_notes = row
        if attempt.verdict is not None:
            return _attempt_out(attempt)
        answer = attempt.answer

    grade = grade_answer(question, grading_notes, answer)

    with SessionLocal() as session, session.begin():
        session.execute(
            update(TaskAttempt)
            .where(TaskAttempt.id == attempt_id)
            .values(verdict=grade.verdict, feedback=grade.feedback)
        )
        return _attempt_out(session.get(TaskAttempt, attempt_id))
