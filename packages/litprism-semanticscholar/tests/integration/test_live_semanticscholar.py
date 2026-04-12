"""Integration tests for litprism-semanticscholar — requires network access.

Run with:
    uv run pytest packages/litprism-semanticscholar/tests/integration/ -v -m integration
"""

import pytest
from litprism.semanticscholar.client import AsyncSemanticScholarClient
from litprism.semanticscholar.models import SearchFilters


@pytest.mark.integration
async def test_search_returns_articles():
    """Basic smoke test — search returns at least one article."""
    client = AsyncSemanticScholarClient()
    articles = await client.search(query="CRISPR gene editing", max_results=5)
    assert len(articles) > 0
    assert all(a.title for a in articles)
    assert all(a.source == "semanticscholar" for a in articles)


@pytest.mark.integration
async def test_search_iter_yields_batches():
    """search_iter yields at least one batch."""
    client = AsyncSemanticScholarClient()
    batches = []
    async for batch in client.search_iter(query="cancer immunotherapy", max_results=50):
        batches.append(batch)
        break  # only need one batch
    assert len(batches) == 1
    assert len(batches[0]) > 0


@pytest.mark.integration
async def test_get_known_article():
    """Fetch a known article by PMID external ID."""
    client = AsyncSemanticScholarClient()
    article = await client.get("PMID:33577785")
    assert article.title
    assert article.source == "semanticscholar"


@pytest.mark.integration
async def test_filters_narrow_results():
    """Applying open-access PDF filter returns fewer results than unfiltered."""
    client = AsyncSemanticScholarClient()
    all_results = await client.search(query="diabetes treatment", max_results=100)
    oa_results = await client.search(
        query="diabetes treatment",
        filters=SearchFilters(semanticscholar_open_access_pdf=True),
        max_results=100,
    )
    assert len(oa_results) <= len(all_results)
    assert all(a.pdf_url is not None for a in oa_results)
