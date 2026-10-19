"""Frozen question protocol, vector provenance and independent repeat accounting."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "frozen_bundle", ROOT / "scripts/evaluate_frozen_bundle.py"
)
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def test_new_questions_have_existing_source_anchors_and_no_exact_old_overlap():
    dataset = ROOT / "evaluation/answer_frozen_v7_cases.json"
    docs = bundle.pipeline.load_knowledge_documents(
        ROOT / "evaluation/technical_corpus"
    )
    cases = bundle.pipeline.load_cases(dataset, docs)
    assert len(cases) == 40 and sum(c.answerable for c in cases) == 24
    old = []
    for name in [
        "answer_pipeline_v5_cases.json",
        "answer_regression_v6_cases.json",
        "technical_qa_v6_cases.json",
    ]:
        old.extend(bundle.read(ROOT / "evaluation" / name))
    assert not {c.question for c in cases} & {c["question"] for c in old}
    protocol = bundle.read(ROOT / "evaluation/answer_frozen_v7_protocol.json")
    assert (
        len(protocol["repeated_case_ids"]) == 8
        and not protocol["independent_external_human_labels"]
    )


@pytest.mark.parametrize(
    "value",
    [
        {"x": None},
        {"x": [float("inf")]},
        {"x": [True]},
        {"x": []},
        {"x": [1], "y": [1, 2]},
    ],
)
def test_bad_seed_vector_shape_or_values_rejected(value):
    with pytest.raises(ValueError):
        bundle.select_seed(value, list(value))


def test_seed_copies_only_requested_corpus_content():
    assert bundle.select_seed(
        {"approved": [1, 2], "unused_old_question": [3, 4]}, ["approved"]
    ) == {"approved": [1, 2]}


def test_embedding_model_and_corpus_provenance_must_both_match(tmp_path):
    doc = tmp_path / "a.md"
    doc.write_text("public fixture", encoding="utf-8")
    scope = {"embedding": {"provider_host": "example.org", "model": "v4"}}
    old = {
        "embedding": dict(scope["embedding"]),
        "documents": [{"path": "old/path/a.md", "sha256": bundle.sha(doc)}],
    }
    bundle.validate_seed(scope, old, [doc])
    old["embedding"]["model"] = "different"
    with pytest.raises(ValueError, match="provider/model"):
        bundle.validate_seed(scope, old, [doc])
    old["embedding"] = dict(scope["embedding"])
    doc.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Corpus hashes"):
        bundle.validate_seed(scope, old, [doc])


def test_repeat_summary_keeps_trials_separate_and_does_not_label_accuracy():
    def row(status):
        return {
            "case_id": "a",
            "answerable": True,
            "result": {
                "answer_status": status,
                "evidence_status": "sufficient",
                "sources": [{"source": "a.md"}],
            },
        }

    reports = [
        {
            "request_counts": {"embedding": 4 if i == 0 else 0, "chat": 2},
            "results": [row("supported" if i != 2 else "invalid")],
            "summary": {},
        }
        for i in range(3)
    ]
    result = bundle.summarize(reports, ["a"])
    assert result["unique_questions"] == 1 and result["completed_trials"] == 3
    assert result["all_three_contract_valid_selected"] == 0
    assert result["request_counts"] == {"embedding": 4, "chat": 6}
    assert (
        result["not_independent_factual_accuracy"]
        and not result["human_semantic_review_completed"]
    )


def test_cli_does_not_run_without_explicit_live_authorization(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["evaluate_frozen_bundle.py", "--bundle-dir", str(tmp_path)]
    )
    with pytest.raises(SystemExit) as error:
        bundle.main()
    assert error.value.code == 2
