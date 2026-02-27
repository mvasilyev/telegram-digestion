from app.db.engine import get_db
from app.db.models import Digest, DigestConfig, Message, Source


def _source(row) -> Source:
    return Source(
        id=row["id"],
        telegram_id=row["telegram_id"],
        source_type=row["source_type"],
        title=row["title"],
        topic_id=row["topic_id"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
    )


def _config(row) -> DigestConfig:
    return DigestConfig(
        id=row["id"],
        source_id=row["source_id"],
        cron_expression=row["cron_expression"],
        timezone=row["timezone"],
        max_messages=row["max_messages"],
        prompt_template=row["prompt_template"],
        focus_on=row["focus_on"],
        include_filter=row["include_filter"],
        exclude_filter=row["exclude_filter"],
    )


def _message(row) -> Message:
    return Message(
        id=row["id"],
        source_id=row["source_id"],
        telegram_msg_id=row["telegram_msg_id"],
        content=row["content"],
        sender_name=row["sender_name"],
        sent_at=row["sent_at"],
        topic_id=row["topic_id"],
        is_digested=bool(row["is_digested"]),
        created_at=row["created_at"],
        chat_id=row["chat_id"],
    )


def _digest(row) -> Digest:
    return Digest(
        id=row["id"],
        source_id=row["source_id"],
        content=row["content"],
        model_used=row["model_used"],
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        created_at=row["created_at"],
        sent_at=row["sent_at"],
    )


# ── Sources ──────────────────────────────────────────────

async def add_source(telegram_id: int, source_type: str, title: str,
                     topic_id: int | None = None) -> Source:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO sources (telegram_id, source_type, title, topic_id) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(telegram_id, topic_id) DO UPDATE SET is_active=1, title=? "
        "RETURNING *",
        (telegram_id, source_type, title, topic_id, title),
    )
    row = await cursor.fetchone()
    await db.commit()
    return _source(row)


async def remove_source(source_id: int) -> None:
    db = await get_db()
    await db.execute("UPDATE sources SET is_active=0 WHERE id=?", (source_id,))
    await db.commit()


async def get_active_sources() -> list[Source]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM sources WHERE is_active=1 ORDER BY title"
    )
    return [_source(r) for r in await cursor.fetchall()]


async def get_source(source_id: int) -> Source | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM sources WHERE id=?", (source_id,))
    row = await cursor.fetchone()
    return _source(row) if row else None


# ── Digest Configs ───────────────────────────────────────

async def upsert_digest_config(source_id: int, **kwargs) -> DigestConfig:
    db = await get_db()
    # Ensure row exists
    await db.execute(
        "INSERT INTO digest_configs (source_id) VALUES (?) ON CONFLICT(source_id) DO NOTHING",
        (source_id,),
    )
    if kwargs:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        await db.execute(
            f"UPDATE digest_configs SET {sets} WHERE source_id=?",  # noqa: S608
            (*kwargs.values(), source_id),
        )
    await db.commit()
    cursor = await db.execute(
        "SELECT * FROM digest_configs WHERE source_id=?", (source_id,)
    )
    return _config(await cursor.fetchone())


async def get_digest_config(source_id: int) -> DigestConfig | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM digest_configs WHERE source_id=?", (source_id,)
    )
    row = await cursor.fetchone()
    return _config(row) if row else None


async def get_all_digest_configs() -> list[DigestConfig]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT dc.* FROM digest_configs dc "
        "JOIN sources s ON s.id = dc.source_id WHERE s.is_active=1"
    )
    return [_config(r) for r in await cursor.fetchall()]


# ── Messages ─────────────────────────────────────────────

async def insert_message(source_id: int, telegram_msg_id: int,
                         content: str | None, sender_name: str | None,
                         sent_at: str | None, topic_id: int | None = None,
                         chat_id: int | None = None) -> bool:
    """Insert message, return True if new (not duplicate)."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT OR IGNORE INTO messages "
        "(source_id, telegram_msg_id, content, sender_name, sent_at, topic_id, chat_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (source_id, telegram_msg_id, content, sender_name, sent_at, topic_id, chat_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_undigested_messages(source_id: int, limit: int = 500) -> list[Message]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM messages WHERE source_id=? AND is_digested=0 "
        "ORDER BY sent_at ASC LIMIT ?",
        (source_id, limit),
    )
    return [_message(r) for r in await cursor.fetchall()]


async def get_pending_count(source_id: int) -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE source_id=? AND is_digested=0",
        (source_id,),
    )
    row = await cursor.fetchone()
    return row["cnt"]


async def mark_digested(message_ids: list[int]) -> None:
    if not message_ids:
        return
    db = await get_db()
    placeholders = ",".join("?" for _ in message_ids)
    await db.execute(
        f"UPDATE messages SET is_digested=1 WHERE id IN ({placeholders})",  # noqa: S608
        message_ids,
    )
    await db.commit()


async def get_max_msg_id(source_id: int) -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COALESCE(MAX(telegram_msg_id), 0) as max_id FROM messages WHERE source_id=?",
        (source_id,),
    )
    row = await cursor.fetchone()
    return row["max_id"]


# ── Digests ──────────────────────────────────────────────

async def save_digest(source_id: int, content: str, model_used: str | None = None,
                      prompt_tokens: int | None = None,
                      completion_tokens: int | None = None) -> Digest:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO digests (source_id, content, model_used, prompt_tokens, completion_tokens) "
        "VALUES (?, ?, ?, ?, ?) RETURNING *",
        (source_id, content, model_used, prompt_tokens, completion_tokens),
    )
    row = await cursor.fetchone()
    await db.commit()
    return _digest(row)


async def mark_digest_sent(digest_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE digests SET sent_at=datetime('now') WHERE id=?", (digest_id,)
    )
    await db.commit()


async def get_recent_digests(source_id: int, limit: int = 5) -> list[Digest]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM digests WHERE source_id=? ORDER BY created_at DESC LIMIT ?",
        (source_id, limit),
    )
    return [_digest(r) for r in await cursor.fetchall()]


# ── Settings ─────────────────────────────────────────────

async def get_setting(key: str) -> str | None:
    db = await get_db()
    cursor = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else None


async def set_setting(key: str, value: str) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=?",
        (key, value, value),
    )
    await db.commit()
