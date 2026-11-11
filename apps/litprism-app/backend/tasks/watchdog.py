import asyncio
import logging

from tasks._async import run_async
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_STUCK_THRESHOLD_SECONDS = 180  # run must be running for > 3 min with empty queue


@celery_app.task
def watchdog() -> None:
    run_async(_run_watchdog())


def _in_flight_task_args() -> list[str]:
    """
    Stringified args of every task a worker has picked up (active) or prefetched (reserved).
    These are no longer in the Redis queue, so queue length alone can't see them.
    """
    inspector = celery_app.control.inspect(timeout=2.0)
    in_flight: list[str] = []
    for snapshot in (inspector.active(), inspector.reserved()):
        for tasks in (snapshot or {}).values():
            in_flight.extend(f"{t.get('name')} {t.get('args')}" for t in tasks)
    return in_flight


async def _run_watchdog() -> None:
    from datetime import UTC, datetime

    import redis as redis_lib
    from config import settings
    from db.engine import AsyncSessionLocal
    from db.models import Article, ScreeningRun
    from sqlalchemy import select

    r = redis_lib.from_url(settings.celery_broker_url)
    queue_len = r.llen("celery")
    # Blocking broadcast to workers — keep it off the event loop.
    in_flight = await asyncio.to_thread(_in_flight_task_args)

    async with AsyncSessionLocal() as db:
        # --- Stuck screening runs ---
        running_runs = (
            await db.scalars(select(ScreeningRun).where(ScreeningRun.status == "running"))
        ).all()

        for run in running_runs:
            # Only act if the run has been running long enough to be genuinely stuck
            anchor = run.resumed_at or run.started_at or run.created_at
            age_seconds = (datetime.now(UTC) - anchor.replace(tzinfo=UTC)).total_seconds()
            if age_seconds < _STUCK_THRESHOLD_SECONDS:
                continue

            if any(run.id in args for args in in_flight):
                continue

            if queue_len == 0:
                logger.warning(
                    "Watchdog: screening run %s stuck (running %ds, queue empty) — re-dispatching",
                    run.id,
                    age_seconds,
                )
                from tasks.screening import screen_coordinator

                screen_coordinator.delay(run.id)

        # --- Stuck fulltext retrieval ---
        pending_count = await db.scalar(
            select(Article.id)
            .where(Article.fulltext_status == "pending")
            .with_only_columns(Article.project_id)
            .distinct()
            .limit(1)
        )

        if pending_count is not None and queue_len == 0:
            # Find distinct projects with pending fulltext
            project_ids = (
                await db.scalars(
                    select(Article.project_id)
                    .where(Article.fulltext_status == "pending")
                    .distinct()
                )
            ).all()

            for project_id in project_ids:
                if any(
                    "retrieve_fulltext_task" in args and project_id in args for args in in_flight
                ):
                    continue
                logger.warning(
                    "Watchdog: fulltext retrieval stuck for project %s — re-dispatching",
                    project_id,
                )
                from tasks.fulltext import retrieve_fulltext_task

                retrieve_fulltext_task.delay(project_id)
