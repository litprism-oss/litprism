"""Grounding validation and deterministic decision derivation.

The LLM's only job is to populate per-criterion assessments.
The final include / exclude / uncertain decision is derived here,
by pure Python logic with no LLM dependency.
"""

import logging
from typing import Literal

from litprism.screen.models import CriteriaAssessment, CriteriaHit
from pydantic import BaseModel, Field

_logger = logging.getLogger(__name__)


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

    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    criteria_hits: list[_LLMCriterionResponse]


def derive_decision(
    hits: list[CriteriaHit],
) -> Literal["include", "exclude", "uncertain"]:
    """
    Deterministic decision from per-criterion assessments.

    Rules (applied in order, first match wins):
      1. Any confirmed exclusion  → exclude immediately
      2. Any unassessable inclusion → uncertain (route to full-text)
      3. Any refuted inclusion    → exclude
      4. Otherwise               → include

    An empty hits list returns uncertain.
    """
    if not hits:
        return "uncertain"

    exclusions = [h for h in hits if h.criterion_type == "exclusion"]
    inclusions = [h for h in hits if h.criterion_type == "inclusion"]

    if any(h.assessment == CriteriaAssessment.CONFIRMED for h in exclusions):
        return "exclude"

    if any(h.assessment == CriteriaAssessment.UNASSESSABLE for h in inclusions):
        return "uncertain"

    if any(h.assessment == CriteriaAssessment.REFUTED for h in inclusions):
        return "exclude"

    return "include"


def _extract_json(raw: str) -> str:
    """
    Extract the first complete JSON object from LLM output.

    Handles common local model formatting issues:
      - Markdown code fences: ```json ... ``` or ``` ... ```
      - Preamble prose before the JSON block
      - Trailing text or explanation after the closing brace

    Raises ValueError if no JSON object is found.
    """
    import re

    # Strip markdown code fences first
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = raw.replace("```", "").strip()

    # Find outermost { ... } block
    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in LLM output. First 200 chars: {raw[:200]!r}")

    return raw[start : end + 1]


def validate_and_build(
    llm_response: _LLMResponse,
    title: str,
    abstract: str | None,
) -> list[CriteriaHit]:
    """Parse LLM output, validate quotes, return CriteriaHit list.

    Confirmed/refuted assessments without a supporting quote are downgraded
    to unassessable. Quotes that cannot be found in the source text are kept
    but logged — the assessment is not silently changed.
    """
    haystack = f"{title} {abstract or ''}".lower()
    hits: list[CriteriaHit] = []

    for raw in llm_response.criteria_hits:
        assessment = raw.assessment
        supporting_quote = raw.supporting_quote
        quote_location = raw.quote_location
        unassessable_reason = raw.unassessable_reason

        needs_quote = assessment in (CriteriaAssessment.CONFIRMED, CriteriaAssessment.REFUTED)

        if needs_quote and not supporting_quote:
            _logger.warning(
                "No supporting quote for %r (%s) — downgrading to unassessable",
                raw.criterion,
                assessment,
            )
            assessment = CriteriaAssessment.UNASSESSABLE
            supporting_quote = None
            quote_location = None
            unassessable_reason = "LLM did not provide a supporting quote"

        elif needs_quote and supporting_quote and supporting_quote.lower() not in haystack:
            _logger.warning(
                "Supporting quote not found in article text for %r: %r",
                raw.criterion,
                supporting_quote,
            )
            # Retain the assessment — do not downgrade. Logged for human audit.

        elif assessment == CriteriaAssessment.UNASSESSABLE and not unassessable_reason:
            _logger.warning("No unassessable reason provided for %r", raw.criterion)
            unassessable_reason = "No reason provided by LLM"

        hits.append(
            CriteriaHit(
                criterion=raw.criterion,
                criterion_type=raw.criterion_type,
                assessment=assessment,
                supporting_quote=supporting_quote,
                quote_location=quote_location,
                unassessable_reason=unassessable_reason,
            )
        )

    return hits
