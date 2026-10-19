from pathlib import Path

from career_pilot.multimodal.models import SourceType

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024

SUFFIX_TO_SOURCE_TYPE: dict[str, SourceType] = {
    ".txt": "text",
    ".md": "markdown",
    ".docx": "docx",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}


def route_document(
    path: str | Path,
) -> tuple[Path, SourceType]:
    """Validate a document and identify the required loader."""

    document_path = Path(path)

    if not document_path.exists():
        raise FileNotFoundError(f"文件不存在：{document_path}")

    if not document_path.is_file():
        raise ValueError(f"路径不是文件：{document_path}")

    suffix = document_path.suffix.lower()
    source_type = SUFFIX_TO_SOURCE_TYPE.get(suffix)

    if source_type is None:
        supported = ", ".join(sorted(SUFFIX_TO_SOURCE_TYPE))
        displayed_suffix = suffix or "无扩展名"
        raise ValueError(
            f"不支持的文件类型：{displayed_suffix}；"
            f"支持的类型：{supported}"
        )

    file_size = document_path.stat().st_size

    if file_size == 0:
        raise ValueError("文件内容为空")

    if file_size > MAX_DOCUMENT_BYTES:
        raise ValueError("文件过大，不能超过 20 MB")

    return document_path, source_type