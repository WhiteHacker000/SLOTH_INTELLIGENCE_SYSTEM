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
