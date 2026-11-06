import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The production app serving a fake frontend build from a temporary folder."""

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<p>index</p>")
    (tmp_path / "assets" / "app.js").write_text("console.log('app')")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
    # Imported here: serve.py reads FRONTEND_DIST when it loads.
    serve = importlib.reload(importlib.import_module("src.serve"))
    yield TestClient(serve.app)


def test_root_and_react_routes_get_index(client):
    for path in ["/", "/courses/abc", "/courses/abc/topics/1"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.text == "<p>index</p>"


def test_build_files_are_served(client):
    assert client.get("/assets/app.js").text == "console.log('app')"
    assert client.get("/favicon.svg").text == "<svg/>"


def test_api_is_under_prefix(client):
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    assert "/courses" in response.json()["paths"]


def test_path_outside_build_gets_index(client):
    response = client.get("/..%2F..%2Fsrc%2Fmain.py")
    assert response.text == "<p>index</p>"
