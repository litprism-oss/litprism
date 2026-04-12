"""Unit tests for litprism-semanticscholar client (httpx mocked)."""

import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from litprism.semanticscholar.client import AsyncSemanticScholarClient, SemanticScholarClient
from litprism.semanticscholar.exceptions import SemanticScholarAPIError
from litprism.semanticscholar.models import SearchFilters

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _mock_response(json_data: dict | list | None = None, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


def _mock_http(
    get_side_effects: list | None = None, post_side_effects: list | None = None
) -> AsyncMock:
    """Build a mock httpx.AsyncClient."""
    mock = AsyncMock()
    if get_side_effects is not None:
        mock.get = AsyncMock(side_effect=get_side_effects)
    if post_side_effects is not None:
        mock.post = AsyncMock(side_effect=post_side_effects)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


def _single_page(name: str) -> dict:
    """Load a search fixture with `next` removed so pagination stops after one page."""
    data = _load(name)
    data.pop("next", None)
    return data


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestAsyncSemanticScholarClientInit:
    def test_default_init(self):
        client = AsyncSemanticScholarClient()
        assert client._api_key is None

    def test_init_with_api_key(self):
        client = AsyncSemanticScholarClient(api_key="key123")
        assert client._api_key == "key123"


# ---------------------------------------------------------------------------
# AsyncSemanticScholarClient.search
# ---------------------------------------------------------------------------


class TestAsyncSemanticScholarClientSearch:
    async def test_search_returns_articles(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http(get_side_effects=[_mock_response(json_data=data)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            results = await client.search("CRISPR gene editing")

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].pmid == "33577785"
        assert results[0].source == "semanticscholar"

    async def test_search_returns_empty_list_when_no_results(self):
        data = _load("search_empty_result.json")
        mock_http = _mock_http(get_side_effects=[_mock_response(json_data=data)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            results = await client.search("unlikely_query_xyz")

        assert results == []

    async def test_search_sends_query_param(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http(get_side_effects=[_mock_response(json_data=data)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            await client.search("CRISPR")

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert call_params["query"] == "CRISPR"

    async def test_search_respects_max_results(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http(get_side_effects=[_mock_response(json_data=data)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            await client.search("cancer", max_results=10)

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert call_params["limit"] <= 10

    async def test_search_sends_filter_params(self):
        """Filter params appear in the GET call."""
        data = _single_page("search_single_result.json")
        mock_http = _mock_http(get_side_effects=[_mock_response(json_data=data)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            await client.search(
                "cancer",
                filters=SearchFilters(semanticscholar_fields_of_study=["Medicine"]),
            )

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert call_params.get("fieldsOfStudy") == "Medicine"


# ---------------------------------------------------------------------------
# AsyncSemanticScholarClient.search_iter
# ---------------------------------------------------------------------------


class TestAsyncSemanticScholarClientSearchIter:
    async def test_search_iter_yields_batches(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http(get_side_effects=[_mock_response(json_data=data)])

        batches = []
        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            async for batch in client.search_iter("probiotic"):
                batches.append(batch)

        assert len(batches) == 1
        assert all(isinstance(b, list) for b in batches)

    async def test_search_iter_empty_results(self):
        data = _load("search_empty_result.json")
        mock_http = _mock_http(get_side_effects=[_mock_response(json_data=data)])

        batches = []
        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            async for batch in client.search_iter("nothing"):
                batches.append(batch)

        assert batches == []

    async def test_search_iter_paginates_multiple_pages(self):
        page1 = _load("search_single_result.json")
        page1["next"] = 1
        page1["total"] = 2
        page2 = _load("search_page2.json")
        page2.pop("next", None)  # no next → stop

        mock_http = _mock_http(
            get_side_effects=[_mock_response(json_data=page1), _mock_response(json_data=page2)]
        )

        batches = []
        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            async for batch in client.search_iter("cancer", max_results=2):
                batches.append(batch)

        assert len(batches) == 2
        assert mock_http.get.call_count == 2


# ---------------------------------------------------------------------------
# AsyncSemanticScholarClient.fetch
# ---------------------------------------------------------------------------


class TestAsyncSemanticScholarClientFetch:
    async def test_fetch_returns_articles(self):
        raw_list = _load("search_single_result.json")["data"]
        mock_http = _mock_http(post_side_effects=[_mock_response(json_data=raw_list)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            articles = await client.fetch(["a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"])

        assert len(articles) == 1
        assert articles[0].pmid == "33577785"

    async def test_fetch_empty_list_returns_empty(self):
        client = AsyncSemanticScholarClient()
        articles = await client.fetch([])
        assert articles == []

    async def test_fetch_sends_ids_in_post_body(self):
        raw_list = _load("search_single_result.json")["data"]
        mock_http = _mock_http(post_side_effects=[_mock_response(json_data=raw_list)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            await client.fetch(["a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"])

        call_kwargs = mock_http.post.call_args_list[0][1]
        assert call_kwargs["json"]["ids"] == ["a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"]


# ---------------------------------------------------------------------------
# AsyncSemanticScholarClient.get
# ---------------------------------------------------------------------------


class TestAsyncSemanticScholarClientGet:
    async def test_get_returns_single_article(self):
        raw_list = _load("search_single_result.json")["data"]
        mock_http = _mock_http(post_side_effects=[_mock_response(json_data=raw_list)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = AsyncSemanticScholarClient()
            article = await client.get("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2")

        assert article.pmid == "33577785"

    async def test_get_raises_when_not_found(self):
        mock_http = _mock_http(post_side_effects=[_mock_response(json_data=[])])

        with (
            patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http),
            pytest.raises(SemanticScholarAPIError, match="not found"),
        ):
            client = AsyncSemanticScholarClient()
            await client.get("nonexistent_paper_id")


# ---------------------------------------------------------------------------
# SemanticScholarClient — synchronous wrapper
# ---------------------------------------------------------------------------


class TestSyncClient:
    def test_sync_search_returns_articles(self):
        data = _single_page("search_single_result.json")
        mock_http = _mock_http(get_side_effects=[_mock_response(json_data=data)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = SemanticScholarClient()
            results = client.search("CRISPR")

        assert isinstance(results, list)
        assert len(results) == 1

    def test_sync_get_returns_article(self):
        raw_list = _load("search_single_result.json")["data"]
        mock_http = _mock_http(post_side_effects=[_mock_response(json_data=raw_list)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = SemanticScholarClient()
            article = client.get("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2")

        assert article.pmid == "33577785"

    def test_sync_fetch_returns_articles(self):
        raw_list = _load("search_single_result.json")["data"]
        mock_http = _mock_http(post_side_effects=[_mock_response(json_data=raw_list)])

        with patch("litprism.semanticscholar.api.httpx.AsyncClient", return_value=mock_http):
            client = SemanticScholarClient()
            articles = client.fetch(["a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"])

        assert len(articles) == 1

    def test_sync_search_iter_returns_async_generator(self):
        """search_iter on the sync client returns the underlying async generator."""
        client = SemanticScholarClient()
        gen = client.search_iter("CRISPR")
        assert inspect.isasyncgen(gen)
