from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.evaluation.metrics import hit_at_k, mean, precision, reciprocal_rank
from app.evaluation.retrieval import Question, evaluate, load
from app.schemas.answers import AnswerStatus, AskResponse
from app.schemas.github import DiscussionSourceType
from app.schemas.retrieval import RetrievedEvidence

DATASET = Path(__file__).parents[3] / "evaluation/datasets/questions.jsonl"


def test_ranking_metrics() -> None:
    assert hit_at_k([3, 7, 9], {9}, k=3) == 1.0
    assert hit_at_k([3, 7, 9], {9}, k=2) == 0.0
    assert reciprocal_rank([3, 7, 9], {7, 9}) == 0.5
    assert reciprocal_rank([3], {9}) == 0.0


def test_precision_and_mean_skip_missing_values() -> None:
    assert precision([1, 2, 3, 4], {1, 2}) == 0.5
    assert precision([], {1}) is None
    assert mean([1.0, None, 0.0]) == 0.5
    assert mean([None]) is None


def evidence(number: int) -> RetrievedEvidence:
    return RetrievedEvidence(
        content="text",
        source_url=f"https://github.com/a/b/issues/{number}",
        similarity=0.9,
        repository_full_name="a/b",
        source_type=DiscussionSourceType.ISSUE,
        discussion_number=number,
        discussion_title="t",
        author=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


QUESTIONS = [
    Question("a/b", "found first", [1]),
    Question("a/b", "found second", [2]),
    Question("a/b", "missed", [9]),
    Question("a/b", "nothing about this", [], answerable=False),
]
RESULTS = {"found first": [1, 1, 5], "found second": [5, 2], "missed": [5, 6]}


def search(q: Question) -> list[RetrievedEvidence]:
    return [evidence(n) for n in RESULTS.get(q.question, [5])]


def answer(q: Question, found: list[RetrievedEvidence]) -> AskResponse:
    if not q.answerable or q.question == "missed":
        return AskResponse(
            question=q.question,
            status=AnswerStatus.INSUFFICIENT_EVIDENCE,
            answer=None,
            citations=[],
            limitations=None,
        )
    return AskResponse(
        question=q.question,
        status=AnswerStatus.ANSWERED,
        answer="a",
        citations=found[:2],
        limitations=None,
    )


def test_retrieval_report() -> None:
    report = evaluate(QUESTIONS, search, k=5)

    assert report["questions"] == 3
    assert report["hit@5"] == pytest.approx(2 / 3)
    assert report["hit@1"] == pytest.approx(1 / 3)
    assert report["mrr"] == pytest.approx((1 + 0.5 + 0) / 3)
    assert "answered" not in report


def test_answer_report() -> None:
    report = evaluate(QUESTIONS, search, answer)

    assert report["answered"] == pytest.approx(2 / 3)
    # "found first" cites thread 1 twice (one thread, right); "found second"
    # cites 5 then 2 (half right). Unanswered questions are not counted.
    assert report["citation_precision"] == pytest.approx((1 + 0.5) / 2)
    assert report["abstained"] == 1.0


def test_dataset_is_well_formed() -> None:
    questions = load(DATASET)

    assert len(questions) >= 30
    for q in questions:
        assert q.answerable == bool(q.expected_threads), q.question
