# Coding Conventions

**Analysis Date:** 2026-03-02

## Naming Patterns

**Files:**
- Lowercase with underscores: `engine.py`, `client.py`, `repository.py`, `chunker.py`
- Grouped into domain modules: `app/db/`, `app/bot/`, `app/userbot/`, `app/digest/`, `app/llm/`, `app/scheduler/`
- Handler files named descriptively: `start.py`, `sources.py`, `digest.py`, `schedule.py`, `settings.py`

**Functions:**
- snake_case for all functions: `collect_source()`, `get_active_sources()`, `apply_exclude_filter()`
- Private/internal functions prefixed with underscore: `_source()`, `_config()`, `_message()`, `_fetch_unread()`, `_user_name()`
- Job functions and handlers use clear verb-noun patterns: `collect_job()`, `digest_job()`, `cmd_start()`, `on_select_source()`

**Variables:**
- snake_case: `owner_id`, `source_id`, `telegram_id`, `current_tokens`, `current_chunk`
- Module-level constants with clear intent: `log = logging.getLogger(__name__)`
- Single-letter lambdas allowed for clarity: `ok = lambda v: "OK" if v else "FAIL"` (in `/app/bot/handlers/start.py:38`)

**Types:**
- Union syntax using pipe operator: `int | None`, `str | None`, `list[Message]` (Python 3.10+ syntax)
- Type annotations on all function parameters and returns
- Dataclass models use CapWords: `Source`, `DigestConfig`, `Message`, `Digest`, `Settings`

## Code Style

**Formatting:**
- No explicit formatter configured; code appears hand-formatted with consistent 80-100 character line widths
- 4-space indentation (standard Python)
- Multi-line strings and concatenations use standard Python formatting

**Linting:**
- No ruff/flake8 config detected
- One security comment found: `# noqa: S608` on SQL string formatting in `repository.py:108` and `repository.py:180` (marked for dynamic SQL)

**Import Conventions:**
- No `__all__` exports defined in most modules
- Barrel file pattern: `app/bot/__init__.py`, `app/db/__init__.py` are minimal or empty
- Imports always done at module level (no circular imports observed)

## Import Organization

**Order:**
1. Standard library: `import logging`, `import asyncio`, `import os`
2. Third-party: `from aiogram import ...`, `from telethon import ...`, `import httpx`, `from apscheduler import ...`
3. Local app: `from app.config import ...`, `from app.db import ...`, `from app.bot import ...`

**Path Aliases:**
- Repository imported as alias: `from app.db import repository as repo` (consistent across all handlers)
- Settings imported as alias: `from app.config import settings as app_settings` (to avoid shadowing with local settings var)
- Direct imports used when specific objects needed: `from app.db.models import Source, Message`

**Example from `/app/bot/create.py`:**
```python
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import digest, schedule, settings, sources, start
from app.bot.middlewares import OwnerMiddleware
from app.config import settings as app_settings
```

## Error Handling

**Patterns:**
- Broad `except Exception:` with logging used in most cases: `except Exception:` followed by `log.exception(...)`
- Used in async job context where failures should not crash scheduler (`/app/scheduler/manager.py`, `/app/userbot/collector.py`)
- Health checks return boolean on failure: `try/except Exception: return False` in `/app/llm/client.py:60-72`
- Nested error handling for graceful degradation: In `/app/bot/handlers/digest.py:65-72`, outer exception handler has inner try/except for error message delivery

**Database failures:**
- Functions return `None` on not-found: `return _source(row) if row else None` (consistent pattern)
- Direct `.fetchone()` without null checks in atomic operations (relies on row factory)
- No rollback handling (aiosqlite auto-commits at end of context)

**API failures:**
- `resp.raise_for_status()` used in `/app/llm/client.py:49` to surface HTTP errors
- Timeout configuration explicit: `timeout = httpx.Timeout(connect=10, read=300, write=10, pool=10)`

## Logging

**Framework:** Python built-in `logging` module

**Patterns:**
- Module logger initialized once per file: `log = logging.getLogger(__name__)`
- Info level for operational events: `log.info("Generated digest #%d for %s: ...")`
- Warning level for recoverable issues: `log.warning("Dialog not found for chat_id=%d")`
- Exception level with context for errors: `log.exception("Error fetching messages from chat %d")`
- Formatted strings with % substitution (not f-strings): `log.info("Collected %d new messages from '%s'", count, source.title)`

**Logging configuration:** Set in `/app/__main__.py:9-12` from `settings.log_level` environment variable, defaults to `INFO`

## Comments

**When to Comment:**
- Brief docstrings for functions explaining return value and purpose: `"""Insert message, return True if new (not duplicate)."""`
- Single-line docstrings used for simple utility functions
- Separator comments using visual markers: `# ── Sources ──────────────────────────────────────────────` in `/app/db/repository.py:59`

**JSDoc/TSDoc:**
- Not used (Python project)
- Docstrings are one-line or multi-line with triple quotes

**Example from `/app/db/repository.py:142`:**
```python
async def insert_message(...) -> bool:
    """Insert message, return True if new (not duplicate)."""
```

## Function Design

**Size:** Functions range from 5-50 lines
- Utility functions very short: `estimate_tokens()` is 2 lines
- Handler functions 30-40 lines (state machine callbacks)
- Business logic functions 15-30 lines
- Job functions delegate to specialized modules

**Parameters:**
- Positional-only for required args: `async def add_source(telegram_id: int, source_type: str, ...)`
- Optional parameters with defaults: `topic_id: int | None = None`, `limit: int = 500`
- No *args/**kwargs patterns
- Database functions accept primitive types, not objects

**Return Values:**
- Single return type always specified
- Return `None` explicitly for no-op functions: `async def remove_source(source_id: int) -> None`
- Return complex dicts only in LLM client: `{"content": str, "prompt_tokens": int, ...}`
- Most functions return dataclass models

## Module Design

**Exports:**
- Modules export functions and classes at module level
- No `__all__` list used
- Factory functions for bot/dispatcher: `/app/bot/create.py` exports `create_bot()`, `create_dispatcher()`
- No class-based architecture; all functions and dataclasses

**Barrel Files:**
- `/app/bot/__init__.py` - empty
- `/app/db/__init__.py` - empty
- `/app/bot/handlers/__init__.py` - empty
- Imports done directly from submodules: `from app.db.repository import ...` or `from app.db import repository as repo`

**Module responsibilities:**
- `app/config.py` - Settings loading only
- `app/db/` - Models, engine, migrations, repository (all data access)
- `app/bot/` - Bot/dispatcher factory, handlers organized by feature, middlewares, keyboards, states
- `app/userbot/` - Telethon client, message collection, dialog resolution
- `app/digest/` - Message chunking, prompts, LLM calling, digest generation
- `app/llm/` - HTTP client wrapper for OpenAI-compatible API
- `app/scheduler/` - APScheduler setup and job definitions

---

*Convention analysis: 2026-03-02*
