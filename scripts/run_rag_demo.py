import logging
import sys
from pathlib import Path

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from career_pilot.api import get_rag_service
from career_pilot.llm import load_llm_settings
from career_pilot.rag.documents import (
    chunk_document,
    load_knowledge_documents,
)
from career_pilot.rag.models import KnowledgeChunk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIRECTORY = PROJECT_ROOT / "knowledge"


def configure_console_encoding() -> None:
    """Allow Windows terminals to print model output safely."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)

        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def configure_logging() -> None:
    """Configure readable application logs."""

    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s %(levelname)s %(name)s %(message)s"),
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_all_chunks() -> tuple[int, list[KnowledgeChunk]]:
    """Load all knowledge documents and split them into chunks."""

    documents = load_knowledge_documents(KNOWLEDGE_DIRECTORY)
    chunks: list[KnowledgeChunk] = []

    for document in documents:
        chunks.extend(chunk_document(document, max_characters=300))

    return len(documents), chunks


def main() -> None:
    configure_console_encoding()
    configure_logging()

    question = input("请输入你的问题：").strip()

    if not question:
        print("问题不能为空。")
        return

    if len(question) > 2000:
        print("问题不能超过 2000 字符。")
        return
    document_count, chunks = load_all_chunks()

    settings = load_llm_settings()
    rag_service = get_rag_service()

    print(f"\n已加载 {document_count} 份知识文档。")
    print(f"共生成 {len(chunks)} 个知识分块。")
    print(f"正在使用模型：{settings.model}")

    try:
        result = rag_service.answer(question)
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

    print(f"\n有效检索结果：{result.retrieved_count} 个")
    print(f"是否调用大模型：{'是' if result.used_model else '否'}")

    print("\n回答：")
    print(result.answer)

    if not result.sources:
        print("\n本次回答没有使用知识库资料。")
        return

    print("\n引用来源：")

    for source in result.sources:
        print(
            f"[资料{source.citation_id}] "
            f"{source.title} | "
            f"{source.source} | "
            f"检索排序分数={source.score:.3f}"
        )


if __name__ == "__main__":
    main()
