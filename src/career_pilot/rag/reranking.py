from collections.abc import Sequence
from typing import Protocol

from career_pilot.rag.models import SearchHit
from career_pilot.rag.retrieval import search_chunks
from career_pilot.text_utils import normalize_text


class CandidateReranker(Protocol):
    """Something capable of reranking retrieved hits."""

    def rerank(
        self,
        query: str,
        hits: Sequence[SearchHit],
        *,
        top_k: int = 3,
    ) -> list[SearchHit]: ...


class ScoreFusionReranker:
    """Rerank hits using RRF and lexical evidence scores."""

    def __init__(
        self,
        *,
        fusion_weight: float = 0.7,
        lexical_weight: float = 0.3,
    ) -> None:
        if fusion_weight < 0:
            raise ValueError("fusion_weight 不能小于 0")

        if lexical_weight < 0:
            raise ValueError("lexical_weight 不能小于 0")

        total_weight = fusion_weight + lexical_weight

        if total_weight == 0:
            raise ValueError("重排序权重之和必须大于 0")

        self._fusion_weight = fusion_weight / total_weight
        self._lexical_weight = lexical_weight / total_weight

    def rerank(
        self,
        query: str,
        hits: Sequence[SearchHit],
        *,
        top_k: int = 3,
    ) -> list[SearchHit]:
        """Return candidates sorted by combined evidence."""

        normalized_query = normalize_text(query)

        if not normalized_query:
            raise ValueError("查询不能为空")

        if top_k < 1:
            raise ValueError("top_k 必须大于等于 1")

        reranked_hits: list[SearchHit] = []

        for hit in hits:
            keyword_hits = search_chunks(
                normalized_query,
                [hit.chunk],
                top_k=1,
            )

            if keyword_hits:
                lexical_score = keyword_hits[0].score
                lexical_terms = keyword_hits[0].matched_terms
            else:
                lexical_score = 0.0
                lexical_terms = []

            final_score = (
                self._fusion_weight * hit.score + self._lexical_weight * lexical_score
            )

            combined_terms = sorted(set(hit.matched_terms) | set(lexical_terms))

            reranked_hits.append(
                SearchHit(
                    chunk=hit.chunk,
                    score=final_score,
                    matched_terms=combined_terms,
                )
            )

        reranked_hits.sort(
            key=lambda hit: (
                -hit.score,
                hit.chunk.position,
                hit.chunk.chunk_id,
            )
        )

        return reranked_hits[:top_k]
