from tasks._async import run_async
from tasks.celery_app import celery_app


@celery_app.task
def run_benchmark(run_id: str) -> None:
    run_async(_run(run_id))


async def _run(run_id: str) -> None:
    from datetime import UTC, datetime

    from db.engine import AsyncSessionLocal
    from db.models import BenchmarkDataset, BenchmarkRecord, BenchmarkRun
    from litprism.screen.criteria import Criteria
    from litprism.screen.screener import Screener
    from services.benchmarks import CHUNK, as_article, score
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        run = await db.get(BenchmarkRun, run_id)
        if run is None or run.status not in ("pending", "running"):
            return
        try:
            ds = await db.get(BenchmarkDataset, run.dataset_id)
            records = list(
                (
                    await db.execute(
                        select(BenchmarkRecord).where(BenchmarkRecord.dataset_id == ds.id)
                    )
                ).scalars()
            )
            screener = Screener.from_env()
            criteria = Criteria(
                inclusion=ds.criteria["inclusion"], exclusion=ds.criteria["exclusion"]
            )
            run.status, run.total, run.processed = "running", len(records), 0
            await db.commit()

            results, error_count = [], 0
            for i in range(0, len(records), CHUNK):
                chunk = records[i : i + CHUNK]
                res, errs = await screener.ascreen_batch(
                    [as_article(r) for r in chunk], criteria, stage="abstract"
                )
                results.extend(res)
                error_count += len(errs)
                run.processed = min(i + CHUNK, len(records))
                await db.commit()

            if results:
                run.model_used = results[0].model_used
            run.metrics = score(
                results,
                {r.id: r.label for r in records},
                error_count,
                {r.id: r.title for r in records},
            )
            run.status = "completed"
        except Exception as exc:  # noqa: BLE001 - surface any failure on the run
            run.status = "failed"
            run.error = (str(exc) or repr(exc))[:500]
        run.completed_at = datetime.now(UTC)
        await db.commit()
