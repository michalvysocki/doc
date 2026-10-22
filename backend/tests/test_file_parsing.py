import io

import pytest

from src import file_parsing
from src.file_parsing import FileParsingError, extract_text


def test_extract_text_reads_text_files():
    assert extract_text("notes.md", "text/markdown", "Zażółć".encode()) == "Zażółć"


def test_extract_text_uses_extension_when_type_is_missing():
    assert extract_text("notes.txt", None, b"Hello") == "Hello"


@pytest.mark.parametrize(
    ("filename", "content_type", "data", "message"),
    [
        ("photo.png", "image/png", b"x", "Image uploading is not supported"),
        ("archive.zip", "application/zip", b"x", "Wrong file type"),
        ("empty.txt", "text/plain", b"   ", "Empty file or no readable text found"),
    ],
)
def test_extract_text_rejects_unusable_files(filename, content_type, data, message):
    with pytest.raises(FileParsingError, match=message):
        extract_text(filename, content_type, data)


def test_read_upload_refuses_too_large_files(monkeypatch):
    monkeypatch.setattr(file_parsing, "MAX_UPLOAD_BYTES", 10)
    upload = type("Upload", (), {"file": io.BytesIO(b"x" * 11)})()

    with pytest.raises(file_parsing.FileTooLargeError, match="too large"):
        file_parsing.read_upload(upload)


def test_read_upload_returns_small_files(monkeypatch):
    monkeypatch.setattr(file_parsing, "MAX_UPLOAD_BYTES", 10)
    upload = type("Upload", (), {"file": io.BytesIO(b"x" * 10)})()

    assert file_parsing.read_upload(upload) == b"x" * 10
