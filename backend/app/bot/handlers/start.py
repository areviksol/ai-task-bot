
import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.db.session import SessionLocal
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService


router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def start_handler(message: Message):
    telegram_user = message.from_user

    if telegram_user is None:
        return

    try:
        with SessionLocal() as session:
            repository = UserRepository(session)
            service = UserService(repository)

            user = service.register_telegram_user(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
            )

        logger.info(
            "Telegram user registered: %s",
            user.id,
        )

        await message.answer(
            "Welcome to AI Task Bot!\n\n"
            "Your account is ready.\n"
            "Soon you'll be able to create tasks "
            "using text or voice messages."
        )

    except Exception:
        logger.exception("Failed to register Telegram user")

        await message.answer(
            "Unable to register your account right now. "
            "Please try again later."
        )
