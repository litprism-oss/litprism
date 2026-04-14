"""Prompt construction for LLM screening calls."""

from typing import Literal

from litprism.screen.criteria import Criteria
from litprism.screen.models import ReviewType, ScreenableArticle

# Conservatism instructions by review type.
# Applied only when in-text evidence is genuinely ambiguous — not when
# information is absent (absent information is always "unassessable").
_CONSERVATISM: dict[ReviewType, str] = {
    ReviewType.SYSTEMATIC: (
        "When in-text evidence is ambiguous, prefer 'unassessable' over 'refuted'. "
        "Err toward inclusion."
    ),
    ReviewType.RAPID: (
        "When in-text evidence is ambiguous, prefer 'unassessable' over 'refuted'. "
        "Err toward inclusion."
    ),
    ReviewType.SCOPING: (
        "Apply moderate judgement. Mark genuinely ambiguous in-text evidence as 'unassessable'."
    ),
    ReviewType.LITERATURE: (
        "Apply flexible judgement. You may mark clearly irrelevant articles as 'refuted'."
    ),
    ReviewType.STATE_OF_ART: (
        "Apply flexible judgement. You may mark clearly irrelevant articles as 'refuted'."
    ),
}

_PROMPT_TEMPLATE = """\
You are screening research articles for a {review_type} systematic review.
Your task is to assess each criterion against the title and abstract only.
You must ground every assessment in exact text from the article.

INCLUSION CRITERIA:
{inclusion_criteria}

EXCLUSION CRITERIA:
{exclusion_criteria}

ARTICLE:
Title: {title}
Abstract: {abstract}

ASSESSMENT RULES:
For each criterion, return one of three assessments:

  "confirmed"    — the title or abstract contains clear evidence that
                   this criterion IS met (inclusion) or IS triggered (exclusion).
                   You MUST copy the exact phrase that confirms this.

  "refuted"      — the title or abstract contains clear evidence that
                   this criterion is NOT met (inclusion) or NOT triggered (exclusion).
                   You MUST copy the exact phrase that refutes this.

  "unassessable" — the title or abstract does not contain enough information
                   to assess this criterion. This is NOT the same as refuted.
                   A criterion that is simply not mentioned is unassessable.
                   Provide a brief reason (e.g. "age of participants not stated").

CRITICAL: Do NOT treat silence as negative evidence.
If a criterion is not mentioned in the abstract, it is "unassessable", not "refuted".

CONSERVATISM: {conservatism_instruction}

Respond ONLY in valid JSON with no preamble:
{{
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence explanation of your overall assessment",
  "criteria_hits": [
    {{
      "criterion": "exact criterion text",
      "criterion_type": "inclusion" | "exclusion",
      "assessment": "confirmed" | "refuted" | "unassessable",
      "supporting_quote": "exact phrase from title or abstract, or null",
      "quote_location": "title" | "abstract" | null,
      "unassessable_reason": "brief reason, or null"
    }}
  ]
}}\
"""


def build_prompt(
    article: ScreenableArticle,
    criteria: Criteria,
    stage: Literal["abstract", "fulltext"],
) -> str:
    """Build the screening prompt for a single article."""
    inclusion = "\n".join(f"- {c}" for c in criteria.inclusion)
    exclusion = "\n".join(f"- {c}" for c in criteria.exclusion) if criteria.exclusion else "None"
    abstract = article.abstract or "(no abstract provided)"

    return _PROMPT_TEMPLATE.format(
        review_type=criteria.review_type.value,
        inclusion_criteria=inclusion,
        exclusion_criteria=exclusion,
        title=article.title,
        abstract=abstract,
        conservatism_instruction=_CONSERVATISM[criteria.review_type],
    )
