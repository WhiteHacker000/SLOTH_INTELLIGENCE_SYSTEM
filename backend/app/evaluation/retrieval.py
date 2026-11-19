"""Measure search and answers against labelled questions.

Usage, from backend/ with the database, embeddings and (for --answers) Ollama:

    python -m app.evaluation.retrieval ../evaluation/datasets/questions.jsonl
    python -m app.evaluation.retrieval ../evaluation/datasets/questions.jsonl --answers

Add --save "what changed" to append the result to evaluation/results/history.jsonl.
"""

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.evaluation.metrics import hit_at_k, mean, precision, reciprocal_rank
from app.schemas.answers import AnswerStatus, AskResponse
from app.schemas.retrieval import RetrievedEvidence


@dataclass
class Question:
    repository: str
    question: str
    expected_threads: list[int]
    answerable: bool = True


Search = Callable[[Question], list[RetrievedEvidence]]
Answer = Callable[[Question, list[RetrievedEvidence]], AskResponse]


def load(path: Path) -> list[Question]:
    lines = path.read_text().splitlines()
    return [Question(**json.loads(line)) for line in lines if line.strip()]


def threads(evidence: list[RetrievedEvidence]) -> list[int]:
    """Thread numbers in rank order, each once."""
    return list(dict.fromkeys(e.discussion_number for e in evidence))


def evaluate(
    questions: list[Question], search: Search, answer: Answer | None = None, k=5
) -> dict[str, float | int | None]:
    answerable = [q for q in questions if q.answerable]
    found = {id(q): search(q) for q in questions}
    ranked = {id(q): threads(found[id(q)]) for q in questions}
    report: dict[str, float | int | None] = {
        "questions": len(answerable),
        f"hit@{k}": mean(
            hit_at_k(ranked[id(q)], set(q.expected_threads), k) for q in answerable
        ),
        "hit@1": mean(
            hit_at_k(ranked[id(q)], set(q.expected_threads), 1) for q in answerable
        ),
        "mrr": mean(
            reciprocal_rank(ranked[id(q)], set(q.expected_threads)) for q in answerable
        ),
    }
    if answer is None:
        return report
    replies = {id(q): answer(q, found[id(q)]) for q in questions}
    unanswerable = [q for q in questions if not q.answerable]
    report |= {
        "answered": mean(
            replies[id(q)].status is AnswerStatus.ANSWERED for q in answerable
        ),
        "citation_precision": mean(
            precision(threads(replies[id(q)].citations), set(q.expected_threads))
            for q in answerable
        ),
        "unanswerable": len(unanswerable),
        "abstained": mean(
            replies[id(q)].status is AnswerStatus.INSUFFICIENT_EVIDENCE
            for q in unanswerable
        ),
    }
    return report


def main() -> None:
    from app.api.lookups import repository_id_for
    from app.db.session import SessionLocal
    from app.embeddings.embedder import get_embedder
    from app.generation.answer import answer_from_evidence
    from app.generation.llm import get_language_model
    from app.retrieval.search import THREAD_CANDIDATES, rank_threads, search_chunks

    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--answers", action="store_true", help="also run the LLM")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--save", metavar="LABEL", help="append to the history")
    args = parser.parse_args()

    embedder = get_embedder()
    with SessionLocal() as session:

        def chunks(q: Question, limit: int) -> list[RetrievedEvidence]:
            return search_chunks(
                session,
                embedder.embed_query(q.question),
                repository_id=repository_id_for(session, q.repository),
                limit=limit,
            )

        # Ranked like /search; answers use raw chunks as evidence, like /ask.
        def search(q: Question) -> list[RetrievedEvidence]:
            return rank_threads(chunks(q, THREAD_CANDIDATES), args.k)

        def answer(q: Question, _: list[RetrievedEvidence]) -> AskResponse:
            return answer_from_evidence(get_language_model(), q.question, chunks(q, 6))

        report = evaluate(
            load(args.dataset), search, answer if args.answers else None, args.k
        )
    print(json.dumps(report, indent=2))
    if args.save:
        save(HISTORY, args.save, args.dataset.stem, report)


HISTORY = Path(__file__).parents[3] / "evaluation/results/history.jsonl"


def save(history: Path, label: str, dataset: str, report: dict) -> None:
    """Append one run, so improvements can be shown as before and after."""
    history.parent.mkdir(parents=True, exist_ok=True)
    entry = {"date": date.today().isoformat(), "label": label, "dataset": dataset}
    with history.open("a") as file:
        file.write(json.dumps(entry | report) + "\n")


if __name__ == "__main__":
    main()
