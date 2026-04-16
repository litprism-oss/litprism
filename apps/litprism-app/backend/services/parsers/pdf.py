import asyncio
import json
import re
from datetime import date
from pathlib import Path

import fitz  # pymupdf

from services.parsers import ParsedArticle
from services.parsers.exceptions import EmptyFileError, PasswordProtectedPDFError

_DOI_RE = re.compile(r"\b10\.\d{4,}/\S+")


def parse(content: bytes, filename: str) -> list[ParsedArticle]:
    """
    Four-tier PDF metadata extraction:
      Tier 1 — PDF metadata fields (doc.metadata) — publisher-populated, instant
      Tier 2 — DOI regex → Crossref lookup — authoritative, covers ~90% of born-digital
      Tier 3 — Heuristic text extraction — always produces something
    LLM extraction (Tier 2b) is available but opt-in — see parse_with_llm() below.
    """
    doc = fitz.open(stream=content, filetype="pdf")

    # Fail fast on encrypted / password-protected PDFs
    if doc.needs_pass or doc.is_encrypted:
        raise PasswordProtectedPDFError(filename)

    # Tier 1 — PDF metadata fields
    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip()
    author_str = (meta.get("author") or "").strip()

    # Extract text from first two pages for DOI search and heuristics
    first_pages_text = "\n".join(
        doc[i].get_text("text") for i in range(min(2, doc.page_count))
    ).strip()

    # Catch scanned-only / corrupted PDFs that produce no text layer
    if not first_pages_text and doc.page_count > 0:
        raise EmptyFileError(filename)

    # Tier 2 — DOI regex → Crossref lookup
    doi = _extract_doi(first_pages_text)
    if doi:
        crossref_article = asyncio.run(_crossref_lookup(doi))
        if crossref_article:
            return [crossref_article]

    # Tier 3 — heuristic text extraction
    if not title:
        title = _heuristic_title(first_pages_text, filename)
    abstract = _heuristic_abstract(first_pages_text)
    authors = _parse_author_string(author_str) if author_str else []

    return [
        ParsedArticle(
            title=title,
            upload_format="pdf",
            doi=doi,
            abstract=abstract,
            authors=authors,
            source="upload",
        )
    ]


async def _crossref_lookup(doi: str) -> ParsedArticle | None:
    """Fetch authoritative metadata from Crossref via litprism-crossref."""
    try:
        from litprism.crossref import CrossrefClient

        client = CrossrefClient()
        work = await client.get(doi)
        if not work:
            return None
        return ParsedArticle(
            title=work.title or "",
            upload_format="pdf",
            doi=doi,
            abstract=work.abstract,
            authors=[
                {"last_name": a.last_name, "fore_name": a.fore_name} for a in (work.authors or [])
            ],
            journal=work.journal,
            pub_date=work.publication_date,
            source="upload",
        )
    except Exception:
        return None


def _extract_doi(text: str) -> str | None:
    """Scan text for DOI pattern: 10.XXXX/..."""
    match = _DOI_RE.search(text)
    return match.group(0).rstrip(".,);") if match else None


def _heuristic_title(text: str, filename: str) -> str:
    """
    First non-empty line longer than 15 chars that isn't a journal header.
    Falls back to filename stem.
    """
    skip_patterns = re.compile(
        r"^\s*(vol|volume|issue|doi|http|©|copyright|\d{4}[;,])",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 15 and not skip_patterns.match(line):
            return line
    return Path(filename).stem


def _heuristic_abstract(text: str) -> str | None:
    """
    Extract text following an 'Abstract' heading, up to 'Introduction'
    or 'Keywords' or 600 chars, whichever comes first.
    """
    match = re.search(
        r"\bAbstract\b[\s\n]+(.+?)(?=\n\s*(?:Introduction|Keywords|Background|Methods)\b)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()[:600]
    return None


def _parse_author_string(author_str: str) -> list[dict]:
    """Parse a freeform author string from PDF metadata."""
    authors = []
    # Try semicolon-separated first, then comma-separated pairs
    separators = [";", " and "]
    for sep in separators:
        if sep in author_str:
            for name in author_str.split(sep):
                name = name.strip()
                if not name:
                    continue
                parts = name.split(",", 1)
                if len(parts) == 2:
                    authors.append({"last_name": parts[0].strip(), "fore_name": parts[1].strip()})
                else:
                    authors.append({"last_name": name, "fore_name": ""})
            return authors
    # Single author or unparseable — store as-is
    if author_str:
        authors.append({"last_name": author_str, "fore_name": ""})
    return authors


async def parse_with_llm(first_page_text: str, llm_config) -> ParsedArticle | None:
    """
    Send first-page text to the configured LLM and extract structured metadata.
    Called only when use_llm=True is passed to the upload endpoint.
    Cost: ~$0.001 per PDF with gpt-4o-mini.
    """
    from litprism.screen.llm import call_llm

    prompt = f"""Extract metadata from this academic paper's first page.
Return ONLY valid JSON, no preamble:
{{
  "title": "...",
  "authors": [{{"last_name": "...", "fore_name": "..."}}],
  "abstract": "...",
  "doi": "...",
  "journal": "...",
  "year": "..."
}}

First page:
{first_page_text[:2000]}"""
    try:
        raw = await call_llm(llm_config, prompt)
        data = json.loads(raw)
        return ParsedArticle(
            title=data.get("title", ""),
            upload_format="pdf",
            doi=data.get("doi"),
            abstract=data.get("abstract"),
            authors=data.get("authors", []),
            journal=data.get("journal"),
            pub_date=_parse_year(data.get("year")),
            source="upload",
        )
    except Exception:
        return None


def _parse_year(year: str | None) -> date | None:
    if not year:
        return None
    try:
        return date(int(str(year).strip()[:4]), 1, 1)
    except (ValueError, TypeError):
        return None
