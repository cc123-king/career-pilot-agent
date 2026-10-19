import pytest

from career_pilot.rag.context import build_retrieval_context
from career_pilot.rag.models import KnowledgeChunk, SearchHit


def make_hit(
    chunk_id: str,
    content: str,
    score: float,
    position: int,
) -> SearchHit:
    chunk = KnowledgeChunk(
        chunk_id=chunk_id,
        document_id="resume",
        title="简历指南",
        source="resume_guidance.md",
        content=content,
        position=position,
    )

    return SearchHit(
        chunk=chunk,
        score=score,
        matched_terms=["项目"],
    )


def test_build_retrieval_context_includes_sources() -> None:
    hits = [
        make_hit(
            "resume-0",
            "项目介绍需要说明业务背景和技术方案。",
            0.8,
            0,
        ),
        make_hit(
            "resume-1",
            "项目内容必须能够通过代码和测试验证。",
            0.6,
            1,
        ),
    ]

    context = build_retrieval_context(
        "项目经验应该怎么写？",
        hits,
    )

    assert "[资料1]" in context.content
    assert "[资料2]" in context.content
    assert "resume_guidance.md" in context.content
    assert "不要编造" in context.content
    assert len(context.sources) == 2
    assert context.sources[0].chunk_id == "resume-0"
    assert context.sources[0].citation_id == 1


def test_build_retrieval_context_handles_empty_results() -> None:
    context = build_retrieval_context(
        "知识库中不存在的问题",
        [],
    )

    assert "信息不足" in context.content
    assert context.sources == []


def test_build_retrieval_context_respects_character_limit() -> None:
    hits = [
        make_hit(
            "resume-0",
            "第一条项目资料。" * 10,
            0.8,
            0,
        ),
        make_hit(
            "resume-1",
            "第二条项目资料。" * 10,
            0.7,
            1,
        ),
    ]

    context = build_retrieval_context(
        "项目怎么写？",
        hits,
        max_characters=250,
    )

    assert len(context.sources) == 1
    assert "[资料1]" in context.content
    assert "[资料2]" not in context.content


def test_build_retrieval_context_validates_input() -> None:
    with pytest.raises(ValueError, match="查询不能为空"):
        build_retrieval_context("   ", [])

    with pytest.raises(ValueError, match="最大长度"):
        build_retrieval_context(
            "Python",
            [],
            max_characters=100,
        )


def test_build_context_preserves_multimodal_metadata() -> None:
    chunk = KnowledgeChunk(
        chunk_id="resume-p3-0",
        document_id="resume",
        title="示例候选人简历",
        source="示例候选人简历.pdf",
        content="使用 Python、RAG 和 Agent 工具调用。",
        position=0,
        page_number=3,
        extraction_method="ocr",
        source_type="pdf",
    )
    hit = SearchHit(
        chunk=chunk,
        score=0.85,
        matched_terms=["Agent"],
    )

    context = build_retrieval_context(
        "有哪些 Agent 项目经验？",
        [hit],
    )

    assert "页码：3" in context.content
    assert "文件类型：pdf" in context.content
    assert "提取方式：OCR" in context.content

    source = context.sources[0]
    assert source.page_number == 3
    assert source.source_type == "pdf"
    assert source.extraction_method == "ocr"


def test_context_skips_oversized_first_hit_and_stays_within_full_budget():
    hits = [
        make_hit("large-0", "过长资料。" * 1000, 0.99, 0),
        make_hit("small-0", "这是可以完整放入上下文的有效资料。", 0.8, 1),
    ]
    context = build_retrieval_context("有效资料是什么？", hits, max_characters=300)
    assert len(context.content) <= 300
    assert [s.chunk_id for s in context.sources] == ["small-0"]
    assert context.sources[0].citation_id == 1


def test_context_deduplicates_identical_chunks_and_rejects_conflicting_ids():
    h = make_hit("same-0", "这个原文片段包含可以核对的内容。", 0.9, 0)
    context = build_retrieval_context("原文是什么？", [h, h])
    assert len(context.sources) == 1
    other = h.model_copy(
        update={
            "chunk": h.chunk.model_copy(
                update={"content": "同一分块标识却对应了另一个原文内容。"}
            )
        }
    )
    with pytest.raises(ValueError, match="重复分块标识"):
        build_retrieval_context("原文是什么？", [h, other])
