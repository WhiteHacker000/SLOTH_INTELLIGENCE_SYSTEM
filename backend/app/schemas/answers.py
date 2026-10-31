from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievedEvidence


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1_000)
    repository_full_name: str | None = None
    limit: int = Field(default=6, ge=1, le=10)


class AnswerDraft(BaseModel):
    """What the model returns, before citations are checked."""

    answer: str
    answered: bool
    cited_sources: list[str]
    limitations: str | None = None


class AskResponse(BaseModel):
    question: str
    status: AnswerStatus
    answer: str | None
    citations: list[RetrievedEvidence]
    limitations: str | None
