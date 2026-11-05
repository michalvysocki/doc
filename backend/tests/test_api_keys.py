import pytest
from conftest import TEST_USER_ID
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from src import api_keys, main

client = TestClient(main.app)
FAKE_KEY = "sk-or-v1-0123456789abcdef"


def test_key_hint_shows_only_the_end():
    assert api_keys.key_hint(FAKE_KEY) == "…cdef"
    assert api_keys.key_hint(None) is None


def test_encrypted_key_does_not_contain_the_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEYS_SECRET", Fernet.generate_key().decode())

    encrypted = api_keys._fernet().encrypt(FAKE_KEY.encode())

    assert FAKE_KEY.encode() not in encrypted
    assert api_keys._fernet().decrypt(encrypted).decode() == FAKE_KEY


def test_missing_secret_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("OPENROUTER_KEYS_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="OPENROUTER_KEYS_SECRET"):
        api_keys._fernet()


def test_put_key_saves_it_and_returns_only_the_hint(monkeypatch):
    saved = []
    monkeypatch.setattr(
        main, "set_openrouter_key", lambda user_id, key: saved.append((user_id, key))
    )

    response = client.put("/settings/openrouter-key", json={"key": f" {FAKE_KEY} "})

    assert response.status_code == 200
    assert response.json() == {"key_hint": "…cdef"}
    assert saved == [(TEST_USER_ID, FAKE_KEY)]


def test_get_key_never_returns_the_whole_key(monkeypatch):
    monkeypatch.setattr(main, "get_openrouter_key", lambda user_id: FAKE_KEY)

    response = client.get("/settings/openrouter-key")

    assert response.json() == {"key_hint": "…cdef"}
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize("key", ["sk-proj-0123456789abcdef", "sk-or-short", ""])
def test_put_rejects_what_is_not_an_openrouter_key(monkeypatch, key):
    monkeypatch.setattr(main, "set_openrouter_key", pytest.fail)

    response = client.put("/settings/openrouter-key", json={"key": key})

    assert response.status_code == 422


def test_delete_key_removes_it(monkeypatch):
    saved = []
    monkeypatch.setattr(
        main, "set_openrouter_key", lambda user_id, key: saved.append((user_id, key))
    )

    response = client.delete("/settings/openrouter-key")

    assert response.status_code == 204
    assert saved == [(TEST_USER_ID, None)]
