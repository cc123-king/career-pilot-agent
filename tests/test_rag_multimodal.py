from career_pilot.multimodal.models import (
    ExtractedDocument,
    ExtractedPage,
)
from career_pilot.rag.multimodal import (
    chunk_extracted_document,
)


def test_chunk_extracted_document_preserves_metadata() -> None:
    document = ExtractedDocument(
        filename="示例候选人简历.pdf",
        source_path="uploads/示例候选人简历.pdf",
        source_type="pdf",
        pages=[
            ExtractedPage(
                page_number=1,
                text="Python、FastAPI 和 RAG 项目经验。" * 8,
                extraction_method="native_text",
            ),
            ExtractedPage(
                page_number=3,
                text="通过 OCR 提取的 Agent 项目经历。" * 8,
                extraction_method="ocr",
            ),
        ],
    )

    chunks = chunk_extracted_document(
        document,
        max_characters=60,
    )

    assert len(chunks) >= 4
    assert {chunk.page_number for chunk in chunks} == {1, 3}
    assert all(chunk.source == "示例候选人简历.pdf" for chunk in chunks)
    assert all(chunk.source_type == "pdf" for chunk in chunks)
    assert all(len(chunk.content) <= 60 for chunk in chunks)
    assert chunks[0].extraction_method == "native_text"
    assert chunks[-1].extraction_method == "ocr"
    assert [chunk.position for chunk in chunks] == list(
        range(len(chunks))
    )
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_document_id_is_stable() -> None:
    document = ExtractedDocument(
        filename="resume.txt",
        source_path="uploads/resume.txt",
        source_type="text",
        pages=[
            ExtractedPage(
                page_number=1,
                text="Python RAG Agent 项目内容",
                extraction_method="native_text",
            )
        ],
    )

    first_chunks = chunk_extracted_document(document)
    second_chunks = chunk_extracted_document(document)

    assert (
        first_chunks[0].document_id
        == second_chunks[0].document_id
    )