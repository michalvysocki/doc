import uuid
from pathlib import Path
from typing import Any

import chromadb

from .indexing import chunk_text
from .openrouter import get_embeddings

chroma_dir = Path(__file__).resolve().parent.parent / ".chroma"
client = chromadb.PersistentClient(chroma_dir)
collection = client.get_or_create_collection(name="main")


def add_to_collection(text: str, filename: str) -> str:
    """
    Divides text into chunks, generates embeddings and metadata
    and adds it to a collection.

    Args:
        text (str): text to chunk and add to collection
        filename (str): file's name

    Returns:
        str: returns file's uuid
    """

    chunks = chunk_text(text)

    ids = []
    metadatas = []

    file_uuid = str(uuid.uuid4())[:8]
    embeddings = get_embeddings(chunks)

    for i, _ in enumerate(chunks):
        chunk_id = f"{file_uuid}_chunk_{i}"

        ids.append(chunk_id)
        metadatas.append(
            {"filename": filename, "chunk_index": i, "file_uuid": file_uuid}
        )

    collection.add(
        ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas
    )

    return file_uuid


def retrieve_chunks(
    query: str, file_uuids: list[str], n_results: int = 4
) -> list[dict[str, Any]]:
    """
    Takes a query, generates an embedding for it and searches
    the vector database with this embedding, only within the given documents.

    Args:
        query (str): a query for searching the database
        file_uuids (list[str]): uuids of documents to search in
        n_results (int): number of chunks to retrieve

    Returns:
        list[dict[str, Any]]: returns list of dictionaries with results
    """

    if not file_uuids:
        return []

    query_vector = get_embeddings([query])
    results = collection.query(
        query_embeddings=query_vector,
        n_results=n_results,
        where={"file_uuid": {"$in": file_uuids}},
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    formatted_results = []
    for doc, meta, distance in zip(documents, metadatas, distances):
        formatted_results.append({"text": doc, "metadata": meta, "distance": distance})

    return formatted_results


def get_filenames(file_uuids: list[str]) -> list[str]:
    """
    Returns names of the documents with the given uuids.

    Args:
        file_uuids (list[str]): uuids of documents

    Returns:
        list[str]: sorted list of unique filenames
    """

    if not file_uuids:
        return []

    results = collection.get(
        where={"file_uuid": {"$in": file_uuids}}, include=["metadatas"]
    )

    return sorted({meta["filename"] for meta in results["metadatas"]})


def delete_document(file_uuid: str) -> bool:
    """
    Checks if a document is in the vector store and
    deletes all chunks of file with a specified uuid.

    Args:
        file_uuid (str): file's unique identifier

    Returns:
        bool: returns True if executed correctly or False if file is not found
    """

    existing_data = collection.get(where={"file_uuid": file_uuid}, include=[])

    if not existing_data or len(existing_data.get("ids", [])) == 0:
        return False

    collection.delete(where={"file_uuid": file_uuid})

    return True


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
