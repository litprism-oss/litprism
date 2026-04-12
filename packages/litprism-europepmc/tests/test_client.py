"""Unit tests for litprism-europepmc client (httpx mocked)."""

import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from litprism.europepmc.client import AsyncEuropePMCClient, EuropePMCClient
from litprism.europepmc.exceptions import EuropePMCAPIError
from litprism.europepmc.models import SearchFilters

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _mock_response(json_data: dict | None = None, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


def _mock_http(side_effects: list) -> AsyncMock:
    """Build a mock httpx.AsyncClient whose .get() cycles through side_effects."""
    mock = AsyncMock()
    mock.get = AsyncMock(side_effect=side_effects)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


def _single_page(name: str, next_cursor: str = "*") -> dict:
    """Load a search fixture and override nextCursorMark so pagination stops."""
    data = _load(name)
    data["nextCursorMark"] = next_cursor
    return data


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestAsyncEuropePMCClientInit:
    def test_default_init(self):
        client = AsyncEuropePMCClient()
        assert client._api_key is None
        assert client._email is None

    def test_init_with_credentials(self):
        client = AsyncEuropePMCClient(api_key="key123", email="test@example.com")
        assert client._api_key == "key123"
        assert client._email == "test@example.com"


# ---------------------------------------------------------------------------
# _build_query
# ---------------------------------------------------------------------------


class TestBuildQuery:
    def test_no_filters_returns_query_unchanged(self):
        client = AsyncEuropePMCClient()
        result = client._build_query("cancer prognosis", None)
        assert result == "cancer prognosis"

    def test_filters_appended_as_and(self):
        client = AsyncEuropePMCClient()
        filters = SearchFilters(has_abstract=True, europepmc_sources=[])
        result = client._build_query("cancer", filters)
        assert result.startswith("(cancer) AND")
        assert "HAS_ABSTRACT:Y" in result

    def test_empty_filter_query_returns_base_query(self):
        client = AsyncEuropePMCClient()
        filters = SearchFilters(europepmc_sources=[], europepmc_mesh_synonyms=True)
        result = client._build_query("cancer", filters)
        assert result == "cancer"


# ---------------------------------------------------------------------------
# AsyncEuropePMCClient.search
# ---------------------------------------------------------------------------


class TestAsyncEuropePMCClientSearch:
    async def test_search_returns_articles(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            results = await client.search("probiotic Crohn disease")

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].pmid == "33577785"
        assert results[0].source == "europepmc"

    async def test_search_returns_empty_list_when_no_results(self):
        data = _load("search_empty_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            results = await client.search("unlikely_query_xyz")

        assert results == []

    async def test_search_embeds_filter_in_query(self):
        """Filters are embedded in the query string sent to the API."""
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            await client.search(
                "cancer",
                filters=SearchFilters(has_abstract=True, europepmc_sources=[]),
            )

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert "HAS_ABSTRACT:Y" in call_params["query"]
        assert "(cancer)" in call_params["query"]

    async def test_search_passes_synonym_param(self):
        """synonym param is derived from SearchFilters.europepmc_mesh_synonyms."""
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            await client.search(
                "cancer",
                filters=SearchFilters(europepmc_mesh_synonyms=False, europepmc_sources=[]),
            )

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert call_params["synonym"] == "false"

    async def test_search_respects_max_results(self):
        """pageSize is capped at max_results on the first request."""
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            await client.search("cancer", max_results=10)

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert call_params["pageSize"] <= 10


# ---------------------------------------------------------------------------
# AsyncEuropePMCClient.search_iter
# ---------------------------------------------------------------------------


class TestAsyncEuropePMCClientSearchIter:
    async def test_search_iter_yields_batches(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        batches = []
        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            async for batch in client.search_iter("probiotic"):
                batches.append(batch)

        assert len(batches) == 1
        assert all(isinstance(b, list) for b in batches)

    async def test_search_iter_empty_results(self):
        data = _load("search_empty_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        batches = []
        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            async for batch in client.search_iter("nothing"):
                batches.append(batch)

        assert batches == []

    async def test_search_iter_paginates_multiple_pages(self):
        page1 = _load("search_single_result.json")
        page1["nextCursorMark"] = "AoE="
        page2 = _load("search_page2.json")
        page2["nextCursorMark"] = "AoE="  # same → stop

        mock_http = _mock_http([_mock_response(json_data=page1), _mock_response(json_data=page2)])

        batches = []
        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            async for batch in client.search_iter("cancer"):
                batches.append(batch)

        assert len(batches) == 2
        assert mock_http.get.call_count == 2

    async def test_search_iter_no_filters_sends_default_synonym(self):
        """No filters → synonym defaults to 'true'."""
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            async for _ in client.search_iter("cancer"):
                pass

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert call_params["synonym"] == "true"


# ---------------------------------------------------------------------------
# AsyncEuropePMCClient.fetch
# ---------------------------------------------------------------------------


class TestAsyncEuropePMCClientFetch:
    async def test_fetch_returns_articles(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            articles = await client.fetch([("33577785", "MED")])

        assert len(articles) == 1
        assert articles[0].pmid == "33577785"

    async def test_fetch_empty_list_returns_empty(self):
        client = AsyncEuropePMCClient()
        articles = await client.fetch([])
        assert articles == []

    async def test_fetch_builds_ext_id_query(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            await client.fetch([("33577785", "MED")])

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert "EXT_ID:33577785" in call_params["query"]
        assert "SRC:MED" in call_params["query"]


# ---------------------------------------------------------------------------
# AsyncEuropePMCClient.get
# ---------------------------------------------------------------------------


class TestAsyncEuropePMCClientGet:
    async def test_get_returns_single_article(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncEuropePMCClient()
            article = await client.get("33577785", source="MED")

        assert article.pmid == "33577785"

    async def test_get_raises_when_not_found(self):
        data = _load("search_empty_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with (
            patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http),
            pytest.raises(EuropePMCAPIError, match="not found"),
        ):
            client = AsyncEuropePMCClient()
            await client.get("00000000")


# ---------------------------------------------------------------------------
# EuropePMCClient — synchronous wrapper
# ---------------------------------------------------------------------------


class TestSyncClient:
    def test_sync_search_returns_articles(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = EuropePMCClient()
            results = client.search("probiotic")

        assert isinstance(results, list)
        assert len(results) == 1

    def test_sync_get_returns_article(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = EuropePMCClient()
            article = client.get("33577785", source="MED")

        assert article.pmid == "33577785"

    def test_sync_fetch_returns_articles(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        with patch("litprism.europepmc.api.httpx.AsyncClient", return_value=mock_http):
            client = EuropePMCClient()
            articles = client.fetch([("33577785", "MED")])

        assert len(articles) == 1

    def test_sync_search_iter_returns_async_generator(self):
        """search_iter on the sync client returns the underlying async generator."""
        client = EuropePMCClient()
        gen = client.search_iter("probiotic")
        assert inspect.isasyncgen(gen)
