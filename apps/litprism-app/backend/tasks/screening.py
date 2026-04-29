import asyncio

from celery.exceptions import MaxRetriesExceededError

from tasks.celery_app import celery_app


def _exc_str(exc: BaseException) -> str:
    msg = str(exc)
    return msg if msg else repr(exc)


@celery_app.task
def screen_coordinator(screening_run_id: str) -> None:
    asyncio.run(_run_coordinator(screening_run_id))


async def _run_coordinator(screening_run_id: str) -> None:
    from datetime import UTC, datetime

    from db.engine import AsyncSessionLocal
    from db.models import ScreeningRun
    from services.screening import get_unscreened_articles

    async with AsyncSessionLocal() as db:
        run = await db.get(ScreeningRun, screening_run_id)
        if not run or run.status in ("completed", "cancelled"):
            return

        unscreened = await get_unscreened_articles(run.project_id, run.criteria_id, db)

        if not unscreened:
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            await db.commit()
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
        asyncio.run(_run_chunk(screening_run_id, article_ids))
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            asyncio.run(_write_chunk_tombstones(screening_run_id, article_ids, _exc_str(exc)))


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
        if not run or run.status in ("completed", "cancelled"):
            return

        criteria = await db.get(Criteria, run.criteria_id)
        project = await db.get(Project, run.project_id)

        # Idempotency: skip articles already screened under this criteria version.
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

        if not remaining_ids:
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
        results, errors = await screener.ascreen_batch(articles, screen_criteria, stage=run.stage)

        now = datetime.now(UTC)

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

        for error in errors:
            await write_tombstone(
                error.article_id,
                run.project_id,
                run.criteria_id,
                _exc_str(error.cause),
                db,
                screening_run_id=run.id,
            )

        run.screened_count = (run.screened_count or 0) + len(results) + len(errors)
        run.error_count = (run.error_count or 0) + len(errors)
        await db.commit()


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

        run.screened_count = (run.screened_count or 0) + len(remaining_ids)
        run.error_count = (run.error_count or 0) + len(remaining_ids)
        await db.commit()
