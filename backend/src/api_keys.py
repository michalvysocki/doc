import os
import uuid

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, update

from .database import SessionLocal
from .models import User


def _fernet() -> Fernet:
    secret = os.getenv("OPENROUTER_KEYS_SECRET")
    if not secret:
        raise RuntimeError("OPENROUTER_KEYS_SECRET is not set in backend/.env")
    return Fernet(secret)


def set_openrouter_key(user_id: uuid.UUID, key: str | None) -> None:
    """Saves the user's OpenRouter key encrypted; None removes it."""

    encrypted = _fernet().encrypt(key.encode()) if key else None
    with SessionLocal() as session, session.begin():
        session.execute(
            update(User).where(User.id == user_id).values(openrouter_key=encrypted)
        )


def get_openrouter_key(user_id: uuid.UUID) -> str | None:
    """
    The user's OpenRouter key, or None when there is none or it can no longer be
    read (the secret changed); then the user enters it again.
    """

    with SessionLocal() as session:
        encrypted = session.scalar(
            select(User.openrouter_key).where(User.id == user_id)
        )
    if encrypted is None:
        return None
    try:
        return _fernet().decrypt(encrypted).decode()
    except InvalidToken:
        return None


def key_hint(key: str | None) -> str | None:
    """Only the end of the key, so the user can tell which key is saved."""

    return f"…{key[-4:]}" if key else None
