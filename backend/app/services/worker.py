"""Runs queued syncs and extractions in background threads, one per kind."""

import logging
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Job, JobKind
from app.services import jobs
from app.services.decisions import run_extraction
from app.services.repositories import run_sync

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0
Handler = Callable[[Job, str | None], None]
SessionFactory = Callable[[], AbstractContextManager[Session]]


def _sync(job: Job, token: str | None) -> None:
    run_sync(job.repository_id, token)


def _extract(job: Job, _: str | None) -> None:
    run_extraction([UUID(i) for i in job.payload["discussion_ids"]])


HANDLERS: dict[JobKind, Handler] = {JobKind.SYNC: _sync, JobKind.EXTRACT: _extract}


def queue_sync(
    repository_id: UUID, token: str | None, user_id: UUID | None = None
) -> None:
    payload = {"user_id": str(user_id)} if user_id else None
    with SessionLocal() as session:
        jobs.enqueue(session, JobKind.SYNC, repository_id, payload, token)
        session.commit()


def queue_extraction(repository_id: UUID, discussion_ids: list[UUID]) -> None:
    payload = {"discussion_ids": [str(i) for i in discussion_ids]}
    with SessionLocal() as session:
        jobs.enqueue(session, JobKind.EXTRACT, repository_id, payload)
        session.commit()


def run_next_job(
    kind: JobKind,
    session_factory: SessionFactory = SessionLocal,
    handlers: dict[JobKind, Handler] = HANDLERS,
) -> bool:
    """Run one due job of this kind. Returns False if there was nothing to do."""
    with session_factory() as session:
        job = jobs.claim_next(session, kind)
        if job is None:
            return False
        session.commit()
        error = None
        try:
            handlers[job.kind](job, jobs.token_for(job))
        except Exception as exc:
            logger.exception("Job %s (%s) failed", job.id, job.kind)
            error = str(exc) or type(exc).__name__
        jobs.finish(session, job, error)
        session.commit()
    return True


def _work(kind: JobKind, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            busy = run_next_job(kind)
        except Exception:
            logger.exception("Job worker hit an error; retrying shortly")
            busy = False
        if not busy:
            stop.wait(POLL_SECONDS)


def start_worker() -> threading.Event:
    """Start one worker thread per job kind. Set the returned event to stop them.

    Separate threads keep a quick sync from waiting behind a long extraction.
    """
    try:
        with SessionLocal() as session:
            if recovered := jobs.recover_interrupted(session):
                logger.info("Requeued %d jobs cut off by a restart", recovered)
            session.commit()
    except Exception:
        logger.exception("Could not requeue interrupted jobs")
    stop = threading.Event()
    for kind in JobKind:
        threading.Thread(
            target=_work, args=(kind, stop), name=f"{kind}-worker", daemon=True
        ).start()
    return stop
