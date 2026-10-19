import gradio as gr
import pytest

from career_pilot.api import KnowledgeUploadResult
from career_pilot.rag.models import ContextSource, RAGAnswer
from career_pilot.ui import (
    answer_question,
    clear_form,
    format_sources,
    upload_knowledge_file,
)


class FakeRAGService:
    """A fake RAG service used by UI tests."""

    def __init__(self, result: RAGAnswer) -> None:
        self._result = result
        self.last_question: str | None = None

    def answer(self, question: str) -> RAGAnswer:
        self.last_question = question
        return self._result


def build_answer(
    *,
    include_source: bool = True,
) -> RAGAnswer:
    """Create a reusable answer for UI tests."""

    sources = []

    if include_source:
        sources.append(
            ContextSource(
                citation_id=1,
                chunk_id="interview-0",
                title="Agent岗位面试指南",
                source="interview_guidance.md",
                score=0.8,
            )
        )

    return RAGAnswer(
        question="怎样介绍Agent项目？",
        answer="介绍业务问题、系统架构和测试结果。[资料1]",
        sources=sources,
        retrieved_count=len(sources),
        used_model=True,
    )


def test_format_sources_displays_source_information() -> None:
    formatted = format_sources(build_answer())

    assert "[资料1]" in formatted
    assert "Agent岗位面试指南" in formatted
    assert "interview_guidance.md" in formatted
    assert "0.800" in formatted

def test_format_sources_displays_multimodal_metadata() -> None:
    result = RAGAnswer(
        question="有哪些 Agent 项目？",
        answer="候选人实现了 CareerPilot Agent。[资料1]",
        sources=[
            ContextSource(
                citation_id=1,
                chunk_id="resume-p3-0",
                title="示例候选人简历",
                source="示例候选人简历.pdf",
                score=0.85,
                page_number=3,
                source_type="pdf",
                extraction_method="ocr",
            )
        ],
        retrieved_count=1,
        used_model=True,
    )

    formatted = format_sources(result)

    assert "[资料1]" in formatted
    assert "示例候选人简历.pdf" in formatted
    assert "第 3 页" in formatted
    assert "PDF" in formatted
    assert "OCR" in formatted
    assert "0.850" in formatted

def test_format_sources_handles_empty_sources() -> None:
    formatted = format_sources(build_answer(include_source=False))

    assert formatted == "本次回答没有引用知识库资料。"


def test_answer_question_uses_rag_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeRAGService(build_answer())

    monkeypatch.setattr(
        "career_pilot.ui.get_rag_service",
        lambda: fake_service,
    )

    answer, sources, status = answer_question("  怎样介绍Agent项目？  ")

    assert "[资料1]" in answer
    assert "Agent岗位面试指南" in sources
    assert status == "检索结果：1 条 | 已调用大模型"
    assert fake_service.last_question == "怎样介绍Agent项目？"


def test_answer_question_rejects_blank_question() -> None:
    with pytest.raises(gr.Error) as error_info:
        answer_question("   ")

    assert error_info.value.message == "请输入问题后再提交。"


def test_clear_form_returns_empty_values() -> None:
    assert clear_form() == ("", "", "", "")

def test_upload_knowledge_file_displays_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_paths: list[str] = []

    def fake_ingest(
        file_path: str,
    ) -> KnowledgeUploadResult:
        received_paths.append(file_path)

        return KnowledgeUploadResult(
            filename="resume.pdf",
            source_type="pdf",
            page_count=2,
            chunk_count=5,
            total_document_count=1,
            total_chunk_count=5,
        )

    monkeypatch.setattr(
        "career_pilot.ui.ingest_knowledge_file",
        fake_ingest,
    )

    message = upload_knowledge_file(
        "C:/temp/resume.pdf"
    )

    assert received_paths == [
        "C:/temp/resume.pdf"
    ]
    assert "resume.pdf" in message
    assert "PDF" in message
    assert "页数：2" in message
    assert "新增分块：5" in message


def test_upload_knowledge_file_requires_selection() -> None:
    with pytest.raises(gr.Error) as error_info:
        upload_knowledge_file(None)

    assert error_info.value.message == (
        "请先选择需要上传的文件。"
    )