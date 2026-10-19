from pathlib import Path

from career_pilot.multimodal.image_loader import (
    load_image_document,
)
from career_pilot.multimodal.models import ExtractedDocument
from career_pilot.multimodal.ocr import OCRTextExtractor
from career_pilot.multimodal.pdf_loader import (
    load_pdf_document,
)
from career_pilot.multimodal.routing import route_document
from career_pilot.multimodal.text_loader import (
    load_text_document,
)
from career_pilot.multimodal.word_loader import (
    load_word_document,
)


def load_document(
    path: str | Path,
    *,
    ocr_extractor: OCRTextExtractor | None = None,
) -> ExtractedDocument:
    """Select the correct loader for a supported document."""

    document_path, source_type = route_document(path)

    if source_type in {"text", "markdown"}:
        return load_text_document(document_path)

    if source_type == "docx":
        return load_word_document(document_path)

    if source_type == "pdf":
        return load_pdf_document(
            document_path,
            ocr_extractor=ocr_extractor,
        )

    if source_type == "image":
        return load_image_document(
            document_path,
            ocr_extractor=ocr_extractor,
        )

    raise RuntimeError(
        f"没有适用于 {source_type} 的文件加载器"
    )