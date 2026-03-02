# Architecture

**Analysis Date:** 2025-03-02

## Pattern Overview

**Overall:** Layered async pipeline architecture with coordinated services

**Key Characteristics:**
- Single asyncio event loop shared by all subsystems (userbot, bot, scheduler)
- Sequential initialization order: Database → Userbot → Scheduler → Bot
- Centralized repository pattern for database access (no ORM)
- Message pipeline: Collection → Chunking → LLM processing → Digest storage

## Layers

**Configuration Layer:**
- Purpose: Environment and runtime settings management
- Location: `app/config.py`
- Contains: Pydantic Settings class for Telegram API, LLM, database, and scheduler config
- Depends on: `.env` file via pydantic-settings
- Used by: All subsystems during initialization

**Database Layer:**
- Purpose: Async SQLite access, schema management, and data persistence
- Location: `app/db/`
- Contains:
  - `engine.py`: Singleton aiosqlite connection with WAL mode and foreign keys enabled
  - `migrations.py`: Schema definition (sources, digest_configs, messages, digests, settings) and migration runner
  - `models.py`: Dataclass models (Source, DigestConfig, Message, Digest)
  - `repository.py`: All query functions organized by entity (sources, configs, messages, digests, settings)
- Depends on: aiosqlite, app/config.py
- Used by: Userbot collector, digest generator, scheduler, bot handlers

**Userbot Layer (Message Collection):**
- Purpose: Connect to Telegram user account and collect unread messages from sources
- Location: `app/userbot/`
- Contains:
  - `client.py`: Singleton Telethon TelegramClient initialization
  - `collector.py`: Message fetching from channels/groups/folders (handles unread-only logic, media detection, sender parsing)
  - `resolver.py`: Folder peer resolution (not examined but imported in collector)
- Depends on: Telethon, repository layer
- Used by: Scheduler collection jobs

**Scheduler Layer (Orchestration):**
- Purpose: Schedule periodic collection jobs and source-specific digest generation
- Location: `app/scheduler/manager.py`
- Contains:
  - `setup_scheduler()`: Initializes APScheduler 3.x AsyncIOScheduler with:
    - Fixed interval collection job (default 15 minutes)
    - Dynamic cron-based digest jobs per source (timezone-aware)
  - `_collect_job()`: Calls collector on all active sources
  - `_digest_job()`: Generates digest, sends via bot, marks messages digested
  - `refresh_schedules()`: Hot-reload schedule after configuration changes
- Depends on: APScheduler, userbot, repository, digest generator, bot
- Used by: Main entry point

**Digest Processing Layer (LLM Pipeline):**
- Purpose: Transform collected messages into summaries via LLM
- Location: `app/digest/`
- Contains:
  - `generator.py`: Main pipeline — fetches undigested messages, applies exclude filter, chunks for LLM, calls chat_completion, merges multi-chunk results, saves digest with token counts
  - `chunker.py`: Token-aware message splitting (12k token budget default), exclude keyword filter, message formatting with sender/timestamp/link
  - `prompts.py`: System and user prompt builders (not examined but imported)
- Depends on: Repository, LLM client, chunker
- Used by: Scheduler digest jobs

**LLM Client Layer (External Integration):**
- Purpose: OpenAI-compatible API wrapper with configurable endpoint and model
- Location: `app/llm/client.py`
- Contains:
  - `chat_completion()`: POST to /chat/completions with bearer auth, timeout handling, token extraction
  - `get_llm_config()`: Fetch base_url/model/api_key from settings table (overridable at runtime)
  - `check_llm_health()`: GET /models endpoint for health check
- Depends on: httpx, repository (for runtime settings)
- Used by: Digest generator, bot status command

**Bot Layer (User Interface & Control):**
- Purpose: Telegram bot command handlers and FSM-based stateful interactions
- Location: `app/bot/`
- Contains:
  - `create.py`: Bot and Dispatcher factory functions
  - `middlewares.py`: OwnerMiddleware — first /start user becomes owner, non-owners silently blocked
  - `handlers/`: Command routers (start, sources, schedule, digest, settings)
  - `states.py`: FSM state definitions
  - `keyboards.py`: Inline/reply keyboard builders
  - `formatting.py`: Message splitting for Telegram's 4096 char limit
- Depends on: aiogram, repository, userbot (for connection status), LLM client
- Used by: Entry point as polling receiver

**Entry Point Layer:**
- Purpose: Bootstrap and coordinate all subsystems on shared asyncio loop
- Location: `app/__main__.py`
- Orchestration sequence:
  1. Configure logging from settings
  2. Run database migrations
  3. Connect userbot (Telethon)
  4. Start scheduler with initial digest jobs
  5. Create bot and dispatcher
  6. Poll for bot messages
  7. Shutdown: scheduler → userbot → database

## Data Flow

**Message Collection Cycle:**
1. Scheduler triggers `_collect_job()` every N minutes
2. Collector queries all active sources from DB
3. For each source:
   - Resolve folder peers (if folder type)
   - Query Telegram dialog to get unread count
   - Iterate unread messages, extract text/sender/timestamp
   - Insert into `messages` table (duplicates ignored via UNIQUE constraint)
   - Mark `is_digested=0` for new messages

**Digest Generation Cycle:**
1. Scheduler triggers `_digest_job(source_id)` on cron schedule
2. Generator fetches undigested messages for source
3. Apply exclude_filter (pre-LLM, filters by keyword/sender)
4. Chunk messages into 12k token budget slices
5. For each chunk:
   - Build system prompt (with focus_on, include_filter from config)
   - Call LLM /chat/completions
   - Accumulate prompt + completion tokens
6. If multiple chunks, send merge request to LLM
7. Save digest to `digests` table with token counts
8. Mark messages as `is_digested=1`
9. Send digest via bot to owner (with message splitting if >4096 chars)
10. Mark digest as `sent_at=now()`

**State Management:**
- **Persistent state:** Database (sources, messages, digests, settings)
- **In-memory state:** Scheduler jobs, bot dispatcher FSM state (MemoryStorage)
- **Configuration state:** Settings table (llm_base_url, llm_model, llm_api_key, owner_id, owner_chat_id)

## Key Abstractions

**Source:**
- Purpose: Represents a Telegram entity to monitor (channel, group, folder, topic)
- File: `app/db/models.py`
- Pattern: Dataclass with source_type enum (folder/channel/group/chat/topic)
- Lifecycle: Created via bot handler, marked inactive (soft delete), reactivated on re-add

**DigestConfig:**
- Purpose: Schedule and filtering rules per source
- File: `app/db/models.py`
- Pattern: Dataclass linked 1:1 with Source
- Includes: cron_expression, timezone, max_messages, prompt_template, focus_on, include_filter, exclude_filter

**Message:**
- Purpose: Collected Telegram message metadata (not full telegram Update object)
- File: `app/db/models.py`
- Pattern: Dataclass with content, sender_name, sent_at, topic_id, is_digested flag
- Lifecycle: Inserted with is_digested=0 → marked is_digested=1 after digest generation

**Digest:**
- Purpose: Generated summary with token accounting
- File: `app/db/models.py`
- Pattern: Dataclass with content, model_used, prompt_tokens, completion_tokens, sent_at
- Lifecycle: Created after LLM processing → marked sent_at after bot sends

## Entry Points

**Process Entry:**
- Location: `app/__main__.py` / main()
- Triggers: `python -m app` (via Docker ENTRYPOINT)
- Responsibilities: Logging setup, data dir creation, async runtime initialization

**Async Entry:**
- Location: `app/__main__.py` / _run()
- Triggers: asyncio.run()
- Responsibilities: Coordinate DB → userbot → scheduler → bot initialization and graceful shutdown

**Bot Commands:**
- Location: `app/bot/handlers/` (start.py, sources.py, schedule.py, digest.py, settings.py)
- Triggers: Telegram bot polling
- Responsibilities: Handle user commands, validate owner status (via OwnerMiddleware), call repository/scheduler

**Scheduled Jobs:**
- Location: `app/scheduler/manager.py`
- Triggers: APScheduler cron/interval triggers
- Responsibilities: Collect messages, generate digests, send to user

## Error Handling

**Strategy:** Try-except at job boundaries with logging; graceful degradation (skip source on error, continue others)

**Patterns:**
- Collection errors: `collect_source()` wrapped in try-except, logs and continues to next source
- Digest generation: `_digest_job()` catches all errors, logs exception, continues scheduler
- LLM errors: `chat_completion()` raises httpx errors, caller handles (digest job catches)
- Bot send errors: `_digest_job()` catches send failures, logs but marks digest sent (best-effort)
- Database errors: Repository functions raise, callers handle (scheduler catches)

## Cross-Cutting Concerns

**Logging:** Python stdlib logging configured from settings.log_level, subsystems use `logging.getLogger(__name__)`

**Validation:** Pydantic in config.py; FSM states enforce command sequences; repository functions validate data types

**Authentication:** OwnerMiddleware checks owner_id in settings; first /start user auto-enrolled as owner

**Rate Limiting:** Manual `await asyncio.sleep(1)` between Telegram API calls in collector and scheduler loops

**Timezone Handling:** Cron triggers use ZoneInfo from DigestConfig.timezone; message sent_at stored as ISO string

**Token Accounting:** Digest generator estimates tokens (len/4 rough heuristic) and accumulates actual counts from LLM response usage

---

*Architecture analysis: 2025-03-02*
