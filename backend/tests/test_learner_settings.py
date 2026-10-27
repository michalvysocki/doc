import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src import main
from src.schemas import CourseOut, CourseProgress

client = TestClient(main.app)


def test_read_settings_returns_the_saved_text(monkeypatch):
    monkeypatch.setattr(main, "get_about", lambda: "ML engineer")

    assert client.get("/learner-settings").json() == {"about": "ML engineer"}


def test_put_settings_saves_the_stripped_text(monkeypatch):
    saved = []
    monkeypatch.setattr(main, "set_about", lambda about: saved.append(about) or about)

    response = client.put("/learner-settings", json={"about": "  ML engineer  "})

    assert response.json() == {"about": "ML engineer"}
    assert saved == ["ML engineer"]


def test_put_settings_allows_clearing(monkeypatch):
    monkeypatch.setattr(main, "set_about", lambda about: about)

    assert client.put("/learner-settings", json={"about": ""}).status_code == 200


def test_put_settings_rejects_too_long_text():
    response = client.put("/learner-settings", json={"about": "x" * 2001})

    assert response.status_code == 422


def test_patch_course_goal_returns_the_course(monkeypatch):
    course_id = uuid.uuid4()

    def update(cid, goal):
        return CourseOut(
            id=cid,
            title="Rust",
            initial_prompt=goal,
            created_at=datetime(2026, 10, 27, tzinfo=UTC),
            topics=[],
            progress=CourseProgress(topics_total=0, topics_completed=0),
        )

    monkeypatch.setattr(main, "update_course_goal", update)

    response = client.patch(
        f"/courses/{course_id}", json={"initial_prompt": " Publish a crate "}
    )

    assert response.json()["initial_prompt"] == "Publish a crate"


def test_patch_course_goal_rejects_empty_goal():
    response = client.patch(f"/courses/{uuid.uuid4()}", json={"initial_prompt": " "})

    assert response.status_code == 422


def test_patch_missing_course_returns_404(monkeypatch):
    monkeypatch.setattr(main, "update_course_goal", lambda cid, goal: None)

    response = client.patch(f"/courses/{uuid.uuid4()}", json={"initial_prompt": "x"})

    assert response.status_code == 404
