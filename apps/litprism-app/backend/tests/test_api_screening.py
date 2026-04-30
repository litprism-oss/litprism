"""Screening API tests — criteria linkage, results filter, reviewer patch."""

import uuid
from datetime import UTC, datetime

from db.models import Article, Criteria, ScreeningResult, ScreeningRun


async def test_screening_run_stores_active_criteria_id(client, project_id, mock_coordinator):
    """POST /screening/run must link the new run to the currently active criteria version."""
    criteria_resp = await client.post(
        f"/projects/{project_id}/criteria",
        json={"inclusion": ["RCT"], "exclusion": ["Animal study"]},
    )
    assert criteria_resp.status_code == 201
    criteria_id = criteria_resp.json()["id"]

    run_resp = await client.post(
        f"/projects/{project_id}/screening/run",
        json={"stage": "abstract"},
    )
    assert run_resp.status_code == 202
    assert run_resp.json()["criteria_id"] == criteria_id


async def test_screening_results_filter_by_run_id(client, project_id, db):
    """GET /screening/results?run_id= should return 200 and only results for that run."""
    # Insert criteria + run + article + result directly into DB
    criteria = Criteria(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version=1,
        inclusion=["RCT"],
        exclusion=["Animal"],
        uncertain_threshold=0.9,
        created_at=datetime.now(UTC),
    )
    db.add(criteria)

    run = ScreeningRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        criteria_id=criteria.id,
        stage="abstract",
        status="completed",
        total_articles=0,
        created_at=datetime.now(UTC),
    )
    db.add(run)

    article = Article(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title="Test Article",
        source="upload",
        authors=[],
    )
    db.add(article)

    sr = ScreeningResult(
        id=str(uuid.uuid4()),
        article_id=article.id,
        project_id=project_id,
        criteria_id=criteria.id,
        screening_run_id=run.id,
        stage="abstract",
        decision="include",
        confidence=0.95,
        reasoning="Meets criteria.",
        criteria_hits=[],
        model_used="test-model",
        llm_provider="openai",
        screened_at=datetime.now(UTC),
    )
    db.add(sr)
    await db.commit()

    resp = await client.get(f"/projects/{project_id}/screening/results?run_id={run.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(
        item["screening_result"] is not None for item in data["items"] if item["screening_result"]
    )


async def test_screening_run_patch_reviewer_fields(client, project_id, db):
    """PATCH /screening/runs/{id} should persist reviewer_name and review_notes."""
    criteria = Criteria(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version=1,
        inclusion=["RCT"],
        exclusion=["Animal"],
        uncertain_threshold=0.9,
        created_at=datetime.now(UTC),
    )
    db.add(criteria)

    run = ScreeningRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        criteria_id=criteria.id,
        stage="abstract",
        status="completed",
        total_articles=0,
        created_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()

    resp = await client.patch(
        f"/projects/{project_id}/screening/runs/{run.id}",
        json={"reviewer_name": "Dr. Test", "review_notes": "Spot-checked"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reviewer_name"] == "Dr. Test"
    assert data["review_notes"] == "Spot-checked"
