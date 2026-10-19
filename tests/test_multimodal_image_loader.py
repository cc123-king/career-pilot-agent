from pathlib import Path

import pytest
from PIL import Image

from career_pilot.multimodal.image_loader import (
    load_image_document,
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


class FailingOCRExtractor:
    def extract_text(
        self,
        image_path: Path,
    ) -> str:
        raise RuntimeError(
            f"OCR backend failed: {image_path}"
        )


def _create_test_image(path: Path) -> None:
    image = Image.new(
        "RGB",
        (200, 100),
        color="white",
    )
    image.save(path)


def test_image_loader_returns_ocr_text(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "resume.png"
    _create_test_image(image_path)

    fake_ocr = FakeOCRExtractor(
        "姓名：示例候选人\n技能：Python、RAG"
    )

    document = load_image_document(
        image_path,
        ocr_extractor=fake_ocr,
    )

    assert document.filename == "resume.png"
    assert document.source_path == str(
        image_path.resolve()
    )
    assert document.source_type == "image"
    assert document.content == (
        "姓名：示例候选人\n技能：Python、RAG"
    )
    assert document.pages[0].page_number == 1
    assert document.pages[0].extraction_method == "ocr"
    assert fake_ocr.calls == [image_path]


def test_image_loader_rejects_non_image_type(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.txt"
    document_path.write_text(
        "普通文本",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="只支持 .png、.jpg 和 .jpeg",
    ):
        load_image_document(document_path)


def test_image_loader_rejects_corrupt_image(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "broken.png"
    image_path.write_bytes(b"not a real image")

    with pytest.raises(
        ValueError,
        match="损坏或格式无效",
    ):
        load_image_document(
            image_path,
            ocr_extractor=FakeOCRExtractor("文字"),
        )


def test_image_loader_rejects_empty_ocr_result(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "blank.png"
    _create_test_image(image_path)

    with pytest.raises(
        ValueError,
        match="没有识别到有效文字",
    ):
        load_image_document(
            image_path,
            ocr_extractor=FakeOCRExtractor("   "),
        )


def test_image_loader_wraps_ocr_backend_error(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "resume.jpg"
    _create_test_image(image_path)

    with pytest.raises(
        RuntimeError,
        match="OCR 识别失败",
    ):
        load_image_document(
            image_path,
            ocr_extractor=FailingOCRExtractor(),
        )