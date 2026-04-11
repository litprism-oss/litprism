"""Raw NCBI E-utilities wrapper.

Handles esearch (query → PMIDs) and efetch (PMIDs → XML).
Rate limiting and retry logic live here.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from litprism.pubmed.exceptions import PubMedAPIError, PubMedNetworkError, PubMedRateLimitError
from litprism.pubmed.models import ArticleFilters, SearchResult

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BATCH_SIZE = 200


class TokenBucket:
    """Token-bucket rate limiter for async use."""

    def __init__(self, rate: float) -> None:
        self.rate = rate  # tokens per second
        self._tokens = rate
        self._last_refill = asyncio.get_event_loop().time()

    async def acquire(self) -> None:
        """Block until a token is available."""
        while True:
            now = asyncio.get_event_loop().time()
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

    async def _get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        """Rate-limited GET with error handling."""
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
        filters: ArticleFilters | None = None,
    ) -> SearchResult:
        """Run esearch and return PMIDs."""
        params = {
            **self._base_params(),
            "term": query,
            "retmax": max_results,
            "usehistory": "y",
        }
        if date_range:
            params["mindate"] = date_range[0]
            params["maxdate"] = date_range[1]
            params["datetype"] = "pdat"
        if filters:
            filter_parts = []
            for lang in filters.languages:
                filter_parts.append(f"{lang}[lang]")
            for at in filters.article_types:
                filter_parts.append(f'"{at}"[pt]')
            if filters.has_abstract:
                filter_parts.append("hasabstract")
            if filter_parts:
                params["term"] = f"({query}) AND ({' AND '.join(filter_parts)})"

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

    async def efetch_batch(self, pmids: list[str]) -> str:
        """Fetch a single batch of PMIDs (max 200) and return raw XML."""
        params = {
            **self._base_params(),
            "id": ",".join(pmids),
            "rettype": "xml",
            "retmode": "xml",
        }
        # Override retmode for xml fetch
        params["retmode"] = "xml"
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
