
import logging
from uuid import UUID

import httpx
from openai import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.voice_job_repository import (
    VoiceJobRepository,
    StaleVoiceLeaseError
)
from app.services.transcription_service import (
    TranscriptionService,
)
from app.services.voice_job_service import VoiceJobService
from app.workers.celery_app import celery_app
from app.workers.lease_heartbeat import VoiceLeaseHeartbeat
from app.services.task_events import publish_task_changed

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5

class TranscriptionQuotaError(Exception):
    pass


def notify_telegram(chat_id: int, text: str) -> None:
    token = (
        get_settings()
        .telegram_bot_token.get_secret_value()
    )

    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
            },
        )
        response.raise_for_status()


def extract_error_code(exc: RateLimitError) -> str | None:
    body = exc.body

    if not isinstance(body, dict):
        return None

    details = body.get("error", body)

    if isinstance(details, dict):
        return details.get("code")

    return None


def notify_safely(chat_id: int, text: str) -> None:
    try:
        notify_telegram(chat_id, text)
    except Exception:
        logger.error(
            "Telegram notification failed for chat %s",
            chat_id,
        )


def get_voice_service(db) -> VoiceJobService:
    return VoiceJobService(VoiceJobRepository(db))


@celery_app.task(
    name="workers.test_task",
)
def test_task(message: str) -> dict:
    return {
        "status": "completed",
        "message": message,
    }


@celery_app.task(
    bind=True,
    name="workers.transcribe_voice",
    max_retries=3,
)
def transcribe_voice(self, job_id: str) -> dict:
    voice_job_id = UUID(job_id)

    # 1. Claim the job.
    with SessionLocal() as db:
        claim = get_voice_service(db).start_processing(
            voice_job_id
        )

        if claim is None:
            return {
                "status": "skipped",
                "job_id": job_id,
            }

        job, lease_token = claim
        file_id = job.telegram_file_id
        chat_id = job.telegram_chat_id
        user_id = job.user_id

    heartbeat = VoiceLeaseHeartbeat(
        job_id=voice_job_id,
        lease_token=lease_token,
    )

    try:
        # 2. Run transcription while the heartbeat is active.
        heartbeat.start()

        try:
            transcription = TranscriptionService().transcribe(
                file_id
            )
        finally:
            heartbeat.stop()

        # 3. A worker that has lost its lease must stop.
        if heartbeat.lease_lost:
            raise StaleVoiceLeaseError(
                "Worker lost ownership during transcription"
            )

        # 4. Save task and complete job atomically.
        # The repository checks lease validity again.
        with SessionLocal() as db:
            task = get_voice_service(db).complete_processing(
                job_id=voice_job_id,
                lease_token=lease_token,
                transcription=transcription,
            )

            task_id = str(task.id)
            title = task.title

    except StaleVoiceLeaseError:
        logger.warning(
            "Stale worker result discarded for job %s",
            job_id,
        )
        return {
            "status": "stale",
            "job_id": job_id,
        }

    except RateLimitError as exc:
        code = extract_error_code(exc)

        if code in {
            "credit_balance_exhausted",
            "insufficient_quota",
            "organization_spend_limit_exceeded",
            "project_spend_limit_exceeded",
        }:
            with SessionLocal() as db:
                changed = get_voice_service(db).fail_processing(
                    voice_job_id,
                    lease_token,
                    "Transcription quota exhausted",
                )

            if changed:
                notify_safely(
                    chat_id,
                    "Voice transcription is unavailable "
                    "because API credits are exhausted.",
                )

            return {
                "status": "failed" if changed else "stale",
                "job_id": job_id,
            }

        return retry_voice_job(
            self,
            voice_job_id,
            lease_token,
            chat_id,
            exc,
        )

    except (
        APIConnectionError,
        APITimeoutError,
        httpx.TransportError,
    ) as exc:
        return retry_voice_job(
            self,
            voice_job_id,
            lease_token,
            chat_id,
            exc,
        )

    except Exception:
        logger.exception(
            "Voice processing failed for job %s",
            job_id,
        )

        with SessionLocal() as db:
            changed = get_voice_service(db).fail_processing(
                voice_job_id,
                lease_token,
                "Voice processing failed",
            )

        if changed:
            notify_safely(
                chat_id,
                "Unable to process your voice message.",
            )

        raise

    # 5. Database transaction has committed.
    # Publish the event and notify Telegram.
    publish_task_changed(
        user_id=user_id,
        redis_url=get_settings().redis_url,
    )

    notify_safely(
        chat_id,
        f"Voice task created!\n\n"
        f"Task: {title}\n"
        "Status: Pending",
    )

    return {
        "job_id": job_id,
        "task_id": task_id,
        "status": "completed",
    }


def retry_voice_job(
    celery_task,
    job_id: UUID,
    lease_token: UUID,
    chat_id: int,
    exc: Exception,
):
    if celery_task.request.retries >= celery_task.max_retries:
        with SessionLocal() as db:
            changed = get_voice_service(db).fail_processing(
                job_id,
                lease_token,
                "Maximum transcription retries exceeded",
            )

        if changed:
            notify_safely(
                chat_id,
                "Voice processing failed after retries.",
            )

        raise exc

    with SessionLocal() as db:
        requeued = get_voice_service(db).retry_processing(
            job_id,
            lease_token,
        )

    if not requeued:
        return {
            "status": "stale",
            "job_id": str(job_id),
        }

    delay = min(
        60,
        2 ** (celery_task.request.retries + 2),
    )

    raise celery_task.retry(
        exc=exc,
        countdown=delay,
    )



@celery_app.task(name="workers.recover_voice_jobs")
def recover_voice_jobs() -> dict:
    with SessionLocal() as db:
        service = get_voice_service(db)

        failed_count = service.fail_exhausted_jobs()
        recoverable_ids = service.find_recoverable_jobs(
            limit=100
        )

    scheduled = 0

    for job_id in recoverable_ids:
        try:
            transcribe_voice.apply_async(
                kwargs={"job_id": str(job_id)}
            )
            scheduled += 1
        except Exception:
            logger.exception(
                "Could not reschedule voice job %s",
                job_id,
            )

    return {
        "failed_exhausted": failed_count,
        "scheduled": scheduled,
    }
