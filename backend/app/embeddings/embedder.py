from functools import lru_cache
from typing import Any, Protocol

from app.core.config import get_settings

# bge v1.5 models expect this prefix on search queries, not on documents.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class EmbeddingsUnavailable(RuntimeError):
    pass


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    """Runs the embedding model locally. The model loads on first use."""

    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self._model: Any = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(
            texts, batch_size=self.batch_size, normalize_embeddings=True
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([QUERY_PREFIX + text])[0]

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise EmbeddingsUnavailable(
                    "Install backend/requirements-embeddings.txt to enable search"
                ) from error
            self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model


@lru_cache
def get_embedder() -> Embedder:
    return SentenceTransformerEmbedder(get_settings().embedding_model)
