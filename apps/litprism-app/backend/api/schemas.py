from datetime import date, datetime
from typing import Literal

from enums import ReviewType
from pydantic import BaseModel, ConfigDict, field_validator

# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    research_question: str | None = None
    review_type: ReviewType


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    research_question: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    research_question: str | None
    review_type: ReviewType
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Search runs
# ---------------------------------------------------------------------------


class SearchRunCreate(BaseModel):
    review_type: ReviewType
    query_natural: str | None = None
    query_final: str | None = None
    filters: dict | None = None


class SearchRunUpdate(BaseModel):
    query_natural: str | None = None
    query_final: str | None = None
    filters: dict | None = None


class SourceQueryOut(BaseModel):
    id: str
    source: str
    interface: str
    query_string: str
    filters_applied: dict
    filters_human_readable: str
    searched_at: datetime
    result_count: int
    model_config = ConfigDict(from_attributes=True)


class SearchRunOut(BaseModel):
    id: str
    project_id: str
    review_type: ReviewType
    query_natural: str | None
    query_generated: str | None
    query_final: str | None
    filters: dict | None
    status: str
    locked_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    source_queries: list[SourceQueryOut] = []
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------


class ArticleOut(BaseModel):
    id: str
    pmid: str | None
    doi: str | None
    source: str
    title: str
    abstract: str | None
    authors: list[dict]
    journal: str | None
    pub_date: date | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ArticleListOut(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Criteria
# ---------------------------------------------------------------------------


class CriteriaCreate(BaseModel):
    inclusion: list[str]
    exclusion: list[str]
    uncertain_threshold: float = 0.90

    @field_validator("inclusion")
    @classmethod
    def inclusion_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one inclusion criterion is required")
        if any(not c.strip() for c in v):
            raise ValueError("Criterion strings must not be blank")
        return v


class CriteriaOut(BaseModel):
    id: str
    project_id: str
    version: int
    inclusion: list[str]
    exclusion: list[str]
    uncertain_threshold: float
    created_at: datetime
    superseded_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class StaleCountOut(BaseModel):
    project_id: str
    active_criteria_version: int
    stale_results: int
    unscreened: int
    total_articles: int


# ---------------------------------------------------------------------------
# Screening preview (Session 7.2)
# ---------------------------------------------------------------------------


class PreviewArticle(BaseModel):
    id: str
    title: str
    abstract: str | None = None


class ScreeningPreviewRequest(BaseModel):
    criteria: CriteriaCreate
    articles: list[PreviewArticle]

    @field_validator("articles")
    @classmethod
    def max_ten_articles(cls, v: list[PreviewArticle]) -> list[PreviewArticle]:
        if not v:
            raise ValueError("At least one article is required")
        if len(v) > 10:
            raise ValueError(
                "Preview is limited to 10 articles. Use the full pipeline for larger batches."
            )
        return v


class PreviewCriteriaHit(BaseModel):
    criterion: str
    criterion_type: str
    assessment: str
    supporting_quote: str | None
    unassessable_reason: str | None


class ScreeningPreviewResult(BaseModel):
    article_id: str
    decision: str
    confidence: float
    reasoning: str
    criteria_hits: list[PreviewCriteriaHit]
    model_used: str


# ---------------------------------------------------------------------------
# Screening runs (Session 7.3)
# ---------------------------------------------------------------------------


class ScreeningRunCreate(BaseModel):
    stage: Literal["abstract", "fulltext"] = "abstract"
    chunk_size: int = 50


class ScreeningRunUpdate(BaseModel):
    reviewer_name: str | None = None
    review_notes: str | None = None


class ScreeningRunOut(BaseModel):
    id: str
    project_id: str
    criteria_id: str
    stage: str
    status: str
    total_articles: int
    screened_count: int
    error_count: int
    chunk_size: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    resumed_at: datetime | None
    reviewer_name: str | None
    review_notes: str | None
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Upload (Session 8)
# ---------------------------------------------------------------------------


class UploadResponseOut(BaseModel):
    upload_id: str
    filename: str
    format: str
    total_parsed: int
    new_articles: int
    duplicates_found: int
    project_id: str


class UploadMetadata(BaseModel):
    source_label: str | None = None
    search_strategy_used: str | None = None
    limits_applied: str | None = None


class UploadRecordOut(BaseModel):
    id: str
    filename: str
    format: str
    uploaded_at: datetime
    record_count: int
    source_label: str | None
    search_strategy_used: str | None
    limits_applied: str | None
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Search preview (Session 8.1)
# ---------------------------------------------------------------------------


class SearchPreviewRequest(BaseModel):
    query_final: str
    filters: dict | None = None
    sources: list[str] = ["pubmed", "europepmc", "semanticscholar"]


class SearchPreviewSource(BaseModel):
    source: str
    estimated_count: int
    sample_titles: list[str]
    error: str | None = None


class SearchPreviewResponse(BaseModel):
    total_estimated: int
    sources: list[SearchPreviewSource]
    query_translations: dict[str, str]
