import logging
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.extraction.extractor import extract_decisions
from app.generation.llm import LanguageModelError, get_language_model
from app.models import Comment, Decision, DecisionEvidence, Discussion
from app.schemas.decisions import DecisionRead, EvidenceRead

logger = logging.getLogger(__name__)

# About 15 seconds per thread on a laptop, so one run takes a few minutes.
THREADS_PER_RUN = 15


def list_decisions(session: Session, repository_id: UUID) -> list[DecisionRead]:
    decisions = list(
        session.scalars(
            select(Decision)
            .where(Decision.repository_id == repository_id)
            .order_by(Decision.created_at.desc())
        )
    )
    evidence: dict[UUID, list[EvidenceRead]] = defaultdict(list)
    for item in session.scalars(
        select(DecisionEvidence).where(
            DecisionEvidence.decision_id.in_([d.id for d in decisions])
        )
    ):
        evidence[item.decision_id].append(
            EvidenceRead(excerpt=item.excerpt, source_url=item.source_url)
        )
    return [
        DecisionRead(
            id=d.id,
            title=d.title,
            decision=d.decision,
            rationale=d.rationale,
            alternatives=d.alternatives,
            evidence=evidence[d.id],
        )
        for d in decisions
    ]


def threads_to_extract(
    session: Session, repository_id: UUID, limit: int = THREADS_PER_RUN
) -> list[UUID]:
    """The most-discussed threads that have not been processed yet."""
    comment_count = (
        select(func.count())
        .where(Comment.discussion_id == Discussion.id)
        .scalar_subquery()
    )
    return list(
        session.scalars(
            select(Discussion.id)
            .where(
                Discussion.repository_id == repository_id,
                Discussion.decisions_extracted_at.is_(None),
            )
            .order_by(comment_count.desc(), Discussion.number)
            .limit(limit)
        )
    )


def run_extraction(discussion_ids: list[UUID]) -> None:
    """Extract decisions thread by thread in the background, saving each one."""
    model, model_name = get_language_model(), get_settings().gemma_model
    with SessionLocal() as session:
        for discussion_id in discussion_ids:
            discussion = session.get(Discussion, discussion_id)
            if discussion is None:
                continue
            try:
                extract_decisions(session, model, model_name, discussion)
            except LanguageModelError as error:
                logger.warning("Extraction stopped: %s", error)
                session.rollback()
                return
            discussion.decisions_extracted_at = datetime.now(UTC)
            session.commit()
