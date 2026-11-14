"""
End-to-end screening flow: real API routes + real Celery task bodies, run in-process.

Only the edges are faked:
- the LLM (Screener.from_env) — decisions are driven by markers in title / full text
- Celery dispatch (.delay) — calls are queued and drained by `Harness.drain()`
- the Redis coordinator lock — an in-memory equivalent

Everything else (routes, coordinator, chunks, completion, eligibility, PRISMA counts)
is the production code path against a shared in-memory SQLite DB.
"""

import asyncio
import json
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from db.engine import get_db
from db.models import Article, Base, ScreeningResult, ScreeningRun
from httpx import ASGITransport, AsyncClient
from litellm import ContentPolicyViolationError
from litprism.screen import ScreeningResult as ScreenResult
from litprism.screen.exceptions import ScreeningError
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tasks.screening import _run_chunk, _run_coordinator, _write_chunk_tombstones
from tasks.watchdog import _run_watchdog

from main import app

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _decide(article, stage: str) -> str | None:
    """Title markers drive abstract decisions; full-text markers drive full-text ones."""
    text = (article.abstract or "") if stage == "fulltext" else article.title
    for marker, decision in (("EXC", "exclude"), ("INC", "include"), ("UNC", "uncertain")):
        if f"{'FT-' if stage == 'fulltext' else ''}{marker}" in text:
            return decision
    return None  # "BLOCK" → content-policy error


class FakeScreener:
    _config = SimpleNamespace(provider="openai", model="fake-model")

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []  # (article_id, stage)

    async def ascreen_batch(self, articles, criteria, stage="abstract"):
        results, errors = [], []
        for a in articles:
            self.calls.append((a.id, stage))
            if "ERR" in a.title:  # a real provider failure, unlike BLOCK (a content-policy hit)
                cause = RuntimeError("provider exploded: key sk-secret-123")
                errors.append(ScreeningError(article_id=a.id, cause=cause))
                continue
            decision = _decide(a, stage)
            if decision is None:
                cause = ContentPolicyViolationError(
                    message="blocked", model="fake-model", llm_provider="openai"
                )
                errors.append(ScreeningError(article_id=a.id, cause=cause))
                continue
            results.append(
                ScreenResult(
                    article_id=a.id,
                    decision=decision,
                    confidence=0.9,
                    reasoning=f"fake {decision}",
                    criteria_hits=[],
                    stage=stage,
                    model_used="fake-model",
                    llm_provider="openai",
                    screened_at=datetime.now(UTC),
                )
            )
        return results, errors


class FakeLock:
    held: set[str] = set()

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    def acquire(self, blocking: bool = False) -> bool:
        if self.run_id in FakeLock.held:
            return False
        FakeLock.held.add(self.run_id)
        return True

    def release(self) -> None:
        FakeLock.held.discard(self.run_id)


class Harness:
    """Captures .delay() calls and runs them in-process on demand."""

    def __init__(self, client: AsyncClient, factory, screener: FakeScreener) -> None:
        self.client = client
        self.factory = factory
        self.screener = screener
        self.queue: deque[tuple[str, tuple]] = deque()

    def enqueue_coordinator(self, run_id: str) -> None:
        self.queue.append(("coordinator", (run_id,)))

    def enqueue_chunk(self, run_id: str, article_ids: list[str]) -> None:
        self.queue.append(("chunk", (run_id, list(article_ids))))

    async def step(self) -> None:
        kind, args = self.queue.popleft()
        if kind == "coordinator":
            await _run_coordinator(*args)
        else:
            await _run_chunk(*args)

    async def drain(self) -> None:
        while self.queue:
            await self.step()

    async def run(self, run_id: str) -> ScreeningRun:
        async with self.factory() as s:
            return await s.get(ScreeningRun, run_id)

    async def result_rows(self, stage: str) -> list[ScreeningResult]:
        async with self.factory() as s:
            return list(
                await s.scalars(select(ScreeningResult).where(ScreeningResult.stage == stage))
            )

    async def max_rows_per_article(self, stage: str) -> int:
        async with self.factory() as s:
            counts = (
                await s.scalars(
                    select(func.count())
                    .where(ScreeningResult.stage == stage)
                    .group_by(ScreeningResult.article_id)
                )
            ).all()
        return max(counts, default=0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def harness(seed_test_users):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record) -> None:  # Postgres always does
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed_test_users(session)

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    screener = FakeScreener()
    FakeLock.held.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        h = Harness(client, factory, screener)
        with (
            patch("db.engine.AsyncSessionLocal", factory),
            patch("litprism.screen.screener.Screener.from_env", return_value=screener),
            patch("tasks.screening._coordinator_lock", side_effect=FakeLock),
            patch("api.screening.screen_coordinator.delay", side_effect=h.enqueue_coordinator),
            patch("tasks.screening.screen_coordinator.delay", side_effect=h.enqueue_coordinator),
            patch("tasks.screening.screen_chunk.delay", side_effect=h.enqueue_chunk),
        ):
            yield h

    app.dependency_overrides.clear()
    await engine.dispose()


async def _project_with_criteria(h: Harness) -> tuple[str, str]:
    project = await h.client.post(
        "/projects", json={"name": "E2E Project", "review_type": "systematic"}
    )
    project_id = project.json()["id"]
    criteria = await h.client.post(
        f"/projects/{project_id}/criteria",
        json={"inclusion": ["RCT"], "exclusion": ["Animal study"]},
    )
    return project_id, criteria.json()["id"]


async def _add_articles(h: Harness, project_id: str, titles: list[str]) -> dict[str, str]:
    """Returns {title: article_id}."""
    ids = {}
    async with h.factory() as s:
        for i, title in enumerate(titles):
            a = Article(
                id=str(uuid.uuid4()),
                project_id=project_id,
                title=title,
                abstract=f"Abstract for {title}",
                source="upload",
                authors=[],
                created_at=datetime.now(UTC) + timedelta(seconds=i),
            )
            s.add(a)
            ids[title] = a.id
        await s.commit()
    return ids


async def _retrieve_fulltext(h: Harness, texts: dict[str, str | None]) -> None:
    """Simulates the retrieval pipeline: {article_id: text or None for unavailable}."""
    async with h.factory() as s:
        for article_id, text in texts.items():
            a = await s.get(Article, article_id)
            a.fulltext_status = "retrieved" if text else "unavailable"
            a.fulltext_text = text
        await s.commit()


# ---------------------------------------------------------------------------
# Full flow
# ---------------------------------------------------------------------------


async def test_abstract_then_fulltext_flow_updates_prisma(harness):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    ids = await _add_articles(
        h, project_id, ["INC one", "INC two", "EXC three", "UNC four", "UNC five", "BLOCK six"]
    )

    # PRISMA before anything is screened.
    prisma = (await h.client.get(f"/projects/{project_id}/prisma-counts")).json()
    assert prisma["records_screened"] == 0
    assert prisma["fulltext_assessed"] is None

    # --- Abstract screening ---------------------------------------------------
    resp = await h.client.post(
        f"/projects/{project_id}/screening/run", json={"stage": "abstract", "chunk_size": 2}
    )
    assert resp.status_code == 202
    abstract_run_id = resp.json()["id"]
    await h.drain()

    run = await h.run(abstract_run_id)
    assert run.status == "completed"
    assert run.screened_count == 6
    assert run.error_count == 0  # content-policy hit is uncertain, not an error

    blocked = next(r for r in await h.result_rows("abstract") if r.article_id == ids["BLOCK six"])
    assert blocked.decision == "uncertain"
    assert blocked.llm_provider == "openai"  # configured provider, not hardcoded "azure"
    assert "routed to full-text review" in blocked.reasoning

    prisma = (await h.client.get(f"/projects/{project_id}/prisma-counts")).json()
    assert prisma["records_screened"] == 6
    assert prisma["excluded_screening"] == 1
    assert prisma["uncertain"] == 3
    assert prisma["studies_included"] == 2
    assert prisma["fulltext_assessed"] is None  # Eligibility row still pending

    # --- Full-text retrieval (simulated) -------------------------------------
    await _retrieve_fulltext(
        h,
        {
            ids["UNC four"]: "Full paper ... FT-INC ...",
            ids["UNC five"]: "Full paper ... FT-EXC ...",
            ids["BLOCK six"]: None,  # unavailable
        },
    )
    elig = (await h.client.get(f"/projects/{project_id}/screening/fulltext-eligibility")).json()
    assert elig == {"eligible": 2, "uncertain_total": 3, "retrieved": 2, "unavailable": 1}

    # --- Full-text screening -------------------------------------------------
    resp = await h.client.post(f"/projects/{project_id}/screening/fulltext-run", json={})
    assert resp.status_code == 202
    ft_run_id = resp.json()["id"]
    assert resp.json()["total_articles"] == 2
    await h.drain()

    ft_run = await h.run(ft_run_id)
    assert ft_run.status == "completed"
    assert ft_run.screened_count == 2
    assert {(aid, stage) for aid, stage in h.screener.calls if stage == "fulltext"} == {
        (ids["UNC four"], "fulltext"),
        (ids["UNC five"], "fulltext"),
    }

    prisma = (await h.client.get(f"/projects/{project_id}/prisma-counts")).json()
    assert prisma["fulltext_assessed"] == 2
    assert prisma["fulltext_excluded"] == 1
    assert prisma["studies_included"] == 3  # 2 abstract + 1 full-text

    # A second full-text run has nothing left to do.
    resp = await h.client.post(f"/projects/{project_id}/screening/fulltext-run", json={})
    assert resp.status_code == 409

    assert await h.max_rows_per_article("abstract") == 1
    assert await h.max_rows_per_article("fulltext") == 1


async def test_fulltext_prompt_is_capped(harness):
    from tasks.screening import _FULLTEXT_MAX_CHARS

    h = harness
    project_id, _ = await _project_with_criteria(h)
    ids = await _add_articles(h, project_id, ["UNC long"])
    await h.client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    await h.drain()
    await _retrieve_fulltext(h, {ids["UNC long"]: "FT-INC " + "x" * (_FULLTEXT_MAX_CHARS * 2)})

    seen: list[int] = []
    original = h.screener.ascreen_batch

    async def spy(articles, criteria, stage="abstract"):
        seen.extend(len(a.abstract) for a in articles)
        return await original(articles, criteria, stage)

    h.screener.ascreen_batch = spy
    await h.client.post(f"/projects/{project_id}/screening/fulltext-run", json={})
    await h.drain()

    assert seen == [_FULLTEXT_MAX_CHARS]


# ---------------------------------------------------------------------------
# Pause / resume / duplicates
# ---------------------------------------------------------------------------


async def test_pause_midway_then_resume_finishes_without_duplicates(harness):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    await _add_articles(h, project_id, [f"INC {i}" for i in range(6)])

    resp = await h.client.post(
        f"/projects/{project_id}/screening/run", json={"stage": "abstract", "chunk_size": 2}
    )
    run_id = resp.json()["id"]

    await h.step()  # coordinator → 3 chunks queued
    assert len(h.queue) == 3
    await h.step()  # first chunk screens 2 articles

    resp = await h.client.post(f"/projects/{project_id}/screening/runs/{run_id}/cancel")
    assert resp.json()["status"] == "paused"
    await h.drain()  # remaining chunks see "paused" and bail

    run = await h.run(run_id)
    assert run.status == "paused"
    assert run.screened_count == 2

    # Resume through the "Start screening" endpoint (previously a silent no-op).
    resp = await h.client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    assert resp.status_code == 202
    assert resp.json()["id"] == run_id
    await h.drain()

    run = await h.run(run_id)
    assert run.status == "completed"
    assert run.screened_count == 6
    assert await h.max_rows_per_article("abstract") == 1


async def test_resumed_fulltext_run_only_requeues_unscreened(harness):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    titles = [f"UNC {i}" for i in range(4)]
    ids = await _add_articles(h, project_id, titles)
    await h.client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    await h.drain()
    await _retrieve_fulltext(h, {aid: "FT-INC" for aid in ids.values()})

    resp = await h.client.post(
        f"/projects/{project_id}/screening/fulltext-run", json={"chunk_size": 2}
    )
    run_id = resp.json()["id"]
    await h.step()  # coordinator → 2 chunks
    await h.step()  # first chunk screens 2
    await h.client.post(f"/projects/{project_id}/screening/runs/{run_id}/cancel")
    await h.drain()

    await h.client.post(f"/projects/{project_id}/screening/runs/{run_id}/resume")
    await h.step()  # coordinator on resume
    queued = [args[1] for kind, args in h.queue if kind == "chunk"]
    assert len(queued) == 1 and len(queued[0]) == 2  # only the 2 still unscreened

    await h.drain()
    run = await h.run(run_id)
    assert run.status == "completed"
    assert run.screened_count == 4
    assert await h.max_rows_per_article("fulltext") == 1


async def test_running_run_is_not_redispatched(harness):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    await _add_articles(h, project_id, ["INC a", "INC b"])

    resp = await h.client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    run_id = resp.json()["id"]
    await h.step()  # coordinator → status running, chunk queued
    queued = len(h.queue)

    again = await h.client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    resume = await h.client.post(f"/projects/{project_id}/screening/runs/{run_id}/resume")

    assert again.status_code == 202
    assert resume.status_code == 409
    assert len(h.queue) == queued  # nothing new dispatched

    await h.drain()
    assert (await h.run(run_id)).status == "completed"


async def test_concurrent_coordinator_is_blocked_by_lock(harness):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    await _add_articles(h, project_id, ["INC a", "INC b"])
    resp = await h.client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    run_id = resp.json()["id"]
    h.queue.clear()

    FakeLock.held.add(run_id)  # another coordinator is mid-dispatch
    await _run_coordinator(run_id)
    assert not h.queue

    FakeLock.held.clear()
    await _run_coordinator(run_id)
    assert len(h.queue) == 1


async def test_late_duplicate_chunk_after_completion_is_harmless(harness):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    ids = await _add_articles(h, project_id, ["INC a", "INC b"])
    resp = await h.client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    run_id = resp.json()["id"]
    await h.drain()

    await _run_chunk(run_id, list(ids.values()))  # e.g. a Celery retry arriving late

    run = await h.run(run_id)
    assert run.status == "completed"
    assert run.screened_count == 2
    assert await h.max_rows_per_article("abstract") == 1


async def test_duplicate_fulltext_chunk_closes_run(harness):
    """A run whose last chunk is all-duplicates must still complete (used to hang 'running')."""
    h = harness
    project_id, _ = await _project_with_criteria(h)
    ids = await _add_articles(h, project_id, ["UNC a"])
    await h.client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    await h.drain()
    await _retrieve_fulltext(h, {ids["UNC a"]: "FT-INC"})

    resp = await h.client.post(f"/projects/{project_id}/screening/fulltext-run", json={})
    run_id = resp.json()["id"]
    await h.step()  # coordinator → running, chunk queued

    # Another worker wrote the result, then died before it could close the run.
    async with h.factory() as s:
        run = await s.get(ScreeningRun, run_id)
        s.add(
            ScreeningResult(
                id=str(uuid.uuid4()),
                article_id=ids["UNC a"],
                project_id=project_id,
                criteria_id=run.criteria_id,
                screening_run_id=run_id,
                stage="fulltext",
                decision="include",
                confidence=0.9,
                reasoning="",
                criteria_hits=[],
                model_used="fake-model",
                llm_provider="openai",
                screened_at=datetime.now(UTC),
            )
        )
        await s.commit()
    assert (await h.run(run_id)).status == "running"

    await h.drain()  # the queued chunk is all-duplicates — it must still close the run
    assert (await h.run(run_id)).status == "completed"
    assert await h.max_rows_per_article("fulltext") == 1


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------


async def _stale_running_run(h: Harness) -> str:
    project_id, _ = await _project_with_criteria(h)
    await _add_articles(h, project_id, ["INC a"])
    resp = await h.client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    run_id = resp.json()["id"]
    h.queue.clear()
    async with h.factory() as s:
        run = await s.get(ScreeningRun, run_id)
        run.status = "running"
        run.started_at = datetime.now(UTC) - timedelta(minutes=10)
        await s.commit()
    return run_id


@pytest.mark.parametrize(
    ("queue_len", "in_flight_for_run", "expect_redispatch"),
    [
        (0, False, True),  # genuinely stuck
        (0, True, False),  # worker is mid-chunk — queue empty but not stuck
        (3, False, False),  # work still queued
    ],
)
async def test_watchdog_redispatch_decision(
    harness, queue_len, in_flight_for_run, expect_redispatch
):
    h = harness
    run_id = await _stale_running_run(h)
    redis_client = MagicMock()
    redis_client.llen.return_value = queue_len
    in_flight = [f"tasks.screening.screen_chunk ['{run_id}', ['a']]"] if in_flight_for_run else []

    with (
        patch("redis.from_url", return_value=redis_client),
        patch("tasks.watchdog._in_flight_task_args", return_value=in_flight),
    ):
        await _run_watchdog()

    assert (list(h.queue) == [("coordinator", (run_id,))]) is expect_redispatch
    if expect_redispatch:
        await h.drain()
        assert (await h.run(run_id)).status == "completed"


# ---------------------------------------------------------------------------
# Live progress: what the worker tells the browser while a run is processed
# ---------------------------------------------------------------------------


def _flat(published) -> list[dict]:
    return [event for _, events in published for event in events]


async def _start_run(h: Harness, project_id: str, **body) -> str:
    resp = await h.client.post(f"/projects/{project_id}/screening/run", json=body)
    assert resp.status_code == 202, resp.text
    return resp.json()["id"]


async def test_a_run_announces_every_article_and_then_its_completion(harness, published_events):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    ids = await _add_articles(h, project_id, ["INC a", "INC b", "EXC c", "UNC d", "BLOCK e"])
    await _start_run(h, project_id, stage="abstract", chunk_size=2)
    await h.drain()

    events = _flat(published_events)
    progress = [e for e in events if e["event"] == "screening_progress"]
    assert sorted(e["processed"] for e in progress) == [1, 2, 3, 4, 5]
    assert {e["total"] for e in progress} == {5}
    decisions = {e["article_id"]: e["decision"] for e in progress}
    assert decisions == {
        ids["INC a"]: "include",
        ids["INC b"]: "include",
        ids["EXC c"]: "exclude",
        ids["UNC d"]: "uncertain",
        ids["BLOCK e"]: "uncertain",  # a content-policy hit is routed to review, not an error
    }
    assert [e for e in events if e["event"] == "screening_complete"] == [
        {
            "event": "screening_complete",
            "total_processed": 5,
            "included": 2,
            "excluded": 1,
            "uncertain": 2,
        }
    ]
    assert events[-1]["event"] == "screening_complete"  # and it comes last
    assert {pid for pid, _ in published_events} == {project_id}


async def test_failed_articles_are_announced_without_provider_details(harness, published_events):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    ids = await _add_articles(h, project_id, ["INC ok", "ERR bad"])
    run_id = await _start_run(h, project_id, stage="abstract")
    await h.drain()

    events = _flat(published_events)
    progress = {e["article_id"]: e for e in events if e["event"] == "screening_progress"}
    assert progress[ids["ERR bad"]]["decision"] == "error"
    assert max(e["processed"] for e in progress.values()) == 2  # errors advance the count too
    errors = [e for e in events if e["event"] == "screening_error"]
    assert errors == [
        {
            "event": "screening_error",
            "article_id": ids["ERR bad"],
            "message": "Screening failed (RuntimeError)",
        }
    ]
    assert "sk-secret" not in json.dumps(events)  # the provider's message never reaches a browser
    done = next(e for e in events if e["event"] == "screening_complete")
    assert (done["included"], done["excluded"], done["uncertain"]) == (1, 0, 0)  # errors excluded
    assert (await h.run(run_id)).error_count == 1


async def test_concurrent_chunks_neither_lose_progress_nor_report_overlapping_counts(
    harness, published_events
):
    """Two worker processes finish chunks at the same time. Each loaded the run at the start;
    writing back `loaded + n` used to make one overwrite the other (screened_count 2, not 4)."""
    h = harness
    project_id, _ = await _project_with_criteria(h)
    await _add_articles(h, project_id, ["INC a", "INC b", "INC c", "INC d"])
    run_id = await _start_run(h, project_id, stage="abstract", chunk_size=2)
    await h.step()  # the coordinator queues two chunks
    chunks = [args for kind, args in h.queue if kind == "chunk"]
    h.queue.clear()
    assert len(chunks) == 2

    await asyncio.gather(*(_run_chunk(*args) for args in chunks))

    assert (await h.run(run_id)).screened_count == 4
    progress = [e for e in _flat(published_events) if e["event"] == "screening_progress"]
    assert sorted(e["processed"] for e in progress) == [1, 2, 3, 4]  # disjoint, nothing repeated


async def test_a_chunk_that_exhausted_its_retries_is_announced_as_failed(harness, published_events):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    ids = await _add_articles(h, project_id, ["INC a", "INC b"])
    run_id = await _start_run(h, project_id, stage="abstract")
    await h.step()  # coordinator: the run is now running and its chunk is queued
    h.queue.clear()

    await _write_chunk_tombstones(run_id, list(ids.values()), "boom")

    events = _flat(published_events)
    assert [e["decision"] for e in events if e["event"] == "screening_progress"] == ["error"] * 2
    assert {e["message"] for e in events if e["event"] == "screening_error"} == {
        "Screening failed (ChunkFailed)"
    }
    run = await h.run(run_id)
    assert (run.screened_count, run.error_count) == (2, 2)
    assert "boom" not in json.dumps(events)


async def test_a_late_duplicate_chunk_announces_nothing(harness, published_events):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    ids = await _add_articles(h, project_id, ["INC a", "EXC b"])
    run_id = await _start_run(h, project_id, stage="abstract")
    await h.drain()
    published_events.clear()

    await _run_chunk(run_id, list(ids.values()))

    assert published_events == []


async def test_a_run_with_nothing_to_screen_still_announces_completion(harness, published_events):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    await _add_articles(h, project_id, ["INC a"])
    await _start_run(h, project_id, stage="abstract")
    await h.drain()
    published_events.clear()

    again = await _start_run(h, project_id, stage="abstract")  # nothing left to screen
    await h.drain()

    complete = [e for e in _flat(published_events) if e["event"] == "screening_complete"]
    assert len(complete) == 1
    assert (await h.run(again)).status == "completed"


async def test_fulltext_runs_announce_progress_too(harness, published_events):
    h = harness
    project_id, _ = await _project_with_criteria(h)
    ids = await _add_articles(h, project_id, ["UNC four", "UNC five", "UNC six"])
    await _start_run(h, project_id, stage="abstract")
    await h.drain()
    await _retrieve_fulltext(
        h,
        {
            ids["UNC four"]: "Full paper ... FT-INC ...",
            ids["UNC five"]: "Full paper ... FT-EXC ...",
            ids["UNC six"]: "Full paper ... FT-INC ...",
        },
    )
    published_events.clear()

    resp = await h.client.post(f"/projects/{project_id}/screening/fulltext-run", json={})
    assert resp.status_code == 202
    await h.drain()

    events = _flat(published_events)
    progress = [e for e in events if e["event"] == "screening_progress"]
    assert sorted(e["processed"] for e in progress) == [1, 2, 3]
    assert {e["total"] for e in progress} == {3}
    assert {e["article_id"]: e["decision"] for e in progress} == {
        ids["UNC four"]: "include",
        ids["UNC five"]: "exclude",
        ids["UNC six"]: "include",
    }
    done = next(e for e in events if e["event"] == "screening_complete")
    assert (done["included"], done["excluded"]) == (2, 1)
