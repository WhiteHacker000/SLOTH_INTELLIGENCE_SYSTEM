import math
from dataclasses import dataclass

from app.ingestion.github_client import PAGE_SIZE, GitHubError, GitHubReader

# Rough guess used only for the estimate.
AVERAGE_COMMENTS_PER_ITEM = 3
TOKEN_NEEDED_MESSAGE = "This repository is large. Add your GitHub token to import it."


@dataclass
class ImportEstimate:
    items: int
    api_calls: int
    token_recommended: bool
    message: str | None


def estimate_import(github: GitHubReader, full_name: str) -> ImportEstimate:
    """Estimate API calls from the newest issue/PR number."""
    newest = github.get_json(
        f"/repos/{full_name}/issues",
        {"state": "all", "sort": "created", "direction": "desc", "per_page": 1},
    )
    if not isinstance(newest, list):
        raise GitHubError("Unexpected response while estimating the import")
    items = newest[0]["number"] if newest else 0
    comments = items * AVERAGE_COMMENTS_PER_ITEM
    # Issue and PR pages, two comment endpoints, and one reviews call per item
    # (an upper bound, since not every item is a PR).
    api_calls = 1 + math.ceil(items / PAGE_SIZE) + 2 * math.ceil(comments / PAGE_SIZE)
    api_calls += items

    remaining = github.rate_limit.remaining
    too_large = remaining is not None and api_calls > remaining
    token_recommended = too_large and not github.authenticated
    return ImportEstimate(
        items=items,
        api_calls=api_calls,
        token_recommended=token_recommended,
        message=TOKEN_NEEDED_MESSAGE if token_recommended else None,
    )
