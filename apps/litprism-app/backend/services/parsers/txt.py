"""Parser for PubMed Summary .txt format.

PubMed Summary export looks like:
    1: Smith JA, Jones AB. Title of article. J Nutr. 2024 Feb;24(1):61-70.
       doi: 10.1234/test. PMID: 31009449.

Each record starts with a number followed by a colon and space.
Records are separated by blank lines.

MEDLINE .txt (tagged format starting with "PMID-") is handled by nbib.parse.
"""

import re

from services.parsers import ParsedArticle

_RECORD_START = re.compile(r"^\d+:\s")
_DOI_RE = re.compile(r"\bdoi:\s*(10\.\d{4,}/\S+)", re.IGNORECASE)
_PMID_RE = re.compile(r"\bPMID:\s*(\d+)", re.IGNORECASE)


def is_pubmed_summary_txt(content: bytes) -> bool:
    """Return True if content looks like a PubMed Summary .txt export."""
    text = content.decode("utf-8-sig", errors="replace")
    first_non_blank = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return bool(_RECORD_START.match(first_non_blank))


def parse(content: bytes, filename: str) -> list[ParsedArticle]:
    """Parse a PubMed Summary .txt export into ParsedArticle objects."""
    text = content.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")

    # Split on blank lines, then re-join records that started with N:
    raw_blocks = text.strip().split("\n\n")
    records: list[str] = []
    buf = ""
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        if _RECORD_START.match(block):
            if buf:
                records.append(buf)
            buf = block
        elif buf:
            buf += " " + block
        else:
            buf = block
    if buf:
        records.append(buf)

    articles = []
    for record in records:
        article = _parse_record(record)
        if article:
            articles.append(article)
    return articles


def _parse_record(record: str) -> ParsedArticle | None:
    # Strip leading "N: " numbering
    text = _RECORD_START.sub("", record, count=1).strip()
    if not text:
        return None

    doi_match = _DOI_RE.search(text)
    doi = doi_match.group(1).rstrip(".") if doi_match else None

    pmid_match = _PMID_RE.search(text)
    pmid = pmid_match.group(1) if pmid_match else None

    # Title heuristic: text before the first period that is followed by a journal/date token.
    # PubMed Summary: "Authors. Title. Journal. Year..."
    # The authors come first, then title, then journal — split on ". " boundaries.
    parts = [p.strip() for p in text.split(". ") if p.strip()]
    title = parts[1] if len(parts) >= 2 else (parts[0] if parts else None)
    if not title:
        return None

    return ParsedArticle(
        title=title,
        upload_format="medline",
        pmid=pmid,
        doi=doi,
        abstract=None,  # Summary format has no abstract
    )
