import pytest
from pydantic import ValidationError

from app.schemas.retrieval import RetrievalRequest, RetrievedEvidence


def test_retrieval_request_defaults_to_bounded_results() -> None:
    request = RetrievalRequest(query="Why was PostgreSQL selected?")

    assert request.limit == 5
    assert request.source_types == []


def test_retrieval_request_rejects_unbounded_result_count() -> None:
    with pytest.raises(ValidationError):
        RetrievalRequest(query="decision", limit=100)


def test_retrieved_evidence_requires_a_valid_similarity_score() -> None:
    with pytest.raises(ValidationError):
        RetrievedEvidence(
            content="A relevant discussion excerpt",
            source_url="https://github.com/example/project/issues/7",
            similarity=1.5,
            repository_full_name="example/project",
            source_type="issue",
        )
