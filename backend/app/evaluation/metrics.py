"""Small, dependency-free metrics for retrieval and answer quality."""

from collections.abc import Iterable


def hit_at_k(ranked: list[int], expected: set[int], k: int) -> float:
    """1.0 if any expected item is in the top k, else 0.0."""
    return 1.0 if expected & set(ranked[:k]) else 0.0


def reciprocal_rank(ranked: list[int], expected: set[int]) -> float:
    """1 / position of the first expected item, or 0.0 if none was found."""
    for position, item in enumerate(ranked, start=1):
        if item in expected:
            return 1 / position
    return 0.0


def precision(found: Iterable[int], expected: set[int]) -> float | None:
    """Share of found items that were expected. None if nothing was found."""
    items = list(found)
    if not items:
        return None
    return sum(item in expected for item in items) / len(items)


def mean(values: Iterable[float | None]) -> float | None:
    """Average of the values that exist, or None if there are none."""
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None
