import pytest
from pydantic import ValidationError

from career_pilot.llm import load_llm_settings


def set_valid_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "aliyun-bailian")
    monkeypatch.setenv("LLM_API_KEY", "test-api-key")
    monkeypatch.setenv(
        "LLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setenv("LLM_DEFAULT_MODEL", "qwen-plus")


def test_load_llm_settings_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_valid_environment(monkeypatch)

    settings = load_llm_settings(env_file=None)

    assert settings.provider == "aliyun-bailian"
    assert settings.model == "qwen-plus"
    assert settings.api_key.get_secret_value() == "test-api-key"


def test_llm_api_key_is_hidden_when_printed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_valid_environment(monkeypatch)

    settings = load_llm_settings(env_file=None)

    assert "test-api-key" not in str(settings)
    assert "**********" in str(settings)


def test_load_llm_settings_rejects_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_valid_environment(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "   ")

    with pytest.raises(ValueError, match="LLM_API_KEY"):
        load_llm_settings(env_file=None)


def test_load_llm_settings_rejects_invalid_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_valid_environment(monkeypatch)
    monkeypatch.setenv(
        "LLM_BASE_URL",
        "dashscope.aliyuncs.com",
    )

    with pytest.raises(ValidationError):
        load_llm_settings(env_file=None)
