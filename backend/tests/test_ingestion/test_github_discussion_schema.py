from app.schemas.github import DiscussionSourceType, GitHubDiscussion


def test_github_discussion_payload_is_validated_and_keeps_source_url() -> None:
    discussion = GitHubDiscussion.model_validate(
        {
            "repository_full_name": "example/project",
            "source_type": "issue_comment",
            "github_id": 42,
            "body": "Why was this approach selected?",
            "source_url": "https://github.com/example/project/issues/7#issuecomment-42",
            "created_at": "2026-01-02T03:04:05Z",
        }
    )

    assert discussion.source_type is DiscussionSourceType.ISSUE_COMMENT
    assert str(discussion.source_url).endswith("#issuecomment-42")
