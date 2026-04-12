"""Pydantic models for litprism-crossref.

CrossrefMetadata is the output contract for AsyncCrossrefClient.enrich_by_doi().
It is intentionally self-contained — no cross-package imports.
"""

from datetime import date

from pydantic import BaseModel, Field


class CrossrefAuthor(BaseModel):
    """A single article author as returned by the Crossref Works API."""

    given: str | None = None
    family: str | None = None
    orcid: str | None = None  # ORCID URI, e.g. "https://orcid.org/0000-0001-2345-6789"
    affiliation: str | None = None  # first affiliation name, if present


class CrossrefMetadata(BaseModel):
    """Enrichment metadata for a single article, fetched from Crossref by DOI.

    Fields map directly to the Crossref Works API ``message`` object.
    All fields except ``doi`` are optional — Crossref records vary widely
    in completeness.
    """

    doi: str

    # Bibliographic
    title: str | None = None
    authors: list[CrossrefAuthor] = Field(default_factory=list)
    publisher: str | None = None
    journal: str | None = None  # first container-title
    publication_date: date | None = None
    publication_year: int | None = None
    abstract: str | None = None
    work_type: str | None = None  # e.g. "journal-article", "book-chapter"

    # Identifiers / access
    url: str | None = None
    issn: list[str] = Field(default_factory=list)
    license_url: str | None = None  # first license URL, if present
    open_access: bool = False  # True when a Creative Commons license is present

    # Metrics
    citation_count: int | None = None  # is-referenced-by-count
    references_count: int | None = None  # references-count

    # Subject classification
    subjects: list[str] = Field(default_factory=list)  # subject field from Crossref
