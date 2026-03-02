# Codebase Structure

**Analysis Date:** 2025-03-02

## Directory Layout

```
telegram-digestion/
├── app/                        # Application code
│   ├── __main__.py             # Entry point: orchestrates init and shutdown
│   ├── __init__.py             # Package marker
│   ├── config.py               # Pydantic Settings (env vars)
│   ├── bot/                    # Telegram bot handlers and setup
│   │   ├── __init__.py
│   │   ├── create.py           # Bot and Dispatcher factories
│   │   ├── middlewares.py       # OwnerMiddleware for auth
│   │   ├── states.py           # FSM state definitions
│   │   ├── keyboards.py        # Keyboard builders (inline/reply)
│   │   ├── formatting.py       # Message splitting for 4096 char limit
│   │   └── handlers/           # Command routers
│   │       ├── __init__.py
│   │       ├── start.py        # /start, /status commands
│   │       ├── sources.py      # /add_source, /remove_source, /list_sources
│   │       ├── schedule.py     # /set_schedule (cron config)
│   │       ├── digest.py       # /digest_now (manual trigger)
│   │       └── settings.py     # /settings (LLM config)
│   ├── db/                     # Database layer
│   │   ├── __init__.py
│   │   ├── engine.py           # aiosqlite singleton, connection setup
│   │   ├── migrations.py       # Schema and migration runner
│   │   ├── models.py           # Dataclasses (Source, Message, Digest, etc.)
│   │   └── repository.py       # All SQL queries (organized by entity)
│   ├── userbot/                # Telegram userbot (client API)
│   │   ├── __init__.py
│   │   ├── client.py           # Telethon TelegramClient singleton
│   │   ├── collector.py        # Message fetching from sources
│   │   └── resolver.py         # Folder peer resolution
│   ├── scheduler/              # Job scheduling
│   │   ├── __init__.py
│   │   └── manager.py          # APScheduler setup and job definitions
│   ├── digest/                 # Message summarization pipeline
│   │   ├── __init__.py
│   │   ├── generator.py        # Main digest generation logic
│   │   ├── chunker.py          # Message chunking (token-aware)
│   │   └── prompts.py          # System/user prompt builders
│   └── llm/                    # LLM API client
│       ├── __init__.py
│       └── client.py           # OpenAI-compatible chat_completion
├── data/                       # Runtime data (generated, not in git)
│   ├── app.db                  # SQLite database (WAL mode)
│   └── userbot.session         # Telethon session file
├── docker-compose.yml          # Docker services (bot + ollama)
├── Dockerfile                  # Bot container image
└── pyproject.toml              # Python project config (deps, scripts)
```

## Directory Purposes

**app/:**
- Purpose: All application Python code
- Contains: Config, 7 subsystem packages, entry point
- Key files: `__main__.py` (entry), `config.py` (settings)

**app/bot/:**
- Purpose: Telegram bot frontend and user interaction
- Contains: Command handlers, middlewares, keyboards, FSM states, message formatting
- Key files: `create.py` (setup), `middlewares.py` (auth), `handlers/` (commands)

**app/bot/handlers/:**
- Purpose: Individual command implementations
- Contains: 5 routers (start, sources, schedule, digest, settings)
- Key files:
  - `start.py`: /start (owner enrollment), /status (health check)
  - `sources.py`: /list_sources, /add_source, /remove_source
  - `schedule.py`: /set_schedule (cron editor with FSM)
  - `digest.py`: /digest_now (manual generation + send)
  - `settings.py`: /settings (LLM override dialog)

**app/db/:**
- Purpose: Data persistence and access layer
- Contains: Singleton connection, schema/migrations, data models, all queries
- Key files:
  - `engine.py`: aiosqlite setup (WAL mode, foreign keys)
  - `migrations.py`: 5 tables + 1 migration
  - `models.py`: 4 dataclasses (Source, DigestConfig, Message, Digest)
  - `repository.py`: 30+ query functions

**app/userbot/:**
- Purpose: Telegram userbot (MTProto client for message collection)
- Contains: Telethon client, message fetcher, folder resolver
- Key files:
  - `client.py`: Singleton TelegramClient
  - `collector.py`: Unread-only message fetching
  - `resolver.py`: Folder → peers resolution

**app/scheduler/:**
- Purpose: APScheduler job management (collection + digest scheduling)
- Contains: Single manager module with job definitions
- Key files: `manager.py` (setup, _collect_job, _digest_job, refresh_schedules)

**app/digest/:**
- Purpose: Message → summary pipeline
- Contains: LLM orchestration, token-aware chunking, prompt templates
- Key files:
  - `generator.py`: Main pipeline (fetch → filter → chunk → LLM → save)
  - `chunker.py`: Token budget splitting (12k default)
  - `prompts.py`: System/user prompt builders

**app/llm/:**
- Purpose: LLM API abstraction (OpenAI-compatible)
- Contains: HTTP client wrapper, config getter, health check
- Key files: `client.py` (chat_completion, get_llm_config, check_llm_health)

**data/:**
- Purpose: Runtime data storage
- Contains: SQLite database, Telethon session
- Generated: Yes (on first run)
- Committed: No (ignored in .gitignore)

## Key File Locations

**Entry Points:**
- `app/__main__.py`: Process entry point (logging, data dir, asyncio.run)
- `app/bot/create.py`: Bot and Dispatcher factories
- `app/scheduler/manager.py`: Scheduler setup (digest jobs from DB)

**Configuration:**
- `app/config.py`: Pydantic Settings (TG_API_ID, TG_BOT_TOKEN, LLM_BASE_URL, etc.)
- `app/db/migrations.py`: Database schema definition

**Core Logic:**
- `app/digest/generator.py`: Digest generation pipeline
- `app/userbot/collector.py`: Message fetching from sources
- `app/scheduler/manager.py`: Job scheduling and execution

**Database Access:**
- `app/db/repository.py`: All SQL queries (sources, messages, configs, digests)
- `app/db/engine.py`: Singleton aiosqlite connection

**Bot Handlers:**
- `app/bot/handlers/start.py`: /start, /status
- `app/bot/handlers/sources.py`: Source CRUD
- `app/bot/handlers/schedule.py`: Cron editor
- `app/bot/handlers/digest.py`: Manual generation
- `app/bot/handlers/settings.py`: LLM config override

**Testing:**
- Not found (no test directory)

## Naming Conventions

**Files:**
- Lowercase with underscores: `engine.py`, `chat_completion()`, `_collect_job()`
- Private functions prefixed with `_`: `_get_llm_setting()`, `_parse_cron()`
- Handler modules named for command: `start.py` (handles /start), `sources.py` (handles /add_source, etc.)

**Directories:**
- Lowercase plural for package groups: `handlers/`, `models/` would be plural if separate
- Module prefix for singletons: `client.py` in both userbot/ and llm/

**Functions:**
- Snake_case: `create_bot()`, `get_db()`, `collect_source()`
- Prefixed helpers with underscore: `_collect_job()`, `_fetch_unread()`, `_user_name()`
- Verb-first for actions: `add_source()`, `remove_source()`, `mark_digested()`
- Getter-setter pattern: `get_setting()`, `set_setting()`, `get_digest_config()`, `upsert_digest_config()`

**Classes:**
- PascalCase: `Source`, `Message`, `Digest`, `OwnerMiddleware`
- Dataclasses for models: no suffix (all in models.py)

**Variables:**
- Snake_case: `source_id`, `max_tokens`, `prompt_tokens`
- Prefixed with underscore for module-level singletons: `_db`, `userbot`, `scheduler`

**Constants:**
- UPPERCASE: `SCHEMA` (in migrations.py), `MIGRATIONS` (list in migrations.py)

## Where to Add New Code

**New Feature (e.g., new source type):**
- Primary code: `app/userbot/resolver.py` (if peer resolution needed) or `app/userbot/collector.py` (if fetch logic needed)
- Database: Update `app/db/migrations.py` MIGRATIONS list
- Repository: Add query functions to `app/db/repository.py`
- Tests: No test directory exists; consider adding `tests/` at project root

**New Bot Command (e.g., /export):**
- Handler: `app/bot/handlers/export.py` (new file, follow start.py pattern)
- Register: Import router in `app/bot/create.py` → `create_dispatcher()` → `dp.include_routers(..., export.router)`
- States: Add to `app/bot/states.py` if FSM needed
- Keyboard: Add button to `app/bot/keyboards.py`

**New Scheduled Job (e.g., cleanup old digests):**
- Job function: Add to `app/scheduler/manager.py` (e.g., `_cleanup_job()`)
- Setup: Call `scheduler.add_job()` in `setup_scheduler()` with appropriate trigger
- Trigger: Use `IntervalTrigger(days=7)` or `CronTrigger(...)` from APScheduler

**Utilities (shared helpers):**
- If specific to a layer: Add to that layer's existing module (e.g., chunker.py for message formatting)
- If cross-cutting: Consider creating `app/utils.py` or `app/common.py` (currently none exist)

**New Integration (e.g., another LLM provider):**
- API client: Create `app/providers/openrouter.py` (new subdir) or extend `app/llm/client.py`
- Repository: Add config getters for new provider keys to settings table usage
- Bot handler: Add /select_provider command in `app/bot/handlers/settings.py`

## Special Directories

**data/:**
- Purpose: Runtime database and session files
- Generated: Yes (created by engine.py on first connect)
- Committed: No (.gitignore)
- Manage: Persistent across restarts (mounted volume in docker-compose.yml)

**No Other Generated/Special Directories**
- `__pycache__/`: Ignored (standard Python)
- `venv/`, `.venv/`: Ignored if local dev
- `.git/`: Ignored (outside scope)

---

*Structure analysis: 2025-03-02*
