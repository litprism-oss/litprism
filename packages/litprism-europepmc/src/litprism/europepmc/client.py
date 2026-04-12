"""Europe PMC client — public API for litprism-europepmc.

AsyncEuropePMCClient is the primary implementation.
EuropePMCClient is a synchronous wrapper for non-async callers.
"""

import asyncio
from collections.abc import AsyncGenerator

from litprism.europepmc.exceptions import EuropePMCAPIError
from litprism.europepmc.filters import FilterTranslator
from litprism.europepmc.models import Article, SearchFilters


class AsyncEuropePMCClient:
    """Async Europe PMC client.

    Args:
        api_key: Europe PMC API key. Optional — raises rate limit from 3/s to 10/s.
        email:   Contact email for the polite pool. Recommended.
    """

    def __init__(
        self,
        api_key: str | None = None,
        email: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._email = email

    async def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        max_results: int = 500,
    ) -> list[Article]:
        """Search Europe PMC and return a list of Article objects.

        Convenience method for small searches (max_results <= 1000 recommended).
        Uses cursor-based pagination internally — collects all pages into a
        single list before returning.

        For large searches use search_iter() to stream results page-by-page.

        Args:
            query:       Europe PMC query string.
            filters:     Optional SearchFilters (dates, languages, pub types…).
            max_results: Maximum number of articles to return.

        Returns:
            List of Article objects.
        """
        results: list[Article] = []
        async for batch in self.search_iter(
            query=query,
            filters=filters,
            page_size=1000,
            max_results=max_results,
        ):
            results.extend(batch)
        return results

    async def search_iter(
        self,
        query: str,
        filters: SearchFilters | None = None,
        page_size: int = 1000,
        max_results: int = 10_000,
    ) -> AsyncGenerator[list[Article], None]:
        """Stream search results as batches of Article objects.

        Uses Europe PMC cursor-based pagination (cursorMark). Each yielded
        batch contains up to page_size articles.

        Args:
            query:       Europe PMC query string.
            filters:     Optional SearchFilters.
            page_size:   Articles per page (max 1000).
            max_results: Total articles to fetch.

        Yields:
            list[Article] — one page per yield.
        """
        raise NotImplementedError

    async def get(self, article_id: str, source: str = "MED") -> Article:
        """Fetch a single article by Europe PMC id.

        Args:
            article_id: Europe PMC article identifier.
            source:     Europe PMC source code (default "MED" for MEDLINE).

        Returns:
            Article object.

        Raises:
            EuropePMCAPIError: If the article is not found.
        """
        articles = await self.fetch([(article_id, source)])
        if not articles:
            raise EuropePMCAPIError(f"Article not found: {source}/{article_id}")
        return articles[0]

    async def fetch(self, ids: list[tuple[str, str]]) -> list[Article]:
        """Fetch full article records for a list of (article_id, source) pairs.

        Args:
            ids: List of (article_id, source) tuples.

        Returns:
            List of Article objects, in no guaranteed order.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers (implemented in subsequent tasks)
    # ------------------------------------------------------------------

    def _build_query(self, query: str, filters: SearchFilters | None) -> str:
        """Combine base query with filter query fragment."""
        if not filters:
            return query
        params = FilterTranslator.to_europepmc(filters)
        filter_query = params.get("filter_query", "")
        if filter_query:
            return f"({query}) AND {filter_query}"
        return query


class EuropePMCClient:
    """Synchronous wrapper around AsyncEuropePMCClient.

    Runs the async client in a new event loop. Use this for scripts and
    notebooks where async/await is not available.

    search_iter() returns the underlying async generator directly —
    use it with `async for` in an async context.
    """

    def __init__(
        self,
        api_key: str | None = None,
        email: str | None = None,
    ) -> None:
        self._async = AsyncEuropePMCClient(api_key=api_key, email=email)

    def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        max_results: int = 500,
    ) -> list[Article]:
        """Synchronous search. See AsyncEuropePMCClient.search for details."""
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
        page_size: int = 1000,
        max_results: int = 10_000,
    ) -> AsyncGenerator[list[Article], None]:
        """Return the async generator for streaming. Use with `async for`."""
        return self._async.search_iter(
            query=query,
            filters=filters,
            page_size=page_size,
            max_results=max_results,
        )

    def get(self, article_id: str, source: str = "MED") -> Article:
        """Synchronous single-article fetch. See AsyncEuropePMCClient.get."""
        return asyncio.run(self._async.get(article_id, source))

    def fetch(self, ids: list[tuple[str, str]]) -> list[Article]:
        """Synchronous fetch. See AsyncEuropePMCClient.fetch."""
        return asyncio.run(self._async.fetch(ids))
