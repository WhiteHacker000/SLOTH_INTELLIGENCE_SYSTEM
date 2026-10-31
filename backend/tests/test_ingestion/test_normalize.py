from datetime import UTC, datetime

import pytest

from app.ingestion.normalize import comment_values, discussion_values, parent_number
from app.models import CommentKind, DiscussionKind

ISSUE = {
    "id": 101,
    "number": 7,
    "title": "Use pgvector?",
    "body": None,
    "state": "closed",
    "user": {"login": "octocat"},
    "labels": [{"name": "design"}],
    "html_url": "https://github.com/a/b/issues/7",
    "created_at": "2026-01-02T03:04:05Z",
    "updated_at": "2026-01-03T00:00:00Z",
    "closed_at": None,
}


def test_issue_is_mapped_with_empty_body_and_labels() -> None:
    values = discussion_values(ISSUE)

    assert values["kind"] is DiscussionKind.ISSUE
    assert values["body"] == ""
    assert values["labels"] == ["design"]
    assert values["author"] == "octocat"
    assert values["created_at"] == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert values["merged_at"] is None


def test_pull_request_keeps_merge_time() -> None:
    item = {**ISSUE, "pull_request": {"merged_at": "2026-01-04T00:00:00Z"}}

    values = discussion_values(item)

    assert values["kind"] is DiscussionKind.PULL_REQUEST
    assert values["merged_at"] == datetime(2026, 1, 4, tzinfo=UTC)


def test_deleted_user_gives_no_author() -> None:
    assert discussion_values({**ISSUE, "user": None})["author"] is None


def test_review_uses_submitted_at_as_created_time() -> None:
    review = {
        "id": 9,
        "body": "Looks good",
        "user": {"login": "reviewer"},
        "html_url": "https://github.com/a/b/pull/8#pullrequestreview-9",
        "submitted_at": "2026-01-05T00:00:00Z",
    }

    values = comment_values(review, CommentKind.REVIEW)

    assert values["created_at"] == datetime(2026, 1, 5, tzinfo=UTC)
    assert values["updated_at"] is None


def test_parent_number_reads_end_of_api_url() -> None:
    item = {"issue_url": "https://api.github.com/repos/a/b/issues/42"}

    assert parent_number(item, "issue_url") == 42


def test_missing_required_field_raises() -> None:
    with pytest.raises(KeyError):
        discussion_values({"id": 1})
