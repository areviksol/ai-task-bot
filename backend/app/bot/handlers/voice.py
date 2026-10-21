
import asyncio
import logging
from uuid import UUID

from aiogram import F, Router
from aiogram.types import Message

from app.db.session import SessionLocal
from app.models.voice_job import VoiceJobStatus
from app.repositories.user_repository import UserRepository
from app.repositories.voice_job_repository import (
    VoiceJobRepository,
)
from app.services.voice_job_service import VoiceJobService
from app.workers.tasks import transcribe_voice


router = Router()
logger = logging.getLogger(__name__)

MAX_VOICE_BYTES = 20 * 1024 * 1024
MAX_VOICE_DURATION = 300


def register_voice_job(
    telegram_id: int,
    chat_id: int,
    message_id: int,
    file_id: str,
) -> tuple[UUID, bool, VoiceJobStatus]:
    with SessionLocal() as db:
        user = UserRepository(db).get_by_telegram_id(
            telegram_id
        )

        if user is None:
            raise ValueError("User is not registered")

        service = VoiceJobService(
            VoiceJobRepository(db)
        )

        job, created = service.register_voice(
            user_id=user.id,
            chat_id=chat_id,
            message_id=message_id,
            file_id=file_id,
        )

        return job.id, created, job.status


@router.message(F.voice)
async def voice_handler(message: Message):
    voice = message.voice

    if voice is None or message.from_user is None:
        return

    if (
        voice.file_size is not None
        and voice.file_size > MAX_VOICE_BYTES
    ):
        await message.answer("Voice message exceeds 20 MB.")
        return

    if voice.duration > MAX_VOICE_DURATION:
        await message.answer(
            "Voice message exceeds 5 minutes."
        )
        return

    try:
        job_id, created, job_status = await asyncio.to_thread(
            register_voice_job,
            message.from_user.id,
            message.chat.id,
            message.message_id,
            voice.file_id,
        )

        if not created:
            await message.answer(
                f"This recording is already registered.\n"
                f"Status: {job_status.value}"
            )
            return

        await asyncio.to_thread(
            transcribe_voice.apply_async,
            kwargs={"job_id": str(job_id)},
        )

        await message.answer(
            "🎙 Voice received. "
            "Your transcription is queued."
        )

    except ValueError:
        await message.answer(
            "Please send /start before using voice tasks."
        )

    except Exception:
        logger.exception("Failed to enqueue voice job")

        await message.answer(
            "Unable to queue your recording. "
            "Please try again later."
        )
