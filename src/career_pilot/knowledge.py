"""A small, dependency-free retrieval component for career knowledge."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .models import KnowledgeReference
from .text_utils import clip, tokenize


@dataclass(slots=True)
class KnowledgeChunk:
    title: str
    content: str


class LocalKnowledgeBase:
    """Retrieve Markdown sections using lexical token overlap.

    This is intentionally lightweight: it demonstrates the retrieval stage of
    RAG without forcing a beginner to download an embedding model. The class
    can later be replaced by Chroma, FAISS, or a hosted vector database.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.chunks = self._load()

    def _load(self) -> list[KnowledgeChunk]:
        if not self.path.exists():
            return []
        text = self.path.read_text(encoding="utf-8")
        parts = re.split(r"(?m)^##\s+", text)
        chunks: list[KnowledgeChunk] = []
        for part in parts[1:]:
            title, _, content = part.partition("\n")
            if content.strip():
                chunks.append(KnowledgeChunk(title=title.strip(), content=content.strip()))
        return chunks

    def search(self, query: str, limit: int = 3) -> list[KnowledgeReference]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk in self.chunks:
            chunk_tokens = tokenize(f"{chunk.title} {chunk.content}")
            overlap = query_tokens & chunk_tokens
            if not overlap:
                continue
            precision = len(overlap) / max(len(query_tokens), 1)
            coverage = len(overlap) / max(len(chunk_tokens), 1)
            score = min(1.0, precision * 0.8 + coverage * 1.5)
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            KnowledgeReference(
                title=chunk.title,
                excerpt=clip(chunk.content, 360),
                relevance=round(score, 3),
            )
            for score, chunk in scored[:limit]
        ]

