import io
import os
import tempfile

from fastapi import UploadFile
from llama_index.core import SimpleDirectoryReader
from markitdown import MarkItDown

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

md = MarkItDown()


class FileParsingError(Exception):
    """Raised when a file cannot be turned into text; the message is for the user."""


class FileTooLargeError(FileParsingError):
    """Raised when an uploaded file is over MAX_UPLOAD_BYTES."""


def read_upload(file: UploadFile) -> bytes:
    """
    Reads an uploaded file, refusing files over MAX_UPLOAD_BYTES without
    loading the rest into memory.

    Raises:
        FileTooLargeError: if the file is too large
    """

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise FileTooLargeError("File is too large (max 20 MB)")
    return data


def extract_text(filename: str, content_type: str | None, data: bytes) -> str:
    """
    Extracts text from a PDF, an Office document or a text file.

    Raises:
        FileParsingError: for images, unsupported or unreadable files and files
            without text
    """

    content_type = content_type or ""
    if content_type.startswith("image/"):
        raise FileParsingError("Image uploading is not supported")

    _, extension = os.path.splitext(filename)
    extension = extension.lower()

    try:
        if content_type == "application/pdf" or extension == ".pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(data)
                tmp_path = tmp_file.name

            try:
                documents = SimpleDirectoryReader(input_files=[tmp_path]).load_data()
                text = "\n".join([doc.text for doc in documents])
            finally:
                os.remove(tmp_path)

        elif content_type.startswith(
            "application/vnd.openxmlformats-officedocument"
        ) or extension in [".docx", ".xlsx", ".pptx"]:
            result = md.convert_stream(io.BytesIO(data), file_extension=extension)
            text = result.text_content

        elif content_type.startswith("text/") or extension in [
            ".md",
            ".txt",
            ".html",
            ".csv",
            ".json",
        ]:
            text = data.decode()

        else:
            raise ValueError(f"Unsupported file extension: {extension}")

    except ValueError as e:
        raise FileParsingError("Wrong file type") from e
    except Exception as e:
        raise FileParsingError(f"Failed to parse file: {e!s}") from e

    if not text or text.strip() == "":
        raise FileParsingError("Empty file or no readable text found")

    return text
