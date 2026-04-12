"""Raw Semantic Scholar Graph API wrapper.

Handles search with offset-based pagination and paper lookup.
Rate limiting and retry logic live here.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from litprism.semanticscholar.exceptions import (
    SemanticScholarAPIError,
    SemanticScholarNetworkError,
    SemanticScholarRateLimitError,
)
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}"

MAX_PAGE_SIZE = 100  # Semantic Scholar hard limit
# SS offset + limit must not exceed 10,000.
MAX_RESULTS_CAP = 10_000

# Fields to request on every call — covers all Article model attributes.
DEFAULT_FIELDS = (
    "paperId,externalIds,title,abstract,authors,year,publicationDate,"
    "journal,venue,openAccessPdf,fieldsOfStudy,publicationTypes,citationCount,isOpenAccess"
)


def _is_retryable(exc: BaseException) -> bool:
    """Return True for errors that warrant a retry (429 rate limit, 503 unavailable)."""
    return isinstance(exc, SemanticScholarRateLimitError) or (
        isinstance(exc, SemanticScholarAPIError) and exc.status_code == 503
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


class SemanticScholarAPIClient:
    """Async wrapper around the Semantic Scholar Graph API.

    Provides offset-based search pagination and paper lookup.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        rate = 10.0 if api_key else 1.0
        self._bucket = TokenBucket(rate)
        self._client: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

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
            response = await self._client.get(
                url, params=params, headers=self._headers(), timeout=30.0
            )
        except httpx.TimeoutException as exc:
            raise SemanticScholarNetworkError("Request timed out") from exc
        except httpx.NetworkError as exc:
            raise SemanticScholarNetworkError(f"Network error: {exc}") from exc
        if response.status_code == 429:
            raise SemanticScholarRateLimitError("Rate limit exceeded", status_code=429)
        if response.status_code == 503:
            raise SemanticScholarAPIError("Service unavailable", status_code=503)
        if response.status_code != 200:
            raise SemanticScholarAPIError(
                f"Unexpected status {response.status_code}",
                status_code=response.status_code,
            )
        return response

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _post(self, url: str, params: dict[str, Any], body: Any) -> httpx.Response:
        """Rate-limited POST with retry on 429/503."""
        await self._bucket.acquire()
        assert self._client is not None
        try:
            response = await self._client.post(
                url, params=params, json=body, headers=self._headers(), timeout=30.0
            )
        except httpx.TimeoutException as exc:
            raise SemanticScholarNetworkError("Request timed out") from exc
        except httpx.NetworkError as exc:
            raise SemanticScholarNetworkError(f"Network error: {exc}") from exc
        if response.status_code == 429:
            raise SemanticScholarRateLimitError("Rate limit exceeded", status_code=429)
        if response.status_code == 503:
            raise SemanticScholarAPIError("Service unavailable", status_code=503)
        if response.status_code != 200:
            raise SemanticScholarAPIError(
                f"Unexpected status {response.status_code}",
                status_code=response.status_code,
            )
        return response

    async def search_paginated(
        self,
        query: str,
        extra_params: dict[str, Any] | None = None,
        page_size: int = MAX_PAGE_SIZE,
        max_results: int = 1_000,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Stream search results using offset-based pagination.

        Args:
            query:        Semantic Scholar query string.
            extra_params: Additional filter params (publicationTypes, fieldsOfStudy, etc.).
            page_size:    Results per page (max 100).
            max_results:  Total results cap.

        Yields:
            list[dict] — raw paper dicts from `data` per page.
        """
        page_size = min(page_size, MAX_PAGE_SIZE)
        max_results = min(max_results, MAX_RESULTS_CAP)
        offset = 0

        while offset < max_results:
            limit = min(page_size, max_results - offset)
            params: dict[str, Any] = {
                "query": query,
                "fields": DEFAULT_FIELDS,
                "limit": limit,
                "offset": offset,
            }
            if extra_params:
                params.update(extra_params)

            response = await self._get(SEARCH_URL, params)
            data = response.json()

            results: list[dict[str, Any]] = data.get("data") or []
            if not results:
                break

            yield results
            offset += len(results)

            # SS signals end-of-results by omitting "next" or setting it past total
            if "next" not in data:
                break
            total = data.get("total", 0)
            if offset >= total:
                break

    async def fetch_by_ids(
        self, paper_ids: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch papers by Semantic Scholar paper IDs via the batch endpoint.

        IDs may be any format accepted by the SS API:
          - plain paperId (40-char hex)
          - "DOI:10.1234/..."
          - "PMID:12345678"
          - "ArXiv:2101.00001"

        Args:
            paper_ids: List of paper ID strings.

        Yields:
            list[dict] — raw paper dicts for each batch.
        """
        batch_size = 500  # SS batch endpoint accepts up to 500
        for i in range(0, len(paper_ids), batch_size):
            batch = paper_ids[i : i + batch_size]
            params: dict[str, Any] = {"fields": DEFAULT_FIELDS}
            response = await self._post(BATCH_URL, params, {"ids": batch})
            results: list[dict[str, Any]] = response.json()
            # Filter out None entries (SS returns null for unrecognised IDs)
            valid = [r for r in results if r is not None]
            if valid:
                yield valid

    async def __aenter__(self) -> "SemanticScholarAPIClient":
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
