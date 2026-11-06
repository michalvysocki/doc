"""
Production entry point: one address serves the API under /api and the built
frontend everywhere else, so the login cookie stays first-party.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .main import app as api

FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", "/app/frontend_dist")).resolve()

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", api)
app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str) -> FileResponse:
    """
    Returns a file from the frontend build, or index.html for any other path
    so that React Router shows the right page (e.g. /courses/<id> after a refresh).
    """
    file = (FRONTEND_DIST / path).resolve()
    if file.is_file() and file.is_relative_to(FRONTEND_DIST):
        return FileResponse(file)
    return FileResponse(FRONTEND_DIST / "index.html")
