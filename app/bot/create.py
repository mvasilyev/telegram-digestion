from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import digest, schedule, settings, sources, start
from app.bot.middlewares import OwnerMiddleware
from app.config import settings as app_settings


def create_bot() -> Bot:
    return Bot(
        token=app_settings.tg_bot_token,
        default=DefaultBotProperties(),
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(OwnerMiddleware())
    dp.callback_query.middleware(OwnerMiddleware())

    dp.include_routers(
        start.router,
        sources.router,
        schedule.router,
        digest.router,
        settings.router,
    )
    return dp
