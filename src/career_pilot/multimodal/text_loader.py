from pathlib import Path

from career_pilot.multimodal.models import (
    ExtractedDocument,
    ExtractedPage,
)
from career_pilot.multimodal.routing import route_document


def load_text_document(
    path: str | Path,
) -> ExtractedDocument:
    """Load a UTF-8 TXT or Markdown file."""

    document_path, source_type = route_document(path)

    if source_type not in {"text", "markdown"}:
        raise ValueError(
            "文本加载器只支持 .txt 和 .md 文件"
        )

    try:
        content = document_path.read_text(
            encoding="utf-8-sig",
        ).strip()
    except UnicodeDecodeError as exc:
        raise ValueError(
            "文本文件必须使用 UTF-8 编码"
        ) from exc

    if not content:
        raise ValueError("文本文件没有有效内容")

    return ExtractedDocument(
        filename=document_path.name,
        source_path=str(document_path.resolve()),
        source_type=source_type,
        pages=[
            ExtractedPage(
                page_number=1,
                text=content,
                extraction_method="native_text",
            )
        ],
    )