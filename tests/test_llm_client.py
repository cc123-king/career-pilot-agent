from types import SimpleNamespace

import pytest

from career_pilot.llm import LLMClient, LLMSettings
from career_pilot.rag.models import RetrievalContext


class FakeCompletions:
    def __init__(self, answer: str | None) -> None:
        self.answer = answer
        self.last_request: dict[str, object] | None = None

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.last_request = kwargs

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=self.answer,
                    )
                )
            ]
        )


class FakeOpenAI:
    def __init__(self, answer: str | None) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(answer))


def make_settings() -> LLMSettings:
    return LLMSettings(
        provider="aliyun-bailian",
        api_key="test-api-key",
        base_url=("https://dashscope.aliyuncs.com/compatible-mode/v1"),
        model="qwen-plus",
    )


def make_context() -> RetrievalContext:
    return RetrievalContext(
        query="Agent 项目经验怎么写？",
        content=(
            "[资料1]\n标题：简历指南\n内容：项目经验需要说明问题、技术方案和结果。"
        ),
        sources=[],
    )


def test_answer_with_context_sends_grounded_prompt() -> None:
    fake_client = FakeOpenAI("建议说明项目问题、技术方案和结果。[资料1]")
    llm_client = LLMClient(
        make_settings(),
        client=fake_client,
    )

    answer = llm_client.answer_with_context(
        "Agent 项目经验怎么写？",
        make_context(),
    )

    request = fake_client.chat.completions.last_request

    assert request is not None
    assert request["model"] == "qwen-plus"
    assert request["temperature"] == 0.2

    messages = request["messages"]

    assert "不得编造" in messages[0]["content"]
    assert "Agent 项目经验怎么写" in messages[1]["content"]
    assert "[资料1]" in messages[1]["content"]
    assert "技术方案和结果" in messages[1]["content"]
    assert "[资料1]" in answer


def test_answer_with_context_rejects_empty_question() -> None:
    fake_client = FakeOpenAI("不会被使用")
    llm_client = LLMClient(
        make_settings(),
        client=fake_client,
    )

    with pytest.raises(ValueError, match="问题不能为空"):
        llm_client.answer_with_context(
            "   ",
            make_context(),
        )

    assert fake_client.chat.completions.last_request is None


def test_answer_with_context_rejects_empty_answer() -> None:
    fake_client = FakeOpenAI("   ")
    llm_client = LLMClient(
        make_settings(),
        client=fake_client,
    )

    with pytest.raises(RuntimeError, match="空回答"):
        llm_client.answer_with_context(
            "Agent 项目经验怎么写？",
            make_context(),
        )
