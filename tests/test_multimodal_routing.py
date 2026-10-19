from pathlib import Path

import pytest

from career_pilot.multimodal.routing import (
    MAX_DOCUMENT_BYTES,
    route_document,
)


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        ("resume.txt", "text"),
        ("notes.md", "markdown"),
        ("resume.docx", "docx"),
        ("resume.pdf", "pdf"),
        ("resume.png", "image"),
        ("resume.JPG", "image"),
    ],
)
def test_route_document_recognizes_supported_types(
    tmp_path: Path,
    filename: str,
    expected_type: str,
) -> None:
    document_path = tmp_path / filename
    document_path.write_bytes(b"test content")

    validated_path, source_type = route_document(document_path)

    assert validated_path == document_path
    assert source_type == expected_type


def test_route_document_rejects_missing_file(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "missing.pdf"

    with pytest.raises(FileNotFoundError, match="文件不存在"):
        route_document(document_path)


def test_route_document_rejects_unsupported_type(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "program.exe"
    document_path.write_bytes(b"fake program")

    with pytest.raises(ValueError, match="不支持的文件类型"):
        route_document(document_path)


def test_route_document_rejects_empty_file(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "empty.pdf"
    document_path.write_bytes(b"")

    with pytest.raises(ValueError, match="文件内容为空"):
        route_document(document_path)


def test_route_document_rejects_large_file(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "large.pdf"

    with document_path.open("wb") as file:
        file.truncate(MAX_DOCUMENT_BYTES + 1)

    with pytest.raises(ValueError, match="不能超过 20 MB"):
        route_document(document_path)