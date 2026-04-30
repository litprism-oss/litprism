"""Enrichment service tests — strategy routing, no-overwrite rule, status tracking."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.models import Article
from services.enrichment import _enrich_by_doi, _enrich_by_pmid, _enrich_by_title, enrich_articles


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.pubmed_api_key = None
    s.semantic_scholar_api_key = None
    return s


async def _add_article(db, **kwargs) -> Article:
    defaults = {
        "id": str(uuid.uuid4()),
        "project_id": "proj-1",
        "source": "upload",
        "authors": [],
        "enrichment_status": "pending",
    }
    defaults.update(kwargs)
    a = Article(**defaults)
    db.add(a)
    await db.commit()
    return a


async def test_enrich_by_pmid_fills_abstract(db, mock_settings):
    """Abstract should be filled when PubMed returns it."""
    article = await _add_article(db, pmid="31009449", title="Test", abstract=None)

    mock_hit = MagicMock()
    mock_hit.pmid = "31009449"
    mock_hit.abstract = "Background: Probiotics..."
    mock_hit.authors = []

    with patch(
        "services.enrichment.AsyncPubMedClient.fetch",
        new_callable=AsyncMock,
        return_value=[mock_hit],
    ):
        enriched = await _enrich_by_pmid([article], db, mock_settings)

    assert enriched == 1
    assert article.abstract == "Background: Probiotics..."
    assert article.enrichment_status == "enriched"


async def test_enrich_does_not_overwrite_existing_abstract(db, mock_settings):
    """Articles with an existing abstract are marked skipped — PubMed is never called."""
    article = await _add_article(
        db,
        pmid="31009449",
        title="Test",
        abstract="Existing abstract that must not be overwritten",
        enrichment_status=None,
    )

    with patch(
        "services.enrichment.AsyncPubMedClient.fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        result = await enrich_articles("proj-1", [article.id], db, mock_settings)

    mock_fetch.assert_not_called()
    assert result["skipped"] == 1
    assert article.abstract == "Existing abstract that must not be overwritten"
    assert article.enrichment_status == "skipped"


async def test_enrich_by_doi_fills_abstract_when_no_pmid(db):
    """DOI strategy runs when article has no PMID."""
    article = await _add_article(db, pmid=None, doi="10.1016/test", title="Test", abstract=None)

    mock_result = MagicMock()
    mock_result.abstract = "Abstract from Europe PMC"

    with patch(
        "services.enrichment.AsyncEuropePMCClient.search",
        new_callable=AsyncMock,
        return_value=[mock_result],
    ):
        enriched = await _enrich_by_doi([article], db)

    assert enriched == 1
    assert article.abstract == "Abstract from Europe PMC"
    assert article.enrichment_status == "enriched"


async def test_enrich_by_title_rejects_low_similarity(db, mock_settings):
    """Title match below 0.95 similarity must not be used."""
    article = await _add_article(
        db,
        pmid=None,
        doi=None,
        title="Probiotics in inflammatory bowel disease",
        abstract=None,
    )

    mock_result = MagicMock()
    mock_result.title = "Completely different title about quantum computing"
    mock_result.abstract = "Should not be used"

    with patch(
        "services.enrichment.AsyncSemanticScholarClient.search",
        new_callable=AsyncMock,
        return_value=[mock_result],
    ):
        enriched = await _enrich_by_title([article], db, mock_settings)

    assert enriched == 0
    assert article.abstract is None


async def test_enrich_marks_not_found_when_all_strategies_fail(db, mock_settings):
    """An article whose PMID returns no results should be marked not_found."""
    article = await _add_article(db, pmid="99999999", title="Test", abstract=None)

    with patch(
        "services.enrichment.AsyncPubMedClient.fetch",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await enrich_articles("proj-1", [article.id], db, mock_settings)

    assert result["not_found"] == 1
    assert article.enrichment_status == "not_found"


async def test_enrich_handles_per_article_exception(db, mock_settings):
    """Exception on one PubMed batch must not stop the overall enrichment from completing."""
    articles = [
        await _add_article(db, pmid=str(i), title=f"Title {i}", abstract=None) for i in range(1, 4)
    ]

    call_count = 0

    async def flaky_fetch(pmids):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Simulated API failure")
        return []

    with patch("services.enrichment.AsyncPubMedClient.fetch", side_effect=flaky_fetch):
        result = await enrich_articles("proj-1", [a.id for a in articles], db, mock_settings)

    # The call should complete without raising
    assert "not_found" in result or "errors" in result
