# Technology Stack

**Analysis Date:** 2026-03-02

## Languages

**Primary:**
- Python 3.12 - All application code

## Runtime

**Environment:**
- Python 3.12-slim (Docker image: `python:3.12-slim`)

**Package Manager:**
- pip (install via `setuptools` build backend)
- Lockfile: Not detected (no requirements.lock, relies on pinned versions in pyproject.toml)

## Frameworks

**Core Application:**
- Telethon 1.37+ - Telegram userbot client (MTProto protocol)
- aiogram 3.16+ - Telegram bot framework (polling mode)
- APScheduler 3.10-3.x - Job scheduling (async IO scheduler, cron + interval triggers)

**Async Runtime:**
- asyncio (Python standard library) - Shared event loop for all async components

**Database:**
- aiosqlite 0.20+ - Async SQLite driver (no ORM, direct SQL queries)

**HTTP Client:**
- httpx 0.28+ - Async HTTP client for LLM API calls (OpenAI-compatible endpoints)

**Configuration Management:**
- pydantic-settings 2.7+ - Environment variable loading and validation

**Encryption:**
- cryptg 0.4+ - Telegram library encryption support

## Key Dependencies

**Critical:**
- telethon 1.37+ - Enables userbot message collection from Telegram channels/groups/topics
- aiogram 3.16+ - Provides bot interface for user commands and digest delivery
- apscheduler 3.10 - Schedules periodic collection and per-source digest generation
- httpx 0.28+ - Makes async calls to LLM endpoints for digest summarization

**Infrastructure:**
- aiosqlite 0.20+ - SQLite connection management with WAL (write-ahead logging)
- pydantic-settings 2.7+ - Validates required credentials at startup

## Configuration

**Environment Variables:**
All configuration via `.env` file (read by `app/config.py` via pydantic-settings):

- `TG_API_ID` - Telegram App API ID (from my.telegram.org)
- `TG_API_HASH` - Telegram App API Hash
- `TG_BOT_TOKEN` - Telegram Bot token (BotFather)
- `LLM_BASE_URL` - OpenAI-compatible API endpoint (default: `http://ollama:11434/v1`)
- `LLM_MODEL` - Model name to use (default: `gemma3:27b`)
- `LLM_API_KEY` - Optional API key for LLM endpoint (empty for local Ollama)
- `TIMEZONE` - Default timezone for cron schedules (default: `Europe/Moscow`)
- `COLLECTION_INTERVAL` - Minutes between message collection runs (default: `15`)
- `DB_PATH` - SQLite database file path (default: `data/app.db`)
- `SESSION_PATH` - Telethon session storage path (default: `data/userbot`)
- `LOG_LEVEL` - Python logging level (default: `INFO`)

**Configuration Class:**
- `app/config.py` - `Settings` class (pydantic BaseSettings)
  - Required fields: `tg_api_id`, `tg_api_hash`, `tg_bot_token`
  - Optional fields default to development values
  - Loaded at module import time into singleton `settings` object

**Build Configuration:**
- `pyproject.toml` - Project metadata, version, dependencies, build system
- `docker-compose.yml` - Two services: app (main), ollama (optional local LLM, profile-gated)
- `Dockerfile` - Multi-step: installs dependencies, copies code, runs `python -m app`

## Platform Requirements

**Development:**
- Python 3.12+
- pip/setuptools
- Internet access to Telegram and LLM API
- Telegram account (for userbot credentials)
- Telegram Bot token (from BotFather)

**Production/Deployment:**
- Docker + Docker Compose (preferred)
- Persistent volume for `data/` directory (SQLite database + Telethon sessions)
- Network access to:
  - Telegram API (core functionality)
  - LLM API endpoint (digest generation)
- Optional: Local Ollama service (if using local LLM instead of remote)

**Database:**
- SQLite 3 with WAL mode enabled
- Creates `data/app.db` on first run
- Schema: 5 tables (sources, digest_configs, messages, digests, settings)

---

*Stack analysis: 2026-03-02*
