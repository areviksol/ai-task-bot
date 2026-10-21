
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.voice_job import VoiceJobStatus
from app.repositories.voice_job_repository import VoiceJobRepository
from app.workers.tasks import recover_voice_jobs


def register_job(
    db_session,
    user_id,
    message_id,
):
    repo = VoiceJobRepository(db_session)

    job, created = repo.create_or_get(
        user_id=user_id,
        chat_id=900,
        message_id=message_id,
        file_id=f"test-file-{message_id}",
    )

    assert created is True

    return job, repo



def test_recovery_dispatches_expired_job(
    db_session,
    test_users,
    monkeypatch,
    test_engine,
):
    user, _ = test_users

    job, repo = register_job(
        db_session,
        user.id,
        message_id=401,
    )

    claim = repo.claim_for_processing(job.id)
    assert claim is not None

    job.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    )
    db_session.commit()

    # Redirect the worker's database connection
    # to the isolated test database.
    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    with patch(
        "app.workers.tasks.transcribe_voice.apply_async"
    ) as dispatch:
        result = recover_voice_jobs()

    assert result["scheduled"] == 1

    dispatch.assert_called_once_with(
        kwargs={"job_id": str(job.id)}
    )


def test_recovery_ignores_active_lease(
    db_session,
    test_users,
    monkeypatch,
    test_engine,
):
    user, _ = test_users

    job, repo = register_job(
        db_session,
        user.id,
        message_id=402,
    )

    claim = repo.claim_for_processing(job.id)
    assert claim is not None

    # The lease is still valid.
    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    with patch(
        "app.workers.tasks.transcribe_voice.apply_async"
    ) as dispatch:
        result = recover_voice_jobs()

    assert result["scheduled"] == 0
    dispatch.assert_not_called()


def test_recovery_ignores_completed_job(
    db_session,
    test_users,
    monkeypatch,
    test_engine,
):
    user, _ = test_users

    job, repo = register_job(
        db_session,
        user.id,
        message_id=403,
    )

    claim = repo.claim_for_processing(job.id)
    assert claim is not None

    _, lease_token = claim

    repo.complete_with_task(
        job_id=job.id,
        lease_token=lease_token,
        transcription="Completed test task",
    )

    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    with patch(
        "app.workers.tasks.transcribe_voice.apply_async"
    ) as dispatch:
        result = recover_voice_jobs()

    assert result["scheduled"] == 0
    dispatch.assert_not_called()
