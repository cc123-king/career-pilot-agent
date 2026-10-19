from pathlib import Path

from career_pilot.api import (
    UPLOADED_KNOWLEDGE_STORE,
    get_rag_service,
    ingest_knowledge_file,
)


def test_ingest_knowledge_file_registers_document(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "agent-notes.md"
    document_path.write_text(
        "# Agent 项目\n\n"
        "CareerPilot 使用混合检索和工具调用。",
        encoding="utf-8",
    )

    UPLOADED_KNOWLEDGE_STORE.clear()
    get_rag_service.cache_clear()

    try:
        result = ingest_knowledge_file(
            document_path
        )

        assert result.filename == "agent-notes.md"
        assert result.source_type == "markdown"
        assert result.page_count == 1
        assert result.chunk_count >= 1
        assert result.total_document_count == 1
        assert result.total_chunk_count >= 1

        stored_chunks = (
            UPLOADED_KNOWLEDGE_STORE.list_chunks()
        )

        assert len(stored_chunks) == (
            result.total_chunk_count
        )
        assert stored_chunks[0].source == (
            "agent-notes.md"
        )
        assert "混合检索" in stored_chunks[0].content
    finally:
        UPLOADED_KNOWLEDGE_STORE.clear()
        get_rag_service.cache_clear()