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


def test_prepare_upload_transcribes_images_and_keeps_bytes(monkeypatch):
    received = {}

    def fake_transcribe(data, media_type):
        received.update(data=data, media_type=media_type)
        return "# Notes"

    monkeypatch.setattr(file_parsing, "transcribe_image", fake_transcribe)
    monkeypatch.setattr(file_parsing, "summarize_document", lambda name, text: "S")

    parsed = file_parsing.prepare_upload("notes.png", "image/png", b"PNG")

    assert parsed == file_parsing.ParsedFile("# Notes", "image/png", b"PNG", "S")
    assert received == {"data": b"PNG", "media_type": "image/png"}


def test_prepare_upload_rejects_unsupported_images(monkeypatch):
    monkeypatch.setattr(file_parsing, "transcribe_image", lambda *args: "text")

    with pytest.raises(FileParsingError, match="Unsupported image type"):
        file_parsing.prepare_upload("anim.gif", "image/gif", b"GIF")


def test_prepare_upload_rejects_images_without_content(monkeypatch):
    monkeypatch.setattr(file_parsing, "transcribe_image", lambda *args: None)

    with pytest.raises(FileParsingError, match="No readable content"):
        file_parsing.prepare_upload("floor.jpg", "image/jpeg", b"JPG")


def test_prepare_upload_parses_documents_without_bytes(monkeypatch):
    monkeypatch.setattr(
        file_parsing, "summarize_document", lambda name, text: f"About {name}"
    )

    parsed = file_parsing.prepare_upload("notes.txt", "text/plain", b"Hello")

    assert parsed == file_parsing.ParsedFile("Hello", summary="About notes.txt")


def test_prepare_upload_keeps_the_file_when_summarizing_fails(monkeypatch):
    def fail(name, text):
        raise file_parsing.OpenRouterError("timeout")

    monkeypatch.setattr(file_parsing, "summarize_document", fail)

    parsed = file_parsing.prepare_upload("notes.txt", "text/plain", b"Hello")

    assert parsed == file_parsing.ParsedFile("Hello")
