from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import main_menu
from app.db import repository as repo
from app.llm.client import check_llm_health
from app.userbot.client import get_userbot

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not message.from_user:
        return

    owner_id = await repo.get_setting("owner_id")
    if owner_id is None:
        await repo.set_setting("owner_id", str(message.from_user.id))
        await repo.set_setting("owner_chat_id", str(message.chat.id))

    await message.answer(
        "Telegram Digestion готов к работе!\n\n"
        "Используй кнопки внизу или команды из меню.",
        reply_markup=main_menu(),
    )


@router.message(F.text == "Статус")
@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    userbot = get_userbot()
    ub_connected = userbot.is_connected() if userbot else False
    sources = await repo.get_active_sources()
    llm_ok = await check_llm_health()

    ok = lambda v: "OK" if v else "FAIL"

    text = (
        f"Статус:\n"
        f"  Userbot: {ok(ub_connected)}\n"
        f"  Источники: {len(sources)}\n"
        f"  LLM: {ok(llm_ok)}"
    )
    await message.answer(text)
