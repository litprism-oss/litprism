"""PubMed client — public API for litprism-pubmed.

AsyncPubMedClient is the primary implementation.
PubMedClient is a synchronous wrapper for non-async callers.
"""

import asyncio

from litprism.pubmed.cache import ArticleCache
from litprism.pubmed.entrez import EntrezClient
from litprism.pubmed.models import Article, ArticleFilters, SearchResult
from litprism.pubmed.parser import parse_xml


class AsyncPubMedClient:
    """Async PubMed client.

    Args:
        api_key: NCBI API key. Optional — raises rate limit from 3/s to 10/s.
        email: Contact email for NCBI's polite pool. Recommended.
        cache: Optional ArticleCache instance. If provided, fetch() checks the
               cache before hitting the API and stores new results.
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
        max_results: int = 500,
        date_range: tuple[str, str] | None = None,
        filters: ArticleFilters | None = None,
    ) -> SearchResult:
        """Search PubMed and return a SearchResult containing PMIDs.

        Args:
            query: PubMed boolean query string.
            max_results: Maximum number of PMIDs to retrieve.
            date_range: Optional (start, end) dates as "YYYY-MM-DD" strings.
            filters: Optional ArticleFilters (article types, language, abstract).

        Returns:
            SearchResult with PMIDs and metadata.
        """
        async with self._entrez:
            return await self._entrez.esearch(
                query=query,
                max_results=max_results,
                date_range=date_range,
                filters=filters,
            )

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
        max_results: int = 500,
        date_range: tuple[str, str] | None = None,
        filters: ArticleFilters | None = None,
    ) -> SearchResult:
        """Synchronous search. See AsyncPubMedClient.search for details."""
        return asyncio.run(
            self._async.search(
                query=query,
                max_results=max_results,
                date_range=date_range,
                filters=filters,
            )
        )

    def fetch(self, pmids: list[str]) -> list[Article]:
        """Synchronous fetch. See AsyncPubMedClient.fetch for details."""
        return asyncio.run(self._async.fetch(pmids))
