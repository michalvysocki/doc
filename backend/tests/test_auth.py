import uuid

import pytest
from fastapi.testclient import TestClient

from src import main
from src.users import EmailTakenError

USER_ID = uuid.uuid4()
CREDENTIALS = {"email": " Ala@X.pl ", "password": "correct horse"}


@pytest.fixture
def client(real_auth):
    return TestClient(main.app)


@pytest.fixture
def sessions(monkeypatch):
    """Fake session store: token -> user id."""

    store = {}

    def start(user_id):
        token = f"token-{len(store)}"
        store[token] = user_id
        return token

    monkeypatch.setattr(main, "start_session", start)
    monkeypatch.setattr(main, "session_user", store.get)
    monkeypatch.setattr(main, "end_session", lambda token: store.pop(token, None))
    return store


def test_register_logs_in_with_an_http_only_cookie(client, sessions, monkeypatch):
    created = []
    monkeypatch.setattr(
        main,
        "create_user",
        lambda email, password: created.append((email, password)) or USER_ID,
    )

    response = client.post("/auth/register", json=CREDENTIALS)

    assert response.status_code == 201
    assert response.json() == {"id": str(USER_ID), "email": "ala@x.pl"}
    assert created == [("Ala@X.pl", "correct horse")]
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{main.SESSION_COOKIE}=token-0")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert sessions == {"token-0": USER_ID}


def test_register_with_taken_email_is_a_conflict(client, sessions, monkeypatch):
    def taken(email, password):
        raise EmailTakenError(email)

    monkeypatch.setattr(main, "create_user", taken)

    response = client.post("/auth/register", json=CREDENTIALS)

    assert response.status_code == 409
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "password": "correct horse"},
        {"email": "ala@x.pl", "password": "short"},
    ],
)
def test_register_rejects_bad_input(client, monkeypatch, body):
    monkeypatch.setattr(main, "create_user", pytest.fail)

    assert client.post("/auth/register", json=body).status_code == 422


def test_login_with_wrong_password_sets_no_cookie(client, sessions, monkeypatch):
    monkeypatch.setattr(main, "authenticate", lambda email, password: None)

    response = client.post("/auth/login", json=CREDENTIALS)

    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    assert sessions == {}


def test_login_starts_a_session(client, sessions, monkeypatch):
    monkeypatch.setattr(main, "authenticate", lambda email, password: USER_ID)

    response = client.post("/auth/login", json=CREDENTIALS)

    assert response.status_code == 200
    assert response.json() == {"id": str(USER_ID), "email": "ala@x.pl"}
    assert sessions == {"token-0": USER_ID}


def test_me_needs_a_valid_session(client, sessions, monkeypatch):
    monkeypatch.setattr(main, "user_email", lambda user_id: "ala@x.pl")

    assert client.get("/auth/me").status_code == 401
    client.cookies.set(main.SESSION_COOKIE, "unknown")
    assert client.get("/auth/me").status_code == 401

    sessions["valid"] = USER_ID
    client.cookies.set(main.SESSION_COOKIE, "valid")
    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json() == {"id": str(USER_ID), "email": "ala@x.pl"}


def test_logout_ends_the_session_and_clears_the_cookie(client, sessions):
    sessions["valid"] = USER_ID
    client.cookies.set(main.SESSION_COOKIE, "valid")

    response = client.post("/auth/logout")

    assert response.status_code == 204
    assert sessions == {}
    assert response.headers["set-cookie"].startswith(f'{main.SESSION_COOKIE}=""')


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [("http://localhost:5173", True), ("https://evil.example", False)],
)
def test_cors_allows_only_the_frontend(client, origin, allowed):
    response = client.options(
        "/auth/me",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )

    assert (response.headers.get("access-control-allow-origin") == origin) is allowed
