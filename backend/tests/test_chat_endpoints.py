import json
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src import main
from src.chat import NothingToRetryError
from src.openrouter import OpenRouterError
from src.schemas import ChatMessageOut, ChatReply

client = TestClient(main.app)


def message(message_id: int, role: str, content: str) -> ChatMessageOut:
    return ChatMessageOut(
        id=message_id,
        role=role,
        content=content,
        created_at=datetime(2026, 10, 24, tzinfo=UTC),
        attachments=[],
    )


def events_of(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines()]


def test_message_streams_events_as_json_lines(monkeypatch):
    user = message(1, "user", "Hi")
    reply = ChatReply(
        user_message=user,
        assistant_message=message(2, "assistant", "Hello"),
        course_changed=True,
    )

    def send(topic_id, content, file_uuids):
        yield {"type": "user_message", "message": user}
        yield {"type": "delta", "text": "Hello"}
        yield {"type": "done", "reply": reply}

    monkeypatch.setattr(main, "send_topic_message", send)

    response = client.post(
        f"/topics/{uuid.uuid4()}/messages", json={"content": "Hi", "file_uuids": []}
    )

    assert response.status_code == 201
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = events_of(response)
    assert [event["type"] for event in events] == ["user_message", "delta", "done"]
    assert events[0]["message"]["created_at"] == "2026-10-24T00:00:00Z"
    assert events[2]["reply"]["assistant_message"]["content"] == "Hello"
    assert events[2]["reply"]["course_changed"] is True


def test_model_failure_mid_stream_ends_with_an_error_event(monkeypatch):
    def send(course_id, content, file_uuids):
        yield {"type": "delta", "text": "Part"}
        raise OpenRouterError("OpenRouter stream broke off")

    monkeypatch.setattr(main, "send_course_message", send)

    response = client.post(
        f"/courses/{uuid.uuid4()}/messages", json={"content": "Hi", "file_uuids": []}
    )

    assert events_of(response)[-1] == {
        "type": "error",
        "detail": "OpenRouter stream broke off",
    }


def test_unexpected_failure_sends_a_general_error(monkeypatch):
    def retry(course_id):
        raise RuntimeError("database password is wrong")
        yield

    monkeypatch.setattr(
        main, "retry_course_message", lambda course_id: retry(course_id)
    )

    response = client.post(f"/courses/{uuid.uuid4()}/messages/retry")

    assert events_of(response) == [
        {"type": "error", "detail": "Something went wrong while answering"}
    ]


def test_missing_topic_returns_404_without_a_stream(monkeypatch):
    monkeypatch.setattr(main, "send_topic_message", lambda *args: None)

    response = client.post(
        f"/topics/{uuid.uuid4()}/messages", json={"content": "Hi", "file_uuids": []}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Topic not found"}


def test_retry_without_unanswered_message_returns_409(monkeypatch):
    def retry(topic_id):
        raise NothingToRetryError()

    monkeypatch.setattr(main, "retry_topic_message", retry)

    response = client.post(f"/topics/{uuid.uuid4()}/messages/retry")

    assert response.status_code == 409
