import pytest
from pydantic import ValidationError

from app.schemas.decisions import DecisionExtraction, DecisionStatus


def test_decision_schema_accepts_known_statuses_and_evidence() -> None:
    decision = DecisionExtraction.model_validate(
        {
            "decision": "Use PostgreSQL for persistence",
            "context": "The project needs relational and vector storage.",
            "rationale": "One database keeps operations simple.",
            "alternatives": [
                {
                    "approach": "Use a separate vector database",
                    "rejection_reason": "It adds infrastructure for the MVP.",
                }
            ],
            "trade_offs": ["Vector search shares database resources."],
            "status": "proposed",
            "supporting_evidence": ["https://github.com/example/project/issues/7"],
        }
    )

    assert decision.status is DecisionStatus.PROPOSED
    assert decision.supporting_evidence[0].host == "github.com"


def test_decision_schema_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        DecisionExtraction.model_validate(
            {
                "decision": "A decision",
                "context": "Context",
                "rationale": "Reason",
                "alternatives": [],
                "trade_offs": [],
                "status": "merged",
                "supporting_evidence": [],
            }
        )
