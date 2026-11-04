import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from .database import SessionLocal
from .models import User, UserSession

SESSION_DAYS = 30

_hasher = PasswordHasher()
# Checked when the email is unknown, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash("dummy password")


class EmailTakenError(Exception):
    """Raised when an account with this email already exists."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(email: str, password: str) -> uuid.UUID:
    """Creates an account and returns its id; only the password hash is saved."""

    user_id = uuid.uuid4()
    email = normalize_email(email)
    try:
        with SessionLocal() as session, session.begin():
            session.add(
                User(id=user_id, email=email, password_hash=_hasher.hash(password))
            )
    except IntegrityError as error:
        raise EmailTakenError(email) from error
    return user_id


def _find_user(email: str) -> User | None:
    with SessionLocal() as session:
        return session.scalar(select(User).where(User.email == normalize_email(email)))


def authenticate(email: str, password: str) -> uuid.UUID | None:
    """The id of the account when the email and password match, otherwise None."""

    user = _find_user(email)
    try:
        _hasher.verify(user.password_hash if user else _DUMMY_HASH, password)
    except VerifyMismatchError:
        return None
    return user.id if user else None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(user_id: uuid.UUID) -> str:
    """Starts a login for the user and returns its token (for the cookie)."""

    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    with SessionLocal() as session, session.begin():
        session.execute(
            delete(UserSession).where(
                UserSession.user_id == user_id, UserSession.expires_at <= now
            )
        )
        session.add(
            UserSession(
                user_id=user_id,
                token_hash=_token_hash(token),
                expires_at=now + timedelta(days=SESSION_DAYS),
            )
        )
    return token


def session_user(token: str) -> uuid.UUID | None:
    """The id of the logged-in user, or None for an unknown or expired token."""

    with SessionLocal() as session:
        return session.scalar(
            select(UserSession.user_id).where(
                UserSession.token_hash == _token_hash(token),
                UserSession.expires_at > datetime.now(UTC),
            )
        )


def end_session(token: str) -> None:
    """Logs out: the token stops working (unknown tokens are ignored)."""

    with SessionLocal() as session, session.begin():
        session.execute(
            delete(UserSession).where(UserSession.token_hash == _token_hash(token))
        )


def user_email(user_id: uuid.UUID) -> str | None:
    with SessionLocal() as session:
        return session.scalar(select(User.email).where(User.id == user_id))
