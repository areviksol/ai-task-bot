
from celery import Celery

from app.core.config import get_settings


settings = get_settings()

celery_app = Celery(
    "ai_task_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=180,
    task_soft_time_limit=150,
    result_expires=3600,
)


celery_app.conf.beat_schedule = {
    "recover-abandoned-voice-jobs": {
        "task": "workers.recover_voice_jobs",
        "schedule": 60.0,
    },
}