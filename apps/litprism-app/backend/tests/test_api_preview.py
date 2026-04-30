"""Search preview API tests — sources param, default all-sources, per-source error isolation."""

from unittest.mock import AsyncMock, patch

from api.schemas import SearchPreviewSource


async def test_preview_respects_sources_param(client, project_id):
    """Sending sources=['pubmed'] should call only the PubMed preview function."""
    mock_result = SearchPreviewSource(
        source="pubmed", estimated_count=100, sample_titles=["Test title"]
    )
    with patch("api.search._preview_pubmed", new_callable=AsyncMock, return_value=mock_result):
        resp = await client.post(
            f"/projects/{project_id}/search-runs/preview",
            json={"query_final": "probiotic*[tiab]", "sources": ["pubmed"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source"] == "pubmed"
    assert data["sources"][0]["error"] is None


async def test_preview_returns_all_sources_by_default(client, project_id):
    """When sources is not specified, all three default sources are returned."""
    pubmed_result = SearchPreviewSource(source="pubmed", estimated_count=50, sample_titles=[])
    epmc_result = SearchPreviewSource(source="europepmc", estimated_count=30, sample_titles=[])
    s2_result = SearchPreviewSource(source="semanticscholar", estimated_count=20, sample_titles=[])

    with (
        patch("api.search._preview_pubmed", new_callable=AsyncMock, return_value=pubmed_result),
        patch("api.search._preview_europepmc", new_callable=AsyncMock, return_value=epmc_result),
        patch(
            "api.search._preview_semanticscholar",
            new_callable=AsyncMock,
            return_value=s2_result,
        ),
    ):
        resp = await client.post(
            f"/projects/{project_id}/search-runs/preview",
            json={"query_final": "probiotics"},
        )

    assert resp.status_code == 200
    sources = {s["source"] for s in resp.json()["sources"]}
    assert sources == {"pubmed", "europepmc", "semanticscholar"}


async def test_preview_source_error_does_not_fail_whole_request(client, project_id):
    """A rate-limited source returns an error field; other sources succeed normally."""
    pubmed_ok = SearchPreviewSource(source="pubmed", estimated_count=100, sample_titles=[])
    s2_error = SearchPreviewSource(
        source="semanticscholar",
        estimated_count=0,
        sample_titles=[],
        error="Rate limited — try again in a moment",
    )

    with (
        patch("api.search._preview_pubmed", new_callable=AsyncMock, return_value=pubmed_ok),
        patch(
            "api.search._preview_semanticscholar",
            new_callable=AsyncMock,
            return_value=s2_error,
        ),
    ):
        resp = await client.post(
            f"/projects/{project_id}/search-runs/preview",
            json={"query_final": "probiotic*[tiab]", "sources": ["pubmed", "semanticscholar"]},
        )

    assert resp.status_code == 200
    by_source = {s["source"]: s for s in resp.json()["sources"]}
    assert by_source["pubmed"]["error"] is None
    assert "Rate limited" in by_source["semanticscholar"]["error"]
