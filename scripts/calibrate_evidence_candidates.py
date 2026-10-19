"""Validate one development-selected candidate configuration within an approved budget."""

import argparse
import hashlib
import json
import runpy
from pathlib import Path
from urllib.parse import urlsplit

from openai import OpenAI

from career_pilot.llm import EVIDENCE_SYSTEM_PROMPT, LLMClient, load_llm_settings
from career_pilot.rag.benchmark import evaluate_snapshot, load_benchmark_cases
from career_pilot.rag.documents import chunk_document, load_knowledge_documents
from career_pilot.rag.evidence import EvidenceGate

ROOT = Path(__file__).resolve().parents[1]


def sha(value):
    return hashlib.sha256(value).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


class RecordedEmbedder:
    def __init__(self, values):
        self.values = values

    def embed_texts(self, texts):
        return [self.values[text] for text in texts]

    def embed_query(self, query):
        return self.values[query]


class BudgetedJudge:
    def __init__(self, client, cache, model, directory, original_count, limit):
        self.client, self.values, self.model = client, cache, model
        self.directory = directory
        self.original_count, self.limit = original_count, limit
        ledger = directory / "request-ledger.json"
        self.new_requests = (
            json.loads(ledger.read_text("utf-8"))["new_requests"]
            if ledger.exists()
            else 0
        )
        self.prompt_hash = sha(EVIDENCE_SYSTEM_PROMPT.encode("utf-8"))
        self.cache_hits = 0

    def assess_evidence(self, question, passages):
        key = sha(
            json.dumps(
                [self.model, self.prompt_hash, question, passages],
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        )
        if key in self.values:
            self.cache_hits += 1
            return self.values[key]
        if (
            self.new_requests >= 60
            or self.original_count + self.new_requests >= self.limit
        ):
            raise RuntimeError("Approved request budget exhausted")
        # Count before transmission, including timeouts or provider failures.
        self.new_requests += 1
        save(
            self.directory / "request-ledger.json",
            {
                "original_requests": self.original_count,
                "new_requests": self.new_requests,
                "total_requests": self.original_count + self.new_requests,
                "maximum_total": self.limit,
            },
        )
        value = self.client.assess_evidence(question, passages)
        self.values[key] = value
        save(self.directory / "judge-cache.json", self.values)
        return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-dir", type=Path, required=True)
    p.add_argument("--selection", type=Path, required=True)
    p.add_argument("--scope-manifest", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--prior-run-dir", type=Path)
    p.add_argument("--split", choices=["all", "dev", "test"], default="all")
    p.add_argument("--allow-live-calls", action="store_true")
    args = p.parse_args()
    if not args.allow_live_calls:
        p.error("需要显式允许在同一批准总预算内调用核验模型")
    original_path = args.original_dir / "report.json"
    original = json.loads(original_path.read_text("utf-8"))
    scope = json.loads(args.scope_manifest.read_text(encoding="utf-8-sig"))
    if original["scope"] != {k: scope[k] for k in original["scope"]}:
        p.error("原始评测与批准范围不一致")
    dataset = Path(scope["dataset"]["path"])
    if sha(dataset.read_bytes()) != scope["dataset"]["sha256"]:
        p.error("题集发生变化")
    paths = {Path(d["path"]) for d in scope["documents"]}
    directory = next(iter(paths)).parent
    if set(directory.glob("*.md")) != paths:
        p.error("知识范围发生变化")
    for item in scope["documents"]:
        if sha(Path(item["path"]).read_bytes()) != item["sha256"]:
            p.error("知识内容发生变化")
    selected = json.loads(args.selection.read_text("utf-8"))
    options = original["dev_experiments"]["hybrid_reranked"]

    def key(option):
        m, c = option["metrics"], option["configuration"]
        return (
            m["evidence_coverage_at_k"],
            m["evidence_mrr_at_k"],
            m["unanswerable_empty_rate"],
            -c["top_k"],
            -c["max_characters"],
            c["min_score"],
        )

    config = max(options, key=key)["configuration"]
    if (
        selected["configuration"] != config
        or selected["test_metrics_inspected_for_selection"]
    ):
        p.error("配置必须仅由开发指标选择")
    base_judge_requests = original["new_judge_requests"]
    prior_cache = args.original_dir / "judge-cache.json"
    if args.prior_run_dir:
        prior = json.loads((args.prior_run_dir / "report.json").read_text("utf-8"))
        if prior["provenance"]["scope_manifest_sha256"] != sha(
            args.scope_manifest.read_bytes()
        ):
            p.error("先前调用不属于本次批准范围")
        base_judge_requests = prior["total_judge_requests_in_authorized_scope"]
        prior_cache = args.prior_run_dir / "judge-cache.json"
    if not 0 <= base_judge_requests <= scope["maximum_judge_requests"]:
        p.error("先前请求数量超出批准范围")
    settings = load_llm_settings(ROOT / ".env")
    if scope["judge"] != {
        "provider_host": urlsplit(settings.base_url).hostname,
        "model": settings.model,
    }:
        p.error("核验模型发生变化")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    provenance = {
        "selection": selected,
        "evaluation_split": args.split,
        "prior_judge_requests": base_judge_requests,
        "prompt_sha256": sha(EVIDENCE_SYSTEM_PROMPT.encode("utf-8")),
        "dataset_sha256": scope["dataset"]["sha256"],
        "original_report_sha256": sha(original_path.read_bytes()),
        "evidence_validator_sha256": sha(
            (ROOT / "src/career_pilot/rag/evidence.py").read_bytes()
        ),
        "script_sha256": sha(Path(__file__).read_bytes()),
        "new_embedding_requests": 0,
        "maximum_total_judge_requests": scope["maximum_judge_requests"],
        "scope_manifest_sha256": sha(args.scope_manifest.read_bytes()),
    }
    frozen = args.output_dir / "frozen-provenance.json"
    if frozen.exists() and json.loads(frozen.read_text("utf-8")) != provenance:
        p.error("恢复运行时实现与输入必须一致")
    save(frozen, provenance)
    cache_path = args.output_dir / "judge-cache.json"
    cache = json.loads(
        (cache_path if cache_path.exists() else prior_cache).read_text("utf-8")
    )
    client = OpenAI(
        api_key=settings.api_key.get_secret_value(),
        base_url=settings.base_url,
        timeout=30,
        max_retries=0,
    )
    judge = BudgetedJudge(
        LLMClient(settings, client=client),
        cache,
        settings.model,
        args.output_dir,
        base_judge_requests,
        scope["maximum_judge_requests"],
    )
    gate = EvidenceGate(judge)
    embedder = RecordedEmbedder(
        json.loads((args.original_dir / "embedding-cache.json").read_text("utf-8"))
    )
    documents = load_knowledge_documents(directory)
    chunks = [
        c
        for d in documents
        for c in chunk_document(d, max_characters=config["max_characters"])
    ]
    base = runpy.run_path(str(ROOT / "scripts/benchmark_retrieval.py"))
    retriever = base["build_retrievers"](chunks, mode="compare", embedder=embedder)[
        "hybrid_reranked"
    ]
    cases = load_benchmark_cases(dataset)
    result = {"configuration": config}
    for split in ("dev", "test") if args.split == "all" else (args.split,):
        group = [c for c in cases if c.split == split]
        raw, guarded, decisions = {}, {}, {}
        for i, case in enumerate(group, 1):
            hits = retriever.search(case.question, top_k=3)
            raw[case.case_id] = hits
            retained = [
                h for h in hits[: config["top_k"]] if h.score >= config["min_score"]
            ]
            decision = gate.evaluate(case.question, retained)
            decisions[case.case_id] = decision.model_dump()
            save(args.output_dir / f"decisions-{split}.json", decisions)
            if decision.status == "unavailable":
                raise RuntimeError("Evidence service unavailable; stopped")
            accepted = set(decision.retained_chunk_ids)
            guarded[case.case_id] = [
                h for h in retained if h.chunk.chunk_id in accepted
            ]
            print(f"candidate-recall/{split}: {i}/{len(group)}", flush=True)
        result[split + "_metrics"] = evaluate_snapshot(
            group, raw, top_k=config["top_k"], min_score=config["min_score"]
        )
        result[split + "_gated_metrics"] = evaluate_snapshot(
            group, guarded, top_k=config["top_k"], min_score=0
        )
        result[split + "_gate_decisions"] = decisions
        result[split + "_gate_errors"] = sum(
            d["status"] in ("invalid", "unavailable") for d in decisions.values()
        )
    report = {
        "evaluation_scope": "retrieval_and_evidence_sufficiency_only",
        "variant": "candidate_recall_then_evidence_gate",
        "document_count": len(documents),
        "case_count": len(cases)
        if args.split == "all"
        else sum(c.split == args.split for c in cases),
        "dataset_total_cases": len(cases),
        "dev_count": 30 if args.split in ("all", "dev") else 0,
        "test_count": 30 if args.split in ("all", "test") else 0,
        "mode": "compare",
        "gate": "model",
        "generation_calls": False,
        "live_embedding_calls": False,
        "cached_real_embeddings": True,
        "live_judge_calls": True,
        "provenance": provenance,
        "selected_by_mode": {"hybrid_reranked": result},
        "new_embedding_requests": 0,
        "new_judge_requests": judge.new_requests,
        "reused_judge_responses": judge.cache_hits,
        "total_judge_requests_in_authorized_scope": base_judge_requests
        + judge.new_requests,
        "total_embedding_requests_in_authorized_scope": original[
            "new_embedding_requests"
        ],
        "sdk_automatic_retries": 0,
    }
    save(args.output_dir / "report.json", report)
    formatter = runpy.run_path(str(ROOT / "scripts/benchmark_evidence.py"))
    (args.output_dir / "summary.md").write_text(
        "# 先保留候选证据、再判断可回答性\n\n"
        "候选配置仅用开发指标冻结；复用已缓存真实向量。\n\n"
        + formatter["markdown_summary"](report),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "new_judge_requests": judge.new_requests,
                "total_judge_requests": base_judge_requests
                + judge.new_requests,
                "total_embedding_requests": original["new_embedding_requests"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f"评测未完成：{type(error).__name__}；检查点已保留。")
        raise SystemExit(1) from None
