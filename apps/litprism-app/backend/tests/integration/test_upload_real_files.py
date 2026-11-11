import os

import pytest

pytestmark = pytest.mark.integration


async def test_upload_pubmed_csv_real(client):
    """Upload the real PubMed CSV fixture and verify 53 articles parsed."""
    csv_path = "tests/fixtures/csv-ironMeSHTe-set.csv"
    if not os.path.exists(csv_path):
        pytest.skip("Real CSV fixture not available")

    projects = (await client.get("/projects")).json()
    project_id = projects[0]["id"] if projects else None
    if not project_id:
        pytest.skip("No project available")

    with open(csv_path, "rb") as f:
        response = await client.post(
            f"/projects/{project_id}/upload",
            files={"file": ("csv-ironMeSHTe-set.csv", f, "text/csv")},
            data={"source_label": "PubMed (web interface)"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["total_parsed"] == 53
    assert data["new_articles"] + data.get("duplicates_found", 0) == 53

    articles = (await client.get(f"/projects/{project_id}/articles?page_size=5")).json()
    for article in articles["items"]:
        assert article["title"] is not None
        assert article["pmid"] is not None


async def test_upload_pubmed_txt_real(client):
    """Upload PubMed MEDLINE .txt and verify abstract is present."""
    txt_path = "tests/fixtures/pubmed-physicalac-set.txt"
    if not os.path.exists(txt_path):
        pytest.skip("Real .txt fixture not available")

    projects = (await client.get("/projects")).json()
    project_id = projects[0]["id"] if projects else None
    if not project_id:
        pytest.skip("No project available")

    with open(txt_path, "rb") as f:
        response = await client.post(
            f"/projects/{project_id}/upload",
            files={"file": ("pubmed-physicalac-set.txt", f, "text/plain")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["total_parsed"] == 10

    articles = (await client.get(f"/projects/{project_id}/articles?page_size=10")).json()
    articles_with_abstract = [a for a in articles["items"] if a["abstract"]]
    assert len(articles_with_abstract) > 0
