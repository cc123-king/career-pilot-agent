"""Freeze 40 new questions plus two independent 8-question repeat runs. No paid calls by default."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location(
    "answer_pipeline_evaluator", ROOT / "scripts/evaluate_answer_pipeline.py"
)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def validate_seed(scope, seed_scope, documents):
    if scope["embedding"] != seed_scope["embedding"]:
        raise ValueError("Embedding provider/model does not match seed provenance")
    previous = {Path(d["path"]).name: d["sha256"] for d in seed_scope["documents"]}
    current = {p.name: sha(p) for p in documents}
    if previous != current:
        raise ValueError("Corpus hashes do not match seed provenance")


def select_seed(vectors, texts):
    selected = {text: vectors[text] for text in texts if text in vectors}
    if not selected or any(
        not isinstance(v, list)
        or not v
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
        for v in selected.values()
    ):
        raise ValueError("Seed vectors are invalid")
    sizes = {len(v) for v in selected.values()}
    if len(sizes) != 1:
        raise ValueError("Seed vectors have mixed dimensions")
    return selected


def summarize(reports, repeat_ids):
    grouped = {}
    requests = {"embedding": 0, "chat": 0}
    for number, report in enumerate(reports, 1):
        for key in requests:
            requests[key] += report["request_counts"][key]
        for row in report["results"]:
            grouped.setdefault(row["case_id"], []).append(row)

    def valid(row):
        result = row["result"]
        return (
            result["answer_status"] == "supported"
            if row["answerable"]
            else result["evidence_status"] == "insufficient"
            and result["answer_status"] in ("not_checked", "insufficient")
            and not result["sources"]
        )

    return {
        "unique_questions": len(grouped),
        "completed_trials": sum(len(v) for v in grouped.values()),
        "request_counts": requests,
        "per_run": [r["summary"] for r in reports],
        "all_three_contract_valid_selected": sum(
            len(grouped.get(cid, [])) == 3 and all(valid(r) for r in grouped[cid])
            for cid in repeat_ids
        ),
        "selected_repeated_questions": len(repeat_ids),
        "human_semantic_review_completed": False,
        "not_independent_factual_accuracy": True,
        "known_corpus_new_author_labeled_questions": True,
    }


def prepare(args):
    dataset = ROOT / "evaluation/answer_frozen_v7_cases.json"
    protocol_path = ROOT / "evaluation/answer_frozen_v7_protocol.json"
    raw = read(dataset)
    protocol = read(protocol_path)
    if len(raw) != 40 or len({x["case_id"] for x in raw}) != 40:
        raise ValueError("Expected 40 unique new questions")
    selected = [c for c in raw if c["case_id"] in protocol["repeated_case_ids"]]
    if len(selected) != 8:
        raise ValueError("Expected 8 fixed repeated questions")
    docs = pipeline.load_knowledge_documents(ROOT / "evaluation/technical_corpus")
    pipeline.load_cases(dataset, docs)
    chunks = [
        c
        for d in docs
        for c in pipeline.chunk_document(
            d, max_characters=pipeline.DEFAULT_RAG_CONFIG["max_characters"]
        )
    ]
    corpus_texts = list(
        dict.fromkeys(pipeline.normalize_text(c.content) for c in chunks)
    )
    seed_scope = read(args.seed_scope)
    vectors = read(args.seed_vectors)
    bundle = args.bundle_dir.resolve()
    bundle.mkdir(parents=True, exist_ok=True)
    runs = []
    for name, items, limit in [
        ("primary-40", raw, 4),
        ("repeat-2", selected, 0),
        ("repeat-3", selected, 0),
    ]:
        case_path = bundle / (name + "-cases.json")
        write(case_path, items)
        cases = pipeline.load_cases(case_path, docs)
        scope = pipeline.prepare_scope(
            case_path, ROOT / "evaluation/technical_corpus", cases, chunks
        )
        scope["maximum_embedding_requests"] = min(
            scope["maximum_embedding_requests"], limit
        )
        validate_seed(
            scope,
            seed_scope,
            sorted((ROOT / "evaluation/technical_corpus").glob("*.md")),
        )
        seed = select_seed(vectors, corpus_texts)
        if len(seed) != len(corpus_texts):
            raise ValueError("Seed does not cover all frozen corpus chunks")
        if name == "primary-40":
            missing = {pipeline.normalize_text(c.question) for c in cases} - set(seed)
            if math.ceil(len(missing) / 10) > 4:
                raise ValueError("New vector budget insufficient")
            output = bundle / name
            output.mkdir(exist_ok=True)
            cache = output / "vectors.json"
            if not cache.exists():
                write(cache, seed)
        scope_path = bundle / (name + "-scope.json")
        write(scope_path, scope)
        runs.append(
            {
                "name": name,
                "dataset": str(case_path),
                "scope_file": str(scope_path),
                "scope": scope,
                "output": str(bundle / name),
                "embedding_limit": limit,
            }
        )
    manifest = {
        "kind": "career-frozen-question-bundle-v7",
        "unique_questions": 40,
        "positive": 24,
        "negative": 16,
        "planned_trials": 56,
        "repeat_selected_questions": 8,
        "repeat_count_per_selected_question": 3,
        "maximum_chat_requests": 224,
        "maximum_embedding_requests": 4,
        "dataset_sha256": sha(dataset),
        "protocol_sha256": sha(protocol_path),
        "runner_sha256": sha(__file__),
        "seed_vector_sha256": sha(args.seed_vectors),
        "seed_scope_sha256": sha(args.seed_scope),
        "seed_embedding": seed_scope["embedding"],
        "all_chat_stages_fresh_across_repeat_runs": True,
        "reuse_only_embedding_vectors": True,
        "repeat_ids": protocol["repeated_case_ids"],
        "runs": runs,
        "labels_sent_to_model": False,
        "independent_external_human_labels": False,
    }
    frozen = bundle / "bundle-scope.json"
    if frozen.exists() and read(frozen) != manifest:
        raise ValueError("Cannot replace existing bundle with changed scope")
    write(frozen, manifest)
    return manifest


def live(args):
    manifest = read(args.scope_manifest)
    bundle = args.bundle_dir.resolve()
    if manifest["runner_sha256"] != sha(__file__):
        raise ValueError("Runner changed after scope freeze")
    if manifest["dataset_sha256"] != sha(
        ROOT / "evaluation/answer_frozen_v7_cases.json"
    ) or manifest["protocol_sha256"] != sha(
        ROOT / "evaluation/answer_frozen_v7_protocol.json"
    ):
        raise ValueError("Task set changed after scope freeze")
    docs = pipeline.load_knowledge_documents(ROOT / "evaluation/technical_corpus")
    chunks = [
        c
        for d in docs
        for c in pipeline.chunk_document(
            d, max_characters=pipeline.DEFAULT_RAG_CONFIG["max_characters"]
        )
    ]
    reports = []
    for run in manifest["runs"]:
        cases = pipeline.load_cases(Path(run["dataset"]), docs)
        actual = pipeline.prepare_scope(
            Path(run["dataset"]), ROOT / "evaluation/technical_corpus", cases, chunks
        )
        actual["maximum_embedding_requests"] = min(
            actual["maximum_embedding_requests"], run["embedding_limit"]
        )
        if actual != run["scope"] or read(run["scope_file"]) != actual:
            raise ValueError("Run source/model/input changed after freeze")
        output = Path(run["output"])
        output.mkdir(exist_ok=True)
        if output.parent != bundle:
            raise ValueError("Unexpected checkpoint directory")
        if run["name"] != "primary-40":
            primary_vectors = read(bundle / "primary-40/vectors.json")
            required = list(
                dict.fromkeys(
                    [
                        *(pipeline.normalize_text(c.content) for c in chunks),
                        *(pipeline.normalize_text(c.question) for c in cases),
                    ]
                )
            )
            seed = select_seed(primary_vectors, required)
            if len(seed) != len(required):
                raise ValueError(
                    "Repeat query vectors unavailable; no extra vector request permitted"
                )
            if not (output / "vectors.json").exists():
                write(output / "vectors.json", seed)
        command = [
            sys.executable,
            str(ROOT / "scripts/evaluate_answer_pipeline.py"),
            "--dataset",
            run["dataset"],
            "--knowledge-dir",
            str(ROOT / "evaluation/technical_corpus"),
            "--scope-manifest",
            run["scope_file"],
            "--allow-live-calls",
            "--output-dir",
            str(output),
            "--embedding-request-limit",
            str(run["embedding_limit"]),
        ]
        result = subprocess.run(command, cwd=str(ROOT), check=False)
        if result.returncode:
            raise RuntimeError(
                "Child run interrupted; original checkpoints and ledgers retained"
            )
        reports.append(read(output / "report.json"))
        summary = summarize(reports, manifest["repeat_ids"])
        if (
            summary["request_counts"]["chat"] > 224
            or summary["request_counts"]["embedding"] > 4
        ):
            raise RuntimeError("Bundle budget invariant violated")
        write(bundle / "summary.json", summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle-dir", type=Path, required=True)
    p.add_argument("--seed-vectors", type=Path)
    p.add_argument("--seed-scope", type=Path)
    p.add_argument("--prepare-scope", type=Path)
    p.add_argument("--scope-manifest", type=Path)
    p.add_argument("--allow-live-calls", action="store_true")
    a = p.parse_args()
    if a.prepare_scope:
        if a.seed_vectors is None or a.seed_scope is None:
            p.error("Seed vectors and their provenance scope are required")
        manifest = prepare(a)
        write(a.prepare_scope, manifest)
        print(
            json.dumps(
                {
                    "questions": 40,
                    "planned_trials": 56,
                    "maximum_chat_requests": 224,
                    "maximum_embedding_requests": 4,
                    "network_calls": 0,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if not a.allow_live_calls or a.scope_manifest is None:
        p.error("Prepare-only or explicit live mode with frozen scope required")
    print(json.dumps(live(a), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
