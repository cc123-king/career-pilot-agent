from pathlib import Path

import pytest

from career_pilot.documents import read_text_document


def test_read_text_document_returns_utf8_content(tmp_path: Path) -> None:
    document_path = tmp_path / "resume.txt"
    document_path.write_text(
        "示例候选人\nPython、FastAPI、RAG",
        encoding="utf-8",
    )

    result = read_text_document(document_path)

    assert result == "示例候选人\nPython、FastAPI、RAG"


def test_read_markdown_document(tmp_path: Path) -> None:
    document_path = tmp_path / "job.md"
    document_path.write_text(
        "# 岗位职责\n负责 AI Agent 开发",
        encoding="utf-8",
    )

    result = read_text_document(document_path)

    assert "AI Agent" in result


def test_read_document_rejects_unsupported_suffix(tmp_path: Path) -> None:
    document_path = tmp_path / "resume.pdf"
    document_path.write_bytes(b"fake pdf")

    with pytest.raises(ValueError, match="不支持"):
        read_text_document(document_path)


def test_read_document_rejects_missing_file(tmp_path: Path) -> None:
    document_path = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError):
        read_text_document(document_path)


def test_read_document_rejects_empty_file(tmp_path: Path) -> None:
    document_path = tmp_path / "empty.txt"
    document_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="为空"):
        read_text_document(document_path)
