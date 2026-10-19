"""Replay a completed real run with local quote validation; network is forbidden."""

import argparse
import copy
import hashlib
import json
import runpy
from pathlib import Path

from career_pilot.llm import EVIDENCE_SYSTEM_PROMPT
from career_pilot.rag.benchmark import evaluate_snapshot, load_benchmark_cases
from career_pilot.rag.documents import chunk_document, load_knowledge_documents
from career_pilot.rag.evidence import EvidenceGate
from career_pilot.rag.models import SearchHit

ROOT = Path(__file__).resolve().parents[1]


def sha(value):
    return hashlib.sha256(value).hexdigest()


class RecordedJudge:
    def __init__(self, cache, model):
        self.cache, self.model = cache, model
        self.prompt_hash = sha(EVIDENCE_SYSTEM_PROMPT.encode("utf-8"))
        self.reused = 0

    def assess_evidence(self, question, passages):
        key = sha(
            json.dumps(
                [self.model, self.prompt_hash, question, passages],
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        )
        # A miss raises KeyError, never calls a provider or silently abstains.
        value = self.cache[key]
        self.reused += 1
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--judge-cache", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    original = json.loads(args.report.read_text("utf-8"))
    scope = original["scope"]
    if scope["mode"] != "compare" or scope["gate"] != "model":
        parser.error("需要真实向量与核验对照报告")
    dataset = Path(scope["dataset"]["path"])
    if sha(dataset.read_bytes()) != scope["dataset"]["sha256"]:
        parser.error("题集指纹发生变化")
    for item in scope["documents"]:
        if sha(Path(item["path"]).read_bytes()) != item["sha256"]:
            parser.error("知识文档指纹发生变化")
    judge = RecordedJudge(
        json.loads(args.judge_cache.read_text("utf-8")), scope["judge"]["model"]
    )
    gate = EvidenceGate(judge)
    cases = load_benchmark_cases(dataset)
    documents = load_knowledge_documents(Path(scope["documents"][0]["path"]).parent)
    report = copy.deepcopy(original)
    report["model_output_origin"] = "previous_real_run_reused_offline"
    report["original_live_report_sha256"] = sha(args.report.read_bytes())
    report["original_live_request_counts"] = {
        key: original[key]
        for key in (
            "new_embedding_requests",
            "new_embedded_texts",
            "new_judge_requests",
        )
    }
    report["new_embedding_requests"] = report["new_judge_requests"] = 0
    report["new_embedded_texts"] = 0
    report["offline_replay_source_sha256"] = {
        "evidence.py": sha((ROOT / "src/career_pilot/rag/evidence.py").read_bytes()),
        "replay_evidence.py": sha(Path(__file__).read_bytes()),
    }
    for selection in report["selected_by_mode"].values():
        chunks = {
            c.chunk_id: c
            for d in documents
            for c in chunk_document(
                d, max_characters=selection["configuration"]["max_characters"]
            )
        }
        for split in ("dev", "test"):
            group = [c for c in cases if c.split == split]
            raw = selection[split + "_metrics"]
            by_id = {r["case_id"]: r for r in raw["results"]}
            guarded, decisions = {}, {}
            for case in group:
                hits = [
                    SearchHit(chunk=chunks[h["chunk_id"]], score=h["score"])
                    for h in by_id[case.case_id]["retrieved"]
                ]
                decision = gate.evaluate(case.question, hits)
                allowed = set(decision.retained_chunk_ids)
                guarded[case.case_id] = (
                    [h for h in hits if h.chunk.chunk_id in allowed]
                    if decision.status == "supported"
                    else []
                )
                decisions[case.case_id] = decision.model_dump()
            old = selection[split + "_gated_metrics"]
            selection[split + "_original_validator_metrics"] = {
                k: v for k, v in old.items() if k != "results"
            }
            selection[split + "_gated_metrics"] = evaluate_snapshot(
                group,
                guarded,
                top_k=selection["configuration"]["top_k"],
                min_score=0,
            )
            selection[split + "_gate_decisions"] = decisions
            selection[split + "_gate_errors"] = sum(
                d["status"] in ("invalid", "unavailable") for d in decisions.values()
            )
    report["cached_verdicts_reused"] = judge.reused
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    base = runpy.run_path(str(ROOT / "scripts/benchmark_evidence.py"))
    (args.output_dir / "summary.md").write_text(
        "# 本地数值校验修正后的离线重放\n\n"
        "复用同一批真实模型输出；新增接口请求为零。\n\n"
        + base["markdown_summary"](report),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "network_calls": 0,
                "cached_verdicts_reused": judge.reused,
                "output": str(args.output_dir),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    # Deny even accidental networking during replay.
    import socket

    def deny_network(*args, **kwargs):
        raise AssertionError("Offline replay cannot access the network")

    previous_connect = socket.socket.connect
    socket.socket.connect = deny_network
    try:
        main()
    finally:
        socket.socket.connect = previous_connect
