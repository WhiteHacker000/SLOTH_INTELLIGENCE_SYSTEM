from datetime import UTC, datetime

from app.retrieval.search import rank_threads
from app.schemas.github import DiscussionSourceType
from app.schemas.retrieval import RetrievedEvidence


def chunk(thread: int, similarity: float, repo: str = "a/b") -> RetrievedEvidence:
    return RetrievedEvidence(
        content=f"{repo}#{thread} at {similarity}",
        source_url=f"https://github.com/{repo}/issues/{thread}",
        similarity=similarity,
        repository_full_name=repo,
        source_type=DiscussionSourceType.ISSUE,
        discussion_number=thread,
        discussion_title="t",
        author=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_threads_discussing_the_question_twice_rank_first() -> None:
    # Thread 1 has the single best chunk; thread 2 has two good ones.
    chunks = [chunk(1, 0.80), chunk(2, 0.75), chunk(3, 0.60), chunk(2, 0.70)]

    ranked = rank_threads(chunks, limit=5)

    assert [c.discussion_number for c in ranked] == [2, 1, 3]
    assert ranked[0].similarity == 0.75  # each thread shows its best chunk


def test_only_the_two_best_chunks_count() -> None:
    chunks = [chunk(1, 0.8), chunk(1, 0.7), chunk(2, 0.6), *[chunk(2, 0.5)] * 3]

    assert [c.discussion_number for c in rank_threads(chunks, limit=5)] == [1, 2]


def test_limit_and_threads_in_other_repositories_stay_apart() -> None:
    chunks = [chunk(1, 0.8), chunk(1, 0.7, repo="c/d"), chunk(2, 0.6)]

    ranked = rank_threads(chunks, limit=2)

    assert [(c.repository_full_name, c.discussion_number) for c in ranked] == [
        ("a/b", 1),
        ("c/d", 1),
    ]
