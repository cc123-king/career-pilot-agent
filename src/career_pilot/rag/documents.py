import re
from pathlib import Path

from career_pilot.documents import read_text_document
from career_pilot.rag.models import (
    KnowledgeChunk,
    KnowledgeDocument,
)
from career_pilot.text_utils import normalize_text


def load_knowledge_documents(
    directory: str | Path,
) -> list[KnowledgeDocument]:
    """Load Markdown files as traceable knowledge documents."""
    knowledge_directory = Path(directory)

    if not knowledge_directory.exists():
        raise FileNotFoundError(f"知识库目录不存在：{knowledge_directory}")

    file_paths = sorted(knowledge_directory.glob("*.md"))
    if not file_paths:
        raise ValueError("知识库中没有 Markdown 文档")

    documents: list[KnowledgeDocument] = []

    for file_path in file_paths:
        content = read_text_document(file_path)
        first_line = content.splitlines()[0]
        title = first_line.lstrip("#").strip() or file_path.stem

        documents.append(
            KnowledgeDocument(
                document_id=file_path.stem.lower(),
                title=title,
                source=file_path.name,
                content=content,
            )
        )

    return documents


def _split_long_paragraph(
    paragraph: str,
    max_characters: int,
) -> list[str]:
    return [
        paragraph[start : start + max_characters]
        for start in range(0, len(paragraph), max_characters)
    ]


def chunk_document(
    document: KnowledgeDocument,
    *,
    max_characters: int = 500,
) -> list[KnowledgeChunk]:
    """Split a document into small, traceable chunks."""
    if max_characters < 50:
        raise ValueError("每个分块至少允许 50 个字符")

    raw_paragraphs = re.split(r"\n\s*\n", document.content)
    units: list[str] = []

    for raw_paragraph in raw_paragraphs:
        paragraph = normalize_text(raw_paragraph)
        if not paragraph:
            continue

        units.extend(
            _split_long_paragraph(
                paragraph,
                max_characters,
            )
        )

    chunk_texts: list[str] = []
    current = ""

    for unit in units:
        candidate = unit if not current else f"{current}\n\n{unit}"

        if current and len(candidate) > max_characters:
            chunk_texts.append(current)
            current = unit
        else:
            current = candidate

    if current:
        chunk_texts.append(current)

    return [
        KnowledgeChunk(
            chunk_id=f"{document.document_id}-{position}",
            document_id=document.document_id,
            title=document.title,
            source=document.source,
            content=content,
            position=position,
        )
        for position, content in enumerate(chunk_texts)
    ]
