from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class RejectedAlternative(BaseModel):
    approach: str
    rejection_reason: str


class DecisionExtraction(BaseModel):
    decision: str
    context: str
    rationale: str
    alternatives: list[RejectedAlternative]
    trade_offs: list[str]
    status: DecisionStatus
    supporting_evidence: list[AnyHttpUrl]
