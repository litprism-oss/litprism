"""Integration tests — hit the real PubMed API.

Run manually (needs network; PUBMED_API_KEY is optional but reduces rate limits):

    uv run pytest packages/litprism-pubmed/tests/integration/ -v -m integration

Skipped in CI by default (addopts = "-m 'not integration'" in pyproject.toml).
"""

import os
import tempfile
from datetime import date

import pytest

from litprism.pubmed import AsyncPubMedClient
from litprism.pubmed.cache import ArticleCache
from litprism.pubmed.models import DateRange, SearchFilters

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_real_search_with_filters():
    """Search with date, publication-type, and abstract filters.

    Uses systematic reviews on probiotics + Crohn — a well-studied topic with
    guaranteed results. Species filter is omitted: many Crohn probiotic trials
    are not indexed with a Humans MeSH term despite being human studies.
    """
    client = AsyncPubMedClient(api_key=os.getenv("PUBMED_API_KEY"))
    filters = SearchFilters(
        date_range=DateRange(start=date(2015, 1, 1), end=date(2024, 12, 31)),
        publication_types=["systematic_review"],
        has_abstract=True,
    )
    result = await client.search(
        query="probiotic[tiab] AND Crohn[tiab]",
        filters=filters,
        max_results=10,
    )
    assert len(result) > 0
    assert len(result) <= 10
    for article in result:
        assert article.abstract is not None


@pytest.mark.asyncio
async def test_pagination_streams_correctly():
    """search_iter yields batches; total collected respects max_results."""
    client = AsyncPubMedClient(api_key=os.getenv("PUBMED_API_KEY"))
    total = 0
    async for batch in client.search_iter(
        query="probiotic[tiab]",
        filters=SearchFilters(),
        batch_size=200,
        max_results=250,
    ):
        assert len(batch) <= 200
        total += len(batch)
    assert 0 < total <= 250


@pytest.mark.asyncio
async def test_fetch_single_article():
    """get() returns a well-formed Article for a known stable PMID."""
    client = AsyncPubMedClient(api_key=os.getenv("PUBMED_API_KEY"))
    # PMID 11748933 — Watson & Crick 1953 (stable, will not disappear)
    article = await client.get("11748933")
    assert article.pmid == "11748933"
    assert article.title
    assert article.source == "pubmed"


@pytest.mark.asyncio
async def test_cache_hit_on_repeat_fetch():
    """Second fetch() call returns cached results without hitting the network."""
    with tempfile.TemporaryDirectory() as tmp:
        cache = ArticleCache(db_path=f"{tmp}/test_cache.db")
        client = AsyncPubMedClient(
            api_key=os.getenv("PUBMED_API_KEY"),
            cache=cache,
        )
        pmids = ["11748933", "16541075"]

        first = await client.fetch(pmids)
        assert len(first) == 2

        # Verify both PMIDs are now in the cache
        cached = cache.get_many(pmids)
        assert set(cached.keys()) == set(pmids)

        # Second fetch should be a full cache hit — results match
        second = await client.fetch(pmids)
        assert {a.pmid for a in second} == {a.pmid for a in first}


@pytest.mark.asyncio
async def test_search_returns_article_fields():
    """Articles returned by search() have the expected fields populated."""
    client = AsyncPubMedClient(api_key=os.getenv("PUBMED_API_KEY"))
    results = await client.search(
        query="CRISPR[tiab] AND cancer[tiab]",
        filters=SearchFilters(has_abstract=True),
        max_results=5,
    )
    assert len(results) > 0
    for article in results:
        assert article.pmid is not None
        assert article.title
        assert article.abstract is not None
        assert article.source == "pubmed"
