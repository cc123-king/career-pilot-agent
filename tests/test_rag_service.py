import logging

import pytest

from career_pilot.rag.models import (
    KnowledgeChunk,
    RetrievalContext,
    SearchHit,
)
from career_pilot.rag.service import RAGService


class FakeAnswerer:
    def __init__(self) -> None:
        self.calls = 0
        self.last_context: RetrievalContext | None = None

    def answer_with_context(
        self,
        question: str,
        context: RetrievalContext,
    ) -> str:
        self.calls += 1
        self.last_context = context
        return "应介绍系统架构、关键难点和测试结果。[资料1]"


class FakeRetriever:
    """Return controlled retrieval results for service tests."""

    def __init__(
        self,
        hits: list[SearchHit],
    ) -> None:
        self._hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
    ) -> list[SearchHit]:
        self.calls.append((query, top_k))
        return self._hits[:top_k]


def make_chunk(content: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="interview-0",
        document_id="interview",
        title="Agent岗位面试指南",
        source="interview_guidance.md",
        content=content,
        position=0,
    )


def test_rag_service_calls_model_when_knowledge_is_found() -> None:
    fake_answerer = FakeAnswerer()
    service = RAGService(
        chunks=[make_chunk("Agent项目面试需要介绍系统架构、关键难点和测试结果。")],
        llm_client=fake_answerer,
        top_k=1,
    )

    result = service.answer("Agent项目面试应该怎么介绍？")

    assert result.used_model is True
    assert result.retrieved_count == 1
    assert result.sources[0].source == "interview_guidance.md"
    assert "[资料1]" in result.answer
    assert fake_answerer.calls == 1
    assert fake_answerer.last_context is not None
    assert "[资料1]" in fake_answerer.last_context.content


def test_rag_service_skips_model_when_no_knowledge_is_found() -> None:
    fake_answerer = FakeAnswerer()
    service = RAGService(
        chunks=[make_chunk("Agent项目面试需要介绍系统架构和测试结果。")],
        llm_client=fake_answerer,
    )

    result = service.answer("量子芯片制造工艺是什么？")

    assert result.used_model is False
    assert result.retrieved_count == 0
    assert result.sources == []
    assert "没有足够相关的资料" in result.answer
    assert fake_answerer.calls == 0


def test_rag_service_filters_hits_below_minimum_score() -> None:
    fake_answerer = FakeAnswerer()
    service = RAGService(
        chunks=[make_chunk("Python 是一种编程语言。")],
        llm_client=fake_answerer,
        min_score=0.5,
    )

    result = service.answer("Python FastAPI Docker Kubernetes Redis")

    assert result.used_model is False
    assert result.retrieved_count == 0
    assert result.sources == []
    assert fake_answerer.calls == 0


def test_rag_service_rejects_empty_question() -> None:
    fake_answerer = FakeAnswerer()
    service = RAGService(
        chunks=[make_chunk("Agent项目面试指南。")],
        llm_client=fake_answerer,
    )

    with pytest.raises(ValueError, match="问题不能为空"):
        service.answer("   ")

    assert fake_answerer.calls == 0


def test_rag_service_validates_configuration() -> None:
    fake_answerer = FakeAnswerer()
    chunk = make_chunk("Agent项目面试指南。")

    with pytest.raises(ValueError, match="知识分块不能为空"):
        RAGService(
            chunks=[],
            llm_client=fake_answerer,
        )

    with pytest.raises(ValueError, match="top_k"):
        RAGService(
            chunks=[chunk],
            llm_client=fake_answerer,
            top_k=0,
        )

    with pytest.raises(ValueError, match="min_score"):
        RAGService(
            chunks=[chunk],
            llm_client=fake_answerer,
            min_score=-0.1,
        )

    with pytest.raises(ValueError, match="min_score"):
        RAGService(
            chunks=[chunk],
            llm_client=fake_answerer,
            min_score=1.1,
        )


def test_rag_service_writes_safe_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.INFO,
        logger="career_pilot.rag.service",
    )

    service = RAGService(
        chunks=[make_chunk("Agent项目面试需要介绍系统架构和测试结果。")],
        llm_client=FakeAnswerer(),
    )

    service.answer("Agent项目面试应该怎么介绍？")

    assert "rag_request_started" in caplog.text
    assert "rag_retrieval_finished" in caplog.text
    assert "rag_request_finished" in caplog.text
    assert "used_model=true" in caplog.text

    # 日志只记录长度和数量，不记录用户的完整问题。
    assert "Agent项目面试应该怎么介绍" not in caplog.text


def test_rag_service_uses_injected_retriever() -> None:
    chunk = make_chunk("这段资料由注入的检索器直接返回。")
    fake_retriever = FakeRetriever(
        [
            SearchHit(
                chunk=chunk,
                score=0.9,
                matched_terms=[],
            )
        ]
    )
    fake_answerer = FakeAnswerer()

    service = RAGService(
        chunks=[chunk],
        llm_client=fake_answerer,
        retriever=fake_retriever,
        top_k=2,
        min_score=0.5,
    )

    result = service.answer("  一个与文档字面内容不同的问题  ")

    assert result.used_model is True
    assert result.retrieved_count == 1
    assert fake_answerer.calls == 1
    assert fake_retriever.calls == [("一个与文档字面内容不同的问题", 2)]


def test_rag_service_filters_injected_low_score_hit() -> None:
    chunk = make_chunk("由假的混合检索器返回的低分资料。")
    fake_retriever = FakeRetriever(
        [
            SearchHit(
                chunk=chunk,
                score=0.2,
                matched_terms=[],
            )
        ]
    )
    fake_answerer = FakeAnswerer()

    service = RAGService(
        chunks=[chunk],
        llm_client=fake_answerer,
        retriever=fake_retriever,
        min_score=0.5,
    )

    result = service.answer("测试低分结果")

    assert result.used_model is False
    assert result.retrieved_count == 0
    assert result.sources == []
    assert fake_answerer.calls == 0
    assert fake_retriever.calls == [("测试低分结果", 3)]


def test_service_search_reuses_retriever_without_calling_answer_model() -> None:
    chunk = make_chunk("求职项目介绍资料。")
    hit = SearchHit(chunk=chunk, score=0.9)
    retriever = FakeRetriever([hit])
    answerer = FakeAnswerer()
    service = RAGService(chunks=[chunk], llm_client=answerer, retriever=retriever)

    assert service.search("  求职项目介绍  ", top_k=2) == [hit]
    assert retriever.calls == [("求职项目介绍", 2)]
    assert answerer.calls == 0


def test_service_search_can_use_keyword_retrieval_without_calling_model() -> None:
    chunk = make_chunk("Python 项目介绍资料。")
    answerer = FakeAnswerer()
    service = RAGService(chunks=[chunk], llm_client=answerer)

    hits = service.search("Python", top_k=1)

    assert hits[0].chunk == chunk
    assert answerer.calls == 0
