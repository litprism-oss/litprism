"""Eligibility criteria definition for systematic review screening."""

from litprism.screen.models import ReviewType
from pydantic import BaseModel, ValidationInfo, field_validator


class Criteria(BaseModel):
    review_type: ReviewType = ReviewType.SYSTEMATIC
    inclusion: list[str]
    exclusion: list[str] = []

    @field_validator("inclusion")
    @classmethod
    def _inclusion_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("inclusion criteria must not be empty")
        return v

    @field_validator("inclusion", "exclusion")
    @classmethod
    def _no_blank_criteria(cls, v: list[str], info: ValidationInfo) -> list[str]:
        blank = [c for c in v if not c.strip()]
        if blank:
            raise ValueError(f"{info.field_name} contains blank criterion")
        return v
