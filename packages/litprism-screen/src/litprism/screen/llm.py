"""LLM provider configuration and low-level call wrapper."""

import asyncio
import os
import re
from typing import Literal

import litellm
from pydantic import BaseModel
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class OpenAIConfig(BaseModel):
    provider: Literal["openai"] = "openai"
    api_key: str
    model: str = "gpt-4o-mini"


class GeminiConfig(BaseModel):
    provider: Literal["gemini"] = "gemini"
    api_key: str
    model: str = "gemini-3.5-flash-lite"


class AzureOpenAIConfig(BaseModel):
    provider: Literal["azure"] = "azure"
    api_key: str
    azure_endpoint: str
    azure_deployment: str
    api_version: str = "2026-03-17"


class OllamaConfig(BaseModel):
    provider: Literal["ollama"] = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    timeout: float = 300.0


LLMConfig = OpenAIConfig | AzureOpenAIConfig | GeminiConfig | OllamaConfig


def _build_call_kwargs(config: LLMConfig, prompt: str) -> dict:
    """Translate a config + prompt into kwargs for litellm.acompletion."""
    messages = [{"role": "user", "content": prompt}]
    if isinstance(config, OpenAIConfig):
        return {"model": config.model, "messages": messages, "api_key": config.api_key}
    if isinstance(config, GeminiConfig):
        # litellm routes "gemini/<model>" to the Google AI Studio API.
        return {
            "model": f"gemini/{config.model}",
            "messages": messages,
            "api_key": config.api_key,
            # Sent as responseMimeType=application/json. Without it Gemini 3.x models
            # sometimes return syntactically broken JSON.
            "response_format": {"type": "json_object"},
        }
    if isinstance(config, AzureOpenAIConfig):
        return {
            "model": f"azure/{config.azure_deployment}",
            "messages": messages,
            "api_key": config.api_key,
            "api_base": config.azure_endpoint,
            "api_version": config.api_version,
        }
    # OllamaConfig
    return {
        "model": f"ollama/{config.model}",
        "messages": messages,
        "api_base": config.base_url,
    }


# asyncio.TimeoutError is intentionally not retried.
# A timeout means the provider is hanging, not rate-limiting.
# Retrying a hang would block this semaphore slot for up to
# 3 × 60 s = 3 minutes. Let it surface as ScreeningError immediately.
def _get_timeout(config: LLMConfig) -> float:
    if isinstance(config, OllamaConfig):
        return config.timeout
    return 60.0


_RETRY_ATTEMPTS = 3
# Longest we will wait between attempts for a rate limit to clear.
_MAX_RATE_LIMIT_WAIT = 90.0

# Google tells us how long to wait: "Please retry in 36.5s" in the message and
# "retryDelay": "36s" in the error details.
_RETRY_HINT = re.compile(r'retry(?: in|Delay"?\s*:)\s*"?(\d+(?:\.\d+)?)\s*s', re.IGNORECASE)
_backoff = wait_exponential(multiplier=1, min=1, max=60)


def _retry_hint_seconds(exc: BaseException) -> float | None:
    """Seconds the provider asked us to wait, if the error says so."""
    match = _RETRY_HINT.search(str(exc))
    return float(match.group(1)) if match else None


def _wait_before_retry(retry_state: RetryCallState) -> float:
    """Exponential backoff, or the provider's own hint (plus a second) if that is longer.

    A free-tier per-minute quota needs ~30-60 s to reset; a 1-2 s backoff just burns attempts.
    """
    backoff = _backoff(retry_state)
    outcome = retry_state.outcome
    exc = outcome.exception() if outcome is not None else None
    hint = _retry_hint_seconds(exc) if exc is not None else None
    if hint is None:
        return backoff
    return min(max(backoff, hint + 1.0), _MAX_RATE_LIMIT_WAIT)


async def _real_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


_sleeper = _real_sleep  # a seam tests replace so they don't really wait


async def _sleep(seconds: float) -> None:
    # Looked up at call time: tenacity captures this function when the decorator is built,
    # so patching a module attribute that the decorator references directly has no effect.
    await _sleeper(seconds)


def call_budget(config: LLMConfig) -> float:
    """Upper bound for one call_llm(), retries and rate-limit waits included.

    Each attempt is already bounded by _get_timeout(); this is only the outer safety net.
    """
    attempts, waits = _RETRY_ATTEMPTS, _RETRY_ATTEMPTS - 1
    return _get_timeout(config) * attempts + _MAX_RATE_LIMIT_WAIT * waits + 5


@retry(
    retry=retry_if_exception_type((litellm.RateLimitError, litellm.ServiceUnavailableError)),
    wait=_wait_before_retry,
    stop=stop_after_attempt(_RETRY_ATTEMPTS),
    sleep=_sleep,
    reraise=True,
)
async def _call_with_retry(kwargs: dict, timeout: float) -> str:
    response = await asyncio.wait_for(litellm.acompletion(**kwargs), timeout=timeout)
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("LLM returned an empty response")
    return content


async def call_llm(config: LLMConfig, prompt: str) -> str:
    """Call the configured LLM and return the raw JSON response string."""
    return await _call_with_retry(_build_call_kwargs(config, prompt), _get_timeout(config))


# Free Gemini keys allow only a few requests a minute; a lower default avoids 429s.
_DEFAULT_CONCURRENCY = {"gemini": 3}
_FALLBACK_CONCURRENCY = 10


def default_concurrency(config: LLMConfig) -> int:
    """LLM_CONCURRENCY if set to a positive integer, else a per-provider default."""
    raw = os.environ.get("LLM_CONCURRENCY", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return _DEFAULT_CONCURRENCY.get(config.provider, _FALLBACK_CONCURRENCY)


def _env(name: str, default: str) -> str:
    """Like os.environ.get, but a blank value (`LLM_MODEL=` in a .env) uses the default."""
    return os.environ.get(name) or default


def from_env() -> LLMConfig:
    """Construct an LLMConfig from environment variables."""
    provider = os.environ.get("LLM_PROVIDER", "openai")

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIConfig(
            api_key=api_key,
            model=_env("LLM_MODEL", "gpt-4o-mini"),
        )

    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        return GeminiConfig(
            api_key=api_key,
            model=_env("LLM_MODEL", "gemini-3.5-flash-lite"),
        )

    if provider == "azure":
        api_key = os.environ.get("AZURE_API_KEY")
        azure_endpoint = os.environ.get("AZURE_API_BASE")
        azure_deployment = os.environ.get("AZURE_DEPLOYMENT_NAME")
        missing = [
            name
            for name, val in {
                "AZURE_API_KEY": api_key,
                "AZURE_API_BASE": azure_endpoint,
                "AZURE_DEPLOYMENT_NAME": azure_deployment,
            }.items()
            if not val
        ]
        if missing:
            raise ValueError(
                f"Missing required environment variables for Azure: {', '.join(missing)}"
            )
        return AzureOpenAIConfig(
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            azure_deployment=azure_deployment,
            api_version=_env("AZURE_API_VERSION", "2026-03-17"),
        )

    if provider == "ollama":
        return OllamaConfig(
            base_url=_env("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=_env("LLM_MODEL", "llama3.2"),
            timeout=float(_env("OLLAMA_TIMEOUT", "300")),
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER {provider!r}. Must be one of: openai, azure, gemini, ollama"
    )
