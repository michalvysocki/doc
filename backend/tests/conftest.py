import pytest

from src import openrouter


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
