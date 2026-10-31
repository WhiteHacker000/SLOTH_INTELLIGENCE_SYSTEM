import logging
import re
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.extraction.prompt import SYSTEM_PROMPT, Message, build_prompt, build_thread
from app.generation.llm import LanguageModel, generate_validated
from app.models import Comment, Decision, DecisionEvidence, Discussion
from app.schemas.decisions import DecisionExtraction, DecisionStatus, ExtractionResult

logger = logging.getLogger(__name__)

FINAL_STATUSES = {DecisionStatus.ACCEPTED, DecisionStatus.REJECTED}


def extract_decisions(
    session: Session, model: LanguageModel, model_name: str, discussion: Discussion
) -> list[Decision]:
    """Extract decisions from one issue or PR, replacing earlier results."""
    comments = list(
        session.scalars(
            select(Comment)
            .where(Comment.discussion_id == discussion.id)
            .order_by(Comment.created_at)
        )
    )
    messages = build_thread(discussion, comments)
    result = generate_validated(
        model, SYSTEM_PROMPT, build_prompt(discussion, messages), ExtractionResult
    )

    previous = select(DecisionEvidence.decision_id).where(
        DecisionEvidence.discussion_id == discussion.id
    )
    session.execute(delete(Decision).where(Decision.id.in_(previous)))

    by_id = {message.id: message for message in messages}
    saved = []
    for extracted in result.decisions:
        evidence = _checked_evidence(extracted, by_id, discussion.id)
        if not evidence:
            logger.info("Dropped decision without real evidence: %s", extracted.title)
            continue
        status = extracted.status
        if status in FINAL_STATUSES and all(e.comment_id is None for e in evidence):
            # The opening post alone cannot show that anyone else agreed.
            status = DecisionStatus.PROPOSED
        decision = Decision(
            **extracted.model_dump(exclude={"evidence", "status"}),
            status=status,
            repository_id=discussion.repository_id,
            extraction_model=model_name,
        )
        session.add(decision)
        session.flush()
        for item in evidence:
            item.decision_id = decision.id
            session.add(item)
        saved.append(decision)
    session.flush()
    return saved


def _checked_evidence(
    extracted: DecisionExtraction, messages: dict[str, Message], discussion_id: UUID
) -> list[DecisionEvidence]:
    """Keep only quotes that really appear in the message they cite."""
    evidence = []
    for item in extracted.evidence:
        message = messages.get(item.message_id)
        if message is None or _normalize(item.quote) not in _normalize(message.text):
            continue
        evidence.append(
            DecisionEvidence(
                discussion_id=discussion_id,
                comment_id=message.comment_id,
                excerpt=item.quote,
                source_url=message.source_url,
            )
        )
    return evidence


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()
