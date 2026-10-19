from typing import Literal

from pydantic import Field

from career_pilot.models import StrictModel
from career_pilot.multimodal.models import (
    ExtractionMethod,
    SourceType,
)


class KnowledgeDocument(StrictModel):
    """A complete source document in the knowledge base."""

    document_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=100_000)


class KnowledgeChunk(StrictModel):
    """A retrievable part of a knowledge document."""

    chunk_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    document_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=10_000)
    position: int = Field(ge=0)
    constituent_chunk_ids: list[str] = Field(default_factory=list, max_length=5)
    page_number: int | None = Field(default=None, ge=1)
    extraction_method: ExtractionMethod | None = None
    source_type: SourceType | None = None


class SearchHit(StrictModel):
    """A ranked retrieval result with traceable source information."""

    chunk: KnowledgeChunk
    score: float = Field(ge=0, le=1)
    matched_terms: list[str] = Field(default_factory=list)


class ContextSource(StrictModel):
    """A source cited in the context sent to the language model."""

    citation_id: int = Field(ge=1)
    chunk_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    score: float = Field(ge=0, le=1)
    constituent_chunk_ids: list[str] = Field(default_factory=list, max_length=5)
    page_number: int | None = Field(default=None, ge=1)
    extraction_method: ExtractionMethod | None = None
    source_type: SourceType | None = None


class RetrievalContext(StrictModel):
    """Formatted knowledge context and its traceable sources."""

    query: str = Field(min_length=1, max_length=2_000)
    content: str = Field(min_length=1, max_length=20_000)
    sources: list[ContextSource] = Field(default_factory=list)


class RAGAnswer(StrictModel):
    """A grounded answer returned by the RAG service."""

    question: str = Field(min_length=1, max_length=2_000)
    answer: str = Field(min_length=1, max_length=20_000)
    sources: list[ContextSource] = Field(default_factory=list)
    retrieved_count: int = Field(ge=0)
    used_model: bool
    candidate_count: int = Field(default=0, ge=0)
    verification_used_model: bool = False
    generation_used_model: bool = False
    evidence_status: Literal[
        "not_checked", "supported", "insufficient", "invalid", "unavailable"
    ] = "not_checked"
    evidence_reason: str | None = None
    evidence_recovery_used: bool = False
    answer_check_used_model: bool = False
    answer_status: Literal[
        "not_checked", "supported", "insufficient", "invalid", "unavailable"
    ] = "not_checked"
    answer_reason: str | None = None
    answer_claim_count: int = Field(default=0, ge=0)
    llm_request_count: int = Field(default=0, ge=0, le=4)
