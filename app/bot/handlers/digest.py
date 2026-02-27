import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.formatting import split_message
from app.bot.keyboards import sources_keyboard
from app.db import repository as repo
from app.digest.generator import generate_digest
from app.userbot.client import get_userbot
from app.userbot.collector import collect_source

log = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "Дайджест")
@router.message(Command("digest_now"))
async def cmd_digest_now(message: Message) -> None:
    sources = await repo.get_active_sources()
    if not sources:
        await message.answer("No active sources.")
        return
    await message.answer(
        "Select source for immediate digest:",
        reply_markup=sources_keyboard(sources, "dnow"),
    )


@router.callback_query(F.data.startswith("dnow:"))
async def on_digest_now(callback: CallbackQuery) -> None:
    source_id = int(callback.data.split(":")[1])
    source = await repo.get_source(source_id)
    if not source:
        await callback.answer("Source not found", show_alert=True)
        return

    await callback.message.edit_text(f"Collecting messages from {source.title}...")
    await callback.answer()

    try:
        client = get_userbot()
        collected = await collect_source(client, source)
        log.info("Collected %d new messages from %s before digest", collected, source.title)

        await callback.message.edit_text(f"Generating digest for {source.title}...")
        content = await generate_digest(source)
        if content is None:
            await callback.message.edit_text(f"No new messages for {source.title}.")
            return

        # Send digest parts
        parts = split_message(content)
        await callback.message.edit_text(parts[0])
        for part in parts[1:]:
            await callback.message.answer(part)

        # Mark as sent
        digests = await repo.get_recent_digests(source_id, limit=1)
        if digests:
            await repo.mark_digest_sent(digests[0].id)

    except Exception:
        log.exception("Digest generation failed for %s", source.title)
        try:
            await callback.message.edit_text(
                f"Digest generation failed for {source.title}. Check logs."
            )
        except Exception:
            log.exception("Also failed to send error message")


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    sources = await repo.get_active_sources()
    if not sources:
        await message.answer("No active sources.")
        return
    await message.answer(
        "Select source to view history:",
        reply_markup=sources_keyboard(sources, "hist"),
    )


@router.callback_query(F.data.startswith("hist:"))
async def on_history(callback: CallbackQuery) -> None:
    source_id = int(callback.data.split(":")[1])
    digests = await repo.get_recent_digests(source_id, limit=5)

    if not digests:
        await callback.message.edit_text("No digests yet.")
        await callback.answer()
        return

    lines = []
    for d in digests:
        sent = "sent" if d.sent_at else "not sent"
        preview = (d.content[:100] + "...") if len(d.content) > 100 else d.content
        preview = preview.replace("\n", " ")
        lines.append(f"[{d.created_at}] ({sent}) {preview}")

    await callback.message.edit_text("Recent digests:\n\n" + "\n\n".join(lines))
    await callback.answer()
