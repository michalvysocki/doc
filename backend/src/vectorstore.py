import uuid
from pathlib import Path
from typing import Any

import chromadb
from sqlalchemy import delete, select

from .database import SessionLocal
from .indexing import chunk_text
from .models import Chunk, Document
from .openrouter import get_embeddings

chroma_dir = Path(__file__).resolve().parent.parent / ".chroma"
client = chromadb.PersistentClient(chroma_dir)
collection = client.get_or_create_collection(name="main")


def add_to_collection(text: str, filename: str) -> str:
    """
    Divides text into chunks, generates embeddings and saves
    the document with its chunks in the database.

    Args:
        text (str): text to chunk and save
        filename (str): file's name

    Returns:
        str: returns document's uuid
    """

    chunks = chunk_text(text)
    embeddings = get_embeddings(chunks)

    document_id = uuid.uuid4()
    document = Document(
        id=document_id,
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
    query: str, file_uuids: list[uuid.UUID], n_results: int = 4
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
        select(Chunk.text, Chunk.chunk_index, Document.id, Document.filename, distance)
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
            },
            "distance": row.distance,
        }
        for row in rows
    ]


def get_filenames(file_uuids: list[uuid.UUID]) -> list[str]:
    """
    Returns names of the documents with the given uuids.

    Args:
        file_uuids (list[uuid.UUID]): uuids of documents

    Returns:
        list[str]: sorted list of filenames
    """

    if not file_uuids:
        return []

    statement = (
        select(Document.filename)
        .where(Document.id.in_(file_uuids))
        .order_by(Document.filename)
    )

    with SessionLocal() as session:
        return list(session.scalars(statement).all())


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


if __name__ == "__main__":
    query = "Czym jest architektura RAG i jakie problemy rozwiązuje?"

    all_metadatas = collection.get(include=["metadatas"])["metadatas"]
    file_uuids = list({meta["file_uuid"] for meta in all_metadatas})
    found = retrieve_chunks(query, file_uuids)
    for i, result in enumerate(found, 1):
        print(f"\n Result: {i} | Distance: {result['distance']:.4f}")
        print(
            f"File: {result['metadata']['filename']} | Chunk: {result['metadata']['chunk_index']}"
        )
        print(f"Text: {result['text'][:150]}")
