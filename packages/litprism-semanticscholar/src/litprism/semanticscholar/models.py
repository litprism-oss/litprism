"""Pydantic models for litprism-semanticscholar.

The Article model is the shared contract between litprism-semanticscholar and downstream
consumers (litprism-screen, the app backend). Each package defines its own copy
— there are no cross-package imports.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Author(BaseModel):
    """A single article author."""

    last_name: str
    fore_name: str | None = None
    affiliation: str | None = None
    orcid: str | None = None


class Article(BaseModel):
    """Normalised article record.

    Produced by SemanticScholarClient.fetch() and consumed by litprism-screen.
    """

    # Identity — at least one of id/pmid/doi must be present
    id: str  # Semantic Scholar paperId
    pmid: str | None = None
    doi: str | None = None
    source: Literal["semanticscholar"] = "semanticscholar"
    upload_format: str | None = None  # None for API results

    # Content
    title: str
    abstract: str | None = None
    authors: list[Author] = Field(default_factory=list)
    journal: str | None = None
    publication_date: date | None = None
    publication_year: int | None = None

    # Access
    open_access: bool = False
    pdf_url: str | None = None
    full_text_url: str | None = None
    pdf_path: str | None = None  # local path if PDF uploaded

    # Semantic Scholar-specific
    fields_of_study: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    article_types: list[str] = Field(default_factory=list)
    citation_count: int | None = None
    venue: str | None = None  # journal or conference venue


class DateRange(BaseModel):
    """Inclusive publication date range for search filters."""

    start: date | None = None  # None = no lower bound
    end: date | None = None  # None = no upper bound (today)


class SearchFilters(BaseModel):
    """Unified search filters — configured once, translated per source.

    Universal fields are supported by all sources. Source-prefixed fields
    (pubmed_*, europepmc_*, semanticscholar_*) are passed through only when
    targeting that source.

    Accepted publication_types values (mapped internally per source):
        "journal_article", "review", "systematic_review", "meta_analysis",
        "clinical_trial", "rct", "case_report", "conference_paper",
        "preprint", "book_chapter"
    """

    # Universal — supported by all sources
    date_range: DateRange | None = None
    languages: list[str] = Field(default_factory=list)  # ISO 639-1 codes: ["en", "fr"]
    has_abstract: bool = False

    # Publication type — common values mapped per source
    publication_types: list[str] = Field(default_factory=list)

    # PubMed-specific
    pubmed_species: list[str] = Field(default_factory=list)  # "human", "animal"
    pubmed_sex: list[str] = Field(default_factory=list)  # "male", "female"
    pubmed_age_groups: list[str] = Field(default_factory=list)
    # "infant", "child", "adolescent", "adult", "aged"
    pubmed_free_full_text: bool = False

    # Europe PMC-specific
    europepmc_sources: list[str] = Field(default_factory=lambda: ["MED"])
    # MED=MEDLINE, PMC=PubMed Central, PPR=preprints
    europepmc_open_access: bool = False
    europepmc_mesh_synonyms: bool = True

    # Semantic Scholar-specific
    semanticscholar_fields_of_study: list[str] = Field(default_factory=list)
    # "Medicine", "Biology", "Computer Science", etc.
    semanticscholar_open_access_pdf: bool = False
    semanticscholar_min_citation_count: int | None = None
    semanticscholar_venues: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Result of a Semantic Scholar search call — article ids only, not full records."""

    query: str
    article_ids: list[str]
    total_count: int
    retrieved_count: int
    searched_at: datetime
