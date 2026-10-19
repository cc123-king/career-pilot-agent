"""Regression contracts for cross-language retrieval and source boundaries."""

from types import SimpleNamespace

import pytest

from career_pilot.rag.context import build_retrieval_context
from career_pilot.rag.grounding import (
    GroundedAnswerPipeline,
    build_candidate_answer_material,
    split_question_requirements,
)
from career_pilot.rag.models import KnowledgeChunk, SearchHit
from career_pilot.rag.rrf import reciprocal_rank_fusion
from career_pilot.rag.windows import NeighborWindowRetriever


def chunk(position, **updates):
    return KnowledgeChunk(
        chunk_id=f"doc-{position}",
        document_id="doc",
        source="doc.md",
        title="source",
        position=position,
        content=f"Original source segment {position}.",
        **updates,
    )


def retriever(chunks, ranked=None):
    hits = [SearchHit(chunk=c, score=0.8) for c in (ranked or chunks)]
    return NeighborWindowRetriever(
        chunks, SimpleNamespace(search=lambda query, top_k: hits[:top_k])
    )


def test_window_keeps_adjacent_original_text_and_exposes_constituent_ids():
    cs = [chunk(i) for i in range(4)]
    r = retriever(cs, [cs[1], cs[0], cs[2], cs[3]])
    first = r.search("question", top_k=1)[0]
    assert first.chunk.constituent_chunk_ids == [c.chunk_id for c in cs[:3]]
    assert all(c.content in first.chunk.content for c in cs[:3])
    assert cs[3].content not in first.chunk.content
    assert r.search("question", top_k=1) == [first]
    context = build_retrieval_context("question", [first])
    assert context.sources[0].constituent_chunk_ids == first.chunk.constituent_chunk_ids
    assert "doc-0, doc-1, doc-2" in context.content


def test_nearby_ranking_does_not_repeat_an_already_covered_center():
    cs = [chunk(i) for i in range(6)]
    hits = retriever(cs, [cs[1], cs[0], cs[2], cs[4]]).search("question", top_k=2)
    assert len(hits) == 2
    assert hits[1].chunk.constituent_chunk_ids == ["doc-3", "doc-4", "doc-5"]


@pytest.mark.parametrize(
    "other",
    [
        {"document_id": "other"},
        {"source": "other.md"},
        {"page_number": 2},
        {"extraction_method": "ocr"},
        {"source_type": "pdf"},
    ],
)
def test_neighbor_never_crosses_source_or_page_or_extraction_boundary(other):
    a = chunk(0)
    b = chunk(1).model_copy(update=other)
    hit = retriever([a, b], [a, b]).search("question", top_k=1)[0]
    assert hit.chunk == a


def test_missing_position_is_a_boundary_even_within_same_document():
    a, b = chunk(0), chunk(2)
    assert retriever([a, b]).search("q", top_k=1)[0].chunk == a


def test_window_rejects_a_foreign_snapshot():
    a = chunk(0)
    foreign = a.model_copy(update={"content": "Changed source text."})
    with pytest.raises(ValueError, match="快照"):
        retriever([a], [foreign]).search("q", top_k=1)


def test_weighted_rank_fusion_keeps_a_semantic_only_candidate_over_lexical_noise():
    a, b = chunk(0), chunk(1)
    hs = reciprocal_rank_fusion(
        [[SearchHit(chunk=a, score=0.99)], [SearchHit(chunk=b, score=0.1)]],
        weights=[1, 2],
    )
    assert hs[0].chunk == b
    assert all(0 <= h.score <= 1 for h in hs)


@pytest.mark.parametrize(
    "weights", [[0, 0], [-1, 2], [1, float("nan")], [1, float("inf")], [1]]
)
def test_rrf_rejects_unusable_channel_weights(weights):
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[], []], weights=weights)


def test_question_segmentation_preserves_separate_questions_and_all_excess_text():
    question = "是否允许？随后怎样做？"
    assert split_question_requirements(question) == ["是否允许？", "随后怎样做？"]
    assert split_question_requirements("Why? What next?") == ["Why?", "What next?"]
    assert split_question_requirements("https://example.invalid/?a=1 是什么？") == [
        "https://example.invalid/?a=1 是什么？"
    ]
    many = "".join(f"第{i}项？" for i in range(12))
    parts = split_question_requirements(many)
    assert len(parts) == 8
    assert all(f"第{i}项？" in "".join(parts) for i in range(12))


def test_missing_second_question_is_blocked_before_a_self_audit_can_pass():
    source = chunk(0)
    hit = SearchHit(chunk=source, score=0.9)
    material = build_candidate_answer_material(
        "First question? Second question?", [hit]
    )
    calls = []

    def proposal(_):
        calls.append("proposal")
        import json

        return json.dumps(
            {
                "answerable": True,
                "claims": [
                    {
                        "claim_id": 1,
                        "text": "A supported first answer.",
                        "requirement_ids": [1],
                        "evidence": [{"citation_id": 1, "quote": source.content}],
                    }
                ],
                "missing_information": [],
            }
        )

    client = SimpleNamespace(
        propose_grounded_answer=proposal,
        audit_grounded_answer=lambda *_: calls.append("audit"),
    )
    result = GroundedAnswerPipeline(client).answer(material, proposal=True)
    assert result.status == "invalid" and not result.sources
    assert calls == ["proposal"]
