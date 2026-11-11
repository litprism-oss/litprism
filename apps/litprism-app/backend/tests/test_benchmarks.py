"""Built-in benchmark datasets: seeding, API and the Celery task logic."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from db.models import BenchmarkDataset, BenchmarkRecord, BenchmarkRun
from litprism.screen.models import ScreeningResult
from services.benchmarks import seed_datasets
from sqlalchemy import func, select


async def test_seed_is_idempotent_and_complete(db):
    first = await seed_datasets(db)
    assert first == 4
    assert await seed_datasets(db) == 0
    ds = (await db.execute(select(BenchmarkDataset))).scalars().all()
    assert len(ds) == first
    for d in ds:
        n = await db.scalar(
            select(func.count())
            .select_from(BenchmarkRecord)
            .where(BenchmarkRecord.dataset_id == d.id)
        )
        assert n == d.record_count == 150 and d.relevant_count >= 29


async def test_list_and_start_benchmark(client, db):
    await seed_datasets(db)
    listing = (await client.get("/benchmarks")).json()
    assert len(listing) == 4 and listing[0]["latest_run"] is None

    with patch("api.benchmarks.run_benchmark.delay") as delay:
        resp = await client.post(f"/benchmarks/{listing[0]['slug']}/run")
        assert resp.status_code == 202, resp.text
        delay.assert_called_once_with(resp.json()["id"])
        again = await client.post(f"/benchmarks/{listing[1]['slug']}/run")
        assert again.status_code == 409  # one at a time

    run = (await client.get(f"/benchmarks/runs/{resp.json()['id']}")).json()
    assert run["status"] == "pending" and run["total"] == 150


async def test_unknown_benchmark_is_404(client, db):
    await seed_datasets(db)
    assert (await client.post("/benchmarks/nope/run")).status_code == 404


async def test_task_scores_the_run(db):
    await seed_datasets(db)
    ds = (await db.execute(select(BenchmarkDataset).limit(1))).scalar_one()
    run = BenchmarkRun(dataset_id=ds.id, status="pending", total=ds.record_count)
    db.add(run)
    await db.commit()

    async def fake_batch(articles, criteria, stage):
        # Keeps every record that mentions "adults", excludes the rest.
        out = [
            ScreeningResult(
                article_id=a.id,
                decision="include" if "adults" in (a.abstract or "") else "exclude",
                confidence=0.9,
                reasoning="x",
                criteria_hits=[],
                model_used="fake-model",
                llm_provider="fake",
                stage="abstract",
                screened_at=datetime.now(UTC),
            )
            for a in articles
        ]
        return out, []

    screener = AsyncMock()
    screener.ascreen_batch = fake_batch
    from tasks import benchmark as task

    with (
        patch("litprism.screen.screener.Screener.from_env", return_value=screener),
        patch("db.engine.AsyncSessionLocal", return_value=_Ctx(db)),
    ):
        await task._run(run.id)

    await db.refresh(run)
    assert run.status == "completed", run.error
    assert run.processed == 150 and run.model_used == "fake-model"
    assert run.metrics["n"] == 150 and run.metrics["recall"] is not None
    assert run.metrics["kept"] + (run.metrics["n"] - run.metrics["kept"]) == 150
    assert len(run.metrics["missed_records"]) == min(10, run.metrics["missed"])


class _Ctx:
    """Lets the task reuse the test session instead of opening its own."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


async def test_seed_removes_datasets_that_are_no_longer_bundled(db):
    await seed_datasets(db)
    db.add(
        BenchmarkDataset(
            slug="old", name="Old", description="x", criteria={}, record_count=0, relevant_count=0
        )
    )
    await db.commit()
    await seed_datasets(db)
    slugs = set((await db.execute(select(BenchmarkDataset.slug))).scalars())
    assert "old" not in slugs and len(slugs) == 4


async def test_seed_refreshes_criteria_of_existing_datasets(db):
    await seed_datasets(db)
    ds = (await db.execute(select(BenchmarkDataset).limit(1))).scalar_one()
    ds.criteria = {"inclusion": ["stale"], "exclusion": []}
    await db.commit()
    await seed_datasets(db)
    await db.refresh(ds)
    assert ds.criteria["inclusion"] != ["stale"]
