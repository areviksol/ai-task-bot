
import asyncio
import logging

from aiogram import Bot

from app.bot.dispatcher import create_dispatcher
from app.core.config import get_settings


async def main():
    settings = get_settings()

    token = settings.telegram_bot_token.get_secret_value()

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    bot = Bot(token=token)
    dispatcher = create_dispatcher()

    async with bot:
        await dispatcher.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
