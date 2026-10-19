from collections.abc import Sequence

import pytest

from career_pilot.rag.hybrid_retrieval import (
    HybridCandidateRetriever,
    HybridRetriever,
)
from career_pilot.rag.models import (
    KnowledgeChunk,
    SearchHit,
)


class FakeVectorSearcher:
    """Return fixed vector-search results without an API call."""

    def __init__(
        self,
        hits: list[SearchHit],
    ) -> None:
        self._hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
    ) -> list[SearchHit]:
        self.calls.append((query, top_k))
        return self._hits[:top_k]

class FakeReranker:
    """Record candidates and deliberately reverse them."""

    def __init__(self) -> None:
        self.calls: list[
            tuple[str, list[str], int]
        ] = []

    def rerank(
        self,
        query: str,
        hits: Sequence[SearchHit],
        *,
        top_k: int = 3,
    ) -> list[SearchHit]:
        chunk_ids = [
            hit.chunk.chunk_id
            for hit in hits
        ]
        self.calls.append(
            (query, chunk_ids, top_k)
        )

        return list(hits)[::-1][:top_k]

def make_chunk(
    chunk_id: str,
    content: str,
    position: int,
) -> KnowledgeChunk:
    """Create one knowledge chunk for testing."""

    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id="agent-guide",
        title="Agent 开发指南",
        source="agent_guide.md",
        content=content,
        position=position,
    )


def test_retrieve_returns_two_candidate_lists() -> None:
    keyword_chunk = make_chunk(
        "agent-guide-0",
        "LangGraph 可以组织 Agent 的工具调用流程。",
        0,
    )
    semantic_chunk = make_chunk(
        "agent-guide-1",
        "智能体可以根据任务选择合适的外部函数。",
        1,
    )
    chunks = [
        keyword_chunk,
        semantic_chunk,
    ]

    fake_vector_searcher = FakeVectorSearcher(
        [
            SearchHit(
                chunk=semantic_chunk,
                score=0.93,
                matched_terms=[],
            ),
            SearchHit(
                chunk=keyword_chunk,
                score=0.81,
                matched_terms=[],
            ),
        ]
    )

    retriever = HybridCandidateRetriever(
        chunks,
        fake_vector_searcher,
        candidate_k=2,
    )

    candidates = retriever.retrieve("  LangGraph   工具调用  ")

    assert [hit.chunk.chunk_id for hit in candidates.keyword_hits] == ["agent-guide-0"]

    assert [hit.chunk.chunk_id for hit in candidates.vector_hits] == [
        "agent-guide-1",
        "agent-guide-0",
    ]

    assert fake_vector_searcher.calls == [("LangGraph 工具调用", 2)]


def test_retrieve_rejects_blank_query() -> None:
    chunk = make_chunk(
        "agent-guide-0",
        "Agent 工具调用。",
        0,
    )
    fake_vector_searcher = FakeVectorSearcher([])

    retriever = HybridCandidateRetriever(
        [chunk],
        fake_vector_searcher,
    )

    with pytest.raises(
        ValueError,
        match="查询不能为空",
    ):
        retriever.retrieve("   ")

    assert fake_vector_searcher.calls == []


def test_retriever_rejects_empty_chunks() -> None:
    fake_vector_searcher = FakeVectorSearcher([])

    with pytest.raises(
        ValueError,
        match="知识分块不能为空",
    ):
        HybridCandidateRetriever(
            [],
            fake_vector_searcher,
        )


def test_retriever_rejects_invalid_candidate_k() -> None:
    chunk = make_chunk(
        "agent-guide-0",
        "Agent 工具调用。",
        0,
    )
    fake_vector_searcher = FakeVectorSearcher([])

    with pytest.raises(
        ValueError,
        match="candidate_k 必须大于等于 1",
    ):
        HybridCandidateRetriever(
            [chunk],
            fake_vector_searcher,
            candidate_k=0,
        )


def test_hybrid_retriever_returns_fused_results() -> None:
    keyword_chunk = make_chunk(
        "agent-guide-0",
        "LangGraph 可以组织 Agent 的工具调用流程。",
        0,
    )
    semantic_chunk = make_chunk(
        "agent-guide-1",
        "智能体可以根据任务选择合适的外部函数。",
        1,
    )
    fake_vector_searcher = FakeVectorSearcher(
        [
            SearchHit(
                chunk=semantic_chunk,
                score=0.93,
                matched_terms=[],
            ),
            SearchHit(
                chunk=keyword_chunk,
                score=0.81,
                matched_terms=[],
            ),
        ]
    )

    candidate_retriever = HybridCandidateRetriever(
        [keyword_chunk, semantic_chunk],
        fake_vector_searcher,
        candidate_k=2,
    )
    hybrid_retriever = HybridRetriever(candidate_retriever)

    results = hybrid_retriever.search(
        "LangGraph 工具调用",
        top_k=2,
    )

    assert [hit.chunk.chunk_id for hit in results] == [
        "agent-guide-0",
        "agent-guide-1",
    ]
    assert results[0].score > results[1].score
    assert results[0].matched_terms
    assert fake_vector_searcher.calls == [("LangGraph 工具调用", 2)]


def test_hybrid_retriever_validates_top_k_first() -> None:
    chunk = make_chunk(
        "agent-guide-0",
        "Agent 工具调用。",
        0,
    )
    fake_vector_searcher = FakeVectorSearcher([])

    candidate_retriever = HybridCandidateRetriever(
        [chunk],
        fake_vector_searcher,
    )
    hybrid_retriever = HybridRetriever(candidate_retriever)

    with pytest.raises(
        ValueError,
        match="top_k 必须大于等于 1",
    ):
        hybrid_retriever.search(
            "Agent",
            top_k=0,
        )

    assert fake_vector_searcher.calls == []

def test_hybrid_retriever_passes_all_hits_to_reranker() -> None:
    keyword_chunk = make_chunk(
        "agent-guide-0",
        "LangGraph 可以组织 Agent 的工具调用流程。",
        0,
    )
    semantic_chunk = make_chunk(
        "agent-guide-1",
        "智能体可以选择合适的外部函数。",
        1,
    )
    extra_chunk = make_chunk(
        "agent-guide-2",
        "系统需要记录运行日志和执行状态。",
        2,
    )

    fake_vector_searcher = FakeVectorSearcher(
        [
            SearchHit(
                chunk=semantic_chunk,
                score=0.95,
                matched_terms=[],
            ),
            SearchHit(
                chunk=keyword_chunk,
                score=0.90,
                matched_terms=[],
            ),
            SearchHit(
                chunk=extra_chunk,
                score=0.80,
                matched_terms=[],
            ),
        ]
    )
    fake_reranker = FakeReranker()

    candidate_retriever = HybridCandidateRetriever(
        [
            keyword_chunk,
            semantic_chunk,
            extra_chunk,
        ],
        fake_vector_searcher,
        candidate_k=3,
    )
    hybrid_retriever = HybridRetriever(
        candidate_retriever,
        reranker=fake_reranker,
    )

    results = hybrid_retriever.search(
        "  LangGraph   工具调用  ",
        top_k=1,
    )

    assert fake_reranker.calls == [
        (
            "LangGraph 工具调用",
            [
                "agent-guide-0",
                "agent-guide-1",
                "agent-guide-2",
            ],
            1,
        )
    ]

    assert len(results) == 1
    assert (
        results[0].chunk.chunk_id
        == "agent-guide-2"
    )