
import json
import logging
from uuid import UUID

from redis import Redis

logger = logging.getLogger(__name__)


def task_channel(user_id: UUID) -> str:
    return f"tasks:user:{user_id}"


def publish_task_changed(
    user_id: UUID,
    redis_url: str,
) -> None:
    payload = json.dumps({
        "type": "tasks.changed",
    })

    try:
        client = Redis.from_url(redis_url)

        try:
            client.publish(
                task_channel(user_id),
                payload,
            )
        finally:
            client.close()

    except Exception:
        # The database operation has already succeeded.
        # Redis should not make the task creation fail.
        logger.exception(
            "Failed to publish task event for user %s",
            user_id,
        )
