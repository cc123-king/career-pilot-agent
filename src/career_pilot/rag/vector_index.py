from collections.abc import Sequence
from math import isfinite, sqrt
from typing import Protocol

from career_pilot.rag.models import (
    KnowledgeChunk,
    SearchHit,
)
from career_pilot.text_utils import normalize_text


class VectorEmbedder(Protocol):
    """Something capable of converting text into vectors."""

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]: ...

    def embed_query(self, query: str) -> list[float]: ...


def cosine_similarity(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    """Calculate cosine similarity between two vectors."""

    if not left or not right:
        raise ValueError("向量不能为空")

    if len(left) != len(right):
        raise ValueError("向量维度必须一致")

    if any(not isfinite(value) for value in (*left, *right)):
        raise ValueError("向量必须包含有限数值")

    dot_product = sum(
        left_value * right_value
        for left_value, right_value in zip(
            left,
            right,
            strict=True,
        )
    )
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        raise ValueError("零向量无法计算余弦相似度")

    similarity = dot_product / (left_norm * right_norm)

    return max(-1.0, min(1.0, similarity))


class InMemoryVectorIndex:
    """Search knowledge chunks using vector similarity."""

    def __init__(
        self,
        chunks: Sequence[KnowledgeChunk],
        embedder: VectorEmbedder,
    ) -> None:
        if not chunks:
            raise ValueError("知识分块不能为空")

        self._chunks = list(chunks)
        self._embedder = embedder
        self._vectors = embedder.embed_texts([chunk.content for chunk in self._chunks])

        if len(self._vectors) != len(self._chunks):
            raise RuntimeError("知识分块和向量数量不一致")

        if not self._vectors or not self._vectors[0]:
            raise RuntimeError("知识分块向量不能为空")

        self._dimension = len(self._vectors[0])

        if any(len(vector) != self._dimension for vector in self._vectors):
            raise RuntimeError("知识分块向量维度不一致")

    @property
    def size(self) -> int:
        """Return the number of indexed chunks."""

        return len(self._chunks)

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""

        return self._dimension

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
    ) -> list[SearchHit]:
        """Return chunks closest to the query vector."""

        normalized_query = normalize_text(query)

        if not normalized_query:
            raise ValueError("查询不能为空")

        if top_k < 1:
            raise ValueError("top_k 必须大于等于 1")

        query_vector = self._embedder.embed_query(normalized_query)

        if len(query_vector) != self._dimension:
            raise RuntimeError("查询向量和知识分块向量维度不一致")

        hits: list[SearchHit] = []

        for chunk, vector in zip(
            self._chunks,
            self._vectors,
            strict=True,
        ):
            similarity = cosine_similarity(
                query_vector,
                vector,
            )

            score = max(0.0, similarity)

            if score <= 0:
                continue

            hits.append(
                SearchHit(
                    chunk=chunk,
                    score=score,
                    matched_terms=[],
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
