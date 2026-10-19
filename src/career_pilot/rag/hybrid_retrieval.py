from collections.abc import Sequence
from typing import Protocol

from pydantic import Field

from career_pilot.models import StrictModel
from career_pilot.rag.models import (
    KnowledgeChunk,
    SearchHit,
)
from career_pilot.rag.reranking import (
    CandidateReranker,
)
from career_pilot.rag.retrieval import search_chunks
from career_pilot.rag.rrf import reciprocal_rank_fusion
from career_pilot.text_utils import normalize_text


class VectorSearcher(Protocol):
    """Something capable of vector-based search."""

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
    ) -> list[SearchHit]: ...


class HybridCandidates(StrictModel):
    """Candidate lists returned by two retrieval methods."""

    keyword_hits: list[SearchHit] = Field(default_factory=list)
    vector_hits: list[SearchHit] = Field(default_factory=list)


class HybridCandidateRetriever:
    """Retrieve candidates with keyword and vector search."""

    def __init__(
        self,
        chunks: Sequence[KnowledgeChunk],
        vector_searcher: VectorSearcher,
        *,
        candidate_k: int = 6,
    ) -> None:
        if not chunks:
            raise ValueError("知识分块不能为空")

        if candidate_k < 1:
            raise ValueError("candidate_k 必须大于等于 1")

        self._chunks = list(chunks)
        self._vector_searcher = vector_searcher
        self._candidate_k = candidate_k

    def retrieve(
        self,
        query: str,
    ) -> HybridCandidates:
        """Run both retrieval methods for one query."""

        normalized_query = normalize_text(query)

        if not normalized_query:
            raise ValueError("查询不能为空")

        keyword_hits = search_chunks(
            normalized_query,
            self._chunks,
            top_k=self._candidate_k,
        )
        vector_hits = self._vector_searcher.search(
            normalized_query,
            top_k=self._candidate_k,
        )

        return HybridCandidates(
            keyword_hits=keyword_hits,
            vector_hits=vector_hits,
        )


class HybridRetriever:
    """Combine retrieval, RRF, and optional reranking."""

    def __init__(
        self,
        candidate_retriever: HybridCandidateRetriever,
        *,
        reranker: CandidateReranker | None = None,
        rank_constant: int = 60,
        keyword_weight: float = 1.0,
        vector_weight: float = 1.0,
    ) -> None:
        if rank_constant < 0:
            raise ValueError("rank_constant 不能小于 0")

        self._candidate_retriever = candidate_retriever
        self._reranker = reranker
        self._rank_constant = rank_constant
        self._weights = [keyword_weight, vector_weight]
        reciprocal_rank_fusion([[], []], weights=self._weights)

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
    ) -> list[SearchHit]:
        """Return final hybrid and reranked results."""

        if top_k < 1:
            raise ValueError("top_k 必须大于等于 1")

        normalized_query = normalize_text(query)

        if not normalized_query:
            raise ValueError("查询不能为空")

        candidates = self._candidate_retriever.retrieve(normalized_query)

        fusion_top_k = top_k

        if self._reranker is not None:
            candidate_count = len(candidates.keyword_hits) + len(candidates.vector_hits)
            fusion_top_k = max(
                top_k,
                candidate_count,
            )

        fused_hits = reciprocal_rank_fusion(
            [
                candidates.keyword_hits,
                candidates.vector_hits,
            ],
            top_k=fusion_top_k,
            rank_constant=self._rank_constant,
            weights=self._weights,
        )

        if self._reranker is None:
            return fused_hits[:top_k]

        return self._reranker.rerank(
            normalized_query,
            fused_hits,
            top_k=top_k,
        )
