"""Upload API tests — PubMed CSV BOM, dry_run, source metadata."""

import io
from pathlib import Path


async def test_upload_pubmed_csv_bom_returns_correct_count(client, project_id, pubmed_csv_path):
    """PubMed CSV with BOM character should parse 2 records successfully."""
    content = Path(pubmed_csv_path).read_bytes()
    resp = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("pubmed_export.csv", io.BytesIO(content), "text/csv")},
    )
    assert resp.status_code == 201
    assert resp.json()["total_parsed"] == 2
    assert resp.json()["new_articles"] == 2


async def test_upload_dry_run_does_not_save(client, project_id, pubmed_csv_path):
    """dry_run=true should return parse preview without writing articles to the DB."""
    content = Path(pubmed_csv_path).read_bytes()
    resp = await client.post(
        f"/projects/{project_id}/upload?dry_run=true",
        files={"file": ("pubmed_export.csv", io.BytesIO(content), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_parsed"] == 2

    # Verify nothing was written
    articles_resp = await client.get(f"/projects/{project_id}/articles")
    assert articles_resp.status_code == 200
    assert articles_resp.json()["total"] == 0


async def test_upload_stores_source_metadata(client, project_id, pubmed_csv_path):
    """source_label and search_strategy_used should be persisted on the upload record."""
    content = Path(pubmed_csv_path).read_bytes()
    resp = await client.post(
        f"/projects/{project_id}/upload",
        files={"file": ("pubmed_export.csv", io.BytesIO(content), "text/csv")},
        data={
            "source_label": "PubMed (web interface)",
            "search_strategy_used": "probiotic*[tiab] AND Crohn[tiab]",
        },
    )
    assert resp.status_code == 201

    uploads_resp = await client.get(f"/projects/{project_id}/uploads")
    assert uploads_resp.status_code == 200
    upload = uploads_resp.json()[0]
    assert upload["source_label"] == "PubMed (web interface)"
    assert "probiotic" in upload["search_strategy_used"]
