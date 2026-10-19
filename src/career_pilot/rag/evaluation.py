"""Evaluate retrieval against manually labeled sources without model calls."""

from collections.abc import Sequence
from pathlib import Path
from statistics import mean

from pydantic import Field, TypeAdapter, field_validator

from career_pilot.models import StrictModel
from career_pilot.rag.service import ChunkRetriever


class EvaluationCase(StrictModel):
    case_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    question: str = Field(min_length=1, max_length=2_000)
    expected_sources: list[str]

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("评测问题不能为空")
        return value

    @field_validator("expected_sources")
    @classmethod
    def validate_sources(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values) or len(set(values)) != len(
            values
        ):
            raise ValueError("标准来源不能重复或为空白")
        return values


class RetrievedEvidence(StrictModel):
    chunk_id: str
    source: str
    score: float


class CaseEvaluation(StrictModel):
    case_id: str
    question: str
    expected_sources: list[str]
    retrieved: list[RetrievedEvidence]
    source_recall: float | None
    reciprocal_rank: float | None
    unanswerable_empty: bool | None


class EvaluationReport(StrictModel):
    top_k: int
    min_score: float
    case_count: int
    answerable_count: int
    unanswerable_count: int
    source_recall_at_k: float | None
    mrr_at_k: float | None
    unanswerable_empty_rate: float | None
    results: list[CaseEvaluation]


def load_evaluation_cases(path: str | Path) -> list[EvaluationCase]:
    cases = TypeAdapter(list[EvaluationCase]).validate_json(
        Path(path).read_text(encoding="utf-8")
    )
    if not cases:
        raise ValueError("评测集不能为空")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("评测问题的 case_id 不能重复")
    return cases


def evaluate_retrieval(
    cases: Sequence[EvaluationCase],
    retriever: ChunkRetriever,
    *,
    top_k: int = 1,
    min_score: float = 0.05,
) -> EvaluationReport:
    if not cases:
        raise ValueError("评测集不能为空")
    if top_k < 1:
        raise ValueError("top_k 必须大于等于 1")
    if not 0 <= min_score <= 1:
        raise ValueError("min_score 必须在 0 到 1 之间")

    results: list[CaseEvaluation] = []
    for case in cases:
        # Use the same top-k-then-threshold order as RAGService.answer().
        hits = retriever.search(case.question, top_k=top_k)[:top_k]
        retained = [hit for hit in hits if hit.score >= min_score]
        expected = set(case.expected_sources)
        sources = {hit.chunk.source for hit in retained}
        first_rank = next(
            (
                rank
                for rank, hit in enumerate(retained, start=1)
                if hit.chunk.source in expected
            ),
            None,
        )
        results.append(
            CaseEvaluation(
                case_id=case.case_id,
                question=case.question,
                expected_sources=case.expected_sources,
                retrieved=[
                    RetrievedEvidence(
                        chunk_id=hit.chunk.chunk_id,
                        source=hit.chunk.source,
                        score=hit.score,
                    )
                    for hit in retained
                ],
                source_recall=len(expected & sources) / len(expected)
                if expected
                else None,
                reciprocal_rank=(1 / first_rank if first_rank else 0.0)
                if expected
                else None,
                unanswerable_empty=not retained if not expected else None,
            )
        )

    recalls = [item.source_recall for item in results if item.source_recall is not None]
    ranks = [
        item.reciprocal_rank for item in results if item.reciprocal_rank is not None
    ]
    empty_checks = [
        item.unanswerable_empty
        for item in results
        if item.unanswerable_empty is not None
    ]
    return EvaluationReport(
        top_k=top_k,
        min_score=min_score,
        case_count=len(results),
        answerable_count=len(recalls),
        unanswerable_count=len(empty_checks),
        source_recall_at_k=mean(recalls) if recalls else None,
        mrr_at_k=mean(ranks) if ranks else None,
        unanswerable_empty_rate=mean(empty_checks) if empty_checks else None,
        results=results,
    )
