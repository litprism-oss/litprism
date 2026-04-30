import uuid
from datetime import UTC, datetime

from db.models import Article, ScreeningResult, ScreeningRun
from db.models import Criteria as DBCriteria
from services.screening import get_unscreened_articles, write_tombstone

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
    assert resp.json()["status"] == "cancelled"


async def test_resume_completed_run_rejected(
    client, db, project_id, criteria_id, mock_coordinator
):
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
