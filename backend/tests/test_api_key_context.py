"""The user's OpenRouter key must reach every place that calls the model."""

import uuid
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from src import main, openrouter
from src.openrouter import MissingApiKeyError, current_api_key

USERS = {"token-a": uuid.uuid4(), "token-b": uuid.uuid4()}
KEYS = {USERS["token-a"]: "sk-or-key-of-a", USERS["token-b"]: None}

# A separate app, so these routes do not join the real API (and its route tests).
app = FastAPI()
User = Annotated[uuid.UUID, Depends(main.current_user)]


@app.get("/key")
def read_key(user_id: User):
    return {"key": current_api_key.get()}


@app.get("/streamed-key")
def stream_key(user_id: User):
    def lines():
        yield str(current_api_key.get())

    return StreamingResponse(lines())


@app.get("/course-thread-key")
def course_thread_key(user_id: User):
    def work(on_status):
        return current_api_key.get()

    return {"events": list(main._run_with_status(work))}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "session_user", USERS.get)
    monkeypatch.setattr(main, "get_openrouter_key", KEYS.get)
    return TestClient(app)


def as_user(client: TestClient, token: str) -> TestClient:
    client.cookies.set(main.SESSION_COOKIE, token)
    return client


def test_headers_need_a_key():
    with pytest.raises(MissingApiKeyError, match="settings"):
        openrouter._headers()


def test_headers_use_the_key_of_the_context():
    token = current_api_key.set("sk-or-some-key")
    try:
        assert openrouter._headers()["Authorization"] == "Bearer sk-or-some-key"
    finally:
        current_api_key.reset(token)


def test_endpoint_sees_the_key_of_the_logged_in_user(client):
    assert as_user(client, "token-a").get("/key").json() == {"key": "sk-or-key-of-a"}
    # The next request of another user does not see the previous key.
    assert as_user(client, "token-b").get("/key").json() == {"key": None}


def test_streamed_response_sees_the_key(client):
    assert as_user(client, "token-a").get("/streamed-key").text == "sk-or-key-of-a"


def test_course_creation_thread_sees_the_key(client):
    events = as_user(client, "token-a").get("/course-thread-key").json()["events"]

    assert events == [{"type": "done", "course": "sk-or-key-of-a"}]
