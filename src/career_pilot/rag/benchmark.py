"""Evidence-level retrieval evaluation with development-only selection."""

from collections.abc import Sequence
from math import ceil
from pathlib import Path
from statistics import mean, median
from typing import Literal

from pydantic import Field, TypeAdapter, field_validator, model_validator

from career_pilot.models import StrictModel
from career_pilot.rag.models import KnowledgeDocument, SearchHit


def canonical_text(value: str) -> str:
    return "".join(value.split()).casefold()


class EvidenceLabel(StrictModel):
    source: str = Field(min_length=1)
    anchor: str = Field(min_length=1)

    @field_validator("source", "anchor")
    @classmethod
    def strip_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("证据来源和原文锚点不能为空")
        return value.strip()


class BenchmarkCase(StrictModel):
    case_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    split: Literal["dev", "test"]
    category: Literal["direct", "paraphrase", "multi_source", "negative"]
    question: str = Field(min_length=1, max_length=2000)
    evidence: list[EvidenceLabel]

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()

    @model_validator(mode="after")
    def check_labels(self) -> "BenchmarkCase":
        if (self.category == "negative") != (not self.evidence):
            raise ValueError("无答案题应标为 negative，其他题必须有证据")
        labels = {(item.source, canonical_text(item.anchor)) for item in self.evidence}
        if len(labels) != len(self.evidence):
            raise ValueError("证据标签不能重复")
        if (
            self.category == "multi_source"
            and len({item.source for item in self.evidence}) < 2
        ):
            raise ValueError("multi_source 至少需要两个不同来源")
        return self


def load_benchmark_cases(path: str | Path) -> list[BenchmarkCase]:
    cases = TypeAdapter(list[BenchmarkCase]).validate_json(
        Path(path).read_text(encoding="utf-8")
    )
    if not cases:
        raise ValueError("评测集不能为空")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("case_id 不能重复")
    if len({canonical_text(case.question) for case in cases}) != len(cases):
        raise ValueError("问题不能在开发和测试分组中重复")
    for split in ("dev", "test"):
        group = [case for case in cases if case.split == split]
        if not any(case.evidence for case in group) or not any(
            not case.evidence for case in group
        ):
            raise ValueError(f"{split} 分组必须同时有可回答和无答案题")
    return cases


def validate_benchmark_labels(
    cases: Sequence[BenchmarkCase], documents: Sequence[KnowledgeDocument]
) -> None:
    contents = {
        document.source: canonical_text(document.content) for document in documents
    }
    for case in cases:
        for label in case.evidence:
            if label.source not in contents:
                raise ValueError(f"{case.case_id}: 标准来源不存在: {label.source}")
            if canonical_text(label.anchor) not in contents[label.source]:
                raise ValueError(f"{case.case_id}: 原文锚点不存在: {label.anchor}")


def _supports(hit: SearchHit, label: EvidenceLabel) -> bool:
    return hit.chunk.source == label.source and canonical_text(
        label.anchor
    ) in canonical_text(hit.chunk.content)


def evaluate_snapshot(
    cases: Sequence[BenchmarkCase],
    snapshots: dict[str, list[SearchHit]],
    *,
    top_k: int,
    min_score: float,
    elapsed_ms: dict[str, float] | None = None,
) -> dict:
    if not cases or top_k < 1 or not 0 <= min_score <= 1:
        raise ValueError("评测集不能为空，top_k >= 1，阈值必须在 0 到 1 之间")
    rows = []
    for case in cases:
        # Preserve positions in the original top-k result list after filtering.
        retained = [
            (rank, hit)
            for rank, hit in enumerate(snapshots[case.case_id][:top_k], start=1)
            if hit.score >= min_score
        ]
        sources = {hit.chunk.source for _, hit in retained}
        expected_sources = {label.source for label in case.evidence}
        covered = [
            any(_supports(hit, label) for _, hit in retained) for label in case.evidence
        ]
        ranks = [
            rank
            for rank, hit in retained
            if any(_supports(hit, label) for label in case.evidence)
        ]
        answerable = bool(case.evidence)
        rows.append(
            {
                "case_id": case.case_id,
                "question": case.question,
                "category": case.category,
                "expected_evidence": [label.model_dump() for label in case.evidence],
                "source_recall": len(sources & expected_sources) / len(expected_sources)
                if answerable
                else None,
                "evidence_coverage": mean(covered) if answerable else None,
                "evidence_reciprocal_rank": 1 / min(ranks)
                if ranks
                else 0.0
                if answerable
                else None,
                "unanswerable_empty": not retained if not answerable else None,
                "answerable_empty": not retained if answerable else None,
                "retrieved": [
                    {
                        "rank": rank,
                        "chunk_id": hit.chunk.chunk_id,
                        "source": hit.chunk.source,
                        "score": hit.score,
                        "content": hit.chunk.content,
                        "supports_expected_evidence": any(
                            _supports(hit, label) for label in case.evidence
                        ),
                    }
                    for rank, hit in retained
                ],
            }
        )

    def average(field: str) -> float | None:
        values = [row[field] for row in rows if row[field] is not None]
        return mean(values) if values else None

    durations = sorted((elapsed_ms or {}).get(case.case_id, 0.0) for case in cases)
    return {
        "case_count": len(cases),
        "answerable_count": sum(bool(case.evidence) for case in cases),
        "unanswerable_count": sum(not case.evidence for case in cases),
        "source_recall_at_k": average("source_recall"),
        "evidence_coverage_at_k": average("evidence_coverage"),
        "evidence_mrr_at_k": average("evidence_reciprocal_rank"),
        "unanswerable_empty_rate": average("unanswerable_empty"),
        "answerable_empty_rate": average("answerable_empty"),
        "retrieval_p50_ms": median(durations) if elapsed_ms else None,
        "retrieval_p95_ms": durations[ceil(len(durations) * 0.95) - 1]
        if elapsed_ms
        else None,
        "results": rows,
    }


def select_development_configuration(experiments: Sequence[dict]) -> dict:
    """Select using dev metrics only, never accepting test rows as candidates."""
    if not experiments or any(item.get("split") != "dev" for item in experiments):
        raise ValueError("参数选择只接受非空 dev 评测结果")

    def key(item: dict) -> tuple:
        metrics = item["metrics"]
        coverage = metrics["evidence_coverage_at_k"]
        empty_rate = metrics["unanswerable_empty_rate"]
        if coverage is None or empty_rate is None:
            raise ValueError("开发集必须包含可回答和无答案题")
        options = item["configuration"]
        return (
            (coverage + empty_rate) / 2,
            coverage,
            empty_rate,
            -options["top_k"],
            -options["max_characters"],
            -options["min_score"],
        )

    return max(experiments, key=key)
