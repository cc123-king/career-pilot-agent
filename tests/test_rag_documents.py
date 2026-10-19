from pathlib import Path

from career_pilot.rag.documents import (
    chunk_document,
    load_knowledge_documents,
)
from career_pilot.rag.models import KnowledgeDocument


def test_load_knowledge_documents_preserves_sources(
    tmp_path: Path,
) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    (knowledge_dir / "resume.md").write_text(
        "# 简历指南\n\n项目描述需要包含真实证据。",
        encoding="utf-8",
    )
    (knowledge_dir / "interview.md").write_text(
        "# 面试指南\n\n介绍项目时需要说明问题和解决方案。",
        encoding="utf-8",
    )

    documents = load_knowledge_documents(knowledge_dir)
    documents_by_id = {document.document_id: document for document in documents}

    assert len(documents) == 2
    assert documents_by_id["resume"].title == "简历指南"
    assert documents_by_id["resume"].source == "resume.md"
    assert "真实证据" in documents_by_id["resume"].content


def test_chunk_document_preserves_traceable_metadata() -> None:
    document = KnowledgeDocument(
        document_id="resume",
        title="简历指南",
        source="resume.md",
        content=(
            "第一部分介绍简历项目证据、个人职责和技术实现。" * 4
            + "\n\n"
            + "第二部分介绍如何保证简历内容真实并且可以验证。" * 4
        ),
    )

    chunks = chunk_document(
        document,
        max_characters=60,
    )

    assert len(chunks) >= 2
    assert all(len(chunk.content) <= 60 for chunk in chunks)
    assert all(chunk.document_id == "resume" for chunk in chunks)
    assert all(chunk.source == "resume.md" for chunk in chunks)
    assert chunks[0].chunk_id == "resume-0"
    assert chunks[0].position == 0


def test_project_knowledge_base_contains_documents() -> None:
    project_root = Path(__file__).resolve().parents[1]
    knowledge_dir = project_root / "knowledge"

    documents = load_knowledge_documents(knowledge_dir)

    assert len(documents) >= 2
