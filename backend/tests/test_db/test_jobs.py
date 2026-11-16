from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db import crud
from app.models import JobKind, JobStatus, Repository
from app.services import jobs


def repo(session: Session, full_name: str = "a/b") -> Repository:
    return crud.create_repository(
        session, full_name=full_name, html_url=f"https://github.com/{full_name}"
    )


def test_only_one_active_job_per_kind_and_repository(db_session: Session) -> None:
    r = repo(db_session)

    first = jobs.enqueue(db_session, JobKind.SYNC, r.id)
    duplicate = jobs.enqueue(db_session, JobKind.SYNC, r.id)
    other_kind = jobs.enqueue(db_session, JobKind.EXTRACT, r.id, {"ids": []})

    assert first is not None and other_kind is not None
    assert duplicate is None
    assert jobs.has_active(db_session, r.id, JobKind.EXTRACT)


def test_claim_takes_the_oldest_due_job(db_session: Session) -> None:
    r = repo(db_session)
    later = jobs.enqueue(db_session, JobKind.SYNC, r.id)
    assert later is not None
    later.run_after = datetime.now(UTC) + timedelta(minutes=5)
    other = repo(db_session, "a/c")
    due = jobs.enqueue(db_session, JobKind.SYNC, other.id)
    extract = jobs.enqueue(db_session, JobKind.EXTRACT, r.id)

    claimed = jobs.claim_next(db_session, JobKind.SYNC)

    assert claimed is due
    assert claimed is not None
    assert claimed.status is JobStatus.RUNNING
    assert claimed.attempts == 1
    assert jobs.claim_next(db_session, JobKind.SYNC) is None
    assert jobs.claim_next(db_session, JobKind.EXTRACT) is extract


def test_failed_jobs_retry_later_then_give_up(db_session: Session) -> None:
    job = jobs.enqueue(db_session, JobKind.SYNC, repo(db_session).id)
    assert job is not None

    for attempt in range(1, jobs.MAX_ATTEMPTS + 1):
        job.run_after = datetime.now(UTC)
        assert jobs.claim_next(db_session, JobKind.SYNC) is job
        jobs.finish(db_session, job, "Ollama is not running")
        if attempt < jobs.MAX_ATTEMPTS:
            assert job.status is JobStatus.QUEUED
            assert job.run_after > datetime.now(UTC)

    assert job.status is JobStatus.FAILED
    assert job.last_error == "Ollama is not running"
    assert job.finished_at is not None


def test_pasted_token_stays_out_of_the_database(db_session: Session) -> None:
    job = jobs.enqueue(db_session, JobKind.SYNC, repo(db_session).id, token="ghp_x")
    assert job is not None

    assert jobs.token_for(job) == "ghp_x"
    assert "ghp_x" not in str(job.payload)

    jobs.claim_next(db_session, JobKind.SYNC)
    jobs.finish(db_session, job)

    assert job.status is JobStatus.DONE
    assert jobs.token_for(job) is None


def test_jobs_cut_off_by_a_restart_go_back_in_the_queue(db_session: Session) -> None:
    job = jobs.enqueue(db_session, JobKind.EXTRACT, repo(db_session).id)
    jobs.claim_next(db_session, JobKind.EXTRACT)

    assert jobs.recover_interrupted(db_session) == 1
    assert job is not None
    assert job.status is JobStatus.QUEUED
    assert job.attempts == 0
    assert job.last_error == "Interrupted by a server restart"
    assert jobs.claim_next(db_session, JobKind.EXTRACT) is job
