from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import crud
from app.models import CommentKind, DiscussionKind, DocumentChunk
from app.processing.chunks import chunk_repository

CREATED = datetime(2026, 1, 2, tzinfo=UTC)
WEB = "https://github.com/a/b"


def setup_issue(session: Session, body: str = "Should we use pgvector?"):
    repo = crud.create_repository(session, full_name="a/b", html_url=WEB)
    issue = crud.upsert_discussion(
        session,
        repo.id,
        kind=DiscussionKind.ISSUE,
        github_id=1,
        number=7,
        title="Vector storage",
        body=body,
        state="open",
        source_url=f"{WEB}/issues/7",
        created_at=CREATED,
    )
    return repo, issue


def add_comment(session: Session, issue_id, body: str) -> None:
    crud.upsert_comment(
        session,
        issue_id,
        kind=CommentKind.ISSUE_COMMENT,
        github_id=11,
        body=body,
        source_url=f"{WEB}/issues/7#issuecomment-11",
        created_at=CREATED,
    )


def chunks(session: Session) -> list[DocumentChunk]:
    return list(session.scalars(select(DocumentChunk).order_by(DocumentChunk.content)))


def test_chunks_keep_their_source_and_issue_context(db_session: Session) -> None:
    repo, issue = setup_issue(db_session)
    add_comment(db_session, issue.id, "Yes, it avoids a second database.")

    stats = chunk_repository(db_session, repo.id)

    assert stats.created == 2
    body, comment = sorted(chunks(db_session), key=lambda c: c.comment_id is not None)
    assert body.source_url == f"{WEB}/issues/7"
    assert body.content == "Issue #7: Vector storage\n\nShould we use pgvector?"
    assert comment.source_url.endswith("#issuecomment-11")
    assert comment.content.startswith("Issue #7: Vector storage")
    assert all(chunk.discussion_id == issue.id for chunk in (body, comment))


def test_rerun_keeps_unchanged_chunks_and_embeddings(db_session: Session) -> None:
    repo, _ = setup_issue(db_session)
    chunk_repository(db_session, repo.id)
    chunks(db_session)[0].embedding = [0.1] * 384

    stats = chunk_repository(db_session, repo.id)

    assert (stats.created, stats.unchanged) == (0, 1)
    assert chunks(db_session)[0].embedding is not None


def test_edited_text_clears_embedding(db_session: Session) -> None:
    repo, issue = setup_issue(db_session)
    chunk_repository(db_session, repo.id)
    chunks(db_session)[0].embedding = [0.1] * 384
    issue.body = "Edited: we chose pgvector."

    stats = chunk_repository(db_session, repo.id)

    assert stats.updated == 1
    assert chunks(db_session)[0].embedding is None


def test_shorter_text_deletes_leftover_chunks(db_session: Session) -> None:
    repo, issue = setup_issue(db_session, body="\n\n".join(["x" * 1000] * 3))
    chunk_repository(db_session, repo.id)
    issue.body = "short"

    stats = chunk_repository(db_session, repo.id)

    assert stats.deleted == 2
    assert len(chunks(db_session)) == 1


def test_issue_without_body_gets_a_title_chunk(db_session: Session) -> None:
    repo, _ = setup_issue(db_session, body="")

    chunk_repository(db_session, repo.id)

    assert [chunk.content for chunk in chunks(db_session)] == [
        "Issue #7: Vector storage"
    ]
