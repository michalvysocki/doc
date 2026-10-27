import json
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src import main
from src.file_parsing import FileParsingError, ParsedFile
from src.schemas import CourseOut, CourseProgress, TopicMap

client = TestClient(main.app)


def events_of(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines()]


def fake_course(course_id: uuid.UUID) -> CourseOut:
    return CourseOut(
        id=course_id,
        title="Stats",
        initial_prompt="Statistics",
        created_at=datetime(2026, 10, 24, tzinfo=UTC),
        topics=[],
        progress=CourseProgress(topics_total=0, topics_completed=0),
        sources=[],
    )


def test_course_without_files_streams_statuses_then_the_course(monkeypatch):
    course_id = uuid.uuid4()

    def generate(prompt, on_status=None, about=None):
        on_status("Planning the course map…")
        on_status("Checking the map…")
        return TopicMap(course_title="Stats", topics=[]), []

    monkeypatch.setattr(main, "generate_topic_map", generate)
    monkeypatch.setattr(main, "get_about", lambda: "")
    monkeypatch.setattr(main, "save_course", lambda *args: course_id)
    monkeypatch.setattr(main, "get_course", fake_course)

    response = client.post("/courses", data={"initial_prompt": "Statistics"})

    assert response.status_code == 201
    events = events_of(response)
    assert events[:2] == [
        {"type": "status", "text": "Planning the course map…"},
        {"type": "status", "text": "Checking the map…"},
    ]
    assert events[2]["type"] == "done"
    assert events[2]["course"]["id"] == str(course_id)


def test_course_with_a_file_reads_it_first(monkeypatch):
    course_id = uuid.uuid4()
    monkeypatch.setattr(
        main, "prepare_upload", lambda *args: ParsedFile("notes", summary=None)
    )
    monkeypatch.setattr(
        main,
        "create_course_with_files",
        lambda prompt, texts, on_status: course_id,
    )
    monkeypatch.setattr(main, "get_course", fake_course)

    response = client.post(
        "/courses",
        data={"initial_prompt": "Statistics"},
        files=[("files", ("notes.txt", b"notes", "text/plain"))],
    )

    events = events_of(response)
    assert events[0] == {"type": "status", "text": "Reading notes.txt (1/1)…"}
    assert events[-1]["type"] == "done"


def test_file_that_cannot_be_read_ends_with_an_error(monkeypatch):
    def prepare(*args):
        raise FileParsingError("No readable content found in the image")

    monkeypatch.setattr(main, "prepare_upload", prepare)

    response = client.post(
        "/courses",
        data={"initial_prompt": "Statistics"},
        files=[("files", ("board.png", b"x", "image/png"))],
    )

    assert events_of(response)[-1] == {
        "type": "error",
        "detail": "board.png: No readable content found in the image",
    }


def test_too_long_prompt_is_rejected_before_streaming():
    response = client.post("/courses", data={"initial_prompt": "x" * 5000})

    assert response.status_code == 422


def test_too_many_files_are_rejected_before_streaming():
    files = [
        ("files", (f"f{number}.txt", b"x", "text/plain"))
        for number in range(main.MAX_FILES_PER_COURSE + 1)
    ]

    response = client.post(
        "/courses", data={"initial_prompt": "Statistics"}, files=files
    )

    assert response.status_code == 400
