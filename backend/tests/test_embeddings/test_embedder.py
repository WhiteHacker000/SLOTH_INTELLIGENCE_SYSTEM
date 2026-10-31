import sys

import pytest

from app.embeddings.embedder import (
    QUERY_PREFIX,
    EmbeddingsUnavailable,
    SentenceTransformerEmbedder,
)


class FakeVector(list):
    """Stands in for a numpy row, which has tolist()."""

    def tolist(self) -> list[float]:
        return list(self)


class FakeModel:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def encode(self, texts: list[str], **_: object) -> list[FakeVector]:
        self.seen.extend(texts)
        return [FakeVector([1.0] * 384) for _ in texts]


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
