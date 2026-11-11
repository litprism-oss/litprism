import csv
import io
from datetime import date

import openpyxl

from services.parsers import ParsedArticle

# Mapping from normalised (lowercase) column names to ParsedArticle fields.
# Covers Scopus CSV column names.
_COLUMN_MAP = {
    "title": "title",
    "abstract": "abstract",
    "authors": "authors",
    "source title": "journal",
    "year": "pub_date",
    "doi": "doi",
    "pubmed id": "pmid",
    "author keywords": "keywords",
    "document type": "article_types",
}

# PubMed CSV exports use these column names (after BOM strip + strip()).
_PUBMED_CSV_SIGNATURE = {"PMID", "Title", "Authors", "Journal/Book"}


def parse(content: bytes, filename: str) -> list[ParsedArticle]:
    if filename.lower().endswith(".xlsx"):
        return _parse_xlsx(content)
    return _parse_csv(content)


def _is_pubmed_csv(fieldnames: list[str]) -> bool:
    cols = {h.strip() for h in fieldnames if h}
    return _PUBMED_CSV_SIGNATURE.issubset(cols)


def _parse_csv(content: bytes) -> list[ParsedArticle]:
    text = content.decode("utf-8-sig", errors="replace")  # handles BOM
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    if _is_pubmed_csv(list(reader.fieldnames)):
        return _parse_pubmed_csv(text)
    # Build normalised header → original header map
    norm = {h.strip().lower(): h for h in reader.fieldnames if h}
    articles = []
    for row in reader:
        article = _row_to_article(row, norm)
        if article:
            articles.append(article)
    return articles


def _parse_pubmed_csv(text: str) -> list[ParsedArticle]:
    """Parse a PubMed CSV export (no Abstract column; authors as comma-delimited string)."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    # Strip whitespace from all column names
    reader.fieldnames = [h.strip() for h in reader.fieldnames]
    articles = []
    for row in reader:
        title = str(row.get("Title", "") or "").strip() or None
        if not title:
            continue
        pmid = str(row.get("PMID", "") or "").strip() or None
        doi = str(row.get("DOI", "") or "").strip() or None
        journal = str(row.get("Journal/Book", "") or "").strip() or None
        year_raw = str(row.get("Publication Year", "") or "").strip()
        pub_date = _parse_year(year_raw)
        authors = _parse_authors_pubmed(str(row.get("Authors", "") or "").strip())
        articles.append(
            ParsedArticle(
                title=title,
                upload_format="csv",
                pmid=pmid,
                doi=doi,
                abstract=None,  # PubMed CSV has no abstract column
                authors=authors,
                journal=journal,
                pub_date=pub_date,
            )
        )
    return articles


def _parse_authors_pubmed(authors_str: str) -> list[dict]:
    """Parse PubMed CSV author string: 'Smith J, Jones A, Kumar R.' → list of dicts."""
    if not authors_str:
        return []
    authors_str = authors_str.rstrip(".")
    result = []
    for part in authors_str.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if len(tokens) >= 2:
            result.append({"last_name": tokens[0], "fore_name": " ".join(tokens[1:])})
        else:
            result.append({"last_name": part, "fore_name": None})
    return result


def _parse_xlsx(content: bytes) -> list[ParsedArticle]:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    raw_headers = next(rows, None)
    if raw_headers is None:
        return []
    headers = [str(h).strip().lower() if h is not None else "" for h in raw_headers]
    articles = []
    for row in rows:
        row_dict = {headers[i]: (str(v) if v is not None else "") for i, v in enumerate(row)}
        # Rebuild with original casing expected by _row_to_article via norm map
        norm = {h: h for h in headers}
        article = _row_to_article(row_dict, norm)
        if article:
            articles.append(article)
    return articles


def _row_to_article(row: dict, norm: dict[str, str]) -> ParsedArticle | None:
    """Map one CSV/XLSX row to a ParsedArticle using the column map."""

    def get(field_key: str) -> str:
        """Return the cell value for a logical field, or ''."""
        for norm_col, target in _COLUMN_MAP.items():
            if target == field_key and norm_col in norm:
                return str(row.get(norm[norm_col], "") or "").strip()
        return ""

    title = get("title")
    if not title:
        return None

    authors_raw = get("authors")
    authors = _parse_authors(authors_raw) if authors_raw else []

    keywords_raw = get("keywords")
    keywords = [k.strip() for k in keywords_raw.split(";") if k.strip()] if keywords_raw else []

    article_types_raw = get("article_types")
    article_types = [article_types_raw] if article_types_raw else []

    return ParsedArticle(
        title=title,
        upload_format="csv",
        doi=get("doi") or None,
        pmid=get("pmid") or None,
        abstract=get("abstract") or None,
        authors=authors,
        journal=get("journal") or None,
        pub_date=_parse_year(get("pub_date")),
        keywords=keywords,
        article_types=article_types,
    )


def _parse_authors(authors_str: str) -> list[dict]:
    """Parse Scopus-style author strings: 'Smith J., Jones A.B.'"""
    authors = []
    for name in authors_str.split(";"):
        name = name.strip().rstrip(".")
        if not name:
            continue
        parts = name.split(",", 1)
        if len(parts) == 2:
            authors.append({"last_name": parts[0].strip(), "fore_name": parts[1].strip()})
        else:
            authors.append({"last_name": name, "fore_name": ""})
    return authors


def _parse_year(value: str) -> date | None:
    if not value:
        return None
    try:
        return date(int(value.strip()[:4]), 1, 1)
    except (ValueError, TypeError):
        return None
