# External Integrations

**Analysis Date:** 2026-03-02

## APIs & External Services

**Telegram API (via Telethon):**
- Userbot message collection from channels, groups, forums, topics
  - SDK/Client: `telethon` 1.37+
  - Auth: Requires TG_API_ID, TG_API_HASH (app-level)
  - Session: Stored locally in `SESSION_PATH` (default: `data/userbot`)
  - Implementation: `app/userbot/client.py` - Singleton TelegramClient instance
  - Used for: Fetching messages from all configured sources at interval

**Telegram Bot API (via aiogram):**
- Bot command handling and digest message delivery to user
  - SDK/Client: `aiogram` 3.16+
  - Auth: TG_BOT_TOKEN (from BotFather)
  - Implementation: `app/bot/create.py` - Bot+Dispatcher factory
  - Polling mode: Long-polling (no webhooks)
  - Used for: Receiving user commands (/add_source, /digest_now, etc.), sending digests

**LLM API (OpenAI-compatible):**
- Chat completion for message summarization
  - Endpoint: Configurable via `LLM_BASE_URL` (default: `http://ollama:11434/v1`)
  - SDK/Client: `httpx` 0.28+ (async HTTP POST)
  - Auth: Optional `LLM_API_KEY` header (empty for local Ollama)
  - Model: Configurable via `LLM_MODEL` (default: `gemma3:27b`)
  - Implementation: `app/llm/client.py`
    - `chat_completion()`: POST `/chat/completions` with system+user messages
    - `check_llm_health()`: GET `/models` for health check
  - Used for: Summarizing message chunks into digests

## Data Storage

**Databases:**
- SQLite (local filesystem)
  - Connection: `aiosqlite` 0.20+
  - File: `DB_PATH` (default: `data/app.db`)
  - Client: Direct SQL via aiosqlite.Row interface
  - Schema (5 tables):
    - `sources` - Channels/groups/topics being tracked (telegram_id, source_type, is_active)
    - `digest_configs` - Per-source schedule/filters (cron_expression, timezone, max_messages, prompts)
    - `messages` - Collected Telegram messages (telegram_msg_id, content, sent_at, is_digested)
    - `digests` - Generated summaries (content, model_used, prompt_tokens, completion_tokens, sent_at)
    - `settings` - App settings (owner_chat_id, llm_base_url, llm_model, llm_api_key)
  - WAL mode: Enabled for concurrent access
  - Foreign keys: Enabled

**File Storage:**
- Local filesystem only (SQLite DB + Telethon session files)
- Volumes in Docker Compose:
  - `./data:/app/data` - Persists database and sessions

**Caching:**
- None detected - No Redis or in-memory cache layer
- Settings loaded per-request from database via `app/db/repository.py`

## Authentication & Identity

**Auth Provider:**
- Custom owner-based auth (no external provider)
  - Implementation: `app/bot/middlewares.py` - OwnerMiddleware
  - Approach: First user to /start becomes owner (chat_id stored in settings table)
  - All subsequent bot commands restricted to owner_chat_id
  - Userbot auth: App-level credentials (TG_API_ID + TG_API_HASH)
  - Bot auth: Token-based (TG_BOT_TOKEN)

## Monitoring & Observability

**Error Tracking:**
- None detected - No Sentry, Rollbar, or similar

**Logs:**
- Python standard logging library (configured in `app/__main__.py`)
  - Log level: Configurable via `LOG_LEVEL` env var (default: INFO)
  - Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
  - Output: Stdout (suitable for Docker container logs)
  - Module loggers: Named per module (e.g., `__name__`)
  - Token usage tracking: Logged in `app/digest/generator.py`

**Health Checks:**
- `app/llm/client.py` - `check_llm_health()` function (GET /models endpoint)
- Status command in bot: Reports Telegram connection + LLM availability

## CI/CD & Deployment

**Hosting:**
- Docker Compose (development and production)
- Services:
  - `app` - Main bot + userbot + scheduler service
  - `ollama` - Optional local LLM (profile: `local-llm`)

**CI Pipeline:**
- Not detected - No GitHub Actions, GitLab CI, or similar

**Deployment Trigger:**
- Manual via `docker-compose up`
- Entry point: `CMD ["python", "-m", "app"]` (runs `app/__main__.py`)

**Restart Policy:**
- `restart: unless-stopped` on app service

## Environment Configuration

**Required Environment Variables:**
- `TG_API_ID` (no default) - Telegram app ID
- `TG_API_HASH` (no default) - Telegram app hash
- `TG_BOT_TOKEN` (no default) - Telegram bot token

**Optional Environment Variables (with defaults):**
- `LLM_BASE_URL` (default: `http://ollama:11434/v1`)
- `LLM_MODEL` (default: `gemma3:27b`)
- `LLM_API_KEY` (default: empty string)
- `TIMEZONE` (default: `Europe/Moscow`)
- `COLLECTION_INTERVAL` (default: `15` minutes)
- `DB_PATH` (default: `data/app.db`)
- `SESSION_PATH` (default: `data/userbot`)
- `LOG_LEVEL` (default: `INFO`)

**Secrets Location:**
- `.env` file (git-ignored, provided at runtime)
- Docker Compose: `env_file: .env` in app service
- Example template: `.env.example`

## Webhooks & Callbacks

**Incoming:**
- None - Bot uses long-polling mode (no webhook)

**Outgoing:**
- None detected - No outbound webhooks

**Message Delivery:**
- Bot sends digests via `bot.send_message()` (aiogram API) to owner_chat_id
- Message splitting: `app/bot/formatting.py` - `split_message()` chunks long digests into Telegram message limits

## Data Flow Summary

1. **Collection Phase** (periodic, interval trigger):
   - Scheduler runs `_collect_job()` every N minutes
   - Userbot fetches new messages from all active sources
   - Messages stored in `messages` table with `is_digested=0`

2. **Digest Generation Phase** (per-source, cron trigger):
   - Scheduler runs `_digest_job(source_id)` per configured schedule
   - Repository fetches undigested messages
   - Pre-LLM filtering applied (exclude_filter)
   - Messages chunked by token limit
   - Each chunk sent to LLM API (with system+user prompts)
   - Multi-chunk results merged into single digest
   - Digest saved to `digests` table, messages marked `is_digested=1`

3. **Delivery Phase**:
   - Bot sends digest via `send_message()` (split if > 4096 chars)
   - Digest marked `sent_at` timestamp

---

*Integration audit: 2026-03-02*
