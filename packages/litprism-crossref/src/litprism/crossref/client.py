"""Crossref enrichment client — public API for litprism-crossref.

AsyncCrossrefClient is the primary implementation.
CrossrefClient is a synchronous wrapper for non-async callers.

Always supply ``mailto`` so Crossref routes requests through the polite pool.
"""

import asyncio
import urllib.parse
from datetime import date

import httpx
from litprism.crossref.exceptions import (
    CrossrefAPIError,
    CrossrefNetworkError,
    CrossrefNotFoundError,
    CrossrefParseError,
    CrossrefRateLimitError,
)
from litprism.crossref.models import CrossrefAuthor, CrossrefMetadata
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_BASE_URL = "https://api.crossref.org"
_CC_PREFIX = "https://creativecommons.org"


def _build_user_agent(mailto: str | None) -> str:
    base = "litprism-crossref/0.1.0 (https://litprism.org)"
    if mailto:
        return f"{base}; mailto:{mailto}"
    return base


def _parse_date(published: dict | None) -> tuple[date | None, int | None]:
    """Extract (date, year) from a Crossref ``published`` object."""
    if not published:
        return None, None
    parts = published.get("date-parts", [[]])
    if not parts or not parts[0]:
        return None, None
    dp = parts[0]
    year = dp[0] if len(dp) >= 1 else None
    if year is None:
        return None, None
    month = dp[1] if len(dp) >= 2 else 1
    day = dp[2] if len(dp) >= 3 else 1
    try:
        return date(year, month, day), year
    except ValueError:
        return None, year


def _parse_authors(raw: list[dict]) -> list[CrossrefAuthor]:
    authors = []
    for a in raw:
        affiliations = a.get("affiliation") or []
        affil = affiliations[0].get("name") if affiliations else None
        orcid_raw = a.get("ORCID")
        authors.append(
            CrossrefAuthor(
                given=a.get("given"),
                family=a.get("family"),
                orcid=orcid_raw,
                affiliation=affil,
            )
        )
    return authors


def _parse_message(msg: dict) -> CrossrefMetadata:
    """Convert a Crossref Works ``message`` dict into a CrossrefMetadata object."""
    doi = msg.get("DOI", "")

    titles = msg.get("title") or []
    title = titles[0] if titles else None

    container = msg.get("container-title") or []
    journal = container[0] if container else None

    pub_date, pub_year = _parse_date(msg.get("published") or msg.get("published-print"))

    authors = _parse_authors(msg.get("author") or [])

    issn: list[str] = msg.get("ISSN") or []
    subjects: list[str] = msg.get("subject") or []

    licenses: list[dict] = msg.get("license") or []
    license_url = licenses[0].get("URL") if licenses else None
    open_access = any((lic.get("URL") or "").startswith(_CC_PREFIX) for lic in licenses)

    return CrossrefMetadata(
        doi=doi,
        title=title,
        authors=authors,
        publisher=msg.get("publisher"),
        journal=journal,
        publication_date=pub_date,
        publication_year=pub_year,
        abstract=msg.get("abstract"),
        work_type=msg.get("type"),
        url=msg.get("URL"),
        issn=issn,
        license_url=license_url,
        open_access=open_access,
        citation_count=msg.get("is-referenced-by-count"),
        references_count=msg.get("references-count"),
        subjects=subjects,
    )


class AsyncCrossrefClient:
    """Async Crossref enrichment client.

    Fetches metadata for a single article by DOI from the Crossref Works API.
    No search, no pagination — enrichment only.

    Args:
        mailto: Contact email address. Required for the Crossref polite pool,
                which offers higher rate limits and reliability.
    """

    def __init__(self, mailto: str | None = None) -> None:
        self._mailto = mailto
        self._headers = {"User-Agent": _build_user_agent(mailto)}

    async def _do_enrich(self, doi: str) -> CrossrefMetadata:
        """Single HTTP fetch + parse — no retry logic.

        Separated from enrich_by_doi so unit tests can call it directly
        without triggering tenacity's retry backoff.

        Args:
            doi: Already-normalised DOI (no https://doi.org/ prefix).

        Raises:
            CrossrefNotFoundError, CrossrefRateLimitError, CrossrefAPIError,
            CrossrefParseError, CrossrefNetworkError.
        """
        encoded = urllib.parse.quote(doi, safe="")
        url = f"{_BASE_URL}/works/{encoded}"

        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as http:
                response = await http.get(url)
        except httpx.TimeoutException as exc:
            raise CrossrefNetworkError(f"Request timed out for DOI {doi!r}") from exc
        except httpx.RequestError as exc:
            raise CrossrefNetworkError(f"Network error for DOI {doi!r}: {exc}") from exc

        if response.status_code == 404:
            raise CrossrefNotFoundError(f"DOI not found: {doi!r}", status_code=404)
        if response.status_code == 429:
            raise CrossrefRateLimitError("Crossref rate limit exceeded", status_code=429)
        if response.status_code >= 400:
            raise CrossrefAPIError(
                f"Crossref API error {response.status_code} for DOI {doi!r}",
                status_code=response.status_code,
            )

        try:
            body = response.json()
            message = body["message"]
        except Exception as exc:
            raise CrossrefParseError(f"Failed to parse Crossref response for DOI {doi!r}") from exc

        return _parse_message(message)

    @retry(
        retry=retry_if_exception_type(CrossrefRateLimitError),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def enrich_by_doi(self, doi: str) -> CrossrefMetadata:
        """Fetch enrichment metadata for a single article by DOI.

        Retries automatically on HTTP 429 (up to 5 attempts, exponential backoff).

        Args:
            doi: The DOI string, e.g. ``"10.1038/s41586-021-03819-2"``.
                 A leading ``https://doi.org/`` prefix is stripped automatically.

        Returns:
            CrossrefMetadata populated from the Crossref Works API.

        Raises:
            CrossrefNotFoundError: DOI not found in Crossref (HTTP 404).
            CrossrefRateLimitError: Rate limit still exceeded after all retries.
            CrossrefAPIError: Any other non-2xx response.
            CrossrefParseError: Response could not be parsed.
            CrossrefNetworkError: Network-level failure.
        """
        doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
        return await self._do_enrich(doi)


class CrossrefClient:
    """Synchronous wrapper around AsyncCrossrefClient.

    Runs the async client in a new event loop. Use this for scripts and
    notebooks where async/await is not available.

    Args:
        mailto: Contact email for the Crossref polite pool. Always set this.
    """

    def __init__(self, mailto: str | None = None) -> None:
        self._async = AsyncCrossrefClient(mailto=mailto)

    def enrich_by_doi(self, doi: str) -> CrossrefMetadata:
        """Synchronous DOI enrichment. See AsyncCrossrefClient.enrich_by_doi."""
        return asyncio.run(self._async.enrich_by_doi(doi))
