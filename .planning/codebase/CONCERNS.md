# Codebase Concerns

**Analysis Date:** 2025-03-02

## Tech Debt

**Silent migration failures in schema versioning:**
- Issue: Migrations catch all exceptions with bare `pass`, masking legitimate errors. If a column add fails due to constraint issues or corruption, the application starts anyway with an incomplete schema.
- Files: `app/db/migrations.py` (lines 67-70)
- Impact: Database inconsistency, silent failures that surface unpredictably. Difficult to debug in production.
- Fix approach: Log caught exceptions with severity levels. Validate schema before allowing app startup. Use explicit column existence checks instead of broad exception handling.

**Token estimation is inaccurate:**
- Issue: `estimate_tokens()` uses hardcoded 4 chars per token, but modern tokenizers vary by 3.5-4.5 chars/token depending on content. This causes under/over-chunking.
- Files: `app/digest/chunker.py` (lines 4-6)
- Impact: Digest chunks may exceed LLM context limits (especially with Cyrillic/non-ASCII), causing API failures mid-generation. Inconsistent chunking behavior.
- Fix approach: Implement proper tokenization using `tiktoken` library or track actual token counts from LLM responses. Validate chunk sizes empirically.

**Bare exception handling masks real errors:**
- Issue: Multiple catch-all `except Exception:` blocks log but don't re-raise or fail gracefully, hiding cascading failures.
- Files: `app/userbot/resolver.py` (lines 32-36, 45-62), `app/userbot/collector.py` (lines 45-99), `app/scheduler/manager.py` (lines 104-115), `app/bot/handlers/digest.py` (lines 65-72)
- Impact: Failed operations (network errors, invalid folder IDs, malformed cron) silently continue. Jobs may appear scheduled but never execute.
- Fix approach: Categorize exceptions (retryable vs permanent). Raise or set error flags for non-transient failures. Add structured error context to logs.

**Database connections pooling not implemented:**
- Issue: Single global connection `_db` in `app/db/engine.py` handles all queries. Under high concurrency (multiple digest jobs + user requests), connections may block or queue.
- Files: `app/db/engine.py` (lines 8-15)
- Impact: Performance degradation during peak load (multiple digests + scheduler jobs + bot handlers). No connection timeout protection.
- Fix approach: Implement aiosqlite connection pooling. Set WAL mode checkpoint intervals. Monitor connection queue depth.

**LLM timeout configuration is loose:**
- Issue: `httpx.AsyncClient` timeout is 300s (5 min) for read/completion. No per-request retry logic or circuit breaker for LLM service outages.
- Files: `app/llm/client.py` (lines 46)
- Impact: Long-running requests block digest jobs. If LLM is slow/down, entire digest pipeline hangs. No graceful degradation.
- Fix approach: Implement exponential backoff with jitter. Add circuit breaker (fail-fast after N consecutive failures). Cache partial results.

**Cron expression validation is deferred:**
- Issue: Invalid cron expressions are parsed at scheduler runtime, not at user input time.
- Files: `app/scheduler/manager.py` (lines 104-115, 135-149)
- Impact: Invalid cron input silently fails to schedule a job. User gets no feedback. Job never runs but UI reports "success".
- Fix approach: Validate cron at input time in `app/bot/handlers/schedule.py`. Use `croniter` to pre-validate before persistence.

## Known Bugs

**Forum topic resolution may return wrong topic IDs:**
- Symptoms: Messages from forum topics are assigned incorrect `topic_id`, breaking topic-specific filtering.
- Files: `app/userbot/collector.py` (lines 68-73)
- Trigger: When fetching messages with `reply_to` parameter in forum chats, the code attempts to extract topic ID from `msg.reply_to.forum_topic` or `reply_to_top_id`, which may not align with actual topic structure.
- Workaround: Use Telethon's `get_messages()` with explicit `reply_to` parameter; avoid `iter_messages()` for forum chats.

**Owner middleware silently drops non-owner events:**
- Symptoms: Non-owner users send commands but receive no response (not even "unauthorized").
- Files: `app/bot/middlewares.py` (lines 30-31)
- Trigger: Any non-owner user interacts with bot after owner is set.
- Workaround: Send explicit "unauthorized" response instead of silent drop. Track attempted access for audit.

**Digest generation fails if no config exists:**
- Symptoms: When `generate_digest()` is called but no `digest_config` row exists for the source, it uses hardcoded defaults (500 messages). This breaks if user changes settings after source was added.
- Files: `app/digest/generator.py` (lines 18-19)
- Trigger: Source has no config row (shouldn't happen due to auto-create in `add_source`, but race conditions possible).
- Workaround: Always create config row synchronously in `add_source()`. Add NOT NULL constraint to config table.

**Scheduler doesn't persist state across restarts:**
- Symptoms: Scheduled digests run once on startup, then disappear if the app crashes/restarts.
- Files: `app/scheduler/manager.py` (lines 86-118)
- Trigger: Scheduler jobs are built from DB at startup but not persisted. Job state is only in-memory.
- Workaround: Implement persistent job store (SQLite or file-based). Use APScheduler's `default_executor` with persistence enabled.

## Security Considerations

**SQL injection risk in dynamic UPDATE:**
- Risk: `upsert_digest_config()` builds SQL string dynamically with `f-string`, though parameterized values are used for content.
- Files: `app/db/repository.py` (lines 106-109) - marked with `# noqa: S608`
- Current mitigation: Parameters are still bound (not concatenated into string), so injection is prevented. But the pattern is brittle.
- Recommendations: Use SQLBuilder pattern or explicit field lists instead of `f-string` SQL. Remove `noqa` comments to enforce static analysis on future changes.

**API key in plaintext in settings table:**
- Risk: LLM API key is stored unencrypted in SQLite settings table.
- Files: `app/config.py`, `app/llm/client.py` (lines 20)
- Current mitigation: None. Key is transmitted in HTTP headers (HTTPS assumed in production).
- Recommendations: Encrypt API key at rest using `cryptography.Fernet`. Store encryption key separately (env var or secrets manager). Implement key rotation.

**No rate limiting on bot commands:**
- Risk: User can spam digest generation, exhausting LLM quota and bot resources.
- Files: `app/bot/handlers/digest.py` (lines 19-29), all command handlers
- Current mitigation: None.
- Recommendations: Add per-user rate limiting (e.g., max 1 digest per 5 minutes). Use aiogram's `CallbackQueryLimit` or custom middleware.

**Userbot session tokens not secured:**
- Risk: Telethon session file (`data/userbot`) contains Telegram account credentials. If leaked, account is compromised.
- Files: `app/config.py` (line 16), `app/userbot/client.py`
- Current mitigation: Session path defaults to `data/userbot` (unencrypted, world-readable if permissions not set).
- Recommendations: Encrypt session file. Set strict file permissions (0600). Rotate API credentials if session is exposed. Consider using bot token instead of userbot (limitations apply).

**No input validation on user-provided filters:**
- Risk: User can provide arbitrarily large `focus_on`, `include_filter`, `exclude_filter` strings, potentially causing memory issues or LLM abuse.
- Files: `app/bot/handlers/sources.py` (lines 237-241), `app/digest/generator.py` (lines 32-36)
- Current mitigation: None.
- Recommendations: Enforce max length (e.g., 500 chars). Validate filter syntax. Add input sanitization before LLM prompt injection.

## Performance Bottlenecks

**Dialog iteration during message collection is O(n) for all dialogs:**
- Problem: `_fetch_unread()` iterates all dialogs to find the target chat, even when chat_id is known.
- Files: `app/userbot/collector.py` (lines 48-51)
- Cause: Telethon's dialog API requires iteration; no direct lookup by ID.
- Improvement path: Cache dialog list or use `get_entity()` directly instead of iterating all dialogs.

**LLM inference for multi-chunk digests makes extra API call:**
- Problem: When a digest has >1 chunk, all summaries are merged in a second LLM call (lines 61-73 in `generator.py`). This doubles token usage and latency.
- Files: `app/digest/generator.py` (lines 61-73)
- Cause: Original design assumes chunks need merging, but could use extractive summarization or streaming.
- Improvement path: Implement single-pass streaming summarization, or use more intelligent chunking that preserves logical boundaries.

**Scheduler refresh is synchronous and blocks event loop:**
- Problem: `refresh_schedules()` rebuilds all jobs synchronously during user requests.
- Files: `app/scheduler/manager.py` (lines 121-156)
- Cause: Called from bot handlers, which are async but db queries are serial.
- Improvement path: Move refresh to background job or async queue. Implement incremental job updates (only update changed jobs).

**No pagination for message collection:**
- Problem: `collect_source()` fetches up to 500 unread messages per source, and chunks them for LLM. If messages are large, this causes memory spike.
- Files: `app/digest/generator.py` (lines 18-20)
- Cause: All messages loaded into memory before chunking.
- Improvement path: Implement streaming generator for messages. Process chunks as they're fetched, not after.

## Fragile Areas

**Telethon entity resolution is brittle:**
- Files: `app/userbot/resolver.py` (lines 22-40), `app/userbot/collector.py` (lines 22-31)
- Why fragile: Dialog filters, folder IDs, and forum topic structures vary by account. Code assumes specific API response format and structure. Changes to Telethon library or Telegram API break silently.
- Safe modification: Add comprehensive logging of entity types and structures. Test against multiple account types (personal, business, with forums/topics). Mock Telethon responses in tests.
- Test coverage: No unit tests for resolver. Integration tests only in manual testing.

**Cron expression parsing has minimal validation:**
- Files: `app/scheduler/manager.py` (lines 73-83, 104-115)
- Why fragile: APScheduler's `CronTrigger` accepts invalid expressions without error. Timezone handling may fail if `ZoneInfo` doesn't recognize timezone string.
- Safe modification: Pre-validate all cron before passing to scheduler. Test timezone boundaries (DST transitions, leap seconds).
- Test coverage: No unit tests for cron parsing.

**LLM prompt injection via user filters:**
- Files: `app/digest/prompts.py`, `app/digest/generator.py` (lines 32-37)
- Why fragile: User-provided `focus_on`, `include_filter` are directly embedded in system prompt without sanitization. Malicious user could inject prompt instructions.
- Safe modification: Use prompt parameterization instead of string concatenation. Escape special characters. Add strict input validation.
- Test coverage: No tests for prompt injection scenarios.

**Global scheduler singleton without thread-safety:**
- Files: `app/scheduler/manager.py` (lines 15, 88)
- Why fragile: `scheduler` global is modified during `setup_scheduler()` and `refresh_schedules()`. If called concurrently, race conditions possible.
- Safe modification: Use lock or atomic compare-and-swap. Move scheduler to dependency injection.
- Test coverage: No concurrency tests.

**Database schema versioning is missing:**
- Files: `app/db/migrations.py` (lines 58-71)
- Why fragile: No version tracking. If future migrations conflict, no way to detect which migrations have run. Adding new migrations is error-prone.
- Safe modification: Implement versioned migrations (e.g., `001_initial.sql`, `002_add_chat_id.sql`). Track applied versions in DB. Validate schema at startup.
- Test coverage: No migration tests.

## Scaling Limits

**Single-threaded Telegram userbot can't handle multiple sources efficiently:**
- Current capacity: 1 userbot instance, sequential source collection with 1-second delays.
- Limit: With 10+ sources, collection takes >10 seconds. If unread message counts are high, this can exceed LLM token budgets.
- Scaling path: Implement multiple userbot instances (authenticated accounts) or use Telegram's official Bot API for non-protected chats. Pre-filter large message batches.

**SQLite WAL mode will saturate on high concurrency:**
- Current capacity: ~100-200 writes/sec on modern hardware.
- Limit: If multiple digest jobs run concurrently and bot handles many user requests, write contention increases. WAL checkpoints can block readers.
- Scaling path: Migrate to PostgreSQL or use connection pooling with SQLite. Implement write batching.

**LLM API rate limits not enforced:**
- Current capacity: Limited by upstream API (OpenAI, Ollama, etc).
- Limit: No queue or rate limiter on requests. Multiple concurrent digests can burst and hit rate limits.
- Scaling path: Implement request queue with token bucket algorithm. Add circuit breaker. Cache summaries.

**Bot update polling is not scalable:**
- Current capacity: Single polling loop, ~30-50 updates/sec typical.
- Limit: High-volume bot cannot handle many concurrent users. Polling introduces latency.
- Scaling path: Migrate to webhooks. Use message queue (Redis, RabbitMQ) to decouple update processing.

## Dependencies at Risk

**APScheduler 3.x is the last release of v3; v4 is alpha:**
- Risk: v3 is no longer maintained. Security updates unlikely. v4 has breaking changes and is unstable.
- Impact: Future Python versions may drop v3 support. No bug fixes for newly discovered issues.
- Migration plan: Monitor APScheduler v4 maturity. If v3 causes problems, consider switching to `croniter` + `asyncio.Task` scheduler (simpler, no external scheduler).

**Telethon's MTProto API is reverse-engineered:**
- Risk: Telegram can change protocol without notice. Telethon may break after Telegram updates.
- Impact: Userbot functionality could suddenly stop working. Account could be flagged for suspicious activity.
- Migration plan: Reduce reliance on userbot (userbot fetching is fragile). Use Telegram Bot API for public channels. Implement fallback to user notification if userbot fails.

**`aiosqlite` lacks connection pooling:**
- Risk: Single-threaded, no recovery for hung connections. Manual cleanup required.
- Impact: Long-running connections may become stale. Memory leaks if connections not properly closed.
- Migration plan: Evaluate `databases` library (async ORM) or implement manual connection pooling. Add connection health checks.

**Pydantic v2 migration incomplete:**
- Risk: Using `pydantic_settings` suggests v2, but no strict version pinning. Breaking changes between v1 and v2 possible.
- Impact: Environment parsing could fail silently if settings schema changes.
- Migration plan: Explicitly pin `pydantic>=2.0,<3.0` in requirements. Add pydantic validation tests.

## Missing Critical Features

**No error recovery for LLM outages:**
- Problem: If LLM service is down, digests fail silently. No queuing or retry.
- Blocks: Cannot reliably generate digests when LLM is intermittently unavailable.
- Recommendation: Implement exponential backoff. Queue failed digests. Add fallback to cached/partial summaries.

**No audit logging for user actions:**
- Problem: No record of who added/removed sources, when, or what was modified.
- Blocks: Cannot investigate unauthorized changes or debug user issues.
- Recommendation: Add audit log table. Log all data mutations with user ID, timestamp, before/after values.

**No health monitoring or metrics:**
- Problem: No way to know digest success rate, LLM latency, or message collection stats.
- Blocks: Cannot proactively detect problems or optimize performance.
- Recommendation: Implement Prometheus metrics export. Track success/failure rates, latencies, token usage. Add health check endpoint.

**No backup or disaster recovery:**
- Problem: No automated backups of SQLite database.
- Blocks: Database corruption or accidental data loss is unrecoverable.
- Recommendation: Implement automated WAL-safe backups. Test recovery procedure. Consider read replicas.

## Test Coverage Gaps

**No tests for Telethon resolver functions:**
- What's not tested: `resolve_folder_peers()`, `get_forum_topics()`, `search_dialogs()`, `list_folders()`
- Files: `app/userbot/resolver.py`
- Risk: Dialog resolution bugs only found in production. Changes to Telethon may break undetected.
- Priority: High - core functionality used in every source addition.

**No tests for digest generation pipeline:**
- What's not tested: End-to-end `generate_digest()` with multi-chunk messages, filter application, LLM calls.
- Files: `app/digest/generator.py`, `app/digest/chunker.py`
- Risk: Chunking errors, token overages, LLM failures discovered too late. Filter logic bugs missed.
- Priority: High - critical user-facing feature.

**No tests for scheduler job management:**
- What's not tested: Cron parsing, job scheduling, refresh logic, error handling for invalid cron.
- Files: `app/scheduler/manager.py`
- Risk: Invalid cron expressions silently fail. Job updates don't propagate. Scheduler state becomes inconsistent.
- Priority: High - users depend on scheduled digests.

**No tests for database repository:**
- What's not tested: CRUD operations, concurrent access, transaction handling, constraint violations.
- Files: `app/db/repository.py`
- Risk: Silent query failures, constraint violations, data corruption not caught.
- Priority: Medium - indirectly tested via integration tests.

**No tests for LLM client:**
- What's not tested: Timeout handling, retry logic, error responses, token counting.
- Files: `app/llm/client.py`
- Risk: LLM failures cause cryptic errors. Timeouts hang the app. Invalid API keys not caught early.
- Priority: Medium - could fail gracefully.

**No tests for bot handlers:**
- What's not tested: Command parsing, state machine transitions, callback handling, error recovery.
- Files: `app/bot/handlers/`
- Risk: User interactions cause unhandled exceptions. State becomes invalid. Commands have unexpected behavior.
- Priority: Medium - lower risk due to exception handling in main loop.

---

*Concerns audit: 2025-03-02*
