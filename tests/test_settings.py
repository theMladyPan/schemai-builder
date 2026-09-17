"""Tests for settings env parsing (pydantic-settings skill)."""

from schemai_builder.config.settings import Settings


def test_defaults_without_env(monkeypatch):
    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("SCHEMAI_PROJECT", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    s = Settings(_env_file=None)
    assert s.project == "schemai"
    assert s.environment == "local"
    assert s.debug is False
    assert s.logfire.token is None


def test_token_from_env(monkeypatch):
    monkeypatch.setenv("LOGFIRE_TOKEN", "pylf_test")
    s = Settings(_env_file=None)
    assert s.logfire.token_value == "pylf_test"


def test_blank_token_is_none(monkeypatch):
    monkeypatch.setenv("LOGFIRE_TOKEN", "   ")
    s = Settings(_env_file=None)
    assert s.logfire.token is None


def test_nested_fields_with_underscores(monkeypatch):
    monkeypatch.setenv("LOGFIRE_TOKEN", "t1")
    s = Settings(_env_file=None)
    assert s.logfire.token_value == "t1"  # not split as logfire.token (max_split=1)


def test_llm_model_default(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    s = Settings(_env_file=None)
    assert s.llm_model == "openrouter:z-ai/glm-5.3-flash"


def test_llm_model_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter:openai/gpt-4.1-mini")
    s = Settings(_env_file=None)
    assert s.llm_model == "openrouter:openai/gpt-4.1-mini"
