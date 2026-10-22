import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from .database import SessionLocal
from .models import Task, TaskAttempt, Topic

MAX_TOPICS_PER_LINE = 8
VERDICT_NAMES = {"incorrect": "incorrect", "partially_correct": "partially correct"}


def _describe(counts: Counter) -> str:
    """Describes mistakes in a topic, e.g. '2 incorrect, 1 partially correct'."""

    return ", ".join(
        f"{counts[verdict]} {name}"
        for verdict, name in VERDICT_NAMES.items()
        if counts[verdict]
    )


def build_learner_profile(rows: list[Any], now: datetime) -> str | None:
    """
    Builds the learner profile section from active tasks of a course (rows with
    topic_title, verdict of the latest graded attempt or None, review_streak and
    review_due_at), in outline order. Returns None if nothing was graded yet.
    """

    if not any(row.verdict for row in rows):
        return None

    struggles: dict[str, Counter] = defaultdict(Counter)
    by_topic: dict[str, list[Any]] = defaultdict(list)
    due_tasks, due_topics = 0, set()
    for row in rows:
        by_topic[row.topic_title].append(row)
        if row.verdict in VERDICT_NAMES:
            struggles[row.topic_title][row.verdict] += 1
        if row.review_due_at is not None and row.review_due_at <= now:
            due_tasks += 1
            due_topics.add(row.topic_title)

    strong = [
        title
        for title, tasks in by_topic.items()
        if all(task.verdict == "correct" for task in tasks)
        and any(task.review_streak >= 2 for task in tasks)
    ]

    lines = []
    if struggles:
        topics = list(struggles.items())[:MAX_TOPICS_PER_LINE]
        lines.append(
            "- Struggles with: "
            + ", ".join(f"{title} ({_describe(counts)})" for title, counts in topics)
        )
    if due_tasks:
        lines.append(f"- Due for review: {due_tasks} tasks in {len(due_topics)} topics")
    if strong:
        lines.append("- Strong: " + ", ".join(strong[:MAX_TOPICS_PER_LINE]))

    if not lines:
        return None
    return "LEARNER PROFILE (from practice tasks):\n" + "\n".join(lines)


def format_learner_profile(course_id: uuid.UUID) -> str | None:
    """
    Loads the course's active tasks with the verdict of their latest graded
    attempt and builds the learner profile section.
    """

    latest = (
        select(
            TaskAttempt.task_id,
            TaskAttempt.verdict,
            func.row_number()
            .over(partition_by=TaskAttempt.task_id, order_by=TaskAttempt.id.desc())
            .label("rank"),
        )
        .where(TaskAttempt.verdict.is_not(None))
        .subquery()
    )

    with SessionLocal() as session:
        rows = session.execute(
            select(
                Topic.title.label("topic_title"),
                latest.c.verdict,
                Task.review_streak,
                Task.review_due_at,
            )
            .join(Topic, Task.topic_id == Topic.id)
            .outerjoin(latest, (latest.c.task_id == Task.id) & (latest.c.rank == 1))
            .where(Topic.course_id == course_id, Task.archived_at.is_(None))
            .order_by(Topic.position, Task.position)
        ).all()

    return build_learner_profile(rows, datetime.now(UTC))
