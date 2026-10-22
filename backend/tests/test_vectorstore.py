import uuid

import pytest

from src import vectorstore


def test_add_document_rejects_too_many_chunks_before_embedding(monkeypatch):
    calls = []
    monkeypatch.setattr(
        vectorstore,
        "chunk_text",
        lambda text: ["c"] * (vectorstore.MAX_CHUNKS_PER_DOCUMENT + 1),
    )
    monkeypatch.setattr(vectorstore, "get_embeddings", lambda texts: calls.append(1))

    with pytest.raises(vectorstore.DocumentTooLargeError, match="2001 fragments"):
        vectorstore.add_document("big", "big.txt", uuid.uuid4())

    assert calls == []
