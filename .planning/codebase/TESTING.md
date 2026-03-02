# Testing Patterns

**Analysis Date:** 2026-03-02

## Test Framework

**Status:** No testing framework configured or tests present

**Detection:**
- No pytest/unittest dependencies in `pyproject.toml`
- No test files found in codebase (searched for `*test*.py` and `test_*.py` patterns)
- No pytest/tox/unittest configuration files detected (no `pytest.ini`, `tox.ini`, `setup.cfg`, `.pytest.ini`)
- No CI/CD pipeline configuration found (no `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`)

**Implications:**
- New tests should follow pytest convention if added (Python standard for async projects)
- Consider pytest-asyncio for testing async functions (given heavy asyncio usage)
- No test data fixtures exist

## Development Dependencies Needed for Testing

If testing is to be added, based on tech stack:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=app --cov-report=html"
```

**Recommended packages:**
- `pytest` - Test runner
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking support
- Possibly `freezegun` for time mocking (given APScheduler usage)

## Current Testing Approach

**Manual Testing Only:**
- System appears to rely on runtime behavior verification
- Scheduler jobs test their paths during execution
- Bot handlers tested through Telegram bot interaction
- No automated regression protection

## Code Testability Assessment

**Highly Testable Components:**

1. **Data Access Layer** (`app/db/repository.py`)
   - Pure functions mapping rows to dataclasses
   - Dependency: aiosqlite Connection (can be mocked)
   - No side effects in mapping functions
   - Would benefit from fixture-based SQL testing

2. **Digest Generation** (`app/digest/generator.py`)
   - Clear input/output contracts
   - Depends on repo (mockable) and LLM client (mockable)
   - Message chunking and filtering are deterministic

3. **Message Chunking** (`app/digest/chunker.py`)
   - Pure functions: `chunk_messages()`, `apply_exclude_filter()`, `format_message()`
   - Token estimation is deterministic
   - Filter logic has clear test cases

4. **LLM Client** (`app/llm/client.py`)
   - HTTP wrapper with clear interface
   - Could mock httpx.AsyncClient responses
   - Health check has try/except boundary

**Hard to Test Components:**

1. **Bot Handlers** (`app/bot/handlers/*.py`)
   - Tight coupling to aiogram types (Message, CallbackQuery, FSMContext)
   - State machine testing would require FSM mocking
   - Keyboard generation is coupled to handler logic
   - Would need `pytest-aiogram` or similar

2. **Userbot Collection** (`app/userbot/collector.py`)
   - Depends on TelegramClient (Telethon) which is stateful
   - Async iteration patterns (`client.iter_dialogs()`, `client.iter_messages()`)
   - Would require Telethon mock or integration testing

3. **Scheduler Jobs** (`app/scheduler/manager.py`)
   - APScheduler integration tests
   - Job scheduling and triggering would need real scheduler or mock

4. **Middleware** (`app/bot/middlewares.py`)
   - Depends on aiogram middleware interface
   - State-dependent (owner_id from database)

## Recommended Test Structure

If testing is added, follow this organization:

```
tests/
├── conftest.py              # Pytest fixtures and config
├── unit/
│   ├── test_chunker.py      # Pure function tests (high ROI)
│   ├── test_repository.py   # Data mapping tests (requires mock DB)
│   ├── test_llm_client.py   # HTTP client tests (mock httpx)
│   └── test_formatter.py    # Message formatting
├── integration/
│   ├── test_digest_flow.py  # Generator + repo + LLM mock
│   └── test_db.py           # With real SQLite test database
└── fixtures/
    ├── messages.py          # Sample Message dataclass instances
    ├── sources.py           # Sample Source instances
    └── digests.py           # Sample Digest instances
```

## Pure Function Testing (High Priority)

These functions have no I/O and are ideal starting points:

**From `/app/digest/chunker.py`:**
```python
# These should be first tests written
def test_estimate_tokens():
    assert estimate_tokens("hello") == 1
    assert estimate_tokens("hello world test") == 3

def test_format_message():
    msg = Message(id=1, source_id=1, telegram_msg_id=1, ...)
    formatted = format_message(msg)
    assert "[link:" in formatted

def test_chunk_messages_splits_on_budget():
    # Create 3 messages with known token size
    # Verify chunking at token_budget boundary

def test_apply_exclude_filter():
    messages = [...]  # Create test messages
    filtered = apply_exclude_filter(messages, "keyword1,keyword2")
    # Verify keyword matching (case-insensitive)
```

**From `/app/bot/formatting.py`:**
```python
# Likely includes message splitting logic
# Would test output format and line breaking
```

## Integration Test Example Pattern

If async testing is added with pytest-asyncio:

```python
@pytest.mark.asyncio
async def test_generate_digest_with_mocks(mocker):
    """Test digest generation with mocked repo and LLM."""
    # Mock repository
    mock_repo = mocker.patch('app.digest.generator.repo')
    mock_repo.get_digest_config.return_value = DigestConfig(
        id=1, source_id=1, cron_expression="0 9 * * *",
        timezone="Europe/Moscow", max_messages=500, ...
    )
    mock_repo.get_undigested_messages.return_value = [
        Message(id=1, source_id=1, telegram_msg_id=123, content="Test")
    ]

    # Mock LLM client
    mocker.patch('app.digest.generator.chat_completion', return_value={
        "content": "Summary text",
        "prompt_tokens": 100,
        "completion_tokens": 50
    })

    # Execute
    source = Source(id=1, telegram_id=123456, source_type="channel", ...)
    result = await generate_digest(source)

    # Verify
    assert result is not None
    assert "Summary" in result
    mock_repo.save_digest.assert_called_once()
```

## Database Testing

For testing `/app/db/repository.py`, use pytest fixture with in-memory SQLite:

```python
@pytest.fixture
async def test_db():
    """Provide in-memory test database with schema."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row

    # Run migrations
    from app.db.migrations import run_migrations_on_connection
    await run_migrations_on_connection(db)

    yield db
    await db.close()

@pytest.mark.asyncio
async def test_add_source(test_db, mocker):
    """Test source insertion."""
    mocker.patch('app.db.repository.get_db', return_value=test_db)

    source = await add_source(12345, "channel", "Test Channel")
    assert source.telegram_id == 12345
    assert source.title == "Test Channel"
```

## Coverage Targets

**If testing is implemented:**
- Aim for 80%+ on `app/digest/` (business logic)
- Aim for 90%+ on `app/db/` (data layer)
- Aim for 60%+ on `app/bot/handlers/` (handler integration tests)
- Skip coverage enforcement on `app/userbot/` (requires Telethon mocking)

**Coverage command would be:**
```bash
pytest --cov=app --cov-report=html --cov-report=term-missing
```

## What NOT to Test

Given the architecture:

1. **Telethon integration** - Too complex to mock; requires live Telegram connection or comprehensive integration setup
2. **aiogram handler dispatch** - Framework responsibility; test business logic instead of routing
3. **APScheduler scheduling** - Library responsibility; test job functions, not scheduling
4. **httpx HTTP layer** - Library responsibility; mock at response level, not transport

---

*Testing analysis: 2026-03-02*

**Note:** This project currently has zero test coverage. Any testing framework implementation should start with the pure functions in `app/digest/chunker.py` and `app/db/repository.py` (mapping functions), as these have the highest ROI and lowest testing complexity.
