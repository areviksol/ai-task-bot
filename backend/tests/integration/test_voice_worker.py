
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.voice_job import VoiceJob, VoiceJobStatus
from app.repositories.voice_job_repository import VoiceJobRepository
from app.workers.tasks import transcribe_voice
from unittest.mock import Mock

from celery.exceptions import Retry
from openai import APIConnectionError, RateLimitError

def test_worker_completes_voice_job(
    db_session,
    test_users,
    test_engine,
    monkeypatch,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    job, created = repo.create_or_get(
        user_id=user.id,
        chat_id=1100,
        message_id=600,
        file_id="fake-voice-file",
    )

    assert created is True
    job_id = job.id

    # Worker sessions use the isolated test database.
    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    # Disable real heartbeat threads for this test.
    with (
        patch(
            "app.workers.tasks.VoiceLeaseHeartbeat"
        ) as heartbeat_class,
        patch(
            "app.workers.tasks.TranscriptionService"
        ) as transcription_class,
        patch(
            "app.workers.tasks.publish_task_changed"
        ) as publish,
        patch(
            "app.workers.tasks.notify_safely"
        ) as notify,
    ):
        heartbeat_class.return_value.lease_lost = False

        transcription_class.return_value.transcribe.return_value = (
            "Prepare tomorrow's project presentation"
        )

        # Calling .run() executes the task locally.
        # Nothing is sent to Celery's Redis broker.
        result = transcribe_voice.run(str(job_id))

    assert result["status"] == "completed"

    db_session.expire_all()

    saved_job = db_session.get(VoiceJob, job_id)

    assert saved_job is not None
    assert saved_job.status == VoiceJobStatus.COMPLETED
    assert saved_job.task_id is not None
    assert saved_job.lease_token is None
    assert saved_job.lease_expires_at is None

    saved_task = db_session.get(Task, saved_job.task_id)

    assert saved_task is not None
    assert saved_task.title == (
        "Prepare tomorrow's project presentation"
    )
    assert saved_task.user_id == user.id

    publish.assert_called_once()
    notify.assert_called_once()


def test_completed_voice_job_is_not_processed_again(
    db_session,
    test_users,
    test_engine,
    monkeypatch,
):
    user, _ = test_users
    repo = VoiceJobRepository(db_session)

    job, _ = repo.create_or_get(
        user_id=user.id,
        chat_id=1100,
        message_id=601,
        file_id="fake-duplicate-file",
    )

    claim = repo.claim_for_processing(job.id)
    assert claim is not None

    _, lease_token = claim

    task = repo.complete_with_task(
        job_id=job.id,
        lease_token=lease_token,
        transcription="Already processed voice message",
    )

    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    with (
        patch(
            "app.workers.tasks.TranscriptionService"
        ) as transcription,
        patch(
            "app.workers.tasks.publish_task_changed"
        ) as publish,
        patch(
            "app.workers.tasks.notify_safely"
        ) as notify,
    ):
        result = transcribe_voice.run(str(job.id))

    assert result["status"] == "skipped"

    transcription.assert_not_called()
    publish.assert_not_called()
    notify.assert_not_called()

    db_session.expire_all()

    saved_job = db_session.get(VoiceJob, job.id)
    assert saved_job is not None
    assert saved_job.task_id == task.id



def register_test_voice_job(
    db_session,
    user_id,
    message_id,
):
    repo = VoiceJobRepository(db_session)

    job, created = repo.create_or_get(
        user_id=user_id,
        chat_id=1200,
        message_id=message_id,
        file_id=f"fake-voice-{message_id}",
    )

    assert created is True
    return job


def test_worker_marks_quota_exhaustion_as_failed(
    db_session,
    test_users,
    test_engine,
    monkeypatch,
):
    user, _ = test_users
    job = register_test_voice_job(
        db_session,
        user.id,
        701,
    )

    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    quota_error = RateLimitError(
        "Insufficient quota",
        response=Mock(
            status_code=429,
            headers={},
            request=Mock(),
        ),
        body={
            "error": {
                "code": "insufficient_quota",
                "message": "Quota exhausted",
            }
        },
    )

    with (
        patch(
            "app.workers.tasks.VoiceLeaseHeartbeat"
        ) as heartbeat,
        patch(
            "app.workers.tasks.TranscriptionService"
        ) as transcription,
        patch(
            "app.workers.tasks.publish_task_changed"
        ) as publish,
        patch(
            "app.workers.tasks.notify_safely"
        ) as notify,
    ):
        heartbeat.return_value.lease_lost = False
        transcription.return_value.transcribe.side_effect = (
            quota_error
        )

        result = transcribe_voice.run(str(job.id))

    assert result["status"] == "failed"
    publish.assert_not_called()
    notify.assert_called_once()

    db_session.expire_all()
    saved_job = db_session.get(VoiceJob, job.id)

    assert saved_job.status == VoiceJobStatus.FAILED
    assert saved_job.task_id is None
    assert saved_job.lease_token is None



def test_worker_discards_result_after_losing_lease(
    db_session,
    test_users,
    test_engine,
    monkeypatch,
):
    user, _ = test_users
    job = register_test_voice_job(
        db_session,
        user.id,
        702,
    )

    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    with (
        patch(
            "app.workers.tasks.VoiceLeaseHeartbeat"
        ) as heartbeat,
        patch(
            "app.workers.tasks.TranscriptionService"
        ) as transcription,
        patch(
            "app.workers.tasks.publish_task_changed"
        ) as publish,
        patch(
            "app.workers.tasks.notify_safely"
        ) as notify,
    ):
        heartbeat.return_value.lease_lost = True
        transcription.return_value.transcribe.return_value = (
            "This result must be discarded"
        )

        result = transcribe_voice.run(str(job.id))

    assert result["status"] == "stale"
    publish.assert_not_called()
    notify.assert_not_called()

    db_session.expire_all()
    saved_job = db_session.get(VoiceJob, job.id)

    assert saved_job.status == VoiceJobStatus.PROCESSING
    assert saved_job.task_id is None


def test_worker_requests_retry_on_connection_error(
    db_session,
    test_users,
    test_engine,
    monkeypatch,
):
    user, _ = test_users
    job = register_test_voice_job(
        db_session,
        user.id,
        703,
    )

    monkeypatch.setattr(
        "app.workers.tasks.SessionLocal",
        lambda: Session(test_engine),
    )

    connection_error = APIConnectionError(
        request=Mock(),
    )

    with (
        patch(
            "app.workers.tasks.VoiceLeaseHeartbeat"
        ) as heartbeat,
        patch(
            "app.workers.tasks.TranscriptionService"
        ) as transcription,
        patch(
            "app.workers.tasks.retry_voice_job"
        ) as retry,
        patch(
            "app.workers.tasks.publish_task_changed"
        ) as publish,
    ):
        heartbeat.return_value.lease_lost = False
        transcription.return_value.transcribe.side_effect = (
            connection_error
        )
        retry.return_value = {
            "status": "retry_requested"
        }

        result = transcribe_voice.run(str(job.id))

    assert result["status"] == "retry_requested"
    retry.assert_called_once()
    publish.assert_not_called()
