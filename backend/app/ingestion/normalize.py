"""Convert GitHub API payloads into column values for the database.

GitHub content is untrusted. It is stored as plain data and never interpreted.
"""

from datetime import datetime
from typing import Any

from app.models import CommentKind, DiscussionKind


def discussion_values(item: dict[str, Any]) -> dict[str, Any]:
    """Map an item from the issues endpoint, which also returns pull requests."""
    pull_request = item.get("pull_request")
    return {
        "kind": DiscussionKind.PULL_REQUEST if pull_request else DiscussionKind.ISSUE,
        "github_id": item["id"],
        "number": item["number"],
        "title": item["title"],
        "body": item.get("body") or "",
        "state": item["state"],
        "author": _login(item),
        "labels": [label["name"] for label in item.get("labels") or []],
        "source_url": item["html_url"],
        "created_at": _timestamp(item["created_at"]),
        "updated_at": _timestamp(item.get("updated_at")),
        "closed_at": _timestamp(item.get("closed_at")),
        "merged_at": _timestamp((pull_request or {}).get("merged_at")),
    }


def comment_values(item: dict[str, Any], kind: CommentKind) -> dict[str, Any]:
    return {
        "kind": kind,
        "github_id": item["id"],
        "author": _login(item),
        "body": item.get("body") or "",
        "source_url": item["html_url"],
        # Reviews only have submitted_at.
        "created_at": _timestamp(item.get("created_at") or item["submitted_at"]),
        "updated_at": _timestamp(item.get("updated_at")),
    }


def parent_number(item: dict[str, Any], url_key: str) -> int:
    """Read the issue or PR number from the end of the item's parent API URL."""
    return int(item[url_key].rstrip("/").rsplit("/", 1)[1])


def _login(item: dict[str, Any]) -> str | None:
    return (item.get("user") or {}).get("login")


def _timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
