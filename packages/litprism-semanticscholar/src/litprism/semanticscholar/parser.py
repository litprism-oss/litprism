"""JSON → Pydantic parser for Semantic Scholar Graph API responses."""

import contextlib
from datetime import date
from typing import Any

from litprism.semanticscholar.exceptions import SemanticScholarParseError
from litprism.semanticscholar.models import Article, Author


def _str(value: Any, default: str | None = None) -> str | None:
    """Coerce a value to a stripped string, or return default."""
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def _parse_date(date_str: str | None) -> tuple[date | None, int | None]:
    """Parse a publicationDate string (YYYY-MM-DD or YYYY) into (date, year)."""
    if not date_str:
        return None, None

    year: int | None = None
    pub_date: date | None = None

    with contextlib.suppress(ValueError):
        if len(date_str) >= 10:
            pub_date = date.fromisoformat(date_str[:10])
            year = pub_date.year
        elif len(date_str) == 4:
            year = int(date_str)

    return pub_date, year


def _parse_authors(raw: dict[str, Any]) -> list[Author]:
    """Parse SS `authors` list into Author models.

    SS author objects have `authorId` and `name` (full name, not split).
    We attempt to split `name` into fore/last; on failure we store the
    full name as last_name.
    """
    raw_authors = raw.get("authors") or []
    authors: list[Author] = []
    for a in raw_authors:
        name = _str(a.get("name"))
        if not name:
            continue
        parts = name.rsplit(" ", 1)
        if len(parts) == 2:
            fore_name, last_name = parts[0], parts[1]
        else:
            fore_name, last_name = None, parts[0]
        authors.append(Author(last_name=last_name, fore_name=fore_name))
    return authors


def parse_article(raw: dict[str, Any]) -> Article | None:
    """Parse a single Semantic Scholar paper dict into an Article.

    Returns None if the record is missing required fields.
    """
    paper_id = _str(raw.get("paperId"))
    if not paper_id:
        return None

    title = _str(raw.get("title")) or ""
    if not title:
        return None

    external_ids = raw.get("externalIds") or {}
    pmid = _str(external_ids.get("PubMed"))
    doi = _str(external_ids.get("DOI"))

    abstract = _str(raw.get("abstract"))

    pub_date, pub_year = _parse_date(_str(raw.get("publicationDate")))
    if pub_year is None:
        with contextlib.suppress(ValueError, TypeError):
            year_raw = raw.get("year")
            pub_year = int(year_raw) if year_raw else None

    authors = _parse_authors(raw)

    # Journal / venue
    journal_obj = raw.get("journal") or {}
    journal = _str(journal_obj.get("name")) if isinstance(journal_obj, dict) else None
    venue = _str(raw.get("venue"))

    # Open access
    open_access = bool(raw.get("isOpenAccess"))
    oa_pdf = raw.get("openAccessPdf") or {}
    pdf_url = _str(oa_pdf.get("url")) if isinstance(oa_pdf, dict) else None

    # Fields of study — prefer top-level fieldsOfStudy list
    fields_of_study: list[str] = []
    fos_raw = raw.get("fieldsOfStudy") or []
    if isinstance(fos_raw, list):
        fields_of_study = [f for f in fos_raw if isinstance(f, str)]

    # Publication types
    article_types: list[str] = []
    pt_raw = raw.get("publicationTypes") or []
    if isinstance(pt_raw, list):
        article_types = [t for t in pt_raw if isinstance(t, str)]

    # Citation count
    citation_count: int | None = None
    with contextlib.suppress(ValueError, TypeError):
        cc = raw.get("citationCount")
        citation_count = int(cc) if cc is not None else None

    return Article(
        id=paper_id,
        pmid=pmid,
        doi=doi,
        title=title,
        abstract=abstract,
        authors=authors,
        journal=journal,
        publication_date=pub_date,
        publication_year=pub_year,
        open_access=open_access,
        pdf_url=pdf_url,
        fields_of_study=fields_of_study,
        article_types=article_types,
        citation_count=citation_count,
        venue=venue,
    )


def parse_results(results: list[dict[str, Any]]) -> list[Article]:
    """Parse a list of raw Semantic Scholar paper dicts into Article objects.

    Malformed individual records are skipped with no error raised.
    An empty input returns an empty list; a non-list input raises SemanticScholarParseError.
    """
    if not isinstance(results, list):
        raise SemanticScholarParseError(f"Expected a list of results, got {type(results).__name__}")

    articles: list[Article] = []
    for raw in results:
        article = parse_article(raw)
        if article is not None:
            articles.append(article)
    return articles
