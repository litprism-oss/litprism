"""Unit tests for derive_decision() and validate_and_build()."""

from pathlib import Path

from litprism.screen.grounding import _LLMResponse, derive_decision, validate_and_build
from litprism.screen.models import CriteriaAssessment, CriteriaHit

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hit(criterion_type: str, assessment: CriteriaAssessment) -> CriteriaHit:
    """Minimal CriteriaHit that satisfies the model validator."""
    if assessment in (CriteriaAssessment.CONFIRMED, CriteriaAssessment.REFUTED):
        return CriteriaHit(
            criterion="test criterion",
            criterion_type=criterion_type,
            assessment=assessment,
            supporting_quote="test quote",
        )
    return CriteriaHit(
        criterion="test criterion",
        criterion_type=criterion_type,
        assessment=assessment,
        unassessable_reason="not mentioned",
    )


def _load_fixture(name: str) -> _LLMResponse:
    return _LLMResponse.model_validate_json((FIXTURES / name).read_text())


# ---------------------------------------------------------------------------
# derive_decision() — all four rules plus edge cases
# ---------------------------------------------------------------------------


def test_confirmed_exclusion_excludes_immediately():
    """Rule 1: confirmed exclusion wins regardless of inclusion state."""
    hits = [
        _hit("inclusion", CriteriaAssessment.CONFIRMED),
        _hit("exclusion", CriteriaAssessment.CONFIRMED),
    ]
    assert derive_decision(hits) == "exclude"


def test_exclusion_takes_priority_over_unassessable_inclusion():
    """Rule 1 beats Rule 2: confirmed exclusion overrides unassessable inclusion."""
    hits = [
        _hit("inclusion", CriteriaAssessment.UNASSESSABLE),
        _hit("exclusion", CriteriaAssessment.CONFIRMED),
    ]
    assert derive_decision(hits) == "exclude"


def test_unassessable_inclusion_gives_uncertain():
    """Rule 2: unassessable inclusion → uncertain when no exclusion triggered."""
    hits = [
        _hit("inclusion", CriteriaAssessment.CONFIRMED),
        _hit("inclusion", CriteriaAssessment.UNASSESSABLE),
    ]
    assert derive_decision(hits) == "uncertain"


def test_only_unassessable_inclusion_is_uncertain():
    """Rule 2 applies with a single unassessable inclusion and no exclusions."""
    hits = [_hit("inclusion", CriteriaAssessment.UNASSESSABLE)]
    assert derive_decision(hits) == "uncertain"


def test_refuted_inclusion_excludes():
    """Rule 3: refuted inclusion → exclude when no confirmed exclusion or unassessable."""
    hits = [
        _hit("inclusion", CriteriaAssessment.CONFIRMED),
        _hit("inclusion", CriteriaAssessment.REFUTED),
    ]
    assert derive_decision(hits) == "exclude"


def test_all_confirmed_includes():
    """Rule 4: all inclusion confirmed, exclusion refuted → include."""
    hits = [
        _hit("inclusion", CriteriaAssessment.CONFIRMED),
        _hit("inclusion", CriteriaAssessment.CONFIRMED),
        _hit("exclusion", CriteriaAssessment.REFUTED),
    ]
    assert derive_decision(hits) == "include"


def test_empty_hits_returns_uncertain():
    """Edge case: empty list → uncertain (cannot include without evidence)."""
    assert derive_decision([]) == "uncertain"


# ---------------------------------------------------------------------------
# validate_and_build() — fixture-based and inline
# ---------------------------------------------------------------------------

# Abstract whose text contains the quotes used in include_response.json.
_INCLUDE_ABSTRACT = (
    "This randomised controlled trial enrolled adult participants aged 18 years and over "
    "with confirmed Crohn's disease who received probiotic therapy."
)


def test_include_fixture_passes_through_cleanly():
    """All quotes verified in haystack — no downgrades, assessments preserved."""
    llm_response = _load_fixture("include_response.json")
    hits = validate_and_build(llm_response, title="Probiotic RCT", abstract=_INCLUDE_ABSTRACT)

    assert len(hits) == 3
    assert hits[0].assessment == CriteriaAssessment.CONFIRMED
    assert hits[1].assessment == CriteriaAssessment.CONFIRMED
    assert hits[2].assessment == CriteriaAssessment.REFUTED
    assert hits[0].supporting_quote is not None
    assert hits[1].supporting_quote is not None
    assert derive_decision(hits) == "include"


def test_missing_quote_downgraded_to_unassessable():
    """CONFIRMED hit with null supporting_quote is downgraded; quote and location cleared."""
    llm_response = _load_fixture("missing_quote_response.json")
    hits = validate_and_build(llm_response, title="Some Title", abstract="Some abstract text.")

    assert len(hits) == 1
    hit = hits[0]
    assert hit.assessment == CriteriaAssessment.UNASSESSABLE
    assert hit.supporting_quote is None
    assert hit.quote_location is None
    assert hit.unassessable_reason == "LLM did not provide a supporting quote"


def test_unverified_quote_retains_assessment():
    """Quote present but not in source text: assessment kept, not downgraded."""
    llm_response = _LLMResponse.model_validate(
        {
            "confidence": 0.80,
            "reasoning": "Confirmed but quote absent from text.",
            "criteria_hits": [
                {
                    "criterion": "Randomised controlled trial",
                    "criterion_type": "inclusion",
                    "assessment": "confirmed",
                    "supporting_quote": "phrase that does not appear in the abstract",
                    "quote_location": "abstract",
                    "unassessable_reason": None,
                }
            ],
        }
    )
    hits = validate_and_build(llm_response, title="Some Title", abstract="Some abstract text.")

    assert hits[0].assessment == CriteriaAssessment.CONFIRMED
    assert hits[0].supporting_quote == "phrase that does not appear in the abstract"


def test_missing_unassessable_reason_filled_in():
    """UNASSESSABLE hit with null reason gets a default reason filled in."""
    llm_response = _LLMResponse.model_validate(
        {
            "confidence": 0.50,
            "reasoning": "Cannot assess.",
            "criteria_hits": [
                {
                    "criterion": "Adult participants (≥18 years)",
                    "criterion_type": "inclusion",
                    "assessment": "unassessable",
                    "supporting_quote": None,
                    "quote_location": None,
                    "unassessable_reason": None,
                }
            ],
        }
    )
    hits = validate_and_build(llm_response, title="Some Title", abstract="Some abstract text.")

    assert hits[0].assessment == CriteriaAssessment.UNASSESSABLE
    assert hits[0].unassessable_reason == "No reason provided by LLM"


def test_exclude_on_confirmed_exclusion_fixture():
    """End-to-end: confirmed exclusion in fixture → derive_decision returns exclude."""
    llm_response = _load_fixture("exclude_on_exclusion.json")
    hits = validate_and_build(
        llm_response,
        title="Gut microbiome in murine colitis models",
        abstract="We investigated probiotic effects in DSS-induced colitis in mice.",
    )
    assert derive_decision(hits) == "exclude"


def test_uncertain_fixture():
    """End-to-end: unassessable inclusion in fixture → derive_decision returns uncertain."""
    llm_response = _load_fixture("uncertain_response.json")
    hits = validate_and_build(
        llm_response,
        title="IBD study",
        abstract="We recruited human subjects with inflammatory bowel disease.",
    )
    assert derive_decision(hits) == "uncertain"


def test_exclude_on_refuted_inclusion_fixture():
    """End-to-end: refuted inclusion in fixture → derive_decision returns exclude."""
    llm_response = _load_fixture("exclude_on_refuted_inclusion.json")
    abstract = "This retrospective cohort study enrolled patients with confirmed Crohn's disease."
    hits = validate_and_build(
        llm_response,
        title="Retrospective analysis of Crohn's disease",
        abstract=abstract,
    )
    assert derive_decision(hits) == "exclude"
