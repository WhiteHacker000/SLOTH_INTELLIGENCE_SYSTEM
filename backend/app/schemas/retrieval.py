from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field

from app.schemas.github import DiscussionSourceType


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    repository_full_name: str | None = None
    source_types: list[DiscussionSourceType] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=20)


class RetrievedEvidence(BaseModel):
    content: str
    source_url: AnyHttpUrl
    similarity: float = Field(ge=0, le=1)
    repository_full_name: str
    source_type: DiscussionSourceType
    discussion_number: int
    discussion_title: str
    author: str | None
    created_at: datetime


class SearchResponse(BaseModel):
    query: str
    results: list[RetrievedEvidence]
