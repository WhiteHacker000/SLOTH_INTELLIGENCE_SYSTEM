import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

GITHUB_REPOSITORY = re.compile(
    r"^(?:https?://(?:www\.)?github\.com/)?"
    r"(?P<owner>[A-Za-z0-9-]+)/(?P<name>[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


class TokenRequest(BaseModel):
    # SecretStr keeps the token out of logs, reprs and error messages.
    token: SecretStr | None = None

    def token_value(self) -> str | None:
        return self.token.get_secret_value() if self.token else None


class RepositoryCreate(TokenRequest):
    url: str = Field(examples=["https://github.com/pallets/click"])

    @field_validator("url")
    @classmethod
    def must_be_github_repository(cls, value: str) -> str:
        match = GITHUB_REPOSITORY.match(value.strip())
        if not match:
            raise ValueError("Enter a GitHub repository like owner/name")
        return f"{match['owner']}/{match['name']}"

    @property
    def full_name(self) -> str:
        return self.url


class ImportEstimateRead(BaseModel):
    items: int
    api_calls: int
    token_recommended: bool
    message: str | None


class RepositoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    html_url: str
    description: str | None
    last_synced_at: datetime | None
    last_sync_error: str | None
    created_at: datetime


class RepositoryRegistered(BaseModel):
    repository: RepositoryRead
    estimate: ImportEstimateRead
