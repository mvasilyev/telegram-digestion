import asyncio
import logging

from telethon import TelegramClient

from app.db import repository as repo
from app.db.models import Source
from app.userbot.resolver import resolve_folder_peers

log = logging.getLogger(__name__)


async def collect_source(client: TelegramClient, source: Source) -> int:
    """Collect new messages for a source. Returns count of new messages."""
    log.info("Collecting from '%s' [%s] telegram_id=%d", source.title, source.source_type, source.telegram_id)
    count = 0

    if source.source_type == "folder":
        peers = await resolve_folder_peers(client, source.telegram_id)
        log.info("Folder '%s' resolved to %d peers", source.title, len(peers))
        for peer in peers:
            peer_title = getattr(peer, "title", None) or getattr(peer, "first_name", str(peer.id))
            n = await _fetch_new(client, source, peer.id)
            log.info("  peer '%s' (%d): %d new messages", peer_title, peer.id, n)
            count += n
            await asyncio.sleep(1)
    else:
        count = await _fetch_new(
            client, source, source.telegram_id,
            topic_id=source.topic_id,
        )

    log.info("Collected %d new messages from '%s'", count, source.title)
    return count


async def _fetch_new(
    client: TelegramClient,
    source: Source,
    chat_id: int,
    topic_id: int | None = None,
) -> int:
    """Fetch messages newer than the last collected one."""
    count = 0
    try:
        min_id = await repo.get_max_msg_id(source.id, chat_id)

        # First collection: start from first unread message, not from the beginning
        if min_id == 0:
            try:
                dialog = await client.get_entity(chat_id)
                full = await client(
                    __import__("telethon.tl.functions.messages", fromlist=["GetPeerDialogsRequest"])
                    .GetPeerDialogsRequest(peers=[dialog])
                )
                if full.dialogs:
                    min_id = full.dialogs[0].read_inbox_max_id
                    log.info("First collection for chat %d: starting from read_inbox_max_id=%d", chat_id, min_id)
            except Exception:
                log.warning("Could not get read position for chat %d, collecting from start", chat_id)

        kwargs: dict = {"min_id": min_id}
        if topic_id:
            kwargs["reply_to"] = topic_id

        async for msg in client.iter_messages(chat_id, **kwargs):
            msg_topic_id = topic_id
            if not topic_id and hasattr(msg, "reply_to") and msg.reply_to:
                msg_topic_id = getattr(msg.reply_to, "forum_topic", None)
                if msg_topic_id is None:
                    msg_topic_id = getattr(msg.reply_to, "reply_to_top_id", None)

            text = msg.text or ""
            if not text and msg.media:
                text = f"[media: {type(msg.media).__name__}]"
            if not text:
                continue

            sender_name = None
            if msg.sender:
                sender_name = getattr(msg.sender, "title", None) or _user_name(msg.sender)

            sent_at = msg.date.isoformat() if msg.date else None

            inserted = await repo.insert_message(
                source_id=source.id,
                telegram_msg_id=msg.id,
                content=text,
                sender_name=sender_name,
                sent_at=sent_at,
                topic_id=msg_topic_id,
                chat_id=chat_id,
            )
            if inserted:
                count += 1
    except Exception:
        log.exception("Error fetching messages from chat %d for source '%s'", chat_id, source.title)
    return count


def _user_name(sender) -> str:
    first = getattr(sender, "first_name", "") or ""
    last = getattr(sender, "last_name", "") or ""
    return f"{first} {last}".strip() or "Unknown"


async def collect_all(client: TelegramClient) -> dict[str, int]:
    """Collect messages from all active sources. Returns {source_title: count}."""
    sources = await repo.get_active_sources()
    results = {}
    for source in sources:
        try:
            count = await collect_source(client, source)
            results[source.title] = count
        except Exception:
            log.exception("Failed to collect from %s", source.title)
        await asyncio.sleep(1)
    return results
