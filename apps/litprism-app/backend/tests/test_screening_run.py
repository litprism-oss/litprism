import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from db.models import Article, ScreeningResult, ScreeningRun
from db.models import Criteria as DBCriteria
from services.screening import (
    get_fulltext_eligible_articles,
    get_unscreened_articles,
    write_tombstone,
)
from tasks.screening import (
    _FULLTEXT_MAX_CHARS,
    _maybe_complete_run,
    _prepare_fulltext_articles,
    _run_coordinator,
)
from tasks.watchdog import _in_flight_task_args

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_article(project_id: str, idx: int = 0) -> Article:
    return Article(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=f"Test Article {idx}",
        source="pubmed",
        authors=[],
        created_at=datetime.now(UTC),
    )


def _make_screening_result(article_id: str, project_id: str, criteria_id: str) -> ScreeningResult:
    return ScreeningResult(
        id=str(uuid.uuid4()),
        article_id=article_id,
        project_id=project_id,
        criteria_id=criteria_id,
        stage="abstract",
        decision="include",
        confidence=0.95,
        reasoning="Meets criteria.",
        criteria_hits=[],
        model_used="gpt-5.4-mini",
        llm_provider="openai",
        screened_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Unit tests — get_unscreened_articles (no HTTP, direct DB)
# ---------------------------------------------------------------------------


async def test_get_unscreened_returns_all_when_no_results(db, project_id, criteria_id):
    articles = [_make_article(project_id, i) for i in range(3)]
    for a in articles:
        db.add(a)
    await db.commit()

    result = await get_unscreened_articles(project_id, criteria_id, db)

    assert len(result) == 3


async def test_get_unscreened_excludes_screened_articles(db, project_id, criteria_id):
    articles = [_make_article(project_id, i) for i in range(3)]
    for a in articles:
        db.add(a)
    await db.commit()

    db.add(_make_screening_result(articles[0].id, project_id, criteria_id))
    await db.commit()

    result = await get_unscreened_articles(project_id, criteria_id, db)
    result_ids = [a.id for a in result]

    assert len(result) == 2
    assert articles[0].id not in result_ids


async def test_get_unscreened_includes_stale_results(db, project_id, criteria_id):
    """A result under an old criteria version does not count as screened under the new one."""
    article = _make_article(project_id)
    db.add(article)
    await db.commit()

    # Result exists under v1 (criteria_id from fixture).
    db.add(_make_screening_result(article.id, project_id, criteria_id))

    # New criteria version v2.
    criteria_v2 = DBCriteria(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version=2,
        inclusion=["RCT"],
        exclusion=[],
        uncertain_threshold=0.90,
        created_at=datetime.now(UTC),
    )
    db.add(criteria_v2)
    await db.commit()

    result = await get_unscreened_articles(project_id, criteria_v2.id, db)

    assert len(result) == 1
    assert result[0].id == article.id


async def test_get_unscreened_tombstones_excluded(db, project_id, criteria_id):
    """A tombstone ScreeningResult marks the article as handled — not re-queued on resume."""
    article = _make_article(project_id)
    db.add(article)
    await db.commit()

    await write_tombstone(article.id, project_id, criteria_id, "test error", db)

    result = await get_unscreened_articles(project_id, criteria_id, db)

    assert len(result) == 0


# ---------------------------------------------------------------------------
# API tests — screening run lifecycle
# ---------------------------------------------------------------------------


async def test_create_screening_run_requires_active_criteria(client, project_id):
    """POST /screening/run returns 404 when no criteria exist for the project."""
    resp = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    assert resp.status_code == 404


async def test_create_screening_run_returns_202(client, project_id, criteria_id, mock_coordinator):
    resp = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert data["criteria_id"] == criteria_id
    mock_coordinator.assert_called_once()


async def test_second_run_resumes_existing_incomplete(
    client, project_id, criteria_id, mock_coordinator
):
    """A second POST /screening/run resumes the existing incomplete run — no new row created."""
    r1 = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    assert r1.status_code == 202
    run_id = r1.json()["id"]

    r2 = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    assert r2.status_code == 202
    assert r2.json()["id"] == run_id


async def test_cancel_screening_run(client, project_id, criteria_id, mock_coordinator):
    create = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    run_id = create.json()["id"]

    resp = await client.post(f"/projects/{project_id}/screening/runs/{run_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


async def test_resume_completed_run_rejected(client, db, project_id, criteria_id, mock_coordinator):
    """Attempting to resume a completed run returns 409 Conflict."""
    create = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    run_id = create.json()["id"]

    run = await db.get(ScreeningRun, run_id)
    run.status = "completed"
    await db.commit()

    resp = await client.post(f"/projects/{project_id}/screening/runs/{run_id}/resume")
    assert resp.status_code == 409


async def test_list_screening_runs(client, project_id, criteria_id, mock_coordinator):
    await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})

    resp = await client.get(f"/projects/{project_id}/screening/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_run_endpoint_unpauses_paused_run(client, project_id, criteria_id, mock_coordinator):
    """POST /screening/run on a paused run must flip it to pending or the coordinator no-ops."""
    r1 = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    run_id = r1.json()["id"]
    await client.post(f"/projects/{project_id}/screening/runs/{run_id}/cancel")

    r2 = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})

    assert r2.status_code == 202
    assert r2.json()["id"] == run_id
    assert r2.json()["status"] == "pending"


# ---------------------------------------------------------------------------
# Full-text eligibility / completion
# ---------------------------------------------------------------------------


def _fulltext_article(project_id: str, idx: int) -> Article:
    article = _make_article(project_id, idx)
    article.fulltext_status = "retrieved"
    return article


def _result(article_id: str, project_id: str, criteria_id: str, stage: str) -> ScreeningResult:
    sr = _make_screening_result(article_id, project_id, criteria_id)
    sr.stage = stage
    sr.decision = "uncertain" if stage == "abstract" else "include"
    return sr


async def test_fulltext_eligible_excludes_already_screened(db, project_id, criteria_id):
    articles = [_fulltext_article(project_id, i) for i in range(3)]
    for a in articles:
        db.add(a)
        db.add(_result(a.id, project_id, criteria_id, "abstract"))
    await db.commit()
    db.add(_result(articles[0].id, project_id, criteria_id, "fulltext"))
    await db.commit()

    without_cursor = await get_fulltext_eligible_articles(project_id, db)
    with_cursor = await get_fulltext_eligible_articles(project_id, db, criteria_id=criteria_id)

    assert len(without_cursor) == 3
    assert {a.id for a in with_cursor} == {articles[1].id, articles[2].id}


async def test_maybe_complete_run_closes_fulltext_run(db, project_id, criteria_id):
    article = _fulltext_article(project_id, 0)
    db.add(article)
    db.add(_result(article.id, project_id, criteria_id, "abstract"))
    run = ScreeningRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        criteria_id=criteria_id,
        stage="fulltext",
        status="running",
        total_articles=1,
        screened_count=0,
        error_count=0,
        created_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()

    await _maybe_complete_run(run.id, project_id, criteria_id, "fulltext", db)
    await db.refresh(run)
    assert run.status == "running"  # article still unscreened at full-text stage

    db.add(_result(article.id, project_id, criteria_id, "fulltext"))
    await db.commit()

    await _maybe_complete_run(run.id, project_id, criteria_id, "fulltext", db)
    await db.refresh(run)
    assert run.status == "completed"


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------


def test_in_flight_task_args_includes_active_and_reserved():
    inspector = MagicMock()
    inspector.active.return_value = {
        "w1": [{"name": "tasks.screening.screen_chunk", "args": "['run-1']"}]
    }
    inspector.reserved.return_value = {
        "w1": [{"name": "tasks.screening.screen_chunk", "args": "['run-2']"}]
    }

    with patch("tasks.watchdog.celery_app.control.inspect", return_value=inspector):
        in_flight = _in_flight_task_args()

    assert any("run-1" in a for a in in_flight)
    assert any("run-2" in a for a in in_flight)


def test_in_flight_task_args_handles_no_workers():
    inspector = MagicMock()
    inspector.active.return_value = None
    inspector.reserved.return_value = None

    with patch("tasks.watchdog.celery_app.control.inspect", return_value=inspector):
        assert _in_flight_task_args() == []


# ---------------------------------------------------------------------------
# Eligibility count + run delete
# ---------------------------------------------------------------------------


async def test_fulltext_eligibility_counts_article_once_across_criteria_versions(
    client, db, project_id, criteria_id
):
    article = _fulltext_article(project_id, 0)
    db.add(article)
    db.add(_result(article.id, project_id, criteria_id, "abstract"))
    db.add(_result(article.id, project_id, criteria_id, "abstract"))
    await db.commit()

    resp = await client.get(f"/projects/{project_id}/screening/fulltext-eligibility")

    assert resp.status_code == 200
    assert resp.json()["uncertain_total"] == 1
    assert resp.json()["retrieved"] == 1


async def test_fulltext_run_total_matches_unscreened_and_rejects_when_done(
    client, db, project_id, criteria_id, mock_coordinator
):
    articles = [_fulltext_article(project_id, i) for i in range(2)]
    for a in articles:
        db.add(a)
        db.add(_result(a.id, project_id, criteria_id, "abstract"))
    await db.commit()
    db.add(_result(articles[0].id, project_id, criteria_id, "fulltext"))
    await db.commit()

    resp = await client.post(f"/projects/{project_id}/screening/fulltext-run", json={})
    assert resp.status_code == 202
    assert resp.json()["total_articles"] == 1

    db.add(_result(articles[1].id, project_id, criteria_id, "fulltext"))
    await db.commit()
    resp = await client.post(f"/projects/{project_id}/screening/fulltext-run", json={})
    assert resp.status_code == 409


async def test_delete_run_blocked_by_human_override(client, db, project_id, criteria_id):
    article = _make_article(project_id)
    db.add(article)
    run = ScreeningRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        criteria_id=criteria_id,
        stage="abstract",
        status="completed",
        total_articles=1,
        screened_count=1,
        error_count=0,
        created_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    sr = _make_screening_result(article.id, project_id, criteria_id)
    sr.screening_run_id = run.id
    sr.human_override = True
    sr.human_decision = "exclude"
    db.add(sr)
    await db.commit()

    resp = await client.delete(f"/projects/{project_id}/screening/runs/{run.id}")
    assert resp.status_code == 409

    sr.human_override = False
    await db.commit()
    resp = await client.delete(f"/projects/{project_id}/screening/runs/{run.id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Full-text prompt cap
# ---------------------------------------------------------------------------


def test_prepare_fulltext_articles_truncates_and_splits():
    long_article = _fulltext_article("p", 0)
    long_article.fulltext_text = "x" * (_FULLTEXT_MAX_CHARS + 500)
    missing = _fulltext_article("p", 1)
    missing.fulltext_text = None

    screenable, no_fulltext = _prepare_fulltext_articles([long_article, missing])

    assert [a.id for a in screenable] == [long_article.id]
    assert len(screenable[0].abstract) == _FULLTEXT_MAX_CHARS
    assert [a.id for a in no_fulltext] == [missing.id]


# ---------------------------------------------------------------------------
# Double-dispatch guards
# ---------------------------------------------------------------------------


async def _running_run(client, db, project_id) -> str:
    create = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})
    run_id = create.json()["id"]
    run = await db.get(ScreeningRun, run_id)
    run.status = "running"
    await db.commit()
    return run_id


async def test_resume_running_run_rejected(client, db, project_id, criteria_id, mock_coordinator):
    run_id = await _running_run(client, db, project_id)
    mock_coordinator.reset_mock()

    resp = await client.post(f"/projects/{project_id}/screening/runs/{run_id}/resume")

    assert resp.status_code == 409
    mock_coordinator.assert_not_called()


async def test_run_endpoint_does_not_redispatch_running_run(
    client, db, project_id, criteria_id, mock_coordinator
):
    run_id = await _running_run(client, db, project_id)
    mock_coordinator.reset_mock()

    resp = await client.post(f"/projects/{project_id}/screening/run", json={"stage": "abstract"})

    assert resp.status_code == 202
    assert resp.json()["id"] == run_id
    mock_coordinator.assert_not_called()


async def test_coordinator_skips_when_lock_held():
    lock = MagicMock()
    lock.acquire.return_value = False

    with (
        patch("tasks.screening._coordinator_lock", return_value=lock),
        patch("tasks.screening._dispatch_unscreened") as dispatch,
    ):
        await _run_coordinator("run-1")

    dispatch.assert_not_called()
    lock.release.assert_not_called()


async def test_coordinator_releases_lock_after_dispatch():
    lock = MagicMock()
    lock.acquire.return_value = True

    with (
        patch("tasks.screening._coordinator_lock", return_value=lock),
        patch("tasks.screening._dispatch_unscreened", new_callable=AsyncMock) as dispatch,
    ):
        await _run_coordinator("run-1")

    dispatch.assert_awaited_once_with("run-1")
    lock.release.assert_called_once()
