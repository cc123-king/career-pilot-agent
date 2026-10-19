import pytest

from career_pilot.rag.models import KnowledgeChunk
from career_pilot.rag.retrieval import KeywordRetriever, search_chunks


def make_chunk(
    chunk_id: str,
    content: str,
    position: int,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id="resume",
        title="简历指南",
        source="resume_guidance.md",
        content=content,
        position=position,
    )


def test_search_chunks_returns_relevant_results() -> None:
    chunks = [
        make_chunk(
            "resume-0",
            "项目介绍需要包含业务背景、技术方案和本人职责。",
            0,
        ),
        make_chunk(
            "resume-1",
            "简历内容必须真实，不能编造用户数量和性能指标。",
            1,
        ),
        make_chunk(
            "resume-2",
            "面试时需要说明 Agent 的工具调用和异常处理。",
            2,
        ),
    ]

    results = search_chunks(
        "项目 技术方案",
        chunks,
        top_k=2,
    )

    assert len(results) == 1
    assert results[0].chunk.chunk_id == "resume-0"
    assert results[0].score > 0
    assert results[0].chunk.source == "resume_guidance.md"
    assert results[0].matched_terms


def test_search_chunks_returns_empty_when_no_term_matches() -> None:
    chunks = [
        make_chunk(
            "resume-0",
            "项目介绍需要包含业务背景和技术方案。",
            0,
        )
    ]

    results = search_chunks("MySQL 数据库", chunks)

    assert results == []


def test_search_chunks_validates_query_and_top_k() -> None:
    with pytest.raises(ValueError, match="查询不能为空"):
        search_chunks("   ", [])

    with pytest.raises(ValueError, match="top_k"):
        search_chunks("Python", [], top_k=0)


def test_keyword_retriever_reuses_search_with_a_stable_chunk_list() -> None:
    chunks = [make_chunk("resume-0", "Python Agent 项目测试", 0)]
    expected = search_chunks("Python", chunks, top_k=1)
    retriever = KeywordRetriever(chunks)
    chunks.clear()

    assert retriever.search("Python", top_k=1) == expected


def test_keyword_retriever_accepts_an_empty_knowledge_base() -> None:
    assert KeywordRetriever([]).search("Python") == []
