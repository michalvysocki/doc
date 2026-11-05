import uuid

from sqlalchemy import select

from .database import SessionLocal
from .models import Course, LearnerSettings


def get_about(user_id: uuid.UUID) -> str:
    """Returns what the learner wrote about themselves, or an empty text."""

    with SessionLocal() as session:
        settings = session.get(LearnerSettings, user_id)
        return settings.about if settings else ""


def set_about(user_id: uuid.UUID, about: str) -> str:
    """Saves what the learner wrote about themselves (empty text clears it)."""

    with SessionLocal() as session, session.begin():
        settings = session.get(LearnerSettings, user_id)
        if settings is None:
            settings = LearnerSettings(user_id=user_id)
            session.add(settings)
        settings.about = about
    return about


def course_about(course_id: uuid.UUID) -> str:
    """What the owner of the course wrote about themselves: the course's learner."""

    with SessionLocal() as session:
        about = session.scalar(
            select(LearnerSettings.about)
            .join(Course, Course.user_id == LearnerSettings.user_id)
            .where(Course.id == course_id)
        )
    return about or ""
