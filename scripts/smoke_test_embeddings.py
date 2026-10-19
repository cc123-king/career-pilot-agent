import sys

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from career_pilot.rag.embeddings import (
    EmbeddingClient,
    load_embedding_settings,
)


def configure_console_encoding() -> None:
    """Allow Windows terminals to print Chinese safely."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)

        if reconfigure is not None:
            reconfigure(
                encoding="utf-8",
                errors="replace",
            )


def main() -> None:
    """Call the real embedding service with two short texts."""

    configure_console_encoding()

    try:
        settings = load_embedding_settings()
    except ValueError as error:
        print(f"配置错误：{error}")
        return

    embedding_client = EmbeddingClient(settings)

    texts = [
        "熟悉 Python 和 Agent 项目开发。",
        "具备 Python 智能体项目开发经验。",
    ]

    print("正在调用阿里云百炼 Embedding 服务……")
    print(f"模型：{settings.model}")
    print(f"文本数量：{len(texts)}")

    try:
        vectors = embedding_client.embed_texts(texts)
    except AuthenticationError:
        print("调用失败：API Key 无效或没有模型访问权限。")
        return
    except RateLimitError:
        print("调用失败：请求受到限流或账户配额不足。")
        return
    except APIConnectionError:
        print("调用失败：无法连接模型服务，请检查网络。")
        return
    except APIStatusError as error:
        print(f"调用失败：模型服务返回状态码 {error.status_code}。")
        return

    print("\n调用成功。")
    print(f"返回向量数量：{len(vectors)}")
    print(f"向量维度：{len(vectors[0])}")

    for index, vector in enumerate(vectors, start=1):
        preview = ", ".join(f"{value:.4f}" for value in vector[:5])
        print(f"文本{index}向量前5个数值：[{preview}]")


if __name__ == "__main__":
    main()
