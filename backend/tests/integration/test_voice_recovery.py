
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.voice_job import VoiceJobStatus
from app.repositories.voice_job_repository import (
    VoiceJobRepository,
)


def test_expired_job_is_detected_for_recovery(
    db_session,
    test_users,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    job, created = repo.create_or_get(
        user_id=user.id,
        chat_id=700,
        message_id=300,
        file_id="test-recovery-audio",
    )

    assert created is True

    claim = repo.claim_for_processing(job.id)
    assert claim is not None

    # Simulate a crashed worker whose lease expired.
    job.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    )
    db_session.commit()

    recoverable_ids = repo.find_recoverable_jobs()

    assert job.id in recoverable_ids


def test_recovered_job_gets_new_lease(
    db_session,
    test_users,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    job, _ = repo.create_or_get(
        user_id=user.id,
        chat_id=700,
        message_id=301,
        file_id="test-recovery-audio-2",
    )

    first_claim = repo.claim_for_processing(job.id)
    assert first_claim is not None

    _, old_token = first_claim

    job.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    )
    db_session.commit()

    second_claim = repo.claim_for_processing(job.id)
    assert second_claim is not None

    recovered_job, new_token = second_claim

    assert new_token != old_token
    assert recovered_job.status == VoiceJobStatus.PROCESSING
    assert recovered_job.attempts == 2
