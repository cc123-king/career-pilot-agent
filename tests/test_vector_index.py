from collections.abc import Sequence

import pytest

from career_pilot.rag.models import KnowledgeChunk
from career_pilot.rag.vector_index import (
    InMemoryVectorIndex,
    cosine_similarity,
)


class FakeEmbedder:
    """Return fixed vectors without calling a real model."""

    def __init__(
        self,
        document_vectors: list[list[float]],
        query_vector: list[float],
    ) -> None:
        self._document_vectors = document_vectors
        self._query_vector = query_vector
        self.embedded_text_batches: list[list[str]] = []
        self.queries: list[str] = []

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        self.embedded_text_batches.append(list(texts))
        return self._document_vectors

    def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return self._query_vector


def make_chunks() -> list[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id="python-agent-0",
            document_id="python-agent",
            title="Python Agent 开发",
            source="python_agent.md",
            content="使用 Python 开发 Agent 和工具调用。",
            position=0,
        ),
        KnowledgeChunk(
            chunk_id="resume-guide-0",
            document_id="resume-guide",
            title="项目简历指南",
            source="resume_guide.md",
            content="简历项目需要介绍技术方案和结果。",
            position=1,
        ),
        KnowledgeChunk(
            chunk_id="database-guide-0",
            document_id="database-guide",
            title="数据库指南",
            source="database_guide.md",
            content="介绍 MySQL 数据库索引设计。",
            position=2,
        ),
    ]


def test_cosine_similarity_known_directions() -> None:
    assert cosine_similarity(
        [1.0, 0.0],
        [1.0, 0.0],
    ) == pytest.approx(1.0)

    assert cosine_similarity(
        [1.0, 0.0],
        [0.0, 1.0],
    ) == pytest.approx(0.0)

    assert cosine_similarity(
        [1.0, 0.0],
        [-1.0, 0.0],
    ) == pytest.approx(-1.0)


@pytest.mark.parametrize(
    ("left", "right", "expected_message"),
    [
        ([], [1.0], "向量不能为空"),
        ([1.0], [1.0, 0.0], "向量维度必须一致"),
        (
            [0.0, 0.0],
            [1.0, 0.0],
            "零向量无法计算余弦相似度",
        ),
    ],
)
def test_cosine_similarity_rejects_invalid_vectors(
    left: list[float],
    right: list[float],
    expected_message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        cosine_similarity(left, right)


def test_vector_index_ranks_chunks_and_reuses_vectors() -> None:
    fake_embedder = FakeEmbedder(
        document_vectors=[
            [1.0, 0.0],
            [0.8, 0.2],
            [0.0, 1.0],
        ],
        query_vector=[1.0, 0.0],
    )

    index = InMemoryVectorIndex(
        make_chunks(),
        fake_embedder,
    )

    assert index.size == 3
    assert index.dimension == 2
    assert len(fake_embedder.embedded_text_batches) == 1

    hits = index.search(
        "  Python   Agent 开发  ",
        top_k=2,
    )

    assert [hit.chunk.chunk_id for hit in hits] == [
        "python-agent-0",
        "resume-guide-0",
    ]

    assert hits[0].score == pytest.approx(1.0)
    assert hits[1].score == pytest.approx(0.9701425)
    assert hits[0].matched_terms == []
    assert fake_embedder.queries == ["Python Agent 开发"]

    index.search("再次查询", top_k=1)

    assert len(fake_embedder.embedded_text_batches) == 1
    assert fake_embedder.queries == [
        "Python Agent 开发",
        "再次查询",
    ]


@pytest.mark.parametrize(
    ("query", "top_k", "expected_message"),
    [
        ("   ", 3, "查询不能为空"),
        ("Python", 0, "top_k 必须大于等于 1"),
    ],
)
def test_vector_index_rejects_invalid_search(
    query: str,
    top_k: int,
    expected_message: str,
) -> None:
    fake_embedder = FakeEmbedder(
        document_vectors=[[1.0, 0.0]],
        query_vector=[1.0, 0.0],
    )
    index = InMemoryVectorIndex(
        make_chunks()[:1],
        fake_embedder,
    )

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        index.search(query, top_k=top_k)

    assert fake_embedder.queries == []
