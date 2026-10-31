import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import crud
from app.ingestion.github_client import GitHubError, GitHubReader, RateLimitExceeded
from app.ingestion.normalize import comment_values, discussion_values, parent_number
from app.models import CommentKind, Discussion, DiscussionKind, Repository, SyncStatus

logger = logging.getLogger(__name__)
T = TypeVar("T")

RATE_LIMITED_ERROR = "GitHub rate limit reached. Add a token and sync again."
SAVE_EVERY = 100


@dataclass
class ImportResult:
    discussions: int = 0
    comments: int = 0
    paused: bool = False
    message: str | None = None

    def count(self, save_progress: Callable[[], None], *, comment: bool) -> None:
        if comment:
            self.comments += 1
        else:
            self.discussions += 1
        if (self.discussions + self.comments) % SAVE_EVERY == 0:
            save_progress()


def import_repository(
    session: Session,
    github: GitHubReader,
    repository: Repository,
    save_progress: Callable[[], None] = lambda: None,
) -> ImportResult:
    """Import issues, PRs, comments and reviews changed since the last sync.

    If the rate limit runs out, saved work is kept and the checkpoint is not
    moved, so the next sync picks up where this one stopped.

    `save_progress` is called every SAVE_EVERY rows so long imports can commit
    as they go. The caller commits at the end.
    """
    started_at = datetime.now(UTC)
    result = ImportResult()
    repository.sync_status = SyncStatus.RUNNING
    save_progress()
    try:
        _import_all(session, github, repository, result, save_progress)
    except RateLimitExceeded:
        logger.info("Import of %s paused by rate limit", repository.full_name)
        crud.record_sync_result(session, repository, error=RATE_LIMITED_ERROR)
        repository.sync_status = SyncStatus.PAUSED
        result.paused = True
        result.message = RATE_LIMITED_ERROR
        return result
    except GitHubError as error:
        logger.warning("Import of %s failed: %s", repository.full_name, error)
        crud.record_sync_result(session, repository, error=str(error))
        repository.sync_status = SyncStatus.FAILED
        result.message = str(error)
        return result

    crud.record_sync_result(session, repository, started_at=started_at)
    repository.sync_status = SyncStatus.SYNCED
    return result


def _import_all(
    session: Session,
    github: GitHubReader,
    repo: Repository,
    result: ImportResult,
    save_progress: Callable[[], None],
) -> None:
    base = f"/repos/{repo.full_name}"
    meta = github.get_json(base)
    repo.github_id = meta["id"]
    repo.html_url = meta["html_url"]
    repo.description = meta.get("description")
    repo.default_branch = meta.get("default_branch")

    since = {"since": repo.last_synced_at.isoformat()} if repo.last_synced_at else {}
    updated_prs: list[Discussion] = []
    for item in github.paginate(f"{base}/issues", {"state": "all", **since}):
        values = _parse(discussion_values, item)
        if values is None:
            continue
        discussion = crud.upsert_discussion(session, repo.id, **values)
        result.count(save_progress, comment=False)
        if discussion.kind is DiscussionKind.PULL_REQUEST:
            updated_prs.append(discussion)

    comment_sources = [
        (f"{base}/issues/comments", "issue_url", CommentKind.ISSUE_COMMENT),
        (f"{base}/pulls/comments", "pull_request_url", CommentKind.REVIEW_COMMENT),
    ]
    for path, parent_key, kind in comment_sources:
        for item in github.paginate(path, since):
            values = _parse(comment_values, item, kind)
            number = _parse(parent_number, item, parent_key)
            if values is None or number is None:
                continue
            parent = _discussion_id(session, repo.id, number)
            if parent is None:
                continue
            crud.upsert_comment(session, parent, **values)
            result.count(save_progress, comment=True)

    for pr in updated_prs:
        for review in github.paginate(f"{base}/pulls/{pr.number}/reviews"):
            values = _parse(comment_values, review, CommentKind.REVIEW)
            if values and values["body"]:
                crud.upsert_comment(session, pr.id, **values)
                result.count(save_progress, comment=True)


def _parse(convert: Callable[..., T], item: dict[str, Any], *args: Any) -> T | None:
    """Skip items with missing or malformed fields instead of failing the import."""
    try:
        return convert(item, *args)
    except (KeyError, TypeError, ValueError):
        logger.warning("Skipping malformed GitHub item %s", item.get("html_url"))
        return None


def _discussion_id(session: Session, repository_id: UUID, number: int) -> UUID | None:
    return session.scalar(
        select(Discussion.id).where(
            Discussion.repository_id == repository_id, Discussion.number == number
        )
    )
