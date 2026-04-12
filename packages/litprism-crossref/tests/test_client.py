"""Unit tests for AsyncCrossrefClient — no real network calls."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from litprism.crossref.client import AsyncCrossrefClient, _build_user_agent
from litprism.crossref.exceptions import (
    CrossrefAPIError,
    CrossrefNetworkError,
    CrossrefNotFoundError,
    CrossrefParseError,
    CrossrefRateLimitError,
)
from litprism.crossref.models import CrossrefMetadata

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(fixture: str, status_code: int = 200) -> MagicMock:
    body = json.loads((FIXTURES / fixture).read_text())
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body
    return resp


def _make_http_client(fixture: str, status_code: int = 200) -> MagicMock:
    """Return a context-manager mock whose .get() returns a fixture response."""
    resp = _mock_response(fixture, status_code)
    http = AsyncMock()
    http.__aenter__ = AsyncMock(return_value=http)
    http.__aexit__ = AsyncMock(return_value=False)
    http.get = AsyncMock(return_value=resp)
    return http


def _make_http_client_status(status_code: int) -> MagicMock:
    """Return a context-manager mock whose .get() returns a bare status code."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    http = AsyncMock()
    http.__aenter__ = AsyncMock(return_value=http)
    http.__aexit__ = AsyncMock(return_value=False)
    http.get = AsyncMock(return_value=resp)
    return http


# ---------------------------------------------------------------------------
# User-Agent
# ---------------------------------------------------------------------------


def test_user_agent_with_mailto() -> None:
    ua = _build_user_agent("test@example.com")
    assert "mailto:test@example.com" in ua
    assert "litprism-crossref" in ua


def test_user_agent_without_mailto() -> None:
    ua = _build_user_agent(None)
    assert "mailto" not in ua
    assert "litprism-crossref" in ua


# ---------------------------------------------------------------------------
# enrich_by_doi — happy path (via _do_enrich to avoid retry backoff)
# ---------------------------------------------------------------------------


async def test_enrich_full_fixture() -> None:
    client = AsyncCrossrefClient(mailto="test@example.com")
    http = _make_http_client("work.json")

    with patch("litprism.crossref.client.httpx.AsyncClient", return_value=http):
        meta = await client._do_enrich("10.1038/s41586-021-03819-2")

    assert isinstance(meta, CrossrefMetadata)
    assert meta.doi == "10.1038/s41586-021-03819-2"
    assert meta.title == "Highly accurate protein structure prediction with AlphaFold"
    assert meta.journal == "Nature"
    assert meta.publisher == "Springer Science and Business Media LLC"
    assert meta.publication_year == 2021
    assert meta.publication_date is not None
    assert meta.publication_date.year == 2021
    assert meta.publication_date.month == 7
    assert meta.publication_date.day == 15
    assert meta.citation_count == 12000
    assert meta.references_count == 48
    assert meta.open_access is True
    assert "https://creativecommons.org" in (meta.license_url or "")
    assert len(meta.authors) == 2
    assert meta.authors[0].given == "John"
    assert meta.authors[0].family == "Jumper"
    assert meta.authors[0].affiliation == "DeepMind, London, UK"
    assert meta.authors[0].orcid == "https://orcid.org/0000-0001-6169-6580"
    assert meta.authors[1].affiliation is None
    assert meta.issn == ["0028-0836", "1476-4687"]
    assert meta.subjects == ["Multidisciplinary"]
    assert meta.work_type == "journal-article"


async def test_enrich_minimal_fixture() -> None:
    client = AsyncCrossrefClient()
    http = _make_http_client("work_minimal.json")

    with patch("litprism.crossref.client.httpx.AsyncClient", return_value=http):
        meta = await client._do_enrich("10.1000/xyz123")

    assert meta.doi == "10.1000/xyz123"
    assert meta.title is None
    assert meta.authors == []
    assert meta.open_access is False
    assert meta.citation_count is None


async def test_doi_prefix_stripped() -> None:
    """https://doi.org/ prefix must be stripped before building the URL."""
    client = AsyncCrossrefClient(mailto="test@example.com")
    http = _make_http_client("work.json")

    with patch("litprism.crossref.client.httpx.AsyncClient", return_value=http):
        meta = await client.enrich_by_doi("https://doi.org/10.1038/s41586-021-03819-2")

    assert meta.doi == "10.1038/s41586-021-03819-2"
    called_url: str = http.get.call_args[0][0]
    assert "https://doi.org" not in called_url


# ---------------------------------------------------------------------------
# enrich_by_doi — error handling (via _do_enrich to avoid retry backoff)
# ---------------------------------------------------------------------------


async def test_raises_not_found_on_404() -> None:
    client = AsyncCrossrefClient()
    http = _make_http_client_status(404)

    with (
        patch("litprism.crossref.client.httpx.AsyncClient", return_value=http),
        pytest.raises(CrossrefNotFoundError),
    ):
        await client._do_enrich("10.0000/doesnotexist")


async def test_raises_rate_limit_on_429() -> None:
    client = AsyncCrossrefClient()
    http = _make_http_client_status(429)

    with (
        patch("litprism.crossref.client.httpx.AsyncClient", return_value=http),
        pytest.raises(CrossrefRateLimitError),
    ):
        await client._do_enrich("10.0000/ratelimited")


async def test_raises_api_error_on_500() -> None:
    client = AsyncCrossrefClient()
    http = _make_http_client_status(500)

    with (
        patch("litprism.crossref.client.httpx.AsyncClient", return_value=http),
        pytest.raises(CrossrefAPIError),
    ):
        await client._do_enrich("10.0000/servererror")


async def test_raises_network_error_on_timeout() -> None:
    client = AsyncCrossrefClient()
    http = AsyncMock()
    http.__aenter__ = AsyncMock(return_value=http)
    http.__aexit__ = AsyncMock(return_value=False)
    http.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with (
        patch("litprism.crossref.client.httpx.AsyncClient", return_value=http),
        pytest.raises(CrossrefNetworkError),
    ):
        await client._do_enrich("10.0000/timeout")


async def test_raises_parse_error_on_bad_json() -> None:
    client = AsyncCrossrefClient()
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.side_effect = ValueError("bad json")
    http = AsyncMock()
    http.__aenter__ = AsyncMock(return_value=http)
    http.__aexit__ = AsyncMock(return_value=False)
    http.get = AsyncMock(return_value=resp)

    with (
        patch("litprism.crossref.client.httpx.AsyncClient", return_value=http),
        pytest.raises(CrossrefParseError),
    ):
        await client._do_enrich("10.0000/badjson")
