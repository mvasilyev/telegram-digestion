import logging

from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import (
    Channel,
    Chat,
    DialogFilter,
    User,
)

log = logging.getLogger(__name__)


def _str(value) -> str:
    """Extract plain text from a value that might be TextWithEntities."""
    if hasattr(value, "text"):
        return value.text
    return str(value)


async def resolve_folder_peers(client: TelegramClient, folder_id: int) -> list:
    """Resolve a folder (dialog filter) to its list of chat entities."""
    result = await client(GetDialogFiltersRequest())
    filters = result.filters if hasattr(result, "filters") else result
    log.debug("Got %d dialog filters, looking for folder_id=%d", len(filters), folder_id)
    for f in filters:
        log.debug("  filter: type=%s id=%s title=%s", type(f).__name__, getattr(f, "id", "?"), getattr(f, "title", "?"))
        if isinstance(f, DialogFilter) and f.id == folder_id:
            entities = []
            for peer in f.include_peers:
                try:
                    entity = await client.get_entity(peer)
                    entities.append(entity)
                except Exception:
                    log.warning("Could not resolve peer %s in folder %d", peer, folder_id)
            log.info("Folder %d resolved to %d entities", folder_id, len(entities))
            return entities
    log.warning("Folder %d not found among filters", folder_id)
    return []


async def get_forum_topics(client: TelegramClient, chat_id: int) -> list[dict]:
    """Get forum topics for a supergroup that has topics enabled."""
    try:
        from telethon.tl.functions.channels import GetForumTopicsRequest

        result = await client(GetForumTopicsRequest(
            channel=chat_id,
            offset_date=0,
            offset_id=0,
            offset_topic=0,
            limit=100,
            q="",
        ))
        return [
            {"id": t.id, "title": _str(t.title)}
            for t in result.topics
        ]
    except Exception:
        log.debug("Could not fetch forum topics for %d", chat_id)
        return []


async def search_dialogs(client: TelegramClient, query: str) -> list[dict]:
    """Search user's dialogs by name. Returns dicts with id, title, type."""
    results = []
    async for dialog in client.iter_dialogs():
        if query.lower() in dialog.title.lower():
            entity = dialog.entity
            if isinstance(entity, Channel):
                dtype = "channel" if entity.broadcast else "group"
            elif isinstance(entity, (Chat, User)):
                dtype = "chat"
            else:
                continue
            results.append({
                "id": dialog.entity.id,
                "title": dialog.title,
                "type": dtype,
                "is_forum": getattr(entity, "forum", False),
            })
            if len(results) >= 10:
                break
    return results


async def list_folders(client: TelegramClient) -> list[dict]:
    """List all dialog folders."""
    result = await client(GetDialogFiltersRequest())
    filters = result.filters if hasattr(result, "filters") else result
    folders = []
    for f in filters:
        if isinstance(f, DialogFilter):
            folders.append({"id": f.id, "title": _str(f.title)})
    return folders
