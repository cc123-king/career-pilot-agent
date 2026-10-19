from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf

from career_pilot.multimodal.models import (
    ExtractedDocument,
    ExtractedPage,
)
from career_pilot.multimodal.ocr import (
    OCRTextExtractor,
    RapidOCRTextExtractor,
)
from career_pilot.multimodal.routing import route_document


def load_pdf_document(
    path: str | Path,
    *,
    ocr_extractor: OCRTextExtractor | None = None,
) -> ExtractedDocument:
    """Extract native text and use OCR for scanned PDF pages."""

    document_path, source_type = route_document(path)

    if source_type != "pdf":
        raise ValueError("PDF 加载器只支持 .pdf 文件")

    try:
        pdf_document = pymupdf.open(document_path)
    except (pymupdf.FileDataError, RuntimeError) as exc:
        raise ValueError(
            "PDF 文件损坏或格式无效"
        ) from exc

    extracted_pages: list[ExtractedPage] = []
    extractor = ocr_extractor

    with pdf_document:
        if pdf_document.needs_pass:
            raise ValueError(
                "PDF 文件已加密，暂不支持读取"
            )

        with TemporaryDirectory(
            prefix="career-pilot-pdf-",
        ) as temporary_directory:
            temporary_path = Path(temporary_directory)

            for page_number, pdf_page in enumerate(
                pdf_document,
                start=1,
            ):
                page_text = pdf_page.get_text(
                    "text",
                    sort=True,
                ).strip()
                extraction_method = "native_text"

                if not page_text:
                    if extractor is None:
                        extractor = RapidOCRTextExtractor()

                    image_path = (
                        temporary_path
                        / f"page-{page_number}.png"
                    )

                    try:
                        pixmap = pdf_page.get_pixmap(
                            matrix=pymupdf.Matrix(2, 2),
                            alpha=False,
                        )
                        pixmap.save(str(image_path))
                        page_text = extractor.extract_text(
                            image_path
                        ).strip()
                    except Exception as exc:
                        raise RuntimeError(
                            f"PDF 第 {page_number} 页 "
                            "OCR 识别失败"
                        ) from exc

                    extraction_method = "ocr"

                if not page_text:
                    continue

                extracted_pages.append(
                    ExtractedPage(
                        page_number=page_number,
                        text=page_text,
                        extraction_method=extraction_method,
                    )
                )

    if not extracted_pages:
        raise ValueError(
            "PDF 文件没有可提取的文本，"
            "可能是空白或扫描内容无法识别"
        )

    return ExtractedDocument(
        filename=document_path.name,
        source_path=str(document_path.resolve()),
        source_type="pdf",
        pages=extracted_pages,
    )