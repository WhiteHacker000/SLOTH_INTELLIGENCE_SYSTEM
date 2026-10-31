from enum import StrEnum

from pydantic import BaseModel, Field


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class RejectedAlternative(BaseModel):
    approach: str
    rejection_reason: str


class EvidenceQuote(BaseModel):
    """A message id from the thread and a short quote copied from it."""

    message_id: str
    quote: str = Field(min_length=1, max_length=300)


class DecisionExtraction(BaseModel):
    """One decision as returned by the model, before it is checked."""

    title: str = Field(max_length=200)
    context: str
    decision: str
    rationale: list[str]
    alternatives: list[RejectedAlternative]
    trade_offs: list[str]
    status: DecisionStatus
    # Self-reported by the model, not a calibrated probability.
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceQuote] = Field(min_length=1)


class ExtractionResult(BaseModel):
    decisions: list[DecisionExtraction] = Field(max_length=5)
