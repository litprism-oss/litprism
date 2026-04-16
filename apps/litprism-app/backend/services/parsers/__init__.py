from dataclasses import dataclass, field
from datetime import date


@dataclass
class ParsedArticle:
    title: str
    source: str = "upload"
    upload_format: str = ""
    pmid: str | None = None
    doi: str | None = None
    abstract: str | None = None
    authors: list[dict] = field(default_factory=list)
    journal: str | None = None
    pub_date: date | None = None
    keywords: list[str] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)
    article_types: list[str] = field(default_factory=list)
