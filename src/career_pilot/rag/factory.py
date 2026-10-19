"""Shared assembly for the real API and the end-to-end evaluation runner."""

from collections.abc import Sequence

from career_pilot.rag.evidence import EvidenceGate
from career_pilot.rag.grounding import GroundedAnswerPipeline
from career_pilot.rag.hybrid_retrieval import HybridCandidateRetriever, HybridRetriever
from career_pilot.rag.models import KnowledgeChunk
from career_pilot.rag.reranking import ScoreFusionReranker
from career_pilot.rag.service import RAGService
from career_pilot.rag.source_scope import APIAwareRetriever
from career_pilot.rag.vector_index import InMemoryVectorIndex
from career_pilot.rag.windows import NeighborWindowRetriever

DEFAULT_RAG_CONFIG = {
    "pipeline_version": "grounded-rag-v8-scope",
    "max_characters": 300,
    "top_k": 6,
    "min_score": 0.0,
    "candidate_k": 20,
    "rank_constant": 60,
    "keyword_weight": 1.0,
    "vector_weight": 2.0,
    "window_radius": 1,
    "fusion_weight": 1.0,
    "lexical_weight": 0.0,
}


def create_grounded_rag_service(
    chunks: Sequence[KnowledgeChunk],
    llm_client,
    embedder,
    *,
    configuration=None,
) -> RAGService:
    config = dict(DEFAULT_RAG_CONFIG if configuration is None else configuration)
    index = InMemoryVectorIndex(chunks, embedder)
    candidates = HybridCandidateRetriever(
        chunks, index, candidate_k=config["candidate_k"]
    )
    retriever = HybridRetriever(
        candidates,
        rank_constant=config["rank_constant"],
        keyword_weight=config.get("keyword_weight", 1.0),
        vector_weight=config.get("vector_weight", 1.0),
        reranker=ScoreFusionReranker(
            fusion_weight=config["fusion_weight"],
            lexical_weight=config["lexical_weight"],
        ),
    )
    retriever = APIAwareRetriever(chunks, retriever)
    if config.get("window_radius", 0):
        retriever = NeighborWindowRetriever(
            chunks, retriever, radius=config["window_radius"]
        )
    return RAGService(
        chunks,
        llm_client,
        retriever=retriever,
        top_k=config["top_k"],
        min_score=config["min_score"],
        evidence_gate=EvidenceGate(llm_client, recover_once=False),
        answer_guard=GroundedAnswerPipeline(llm_client),
        answer_first_recovery=True,
    )
