from pathlib import Path
from typing import Protocol

from rapidocr import RapidOCR


class OCRTextExtractor(Protocol):
    """Interface implemented by OCR text extractors."""

    def extract_text(
        self,
        image_path: Path,
    ) -> str:
        """Extract text from one image."""


class RapidOCRTextExtractor:
    """OCR adapter backed by RapidOCR and ONNX Runtime."""

    def __init__(self) -> None:
        self._engine = RapidOCR()

    def extract_text(
        self,
        image_path: Path,
    ) -> str:
        result = self._engine(str(image_path))

        if result is None or result.txts is None:
            return ""

        texts = [
            text.strip()
            for text in result.txts
            if text and text.strip()
        ]

        return "\n".join(texts)