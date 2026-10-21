

from aiogram import Dispatcher

from app.bot.handlers.start import router as start_router
from app.bot.handlers.login import router as login_router
from app.bot.handlers.voice import router as voice_router
from app.bot.handlers.text import router as text_router


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()

    dispatcher.include_router(start_router)
    dispatcher.include_router(login_router)
    dispatcher.include_router(voice_router)
    dispatcher.include_router(text_router)

    return dispatcher
