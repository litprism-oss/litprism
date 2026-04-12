"""Tests for litprism.pubmed.client — all network calls are mocked."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from litprism.pubmed.client import AsyncPubMedClient, PubMedClient
from litprism.pubmed.exceptions import PubMedAPIError, PubMedNetworkError, PubMedRateLimitError
from litprism.pubmed.models import DateRange, SearchFilters

FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

ESEARCH_RESPONSE = {
    "esearchresult": {
        "count": "2",
        "idlist": ["12345678", "99999999"],
        "querykey": "1",
        "webenv": "MCID_abc123",
    }
}

ESEARCH_EMPTY = {
    "esearchresult": {
        "count": "0",
        "idlist": [],
        "querykey": "1",
        "webenv": "MCID_empty",
    }
}

# count=6, batch_size=3 → 2 efetch calls
ESEARCH_PAGINATED = {
    "esearchresult": {
        "count": "6",
        "idlist": [],
        "querykey": "1",
        "webenv": "MCID_paginate",
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


# ---------------------------------------------------------------------------
# AsyncPubMedClient.search
# ---------------------------------------------------------------------------


class TestAsyncPubMedClientSearch:
    async def test_search_returns_articles(self):
        """search() returns a list of Article objects."""
        client = AsyncPubMedClient()
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_RESPONSE),
                _mock_response(text_data=single_article_xml()),
            ]
        )

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            results = await client.search("Crohn disease probiotic")

        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0].pmid is not None

    async def test_search_returns_empty_list_when_no_results(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(json_data=ESEARCH_EMPTY)])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            results = await client.search("unlikely_query_xyz")

        assert results == []

    async def test_search_with_language_and_abstract_filter(self):
        """Filter terms are embedded in the esearch 'term' param."""
        client = AsyncPubMedClient()
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_RESPONSE),
                _mock_response(text_data=single_article_xml()),
            ]
        )

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            await client.search(
                "Crohn disease",
                filters=SearchFilters(languages=["en"], has_abstract=True),
            )

        esearch_call = mock_http.get.call_args_list[0]
        params = esearch_call[1]["params"] if "params" in esearch_call[1] else esearch_call[0][1]
        assert "english[la]" in params.get("term", "")
        assert "hasabstract" in params.get("term", "")

    async def test_search_with_publication_type_filter(self):
        """Publication type filter is translated to [pt] tags."""
        client = AsyncPubMedClient()
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_RESPONSE),
                _mock_response(text_data=single_article_xml()),
            ]
        )

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            await client.search(
                "probiotic",
                filters=SearchFilters(publication_types=["clinical_trial"]),
            )

        esearch_call = mock_http.get.call_args_list[0]
        params = esearch_call[1]["params"] if "params" in esearch_call[1] else esearch_call[0][1]
        assert "Clinical Trial[pt]" in params.get("term", "")

    async def test_search_with_date_range_filter(self):
        """Date range filter sets mindate/maxdate/datetype params."""
        from datetime import date

        client = AsyncPubMedClient()
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_RESPONSE),
                _mock_response(text_data=single_article_xml()),
            ]
        )

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            await client.search(
                "probiotic",
                filters=SearchFilters(
                    date_range=DateRange(start=date(2020, 1, 1), end=date(2024, 12, 31))
                ),
            )

        esearch_call = mock_http.get.call_args_list[0]
        params = esearch_call[1]["params"] if "params" in esearch_call[1] else esearch_call[0][1]
        assert params.get("mindate") == "2020/01/01"
        assert params.get("maxdate") == "2024/12/31"
        assert params.get("datetype") == "pdat"

    async def test_search_step1_esearch_uses_history_server(self):
        """Step-1 esearch sends retmax=0 (count only) and usehistory=y per spec §8."""
        client = AsyncPubMedClient()
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_EMPTY),
            ]
        )

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            await client.search("probiotic", max_results=50)

        esearch_call = mock_http.get.call_args_list[0]
        params = esearch_call[1]["params"] if "params" in esearch_call[1] else esearch_call[0][1]
        assert params.get("retmax") == 0
        assert params.get("usehistory") == "y"


# ---------------------------------------------------------------------------
# AsyncPubMedClient.search_iter — pagination
# ---------------------------------------------------------------------------


class TestAsyncPubMedClientSearchIter:
    async def test_search_iter_yields_batches(self):
        """search_iter() yields lists of Article objects."""
        client = AsyncPubMedClient()
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_RESPONSE),
                _mock_response(text_data=batch_articles_xml()),
            ]
        )

        batches = []
        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            async for batch in client.search_iter("probiotic[tiab]", batch_size=200):
                batches.append(batch)

        assert len(batches) >= 1
        assert all(isinstance(batch, list) for batch in batches)

    async def test_search_iter_empty_results(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(json_data=ESEARCH_EMPTY)])

        batches = []
        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            async for batch in client.search_iter("nothing"):
                batches.append(batch)

        assert batches == []

    async def test_search_iter_paginates_multiple_batches(self):
        """When count > batch_size, search_iter yields one batch per efetch call."""
        client = AsyncPubMedClient()
        # count=6, batch_size=3 → 2 efetch calls, each returning batch_articles_xml (3 articles)
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_PAGINATED),
                _mock_response(text_data=batch_articles_xml()),  # batch 1
                _mock_response(text_data=batch_articles_xml()),  # batch 2
            ]
        )

        batches = []
        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            async for batch in client.search_iter("probiotic", batch_size=3):
                batches.append(batch)

        assert len(batches) == 2
        assert sum(len(b) for b in batches) == 6

    async def test_search_iter_respects_max_results_cap(self):
        """Total fetched is capped at max_results even when count is higher."""
        client = AsyncPubMedClient()
        # count=6 but max_results=3 → only 1 efetch call
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_PAGINATED),
                _mock_response(text_data=batch_articles_xml()),
            ]
        )

        batches = []
        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            async for batch in client.search_iter("probiotic", batch_size=3, max_results=3):
                batches.append(batch)

        assert len(batches) == 1

    async def test_search_iter_uses_history_server(self):
        """Step 1 esearch sends usehistory=y; step 2 efetch uses WebEnv/query_key."""
        client = AsyncPubMedClient()
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_RESPONSE),
                _mock_response(text_data=single_article_xml()),
            ]
        )

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            async for _ in client.search_iter("probiotic"):
                pass

        esearch_params = mock_http.get.call_args_list[0][1]["params"]
        efetch_params = mock_http.get.call_args_list[1][1]["params"]

        assert esearch_params.get("usehistory") == "y"
        assert esearch_params.get("retmax") == 0
        assert efetch_params.get("WebEnv") == "MCID_abc123"
        assert efetch_params.get("query_key") == "1"
        assert efetch_params.get("retmode") == "xml"


# ---------------------------------------------------------------------------
# AsyncPubMedClient.fetch
# ---------------------------------------------------------------------------


class TestAsyncPubMedClientFetch:
    async def test_fetch_returns_articles(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(text_data=single_article_xml())])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            articles = await client.fetch(["12345678"])

        assert len(articles) == 1
        assert articles[0].pmid == "12345678"
        assert articles[0].title is not None

    async def test_fetch_empty_list_returns_empty(self):
        client = AsyncPubMedClient()
        articles = await client.fetch([])
        assert articles == []

    async def test_fetch_batch_articles(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(text_data=batch_articles_xml())])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            articles = await client.fetch(["11111111", "22222222", "33333333"])

        assert len(articles) == 3

    async def test_fetch_splits_into_batches_of_200(self):
        """More than 200 PMIDs triggers multiple efetch calls."""
        client = AsyncPubMedClient()
        # 201 PMIDs → 2 efetch calls (200 + 1)
        pmids = [str(i).zfill(8) for i in range(201)]
        mock_http = _mock_http(
            [
                _mock_response(text_data=batch_articles_xml()),
                _mock_response(text_data=single_article_xml()),
            ]
        )

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            articles = await client.fetch(pmids)

        assert mock_http.get.call_count == 2
        assert len(articles) == 4  # 3 from batch + 1 from single


# ---------------------------------------------------------------------------
# AsyncPubMedClient.get
# ---------------------------------------------------------------------------


class TestAsyncPubMedClientGet:
    async def test_get_returns_single_article(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(text_data=single_article_xml())])

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            article = await client.get("12345678")

        assert article.pmid == "12345678"

    async def test_get_raises_when_not_found(self):
        client = AsyncPubMedClient()
        empty_xml = "<PubmedArticleSet></PubmedArticleSet>"
        mock_http = _mock_http([_mock_response(text_data=empty_xml)])

        with (
            patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http),
            pytest.raises(PubMedAPIError),
        ):
            await client.get("00000000")


# ---------------------------------------------------------------------------
# Error handling — rate limit, 503, network errors
# ---------------------------------------------------------------------------


class TestErrorHandling:
    async def test_rate_limit_raises_after_retries(self):
        """429 exhausts tenacity retries (3 attempts) then re-raises."""
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(status_code=429)] * 3)

        with (
            patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http),
            pytest.raises(PubMedRateLimitError),
        ):
            await client.fetch(["12345678"])

    async def test_503_retries_then_raises(self):
        """503 is retried up to 3 times then re-raises as PubMedAPIError."""
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(status_code=503)] * 3)

        with (
            patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http),
            pytest.raises(PubMedAPIError) as exc_info,
        ):
            await client.fetch(["12345678"])
        assert exc_info.value.status_code == 503

    async def test_503_succeeds_on_retry(self):
        """503 followed by a successful response does not raise."""
        client = AsyncPubMedClient()
        mock_http = _mock_http(
            [
                _mock_response(status_code=503),
                _mock_response(text_data=single_article_xml()),
            ]
        )

        with patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http):
            articles = await client.fetch(["12345678"])

        assert len(articles) == 1

    async def test_network_error_raises(self):
        client = AsyncPubMedClient()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.NetworkError("connection refused"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http),
            pytest.raises(PubMedNetworkError),
        ):
            await client.fetch(["12345678"])

    async def test_timeout_raises_network_error(self):
        client = AsyncPubMedClient()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http),
            pytest.raises(PubMedNetworkError),
        ):
            await client.fetch(["12345678"])

    async def test_unexpected_status_raises_api_error(self):
        client = AsyncPubMedClient()
        mock_http = _mock_http([_mock_response(status_code=500)])

        with (
            patch("litprism.pubmed.entrez.httpx.AsyncClient", return_value=mock_http),
            pytest.raises(PubMedAPIError),
        ):
            await client.fetch(["12345678"])


# ---------------------------------------------------------------------------
# PubMedClient — synchronous wrapper
# ---------------------------------------------------------------------------


class TestSyncClient:
    def test_sync_search_returns_articles(self):
        client = PubMedClient()
        mock_http = _mock_http(
            [
                _mock_response(json_data=ESEARCH_RESPONSE),
                _mock_response(text_data=single_article_xml()),
            ]
        )

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

    def test_sync_search_iter_returns_async_generator(self):
        """search_iter on the sync client returns the underlying async generator."""
        import inspect

        client = PubMedClient()
        gen = client.search_iter("probiotic")
        assert inspect.isasyncgen(gen)
