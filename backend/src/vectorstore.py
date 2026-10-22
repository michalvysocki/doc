import uuid
from typing import Any

from sqlalchemy import and_, delete, select

from .database import SessionLocal
from .indexing import chunk_text
from .models import Chunk, Document
from .openrouter import get_embeddings


def add_document(
    text: str, filename: str, course_id: uuid.UUID, topic_id: uuid.UUID | None = None
) -> str:
    """
    Divides text into chunks, generates embeddings and saves
    the document with its chunks in the database.

    Args:
        text (str): text to chunk and save
        filename (str): file's name
        course_id (uuid.UUID): course the document belongs to
        topic_id (uuid.UUID | None): topic, if the document is a generated lesson

    Returns:
        str: returns document's uuid
    """

    chunks = chunk_text(text)
    embeddings = get_embeddings(chunks)

    document_id = uuid.uuid4()
    document = Document(
        id=document_id,
        course_id=course_id,
        topic_id=topic_id,
        filename=filename,
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
    Deletes the document with a specified uuid. Its chunks are deleted
    by the database (ON DELETE CASCADE).

    Args:
        file_uuid (uuid.UUID): document's unique identifier

    Returns:
        bool: returns True if deleted or False if document is not found
    """

    with SessionLocal() as session, session.begin():
        result = session.execute(delete(Document).where(Document.id == file_uuid))

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
