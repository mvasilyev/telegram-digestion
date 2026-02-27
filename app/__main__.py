import asyncio
import logging
import os

from app.config import settings


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("app")

    # Ensure data directory exists
    os.makedirs(os.path.dirname(settings.db_path) or "data", exist_ok=True)

    asyncio.run(_run(log))


async def _run(log: logging.Logger) -> None:
    # 1. Database
    from app.db.migrations import run_migrations
    await run_migrations()
    log.info("Database ready")

    # 2. Userbot
    from app.userbot.client import get_userbot
    userbot = get_userbot()
    await userbot.start()
    log.info("Userbot connected (as %s)", (await userbot.get_me()).first_name)

    # 3. Scheduler
    from app.scheduler.manager import setup_scheduler
    sched = await setup_scheduler()

    # 4. Bot
    from app.bot.create import create_bot, create_dispatcher
    bot = create_bot()
    dp = create_dispatcher()

    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="digest_now", description="Сгенерировать дайджест"),
        BotCommand(command="list_sources", description="Список источников"),
        BotCommand(command="add_source", description="Добавить источник"),
        BotCommand(command="remove_source", description="Удалить источник"),
        BotCommand(command="set_schedule", description="Настроить расписание"),
        BotCommand(command="set_focus", description="Фильтры и фокус"),
        BotCommand(command="history", description="История дайджестов"),
        BotCommand(command="settings", description="Настройки LLM"),
        BotCommand(command="status", description="Статус системы"),
    ])
    log.info("Bot starting polling...")

    # Run bot (scheduler already started in setup_scheduler)
    try:
        await dp.start_polling(bot)
    finally:
        sched.shutdown(wait=False)
        await userbot.disconnect()
        from app.db.engine import close_db
        await close_db()
        log.info("Shutdown complete")


if __name__ == "__main__":
    main()
