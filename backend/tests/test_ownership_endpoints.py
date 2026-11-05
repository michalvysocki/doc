import uuid
from datetime import UTC, datetime

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src import main
from src.schemas import CourseOut, CourseProgress, CourseSummary, TopicMap

OWNER = uuid.uuid4()
SOMEONE_ELSE = uuid.uuid4()
COURSE_ID = uuid.uuid4()


@pytest.fixture
def client(real_auth, monkeypatch):
    """A client logged in as OWNER."""

    monkeypatch.setattr(
        main, "session_user", lambda token: OWNER if token == "valid" else None
    )
    client = TestClient(main.app)
    client.cookies.set(main.SESSION_COOKIE, "valid")
    return client


def fake_course(course_id: uuid.UUID) -> CourseOut:
    return CourseOut(
        id=course_id,
        title="Stats",
        initial_prompt="Statistics",
        created_at=datetime(2026, 11, 5, tzinfo=UTC),
        topics=[],
        progress=CourseProgress(topics_total=0, topics_completed=0),
        sources=[],
    )


def protected_routes() -> list[tuple[str, str]]:
    routes = []
    for route in main.app.routes:
        if not isinstance(route, APIRoute) or route.path.startswith("/auth/"):
            continue
        path = route.path.replace("{attempt_id}", "1")
        while "{" in path:
            start, end = path.index("{"), path.index("}")
            path = path[:start] + str(uuid.uuid4()) + path[end + 1 :]
        routes.extend((method, path) for method in route.methods)
    return routes


@pytest.mark.parametrize(("method", "path"), protected_routes())
def test_every_route_needs_login(real_auth, method, path):
    response = TestClient(main.app).request(method, path)

    assert response.status_code == 401


def test_someone_elses_course_looks_missing(client, monkeypatch):
    monkeypatch.setattr(main, "course_owner", lambda course_id: SOMEONE_ELSE)
    monkeypatch.setattr(main, "get_course", pytest.fail)

    response = client.get(f"/courses/{COURSE_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Course not found"}


def test_own_course_is_returned(client, monkeypatch):
    monkeypatch.setattr(main, "course_owner", lambda course_id: OWNER)
    monkeypatch.setattr(main, "get_course", fake_course)

    response = client.get(f"/courses/{COURSE_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(COURSE_ID)


def test_course_list_is_the_users_own(client, monkeypatch):
    asked = []

    def courses(user_id):
        asked.append(user_id)
        return [
            CourseSummary(
                id=COURSE_ID,
                title="Stats",
                created_at=datetime(2026, 11, 5, tzinfo=UTC),
                reviews_due=0,
            )
        ]

    monkeypatch.setattr(main, "list_courses", courses)

    response = client.get("/courses")

    assert response.status_code == 200
    assert asked == [OWNER]


def test_new_course_belongs_to_the_user(client, monkeypatch):
    saved = []
    monkeypatch.setattr(
        main,
        "generate_topic_map",
        lambda prompt, on_status=None, about=None: (
            TopicMap(course_title="Stats", topics=[]),
            [],
        ),
    )
    monkeypatch.setattr(main, "get_about", lambda user_id: "")
    monkeypatch.setattr(
        main,
        "save_course",
        lambda user_id, *args: saved.append(user_id) or COURSE_ID,
    )
    monkeypatch.setattr(main, "get_course", fake_course)

    response = client.post("/courses", data={"initial_prompt": "Statistics"})

    assert response.status_code == 201
    assert saved == [OWNER]


def test_file_upload_to_someone_elses_course_looks_missing(client, monkeypatch):
    monkeypatch.setattr(main, "course_owner", lambda course_id: SOMEONE_ELSE)
    monkeypatch.setattr(main, "prepare_upload", pytest.fail)

    response = client.post(
        "/parse_file",
        data={"course_id": str(COURSE_ID)},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 404
