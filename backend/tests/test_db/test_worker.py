from contextlib import nullcontext

from sqlalchemy.orm import Session

from app.db import crud
from app.models import Job, JobKind, JobStatus
from app.services import jobs
from app.services.worker import run_next_job


def queue(session: Session, token: str | None = None) -> Job:
    repo = crud.create_repository(
        session, full_name="a/b", html_url="https://github.com/a/b"
    )
    job = jobs.enqueue(session, JobKind.SYNC, repo.id, token=token)
    assert job is not None
    return job


def test_runs_a_job_with_its_pasted_token(db_session: Session) -> None:
    job = queue(db_session, token="ghp_x")
    calls: list = []

    ran = run_next_job(
        JobKind.SYNC,
        lambda: nullcontext(db_session),
        {JobKind.SYNC: lambda j, token: calls.append((j.id, token))},
    )

    assert ran is True
    assert calls == [(job.id, "ghp_x")]
    assert job.status is JobStatus.DONE


def test_a_crashing_job_is_queued_again_with_its_error(db_session: Session) -> None:
    job = queue(db_session)

    def crash(*_: object) -> None:
        raise RuntimeError("Ollama is not running")

    run_next_job(JobKind.SYNC, lambda: nullcontext(db_session), {JobKind.SYNC: crash})

    assert job.status is JobStatus.QUEUED
    assert job.attempts == 1
    assert job.last_error == "Ollama is not running"


def test_nothing_to_do_returns_false(db_session: Session) -> None:
    assert run_next_job(JobKind.SYNC, lambda: nullcontext(db_session), {}) is False
