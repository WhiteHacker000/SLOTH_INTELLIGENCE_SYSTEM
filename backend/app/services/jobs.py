"""A small job queue in PostgreSQL, so background work survives restarts."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobKind, JobStatus

MAX_ATTEMPTS = 3
RETRY_DELAY = timedelta(seconds=30)
ACTIVE = (JobStatus.QUEUED, JobStatus.RUNNING)

# Tokens pasted for one sync. Kept in memory only, never in the database, so a
# sync retried after a restart runs with GITHUB_TOKEN or anonymously.
_tokens: dict[UUID, str] = {}


def enqueue(
    session: Session,
    kind: JobKind,
    repository_id: UUID,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
) -> Job | None:
    """Queue a job, or return None if one of this kind is already active."""
    if has_active(session, repository_id, kind):
        return None
    job = Job(kind=kind, repository_id=repository_id, payload=payload or {})
    session.add(job)
    session.flush()
    if token:
        _tokens[job.id] = token
    return job


def has_active(session: Session, repository_id: UUID, kind: JobKind) -> bool:
    return (
        session.scalar(
            select(Job.id).where(
                Job.repository_id == repository_id,
                Job.kind == kind,
                Job.status.in_(ACTIVE),
            )
        )
        is not None
    )


def claim_next(session: Session) -> Job | None:
    """Take the oldest job that is due, skipping rows another worker holds."""
    job = session.scalars(
        select(Job)
        .where(Job.status == JobStatus.QUEUED, Job.run_after <= datetime.now(UTC))
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if job is not None:
        job.status = JobStatus.RUNNING
        job.attempts += 1
    return job


def token_for(job: Job) -> str | None:
    return _tokens.get(job.id)


def finish(session: Session, job: Job, error: str | None = None) -> None:
    """Mark a job done, or queue it again after a delay until attempts run out."""
    now = datetime.now(UTC)
    job.last_error = error
    if error is not None and job.attempts < MAX_ATTEMPTS:
        job.status = JobStatus.QUEUED
        job.run_after = now + RETRY_DELAY * job.attempts
        return
    job.status = JobStatus.FAILED if error is not None else JobStatus.DONE
    job.finished_at = now
    _tokens.pop(job.id, None)


def recover_interrupted(session: Session) -> int:
    """Put jobs left running by a crash or restart back in the queue."""
    stuck = list(session.scalars(select(Job).where(Job.status == JobStatus.RUNNING)))
    for job in stuck:
        finish(session, job, "Interrupted by a server restart")
    return len(stuck)
