from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import crud
from app.extraction.extractor import extract_decisions
from app.models import CommentKind, Decision, DecisionEvidence, DiscussionKind
from app.schemas.decisions import DecisionStatus

CREATED = datetime(2026, 1, 2, tzinfo=UTC)
URL = "https://github.com/a/b/pull/7"


class FakeModel:
    def __init__(self, decisions: list[dict[str, Any]]) -> None:
        self.decisions = decisions
        self.prompts: list[str] = []

    def generate_json(self, system: str, prompt: str, schema: dict) -> dict:
        self.prompts.append(prompt)
        return {"decisions": self.decisions}


def decision(*evidence: tuple[str, str], status: str = "accepted") -> dict:
    return {
        "title": "Drop Python 3.8",
        "context": "3.8 is end of life.",
        "decision": "Stop supporting Python 3.8.",
        "rationale": ["It reached end of life."],
        "alternatives": [],
        "trade_offs": [],
        "status": status,
        "confidence": 0.9,
        "evidence": [{"message_id": m, "quote": q} for m, q in evidence],
    }


def make_pr(session: Session, body: str = "Python 3.8 reached end of life."):
    repo = crud.create_repository(session, full_name="a/b", html_url=URL)
    pr = crud.upsert_discussion(
        session,
        repo.id,
        kind=DiscussionKind.PULL_REQUEST,
        github_id=7,
        number=7,
        title="Drop 3.8",
        body=body,
        state="closed",
        source_url=URL,
        created_at=CREATED,
        merged_at=CREATED,
    )
    crud.upsert_comment(
        session,
        pr.id,
        kind=CommentKind.ISSUE_COMMENT,
        github_id=70,
        author="reviewer",
        body="Agreed, we will drop it in the next release.",
        source_url=f"{URL}#issuecomment-70",
        created_at=CREATED,
    )
    return pr


def run(session: Session, pr, model: FakeModel) -> list[Decision]:
    return extract_decisions(session, model, "gemma3:4b", pr)


def test_saves_decision_with_evidence_linked_to_the_comment(
    db_session: Session,
) -> None:
    pr = make_pr(db_session)
    model = FakeModel([decision(("M1", "we will  drop it"))])

    [saved] = run(db_session, pr, model)

    assert saved.status is DecisionStatus.ACCEPTED
    query = select(DecisionEvidence).where(DecisionEvidence.decision_id == saved.id)
    [evidence] = db_session.scalars(query)
    assert evidence.source_url == f"{URL}#issuecomment-70"


def test_opening_post_alone_cannot_accept(db_session: Session) -> None:
    pr = make_pr(db_session)

    [saved] = run(db_session, pr, FakeModel([decision(("M0", "end of life"))]))

    assert saved.status is DecisionStatus.PROPOSED


def test_made_up_quotes_and_ids_are_dropped(db_session: Session) -> None:
    pr = make_pr(db_session)
    model = FakeModel(
        [decision(("M1", "we rewrote it in Rust")), decision(("M9", "end of life"))]
    )

    assert run(db_session, pr, model) == []


def test_rerun_replaces_earlier_decisions(db_session: Session) -> None:
    pr = make_pr(db_session)
    model = FakeModel([decision(("M0", "end of life"), status="proposed")])

    run(db_session, pr, model)
    run(db_session, pr, model)

    assert db_session.scalar(select(func.count()).select_from(Decision)) == 1


def test_merge_state_is_not_sent_to_the_model(db_session: Session) -> None:
    pr = make_pr(db_session)
    model = FakeModel([])

    run(db_session, pr, model)

    assert "merged" not in model.prompts[0].lower()
