import pytest

from career_pilot.rag.models import (
    KnowledgeChunk,
    SearchHit,
)
from career_pilot.rag.reranking import (
    ScoreFusionReranker,
)


def make_hit(
    chunk_id: str,
    content: str,
    position: int,
    score: float,
    matched_terms: list[str] | None = None,
) -> SearchHit:
    """Create one retrieval hit for reranking tests."""

    chunk = KnowledgeChunk(
        chunk_id=chunk_id,
        document_id="agent-guide",
        title=f"文档 {chunk_id}",
        source="agent_guide.md",
        content=content,
        position=position,
    )

    return SearchHit(
        chunk=chunk,
        score=score,
        matched_terms=matched_terms or [],
    )


def test_reranker_changes_order_using_lexical_evidence() -> None:
    high_rrf_hit = make_hit(
        chunk_id="deployment-0",
        content="Kubernetes Docker deployment guide.",
        position=0,
        score=0.9,
    )
    strong_evidence_hit = make_hit(
        chunk_id="python-api-0",
        content="使用 Python 和 FastAPI 开发 Agent API。",
        position=1,
        score=0.65,
    )

    reranker = ScoreFusionReranker(
        fusion_weight=0.7,
        lexical_weight=0.3,
    )

    results = reranker.rerank(
        "Python FastAPI",
        [high_rrf_hit, strong_evidence_hit],
        top_k=2,
    )

    assert [hit.chunk.chunk_id for hit in results] == [
        "python-api-0",
        "deployment-0",
    ]

    assert results[0].score == pytest.approx(0.755)
    assert results[1].score == pytest.approx(0.63)
    assert results[0].matched_terms == [
        "fastapi",
        "python",
    ]


def test_reranker_handles_empty_hits() -> None:
    reranker = ScoreFusionReranker()

    results = reranker.rerank(
        "Python",
        [],
        top_k=3,
    )

    assert results == []


@pytest.mark.parametrize(
    ("query", "top_k", "expected_message"),
    [
        ("   ", 3, "查询不能为空"),
        ("Python", 0, "top_k 必须大于等于 1"),
    ],
)
def test_reranker_rejects_invalid_request(
    query: str,
    top_k: int,
    expected_message: str,
) -> None:
    reranker = ScoreFusionReranker()

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        reranker.rerank(
            query,
            [],
            top_k=top_k,
        )


@pytest.mark.parametrize(
    (
        "fusion_weight",
        "lexical_weight",
        "expected_message",
    ),
    [
        (-0.1, 0.3, "fusion_weight 不能小于 0"),
        (0.7, -0.1, "lexical_weight 不能小于 0"),
        (0.0, 0.0, "重排序权重之和必须大于 0"),
    ],
)
def test_reranker_rejects_invalid_weights(
    fusion_weight: float,
    lexical_weight: float,
    expected_message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        ScoreFusionReranker(
            fusion_weight=fusion_weight,
            lexical_weight=lexical_weight,
        )
