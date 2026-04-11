"""Tests for litprism.pubmed.client — all network calls are mocked."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from litprism.pubmed.client import AsyncPubMedClient, PubMedClient
from litprism.pubmed.exceptions import PubMedAPIError, PubMedNetworkError
from litprism.pubmed.models import SearchFilters

FIXTURES = Path(__file__).parent / "fixtures"

# esearch response — has webenv + querykey for search_paginated step 1
ESEARCH_RESPONSE = {
    "esearchresult": {
        "count": "2",
        "idlist": ["12345678", "99999999"],
        "querykey": "1",
        "webenv": "MCID_abc123",
    }
}

# esearch response with count=0 (no results)
ESEARCH_EMPTY = {
    "esearchresult": {
        "count": "0",
        "idlist": [],
        "querykey": "1",
        "webenv": "MCID_empty",
    }
}


def single_article_xml() -> str:
    return (FIXTURES / "single_article.xml").read_text()


def batch_articles_xml() -> str:
    return (FIXTURES / "batch_articles.xml").read_text()


def _mock_response(json_data=None, text_data=None, status_code=200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    if text_data is not None:
        resp.text = text_data
    return resp


def _mock_http(side_effects: list) -> AsyncMock:
    """Build a mock httpx.AsyncClient whose .get() cycles through side_effects."""
    mock = AsyncMock()
    mock.get = AsyncMock(side_effect=side_effects)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


class TestAsyncPubMedClientSearch:
    async def test_search_returns_articles(self):
        """search() returns a list of Article objects."""
        client = AsyncPubMedClient()
        mock_http = _mock_http([
            _mock_response(json_data=ESEARCH_RESPONSE),   # step 1: esearch
            _mock_response(text_data=single_article_xml()),  # step 2: efetch batch
        ])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            results = await client.search("Crohn disease probiotic")

        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0].pmid is not None

    async def test_search_returns_empty_list_when_no_results(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([
            _mock_response(json_data=ESEARCH_EMPTY),
        ])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            results = await client.search("unlikely_query_xyz")

        assert results == []

    async def test_search_with_filters_sends_filter_terms(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([
            _mock_response(json_data=ESEARCH_RESPONSE),
            _mock_response(text_data=single_article_xml()),
        ])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            await client.search(
                "Crohn disease",
                filters=SearchFilters(languages=["en"], has_abstract=True),
            )

        # First call is the esearch — check the term includes filter fragments
        esearch_call = mock_http.get.call_args_list[0]
        params = esearch_call[1]["params"] if "params" in esearch_call[1] else esearch_call[0][1]
        assert '"en"[la]' in params.get("term", "")
        assert "hasabstract" in params.get("term", "")


class TestAsyncPubMedClientSearchIter:
    async def test_search_iter_yields_batches(self):
        """search_iter() yields lists of Article objects."""
        client = AsyncPubMedClient()
        mock_http = _mock_http([
            _mock_response(json_data=ESEARCH_RESPONSE),
            _mock_response(text_data=batch_articles_xml()),
        ])

        batches = []
        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            async for batch in client.search_iter("probiotic[tiab]", batch_size=200):
                batches.append(batch)

        assert len(batches) >= 1
        assert all(isinstance(a, object) for batch in batches for a in batch)

    async def test_search_iter_empty_results(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([
            _mock_response(json_data=ESEARCH_EMPTY),
        ])

        batches = []
        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            async for batch in client.search_iter("nothing"):
                batches.append(batch)

        assert batches == []


class TestAsyncPubMedClientFetch:
    async def test_fetch_returns_articles(self):
        client = AsyncPubMedClient()
        mock_efetch = _mock_response(text_data=single_article_xml())
        mock_http = _mock_http([mock_efetch])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            articles = await client.fetch(["12345678"])

        assert len(articles) == 1
        assert articles[0].pmid == "12345678"
        assert articles[0].title is not None

    async def test_fetch_empty_list(self):
        client = AsyncPubMedClient()
        articles = await client.fetch([])
        assert articles == []

    async def test_fetch_batch_articles(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(text_data=batch_articles_xml())])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            articles = await client.fetch(["11111111", "22222222", "33333333"])

        assert len(articles) == 3


class TestAsyncPubMedClientGet:
    async def test_get_returns_single_article(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(text_data=single_article_xml())])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            article = await client.get("12345678")

        assert article.pmid == "12345678"

    async def test_get_raises_when_not_found(self):
        client = AsyncPubMedClient()
        # Efetch returns empty XML (no PubmedArticle elements)
        empty_xml = "<PubmedArticleSet></PubmedArticleSet>"
        mock_http = _mock_http([_mock_response(text_data=empty_xml)])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(PubMedAPIError):
                await client.get("00000000")


class TestErrorHandling:
    async def test_rate_limit_raises_after_retries(self):
        client = AsyncPubMedClient()
        # Return 429 three times to exhaust tenacity retries
        mock_http = _mock_http([_mock_response(status_code=429)] * 3)

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            from litprism.pubmed.exceptions import PubMedRateLimitError
            with pytest.raises(PubMedRateLimitError):
                await client.fetch(["12345678"])

    async def test_network_error_raises(self):
        client = AsyncPubMedClient()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.NetworkError("connection refused"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(PubMedNetworkError):
                await client.fetch(["12345678"])

    async def test_unexpected_status_raises(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(status_code=500)])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(PubMedAPIError):
                await client.fetch(["12345678"])


class TestSyncClient:
    def test_sync_search_returns_articles(self):
        client = PubMedClient()
        mock_http = _mock_http([
            _mock_response(json_data=ESEARCH_RESPONSE),
            _mock_response(text_data=single_article_xml()),
        ])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            results = client.search("Crohn disease")

        assert isinstance(results, list)
        assert len(results) >= 1

    def test_sync_get_returns_article(self):
        client = PubMedClient()
        mock_http = _mock_http([_mock_response(text_data=single_article_xml())])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            article = client.get("12345678")

        assert article.pmid == "12345678"

    def test_sync_fetch_returns_articles(self):
        client = PubMedClient()
        mock_http = _mock_http([_mock_response(text_data=single_article_xml())])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            articles = client.fetch(["12345678"])

        assert len(articles) == 1
