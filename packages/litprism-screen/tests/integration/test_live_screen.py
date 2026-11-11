"""Integration tests — require a real LLM API key in the environment.

Run with:
    uv run pytest packages/litprism-screen/tests/integration/ -v -m integration
"""

from dataclasses import dataclass

import pytest
from litprism.screen.criteria import Criteria
from litprism.screen.models import CriteriaAssessment, ReviewType
from litprism.screen.screener import Screener

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Minimal concrete ScreenableArticle implementation
# ---------------------------------------------------------------------------


@dataclass
class _Article:
    id: str
    title: str
    abstract: str | None


# ---------------------------------------------------------------------------
# Shared criteria (same across all three tests)
# ---------------------------------------------------------------------------

_CRITERIA = Criteria(
    review_type=ReviewType.SYSTEMATIC,
    inclusion=[
        "Randomised controlled trial",
        "Adult participants aged 18 years or older",
        "Probiotic intervention",
    ],
    exclusion=[
        "Animal or in vitro study",
        "No full text available",
    ],
)


# ---------------------------------------------------------------------------
# Test 1 — clear include
# ---------------------------------------------------------------------------


async def test_live_include():
    screener = Screener.from_env()
    article = _Article(
        id="test_include_1",
        title=(
            "Probiotic supplementation in adults with Crohn's disease: "
            "a randomised controlled trial"
        ),
        abstract=(
            "Background: We conducted a randomised controlled trial in adults (≥18 years) "
            "with confirmed Crohn's disease. Methods: Participants received daily probiotic "
            "supplementation or placebo for 12 weeks."
        ),
    )

    results, errors = await screener.ascreen_batch([article], _CRITERIA)

    assert len(errors) == 0
    result = results[0]

    assert result.decision == "include"
    assert result.confidence >= 0.80

    inclusion_hits = [h for h in result.criteria_hits if h.criterion_type == "inclusion"]
    exclusion_hits = [h for h in result.criteria_hits if h.criterion_type == "exclusion"]

    assert all(h.assessment == CriteriaAssessment.CONFIRMED for h in inclusion_hits)
    assert not any(h.assessment == CriteriaAssessment.CONFIRMED for h in exclusion_hits)
    assert all(
        h.supporting_quote and h.supporting_quote.strip()
        for h in result.criteria_hits
        if h.assessment == CriteriaAssessment.CONFIRMED
    )


# ---------------------------------------------------------------------------
# Test 2 — clear exclude via confirmed exclusion criterion
# ---------------------------------------------------------------------------


async def test_live_exclude_on_exclusion():
    screener = Screener.from_env()
    article = _Article(
        id="test_exclude_1",
        title="Probiotic effects on gut microbiome in murine colitis",
        abstract=(
            "We investigated the effects of Lactobacillus in a DSS-induced colitis mouse model. "
            "Male C57BL/6 mice were randomised to probiotic or control diet."
        ),
    )

    results, errors = await screener.ascreen_batch([article], _CRITERIA)

    assert len(errors) == 0
    result = results[0]

    assert result.decision == "exclude"
    assert result.confidence >= 0.80

    confirmed_exclusions = [
        h
        for h in result.criteria_hits
        if h.criterion_type == "exclusion" and h.assessment == CriteriaAssessment.CONFIRMED
    ]
    assert len(confirmed_exclusions) >= 1
    assert all(h.supporting_quote and h.supporting_quote.strip() for h in confirmed_exclusions)


# ---------------------------------------------------------------------------
# Test 3 — uncertain: key study design info absent from abstract
# ---------------------------------------------------------------------------


async def test_live_uncertain():
    screener = Screener.from_env()
    article = _Article(
        id="test_uncertain_1",
        title="Gut microbiome modulation and intestinal inflammation",
        abstract=(
            "This study examined the relationship between microbiome composition and "
            "intestinal inflammation markers in patients with inflammatory bowel disease."
        ),
    )

    results, errors = await screener.ascreen_batch([article], _CRITERIA)

    assert len(errors) == 0
    result = results[0]

    assert result.decision == "uncertain"

    unassessable_inclusions = [
        h
        for h in result.criteria_hits
        if h.criterion_type == "inclusion" and h.assessment == CriteriaAssessment.UNASSESSABLE
    ]
    assert len(unassessable_inclusions) >= 1
