from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.repositories import get_extraction_runner
from app.db import crud
from app.db.session import get_session
from app.main import app
from app.models import CommentKind, Decision, DecisionEvidence, DiscussionKind
from app.schemas.decisions import DecisionStatus
from app.services.decisions import extracting, threads_to_extract

CREATED = datetime(2026, 1, 2, tzinfo=UTC)
WEB = "https://github.com/a/b"


def seed(session: Session, comments_per_thread: list[int]):
    repo = crud.create_repository(session, full_name="a/b", html_url=WEB)
    threads = []
    for number, comment_count in enumerate(comments_per_thread, start=1):
        thread = crud.upsert_discussion(
            session,
            repo.id,
            kind=DiscussionKind.ISSUE,
            github_id=number,
            number=number,
            title=f"Issue {number}",
            state="open",
            source_url=f"{WEB}/issues/{number}",
            created_at=CREATED,
        )
        for i in range(comment_count):
            crud.upsert_comment(
                session,
                thread.id,
                kind=CommentKind.ISSUE_COMMENT,
                github_id=number * 100 + i,
                source_url=f"{WEB}/issues/{number}#c{i}",
                created_at=CREATED,
            )
        threads.append(thread)
    return repo, threads


def client(session: Session, runs: list) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_extraction_runner] = lambda: (
        lambda repo_id, threads: runs.append(threads)
    )
    return TestClient(app)


def test_most_discussed_unprocessed_threads_come_first(db_session: Session) -> None:
    _, threads = seed(db_session, [1, 5, 3])
    threads[1].decisions_extracted_at = CREATED

    picked = threads_to_extract(db_session, threads[0].repository_id, limit=2)

    assert picked == [threads[2].id, threads[0].id]


def test_list_decisions_includes_alternatives_and_evidence(db_session: Session):
    repo, threads = seed(db_session, [0])
    decision = Decision(
        repository_id=repo.id,
        title="Drop 3.8",
        context="",
        decision="Stop supporting Python 3.8.",
        rationale=["End of life."],
        alternatives=[{"approach": "Keep it", "rejection_reason": "Extra work."}],
        trade_offs=[],
        status=DecisionStatus.PROPOSED,
        extraction_model="gemma3:4b",
    )
    db_session.add(decision)
    db_session.flush()
    db_session.add(
        DecisionEvidence(
            decision_id=decision.id,
            discussion_id=threads[0].id,
            excerpt="end of life",
            source_url=threads[0].source_url,
        )
    )
    db_session.flush()
    try:
        body = client(db_session, []).get(f"/api/v1/repositories/{repo.id}/decisions")
        detail = client(db_session, []).get(f"/api/v1/repositories/{repo.id}")
    finally:
        app.dependency_overrides.clear()

    [item] = body.json()
    assert item["decision"] == "Stop supporting Python 3.8."
    assert item["alternatives"][0]["approach"] == "Keep it"
    assert item["evidence"] == [
        {"excerpt": "end of life", "source_url": f"{WEB}/issues/1"}
    ]
    assert detail.json()["decision_count"] == 1


def test_extract_starts_background_run(db_session: Session) -> None:
    repo, threads = seed(db_session, [2, 0])
    runs: list = []
    try:
        first = client(db_session, runs).post(f"/api/v1/repositories/{repo.id}/extract")
        for thread in threads:
            thread.decisions_extracted_at = CREATED
        again = client(db_session, runs).post(f"/api/v1/repositories/{repo.id}/extract")
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 202
    assert first.json()["threads"] == 2
    assert runs[0] == [threads[0].id, threads[1].id]
    assert again.json()["message"] == "All threads are already processed"
    assert len(runs) == 1
    detail = client(db_session, runs).get(f"/api/v1/repositories/{repo.id}")
    app.dependency_overrides.clear()
    extracting.discard(repo.id)
    assert detail.json()["extracting"] is True
