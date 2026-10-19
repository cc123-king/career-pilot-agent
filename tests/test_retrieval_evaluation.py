import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from career_pilot.rag.evaluation import (
    EvaluationCase,
    evaluate_retrieval,
    load_evaluation_cases,
)
from career_pilot.rag.models import KnowledgeChunk, SearchHit


def hit(source: str, score: float = 0.8, position: int = 0) -> SearchHit:
    return SearchHit(
        chunk=KnowledgeChunk(
            chunk_id=f"test-{position}",
            document_id="test",
            title="Test",
            source=source,
            content="Test content",
            position=position,
        ),
        score=score,
    )


class FakeRetriever:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, top_k: int = 3) -> list[SearchHit]:
        self.calls.append((query, top_k))
        return self.hits[:top_k]


def test_metrics_distinguish_missing_sources_from_low_rank() -> None:
    case = EvaluationCase(
        case_id="multi", question="Question", expected_sources=["a.md", "b.md"]
    )
    retriever = FakeRetriever([hit("wrong.md"), hit("a.md", position=1)])

    report = evaluate_retrieval([case], retriever, top_k=2)

    assert retriever.calls == [("Question", 2)]
    assert report.source_recall_at_k == 0.5
    assert report.mrr_at_k == 0.5
    assert report.unanswerable_empty_rate is None


def test_multiple_chunks_from_one_source_do_not_inflate_recall() -> None:
    case = EvaluationCase(
        case_id="duplicates", question="Question", expected_sources=["a.md", "b.md"]
    )
    report = evaluate_retrieval(
        [case],
        FakeRetriever([hit("a.md"), hit("a.md", position=1)]),
        top_k=2,
    )
    assert report.source_recall_at_k == 0.5
    assert report.mrr_at_k == 1.0


def test_unanswerable_cases_are_not_counted_as_recall_successes() -> None:
    cases = [
        EvaluationCase(
            case_id="answerable", question="Known", expected_sources=["a.md"]
        ),
        EvaluationCase(case_id="unanswerable", question="Unknown", expected_sources=[]),
    ]
    report = evaluate_retrieval(cases, FakeRetriever([hit("a.md")]))

    assert report.answerable_count == report.unanswerable_count == 1
    assert report.source_recall_at_k == 1.0
    assert report.unanswerable_empty_rate == 0.0


def test_threshold_filters_irrelevant_results_and_keeps_the_boundary() -> None:
    cases = [EvaluationCase(case_id="unknown", question="Unknown", expected_sources=[])]
    retriever = FakeRetriever([hit("a.md", score=0.05)])
    assert (
        evaluate_retrieval(cases, retriever, min_score=0.05).unanswerable_empty_rate
        == 0
    )
    report = evaluate_retrieval(cases, retriever, min_score=0.06)
    assert report.unanswerable_empty_rate == 1
    assert report.source_recall_at_k is None
    assert report.mrr_at_k is None
    assert report.results[0].retrieved == []


def test_empty_results_count_as_misses_for_answerable_cases() -> None:
    case = EvaluationCase(
        case_id="missing", question="Question", expected_sources=["a.md"]
    )
    report = evaluate_retrieval([case], FakeRetriever([]))
    assert report.source_recall_at_k == 0
    assert report.mrr_at_k == 0


@pytest.mark.parametrize(
    "options",
    [
        {"top_k": 0},
        {"min_score": -0.1},
        {"min_score": 1.1},
        {"min_score": float("nan")},
    ],
    ids=["zero-k", "negative-score", "high-score", "nan-score"],
)
def test_invalid_evaluation_settings_are_rejected(options: dict) -> None:
    case = EvaluationCase(case_id="valid", question="Question", expected_sources=[])
    with pytest.raises(ValueError):
        evaluate_retrieval([case], FakeRetriever([]), **options)


def test_empty_evaluation_is_not_reported_as_perfect() -> None:
    with pytest.raises(ValueError, match="评测集不能为空"):
        evaluate_retrieval([], FakeRetriever([]))


@pytest.mark.parametrize(
    "question,sources", [(" ", []), ("Question", [" "]), ("Question", ["a.md", "a.md"])]
)
def test_invalid_case_labels_are_rejected(question: str, sources: list[str]) -> None:
    with pytest.raises(ValidationError):
        EvaluationCase(case_id="invalid", question=question, expected_sources=sources)


def test_dataset_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    case = {"case_id": "duplicate", "question": "Question", "expected_sources": []}
    path.write_text(json.dumps([case, case]), encoding="utf-8")
    with pytest.raises(ValueError, match="case_id"):
        load_evaluation_cases(path)


def test_bundled_dataset_has_answerable_and_unanswerable_cases() -> None:
    path = Path(__file__).resolve().parents[1] / "evaluation" / "retrieval_cases.json"
    cases = load_evaluation_cases(path)
    assert len(cases) == 10
    assert sum(bool(case.expected_sources) for case in cases) == 8
