from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import settings_keyboard
from app.bot.states import EditSettings
from app.config import settings as app_settings
from app.db import repository as repo

router = Router()

_DEFAULTS = {
    "llm_base_url": lambda: app_settings.llm_base_url,
    "llm_model": lambda: app_settings.llm_model,
    "llm_api_key": lambda: "***" if app_settings.llm_api_key else "(not set)",
}


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    lines = ["Current LLM settings:"]
    for key, default_fn in _DEFAULTS.items():
        val = await repo.get_setting(key)
        if val is None:
            val = default_fn()
        if key == "llm_api_key" and val and val != "(not set)":
            val = val[:4] + "***"
        lines.append(f"  {key}: {val}")

    await message.answer(
        "\n".join(lines),
        reply_markup=settings_keyboard(),
    )


@router.callback_query(F.data.startswith("setting:"))
async def on_setting_select(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":", 1)[1]
    await state.set_state(EditSettings.waiting_value)
    await state.update_data(setting_key=key)
    await callback.message.edit_text(f"Enter new value for {key}:")
    await callback.answer()


@router.message(EditSettings.waiting_value)
async def on_setting_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    key = data["setting_key"]
    value = (message.text or "").strip()

    if not value:
        await message.answer("Value cannot be empty.")
        return

    await repo.set_setting(key, value)
    await state.clear()

    display = value[:4] + "***" if key == "llm_api_key" else value
    await message.answer(f"Updated {key} = {display}")
