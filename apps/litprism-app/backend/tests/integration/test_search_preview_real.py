import pytest

pytestmark = pytest.mark.integration


async def test_preview_pubmed_real(client):
    """Real PubMed preview — should return > 0 results."""
    projects = (await client.get("/projects")).json()
    project_id = projects[0]["id"] if projects else None
    if not project_id:
        pytest.skip("No project available")

    response = await client.post(
        f"/projects/{project_id}/search-runs/preview",
        json={
            "query_final": "probiotic*[tiab] AND Crohn[tiab]",
            "sources": ["pubmed"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    pubmed_result = next(s for s in data["sources"] if s["source"] == "pubmed")
    assert pubmed_result["error"] is None
    assert pubmed_result["estimated_count"] > 0
    assert len(pubmed_result["sample_titles"]) > 0


async def test_preview_only_requested_sources_called(client):
    """When sources=['pubmed'], Europe PMC and S2 should not appear."""
    projects = (await client.get("/projects")).json()
    project_id = projects[0]["id"] if projects else None
    if not project_id:
        pytest.skip("No project available")

    response = await client.post(
        f"/projects/{project_id}/search-runs/preview",
        json={
            "query_final": "probiotic*[tiab]",
            "sources": ["pubmed"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    source_names = [s["source"] for s in data["sources"]]
    assert "pubmed" in source_names
    assert "europepmc" not in source_names
    assert "semanticscholar" not in source_names
