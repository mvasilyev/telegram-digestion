from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    search_results_keyboard,
    sources_keyboard,
    topics_keyboard,
)
from app.bot.states import AddSource, SetFocus
from app.db import repository as repo
from app.scheduler.manager import refresh_schedules
from app.userbot.client import get_userbot
from app.userbot.resolver import get_forum_topics, list_folders, search_dialogs

router = Router()


@router.message(F.text == "Добавить")
@router.message(Command("add_source"))
async def cmd_add_source(message: Message, state: FSMContext) -> None:
    text = (message.text or "").replace("/add_source", "").strip()
    if text:
        await _do_search(message, state, text)
    else:
        await state.set_state(AddSource.waiting_query)
        await message.answer(
            "Enter search query (channel/chat name) or 'folders' to list folders:"
        )


@router.message(AddSource.waiting_query)
async def on_search_query(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if not query:
        return
    await _do_search(message, state, query)


async def _do_search(message: Message, state: FSMContext, query: str) -> None:
    client = get_userbot()

    if query.lower() == "folders":
        folders = await list_folders(client)
        if not folders:
            await message.answer("No folders found.")
            await state.clear()
            return
        results = [{"id": f["id"], "title": f["title"], "type": "folder", "is_forum": False}
                   for f in folders]
    else:
        results = await search_dialogs(client, query)

    if not results:
        await message.answer("Nothing found. Try another query.")
        await state.clear()
        return

    await state.set_state(AddSource.waiting_selection)
    await state.update_data(results=results)
    await message.answer(
        "Select a source to add:",
        reply_markup=search_results_keyboard(results),
    )


@router.callback_query(F.data == "cancel")
async def on_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Cancelled.")
    await callback.answer()


@router.callback_query(F.data.startswith("add:"))
async def on_select_source(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    chat_id = int(parts[1])
    source_type = parts[2]
    is_forum = bool(int(parts[3]))

    data = await state.get_data()
    results = data.get("results", [])
    title = next((r["title"] for r in results if r["id"] == chat_id), f"Chat {chat_id}")

    if is_forum:
        client = get_userbot()
        topics = await get_forum_topics(client, chat_id)
        if topics:
            await state.set_state(AddSource.waiting_topic_selection)
            await state.update_data(chat_id=chat_id, title=title, source_type=source_type)
            await callback.message.edit_text(
                f"'{title}' is a forum. Select topics:",
                reply_markup=topics_keyboard(topics, chat_id),
            )
            await callback.answer()
            return

    source = await repo.add_source(chat_id, source_type, title)
    await repo.upsert_digest_config(source.id)
    await refresh_schedules()
    await state.clear()
    await callback.message.edit_text(f"Added: {title}")
    await callback.answer()


@router.callback_query(F.data.startswith("topic:"))
async def on_select_topic(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    chat_id = int(parts[1])
    topic_raw = parts[2]

    data = await state.get_data()
    title = data.get("title", f"Chat {chat_id}")
    source_type = data.get("source_type", "group")

    if topic_raw == "all":
        source = await repo.add_source(chat_id, source_type, title)
    else:
        topic_id = int(topic_raw)
        source = await repo.add_source(chat_id, "topic", f"{title}/{topic_id}", topic_id=topic_id)

    await repo.upsert_digest_config(source.id)
    await refresh_schedules()
    await state.clear()
    await callback.message.edit_text(f"Added: {source.title}")
    await callback.answer()


@router.message(Command("remove_source"))
async def cmd_remove_source(message: Message) -> None:
    sources = await repo.get_active_sources()
    if not sources:
        await message.answer("No active sources.")
        return
    await message.answer(
        "Select source to remove:",
        reply_markup=sources_keyboard(sources, "rm"),
    )


@router.callback_query(F.data.startswith("rm:"))
async def on_remove_source(callback: CallbackQuery) -> None:
    source_id = int(callback.data.split(":")[1])
    source = await repo.get_source(source_id)
    await repo.remove_source(source_id)
    await refresh_schedules()
    title = source.title if source else f"#{source_id}"
    await callback.message.edit_text(f"Removed: {title}")
    await callback.answer()


@router.message(F.text == "Источники")
@router.message(Command("list_sources"))
async def cmd_list_sources(message: Message) -> None:
    sources = await repo.get_active_sources()
    if not sources:
        await message.answer("No active sources.")
        return

    lines = []
    for s in sources:
        config = await repo.get_digest_config(s.id)
        pending = await repo.get_pending_count(s.id)
        cron = config.cron_expression if config else "not set"
        line = f"  {s.title} [{s.source_type}] — cron: {cron}, pending: {pending}"
        if config and config.focus_on:
            line += f"\n    focus: {config.focus_on}"
        if config and config.exclude_filter:
            line += f"\n    exclude: {config.exclude_filter}"
        lines.append(line)

    await message.answer("Sources:\n" + "\n".join(lines))


# ── Set Focus ────────────────────────────────────────────

@router.message(F.text == "Фильтры")
@router.message(Command("set_focus"))
async def cmd_set_focus(message: Message, state: FSMContext) -> None:
    sources = await repo.get_active_sources()
    if not sources:
        await message.answer("No active sources.")
        return
    await state.set_state(SetFocus.waiting_source)
    await message.answer(
        "Select source to configure focus/filters:",
        reply_markup=sources_keyboard(sources, "focus"),
    )


@router.callback_query(F.data.startswith("focus:"), SetFocus.waiting_source)
async def on_focus_source(callback: CallbackQuery, state: FSMContext) -> None:
    source_id = int(callback.data.split(":")[1])
    await state.update_data(source_id=source_id)
    await state.set_state(SetFocus.waiting_focus_on)
    await callback.message.edit_text(
        "What should the digest focus on?\n"
        "(e.g. 'AI news, model releases')\n\n"
        "Send '-' to skip."
    )
    await callback.answer()


@router.message(SetFocus.waiting_focus_on)
async def on_focus_on(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    focus = text if text != "-" else None
    await state.update_data(focus_on=focus)
    await state.set_state(SetFocus.waiting_include)
    await message.answer(
        "What to always include?\n"
        "(e.g. 'Python mentions, new libraries')\n\n"
        "Send '-' to skip."
    )


@router.message(SetFocus.waiting_include)
async def on_include(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    include = text if text != "-" else None
    await state.update_data(include_filter=include)
    await state.set_state(SetFocus.waiting_exclude)
    await message.answer(
        "What to exclude/ignore?\n"
        "(comma-separated keywords or author names)\n\n"
        "Send '-' to skip."
    )


@router.message(SetFocus.waiting_exclude)
async def on_exclude(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    exclude = text if text != "-" else None
    data = await state.get_data()

    await repo.upsert_digest_config(
        data["source_id"],
        focus_on=data.get("focus_on"),
        include_filter=data.get("include_filter"),
        exclude_filter=exclude,
    )
    await state.clear()
    await message.answer("Focus/filters updated.")
