"""Unit tests for Screener — mocked LLM, no real network."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

from litprism.screen.criteria import Criteria
from litprism.screen.llm import OpenAIConfig
from litprism.screen.models import CriteriaAssessment
from litprism.screen.screener import Screener

FIXTURES = Path(__file__).parent / "fixtures"

_LLM_CONFIG = OpenAIConfig(api_key="test-key")

# screener.py: from litprism.screen.llm import ... call_llm
_PATCH = "litprism.screen.screener.call_llm"


# ---------------------------------------------------------------------------
# Minimal concrete ScreenableArticle implementation
# ---------------------------------------------------------------------------


@dataclass
class _Article:
    id: str
    title: str
    abstract: str | None


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Abstract whose text contains all quotes in include_response.json.
_INCLUDE_ABSTRACT = (
    "This randomised controlled trial enrolled adult participants aged 18 years and over "
    "with confirmed Crohn's disease who received probiotic therapy."
)

_INCLUDE_CRITERIA = Criteria(
    inclusion=["Randomised controlled trial", "Adult participants (≥18 years)"],
    exclusion=["Animal or in vitro study"],
)


# ---------------------------------------------------------------------------
# Test 1 — no abstract: early return, LLM never called
# ---------------------------------------------------------------------------


async def test_no_abstract_returns_uncertain_without_llm_call():
    screener = Screener(_LLM_CONFIG)
    article = _Article(id="pmid:1", title="Some Study", abstract=None)
    criteria = Criteria(inclusion=["Randomised controlled trial"])

    mock = AsyncMock()
    with patch(_PATCH, mock):
        result = await screener._screen_one(article, criteria, stage="abstract")

    assert result.decision == "uncertain"
    assert result.confidence == 0.0
    assert result.criteria_hits == []
    mock.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2 — include path end-to-end
# ---------------------------------------------------------------------------


async def test_include_path_end_to_end():
    screener = Screener(_LLM_CONFIG)
    article = _Article(id="pmid:2", title="Probiotic RCT", abstract=_INCLUDE_ABSTRACT)
    include_json = (FIXTURES / "include_response.json").read_text()

    mock = AsyncMock(return_value=include_json)
    with patch(_PATCH, mock):
        result = await screener._screen_one(article, _INCLUDE_CRITERIA, stage="abstract")

    assert result.decision == "include"
    assert result.confidence == 0.95
    assert len(result.criteria_hits) == 3
    assert result.criteria_hits[0].assessment == CriteriaAssessment.CONFIRMED
    assert result.criteria_hits[1].assessment == CriteriaAssessment.CONFIRMED
    assert result.criteria_hits[2].assessment == CriteriaAssessment.REFUTED


# ---------------------------------------------------------------------------
# Test 3 — exclude on confirmed exclusion criterion
# ---------------------------------------------------------------------------


async def test_exclude_on_confirmed_exclusion():
    screener = Screener(_LLM_CONFIG)
    article = _Article(
        id="pmid:3",
        title="Gut microbiome in murine colitis models",
        abstract="We investigated probiotic effects in DSS-induced colitis in mice.",
    )
    exclude_json = (FIXTURES / "exclude_on_exclusion.json").read_text()
    criteria = Criteria(
        inclusion=["Adult participants (≥18 years)"],
        exclusion=["Animal or in vitro study"],
    )

    mock = AsyncMock(return_value=exclude_json)
    with patch(_PATCH, mock):
        result = await screener._screen_one(article, criteria, stage="abstract")

    assert result.decision == "exclude"
    assert result.confidence == 0.98


# ---------------------------------------------------------------------------
# Test 4 — uncertain path end-to-end
# ---------------------------------------------------------------------------


async def test_uncertain_path_end_to_end():
    screener = Screener(_LLM_CONFIG)
    article = _Article(
        id="pmid:4",
        title="IBD study",
        abstract="We recruited human subjects with inflammatory bowel disease.",
    )
    uncertain_json = (FIXTURES / "uncertain_response.json").read_text()
    criteria = Criteria(
        inclusion=["Randomised controlled trial"],
        exclusion=["Animal or in vitro study"],
    )

    mock = AsyncMock(return_value=uncertain_json)
    with patch(_PATCH, mock):
        result = await screener._screen_one(article, criteria, stage="abstract")

    assert result.decision == "uncertain"


# ---------------------------------------------------------------------------
# Test 5 — batch isolates errors: one failure does not abort the rest
# ---------------------------------------------------------------------------


async def test_batch_isolates_errors():
    screener = Screener(_LLM_CONFIG)
    include_json = (FIXTURES / "include_response.json").read_text()

    article_1 = _Article(id="pmid:10", title="Probiotic RCT", abstract=_INCLUDE_ABSTRACT)
    article_2 = _Article(id="pmid:11", title="Failing Study", abstract="Some abstract.")
    article_3 = _Article(id="pmid:12", title="Probiotic RCT 2", abstract=_INCLUDE_ABSTRACT)

    mock = AsyncMock(side_effect=[include_json, RuntimeError("provider down"), include_json])
    with patch(_PATCH, mock):
        results, errors = await screener.ascreen_batch(
            [article_1, article_2, article_3], _INCLUDE_CRITERIA
        )

    assert len(results) == 2
    assert len(errors) == 1
    assert errors[0].article_id == article_2.id
    assert isinstance(errors[0].cause, RuntimeError)
    assert results[0].decision == "include"
    assert results[1].decision == "include"


# ---------------------------------------------------------------------------
# Test 6 — ascreen_batch return type
# ---------------------------------------------------------------------------


async def test_ascreen_batch_returns_correct_tuple_types():
    screener = Screener(_LLM_CONFIG)
    include_json = (FIXTURES / "include_response.json").read_text()

    article_1 = _Article(id="pmid:20", title="Probiotic RCT", abstract=_INCLUDE_ABSTRACT)
    article_2 = _Article(id="pmid:21", title="Probiotic RCT 2", abstract=_INCLUDE_ABSTRACT)

    mock = AsyncMock(return_value=include_json)
    with patch(_PATCH, mock):
        output = await screener.ascreen_batch([article_1, article_2], _INCLUDE_CRITERIA)

    results, errors = output
    assert isinstance(output, tuple)
    assert len(output) == 2
    assert isinstance(results, list)
    assert isinstance(errors, list)
    assert errors == []
