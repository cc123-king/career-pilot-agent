from collections.abc import Sequence
from math import isfinite

from career_pilot.rag.models import (
    KnowledgeChunk,
    SearchHit,
)


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[SearchHit]],
    *,
    top_k: int = 3,
    rank_constant: int = 60,
    weights: Sequence[float] | None = None,
) -> list[SearchHit]:
    """Fuse ranked result lists using normalized RRF scores."""

    if top_k < 1:
        raise ValueError("top_k 必须大于等于 1")

    if rank_constant < 0:
        raise ValueError("rank_constant 不能小于 0")

    if weights is None:
        weights = [1.0] * len(result_lists)
    if len(weights) != len(result_lists) or any(
        not isfinite(w) or w < 0 for w in weights
    ):
        raise ValueError("RRF权重必须与通道对应且为有限非负数")
    if not result_lists:
        return []
    if sum(weights) <= 0:
        raise ValueError("RRF权重之和必须大于0")

    raw_scores: dict[str, float] = {}
    chunks: dict[str, KnowledgeChunk] = {}
    matched_terms: dict[str, set[str]] = {}

    for hits, weight in zip(result_lists, weights, strict=True):
        if weight == 0:
            continue
        seen_chunk_ids: set[str] = set()

        for rank, hit in enumerate(hits, start=1):
            chunk_id = hit.chunk.chunk_id

            if chunk_id in seen_chunk_ids:
                continue

            seen_chunk_ids.add(chunk_id)
            chunks.setdefault(chunk_id, hit.chunk)
            matched_terms.setdefault(
                chunk_id,
                set(),
            ).update(hit.matched_terms)

            raw_scores[chunk_id] = raw_scores.get(chunk_id, 0.0) + weight / (
                rank_constant + rank
            )

    if not raw_scores:
        return []

    maximum_score = sum(weights) / (rank_constant + 1)

    fused_hits = [
        SearchHit(
            chunk=chunks[chunk_id],
            score=min(
                1.0,
                raw_score / maximum_score,
            ),
            matched_terms=sorted(matched_terms[chunk_id]),
        )
        for chunk_id, raw_score in raw_scores.items()
    ]

    fused_hits.sort(
        key=lambda hit: (
            -hit.score,
            hit.chunk.position,
            hit.chunk.chunk_id,
        )
    )

    return fused_hits[:top_k]
