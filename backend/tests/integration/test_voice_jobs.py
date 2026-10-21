
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.task import Task
from app.models.voice_job import VoiceJob, VoiceJobStatus
from app.repositories.voice_job_repository import (
    StaleVoiceLeaseError,
    VoiceJobRepository,
)


def test_duplicate_voice_message_creates_one_job(
    db_session,
    test_users,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    first, first_created = repo.create_or_get(
        user_id=user.id,
        chat_id=12345,
        message_id=100,
        file_id="telegram-file-abc",
    )

    second, second_created = repo.create_or_get(
        user_id=user.id,
        chat_id=12345,
        message_id=100,
        file_id="telegram-file-abc",
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id

    count = db_session.scalar(
        select(func.count(Task.id)).where(
            Task.telegram_chat_id == 12345,
            Task.telegram_message_id == 100,
        )
    )

    # Registering a voice job does not create a task yet.
    assert count == 0

    job_count = db_session.scalar(
        select(func.count(VoiceJob.id)).where(
            VoiceJob.telegram_chat_id == 12345,
            VoiceJob.telegram_message_id == 100,
        )
    )

    assert job_count == 1


def test_voice_job_cannot_be_claimed_twice(
    db_session,
    test_users,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    job, _ = repo.create_or_get(
        user_id=user.id,
        chat_id=12345,
        message_id=101,
        file_id="telegram-file-def",
    )

    first_claim = repo.claim_for_processing(job.id)

    assert first_claim is not None

    claimed_job, lease_token = first_claim

    assert claimed_job.status == VoiceJobStatus.PROCESSING
    assert claimed_job.lease_token == lease_token

    # The lease is still active, so a second claim fails.
    second_claim = repo.claim_for_processing(job.id)

    assert second_claim is None

    db_session.refresh(job)

    assert job.status == VoiceJobStatus.PROCESSING
    assert job.attempts == 1
    assert job.lease_token == lease_token
    assert job.lease_expires_at is not None


def test_voice_job_creates_task_atomically(
    db_session,
    test_users,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    job, _ = repo.create_or_get(
        user_id=user.id,
        chat_id=12345,
        message_id=102,
        file_id="telegram-file-ghi",
    )

    claim = repo.claim_for_processing(job.id)

    assert claim is not None

    _, lease_token = claim

    task = repo.complete_with_task(
        job_id=job.id,
        lease_token=lease_token,
        transcription="Schedule a meeting tomorrow",
    )

    db_session.refresh(job)

    assert job.status == VoiceJobStatus.COMPLETED
    assert job.task_id == task.id
    assert job.transcription == "Schedule a meeting tomorrow"
    assert job.lease_token is None
    assert job.lease_expires_at is None

    assert task.user_id == user.id
    assert task.title == "Schedule a meeting tomorrow"

    task_count = db_session.scalar(
        select(func.count(Task.id)).where(
            Task.telegram_chat_id == 12345,
            Task.telegram_message_id == 102,
        )
    )

    assert task_count == 1


def test_failed_voice_job_does_not_create_task(
    db_session,
    test_users,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    job, _ = repo.create_or_get(
        user_id=user.id,
        chat_id=12345,
        message_id=103,
        file_id="telegram-file-jkl",
    )

    claim = repo.claim_for_processing(job.id)

    assert claim is not None

    _, lease_token = claim

    updated = repo.mark_failed(
        job_id=job.id,
        lease_token=lease_token,
        error_message="Transcription quota exhausted",
    )

    db_session.refresh(job)

    assert updated is True
    assert job.status == VoiceJobStatus.FAILED
    assert job.task_id is None
    assert job.error_message == "Transcription quota exhausted"
    assert job.lease_token is None
    assert job.lease_expires_at is None

    task_count = db_session.scalar(
        select(func.count(Task.id)).where(
            Task.telegram_chat_id == 12345,
            Task.telegram_message_id == 103,
        )
    )

    assert task_count == 0


def test_expired_lease_can_be_reclaimed(
    db_session,
    test_users,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    job, _ = repo.create_or_get(
        user_id=user.id,
        chat_id=500,
        message_id=200,
        file_id="file-recovery-test",
    )

    first_claim = repo.claim_for_processing(job.id)

    assert first_claim is not None

    _, old_token = first_claim

    # Simulate a worker crash and an expired lease.
    job.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    )
    db_session.commit()

    second_claim = repo.claim_for_processing(job.id)

    assert second_claim is not None

    reclaimed_job, new_token = second_claim

    assert new_token != old_token
    assert reclaimed_job.attempts == 2
    assert reclaimed_job.status == VoiceJobStatus.PROCESSING
    assert reclaimed_job.lease_token == new_token
    assert reclaimed_job.lease_expires_at is not None


def test_stale_worker_cannot_create_task(
    db_session,
    test_users,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    job, _ = repo.create_or_get(
        user_id=user.id,
        chat_id=500,
        message_id=201,
        file_id="file-stale-worker",
    )

    first_claim = repo.claim_for_processing(job.id)

    assert first_claim is not None

    _, old_token = first_claim

    # Expire Worker A's lease.
    job.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    )
    db_session.commit()

    # Worker B reclaims the job.
    second_claim = repo.claim_for_processing(job.id)

    assert second_claim is not None

    _, new_token = second_claim

    assert new_token != old_token

    # Worker A must not create a task.
    with pytest.raises(StaleVoiceLeaseError):
        repo.complete_with_task(
            job_id=job.id,
            lease_token=old_token,
            transcription="Old transcription result",
        )

    # Worker A must not mark Worker B's job as failed.
    old_worker_failed = repo.mark_failed(
        job_id=job.id,
        lease_token=old_token,
        error_message="Old worker failure",
    )

    assert old_worker_failed is False

    # Worker B can complete the job.
    task = repo.complete_with_task(
        job_id=job.id,
        lease_token=new_token,
        transcription="Valid transcription result",
    )

    db_session.refresh(job)

    assert job.status == VoiceJobStatus.COMPLETED
    assert job.task_id == task.id
    assert job.transcription == "Valid transcription result"
    assert job.lease_token is None
    assert job.lease_expires_at is None

    task_count = db_session.scalar(
        select(func.count(Task.id)).where(
            Task.telegram_chat_id == 500,
            Task.telegram_message_id == 201,
        )
    )

    assert task_count == 1
