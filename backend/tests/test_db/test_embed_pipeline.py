from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import crud
from app.embeddings import pipeline
from app.embeddings.embedder import EmbeddingsUnavailable
from app.embeddings.pipeline import embed_pending_chunks
from app.models import DiscussionKind, DocumentChunk
from app.services import repositories as service


class FakeEmbedder:
    def __init__(self) -> None:
        self.batches: list[int] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(len(texts))
        return [[0.1] * 384 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * 384


class MissingEmbedder(FakeEmbedder):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingsUnavailable("not installed")


def make_repository(session: Session, name: str, issues: int):
    repo = crud.create_repository(
        session, full_name=name, html_url=f"https://github.com/{name}"
    )
    for number in range(1, issues + 1):
        crud.upsert_discussion(
            session,
            repo.id,
            kind=DiscussionKind.ISSUE,
            github_id=number if name == "a/b" else 1000 + number,
            number=number,
            title=f"Issue {number}",
            body="Some discussion",
            state="open",
            source_url=f"https://github.com/{name}/issues/{number}",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    return repo


def embedded_count(session: Session) -> int:
    query = select(func.count()).where(DocumentChunk.embedding.is_not(None))
    return session.scalar(query) or 0


def test_index_chunks_and_embeds_in_batches(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "BATCH_SIZE", 2)
    repo = make_repository(db_session, "a/b", issues=5)
    embedder = FakeEmbedder()
    monkeypatch.setattr(service, "get_embedder", lambda: embedder)

    service.build_search_index(db_session, repo)

    assert embedder.batches == [2, 2, 1]
    assert embedded_count(db_session) == 5


def test_only_missing_embeddings_for_that_repository(db_session: Session) -> None:
    repo = make_repository(db_session, "a/b", issues=2)
    make_repository(db_session, "c/d", issues=3)
    service.chunk_repository(db_session, repo.id)

    first = embed_pending_chunks(db_session, FakeEmbedder(), repo.id)
    second = embed_pending_chunks(db_session, FakeEmbedder(), repo.id)

    assert (first, second) == (2, 0)


def test_missing_model_still_saves_chunks(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repository(db_session, "a/b", issues=2)
    monkeypatch.setattr(service, "get_embedder", MissingEmbedder)

    service.build_search_index(db_session, repo)

    assert db_session.scalar(select(func.count()).select_from(DocumentChunk)) == 2
    assert embedded_count(db_session) == 0
