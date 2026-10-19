import pytest

from career_pilot.rag.models import (
    KnowledgeChunk,
    SearchHit,
)
from career_pilot.rag.rrf import reciprocal_rank_fusion


def make_chunk(
    chunk_id: str,
    position: int,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id="agent-guide",
        title=f"文档 {chunk_id}",
        source="agent_guide.md",
        content=f"{chunk_id} 的测试内容。",
        position=position,
    )


def make_hit(
    chunk: KnowledgeChunk,
    score: float,
    matched_terms: list[str] | None = None,
) -> SearchHit:
    return SearchHit(
        chunk=chunk,
        score=score,
        matched_terms=matched_terms or [],
    )


def test_rrf_fuses_rankings_and_removes_duplicates() -> None:
    chunk_a = make_chunk("chunk-a", 0)
    chunk_b = make_chunk("chunk-b", 1)
    chunk_c = make_chunk("chunk-c", 2)
    chunk_d = make_chunk("chunk-d", 3)

    keyword_hits = [
        make_hit(chunk_a, 0.9, ["agent"]),
        make_hit(chunk_b, 0.8, ["工具"]),
        make_hit(chunk_c, 0.7, ["rag"]),
    ]
    vector_hits = [
        make_hit(chunk_c, 0.99),
        make_hit(chunk_a, 0.95),
        make_hit(chunk_d, 0.90),
    ]

    fused_hits = reciprocal_rank_fusion(
        [keyword_hits, vector_hits],
        top_k=3,
    )

    assert [hit.chunk.chunk_id for hit in fused_hits] == [
        "chunk-a",
        "chunk-c",
        "chunk-b",
    ]

    assert fused_hits[0].score > fused_hits[1].score
    assert fused_hits[1].score > fused_hits[2].score
    assert 0 <= fused_hits[0].score <= 1
    assert fused_hits[0].matched_terms == ["agent"]


def test_rrf_handles_empty_results() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


@pytest.mark.parametrize(
    ("top_k", "rank_constant", "expected_message"),
    [
        (0, 60, "top_k 必须大于等于 1"),
        (3, -1, "rank_constant 不能小于 0"),
    ],
)
def test_rrf_rejects_invalid_parameters(
    top_k: int,
    rank_constant: int,
    expected_message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        reciprocal_rank_fusion(
            [],
            top_k=top_k,
            rank_constant=rank_constant,
        )
