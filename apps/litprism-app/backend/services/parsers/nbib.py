from datetime import date

from services.parsers import ParsedArticle


def parse(content: bytes, filename: str) -> list[ParsedArticle]:
    # Normalize CRLF (PubMed exports) and bare CR before splitting
    text = content.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    records = text.strip().split("\n\n")
    fmt = "medline" if filename.lower().endswith(".txt") else "nbib"
    articles = []
    for record in records:
        article = _parse_record(record)
        if article and article.title:
            article.upload_format = fmt
            articles.append(article)
    return articles


def _join_continuations(lines: list[str]) -> list[str]:
    """Merge wrapped continuation lines into the preceding tag line.

    MEDLINE/NBIB continuation lines have whitespace in the tag area (cols 0-3).
    """
    joined: list[str] = []
    for line in lines:
        if joined and len(line) >= 6 and not line[:4].strip():
            joined[-1] = joined[-1] + " " + line[6:].strip()
        else:
            joined.append(line)
    return joined


def _parse_record(record: str) -> ParsedArticle | None:
    """Parse a single NBIB/MEDLINE record. Returns None if record is empty."""
    if not record.strip():
        return None

    article = ParsedArticle(title="")
    has_fau = False  # True once any FAU (full author name) line is seen

    for line in _join_continuations(record.splitlines()):
        if len(line) < 6:
            continue
        tag = line[:4].strip()
        value = line[6:].strip()
        if not tag or not value:
            continue

        if tag == "PMID":
            article.pmid = value
        elif tag == "TI":
            article.title = value
        elif tag == "AB":
            article.abstract = value
        elif tag == "FAU":
            # Full author name: "Last, Fore" — preferred over AU initials
            parts = value.split(",", 1)
            if len(parts) == 2:
                article.authors.append(
                    {"last_name": parts[0].strip(), "fore_name": parts[1].strip()}
                )
            else:
                article.authors.append({"last_name": value, "fore_name": ""})
            has_fau = True
        elif tag == "AU" and not has_fau:
            # Fallback: use initials-only AU when no FAU lines present (some older files)
            parts = value.split(",", 1)
            if len(parts) == 2:
                article.authors.append(
                    {"last_name": parts[0].strip(), "fore_name": parts[1].strip()}
                )
            else:
                article.authors.append({"last_name": value, "fore_name": ""})
        elif tag == "TA":
            article.journal = value
        elif tag == "DP":
            article.pub_date = _parse_date(value)
        elif tag == "MH":
            # Strip trailing / and * markers used for major MeSH headings
            article.mesh_terms.append(value.rstrip("/*"))
        elif tag == "OT":
            article.keywords.append(value)
        elif tag == "AID":
            # DOI lines end with " [doi]" suffix — preserve original casing
            if "[doi]" in value.lower():
                article.doi = value[: value.lower().index("[doi]")].strip()
        elif tag == "PT":
            article.article_types.append(value)

    return article if article.title else None


def _parse_date(value: str) -> date | None:
    """Parse DP tag values like '2023 Mar 15', '2023 Mar', or '2023'."""
    _MONTHS = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    parts = value.split()
    if not parts:
        return None
    try:
        year = int(parts[0])
        month = _MONTHS.get(parts[1].lower()[:3], 1) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day)
    except (ValueError, IndexError):
        return None
