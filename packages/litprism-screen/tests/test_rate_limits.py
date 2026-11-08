"""Rate limits: honour the provider's retry hint, lower default concurrency for Gemini."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import litellm
import pytest
from litprism.screen import llm
from litprism.screen.criteria import Criteria
from litprism.screen.exceptions import ScreeningError
from litprism.screen.llm import (
    GeminiConfig,
    OllamaConfig,
    OpenAIConfig,
    _call_with_retry,
    _retry_hint_seconds,
    call_budget,
    default_concurrency,
)
from litprism.screen.screener import Screener


def _rate_limit(message: str) -> litellm.RateLimitError:
    return litellm.RateLimitError(message=message, llm_provider="gemini", model="m")


def _ok(content: str = "{}"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def sleeps():
    """Replace the real sleep; returns the list of waits requested."""
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    with patch.object(llm, "_sleeper", fake_sleep):
        yield waits


# --- the hint -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("You exceeded your current quota. Please retry in 36.512345s.", 36.512345),
        ('{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "36s"}', 36.0),
        ('"retryDelay":"7.5s"', 7.5),
        ("Rate limited, retry in 12 s", 12.0),
        ("RETRY IN 5S", 5.0),
        ("Too many requests", None),
        ("Please retry later", None),
        ("retrying in a bit", None),
        ("", None),
    ],
)
def test_retry_hint_parsing(message, expected):
    hint = _retry_hint_seconds(RuntimeError(message))
    assert hint == pytest.approx(expected) if expected is not None else hint is None


# --- waiting -----------------------------------------------------------------------------


async def test_waits_for_the_providers_hint_not_a_second_or_two(sleeps):
    err = _rate_limit("quota exceeded. Please retry in 30s.")
    with patch.object(llm.litellm, "acompletion", AsyncMock(side_effect=[err, err, _ok("done")])):
        assert await _call_with_retry({}, 60) == "done"
    assert sleeps == [31.0, 31.0]  # hint + 1 s, twice


async def test_a_huge_hint_is_capped(sleeps):
    err = _rate_limit("Please retry in 3600s")
    with patch.object(llm.litellm, "acompletion", AsyncMock(side_effect=[err, _ok()])):
        await _call_with_retry({}, 60)
    assert sleeps == [llm._MAX_RATE_LIMIT_WAIT]


async def test_a_tiny_hint_still_gets_the_normal_backoff(sleeps):
    err = _rate_limit("Please retry in 0.2s")
    with patch.object(llm.litellm, "acompletion", AsyncMock(side_effect=[err, err, _ok()])):
        await _call_with_retry({}, 60)
    assert sleeps == [1.2, 2.0]  # max(backoff, hint + 1): 1.2 then the 2 s backoff


async def test_without_a_hint_it_is_plain_exponential_backoff(sleeps):
    err = _rate_limit("Too many requests")
    with patch.object(llm.litellm, "acompletion", AsyncMock(side_effect=[err, err, _ok()])):
        await _call_with_retry({}, 60)
    assert sleeps == [1.0, 2.0]


async def test_service_unavailable_uses_backoff_too(sleeps):
    err = litellm.ServiceUnavailableError(message="high demand", llm_provider="gemini", model="m")
    with patch.object(llm.litellm, "acompletion", AsyncMock(side_effect=[err, _ok("ok")])):
        assert await _call_with_retry({}, 60) == "ok"
    assert sleeps == [1.0]


async def test_gives_up_after_three_attempts_and_raises(sleeps):
    err = _rate_limit("Please retry in 10s")
    mock = AsyncMock(side_effect=err)
    with (
        patch.object(llm.litellm, "acompletion", mock),
        pytest.raises(litellm.RateLimitError),
    ):
        await _call_with_retry({}, 60)
    assert mock.await_count == 3
    assert sleeps == [11.0, 11.0]


async def test_other_errors_are_not_retried(sleeps):
    mock = AsyncMock(side_effect=ValueError("bad request"))
    with patch.object(llm.litellm, "acompletion", mock), pytest.raises(ValueError):
        await _call_with_retry({}, 60)
    assert mock.await_count == 1
    assert sleeps == []


# --- the outer guard must leave room for those waits ---------------------------------------


def test_call_budget_covers_every_attempt_and_every_wait():
    budget = call_budget(GeminiConfig(api_key="k"))
    assert budget >= 3 * 60 + 2 * llm._MAX_RATE_LIMIT_WAIT
    # The old guard (65 s) would have cancelled the very first rate-limit wait.
    assert budget > 65 + llm._MAX_RATE_LIMIT_WAIT


def test_call_budget_follows_the_ollama_timeout():
    assert call_budget(OllamaConfig(timeout=300)) > call_budget(OpenAIConfig(api_key="k"))


async def test_screener_outer_guard_comes_from_call_budget():
    article = SimpleNamespace(id="a", title="T", abstract="An abstract.")

    async def hangs(config, prompt):
        await asyncio.sleep(5)

    screener = Screener(OpenAIConfig(api_key="k"))
    with (
        patch("litprism.screen.screener.call_budget", return_value=0.05),
        patch("litprism.screen.screener.call_llm", hangs),
        pytest.raises(ScreeningError) as caught,
    ):
        await screener._screen_one(article, Criteria(inclusion=["RCT"]), stage="abstract")
    assert isinstance(caught.value.cause, TimeoutError)


# --- concurrency ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("LLM_CONCURRENCY", "LLM_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_gemini_defaults_to_low_concurrency():
    assert default_concurrency(GeminiConfig(api_key="k")) == 3


def test_other_providers_keep_ten():
    assert default_concurrency(OpenAIConfig(api_key="k")) == 10
    assert default_concurrency(OllamaConfig()) == 10


def test_env_var_overrides_the_default(monkeypatch):
    monkeypatch.setenv("LLM_CONCURRENCY", "6")
    assert default_concurrency(GeminiConfig(api_key="k")) == 6
    assert default_concurrency(OpenAIConfig(api_key="k")) == 6


@pytest.mark.parametrize("raw", ["", "  ", "abc", "0", "-2", "2.5"])
def test_bad_env_values_fall_back_to_the_default(monkeypatch, raw):
    monkeypatch.setenv("LLM_CONCURRENCY", raw)
    assert default_concurrency(GeminiConfig(api_key="k")) == 3


def test_from_env_uses_the_provider_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert Screener.from_env()._sem._value == 3


def test_from_env_explicit_concurrency_wins(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("LLM_CONCURRENCY", "6")
    assert Screener.from_env(concurrency=2)._sem._value == 2
    assert Screener.from_env()._sem._value == 6


def test_from_env_openai_is_unchanged(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert Screener.from_env()._sem._value == 10
