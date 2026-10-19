import hashlib
import re
from pathlib import Path

from career_pilot.multimodal.models import ExtractedDocument
from career_pilot.rag.documents import chunk_document
from career_pilot.rag.models import (
    KnowledgeChunk,
    KnowledgeDocument,
)


def _build_document_id(
    document: ExtractedDocument,
) -> str:
    """Build a stable and validation-safe document ID."""

    filename_stem = Path(document.filename).stem.lower()
    safe_stem = re.sub(
        r"[^a-z0-9]+",
        "-",
        filename_stem,
    ).strip("-")

    if not safe_stem:
        safe_stem = "document"

    content_hash = hashlib.sha256(
        document.content.encode("utf-8")
    ).hexdigest()[:8]

    return f"{safe_stem[:40]}-{content_hash}"


def chunk_extracted_document(
    document: ExtractedDocument,
    *,
    max_characters: int = 500,
) -> list[KnowledgeChunk]:
    """Convert an extracted document into page-aware RAG chunks."""

    document_id = _build_document_id(document)
    title = Path(document.filename).stem
    chunks: list[KnowledgeChunk] = []

    for page in document.pages:
        page_document = KnowledgeDocument(
            document_id=document_id,
            title=title,
            source=document.filename,
            content=page.text,
        )

        page_chunks = chunk_document(
            page_document,
            max_characters=max_characters,
        )

        for page_chunk in page_chunks:
            chunks.append(
                KnowledgeChunk(
                    chunk_id=(
                        f"{document_id}-"
                        f"p{page.page_number}-"
                        f"{page_chunk.position}"
                    ),
                    document_id=document_id,
                    title=title,
                    source=document.filename,
                    content=page_chunk.content,
                    position=len(chunks),
                    page_number=page.page_number,
                    extraction_method=page.extraction_method,
                    source_type=document.source_type,
                )
            )

    return chunks