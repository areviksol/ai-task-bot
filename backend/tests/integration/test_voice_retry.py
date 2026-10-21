
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from celery.exceptions import Retry
from sqlalchemy.orm import Session

from app.models.voice_job import VoiceJob, VoiceJobStatus
from app.repositories.voice_job_repository import VoiceJobRepository
from app.workers.tasks import retry_voice_job


def create_processing_job(db_session, user_id, message_id):
    repo = VoiceJobRepository(db_session)

    job, created = repo.create_or_get(
        user_id=user_id,
        chat_id=1300,
        message_id=message_id,
        file_id=f"retry-test-{message_id}",
    )

    assert created is True

    claim = repo.claim_for_processing(job.id)
    assert claim is not None

    _, lease_token = claim

    return job.id, lease_token


def make_celery_task(retries=0, max_retries=3):
    task = Mock()
    task.request.retries = retries
    task.max_retries = max_retries

    # Simulate Celery's retry behavior without Redis.
    task.retry.side_effect = Retry("Simulated retry")

    return task


def test_temporary_failure_requeues_job(
    db_session,
    test_users,
    test_engine,
    monkeypatch,
):
    user, _ = test_users

    job_id, lease_token = create_processing_job(
        db_session, user.id, 801
    )

    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    celery_task = make_celery_task()

    with pytest.raises(Retry):
        retry_voice_job(
            celery_task,
            job_id,
            lease_token,
            1300,
            ConnectionError("Temporary failure"),
        )

    db_session.expire_all()
    job = db_session.get(VoiceJob, job_id)

    assert job.status == VoiceJobStatus.QUEUED
    assert job.lease_token is None
    assert job.lease_expires_at is None
    assert job.attempts == 1

    celery_task.retry.assert_called_once()


def test_stale_worker_cannot_requeue_job(
    db_session,
    test_users,
    test_engine,
    monkeypatch,
):
    user, _ = test_users

    job_id, old_token = create_processing_job(
        db_session, user.id, 802
    )

    job = db_session.get(VoiceJob, job_id)

    # Expire the original lease.
    job.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    )
    db_session.commit()

    repo = VoiceJobRepository(db_session)

    # Another worker takes ownership.
    claim = repo.claim_for_processing(job_id)
    assert claim is not None

    _, new_token = claim

    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    celery_task = make_celery_task()

    result = retry_voice_job(
        celery_task,
        job_id,
        old_token,
        1300,
        ConnectionError("Late failure"),
    )

    assert result["status"] == "stale"

    celery_task.retry.assert_not_called()

    db_session.refresh(job)

    assert job.status == VoiceJobStatus.PROCESSING
    assert job.lease_token == new_token


def test_retry_exhaustion_marks_job_failed(
    db_session,
    test_users,
    test_engine,
    monkeypatch,
):
    user, _ = test_users

    job_id, lease_token = create_processing_job(
        db_session, user.id, 803
    )

    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    celery_task = make_celery_task(
        retries=3,
        max_retries=3,
    )

    with patch(
        "app.workers.tasks.notify_safely"
    ) as notify:
        with pytest.raises(ConnectionError):
            retry_voice_job(
                celery_task,
                job_id,
                lease_token,
                1300,
                ConnectionError("Retries exhausted"),
            )

    db_session.expire_all()
    job = db_session.get(VoiceJob, job_id)

    assert job.status == VoiceJobStatus.FAILED
    assert job.task_id is None
    assert job.lease_token is None

    celery_task.retry.assert_not_called()
    notify.assert_called_once()
