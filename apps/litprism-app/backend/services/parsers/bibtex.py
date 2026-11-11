from datetime import date

import bibtexparser

from services.parsers import ParsedArticle


def parse(content: bytes, filename: str) -> list[ParsedArticle]:
    text = content.decode("utf-8", errors="replace")
    library = bibtexparser.parse_string(text)
    articles = []
    for entry in library.entries:
        article = _entry_to_article(entry)
        if article:
            articles.append(article)
    return articles


def _entry_to_article(entry) -> ParsedArticle | None:
    fields = {f.key: f.value for f in entry.fields}
    title = fields.get("title", "").strip("{}")
    if not title:
        return None
    return ParsedArticle(
        title=title,
        upload_format="bib",
        doi=fields.get("doi"),
        abstract=fields.get("abstract"),
        authors=_parse_author_string(fields.get("author", "")),
        journal=fields.get("journal") or fields.get("booktitle"),
        pub_date=_parse_year(fields.get("year")),
        keywords=[k.strip() for k in fields.get("keywords", "").split(",") if k.strip()],
    )


def _parse_author_string(author_str: str) -> list[dict]:
    """Parse BibTeX 'Last, Fore and Last2, Fore2' author strings."""
    if not author_str:
        return []
    authors = []
    for name in author_str.split(" and "):
        name = name.strip()
        if not name:
            continue
        parts = name.split(",", 1)
        if len(parts) == 2:
            authors.append({"last_name": parts[0].strip(), "fore_name": parts[1].strip()})
        else:
            authors.append({"last_name": name, "fore_name": ""})
    return authors


def _parse_year(year: str | None) -> date | None:
    if not year:
        return None
    try:
        return date(int(str(year).strip()[:4]), 1, 1)
    except (ValueError, TypeError):
        return None
