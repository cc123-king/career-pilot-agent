from pathlib import Path

from PIL import Image, UnidentifiedImageError

from career_pilot.multimodal.models import (
    ExtractedDocument,
    ExtractedPage,
)
from career_pilot.multimodal.ocr import (
    OCRTextExtractor,
    RapidOCRTextExtractor,
)
from career_pilot.multimodal.routing import route_document


def load_image_document(
    path: str | Path,
    *,
    ocr_extractor: OCRTextExtractor | None = None,
) -> ExtractedDocument:
    """Validate an image and extract its text with OCR."""

    document_path, source_type = route_document(path)

    if source_type != "image":
        raise ValueError(
            "图片加载器只支持 .png、.jpg 和 .jpeg 文件"
        )

    try:
        with Image.open(document_path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(
            "图片文件损坏或格式无效"
        ) from exc

    extractor = (
        ocr_extractor
        if ocr_extractor is not None
        else RapidOCRTextExtractor()
    )

    try:
        extracted_text = extractor.extract_text(
            document_path
        ).strip()
    except Exception as exc:
        raise RuntimeError(
            "OCR 识别失败"
        ) from exc

    if not extracted_text:
        raise ValueError(
            "图片中没有识别到有效文字"
        )

    return ExtractedDocument(
        filename=document_path.name,
        source_path=str(document_path.resolve()),
        source_type="image",
        pages=[
            ExtractedPage(
                page_number=1,
                text=extracted_text,
                extraction_method="ocr",
            )
        ],
    )