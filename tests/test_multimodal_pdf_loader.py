from pathlib import Path

import pymupdf
import pytest

from career_pilot.multimodal.pdf_loader import (
    load_pdf_document,
)


class FakeOCRExtractor:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[Path] = []

    def extract_text(
        self,
        image_path: Path,
    ) -> str:
        self.calls.append(image_path)
        return self.text

def _create_pdf(
    path: Path,
    page_texts: list[str | None],
) -> None:
    with pymupdf.open() as pdf_document:
        for text in page_texts:
            page = pdf_document.new_page()

            if text:
                page.insert_text(
                    (72, 72),
                    text,
                )

        pdf_document.save(path)


def test_pdf_loader_extracts_text_by_page(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.pdf"
    _create_pdf(
        document_path,
        [
            "Page 1: Python and RAG",
            "Page 2: Agent tool calling",
        ],
    )

    document = load_pdf_document(document_path)

    assert document.filename == "resume.pdf"
    assert document.source_type == "pdf"
    assert document.source_path == str(
        document_path.resolve()
    )
    assert len(document.pages) == 2
    assert document.pages[0].page_number == 1
    assert document.pages[1].page_number == 2
    assert document.pages[0].extraction_method == "native_text"
    assert "Python and RAG" in document.pages[0].text
    assert "Agent tool calling" in document.pages[1].text


def test_pdf_loader_preserves_page_number_after_blank_page(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.pdf"
    _create_pdf(
        document_path,
        [
            None,
            "Page 2 has native text",
        ],
    )

    document = load_pdf_document(
        document_path,
        ocr_extractor=FakeOCRExtractor(""),
    )

    assert len(document.pages) == 1
    assert document.pages[0].page_number == 2
    assert document.pages[0].text == "Page 2 has native text"


def test_pdf_loader_rejects_non_pdf_file(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.txt"
    document_path.write_text(
        "普通文本",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="只支持 .pdf",
    ):
        load_pdf_document(document_path)


def test_pdf_loader_rejects_corrupt_pdf(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "broken.pdf"
    document_path.write_bytes(b"not a real PDF")

    with pytest.raises(
        ValueError,
        match="损坏或格式无效",
    ):
        load_pdf_document(document_path)


def test_pdf_loader_uses_ocr_for_scanned_page(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "scanned.pdf"
    _create_pdf(document_path, [None])
    fake_ocr = FakeOCRExtractor(
        "扫描简历：Python、RAG、Agent"
    )

    document = load_pdf_document(
        document_path,
        ocr_extractor=fake_ocr,
    )

    assert len(document.pages) == 1
    assert document.pages[0].page_number == 1
    assert document.pages[0].extraction_method == "ocr"
    assert "Python、RAG、Agent" in document.content
    assert fake_ocr.calls[0].name == "page-1.png"

def test_pdf_loader_rejects_empty_ocr_result(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "blank.pdf"
    _create_pdf(document_path, [None])

    with pytest.raises(
        ValueError,
        match="没有可提取的文本",
    ):
        load_pdf_document(
            document_path,
            ocr_extractor=FakeOCRExtractor("   "),
        )