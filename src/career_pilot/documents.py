from pathlib import Path

SUPPORTED_SUFFIXES = {".txt", ".md"}
MAX_DOCUMENT_BYTES = 1_000_000


def read_text_document(path: str | Path) -> str:
    """Read a small UTF-8 text or Markdown document."""
    document_path = Path(path)

    if not document_path.exists():
        raise FileNotFoundError(f"文件不存在：{document_path}")

    if not document_path.is_file():
        raise ValueError(f"路径不是文件：{document_path}")

    suffix = document_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"不支持的文件类型：{suffix}，目前只支持 .txt 和 .md")

    if document_path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError("文件过大，不能超过 1 MB")

    content = document_path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError("文件内容为空")

    return content
