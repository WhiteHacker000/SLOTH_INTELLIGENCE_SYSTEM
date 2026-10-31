from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_session
from app.embeddings.embedder import EmbeddingsUnavailable, get_embedder
from app.main import app
from app.models import CommentKind, DiscussionKind, DocumentChunk
from app.retrieval.search import search_chunks
from app.schemas.github import DiscussionSourceType

CREATED = datetime(2026, 1, 2, tzinfo=UTC)


def vector(*axes: int) -> list[float]:
    """A vector along the given axes, so similarity is easy to predict."""
    values = [0.0] * 384
    for axis in axes:
        values[axis] = 1.0
    return values


def seed(session: Session, name: str, axis: int, with_comment: bool = False):
    repo = crud.create_repository(
        session, full_name=name, html_url=f"https://github.com/{name}"
    )
    issue = crud.upsert_discussion(
        session,
        repo.id,
        kind=DiscussionKind.ISSUE,
        github_id=axis,
        number=axis,
        title=f"Issue {axis}",
        state="open",
        source_url=f"https://github.com/{name}/issues/{axis}",
        created_at=CREATED,
    )
    session.add(
        DocumentChunk(
            discussion_id=issue.id,
            ordinal=0,
            content=f"Issue {axis} body",
            source_url=issue.source_url,
            embedding=vector(axis),
        )
    )
    if with_comment:
        comment = crud.upsert_comment(
            session,
            issue.id,
            kind=CommentKind.REVIEW_COMMENT,
            github_id=900 + axis,
            author="reviewer",
            source_url=f"{issue.source_url}#discussion_r1",
            created_at=CREATED,
        )
        session.add(
            DocumentChunk(
                discussion_id=issue.id,
                comment_id=comment.id,
                ordinal=0,
                content="Comment chunk",
                source_url=comment.source_url,
                embedding=vector(axis, axis + 1),
            )
        )
    session.flush()
    return repo


def test_results_are_ranked_and_keep_their_source(db_session: Session) -> None:
    seed(db_session, "a/b", axis=1, with_comment=True)
    seed(db_session, "c/d", axis=5)

    results = search_chunks(db_session, vector(1), limit=3)

    assert [r.content for r in results[:2]] == ["Issue 1 body", "Comment chunk"]
    assert results[0].similarity > results[1].similarity > results[2].similarity
    assert results[0].source_type is DiscussionSourceType.ISSUE
    assert results[1].source_type is DiscussionSourceType.REVIEW_COMMENT
    assert results[1].author == "reviewer"
    assert str(results[1].source_url).endswith("#discussion_r1")


def test_filters_by_repository_and_source_type(db_session: Session) -> None:
    repo = seed(db_session, "a/b", axis=1, with_comment=True)
    seed(db_session, "c/d", axis=5)

    in_repo = search_chunks(db_session, vector(5), repository_id=repo.id)
    comments_only = search_chunks(
        db_session, vector(1), source_types=[DiscussionSourceType.REVIEW_COMMENT]
    )

    assert {r.repository_full_name for r in in_repo} == {"a/b"}
    assert [r.content for r in comments_only] == ["Comment chunk"]


class FakeEmbedder:
    def __init__(self, installed: bool = True) -> None:
        self.installed = installed

    def embed_query(self, text: str) -> list[float]:
        if not self.installed:
            raise EmbeddingsUnavailable("not installed")
        return vector(1)


def search_api(session: Session, embedder: object, body: dict) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_embedder] = lambda: embedder
    try:
        return TestClient(app).post("/api/v1/search", json=body)
    finally:
        app.dependency_overrides.clear()


def test_search_endpoint(db_session: Session) -> None:
    seed(db_session, "a/b", axis=1)

    ok = search_api(db_session, FakeEmbedder(), {"query": "why", "limit": 1})
    unknown = search_api(
        db_session, FakeEmbedder(), {"query": "why", "repository_full_name": "x/y"}
    )
    missing = search_api(db_session, FakeEmbedder(installed=False), {"query": "why"})

    assert ok.status_code == 200
    assert ok.json()["results"][0]["discussion_title"] == "Issue 1"
    assert unknown.status_code == 404
    assert missing.status_code == 503
