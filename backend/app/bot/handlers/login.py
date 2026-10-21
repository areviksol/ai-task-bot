
import asyncio
import logging
from urllib.parse import urlencode

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.auth_repository import AuthRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService


router = Router()
logger = logging.getLogger(__name__)


def generate_login_link(telegram_id: int) -> str:
    with SessionLocal() as db:
        user = UserRepository(db).get_by_telegram_id(
            telegram_id
        )

        if user is None:
            raise ValueError("Telegram user is not registered")

        token = AuthService(
            AuthRepository(db)
        ).create_login_token(user.id)

    base_url = get_settings().frontend_url.rstrip("/")

    return f"{base_url}/login#{urlencode({'token': token})}"

@router.message(Command("login"))
async def login_handler(message: Message):
    if message.from_user is None:
        return

    if message.chat.type != "private":
        await message.answer(
            "For security, request a login link "
            "in a private chat with the bot."
        )
        return

    try:
        link = await asyncio.to_thread(
            generate_login_link,
            message.from_user.id,
        )

        await message.answer(
            "Your dashboard login link:\n"
            f"{link}\n\n"
            "This link expires in 5 minutes "
            "and can only be used once.",
            disable_web_page_preview=True,
        )

    except ValueError:
        await message.answer(
            "Please send /start first."
        )

    except Exception:
        logger.exception("Failed to generate login link")
        await message.answer(
            "Unable to generate a login link right now."
        )
