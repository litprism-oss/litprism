"""LLM provider configuration — env parsing and litellm call kwargs."""

import pytest
from litprism.screen.llm import GeminiConfig, OpenAIConfig, _build_call_kwargs, from_env

PROVIDER_ENV = ("LLM_PROVIDER", "LLM_MODEL", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)


def test_gemini_from_env_uses_gemini_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    config = from_env()
    assert isinstance(config, GeminiConfig)
    assert config.api_key == "g-key"
    assert config.model == "gemini-2.5-flash"


def test_gemini_from_env_accepts_google_api_key_and_model_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-pro")
    config = from_env()
    assert isinstance(config, GeminiConfig)
    assert config.api_key == "google-key"
    assert config.model == "gemini-2.5-pro"


def test_gemini_from_env_prefers_gemini_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "primary")
    monkeypatch.setenv("GOOGLE_API_KEY", "fallback")
    assert from_env().api_key == "primary"


def test_gemini_from_env_requires_a_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        from_env()


def test_gemini_call_kwargs_use_litellm_gemini_route():
    kwargs = _build_call_kwargs(GeminiConfig(api_key="k", model="gemini-2.5-flash"), "hello")
    assert kwargs == {
        "model": "gemini/gemini-2.5-flash",
        "messages": [{"role": "user", "content": "hello"}],
        "api_key": "k",
    }


def test_openai_call_kwargs_unchanged():
    kwargs = _build_call_kwargs(OpenAIConfig(api_key="k", model="gpt-4o-mini"), "hi")
    assert kwargs["model"] == "gpt-4o-mini"
    assert "api_base" not in kwargs


def test_unknown_provider_error_lists_gemini(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(ValueError, match="gemini"):
        from_env()
