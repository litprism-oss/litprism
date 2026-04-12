"""Pydantic models for litprism-pubmed.

The Article model is the shared contract between litprism-pubmed and downstream
consumers (litprism-screen, the app backend). Each package defines its own copy
— there are no cross-package imports.
"""

from datetime import date, datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class Author(BaseModel):
    """A single article author."""

    last_name: str
    fore_name: str | None = None
    affiliation: str | None = None
    orcid: str | None = None


class Article(BaseModel):
    """Normalised article record.

    Produced by PubMedClient.fetch() and consumed by litprism-screen.
    """

    # Identity — at least one of id/pmid must be present
    id: str  # source-specific internal id (same as pmid for PubMed)
    pmid: str | None = None
    doi: str | None = None
    source: Literal["pubmed"] = "pubmed"
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

    # PubMed-specific
    mesh_terms: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    article_types: list[str] = Field(default_factory=list)
    citation_count: int | None = None  # not available from PubMed directly


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


# Backward-compat alias — existing imports of ArticleFilters continue to work.
# entrez.py and client.py reference filters.article_types; those files will be
# updated in a subsequent task to use filters.publication_types instead.
ArticleFilters = SearchFilters


class SearchResult(BaseModel):
    """Result of a PubMed esearch call — PMIDs only, not full records."""

    query: str
    pmids: list[str]
    total_count: int
    retrieved_count: int
    searched_at: datetime


class ScreenableArticle(Protocol):
    """Protocol satisfied by Article without importing litprism-screen."""

    @property
    def id(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def abstract(self) -> str | None: ...
