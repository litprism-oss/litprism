"""Raw NCBI E-utilities wrapper.

Handles esearch (query → PMIDs) and efetch (PMIDs → XML).
Rate limiting and retry logic live here.
"""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import httpx
from litprism.pubmed.exceptions import PubMedAPIError, PubMedNetworkError, PubMedRateLimitError
from litprism.pubmed.filters import FilterTranslator
from litprism.pubmed.models import SearchFilters, SearchResult
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BATCH_SIZE = 200
MAX_RESULTS_CAP = 10_000  # NCBI hard limit per query


def _is_retryable(exc: BaseException) -> bool:
    """Return True for errors that warrant a retry (429 rate limit, 503 unavailable)."""
    return isinstance(exc, PubMedRateLimitError) or (
        isinstance(exc, PubMedAPIError) and exc.status_code == 503
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


class EntrezClient:
    """Async wrapper around NCBI E-utilities esearch and efetch."""

    def __init__(self, api_key: str | None = None, email: str | None = None) -> None:
        self.api_key = api_key
        self.email = email
        rate = 10.0 if api_key else 3.0
        self._bucket = TokenBucket(rate)
        self._client: httpx.AsyncClient | None = None

    def _base_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"db": "pubmed", "retmode": "json"}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email
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
            raise PubMedNetworkError("Request timed out") from exc
        except httpx.NetworkError as exc:
            raise PubMedNetworkError(f"Network error: {exc}") from exc
        if response.status_code == 429:
            raise PubMedRateLimitError("Rate limit exceeded", status_code=429)
        if response.status_code == 503:
            raise PubMedAPIError("Service unavailable", status_code=503)
        if response.status_code != 200:
            raise PubMedAPIError(
                f"Unexpected status {response.status_code}", status_code=response.status_code
            )
        return response

    async def esearch(
        self,
        query: str,
        max_results: int = 500,
        date_range: tuple[str, str] | None = None,
        filters: SearchFilters | None = None,
    ) -> SearchResult:
        """Run esearch and return a SearchResult containing PMIDs.

        Filters are translated via FilterTranslator.to_pubmed(). The legacy
        date_range tuple param is still accepted for backward compatibility and
        overrides any date set in filters.date_range.
        """
        params: dict[str, Any] = {
            **self._base_params(),
            "term": query,
            "retmax": max_results,
            "usehistory": "y",
        }

        if filters:
            filter_params = FilterTranslator.to_pubmed(filters)
            filter_query = filter_params.get("filter_query")
            # Apply date/datetype params from FilterTranslator (skip filter_query key)
            for key, value in filter_params.items():
                if key != "filter_query":
                    params[key] = value
            if filter_query:
                params["term"] = f"({query}) AND {filter_query}"

        # Legacy tuple param overrides any date from filters
        if date_range:
            params["mindate"] = date_range[0]
            params["maxdate"] = date_range[1]
            params["datetype"] = "pdat"

        response = await self._get(ESEARCH_URL, params)
        data = response.json()
        result = data.get("esearchresult", {})
        pmids = result.get("idlist", [])
        total = int(result.get("count", 0))
        return SearchResult(
            query=query,
            pmids=pmids,
            total_count=total,
            retrieved_count=len(pmids),
            searched_at=datetime.now(UTC),
        )

    async def search_paginated(
        self,
        query: str,
        filters_params: dict[str, Any],
        max_results: int,
        batch_size: int = BATCH_SIZE,
    ) -> AsyncGenerator[str, None]:
        """Stream full article XML in batches using PubMed server-side history.

        Two-step approach per spec §8:
          Step 1 — esearch with usehistory=y, retmax=0: stores results on the
                   NCBI history server, returns WebEnv + query_key + total count.
          Step 2 — efetch loop using WebEnv/query_key + retstart offset:
                   fetches up to batch_size articles per call, yields raw XML.

        Args:
            query:          PubMed boolean query string.
            filters_params: Output of FilterTranslator.to_pubmed(). The
                            'filter_query' key (if present) is AND-ed into the
                            query term; remaining keys are passed as API params.
            max_results:    Maximum articles to fetch. Capped at 10,000.
            batch_size:     Articles per efetch call. Max 200 (NCBI hard limit).

        Yields:
            Raw XML string for each batch of up to batch_size articles.
        """
        # Separate the query-fragment from the API-level params
        filter_query = filters_params.get("filter_query")
        term = f"({query}) AND {filter_query}" if filter_query else query
        extra_params = {k: v for k, v in filters_params.items() if k != "filter_query"}

        # Step 1: store results on NCBI history server
        search_params: dict[str, Any] = {
            **self._base_params(),
            "term": term,
            "usehistory": "y",
            "retmax": 0,  # count only — IDs fetched in step 2
            **extra_params,
        }
        response = await self._get(ESEARCH_URL, search_params)
        data = response.json()
        result = data.get("esearchresult", {})

        total = min(int(result.get("count", 0)), max_results, MAX_RESULTS_CAP)
        web_env: str = result.get("webenv", "")
        query_key: str = result.get("querykey", "")

        # Step 2: fetch in batches from history server
        retstart = 0
        while retstart < total:
            batch_actual = min(batch_size, total - retstart)
            fetch_params: dict[str, Any] = {
                **self._base_params(),
                "WebEnv": web_env,
                "query_key": query_key,
                "retstart": retstart,
                "retmax": batch_actual,
                "rettype": "xml",
                "retmode": "xml",  # overrides _base_params retmode=json
            }
            fetch_response = await self._get(EFETCH_URL, fetch_params)
            yield fetch_response.text
            retstart += batch_actual

    async def efetch_batch(self, pmids: list[str]) -> str:
        """Fetch a single batch of PMIDs (max 200) and return raw XML."""
        params: dict[str, Any] = {
            **self._base_params(),
            "id": ",".join(pmids),
            "rettype": "xml",
            "retmode": "xml",  # overrides _base_params retmode=json
        }
        response = await self._get(EFETCH_URL, params)
        return response.text

    async def efetch(self, pmids: list[str]) -> list[str]:
        """Fetch all PMIDs in batches of 200, return list of XML strings."""
        batches = [pmids[i : i + BATCH_SIZE] for i in range(0, len(pmids), BATCH_SIZE)]
        results = []
        for batch in batches:
            xml = await self.efetch_batch(batch)
            results.append(xml)
        return results

    async def __aenter__(self) -> "EntrezClient":
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
