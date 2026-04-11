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


class ArticleFilters(BaseModel):
    """Optional filters applied to a PubMed search."""

    article_types: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    has_abstract: bool = False


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
