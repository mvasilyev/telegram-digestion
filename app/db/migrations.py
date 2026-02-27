from app.db.engine import get_db

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     INTEGER NOT NULL,
    source_type     TEXT NOT NULL CHECK(source_type IN ('folder','channel','group','chat','topic')),
    title           TEXT NOT NULL,
    topic_id        INTEGER,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(telegram_id, topic_id)
);

CREATE TABLE IF NOT EXISTS digest_configs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id        INTEGER NOT NULL UNIQUE REFERENCES sources(id),
    cron_expression  TEXT NOT NULL DEFAULT '0 9 * * *',
    timezone         TEXT NOT NULL DEFAULT 'Europe/Moscow',
    max_messages     INTEGER NOT NULL DEFAULT 500,
    prompt_template  TEXT,
    focus_on         TEXT,
    include_filter   TEXT,
    exclude_filter   TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER NOT NULL REFERENCES sources(id),
    telegram_msg_id INTEGER NOT NULL,
    content         TEXT,
    sender_name     TEXT,
    sent_at         TEXT,
    topic_id        INTEGER,
    is_digested     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_id, telegram_msg_id)
);

CREATE TABLE IF NOT EXISTS digests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     INTEGER NOT NULL REFERENCES sources(id),
    content       TEXT NOT NULL,
    model_used    TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    sent_at       TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


MIGRATIONS = [
    "ALTER TABLE messages ADD COLUMN chat_id INTEGER",
]


async def run_migrations() -> None:
    db = await get_db()
    await db.executescript(SCHEMA)
    for sql in MIGRATIONS:
        try:
            await db.execute(sql)
        except Exception:
            pass  # column already exists
    await db.commit()
