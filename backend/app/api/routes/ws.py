
import asyncio
import logging

from fastapi import APIRouter, WebSocket
from redis.asyncio import Redis

from app.api.routes.auth import COOKIE_NAME
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthService
from app.services.task_events import task_channel


router = APIRouter(tags=["WebSockets"])
logger = logging.getLogger(__name__)


def authenticate_session(token: str):
    with SessionLocal() as db:
        return AuthService(
            AuthRepository(db)
        ).get_authenticated_user(token)


@router.websocket("/ws/tasks")
async def task_events_socket(websocket: WebSocket):
    settings = get_settings()

    # Browsers send an Origin header on WebSocket requests.
    if (
        websocket.headers.get("origin")
        != settings.frontend_url.rstrip("/")
    ):
        await websocket.close(code=1008)
        return

    token = websocket.cookies.get(COOKIE_NAME)

    if not token:
        await websocket.close(code=1008)
        return

    user_id = await asyncio.to_thread(
        authenticate_session,
        token,
    )

    if user_id is None:
        await websocket.close(code=1008)
        return

    redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )

    try:
        async with redis.pubsub() as pubsub:
            await pubsub.subscribe(task_channel(user_id))
            await websocket.accept()
            await websocket.send_json({
                "type": "connected",
            })

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )

                if message is not None:
                    await websocket.send_text(message["data"])

                # Periodically revalidate the session so
                # logout/revocation closes this connection.
                current_user_id = await asyncio.to_thread(
                    authenticate_session,
                    token,
                )
                if current_user_id != user_id:
                    await websocket.close(code=1008)
                    return

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Task WebSocket disconnected")
    finally:
        await redis.aclose()
