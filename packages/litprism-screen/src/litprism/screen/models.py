"""Data models for litprism-screen."""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator


class ReviewType(StrEnum):
    SYSTEMATIC = "systematic"
    RAPID = "rapid"
    SCOPING = "scoping"
    LITERATURE = "literature"
    STATE_OF_ART = "state_of_art"


class CriteriaAssessment(StrEnum):
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    UNASSESSABLE = "unassessable"


class CriteriaHit(BaseModel):
    criterion: str
    criterion_type: Literal["inclusion", "exclusion"]
    assessment: CriteriaAssessment
    supporting_quote: str | None = None
    quote_location: Literal["title", "abstract", "section"] | None = None
    unassessable_reason: str | None = None

    @model_validator(mode="after")
    def _check_assessment_fields(self) -> "CriteriaHit":
        if (
            self.assessment in (CriteriaAssessment.CONFIRMED, CriteriaAssessment.REFUTED)
            and not self.supporting_quote
        ):
            raise ValueError(f"supporting_quote is required when assessment is {self.assessment!r}")
        if self.assessment == CriteriaAssessment.UNASSESSABLE and not self.unassessable_reason:
            raise ValueError("unassessable_reason is required when assessment is 'unassessable'")
        return self


class ScreeningResult(BaseModel):
    article_id: str
    decision: Literal["include", "exclude", "uncertain"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    criteria_hits: list[CriteriaHit]
    stage: Literal["abstract", "fulltext"]
    model_used: str
    llm_provider: str
    screened_at: datetime
    human_override: bool = False
    human_decision: str | None = None
    human_note: str | None = None


class ScreenableArticle(Protocol):
    """Protocol satisfied by Article objects from any litprism search package."""

    @property
    def id(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def abstract(self) -> str | None: ...
