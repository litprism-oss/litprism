"""LLM provider configuration and low-level call wrapper."""

import asyncio
import os
from typing import Literal

import litellm
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class OpenAIConfig(BaseModel):
    provider: Literal["openai"] = "openai"
    api_key: str
    model: str = "gpt-4o-mini"


class AzureOpenAIConfig(BaseModel):
    provider: Literal["azure"] = "azure"
    api_key: str
    azure_endpoint: str
    azure_deployment: str
    api_version: str = "2024-02-01"
    model: str = "azure/gpt-4o"


class OllamaConfig(BaseModel):
    provider: Literal["ollama"] = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "llama3.1"


LLMConfig = OpenAIConfig | AzureOpenAIConfig | OllamaConfig


def _build_call_kwargs(config: LLMConfig, prompt: str) -> dict:
    """Translate a config + prompt into kwargs for litellm.acompletion."""
    messages = [{"role": "user", "content": prompt}]
    if isinstance(config, OpenAIConfig):
        return {"model": config.model, "messages": messages, "api_key": config.api_key}
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
@retry(
    retry=retry_if_exception_type((litellm.RateLimitError, litellm.ServiceUnavailableError)),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _call_with_retry(kwargs: dict) -> str:
    response = await asyncio.wait_for(litellm.acompletion(**kwargs), timeout=60.0)
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("LLM returned an empty response")
    return content


async def call_llm(config: LLMConfig, prompt: str) -> str:
    """Call the configured LLM and return the raw JSON response string."""
    return await _call_with_retry(_build_call_kwargs(config, prompt))


def from_env() -> LLMConfig:
    """Construct an LLMConfig from environment variables."""
    provider = os.environ.get("LLM_PROVIDER", "openai")

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIConfig(
            api_key=api_key,
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
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
            api_version=os.environ.get("AZURE_API_VERSION", "2024-02-01"),
            model=os.environ.get("LLM_MODEL", "azure/gpt-4o"),
        )

    if provider == "ollama":
        return OllamaConfig(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.environ.get("LLM_MODEL", "llama3.1"),
        )

    raise ValueError(f"Unknown LLM_PROVIDER {provider!r}. Must be one of: openai, azure, ollama")
