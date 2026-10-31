from datetime import datetime
from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel


class DiscussionSourceType(StrEnum):
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    ISSUE_COMMENT = "issue_comment"
    REVIEW_COMMENT = "review_comment"
    REVIEW = "review"


class GitHubDiscussion(BaseModel):
    repository_full_name: str
    source_type: DiscussionSourceType
    github_id: int
    title: str | None = None
    body: str
    source_url: AnyHttpUrl
    created_at: datetime
    updated_at: datetime | None = None
