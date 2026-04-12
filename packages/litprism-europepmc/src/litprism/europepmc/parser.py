"""JSON → Pydantic parser for Europe PMC REST API search responses."""

import contextlib
from datetime import date
from typing import Any

from litprism.europepmc.exceptions import EuropePMCParseError
from litprism.europepmc.models import Article, Author


def _str(value: Any, default: str | None = None) -> str | None:
    """Coerce a value to a stripped string, or return default."""
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def _parse_date(date_str: str | None) -> tuple[date | None, int | None]:
    """Parse a firstPublicationDate string (YYYY-MM-DD or YYYY) into (date, year)."""
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
    """Parse authorList dict into a list of Author models."""
    author_list = raw.get("authorList") or {}
    raw_authors = author_list.get("author") or []

    # Europe PMC returns a single author dict (not a list) for single-author articles
    if isinstance(raw_authors, dict):
        raw_authors = [raw_authors]

    authors: list[Author] = []
    for a in raw_authors:
        last = _str(a.get("lastName"))
        if not last:
            continue
        fore = _str(a.get("firstName")) or _str(a.get("initials"))
        affiliation = _str(a.get("affiliation"))

        # ORCID is nested: {"authorId": {"type": "ORCID", "value": "0000-..."}}
        orcid: str | None = None
        author_id = a.get("authorId")
        if isinstance(author_id, dict) and author_id.get("type") == "ORCID":
            orcid = _str(author_id.get("value"))

        authors.append(Author(last_name=last, fore_name=fore, affiliation=affiliation, orcid=orcid))

    return authors


def _parse_full_text_urls(raw: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (pdf_url, full_text_url) from fullTextUrlList."""
    url_list = raw.get("fullTextUrlList") or {}
    urls = url_list.get("fullTextUrl") or []
    if isinstance(urls, dict):
        urls = [urls]

    pdf_url: str | None = None
    html_url: str | None = None

    for entry in urls:
        style = _str(entry.get("documentStyle"), "")
        url = _str(entry.get("url"))
        if not url:
            continue
        if style == "pdf" and pdf_url is None:
            pdf_url = url
        elif style in ("html", "doi") and html_url is None:
            html_url = url

    return pdf_url, html_url


def parse_article(raw: dict[str, Any]) -> Article | None:
    """Parse a single Europe PMC result dict into an Article.

    Returns None if the record is missing required fields.
    """
    article_id = _str(raw.get("id"))
    if not article_id:
        return None

    title = _str(raw.get("title")) or ""
    if not title:
        return None

    pmid = _str(raw.get("pmid"))
    doi = _str(raw.get("doi"))
    europepmc_source = _str(raw.get("source"))

    abstract = _str(raw.get("abstractText"))

    # Journal
    journal_info = raw.get("journalInfo") or {}
    journal_obj = journal_info.get("journal") or {}
    journal = _str(journal_obj.get("title")) if isinstance(journal_obj, dict) else None

    # Dates
    pub_date, pub_year = _parse_date(_str(raw.get("firstPublicationDate")))
    if pub_year is None:
        with contextlib.suppress(ValueError, TypeError):
            pub_year = int(raw.get("pubYear", 0)) or None

    # Authors
    authors = _parse_authors(raw)

    # MeSH terms
    mesh_list = raw.get("meshHeadingList") or {}
    mesh_headings = mesh_list.get("meshHeading") or []
    if isinstance(mesh_headings, dict):
        mesh_headings = [mesh_headings]
    mesh_terms = [_str(m.get("descriptorName")) for m in mesh_headings]
    mesh_terms = [t for t in mesh_terms if t]

    # Keywords
    kw_list = raw.get("keywordList") or {}
    keywords_raw = kw_list.get("keyword") or []
    if isinstance(keywords_raw, str):
        keywords_raw = [keywords_raw]
    keywords = [_str(k) for k in keywords_raw if _str(k)]

    # Publication types
    pt_list = raw.get("pubTypeList") or {}
    pub_types_raw = pt_list.get("pubType") or []
    if isinstance(pub_types_raw, str):
        pub_types_raw = [pub_types_raw]
    article_types = [_str(pt) for pt in pub_types_raw if _str(pt)]

    # Open access
    open_access = _str(raw.get("isOpenAccess"), "N") == "Y"

    # Citation count
    citation_count: int | None = None
    with contextlib.suppress(ValueError, TypeError):
        citation_count = int(raw.get("citedByCount", 0)) or None

    # Full text URLs
    pdf_url, full_text_url = _parse_full_text_urls(raw)

    return Article(
        id=article_id,
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
        full_text_url=full_text_url,
        mesh_terms=mesh_terms,
        keywords=keywords,
        article_types=article_types,
        citation_count=citation_count,
        europepmc_source=europepmc_source,
    )


def parse_results(results: list[dict[str, Any]]) -> list[Article]:
    """Parse a list of raw Europe PMC result dicts into Article objects.

    Malformed individual records are skipped with no error raised.
    An empty input returns an empty list; a non-list input raises EuropePMCParseError.
    """
    if not isinstance(results, list):
        raise EuropePMCParseError(f"Expected a list of results, got {type(results).__name__}")

    articles: list[Article] = []
    for raw in results:
        article = parse_article(raw)
        if article is not None:
            articles.append(article)
    return articles
