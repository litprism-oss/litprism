"""Integration tests for litprism-europepmc — requires network access.

Run with:
    uv run pytest packages/litprism-europepmc/tests/integration/ -v -m integration
"""

import pytest
from litprism.europepmc.client import AsyncEuropePMCClient
from litprism.europepmc.models import SearchFilters


@pytest.mark.integration
async def test_search_returns_articles():
    """Basic smoke test — search returns at least one article."""
    client = AsyncEuropePMCClient()
    articles = await client.search(query="probiotic Crohn disease", max_results=5)
    assert len(articles) > 0
    assert all(a.title for a in articles)
    assert all(a.source == "europepmc" for a in articles)


@pytest.mark.integration
async def test_search_iter_yields_batches():
    """search_iter yields at least one batch."""
    client = AsyncEuropePMCClient()
    batches = []
    async for batch in client.search_iter(query="cancer immunotherapy", max_results=50):
        batches.append(batch)
        break  # only need one batch
    assert len(batches) == 1
    assert len(batches[0]) > 0


@pytest.mark.integration
async def test_get_known_article():
    """Fetch a known MEDLINE article by PMID."""
    client = AsyncEuropePMCClient()
    # PMID 33577785 — a widely-cited COVID-19 article in PubMed/MEDLINE
    article = await client.get(article_id="33577785", source="MED")
    assert article.id == "33577785"
    assert article.title


@pytest.mark.integration
async def test_filters_narrow_results():
    """Applying open-access filter returns fewer results than unfiltered."""
    client = AsyncEuropePMCClient()
    all_results = await client.search(query="diabetes treatment", max_results=100)
    oa_results = await client.search(
        query="diabetes treatment",
        filters=SearchFilters(europepmc_open_access=True),
        max_results=100,
    )
    assert len(oa_results) <= len(all_results)
    assert all(a.open_access for a in oa_results)
