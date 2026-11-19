from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import crud
from app.models import Decision, DecisionEvidence, DiscussionKind
from app.schemas.decisions import DecisionStatus
from scripts.remove_copied_decisions import find_copies, remove

CREATED = datetime(2026, 1, 2, tzinfo=UTC)


def thread_with_decision(session: Session, repo_id, number: int, body: str, text: str):
    thread = crud.upsert_discussion(
        session,
        repo_id,
        kind=DiscussionKind.PULL_REQUEST,
        github_id=number,
        number=number,
        title=f"PR {number}",
        body=body,
        state="closed",
        source_url=f"https://github.com/a/b/pull/{number}",
        created_at=CREATED,
        decisions_extracted_at=CREATED,
    )
    decision = Decision(
        repository_id=repo_id,
        title=text,
        context="",
        decision=text,
        rationale=[],
        alternatives=[],
        trade_offs=[],
        status=DecisionStatus.PROPOSED,
        extraction_model="test",
    )
    session.add(decision)
    session.flush()
    session.add(
        DecisionEvidence(
            decision_id=decision.id,
            discussion_id=thread.id,
            excerpt="quote",
            source_url=thread.source_url,
        )
    )
    session.flush()
    return thread, decision


def test_removes_only_ruff_decisions_from_threads_that_never_mention_ruff(
    db_session: Session,
) -> None:
    repo = crud.create_repository(db_session, full_name="a/b", html_url="https://x")
    copied_thread, _ = thread_with_decision(
        db_session, repo.id, 1, "Build wheels for Windows", "Use ruff for linting"
    )
    _, real = thread_with_decision(
        db_session, repo.id, 2, "Let's switch to Ruff, it is faster", "Use ruff"
    )
    _, unrelated = thread_with_decision(
        db_session, repo.id, 3, "Wheels please", "Build Windows wheels"
    )

    found = find_copies(db_session)
    remove(db_session, found)

    assert [t.number for _, t, _ in found] == [1]
    left = set(db_session.scalars(select(Decision.id)))
    assert left == {real.id, unrelated.id}
    assert copied_thread.decisions_extracted_at is None
