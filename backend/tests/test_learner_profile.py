from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from src.learner_profile import build_learner_profile

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


def row(topic, verdict=None, streak=0, due_in_days=None):
    due = None if due_in_days is None else NOW + timedelta(days=due_in_days)
    return SimpleNamespace(
        topic_title=topic, verdict=verdict, review_streak=streak, review_due_at=due
    )


def test_nothing_graded_gives_no_profile():
    assert build_learner_profile([row("A"), row("B")], NOW) is None


def test_struggles_are_counted_per_topic():
    rows = [
        row("Borrowing", "incorrect", due_in_days=-1),
        row("Borrowing", "incorrect", due_in_days=-1),
        row("Borrowing", "partially_correct", due_in_days=1),
        row("Lifetimes", "correct", streak=1, due_in_days=2),
    ]

    profile = build_learner_profile(rows, NOW)

    assert profile == (
        "LEARNER PROFILE (from practice tasks):\n"
        "- Struggles with: Borrowing (2 incorrect, 1 partially correct)\n"
        "- Due for review: 2 tasks in 1 topics"
    )


def test_strong_needs_all_correct_and_a_passed_review():
    rows = [
        row("Variables", "correct", streak=2, due_in_days=3),
        row("Variables", "correct", streak=1, due_in_days=1),
        row("Functions", "correct", streak=1, due_in_days=1),
        row("Loops", "correct", streak=3, due_in_days=7),
        row("Loops", None),
    ]

    profile = build_learner_profile(rows, NOW)

    assert profile == "LEARNER PROFILE (from practice tasks):\n- Strong: Variables"
