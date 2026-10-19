from career_pilot.multimodal.models import (
    ExtractedDocument,
    ExtractedPage,
)
from career_pilot.rag.knowledge_store import (
    InMemoryKnowledgeStore,
)


def make_document(
    filename: str,
    text: str,
) -> ExtractedDocument:
    return ExtractedDocument(
        filename=filename,
        source_path=f"uploads/{filename}",
        source_type="pdf",
        pages=[
            ExtractedPage(
                page_number=1,
                text=text,
                extraction_method="native_text",
            )
        ],
    )


def test_store_adds_extracted_document() -> None:
    store = InMemoryKnowledgeStore()
    document = make_document(
        "resume.pdf",
        "Python、FastAPI、RAG 和 Agent 项目经验。",
    )

    added_chunks = store.add_document(document)
    stored_chunks = store.list_chunks()

    assert len(added_chunks) == 1
    assert len(stored_chunks) == 1
    assert store.document_count == 1
    assert store.chunk_count == 1
    assert stored_chunks[0].source == "resume.pdf"
    assert stored_chunks[0].page_number == 1
    assert stored_chunks[0].source_type == "pdf"


def test_store_replaces_document_with_same_filename() -> None:
    store = InMemoryKnowledgeStore()

    store.add_document(
        make_document(
            "resume.pdf",
            "第一版简历内容：Python。",
        )
    )
    store.add_document(
        make_document(
            "RESUME.PDF",
            "第二版简历内容：Python、RAG。",
        )
    )

    stored_chunks = store.list_chunks()

    assert store.document_count == 1
    assert store.chunk_count == 1
    assert "第二版" in stored_chunks[0].content
    assert "第一版" not in stored_chunks[0].content


def test_store_returns_independent_snapshot() -> None:
    store = InMemoryKnowledgeStore()
    store.add_document(
        make_document(
            "resume.pdf",
            "CareerPilot Agent 项目内容。",
        )
    )

    snapshot = store.list_chunks()
    snapshot.clear()

    assert snapshot == []
    assert store.chunk_count == 1
    assert len(store.list_chunks()) == 1


def test_store_clear_removes_uploaded_documents() -> None:
    store = InMemoryKnowledgeStore()
    store.add_document(
        make_document(
            "resume.pdf",
            "需要被清理的简历内容。",
        )
    )

    store.clear()

    assert store.document_count == 0
    assert store.chunk_count == 0
    assert store.list_chunks() == []