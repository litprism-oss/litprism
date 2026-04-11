"""Tests for litprism.pubmed.client — all network calls are mocked."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from litprism.pubmed.client import AsyncPubMedClient, PubMedClient
from litprism.pubmed.exceptions import PubMedAPIError, PubMedNetworkError
from litprism.pubmed.models import ArticleFilters

FIXTURES = Path(__file__).parent / "fixtures"

ESEARCH_RESPONSE = {
    "esearchresult": {
        "count": "2",
        "idlist": ["12345678", "99999999"],
        "querykey": "1",
        "webenv": "MCID_abc123",
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


class TestAsyncPubMedClientSearch:
    async def test_search_returns_pmids(self):
        client = AsyncPubMedClient()
        mock_resp = _mock_response(json_data=ESEARCH_RESPONSE)

        with patch("litprism.pubmed.entrez.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            result = await client.search("Crohn disease probiotic")

        assert result.pmids == ["12345678", "99999999"]
        assert result.total_count == 2
        assert result.retrieved_count == 2
        assert result.query == "Crohn disease probiotic"

    async def test_search_with_filters(self):
        client = AsyncPubMedClient()
        mock_resp = _mock_response(json_data=ESEARCH_RESPONSE)

        with patch("litprism.pubmed.entrez.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            await client.search(
                "Crohn disease",
                filters=ArticleFilters(languages=["eng"], has_abstract=True),
            )

        call_kwargs = mock_http.get.call_args
        params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs[0][1]
        assert '"eng"[la]' in params.get("term", "")
        assert "hasabstract" in params.get("term", "")


class TestAsyncPubMedClientFetch:
    async def test_fetch_returns_articles(self):
        client = AsyncPubMedClient()
        mock_efetch = _mock_response(text_data=single_article_xml())

        with patch("litprism.pubmed.entrez.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_efetch)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

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
        mock_efetch = _mock_response(text_data=batch_articles_xml())

        with patch("litprism.pubmed.entrez.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_efetch)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            articles = await client.fetch(["11111111", "22222222", "33333333"])

        assert len(articles) == 3


class TestErrorHandling:
    async def test_rate_limit_raises(self):
        client = AsyncPubMedClient()
        mock_resp = _mock_response(status_code=429)

        with patch("litprism.pubmed.entrez.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            from litprism.pubmed.exceptions import PubMedRateLimitError

            with pytest.raises(PubMedRateLimitError):
                await client.search("test")

    async def test_network_error_raises(self):
        client = AsyncPubMedClient()

        with patch("litprism.pubmed.entrez.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=httpx.NetworkError("connection refused"))
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            with pytest.raises(PubMedNetworkError):
                await client.search("test")

    async def test_unexpected_status_raises(self):
        client = AsyncPubMedClient()
        mock_resp = _mock_response(status_code=503)

        with patch("litprism.pubmed.entrez.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            with pytest.raises(PubMedAPIError):
                await client.search("test")


class TestSyncClient:
    def test_sync_search(self):
        client = PubMedClient()
        mock_resp = _mock_response(json_data=ESEARCH_RESPONSE)

        with patch("litprism.pubmed.entrez.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            result = client.search("Crohn disease")

        assert result.pmids == ["12345678", "99999999"]
