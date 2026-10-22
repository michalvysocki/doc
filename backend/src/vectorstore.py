import uuid
from typing import Any

from sqlalchemy import and_, delete, select

from .database import SessionLocal
from .indexing import chunk_text
from .models import Chunk, Document
from .openrouter import get_embeddings
from .schemas import CourseFileOut

MAX_CHUNKS_PER_DOCUMENT = 2000


class DocumentTooLargeError(Exception):
    """Raised when a document would be split into too many chunks."""

    def __init__(self, chunks: int):
        super().__init__(
            f"The file has too much text ({chunks} fragments, "
            f"max {MAX_CHUNKS_PER_DOCUMENT})"
        )


def add_document(
    text: str,
    filename: str,
    course_id: uuid.UUID,
    topic_id: uuid.UUID | None = None,
    media_type: str | None = None,
    content: bytes | None = None,
    summary: str | None = None,
) -> str:
    """
    Divides text into chunks, generates embeddings and saves
    the document with its chunks in the database.

    Args:
        text (str): text to chunk and save
        filename (str): file's name
        course_id (uuid.UUID): course the document belongs to
        topic_id (uuid.UUID | None): topic, if the document is a generated lesson
        media_type (str | None): for images, their media type
        content (bytes | None): for images, the original image
        summary (str | None): for uploaded files, a short description

    Returns:
        str: returns document's uuid

    Raises:
        DocumentTooLargeError: if the text would be split into too many chunks
        OpenRouterError: if generating embeddings fails
    """

    chunks = chunk_text(text)
    if len(chunks) > MAX_CHUNKS_PER_DOCUMENT:
        raise DocumentTooLargeError(len(chunks))
    embeddings = get_embeddings(chunks)

    document_id = uuid.uuid4()
    document = Document(
        id=document_id,
        course_id=course_id,
        topic_id=topic_id,
        filename=filename,
        media_type=media_type,
        content=content,
        summary=summary,
        chunks=[
            Chunk(chunk_index=i, text=chunk, embedding=embedding)
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
        ],
    )

    with SessionLocal() as session, session.begin():
        session.add(document)

    return str(document_id)


def retrieve_chunks(
    query: str, file_uuids: list[uuid.UUID], n_results: int = 6
) -> list[dict[str, Any]]:
    """
    Takes a query, generates an embedding for it and finds the most similar
    chunks, only within the given documents.

    Args:
        query (str): a query for searching the database
        file_uuids (list[uuid.UUID]): uuids of documents to search in
        n_results (int): number of chunks to retrieve

    Returns:
        list[dict[str, Any]]: returns list of dictionaries with results
    """

    if not file_uuids:
        return []

    query_vector = get_embeddings([query])[0]
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")

    statement = (
        select(
            Chunk.text,
            Chunk.chunk_index,
            Document.id,
            Document.filename,
            Document.topic_id,
            distance,
        )
        .join(Chunk.document)
        .where(Chunk.document_id.in_(file_uuids))
        .order_by(distance)
        .limit(n_results)
    )

    with SessionLocal() as session:
        rows = session.execute(statement).all()

    return [
        {
            "text": row.text,
            "metadata": {
                "filename": row.filename,
                "chunk_index": row.chunk_index,
                "file_uuid": str(row.id),
                "is_lesson": row.topic_id is not None,
            },
            "distance": row.distance,
        }
        for row in rows
    ]


def list_course_files(course_id: uuid.UUID) -> list[CourseFileOut]:
    """Returns the files uploaded to a course (not lesson documents), oldest first."""

    with SessionLocal() as session:
        rows = session.execute(
            select(
                Document.id,
                Document.filename,
                Document.media_type,
                Document.summary,
                Document.created_at,
            )
            .where(Document.course_id == course_id, Document.topic_id.is_(None))
            .order_by(Document.created_at)
        ).all()
    return [
        CourseFileOut(
            id=row.id,
            filename=row.filename,
            media_type=row.media_type,
            summary=row.summary,
            created_at=row.created_at,
        )
        for row in rows
    ]


def get_image(file_uuid: uuid.UUID) -> tuple[bytes, str] | None:
    """
    Returns the bytes and media type of an uploaded image, or None if the
    document does not exist or is not an image.
    """

    with SessionLocal() as session:
        row = session.execute(
            select(Document.content, Document.media_type).where(
                Document.id == file_uuid, Document.content.is_not(None)
            )
        ).first()
    return (row.content, row.media_type) if row else None


MAX_FILES_IN_CONTEXT = 20
MAX_SUMMARY_CHARS_IN_CONTEXT = 600


def format_course_files(course_id: uuid.UUID) -> str | None:
    """
    Formats the summaries of the course's uploaded files as a prompt section,
    or returns None if no file has a summary.
    """

    with SessionLocal() as session:
        rows = session.execute(
            select(Document.filename, Document.summary)
            .where(
                Document.course_id == course_id,
                Document.topic_id.is_(None),
                Document.summary.is_not(None),
            )
            .order_by(Document.created_at)
            .limit(MAX_FILES_IN_CONTEXT)
        ).all()
    if not rows:
        return None
    lines = [
        f"- {row.filename}: {row.summary[:MAX_SUMMARY_CHARS_IN_CONTEXT]}"
        for row in rows
    ]
    return "COURSE FILES:\n" + "\n".join(lines)


def format_fragments(fragments: list[dict[str, Any]]) -> str:
    """Formats retrieved chunks as a labelled section for a model prompt."""

    texts = []
    for fragment in fragments:
        source = "lesson" if fragment["metadata"].get("is_lesson") else "document"
        name = fragment["metadata"]["filename"]
        texts.append(f"--- Fragment of the {source}: {name} ---\n{fragment['text']}")
    return "COURSE MATERIALS:\n" + "\n\n".join(texts)


def delete_document(file_uuid: uuid.UUID) -> bool:
    """
    Deletes an uploaded file (not a lesson document) with the given uuid.
    Its chunks are deleted by the database (ON DELETE CASCADE).

    Args:
        file_uuid (uuid.UUID): document's unique identifier

    Returns:
        bool: True if deleted, False if there is no such uploaded file
    """

    with SessionLocal() as session, session.begin():
        result = session.execute(
            delete(Document).where(
                Document.id == file_uuid, Document.topic_id.is_(None)
            )
        )

    return result.rowcount > 0


def get_course_document_ids(
    course_id: uuid.UUID,
    exclude_topic_id: uuid.UUID | None = None,
    files_only: bool = False,
) -> list[uuid.UUID]:
    """
    Returns ids of documents of the course: uploaded files and lessons, or only
    uploaded files. Optionally without the lesson of one topic.
    """

    condition = Document.course_id == course_id
    if exclude_topic_id is not None:
        condition = and_(
            condition, Document.topic_id.is_distinct_from(exclude_topic_id)
        )
    if files_only:
        condition = and_(condition, Document.topic_id.is_(None))

    with SessionLocal() as session:
        return list(session.scalars(select(Document.id).where(condition)))


if __name__ == "__main__":
    query = "Czym jest architektura RAG i jakie problemy rozwiązuje?"

    with SessionLocal() as session:
        file_uuids = list(session.scalars(select(Document.id)).all())

    found = retrieve_chunks(query, file_uuids)
    for i, result in enumerate(found, 1):
        print(f"\n Result: {i} | Distance: {result['distance']:.4f}")
        print(
            f"File: {result['metadata']['filename']} | Chunk: {result['metadata']['chunk_index']}"
        )
        print(f"Text: {result['text'][:150]}")
