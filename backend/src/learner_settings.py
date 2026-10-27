from .database import SessionLocal
from .models import LearnerSettings

SETTINGS_ID = 1


def get_about() -> str:
    """Returns what the learner wrote about themselves, or an empty text."""

    with SessionLocal() as session:
        settings = session.get(LearnerSettings, SETTINGS_ID)
        return settings.about if settings else ""


def set_about(about: str) -> str:
    """Saves what the learner wrote about themselves (empty text clears it)."""

    with SessionLocal() as session, session.begin():
        settings = session.get(LearnerSettings, SETTINGS_ID)
        if settings is None:
            settings = LearnerSettings(id=SETTINGS_ID)
            session.add(settings)
        settings.about = about
    return about
