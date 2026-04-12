"""Semantic Scholar client — public API for litprism-semanticscholar.

AsyncSemanticScholarClient is the primary implementation.
SemanticScholarClient is a synchronous wrapper for non-async callers.
"""

import asyncio
from collections.abc import AsyncGenerator

from litprism.semanticscholar.api import SemanticScholarAPIClient
from litprism.semanticscholar.exceptions import SemanticScholarAPIError
from litprism.semanticscholar.filters import FilterTranslator
from litprism.semanticscholar.models import Article, SearchFilters
from litprism.semanticscholar.parser import parse_results


class AsyncSemanticScholarClient:
    """Async Semantic Scholar client.

    Args:
        api_key: Semantic Scholar API key. Optional — raises rate limit from 1/s to 10/s.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    async def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        max_results: int = 500,
    ) -> list[Article]:
        """Search Semantic Scholar and return a list of Article objects.

        Convenience method for small searches (max_results <= 1000 recommended).
        Uses offset-based pagination internally — collects all pages into a
        single list before returning.

        For large searches use search_iter() to stream results page-by-page.

        Args:
            query:       Semantic Scholar query string.
            filters:     Optional SearchFilters (dates, fields of study, pub types…).
            max_results: Maximum number of articles to return.

        Returns:
            List of Article objects.
        """
        results: list[Article] = []
        async for batch in self.search_iter(
            query=query,
            filters=filters,
            page_size=100,
            max_results=max_results,
        ):
            results.extend(batch)
        return results

    async def search_iter(
        self,
        query: str,
        filters: SearchFilters | None = None,
        page_size: int = 100,
        max_results: int = 1_000,
    ) -> AsyncGenerator[list[Article], None]:
        """Stream search results as batches of Article objects.

        Uses Semantic Scholar offset-based pagination. Each yielded batch
        contains up to page_size articles.

        Args:
            query:       Semantic Scholar query string.
            filters:     Optional SearchFilters.
            page_size:   Articles per page (max 100).
            max_results: Total articles to fetch (capped at 10,000).

        Yields:
            list[Article] — one page per yield.
        """
        extra_params = FilterTranslator.to_semanticscholar(filters) if filters else {}

        async with SemanticScholarAPIClient(api_key=self._api_key) as api:
            async for raw_batch in api.search_paginated(
                query=query,
                extra_params=extra_params,
                page_size=page_size,
                max_results=max_results,
            ):
                articles = parse_results(raw_batch)
                if articles:
                    yield articles

    async def get(self, paper_id: str) -> Article:
        """Fetch a single article by Semantic Scholar paper ID or external ID.

        The paper_id may be:
          - a 40-character hex paperId
          - "DOI:10.1234/..."
          - "PMID:12345678"
          - "ArXiv:2101.00001"

        Args:
            paper_id: Semantic Scholar paper identifier.

        Returns:
            Article object.

        Raises:
            SemanticScholarAPIError: If the article is not found.
        """
        articles = await self.fetch([paper_id])
        if not articles:
            raise SemanticScholarAPIError(f"Article not found: {paper_id}")
        return articles[0]

    async def fetch(self, paper_ids: list[str]) -> list[Article]:
        """Fetch full article records for a list of paper IDs.

        Args:
            paper_ids: List of paper ID strings (paperId, DOI:…, PMID:…, etc.).

        Returns:
            List of Article objects, in no guaranteed order.
        """
        if not paper_ids:
            return []

        articles: list[Article] = []
        async with SemanticScholarAPIClient(api_key=self._api_key) as api:
            async for raw_batch in api.fetch_by_ids(paper_ids):
                articles.extend(parse_results(raw_batch))
        return articles


class SemanticScholarClient:
    """Synchronous wrapper around AsyncSemanticScholarClient.

    Runs the async client in a new event loop. Use this for scripts and
    notebooks where async/await is not available.

    search_iter() returns the underlying async generator directly —
    use it with `async for` in an async context.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._async = AsyncSemanticScholarClient(api_key=api_key)

    def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        max_results: int = 500,
    ) -> list[Article]:
        """Synchronous search. See AsyncSemanticScholarClient.search for details."""
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
        page_size: int = 100,
        max_results: int = 1_000,
    ) -> AsyncGenerator[list[Article], None]:
        """Return the async generator for streaming. Use with `async for`."""
        return self._async.search_iter(
            query=query,
            filters=filters,
            page_size=page_size,
            max_results=max_results,
        )

    def get(self, paper_id: str) -> Article:
        """Synchronous single-article fetch. See AsyncSemanticScholarClient.get."""
        return asyncio.run(self._async.get(paper_id))

    def fetch(self, paper_ids: list[str]) -> list[Article]:
        """Synchronous fetch. See AsyncSemanticScholarClient.fetch."""
        return asyncio.run(self._async.fetch(paper_ids))
