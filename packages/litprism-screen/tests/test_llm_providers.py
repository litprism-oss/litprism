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
    assert config.model == "gemini-3.5-flash-lite"


def test_gemini_from_env_accepts_google_api_key_and_model_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.setenv("LLM_MODEL", "gemini-3.5-flash")
    config = from_env()
    assert isinstance(config, GeminiConfig)
    assert config.api_key == "google-key"
    assert config.model == "gemini-3.5-flash"


def test_gemini_from_env_prefers_gemini_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "primary")
    monkeypatch.setenv("GOOGLE_API_KEY", "fallback")
    assert from_env().api_key == "primary"


def test_gemini_from_env_requires_a_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        from_env()


def test_gemini_call_kwargs_use_litellm_gemini_route_and_json_mode():
    kwargs = _build_call_kwargs(GeminiConfig(api_key="k", model="gemini-3.5-flash"), "hello")
    assert kwargs == {
        "model": "gemini/gemini-3.5-flash",
        "messages": [{"role": "user", "content": "hello"}],
        "api_key": "k",
        "response_format": {"type": "json_object"},
    }


def test_openai_call_kwargs_unchanged():
    kwargs = _build_call_kwargs(OpenAIConfig(api_key="k", model="gpt-4o-mini"), "hi")
    assert kwargs["model"] == "gpt-4o-mini"
    assert "api_base" not in kwargs


def test_unknown_provider_error_lists_gemini(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(ValueError, match="gemini"):
        from_env()


# --- blank values in a .env (`LLM_MODEL=`) must mean "use the default" ---------------------


@pytest.mark.parametrize(
    ("provider", "key_env", "expected"),
    [
        ("openai", "OPENAI_API_KEY", "gpt-4o-mini"),
        ("gemini", "GEMINI_API_KEY", "gemini-3.5-flash-lite"),
        ("ollama", None, "llama3.2"),
    ],
)
def test_blank_llm_model_falls_back_to_the_default(monkeypatch, provider, key_env, expected):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_MODEL", "")
    if key_env:
        monkeypatch.setenv(key_env, "k")
    assert from_env().model == expected


def test_blank_ollama_settings_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "")  # float("") used to crash
    config = from_env()
    assert config.base_url == "http://localhost:11434"
    assert config.timeout == 300.0


def test_blank_azure_api_version_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_API_KEY", "k")
    monkeypatch.setenv("AZURE_API_BASE", "https://x.openai.azure.com")
    monkeypatch.setenv("AZURE_DEPLOYMENT_NAME", "d")
    monkeypatch.setenv("AZURE_API_VERSION", "")
    assert from_env().api_version == "2026-03-17"


def test_set_values_are_still_respected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "45")
    config = from_env()
    assert config.model == "qwen2.5:7b"
    assert config.timeout == 45.0
