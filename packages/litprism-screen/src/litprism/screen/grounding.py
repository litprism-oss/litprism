"""Grounding validation and deterministic decision derivation.

The LLM's only job is to populate per-criterion assessments.
The final include / exclude / uncertain decision is derived here,
by pure Python logic with no LLM dependency.
"""

from typing import Literal

from litprism.screen.models import CriteriaAssessment, CriteriaHit
from pydantic import BaseModel


class _LLMCriterionResponse(BaseModel):
    """Internal model for a single criterion as returned by the LLM."""

    criterion: str
    criterion_type: Literal["inclusion", "exclusion"]
    assessment: CriteriaAssessment
    supporting_quote: str | None = None
    quote_location: Literal["title", "abstract"] | None = None
    unassessable_reason: str | None = None


class _LLMResponse(BaseModel):
    """Internal model for the full LLM JSON response."""

    confidence: float
    reasoning: str
    criteria_hits: list[_LLMCriterionResponse]


def derive_decision(
    hits: list[CriteriaHit],
) -> Literal["include", "exclude", "uncertain"]:
    """
    Deterministic decision from per-criterion assessments.

    Rules (applied in order, first match wins):
      1. Any confirmed exclusion → exclude immediately
      2. Any unassessable inclusion → uncertain (route to full-text)
      3. Any refuted inclusion → exclude
      4. All inclusion confirmed, no exclusions triggered → include
    """
    raise NotImplementedError


def validate_and_build(
    llm_response: _LLMResponse,
    title: str,
    abstract: str | None,
) -> list[CriteriaHit]:
    """Parse LLM output, validate quotes, return CriteriaHit list."""
    raise NotImplementedError
