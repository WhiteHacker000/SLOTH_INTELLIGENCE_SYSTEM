from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.evaluation.metrics import hit_at_k, mean, precision, reciprocal_rank
from app.evaluation.retrieval import Question, evaluate, load, save
from app.schemas.answers import AnswerStatus, AskResponse
from app.schemas.github import DiscussionSourceType
from app.schemas.retrieval import RetrievedEvidence

DATASETS = Path(__file__).parents[3] / "evaluation/datasets"


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


@pytest.mark.parametrize("name", ["questions", "heldout"])
def test_datasets_are_well_formed(name: str) -> None:
    questions = load(DATASETS / f"{name}.jsonl")

    assert len(questions) >= 30
    for q in questions:
        assert q.answerable == bool(q.expected_threads), q.question


def test_held_out_questions_are_new() -> None:
    tuning = {q.question for q in load(DATASETS / "questions.jsonl")}

    assert not tuning & {q.question for q in load(DATASETS / "heldout.jsonl")}


def test_save_appends_runs(tmp_path: Path) -> None:
    history = tmp_path / "results/history.jsonl"

    save(history, "baseline", "questions", {"hit@1": 0.7})
    save(history, "better", "questions", {"hit@1": 0.8})

    lines = history.read_text().splitlines()
    assert len(lines) == 2
    assert '"label": "better"' in lines[1] and '"hit@1": 0.8' in lines[1]
