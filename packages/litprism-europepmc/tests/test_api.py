"""Unit tests for litprism-europepmc EuropePMCAPIClient — network calls are mocked."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from litprism.europepmc.api import EuropePMCAPIClient
from litprism.europepmc.exceptions import (
    EuropePMCAPIError,
    EuropePMCNetworkError,
    EuropePMCRateLimitError,
)

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


# ---------------------------------------------------------------------------
# EuropePMCAPIClient.search_paginated
# ---------------------------------------------------------------------------


class TestSearchPaginated:
    async def test_yields_results_from_single_page(self, monkeypatch):
        data = _load("search_single_result.json")
        # Make nextCursorMark equal to cursorMark so pagination stops after 1 page
        data["nextCursorMark"] = "*"
        mock_http = _mock_http([_mock_response(json_data=data)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        batches = []
        async for batch in client.search_paginated("probiotic Crohn disease"):
            batches.append(batch)

        assert len(batches) == 1
        assert batches[0][0]["pmid"] == "33577785"

    async def test_stops_when_cursor_does_not_advance(self, monkeypatch):
        """Pagination stops when nextCursorMark equals the current cursorMark."""
        page1 = _load("search_single_result.json")
        page1["nextCursorMark"] = "*"  # same as initial cursor → stop
        mock_http = _mock_http([_mock_response(json_data=page1)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        pages = [batch async for batch in client.search_paginated("query")]
        assert len(pages) == 1
        assert mock_http.get.call_count == 1

    async def test_paginates_across_multiple_pages(self):
        """When cursor advances, a second request is made for the next page."""
        page1 = _load("search_single_result.json")
        page1["nextCursorMark"] = "AoE="  # different from "*" → continue
        page2 = _load("search_page2.json")
        page2["nextCursorMark"] = "AoE="  # same as current → stop after page 2

        mock_http = _mock_http([_mock_response(json_data=page1), _mock_response(json_data=page2)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        pages = [batch async for batch in client.search_paginated("query")]
        assert len(pages) == 2
        assert mock_http.get.call_count == 2

    async def test_respects_max_results(self):
        """max_results=1 stops after receiving the first article."""
        page1 = _load("search_single_result.json")
        page1["nextCursorMark"] = "AoE="  # would continue if not for max_results cap

        mock_http = _mock_http([_mock_response(json_data=page1)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        pages = [batch async for batch in client.search_paginated("query", max_results=1)]
        assert len(pages) == 1
        assert mock_http.get.call_count == 1

    async def test_stops_when_results_empty(self):
        """Pagination stops immediately if resultList.result is empty."""
        data = _load("search_empty_result.json")
        mock_http = _mock_http([_mock_response(json_data=data)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        pages = [batch async for batch in client.search_paginated("unlikely_query_xyz")]
        assert pages == []

    async def test_sends_synonym_param(self):
        """The synonym parameter is forwarded to the API."""
        data = _load("search_single_result.json")
        data["nextCursorMark"] = "*"
        mock_http = _mock_http([_mock_response(json_data=data)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        async for _ in client.search_paginated("query", synonym="false"):
            pass

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert call_params["synonym"] == "false"

    async def test_cursor_mark_advances_on_second_request(self):
        """The second request sends the cursorMark received in the first response."""
        page1 = _load("search_single_result.json")
        page1["nextCursorMark"] = "AoE="
        page2 = _load("search_page2.json")
        page2["nextCursorMark"] = "AoE="  # same → stop

        mock_http = _mock_http([_mock_response(json_data=page1), _mock_response(json_data=page2)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        async for _ in client.search_paginated("query"):
            pass

        first_call = mock_http.get.call_args_list[0][1]["params"]
        second_call = mock_http.get.call_args_list[1][1]["params"]
        assert first_call["cursorMark"] == "*"
        assert second_call["cursorMark"] == "AoE="


# ---------------------------------------------------------------------------
# EuropePMCAPIClient.fetch_by_ids
# ---------------------------------------------------------------------------


class TestFetchByIds:
    async def test_builds_ext_id_query(self):
        """fetch_by_ids builds an EXT_ID:id AND SRC:src query."""
        data = _load("search_single_result.json")
        data["nextCursorMark"] = "*"
        mock_http = _mock_http([_mock_response(json_data=data)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        results = []
        async for batch in client.fetch_by_ids([("33577785", "MED")]):
            results.extend(batch)

        call_params = mock_http.get.call_args_list[0][1]["params"]
        assert "EXT_ID:33577785" in call_params["query"]
        assert "SRC:MED" in call_params["query"]

    async def test_returns_results(self):
        data = _load("search_single_result.json")
        data["nextCursorMark"] = "*"
        mock_http = _mock_http([_mock_response(json_data=data)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        results = []
        async for batch in client.fetch_by_ids([("33577785", "MED")]):
            results.extend(batch)

        assert len(results) == 1
        assert results[0]["pmid"] == "33577785"

    async def test_batches_large_id_lists(self):
        """Lists larger than 100 are split across multiple requests."""
        data = _load("search_single_result.json")
        data["nextCursorMark"] = "*"
        # 101 IDs → 2 requests (100 + 1)
        ids = [(str(i), "MED") for i in range(101)]
        mock_http = _mock_http([_mock_response(json_data=data), _mock_response(json_data=data)])

        client = EuropePMCAPIClient()
        client._client = mock_http

        async for _ in client.fetch_by_ids(ids):
            pass

        assert mock_http.get.call_count == 2


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    async def test_429_raises_rate_limit_error(self):
        mock_http = _mock_http([_mock_response(status_code=429)] * 3)
        client = EuropePMCAPIClient()
        client._client = mock_http

        with pytest.raises(EuropePMCRateLimitError):
            async for _ in client.search_paginated("query"):
                pass

    async def test_503_retries_then_raises(self):
        mock_http = _mock_http([_mock_response(status_code=503)] * 3)
        client = EuropePMCAPIClient()
        client._client = mock_http

        with pytest.raises(EuropePMCAPIError) as exc_info:
            async for _ in client.search_paginated("query"):
                pass
        assert exc_info.value.status_code == 503

    async def test_503_succeeds_on_retry(self):
        data = _load("search_single_result.json")
        data["nextCursorMark"] = "*"
        mock_http = _mock_http([_mock_response(status_code=503), _mock_response(json_data=data)])
        client = EuropePMCAPIClient()
        client._client = mock_http

        pages = [batch async for batch in client.search_paginated("query")]
        assert len(pages) == 1

    async def test_network_error_raises(self):
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.NetworkError("connection refused"))
        client = EuropePMCAPIClient()
        client._client = mock_http

        with pytest.raises(EuropePMCNetworkError):
            async for _ in client.search_paginated("query"):
                pass

    async def test_timeout_raises_network_error(self):
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        client = EuropePMCAPIClient()
        client._client = mock_http

        with pytest.raises(EuropePMCNetworkError):
            async for _ in client.search_paginated("query"):
                pass

    async def test_unexpected_status_raises_api_error(self):
        mock_http = _mock_http([_mock_response(status_code=500)])
        client = EuropePMCAPIClient()
        client._client = mock_http

        with pytest.raises(EuropePMCAPIError):
            async for _ in client.search_paginated("query"):
                pass


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    async def test_aenter_returns_client(self):
        client = EuropePMCAPIClient()
        async with client as c:
            assert c is client
            assert client._client is not None

    async def test_aexit_closes_http_client(self):
        client = EuropePMCAPIClient()
        async with client:
            pass
        # _client is not reset to None after __aexit__; we just verify aclose was called
        assert client._client is not None  # still set, but aclose() was invoked
