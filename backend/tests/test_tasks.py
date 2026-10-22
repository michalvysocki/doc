from datetime import UTC, datetime

from src.tasks import next_review

NOW = datetime(2026, 10, 22, 15, 30, tzinfo=UTC)


def day(d: int) -> datetime:
    return datetime(2026, 10, d, tzinfo=UTC)


def test_correct_answers_climb_the_ladder_and_stay_at_thirty_days():
    streak, dates = 0, []
    for _ in range(6):
        streak, due = next_review(streak, "correct", NOW)
        dates.append((due - datetime(2026, 10, 22, tzinfo=UTC)).days)

    assert dates == [1, 3, 7, 14, 30, 30]
    assert streak == 6


def test_partially_correct_comes_back_tomorrow_and_keeps_the_streak():
    assert next_review(2, "partially_correct", NOW) == (2, day(23))


def test_incorrect_comes_back_tomorrow_and_starts_over():
    assert next_review(3, "incorrect", NOW) == (0, day(23))


def test_review_date_is_the_start_of_the_day():
    late = datetime(2026, 10, 22, 23, 59, tzinfo=UTC)

    assert next_review(0, "correct", late) == (1, day(23))
