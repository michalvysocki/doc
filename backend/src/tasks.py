import uuid
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .courses import due_condition, get_course, get_file_materials, get_topic
from .database import SessionLocal
from .models import Task, TaskAttempt, Topic
from .openrouter import generate_tasks, grade_answer
from .schemas import AttemptOut, GeneratedTask, ReviewTaskOut, TaskOut

REVIEW_LADDER_DAYS = [1, 3, 7, 14, 30]


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


def _attempts_by_task(
    session: Session, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[AttemptOut]]:
    """Returns the attempts of the given tasks, oldest first, grouped by task."""

    attempts = defaultdict(list)
    if task_ids:
        for attempt in session.scalars(
            select(TaskAttempt)
            .where(TaskAttempt.task_id.in_(task_ids))
            .order_by(TaskAttempt.id)
        ):
            attempts[attempt.task_id].append(_attempt_out(attempt))
    return attempts


def get_due_reviews(course_id: uuid.UUID) -> list[ReviewTaskOut]:
    """Returns the course's tasks due for review, the longest overdue first."""

    with SessionLocal() as session:
        rows = session.execute(
            select(Task, Topic.title)
            .join(Topic, Task.topic_id == Topic.id)
            .where(Topic.course_id == course_id, due_condition(datetime.now(UTC)))
            .order_by(Task.review_due_at, Topic.position, Task.position)
        ).all()
        attempts = _attempts_by_task(session, [task.id for task, _ in rows])

        return [
            ReviewTaskOut(
                id=task.id,
                position=task.position,
                question=task.question,
                attempts=attempts[task.id],
                topic_id=task.topic_id,
                topic_title=title,
                review_streak=task.review_streak,
                review_due_at=task.review_due_at,
            )
            for task, title in rows
        ]


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

        attempts = _attempts_by_task(session, [task.id for task in tasks])

        return [
            TaskOut(
                id=task.id,
                position=task.position,
                question=task.question,
                attempts=attempts[task.id],
            )
            for task in tasks
        ]


def create_tasks(
    topic_id: uuid.UUID,
    regenerate: bool = False,
    instructions: str | None = None,
    use_files: bool = False,
) -> list[TaskOut] | None:
    """
    Generates tasks for a topic. Without regenerate returns the existing active
    tasks if there are any. With regenerate archives the current tasks first.
    Optionally follows the learner's instructions and uses fragments of the
    course's uploaded files.

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

    materials = (
        get_file_materials(topic.course_id, f"{topic.title}\n{topic.description}")[0]
        if use_files
        else None
    )
    course = get_course(topic.course_id)
    generated = generate_tasks(
        course_title=topic.course_title,
        path=[link.title for link in topic.path],
        title=topic.title,
        lesson=topic.explanation,
        instructions=instructions,
        materials=materials,
        goal=course.initial_prompt if course else None,
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


def add_tasks(topic_id: uuid.UUID, tasks: list[GeneratedTask]) -> list[int]:
    """
    Appends tasks after the active tasks of a topic.

    Returns:
        list[int]: numbers of the new tasks, as the learner sees them

    Raises:
        LessonMissingError: if the topic does not exist or has no lesson yet
    """

    with SessionLocal() as session, session.begin():
        topic = session.get(Topic, topic_id)
        if topic is None or topic.explanation is None:
            raise LessonMissingError()

        last = session.scalar(
            select(func.max(Task.position)).where(
                Task.topic_id == topic_id, Task.archived_at.is_(None)
            )
        )
        start = 0 if last is None else last + 1
        session.add_all(
            Task(
                topic_id=topic_id,
                position=start + i,
                question=task.question,
                grading_notes=task.grading_notes,
            )
            for i, task in enumerate(tasks)
        )

    return [start + i + 1 for i in range(len(tasks))]


def next_review(streak: int, verdict: str, now: datetime) -> tuple[int, datetime]:
    """
    Returns the new streak of correct answers and the next review date after a
    graded attempt: correct answers climb the ladder, a partially correct one
    comes back tomorrow, an incorrect one comes back tomorrow and starts over.
    The date is the start of that day (UTC), so a task is due for the whole day.
    """

    if verdict == "correct":
        streak += 1
        days = REVIEW_LADDER_DAYS[min(streak, len(REVIEW_LADDER_DAYS)) - 1]
    else:
        days = 1
        if verdict == "incorrect":
            streak = 0

    day = (now + timedelta(days=days)).date()
    return streak, datetime.combine(day, time.min, tzinfo=UTC)


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
        attempt = session.get(TaskAttempt, attempt_id)
        attempt.verdict, attempt.feedback = grade.verdict, grade.feedback
        task = session.get(Task, attempt.task_id)
        task.review_streak, task.review_due_at = next_review(
            task.review_streak, grade.verdict, datetime.now(UTC)
        )
        return _attempt_out(attempt)
