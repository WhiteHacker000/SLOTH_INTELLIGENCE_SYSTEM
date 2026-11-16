from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db import crud
from app.models import CommentKind, Decision, DecisionEvidence, DiscussionKind
from app.schemas.decisions import DecisionStatus
from app.services.code_links import code_for

CREATED = datetime(2026, 1, 2, tzinfo=UTC)
WEB = "https://github.com/a/b"


def seed(session: Session):
    """One PR with a decision about the cache, one issue about the docs."""
    repo = crud.create_repository(
        session, full_name="a/b", html_url=WEB, default_branch="main"
    )
    pr = crud.upsert_discussion(
        session,
        repo.id,
        kind=DiscussionKind.PULL_REQUEST,
        github_id=7,
        number=7,
        title="Drop the cache lock",
        state="closed",
        source_url=f"{WEB}/pull/7",
        created_at=CREATED,
    )
    crud.replace_discussion_files(
        session,
        pr.id,
        [
            {"path": "src/cache.py", "status": "modified"},
            {"path": "src/lock.py", "status": "removed"},
        ],
    )
    review = crud.upsert_comment(
        session,
        pr.id,
        kind=CommentKind.REVIEW_COMMENT,
        github_id=70,
        body="The lock is not needed with the GIL",
        source_url=f"{WEB}/pull/7#discussion_r70",
        created_at=CREATED,
        path="src/cache.py",
        line=42,
        commit_sha="abc123",
    )
    cache = add_decision(session, repo.id, pr.id, review.id, "Remove the cache lock")
    issue = crud.upsert_discussion(
        session,
        repo.id,
        kind=DiscussionKind.ISSUE,
        github_id=8,
        number=8,
        title="Docs",
        state="open",
        source_url=f"{WEB}/issues/8",
        created_at=CREATED,
    )
    other = add_decision(session, repo.id, issue.id, None, "Keep docs short")
    return repo, cache, other


def add_decision(session, repo_id, discussion_id, comment_id, title) -> Decision:
    decision = Decision(
        repository_id=repo_id,
        title=title,
        context="",
        decision=title,
        rationale=[],
        alternatives=[],
        trade_offs=[],
        status=DecisionStatus.ACCEPTED,
        extraction_model="test",
    )
    session.add(decision)
    session.flush()
    session.add(
        DecisionEvidence(
            decision_id=decision.id,
            discussion_id=discussion_id,
            comment_id=comment_id,
            excerpt="quote",
            source_url=f"{WEB}/pull/7",
        )
    )
    session.flush()
    return decision


def test_decisions_link_to_changed_files_and_reviewed_lines(db_session: Session):
    repo, cache, other = seed(db_session)

    code = code_for(db_session, repo, [cache.id, other.id])

    assert [(c.path, c.line, c.url) for c in code[cache.id]] == [
        ("src/cache.py", 42, f"{WEB}/blob/abc123/src/cache.py#L42"),
        ("src/lock.py", None, f"{WEB}/blob/main/src/lock.py"),
    ]
    assert other.id not in code
