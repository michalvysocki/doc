import uuid

import pytest

from src import main, openrouter


@pytest.fixture(autouse=True)
def block_real_openrouter_calls(monkeypatch):
    """Fails any test that would send a real (paid) request to OpenRouter."""

    def blocked(url, payload, timeout):
        pytest.fail(f"Test tried to call OpenRouter for real: {url}")

    monkeypatch.setattr(openrouter, "_post_to_openrouter", blocked)
    monkeypatch.setattr(openrouter, "_stream_from_openrouter", blocked)


@pytest.fixture(autouse=True)
def reviews_off(monkeypatch):
    """Generation tests see one model call; review tests turn reviews on themselves."""

    monkeypatch.setattr(openrouter, "REVIEW_ENABLED", False)


TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

OWNERSHIP_CHECKS = [
    main.owned_course,
    main.owned_topic,
    main.owned_task,
    main.owned_attempt,
    main.owned_document,
    main.owned_topic_deletion,
    main.owned_course_rebuild,
    main.owned_regeneration,
]


@pytest.fixture(autouse=True)
def logged_in():
    """
    Endpoint tests run as one logged-in user who owns everything; tests of
    login and ownership use real_auth instead.
    """

    main.app.dependency_overrides[main.current_user] = lambda: TEST_USER_ID
    for check in OWNERSHIP_CHECKS:
        main.app.dependency_overrides[check] = lambda: None
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def real_auth(logged_in):
    """Turns the fake login and ownership off for one test."""

    main.app.dependency_overrides.clear()
