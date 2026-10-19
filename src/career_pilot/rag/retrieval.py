import re
from collections.abc import Sequence

from career_pilot.rag.models import KnowledgeChunk, SearchHit
from career_pilot.text_utils import normalize_text

ASCII_TERM_PATTERN = re.compile(r"[a-z0-9][a-z0-9+#._-]*")
CHINESE_SEQUENCE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


def _tokenize(text: str) -> set[str]:
    """Create a small deterministic token set for Chinese and English text."""
    normalized = normalize_text(text).casefold()
    terms = {term.rstrip(".") for term in ASCII_TERM_PATTERN.findall(normalized)}
    terms.update(
        part for term in list(terms) for part in term.split(".") if len(part) > 1
    )

    for sequence in CHINESE_SEQUENCE_PATTERN.findall(normalized):
        terms.update(sequence)
        terms.update(sequence[index : index + 2] for index in range(len(sequence) - 1))

    return terms


def _calculate_score(
    query_terms: set[str],
    content: str,
) -> tuple[float, list[str]]:
    content_terms = _tokenize(content)
    matched_terms = sorted(query_terms & content_terms)

    if not query_terms:
        return 0.0, []

    score = len(matched_terms) / len(query_terms)
    return score, matched_terms


def search_chunks(
    query: str,
    chunks: Sequence[KnowledgeChunk],
    *,
    top_k: int = 3,
) -> list[SearchHit]:
    """Return the highest-scoring knowledge chunks."""
    if not normalize_text(query):
        raise ValueError("查询不能为空")

    if top_k < 1:
        raise ValueError("top_k 必须大于等于 1")

    query_terms = _tokenize(query)
    hits: list[SearchHit] = []

    for chunk in chunks:
        score, matched_terms = _calculate_score(
            query_terms,
            chunk.content,
        )

        if score <= 0:
            continue

        hits.append(
            SearchHit(
                chunk=chunk,
                score=score,
                matched_terms=matched_terms,
            )
        )

    hits.sort(
        key=lambda hit: (
            -hit.score,
            hit.chunk.position,
            hit.chunk.chunk_id,
        )
    )

    return hits[:top_k]


class KeywordRetriever:
    """Adapt local keyword search to the workflow's retriever interface."""

    def __init__(self, chunks: Sequence[KnowledgeChunk]) -> None:
        self._chunks = list(chunks)

    def search(self, query: str, *, top_k: int = 3) -> list[SearchHit]:
        return search_chunks(query, self._chunks, top_k=top_k)
