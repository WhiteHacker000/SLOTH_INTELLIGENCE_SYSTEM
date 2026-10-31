import pytest
from pydantic import ValidationError

from app.schemas.decisions import DecisionExtraction, DecisionStatus

VALID = {
    "title": "Use PostgreSQL for persistence",
    "context": "The project needs relational and vector storage.",
    "decision": "Use PostgreSQL with pgvector.",
    "rationale": ["One database keeps operations simple."],
    "alternatives": [{"approach": "Qdrant", "rejection_reason": "Extra service."}],
    "trade_offs": ["Vector search shares database resources."],
    "status": "proposed",
    "confidence": 0.7,
    "evidence": [{"message_id": "M0", "quote": "one database"}],
}


def test_decision_schema_accepts_known_statuses_and_evidence() -> None:
    decision = DecisionExtraction.model_validate(VALID)

    assert decision.status is DecisionStatus.PROPOSED
    assert decision.evidence[0].message_id == "M0"


@pytest.mark.parametrize(
    "change", [{"status": "merged"}, {"evidence": []}, {"confidence": 1.5}]
)
def test_decision_schema_rejects_invalid_output(change: dict) -> None:
    with pytest.raises(ValidationError):
        DecisionExtraction.model_validate({**VALID, **change})
