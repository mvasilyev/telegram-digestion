from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import schedule_presets_keyboard, sources_keyboard
from app.bot.states import SetSchedule
from app.db import repository as repo
from app.scheduler.manager import refresh_schedules

router = Router()


@router.message(F.text == "Расписание")
@router.message(Command("set_schedule"))
async def cmd_set_schedule(message: Message, state: FSMContext) -> None:
    sources = await repo.get_active_sources()
    if not sources:
        await message.answer("No active sources.")
        return
    await state.set_state(SetSchedule.waiting_source)
    await message.answer(
        "Select source to set schedule:",
        reply_markup=sources_keyboard(sources, "sched"),
    )


@router.callback_query(F.data.startswith("sched:"), SetSchedule.waiting_source)
async def on_schedule_source(callback: CallbackQuery, state: FSMContext) -> None:
    source_id = int(callback.data.split(":")[1])
    await state.update_data(source_id=source_id)
    await state.set_state(SetSchedule.waiting_cron)
    await callback.message.edit_text(
        "Choose a schedule preset or send a custom cron expression:",
        reply_markup=schedule_presets_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cron:"), SetSchedule.waiting_cron)
async def on_cron_preset(callback: CallbackQuery, state: FSMContext) -> None:
    cron = callback.data.split(":", 1)[1]
    if cron == "custom":
        await callback.message.edit_text(
            "Send a cron expression (5 fields: min hour day month weekday):"
        )
        await callback.answer()
        return

    data = await state.get_data()
    await repo.upsert_digest_config(data["source_id"], cron_expression=cron)
    await refresh_schedules()
    await state.clear()
    await callback.message.edit_text(f"Schedule set: {cron}")
    await callback.answer()


@router.message(SetSchedule.waiting_cron)
async def on_custom_cron(message: Message, state: FSMContext) -> None:
    cron = (message.text or "").strip()
    parts = cron.split()
    if len(parts) != 5:
        await message.answer("Invalid cron. Need 5 fields: min hour day month weekday")
        return

    data = await state.get_data()
    await repo.upsert_digest_config(data["source_id"], cron_expression=cron)
    await refresh_schedules()
    await state.clear()
    await message.answer(f"Schedule set: {cron}")
