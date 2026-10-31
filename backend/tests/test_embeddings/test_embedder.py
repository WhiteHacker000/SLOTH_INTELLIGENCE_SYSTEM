import sys

import numpy as np
import pytest

from app.embeddings.embedder import (
    QUERY_PREFIX,
    EmbeddingsUnavailable,
    SentenceTransformerEmbedder,
)


class FakeModel:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def encode(self, texts: list[str], **_: object) -> np.ndarray:
        self.seen.extend(texts)
        return np.ones((len(texts), 384), dtype=np.float32)


def test_documents_are_embedded_as_plain_lists() -> None:
    embedder = SentenceTransformerEmbedder("test-model")
    embedder._model = FakeModel()

    vectors = embedder.embed_documents(["first", "second"])

    assert len(vectors) == 2
    assert isinstance(vectors[0], list) and len(vectors[0]) == 384


def test_queries_get_the_bge_search_prefix() -> None:
    embedder = SentenceTransformerEmbedder("test-model")
    model = FakeModel()
    embedder._model = model

    embedder.embed_query("Why pgvector?")

    assert model.seen == [QUERY_PREFIX + "Why pgvector?"]


def test_missing_library_gives_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    with pytest.raises(EmbeddingsUnavailable, match="requirements-embeddings"):
        SentenceTransformerEmbedder("test-model").embed_documents(["text"])
