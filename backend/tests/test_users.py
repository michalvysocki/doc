import uuid

from src import users
from src.models import User


def fake_user(password: str) -> User:
    return User(
        id=uuid.uuid4(),
        email="ala@x.pl",
        password_hash=users._hasher.hash(password),
    )


def test_normalize_email_trims_and_lowercases():
    assert users.normalize_email(" Ala@X.pl ") == "ala@x.pl"


def test_authenticate_checks_the_password(monkeypatch):
    user = fake_user("correct horse")
    monkeypatch.setattr(users, "_find_user", lambda email: user)

    assert users.authenticate("ala@x.pl", "correct horse") == user.id
    assert users.authenticate("ala@x.pl", "wrong horse") is None


def test_authenticate_rejects_unknown_email(monkeypatch):
    monkeypatch.setattr(users, "_find_user", lambda email: None)

    assert users.authenticate("nobody@x.pl", "dummy password") is None


def test_password_is_saved_only_as_argon2_hash():
    user = fake_user("correct horse")

    assert user.password_hash.startswith("$argon2id$")
    assert "correct horse" not in user.password_hash


def test_token_hash_is_stable_and_hides_the_token():
    token = "some-random-token"

    assert users._token_hash(token) == users._token_hash(token)
    assert len(users._token_hash(token)) == 64
    assert token not in users._token_hash(token)
    assert users._token_hash(token) != users._token_hash("other-token")
