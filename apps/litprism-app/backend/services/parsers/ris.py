import re
from datetime import date

import rispy

from services.parsers import ParsedArticle

_DOI_RE = re.compile(r"10\.\d{4,}/\S+")


def parse(content: bytes, filename: str) -> list[ParsedArticle]:
    text = content.decode("utf-8", errors="replace")
    entries = rispy.loads(text)
    articles = []
    for entry in entries:
        article = _entry_to_article(entry)
        if article:
            articles.append(article)
    return articles


def _entry_to_article(entry: dict) -> ParsedArticle | None:
    title = entry.get("title") or entry.get("primary_title") or ""
    if not title:
        return None
    return ParsedArticle(
        title=title,
        upload_format="ris",
        pmid=entry.get("pmid") or entry.get("accession_number"),
        doi=_extract_doi(entry),
        abstract=entry.get("abstract"),
        authors=_parse_authors(entry.get("authors", [])),
        journal=entry.get("journal_name") or entry.get("secondary_title"),
        pub_date=_parse_date(entry.get("year")),
        keywords=entry.get("keywords", []),
        article_types=([entry["type_of_reference"]] if entry.get("type_of_reference") else []),
    )


def _extract_doi(entry: dict) -> str | None:
    """Check entry['doi'] first, then scan entry['url'] for a DOI pattern."""
    if entry.get("doi"):
        return entry["doi"]
    url = entry.get("url") or entry.get("link") or ""
    if url:
        match = _DOI_RE.search(url)
        if match:
            return match.group(0).rstrip(".,);")
    return None


def _parse_authors(authors: list[str]) -> list[dict]:
    """Convert RIS author strings ('Last, Fore' or 'Last') to dicts."""
    result = []
    for author in authors:
        parts = author.split(",", 1)
        if len(parts) == 2:
            result.append({"last_name": parts[0].strip(), "fore_name": parts[1].strip()})
        else:
            result.append({"last_name": author.strip(), "fore_name": ""})
    return result


def _parse_date(year: str | None) -> date | None:
    if not year:
        return None
    try:
        return date(int(str(year).strip()[:4]), 1, 1)
    except (ValueError, TypeError):
        return None
