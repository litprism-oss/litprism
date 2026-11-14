import contextlib
import logging

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.ext.asyncio import AsyncSession

from tasks._async import run_async
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _exc_str(exc: BaseException) -> str:
    msg = str(exc)
    return msg if msg else repr(exc)


@celery_app.task
def screen_coordinator(screening_run_id: str) -> None:
    run_async(_run_coordinator(screening_run_id))


# Coordinating is a few queries + dispatches; the TTL only matters if a worker dies holding it.
_COORDINATOR_LOCK_TTL_SECONDS = 60


def _coordinator_lock(screening_run_id: str):
    import redis as redis_lib
    from config import settings

    r = redis_lib.from_url(settings.celery_broker_url)
    return r.lock(
        f"litprism:screen-coordinator:{screening_run_id}",
        timeout=_COORDINATOR_LOCK_TTL_SECONDS,
    )


async def _run_coordinator(screening_run_id: str) -> None:
    """
    Two coordinators for the same run would each chunk the same unscreened set and
    screen every article twice — so only one may run at a time.
    """
    from redis.exceptions import LockError

    lock = _coordinator_lock(screening_run_id)
    if not lock.acquire(blocking=False):
        return
    try:
        await _dispatch_unscreened(screening_run_id)
    finally:
        with contextlib.suppress(LockError):  # expired under us — nothing to release
            lock.release()


async def _dispatch_unscreened(screening_run_id: str) -> None:
    from datetime import UTC, datetime

    from db.engine import AsyncSessionLocal
    from db.models import ScreeningRun
    from services.screening import get_unscreened_articles

    async with AsyncSessionLocal() as db:
        run = await db.get(ScreeningRun, screening_run_id)
        if not run or run.status in ("completed", "cancelled", "paused"):
            return

        if run.stage == "fulltext":
            from services.screening import get_fulltext_eligible_articles

            unscreened = await get_fulltext_eligible_articles(
                run.project_id, db, criteria_id=run.criteria_id
            )
        else:
            unscreened = await get_unscreened_articles(run.project_id, run.criteria_id, db)

        if not unscreened:
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            await db.commit()
            await _publish_complete(db, run)
            return

        now = datetime.now(UTC)
        if run.status == "pending":
            run.started_at = now
        else:
            run.resumed_at = now
        run.status = "running"
        await db.commit()

        chunk_size = run.chunk_size or 50
        chunks = [
            [a.id for a in unscreened[i : i + chunk_size]]
            for i in range(0, len(unscreened), chunk_size)
        ]

    for chunk_ids in chunks:
        screen_chunk.delay(screening_run_id, chunk_ids)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def screen_chunk(self, screening_run_id: str, article_ids: list[str]) -> None:
    try:
        run_async(_run_chunk(screening_run_id, article_ids))
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            run_async(_write_chunk_tombstones(screening_run_id, article_ids, _exc_str(exc)))


async def _run_chunk(screening_run_id: str, article_ids: list[str]) -> None:
    import uuid
    from datetime import UTC, datetime

    from db.engine import AsyncSessionLocal
    from db.models import Article, Criteria, Project, ScreeningResult, ScreeningRun
    from litprism.screen.criteria import Criteria as ScreenCriteria
    from litprism.screen.models import ReviewType as ScreenReviewType
    from litprism.screen.screener import Screener
    from services.screening import write_tombstone
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        run = await db.get(ScreeningRun, screening_run_id)
        if not run or run.status in ("completed", "cancelled", "paused"):
            return

        criteria = await db.get(Criteria, run.criteria_id)
        project = await db.get(Project, run.project_id)

        # Idempotency: skip articles already screened at this stage under this criteria version.
        already = set(
            (
                await db.scalars(
                    select(ScreeningResult.article_id)
                    .where(ScreeningResult.article_id.in_(article_ids))
                    .where(ScreeningResult.criteria_id == run.criteria_id)
                    .where(ScreeningResult.stage == run.stage)
                )
            ).all()
        )
        remaining_ids = [aid for aid in article_ids if aid not in already]

        if not remaining_ids:
            # Duplicate/late chunk: nothing to do, but the run may still need closing.
            await _maybe_complete_run(run.id, run.project_id, run.criteria_id, run.stage, db)
            return

        articles = list(
            (await db.scalars(select(Article).where(Article.id.in_(remaining_ids)))).all()
        )

        screen_criteria = ScreenCriteria(
            review_type=ScreenReviewType(project.review_type),
            inclusion=criteria.inclusion,
            exclusion=criteria.exclusion,
        )

        screener = Screener.from_env()

        if run.stage == "fulltext":
            screenable, no_fulltext = _prepare_fulltext_articles(articles)
        else:
            screenable, no_fulltext = articles, []

        results, errors = await screener.ascreen_batch(screenable, screen_criteria, stage=run.stage)

        now = datetime.now(UTC)
        decisions: list[tuple[str, str, float]] = []  # announced to the browser after the commit
        failures: list[tuple[str, str]] = []

        # Write immediate uncertain results for articles with no full text.
        for article in no_fulltext:
            model_used = (
                screener._config.azure_deployment  # type: ignore[attr-defined]
                if hasattr(screener._config, "azure_deployment")
                else screener._config.model  # type: ignore[union-attr]
            )
            db.add(
                ScreeningResult(
                    id=str(uuid.uuid4()),
                    article_id=article.id,
                    project_id=run.project_id,
                    criteria_id=run.criteria_id,
                    screening_run_id=run.id,
                    stage="fulltext",
                    decision="uncertain",
                    confidence=0.0,
                    reasoning="No full text available for screening.",
                    criteria_hits=[],
                    model_used=model_used,
                    llm_provider=screener._config.provider,  # type: ignore[union-attr]
                    screened_at=now,
                )
            )
            decisions.append((article.id, "uncertain", 0.0))

        for result in results:
            db.add(
                ScreeningResult(
                    id=str(uuid.uuid4()),
                    article_id=result.article_id,
                    project_id=run.project_id,
                    criteria_id=run.criteria_id,
                    screening_run_id=run.id,
                    stage=result.stage,
                    decision=result.decision,
                    confidence=result.confidence,
                    reasoning=result.reasoning,
                    criteria_hits=[h.model_dump() for h in result.criteria_hits],
                    model_used=result.model_used,
                    llm_provider=result.llm_provider,
                    screened_at=now,
                )
            )
            decisions.append((result.article_id, result.decision, result.confidence))

        from litellm import ContentPolicyViolationError

        policy_errors = [e for e in errors if isinstance(e.cause, ContentPolicyViolationError)]
        real_errors = [e for e in errors if not isinstance(e.cause, ContentPolicyViolationError)]

        # Content policy violations are deterministic — route to uncertain instead of error.
        policy_reasoning = (
            "Full text flagged by content filter — needs manual review."
            if run.stage == "fulltext"
            else "Abstract flagged by content filter — routed to full-text review."
        )
        for error in policy_errors:
            db.add(
                ScreeningResult(
                    id=str(uuid.uuid4()),
                    article_id=error.article_id,
                    project_id=run.project_id,
                    criteria_id=run.criteria_id,
                    screening_run_id=run.id,
                    stage=run.stage,
                    decision="uncertain",
                    confidence=0.0,
                    reasoning=policy_reasoning,
                    criteria_hits=[],
                    model_used="content-filter",
                    llm_provider=screener._config.provider,  # type: ignore[union-attr]
                    screened_at=now,
                )
            )
            decisions.append((error.article_id, "uncertain", 0.0))

        for error in real_errors:
            await write_tombstone(
                error.article_id,
                run.project_id,
                run.criteria_id,
                _exc_str(error.cause),
                db,
                screening_run_id=run.id,
            )
            failures.append((error.article_id, type(error.cause).__name__))

        done = len(results) + len(errors) + len(no_fulltext)
        processed_after = await _add_progress(db, run.id, done=done, failed=len(real_errors))
        _publish_progress(run, processed_after, decisions, failures)

        # Mark run completed if no articles remain unscreened.
        await _maybe_complete_run(run.id, run.project_id, run.criteria_id, run.stage, db)


async def _add_progress(db: AsyncSession, run_id: str, *, done: int, failed: int) -> int:
    """Add to the run's counters in SQL, commit, and return the run's new screened_count.

    Chunks run concurrently and each loaded the run long before it finishes. Writing back
    `loaded value + n` would drop whatever the other chunks added meanwhile. The returned value
    is this chunk's own share of the total, so concurrent chunks report disjoint ranges.
    """
    from db.models import ScreeningRun
    from sqlalchemy import func, update

    new_count = await db.scalar(
        update(ScreeningRun)
        .where(ScreeningRun.id == run_id)
        .values(
            screened_count=func.coalesce(ScreeningRun.screened_count, 0) + done,
            error_count=func.coalesce(ScreeningRun.error_count, 0) + failed,
        )
        .returning(ScreeningRun.screened_count)
    )
    await db.commit()
    return new_count or 0


def _publish_progress(
    run, processed_after: int, decisions: list[tuple[str, str, float]], failures: list
) -> None:
    """Tell the browsers watching this project about a finished chunk (best effort)."""
    from services.events import progress_events, publish_events

    done = len(decisions) + len(failures)
    publish_events(
        run.project_id,
        progress_events(
            processed_before=processed_after - done,
            total=run.total_articles or 0,
            decisions=decisions,
            errors=failures,
        ),
    )


async def _publish_complete(db: AsyncSession, run) -> None:
    """Announce a finished run with its decision counts. Never fails the task: the run is
    already marked completed, and a retry would only repeat the work."""
    try:
        from db.models import ScreeningResult
        from services.events import complete_event, publish_events
        from sqlalchemy import func, select

        # _add_progress updated the counters in SQL, so this object's copy is expired; reading
        # it lazily would fail in an async session. Load it explicitly.
        await db.refresh(run)
        rows = (
            await db.execute(
                select(ScreeningResult.decision, func.count())
                .where(ScreeningResult.screening_run_id == run.id)
                .group_by(ScreeningResult.decision)
            )
        ).all()
        counts = {decision: count for decision, count in rows}
        publish_events(
            run.project_id,
            [complete_event(total_processed=run.screened_count or 0, counts=counts)],
        )
    except Exception:  # noqa: BLE001
        logger.warning("Could not announce completion of run %s", run.id, exc_info=True)


async def _maybe_complete_run(
    run_id: str,
    project_id: str,
    criteria_id: str,
    stage: str,
    db: AsyncSession,
) -> None:
    """Mark the run completed if no unscreened articles remain."""
    from datetime import UTC, datetime

    from db.models import ScreeningRun
    from services.screening import get_fulltext_eligible_articles, get_unscreened_articles

    if stage == "fulltext":
        remaining = await get_fulltext_eligible_articles(project_id, db, criteria_id=criteria_id)
    else:
        remaining = await get_unscreened_articles(project_id, criteria_id, db)

    if remaining:
        return

    run = await db.get(ScreeningRun, run_id)
    if run and run.status == "running":
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        await db.commit()
        await _publish_complete(db, run)


# ~15k tokens; keeps a single paper from blowing the model's context window.
_FULLTEXT_MAX_CHARS = 60_000


def _prepare_fulltext_articles(
    articles: list,
) -> tuple[list, list]:
    """
    Split articles into (screenable, no_fulltext).
    Screenable articles are wrapped so their abstract == fulltext_text, truncated to
    _FULLTEXT_MAX_CHARS.
    """
    from dataclasses import dataclass

    @dataclass
    class _FulltextAdapter:
        id: str
        title: str
        abstract: str | None

    screenable = []
    no_fulltext = []
    for a in articles:
        if a.fulltext_text:
            text = a.fulltext_text[:_FULLTEXT_MAX_CHARS]
            screenable.append(_FulltextAdapter(id=a.id, title=a.title, abstract=text))
        else:
            no_fulltext.append(a)
    return screenable, no_fulltext


async def _write_chunk_tombstones(
    screening_run_id: str, article_ids: list[str], cause: str
) -> None:
    """
    Writes tombstones for all unscreened articles in a chunk after max retries are exceeded.
    Skips articles that already have a result (idempotent).
    """
    from db.engine import AsyncSessionLocal
    from db.models import ScreeningResult, ScreeningRun
    from services.screening import write_tombstone
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        run = await db.get(ScreeningRun, screening_run_id)
        if not run:
            return

        already = set(
            (
                await db.scalars(
                    select(ScreeningResult.article_id)
                    .where(ScreeningResult.article_id.in_(article_ids))
                    .where(ScreeningResult.criteria_id == run.criteria_id)
                )
            ).all()
        )
        remaining_ids = [aid for aid in article_ids if aid not in already]

        for article_id in remaining_ids:
            await write_tombstone(
                article_id,
                run.project_id,
                run.criteria_id,
                cause,
                db,
                screening_run_id=run.id,
            )

        processed_after = await _add_progress(
            db, run.id, done=len(remaining_ids), failed=len(remaining_ids)
        )
        _publish_progress(run, processed_after, [], [(aid, "ChunkFailed") for aid in remaining_ids])
