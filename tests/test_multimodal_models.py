import pytest
from pydantic import ValidationError

from career_pilot.multimodal.models import (
    ExtractedDocument,
    ExtractedPage,
)


def test_extracted_document_combines_page_content() -> None:
    document = ExtractedDocument(
        filename="resume.pdf",
        source_path="uploads/resume.pdf",
        source_type="pdf",
        pages=[
            ExtractedPage(
                page_number=1,
                text="第一页：个人信息",
                extraction_method="native_text",
            ),
            ExtractedPage(
                page_number=2,
                text="第二页：项目经历",
                extraction_method="ocr",
            ),
        ],
    )

    assert document.content == "第一页：个人信息\n\n第二页：项目经历"
    assert document.pages[1].extraction_method == "ocr"


def test_extracted_document_rejects_disordered_pages() -> None:
    with pytest.raises(
        ValidationError,
        match="页码必须严格递增且不能重复",
    ):
        ExtractedDocument(
            filename="resume.pdf",
            source_path="uploads/resume.pdf",
            source_type="pdf",
            pages=[
                ExtractedPage(
                    page_number=2,
                    text="第二页",
                    extraction_method="native_text",
                ),
                ExtractedPage(
                    page_number=1,
                    text="第一页",
                    extraction_method="native_text",
                ),
            ],
        )

def test_extracted_document_allows_page_gaps() -> None:
    document = ExtractedDocument(
        filename="resume.pdf",
        source_path="uploads/resume.pdf",
        source_type="pdf",
        pages=[
            ExtractedPage(
                page_number=1,
                text="第一页",
                extraction_method="native_text",
            ),
            ExtractedPage(
                page_number=3,
                text="第三页",
                extraction_method="native_text",
            ),
        ],
    )

    assert [
        page.page_number for page in document.pages
    ] == [1, 3]