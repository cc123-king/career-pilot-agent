import sys

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from career_pilot.llm import LLMClient, load_llm_settings
from career_pilot.rag.models import (
    ContextSource,
    RetrievalContext,
)


def configure_console_encoding() -> None:
    """Allow Windows terminals to print arbitrary model output safely."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)

        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def build_test_context() -> RetrievalContext:
    """Create fixed RAG context for the real API smoke test."""

    return RetrievalContext(
        query="Agent 项目经验应该怎么写？",
        content=(
            "请只根据以下资料回答问题。"
            "如果资料不足，请明确说明，不要编造。\n\n"
            "[资料1]\n"
            "标题：简历项目经验指南\n"
            "来源：smoke-test\n"
            "分块：resume-guide-0\n"
            "相关度：1.000\n"
            "内容：项目经验应说明业务问题、个人职责、"
            "技术方案和可验证结果。不要只罗列技术名词。"
        ),
        sources=[
            ContextSource(
                citation_id=1,
                chunk_id="resume-guide-0",
                title="简历项目经验指南",
                source="smoke-test",
                score=1.0,
            )
        ],
    )


def main() -> None:
    configure_console_encoding()

    settings = load_llm_settings()
    llm_client = LLMClient(settings)
    context = build_test_context()

    print("正在调用阿里云百炼……")
    print(f"服务商：{settings.provider}")
    print(f"模型：{settings.model}")

    try:
        answer = llm_client.answer_with_context(
            question=context.query,
            context=context,
        )
    except AuthenticationError:
        print("调用失败：API Key 无效或没有模型访问权限。")
        return
    except RateLimitError:
        print("调用失败：请求受到限流，请稍后再试。")
        return
    except APIConnectionError:
        print("调用失败：无法连接模型服务，请检查网络和接口地址。")
        return
    except APIStatusError as error:
        print(f"调用失败：模型服务返回状态码 {error.status_code}。")
        return

    print("\n模型回答：")
    print(answer)
    print("\n使用的资料来源：")

    for source in context.sources:
        print(f"[资料{source.citation_id}] {source.title} - {source.source}")


if __name__ == "__main__":
    main()
