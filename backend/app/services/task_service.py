"""Single-process idempotent maintenance and automatic-analysis loops."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories import task_repository
from app.services import analysis_service

logger = logging.getLogger(__name__)


def run_event_reminder_scan(now: datetime | None = None) -> dict[str, int]:
    """Run one idempotent Event/Reminder state scan in a short transaction."""

    current = _utc_naive(now)
    with SessionLocal() as db:
        result = task_repository.maintain_events_and_reminders(db, current)
        db.commit()
        return result


def recover_stale_messages(now: datetime | None = None) -> list[int]:
    """Recover stale PROCESSING rows according to AI_PROCESSING_STALE_SECONDS."""

    settings = get_settings()
    current = _utc_naive(now)
    cutoff = current - timedelta(seconds=settings.ai_processing_stale_seconds)
    with SessionLocal() as db:
        ids = task_repository.recover_stale_processing(
            db,
            cutoff=cutoff,
            now=current,
        )
        db.commit()
        return ids


async def run_auto_analysis_scan(now: datetime | None = None) -> dict[str, int | bool]:
    """Analyze eligible current-user/channel windows without a durable queue."""

    settings = get_settings()
    recovered = len(recover_stale_messages(now))
    if not settings.ai_api_key.strip() or not settings.ai_default_model.strip():
        return {"recovered": recovered, "groups": 0, "messages": 0, "skipped": True}
    current = _utc_naive(now)
    wait_cutoff = current - timedelta(seconds=settings.ai_batch_max_wait_seconds)
    with SessionLocal() as db:
        groups = task_repository.eligible_pending_groups(
            db,
            size_threshold=settings.ai_batch_size_threshold,
            wait_cutoff=wait_cutoff,
        )
        db.rollback()
    processed_groups = 0
    processed_messages = 0
    for user_id, channel_id, count in groups:
        batch_limit = min(count, settings.ai_batch_size_threshold, 100)
        with SessionLocal() as db:
            ids = task_repository.pending_message_ids(
                db,
                user_id=user_id,
                channel_id=channel_id,
                limit=batch_limit,
            )
            db.rollback()
            if not ids:
                continue
            try:
                await analysis_service.analyze_batch(
                    db,
                    user_id=user_id,
                    message_ids=ids,
                    requested_model=settings.ai_default_model,
                    mode="retry",
                )
            except Exception:
                logger.exception(
                    "automatic analysis batch failed user_id=%s channel_id=%s",
                    user_id,
                    channel_id,
                )
                continue
        processed_groups += 1
        processed_messages += len(ids)
    return {
        "recovered": recovered,
        "groups": processed_groups,
        "messages": processed_messages,
        "skipped": False,
    }


async def periodic_event_reminder_loop() -> None:
    """Run Event/Reminder maintenance until application shutdown."""

    settings = get_settings()
    interval = min(
        settings.reminder_scan_interval_seconds,
        settings.event_status_scan_interval_seconds,
    )
    while True:
        try:
            await asyncio.to_thread(run_event_reminder_scan)
        except Exception:
            logger.exception("event/reminder maintenance scan failed")
        await asyncio.sleep(interval)


async def periodic_auto_analysis_loop() -> None:
    """Run automatic group-window analysis until application shutdown."""

    interval = get_settings().ai_batch_poll_seconds
    while True:
        try:
            await run_auto_analysis_scan()
        except Exception:
            logger.exception("automatic analysis scan failed")
        await asyncio.sleep(interval)


def _utc_naive(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        return current
    return current.astimezone(UTC).replace(tzinfo=None)
