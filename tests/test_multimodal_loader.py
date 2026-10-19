from pathlib import Path

import pymupdf
from docx import Document
from PIL import Image

from career_pilot.multimodal.loader import load_document


class FakeOCRExtractor:
    def extract_text(
        self,
        image_path: Path,
    ) -> str:
        return "OCR 识别结果：Python、RAG、Agent"


def test_load_document_routes_text_file(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.txt"
    document_path.write_text(
        "姓名：示例候选人\n技能：Python",
        encoding="utf-8",
    )

    document = load_document(document_path)

    assert document.source_type == "text"
    assert "Python" in document.content


def test_load_document_routes_word_file(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.docx"

    word_document = Document()
    word_document.add_paragraph(
        "项目经历：CareerPilot Agent"
    )
    word_document.save(document_path)

    document = load_document(document_path)

    assert document.source_type == "docx"
    assert "CareerPilot Agent" in document.content


def test_load_document_routes_pdf_file(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.pdf"

    with pymupdf.open() as pdf_document:
        page = pdf_document.new_page()
        page.insert_text(
            (72, 72),
            "Python RAG Agent",
        )
        pdf_document.save(document_path)

    document = load_document(document_path)

    assert document.source_type == "pdf"
    assert "Python RAG Agent" in document.content
    assert document.pages[0].page_number == 1


def test_load_document_forwards_ocr_to_image(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.png"

    image = Image.new(
        "RGB",
        (200, 100),
        color="white",
    )
    image.save(document_path)

    document = load_document(
        document_path,
        ocr_extractor=FakeOCRExtractor(),
    )

    assert document.source_type == "image"
    assert document.pages[0].extraction_method == "ocr"
    assert "Python、RAG、Agent" in document.content