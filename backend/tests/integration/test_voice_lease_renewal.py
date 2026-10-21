
from datetime import datetime, timedelta, timezone

from app.models.voice_job import VoiceJobStatus
from app.repositories.voice_job_repository import (
    VoiceJobRepository,
)


def create_processing_job(db_session, user_id, message_id):
    repo = VoiceJobRepository(db_session)

    job, _ = repo.create_or_get(
        user_id=user_id,
        chat_id=800,
        message_id=message_id,
        file_id=f"test-audio-{message_id}",
    )

    claim = repo.claim_for_processing(job.id)
    assert claim is not None

    _, lease_token = claim

    return repo, job, lease_token


def test_current_worker_can_renew_lease(
    db_session,
    test_users,
):
    user, _ = test_users

    repo, job, token = create_processing_job(
        db_session, user.id, 501
    )

    original_expiration = job.lease_expires_at
    assert original_expiration is not None

    renewed = repo.renew_lease(job.id, token)

    assert renewed is True

    db_session.refresh(job)

    assert job.status == VoiceJobStatus.PROCESSING
    assert job.lease_token == token
    assert job.lease_expires_at > original_expiration
    assert job.attempts == 1


def test_stale_worker_cannot_renew_lease(
    db_session,
    test_users,
):
    user, _ = test_users

    repo, job, old_token = create_processing_job(
        db_session, user.id, 502
    )

    # Simulate expiration of Worker A's lease.
    job.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    )
    db_session.commit()

    # Worker B takes ownership.
    claim = repo.claim_for_processing(job.id)
    assert claim is not None

    _, new_token = claim

    assert new_token != old_token

    renewed = repo.renew_lease(
        job.id,
        old_token,
    )

    assert renewed is False

    db_session.refresh(job)

    assert job.lease_token == new_token
    assert job.status == VoiceJobStatus.PROCESSING


def test_expired_lease_cannot_be_renewed(
    db_session,
    test_users,
):
    user, _ = test_users

    repo, job, token = create_processing_job(
        db_session, user.id, 503
    )

    job.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=10)
    )
    db_session.commit()

    renewed = repo.renew_lease(job.id, token)

    assert renewed is False


def test_completed_job_cannot_renew_lease(
    db_session,
    test_users,
):
    user, _ = test_users

    repo, job, token = create_processing_job(
        db_session, user.id, 504
    )

    repo.complete_with_task(
        job_id=job.id,
        lease_token=token,
        transcription="Completed task",
    )

    renewed = repo.renew_lease(job.id, token)

    assert renewed is False
