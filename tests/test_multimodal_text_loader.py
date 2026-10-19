from pathlib import Path

import pytest

from career_pilot.multimodal.text_loader import (
    load_text_document,
)


def test_load_text_document_preserves_metadata(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.txt"
    document_path.write_text(
        "姓名：示例候选人\n技能：Python、RAG",
        encoding="utf-8-sig",
    )

    document = load_text_document(document_path)

    assert document.filename == "resume.txt"
    assert document.source_path == str(
        document_path.resolve()
    )
    assert document.source_type == "text"
    assert document.content == "姓名：示例候选人\n技能：Python、RAG"
    assert len(document.pages) == 1
    assert document.pages[0].page_number == 1
    assert document.pages[0].extraction_method == "native_text"


def test_load_markdown_document(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "job.md"
    document_path.write_text(
        "# Agent 开发工程师\n\n负责 RAG 系统开发。",
        encoding="utf-8",
    )

    document = load_text_document(document_path)

    assert document.source_type == "markdown"
    assert "# Agent 开发工程师" in document.content
    assert "RAG 系统开发" in document.content


def test_text_loader_rejects_pdf(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.pdf"
    document_path.write_bytes(b"fake pdf")

    with pytest.raises(
        ValueError,
        match="只支持 .txt 和 .md",
    ):
        load_text_document(document_path)


def test_text_loader_rejects_invalid_encoding(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "resume.txt"
    document_path.write_bytes(b"\xff\xfe\x00\x00")

    with pytest.raises(
        ValueError,
        match="必须使用 UTF-8 编码",
    ):
        load_text_document(document_path)


def test_text_loader_rejects_whitespace_only_file(
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "empty.txt"
    document_path.write_text(
        "   \n\n   ",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="没有有效内容",
    ):
        load_text_document(document_path)