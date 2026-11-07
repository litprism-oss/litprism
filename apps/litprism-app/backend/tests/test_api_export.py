"""Export API tests — format-specific content, decision filter, empty project."""

import json

from db.models import ScreeningResult
from sqlalchemy import select


async def test_export_ris_contains_title_tag(client, project_id, articles_in_db):
    """RIS export should have TY and TI tags for each article."""
    resp = await client.get(f"/projects/{project_id}/export/ris")
    assert resp.status_code == 200
    content = resp.text
    assert "TY  -" in content
    assert "TI  -" in content


async def test_export_csv_has_doi_column(client, project_id, articles_in_db):
    """CSV export first row must include title and doi columns."""
    resp = await client.get(f"/projects/{project_id}/export/csv")
    assert resp.status_code == 200
    first_line = resp.text.split("\n")[0].lower()
    assert "title" in first_line
    assert "doi" in first_line


async def test_export_json_returns_article_list(client, project_id, articles_in_db):
    """JSON export should be a list with all articles and required fields."""
    resp = await client.get(f"/projects/{project_id}/export/json")
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert isinstance(data, list)
    assert len(data) == 5
    assert all("title" in item and "doi" in item for item in data)


# ---------------------------------------------------------------------------
# PRISMA flow counts
# ---------------------------------------------------------------------------


def _result(article_id, project_id, criteria_id, stage, decision, **overrides):
    import uuid
    from datetime import UTC, datetime

    return ScreeningResult(
        id=str(uuid.uuid4()),
        article_id=article_id,
        project_id=project_id,
        criteria_id=criteria_id,
        stage=stage,
        decision=decision,
        confidence=0.9,
        reasoning="",
        criteria_hits=[],
        model_used="test-model",
        llm_provider="openai",
        screened_at=datetime.now(UTC),
        **overrides,
    )


async def test_prisma_counts_unknown_project_404(client):
    resp = await client.get("/projects/nope/prisma-counts")
    assert resp.status_code == 404


async def test_prisma_counts_empty_project(client, project_id):
    resp = await client.get(f"/projects/{project_id}/prisma-counts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["records_screened"] == 0
    assert data["studies_included"] == 0
    assert data["fulltext_assessed"] is None
    assert data["fulltext_excluded"] is None


async def test_prisma_counts_abstract_only(client, project_id, articles_with_decisions):
    """Fixture: include ×3, exclude ×1, uncertain ×1 at abstract stage."""
    data = (await client.get(f"/projects/{project_id}/prisma-counts")).json()

    assert data["records_screened"] == 5
    assert data["excluded_screening"] == 1
    assert data["uncertain"] == 1
    assert data["studies_included"] == 3
    assert data["fulltext_assessed"] is None  # Eligibility row stays pending


async def test_prisma_counts_with_fulltext_overrides_and_errors(
    client, db, project_id, articles_with_decisions
):
    articles = articles_with_decisions
    criteria_id = (await client.get(f"/projects/{project_id}/criteria")).json()["id"]
    uncertain_article = articles[3]

    # Full-text: the uncertain article is included; a stray error tombstone is ignored.
    db.add(_result(uncertain_article.id, project_id, criteria_id, "fulltext", "include"))
    db.add(_result(articles[0].id, project_id, criteria_id, "fulltext", "error"))
    # Human overrides one of the model's abstract includes to exclude.
    sr = await db.scalar(
        select(ScreeningResult).where(
            ScreeningResult.article_id == articles[1].id, ScreeningResult.stage == "abstract"
        )
    )
    sr.human_override = True
    sr.human_decision = "exclude"
    await db.commit()

    data = (await client.get(f"/projects/{project_id}/prisma-counts")).json()

    assert data["records_screened"] == 5
    assert data["excluded_screening"] == 2  # 1 model + 1 human override
    assert data["fulltext_assessed"] == 1  # error tombstone not counted
    assert data["fulltext_excluded"] == 0
    assert data["studies_included"] == 3  # 2 abstract + 1 full-text


async def test_prisma_s_export_still_builds(client, project_id, articles_with_decisions):
    resp = await client.get(f"/projects/{project_id}/export/prisma-s")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
