"""PubMed client — public API for litprism-pubmed.

AsyncPubMedClient is the primary implementation.
PubMedClient is a synchronous wrapper for non-async callers.
"""

import asyncio
from collections.abc import AsyncGenerator

from litprism.pubmed.cache import ArticleCache
from litprism.pubmed.entrez import EntrezClient
from litprism.pubmed.exceptions import PubMedAPIError
from litprism.pubmed.filters import FilterTranslator
from litprism.pubmed.models import Article, SearchFilters
from litprism.pubmed.parser import parse_xml


class AsyncPubMedClient:
    """Async PubMed client.

    Args:
        api_key: NCBI API key. Optional — raises rate limit from 3/s to 10/s.
        email:   Contact email for NCBI's polite pool. Recommended.
        cache:   Optional ArticleCache. fetch() checks the cache before hitting
                 the API and stores new results.
    """

    def __init__(
        self,
        api_key: str | None = None,
        email: str | None = None,
        cache: ArticleCache | None = None,
    ) -> None:
        self._entrez = EntrezClient(api_key=api_key, email=email)
        self._cache = cache

    async def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        max_results: int = 500,
    ) -> list[Article]:
        """Search PubMed and return a list of Article objects.

        Convenience method for small searches (max_results <= 500 recommended).
        Uses server-side history pagination internally — collects all batches
        into a single list before returning.

        For large searches use search_iter() to stream results batch-by-batch.

        Args:
            query:       PubMed boolean query string.
            filters:     Optional SearchFilters (dates, languages, pub types…).
            max_results: Maximum number of articles to return.

        Returns:
            List of Article objects.
        """
        results: list[Article] = []
        async for batch in self.search_iter(
            query=query,
            filters=filters,
            batch_size=200,
            max_results=max_results,
        ):
            results.extend(batch)
        return results

    async def search_iter(
        self,
        query: str,
        filters: SearchFilters | None = None,
        batch_size: int = 200,
        max_results: int = 10_000,
    ) -> AsyncGenerator[list[Article], None]:
        """Stream search results as batches of Article objects.

        Uses PubMed server-side history (WebEnv/query_key) with retstart-based
        batching. Each yielded batch contains up to batch_size articles.
        Total results are capped at 10,000 (NCBI hard limit).

        Args:
            query:       PubMed boolean query string.
            filters:     Optional SearchFilters.
            batch_size:  Articles per batch (max 200, NCBI hard limit).
            max_results: Total articles to fetch. Capped at 10,000.

        Yields:
            list[Article] — one batch per yield.
        """
        filters_params = FilterTranslator.to_pubmed(filters) if filters else {}
        await self._entrez.__aenter__()
        try:
            async for xml_batch in self._entrez.search_paginated(
                query=query,
                filters_params=filters_params,
                max_results=max_results,
                batch_size=batch_size,
            ):
                yield parse_xml(xml_batch)
        finally:
            await self._entrez.__aexit__(None, None, None)

    async def get(self, pmid: str) -> Article:
        """Fetch a single article by PMID.

        Args:
            pmid: PubMed ID string.

        Returns:
            Article object.

        Raises:
            PubMedAPIError: If the PMID is not found.
        """
        articles = await self.fetch([pmid])
        if not articles:
            raise PubMedAPIError(f"Article not found: {pmid}")
        return articles[0]

    async def fetch(self, pmids: list[str]) -> list[Article]:
        """Fetch full article records for a list of PMIDs.

        Checks the cache first (if configured). Fetches missing PMIDs from the
        API in batches of 200, then stores results in the cache.

        Args:
            pmids: List of PubMed IDs to fetch.

        Returns:
            List of Article objects, in no guaranteed order.
        """
        if not pmids:
            return []

        cached: dict[str, Article] = {}
        to_fetch = list(pmids)

        if self._cache:
            cached = self._cache.get_many(pmids)
            to_fetch = [p for p in pmids if p not in cached]

        fetched: list[Article] = []
        if to_fetch:
            async with self._entrez:
                xml_pages = await self._entrez.efetch(to_fetch)
            for xml in xml_pages:
                fetched.extend(parse_xml(xml))
            if self._cache and fetched:
                self._cache.set_many(fetched)

        return list(cached.values()) + fetched


class PubMedClient:
    """Synchronous wrapper around AsyncPubMedClient.

    Runs the async client in a new event loop. Use this for scripts and
    notebooks where async/await is not available.

    search_iter() returns the underlying async generator directly —
    use it with `async for` in an async context.
    """

    def __init__(
        self,
        api_key: str | None = None,
        email: str | None = None,
        cache: ArticleCache | None = None,
    ) -> None:
        self._async = AsyncPubMedClient(api_key=api_key, email=email, cache=cache)

    def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        max_results: int = 500,
    ) -> list[Article]:
        """Synchronous search. See AsyncPubMedClient.search for details."""
        return asyncio.run(
            self._async.search(
                query=query,
                filters=filters,
                max_results=max_results,
            )
        )

    def search_iter(
        self,
        query: str,
        filters: SearchFilters | None = None,
        batch_size: int = 200,
        max_results: int = 10_000,
    ) -> AsyncGenerator[list[Article], None]:
        """Return the async generator for streaming. Use with `async for`."""
        return self._async.search_iter(
            query=query,
            filters=filters,
            batch_size=batch_size,
            max_results=max_results,
        )

    def get(self, pmid: str) -> Article:
        """Synchronous single-article fetch. See AsyncPubMedClient.get."""
        return asyncio.run(self._async.get(pmid))

    def fetch(self, pmids: list[str]) -> list[Article]:
        """Synchronous fetch. See AsyncPubMedClient.fetch."""
        return asyncio.run(self._async.fetch(pmids))
