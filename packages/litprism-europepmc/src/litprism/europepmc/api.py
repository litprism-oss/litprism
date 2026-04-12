"""Raw Europe PMC REST API wrapper.

Handles search with cursor-based pagination and article lookup.
Rate limiting and retry logic live here.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from litprism.europepmc.exceptions import (
    EuropePMCAPIError,
    EuropePMCNetworkError,
    EuropePMCRateLimitError,
)

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
MAX_PAGE_SIZE = 1000
# Practical cap: Europe PMC has no hard server limit, but very large cursor sessions are unreliable.
MAX_RESULTS_CAP = 100_000


def _is_retryable(exc: BaseException) -> bool:
    """Return True for errors that warrant a retry (429 rate limit, 503 unavailable)."""
    return isinstance(exc, EuropePMCRateLimitError) or (
        isinstance(exc, EuropePMCAPIError) and exc.status_code == 503
    )


class TokenBucket:
    """Token-bucket rate limiter for async use."""

    def __init__(self, rate: float) -> None:
        self.rate = rate  # tokens per second
        self._tokens = rate
        self._last_refill: float | None = None  # initialized on first acquire()

    async def acquire(self) -> None:
        """Block until a token is available."""
        loop = asyncio.get_running_loop()
        if self._last_refill is None:
            self._last_refill = loop.time()
        while True:
            now = loop.time()
            elapsed = now - self._last_refill
            self._tokens = min(self.rate, self._tokens + elapsed * self.rate)
            self._last_refill = now
            if self._tokens >= 1:
                self._tokens -= 1
                return
            await asyncio.sleep(1 / self.rate)


class EuropePMCAPIClient:
    """Async wrapper around the Europe PMC REST search endpoint.

    Provides cursor-based pagination and article lookup.
    """

    def __init__(self, api_key: str | None = None, email: str | None = None) -> None:
        self.api_key = api_key
        self.email = email
        rate = 10.0 if api_key else 3.0
        self._bucket = TokenBucket(rate)
        self._client: httpx.AsyncClient | None = None

    def _base_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"format": "json", "resultType": "core"}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        """Rate-limited GET with retry on 429/503."""
        await self._bucket.acquire()
        assert self._client is not None
        try:
            response = await self._client.get(url, params=params, timeout=30.0)
        except httpx.TimeoutException as exc:
            raise EuropePMCNetworkError("Request timed out") from exc
        except httpx.NetworkError as exc:
            raise EuropePMCNetworkError(f"Network error: {exc}") from exc
        if response.status_code == 429:
            raise EuropePMCRateLimitError("Rate limit exceeded", status_code=429)
        if response.status_code == 503:
            raise EuropePMCAPIError("Service unavailable", status_code=503)
        if response.status_code != 200:
            raise EuropePMCAPIError(
                f"Unexpected status {response.status_code}", status_code=response.status_code
            )
        return response

    async def search_paginated(
        self,
        query: str,
        synonym: str = "true",
        page_size: int = MAX_PAGE_SIZE,
        max_results: int = 10_000,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Stream search results using cursor-based pagination.

        Europe PMC uses a cursor token (cursorMark) returned in each response.
        Pagination continues until cursorMark stops changing or max_results is
        reached. The first request uses cursorMark="*".

        Args:
            query:       Full Europe PMC query string (with filters already embedded).
            synonym:     "true" or "false" — whether to expand MeSH synonyms.
            page_size:   Results per page (max 1000).
            max_results: Total results cap.

        Yields:
            list[dict] — raw result dicts from `resultList.result` per page.
        """
        page_size = min(page_size, MAX_PAGE_SIZE)
        max_results = min(max_results, MAX_RESULTS_CAP)
        cursor_mark = "*"
        fetched = 0

        while fetched < max_results:
            batch_size = min(page_size, max_results - fetched)
            params: dict[str, Any] = {
                **self._base_params(),
                "query": query,
                "pageSize": batch_size,
                "cursorMark": cursor_mark,
                "synonym": synonym,
            }
            response = await self._get(SEARCH_URL, params)
            data = response.json()

            results: list[dict[str, Any]] = data.get("resultList", {}).get("result", [])
            if not results:
                break

            yield results
            fetched += len(results)

            next_cursor = data.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor_mark:
                break
            cursor_mark = next_cursor

    async def fetch_by_ids(
        self, ids: list[tuple[str, str]]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch articles by (article_id, source) pairs via targeted search queries.

        Europe PMC has no bulk-fetch endpoint analogous to PubMed's efetch.
        Articles are retrieved by building an `EXT_ID:id AND SRC:source` query.
        Batches of up to 100 IDs are combined with OR to reduce round-trips.

        Args:
            ids: List of (article_id, source) tuples, e.g. [("33577785", "MED")].

        Yields:
            list[dict] — raw result dicts for each batch.
        """
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            batch = ids[i : i + batch_size]
            clauses = [f"(EXT_ID:{aid} AND SRC:{src})" for aid, src in batch]
            query = " OR ".join(clauses)
            params: dict[str, Any] = {
                **self._base_params(),
                "query": query,
                "pageSize": len(batch),
                "cursorMark": "*",
            }
            response = await self._get(SEARCH_URL, params)
            data = response.json()
            results: list[dict[str, Any]] = data.get("resultList", {}).get("result", [])
            if results:
                yield results

    async def __aenter__(self) -> "EuropePMCAPIClient":
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
