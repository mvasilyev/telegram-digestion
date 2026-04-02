import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.db import repository as repo
from app.digest.generator import generate_digest
from app.bot.formatting import split_message

log = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


async def _collect_job() -> None:
    """Scheduled job: collect messages from all sources."""
    from app.userbot.client import get_userbot

    client = get_userbot()
    if not client.is_connected():
        log.warning("Userbot not connected, attempting reconnect...")
        try:
            await client.connect()
            if not await client.is_user_authorized():
                log.error("Userbot reconnected but not authorized, skipping collection")
                return
            log.info("Userbot reconnected successfully")
        except Exception:
            log.exception("Userbot reconnect failed, skipping collection")
            return

    from app.userbot.collector import collect_all
    results = await collect_all(client)
    total = sum(results.values())
    log.info("Collection complete: %d new messages from %d sources", total, len(results))


async def _digest_job(source_id: int) -> None:
    """Scheduled job: generate and send digest for a source."""
    source = await repo.get_source(source_id)
    if not source or not source.is_active:
        return

    try:
        content = await generate_digest(source)
        if content is None:
            log.info("No new messages for %s, skipping digest", source.title)
            return

        # Send via bot
        from app.bot.create import create_bot
        bot = create_bot()
        owner_chat = await repo.get_setting("owner_chat_id")
        if not owner_chat:
            log.warning("No owner_chat_id set, digest stored but not sent")
            return

        parts = split_message(content)
        header = f"Digest: {source.title}\n\n"
        first_part = header + parts[0]
        try:
            await bot.send_message(int(owner_chat), first_part)
            for part in parts[1:]:
                await bot.send_message(int(owner_chat), part)

            digests = await repo.get_recent_digests(source_id, limit=1)
            if digests:
                await repo.mark_digest_sent(digests[0].id)
        except Exception:
            log.exception("Failed to send digest for %s", source.title)
        finally:
            await bot.session.close()

    except Exception:
        log.exception("Digest generation failed for %s", source.title)


def _parse_cron(expr: str, timezone: str | None = None) -> CronTrigger:
    tz = ZoneInfo(timezone or settings.timezone)
    parts = expr.split()
    # Convert crontab day_of_week (0=Sun) to APScheduler (0=Mon)
    dow = _convert_dow(parts[4])
    return CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=dow,
        timezone=tz,
    )


def _convert_dow(dow: str) -> str:
    """Convert crontab day_of_week (0/7=Sun) to APScheduler (0=Mon)."""
    if dow == "*":
        return dow
    cron_to_aps = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6}

    def convert_part(part: str) -> str:
        if "-" in part:
            start, end = part.split("-", 1)
            return f"{cron_to_aps[int(start)]}-{cron_to_aps[int(end)]}"
        return str(cron_to_aps[int(part)])

    return ",".join(convert_part(p) for p in dow.split(","))


async def setup_scheduler() -> AsyncIOScheduler:
    global scheduler
    scheduler = AsyncIOScheduler()

    # Collection job
    scheduler.add_job(
        _collect_job,
        IntervalTrigger(minutes=settings.collection_interval),
        id="collect_all",
        replace_existing=True,
    )

    # Digest jobs from DB
    configs = await repo.get_all_digest_configs()
    for config in configs:
        source = await repo.get_source(config.source_id)
        if not source or not source.is_active:
            continue
        try:
            trigger = _parse_cron(config.cron_expression, config.timezone)
            scheduler.add_job(
                _digest_job,
                trigger,
                id=f"digest_{config.source_id}",
                kwargs={"source_id": config.source_id},
                replace_existing=True,
            )
            log.info("Scheduled digest for %s: %s", source.title, config.cron_expression)
        except Exception:
            log.exception("Invalid cron for source %s: %s", source.title, config.cron_expression)

    scheduler.start()
    return scheduler


async def refresh_schedules() -> None:
    """Reload digest schedules from DB. Call after config changes."""
    if scheduler is None:
        return

    configs = await repo.get_all_digest_configs()
    active_ids = set()

    for config in configs:
        source = await repo.get_source(config.source_id)
        if not source or not source.is_active:
            continue
        job_id = f"digest_{config.source_id}"
        active_ids.add(job_id)
        try:
            trigger = _parse_cron(config.cron_expression, config.timezone)
            if scheduler.get_job(job_id):
                scheduler.reschedule_job(job_id, trigger=trigger)
            else:
                scheduler.add_job(
                    _digest_job,
                    trigger,
                    id=job_id,
                    kwargs={"source_id": config.source_id},
                    replace_existing=True,
                )
            log.info("Refreshed schedule for %s: %s", source.title, config.cron_expression)
        except Exception:
            log.exception("Invalid cron for source %s", source.title)

    # Remove jobs for deactivated/deleted sources
    for job in scheduler.get_jobs():
        if job.id.startswith("digest_") and job.id not in active_ids:
            scheduler.remove_job(job.id)
            log.info("Removed stale digest job %s", job.id)
