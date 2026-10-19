import json
import runpy
from pathlib import Path

import pytest
from pydantic import ValidationError

from career_pilot.rag.benchmark import (
    BenchmarkCase,
    EvidenceLabel,
    evaluate_snapshot,
    load_benchmark_cases,
    select_development_configuration,
    validate_benchmark_labels,
)
from career_pilot.rag.models import KnowledgeChunk, KnowledgeDocument, SearchHit

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/benchmark_retrieval.py"


def make_hit(content="target evidence", source="a.md", position=0, score=0.8):
    return SearchHit(
        chunk=KnowledgeChunk(
            chunk_id=f"a-{position}",
            document_id="a",
            title="A",
            source=source,
            content=content,
            position=position,
        ),
        score=score,
    )


def make_case(**updates):
    values = {
        "case_id": "a",
        "split": "dev",
        "category": "direct",
        "question": "Question",
        "evidence": [{"source": "a.md", "anchor": "target evidence"}],
    }
    values.update(updates)
    return BenchmarkCase(**values)


def test_same_source_wrong_passage_is_not_evidence_success():
    result = evaluate_snapshot(
        [make_case()], {"a": [make_hit("unrelated")]}, top_k=1, min_score=0.05
    )
    assert result["source_recall_at_k"] == 1
    assert result["evidence_coverage_at_k"] == 0
    assert result["evidence_mrr_at_k"] == 0


def test_duplicate_hits_do_not_inflate_evidence_and_mrr_keeps_rank():
    hits = [make_hit("wrong"), make_hit(position=1), make_hit(position=2)]
    result = evaluate_snapshot([make_case()], {"a": hits}, top_k=3, min_score=0.05)
    assert result["evidence_coverage_at_k"] == 1
    assert result["evidence_mrr_at_k"] == 0.5


def test_multiple_evidence_units_measure_partial_coverage():
    case = make_case(
        category="multi_source",
        evidence=[
            {"source": "a.md", "anchor": "target evidence"},
            {"source": "b.md", "anchor": "other evidence"},
        ],
    )
    result = evaluate_snapshot([case], {"a": [make_hit()]}, top_k=1, min_score=0.05)
    assert result["source_recall_at_k"] == result["evidence_coverage_at_k"] == 0.5


def test_no_answer_and_answerable_misses_are_separate():
    cases = [make_case(), make_case(case_id="n", category="negative", evidence=[])]
    result = evaluate_snapshot(
        cases, {"a": [], "n": [make_hit(score=0.19)]}, top_k=1, min_score=0.20
    )
    assert result["answerable_empty_rate"] == 1
    assert result["unanswerable_empty_rate"] == 1
    assert result["evidence_coverage_at_k"] == 0


def test_threshold_boundary_and_original_rank():
    result = evaluate_snapshot(
        [make_case()],
        {"a": [make_hit("bad", score=0.01), make_hit(position=1, score=0.2)]},
        top_k=2,
        min_score=0.2,
    )
    assert result["evidence_mrr_at_k"] == 0.5
    assert result["results"][0]["retrieved"][0]["rank"] == 2


@pytest.mark.parametrize(
    "updates",
    [
        {"category": "negative"},
        {"evidence": []},
        {"category": "multi_source"},
        {"question": " "},
        {"evidence": [{"source": "a.md", "anchor": "x"}] * 2},
    ],
)
def test_invalid_case_labels_are_rejected(updates):
    with pytest.raises(ValidationError):
        make_case(**updates)


@pytest.mark.parametrize("threshold", [-0.1, 1.1, float("nan")])
def test_invalid_thresholds_are_rejected(threshold):
    with pytest.raises(ValueError):
        evaluate_snapshot([make_case()], {"a": []}, top_k=1, min_score=threshold)


def test_labels_are_checked_against_actual_source_content():
    doc = KnowledgeDocument(
        document_id="a", title="A", source="a.md", content="target evidence"
    )
    validate_benchmark_labels([make_case()], [doc])
    with pytest.raises(ValueError, match="原文锚点"):
        validate_benchmark_labels(
            [make_case()], [doc.model_copy(update={"content": "wrong"})]
        )
    with pytest.raises(ValueError, match="标准来源"):
        validate_benchmark_labels([make_case()], [])


def test_parameter_selection_refuses_test_metrics():
    experiment = {
        "split": "dev",
        "configuration": {"top_k": 1, "max_characters": 100, "min_score": 0.2},
        "metrics": {"evidence_coverage_at_k": 0.8, "unanswerable_empty_rate": 0.8},
    }
    assert select_development_configuration([experiment]) == experiment
    with pytest.raises(ValueError, match="dev"):
        select_development_configuration([{**experiment, "split": "test"}])


def test_bundled_cases_have_frozen_splits_and_hard_negatives():
    cases = load_benchmark_cases(ROOT / "evaluation/benchmark_cases.json")
    assert len(cases) == 30
    for split in ("dev", "test"):
        selected = [case for case in cases if case.split == split]
        assert len(selected) == 15
        assert sum(not case.evidence for case in selected) == 5
        assert sum(case.category == "multi_source" for case in selected) == 2


def test_offline_runner_blocks_network_and_saves_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--output-dir", str(tmp_path)])

    def forbid_network(*args, **kwargs):
        raise AssertionError("Offline evaluation must not use a network")

    monkeypatch.setattr("socket.socket.connect", forbid_network)
    runpy.run_path(str(SCRIPT), run_name="__main__")
    path = next(tmp_path.glob("benchmark-*/report.json"))
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["live_embedding_calls"] is False
    assert report["generation_calls"] is False
    assert len(report["dev_experiments"]["keyword"]) == 18
    assert report["selected_by_mode"]["keyword"]["test_metrics"]["case_count"] == 15
    assert len(report["dataset_sha256"]) == 64
    assert path.with_name("summary.md").is_file()


def test_live_comparison_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--mode", "compare"])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert error.value.code == 2


def test_anchors_ignore_whitespace_but_not_source():
    result = evaluate_snapshot(
        [make_case()], {"a": [make_hit("TARGET \n EVIDENCE")]}, top_k=1, min_score=0.05
    )
    assert result["evidence_coverage_at_k"] == 1
    label = EvidenceLabel(source="b.md", anchor="target evidence")
    result = evaluate_snapshot(
        [make_case(evidence=[label])], {"a": [make_hit()]}, top_k=1, min_score=0.05
    )
    assert result["evidence_coverage_at_k"] == 0


def test_embedding_cache_reuses_documents_and_queries():
    namespace = runpy.run_path(str(SCRIPT))

    class FakeEmbedder:
        def __init__(self):
            self.calls = []

        def embed_texts(self, texts):
            self.calls.append(list(texts))
            return [[1.0, float(len(text))] for text in texts]

    client = FakeEmbedder()
    cache = namespace["CachedEmbedder"](client)
    assert len(cache.embed_texts(["a", "a", "bb"])) == 3
    assert cache.embed_query("a") == [1.0, 1.0]
    assert client.calls == [["a", "bb"]]


def test_four_mode_factory_uses_existing_vector_and_rrf_pipeline():
    namespace = runpy.run_path(str(SCRIPT))

    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[1.0, float(len(text))] for text in texts]

        def embed_query(self, query):
            return [1.0, float(len(query))]

    retrievers = namespace["build_retrievers"](
        [make_hit().chunk], mode="compare", embedder=FakeEmbedder()
    )
    assert set(retrievers) == {"keyword", "vector", "hybrid_rrf", "hybrid_reranked"}
    assert all(retriever.search("target", top_k=1) for retriever in retrievers.values())
    # Fake vectors verify wiring only, never semantic retrieval quality.


@pytest.mark.parametrize("returncode", [0, 1])
def test_evidence_collector_records_actual_step_status(
    tmp_path, monkeypatch, returncode
):
    import subprocess

    collector = ROOT / "scripts/collect_interview_evidence.py"
    monkeypatch.setattr("sys.argv", [str(collector), "--output-dir", str(tmp_path)])

    def fake_run(command, **options):
        assert options["check"] is False
        assert options["timeout"] == 120
        return subprocess.CompletedProcess(command, returncode, "7 passed\n", "")

    from types import SimpleNamespace

    main = runpy.run_path(str(collector))["main"]
    # Replace only the collector's process dependency. A global subprocess.run
    # patch also intercepts platform.platform() -> uname on Linux.
    monkeypatch.setitem(
        main.__globals__,
        "subprocess",
        SimpleNamespace(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired),
    )
    if returncode:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 1
    else:
        main()
    manifest_path = next(tmp_path.glob("evidence-*/manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["all_steps_succeeded"] is (returncode == 0)
    assert all(item["exit_code"] == returncode for item in manifest["steps"])
    assert manifest["live_model_calls"] is False
    assert manifest["steps"][0]["passed_tests"] == 7
    assert ".env" not in manifest["source_sha256"]
