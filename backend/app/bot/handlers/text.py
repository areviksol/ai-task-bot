
import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message

from app.db.session import SessionLocal
from app.models.task import TaskSource
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.task import TaskCreate
from app.services.task_service import TaskService


router = Router()
logger = logging.getLogger(__name__)


def create_task_from_message(
    telegram_id: int,
    chat_id: int,
    message_id: int,
    text: str,
) -> tuple[str, bool]:
    """Run synchronous database operations outside the event loop."""
    with SessionLocal() as session:
        user_repo = UserRepository(session)
        user = user_repo.get_by_telegram_id(telegram_id)

        if user is None:
            raise ValueError(
                "User is not registered. Send /start first."
            )

        task_repo = TaskRepository(session)
        task_service = TaskService(task_repo)


        task, created = task_service.create_telegram_task(
            user_id=user.id,
            data=TaskCreate(title=text),
            source=TaskSource.TELEGRAM_TEXT,
            chat_id=chat_id,
            message_id=message_id,
        )

        return str(task.id), created


@router.message(F.text & ~F.text.startswith("/"))
async def text_handler(message: Message):
    if message.from_user is None or message.text is None:
        return

    text = message.text.strip()

    if not text:
        await message.answer("Task cannot be empty.")
        return

    if len(text) > 255:
        await message.answer(
            "Task title is too long. Maximum 255 characters."
        )
        return

    try:
        task_id, created = await asyncio.to_thread(
            create_task_from_message,
            message.from_user.id,
            message.chat.id,
            message.message_id,
            text,
        )

        if created:
            await message.answer(
                f"Task created!\n\n"
                f"Title: {text}\n"
                f"Status: Pending\n"
                f"ID: {task_id}"
            )
        else:
            await message.answer(
                f"ℹ️ This task already exists.\n"
                f"Task ID: {task_id}"
            )


    except ValueError:
        await message.answer(
            "Please send /start before creating tasks."
        )

    except Exception:
        logger.exception("Failed to create Telegram task")
        await message.answer(
            "Unable to create your task. Please try again."
        )
