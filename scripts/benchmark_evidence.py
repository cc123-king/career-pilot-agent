"""Evaluate raw retrieval and evidence gating on a fixed, larger corpus.

Offline by default. Every live run requires explicit opt-in and a matching scope
manifest. Cache checkpoints support resuming without repeating completed calls.
"""

import argparse
import hashlib
import json
import runpy
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

from openai import OpenAI, OpenAIError

from career_pilot.llm import EVIDENCE_SYSTEM_PROMPT, LLMClient, load_llm_settings
from career_pilot.rag.benchmark import (
    evaluate_snapshot,
    load_benchmark_cases,
    select_development_configuration,
    validate_benchmark_labels,
)
from career_pilot.rag.documents import chunk_document, load_knowledge_documents
from career_pilot.rag.embeddings import EmbeddingClient, load_embedding_settings
from career_pilot.rag.evidence import EvidenceGate

ROOT = Path(__file__).resolve().parents[1]
CHUNK_SIZES = (100, 200, 300)
THRESHOLDS = {
    "keyword": (0.20, 0.35, 0.50),
    "vector": (0.25, 0.40, 0.55, 0.70),
    "hybrid_rrf": (0.50, 0.75, 0.90),
    "hybrid_reranked": (0.50, 0.75, 0.90),
}


def fingerprint(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def source_fingerprints():
    paths = [
        "scripts/benchmark_evidence.py",
        "scripts/benchmark_retrieval.py",
        "src/career_pilot/rag/evidence.py",
        "src/career_pilot/rag/benchmark.py",
        "src/career_pilot/rag/embeddings.py",
        "src/career_pilot/rag/context.py",
        "src/career_pilot/rag/documents.py",
        "src/career_pilot/rag/retrieval.py",
        "src/career_pilot/rag/vector_index.py",
        "src/career_pilot/rag/hybrid_retrieval.py",
        "src/career_pilot/rag/rrf.py",
        "src/career_pilot/rag/reranking.py",
        "src/career_pilot/llm.py",
    ]
    return {p: fingerprint((ROOT / p).read_bytes()) for p in paths}


class CachedEmbedder:
    def __init__(self, client, path):
        self.client, self.path = client, path
        self.values = json.loads(path.read_text("utf-8")) if path.exists() else {}
        self.calls = 0
        self.new_texts = 0

    def embed_texts(self, texts):
        missing = list(dict.fromkeys(t for t in texts if t not in self.values))
        if missing:
            vectors = self.client.embed_texts(missing)
            self.calls = self.client.request_count
            self.new_texts += len(missing)
            self.values.update(zip(missing, vectors, strict=True))
            write_json(self.path, self.values)
        return [self.values[t] for t in texts]

    def embed_query(self, text):
        return self.embed_texts([text])[0]


class CachedJudge:
    def __init__(self, client, path, model):
        self.client, self.path, self.model = client, path, model
        self.values = json.loads(path.read_text("utf-8")) if path.exists() else {}
        self.calls = 0
        self.prompt_hash = fingerprint(EVIDENCE_SYSTEM_PROMPT.encode("utf-8"))

    def assess_evidence(self, question, passages):
        key = fingerprint(
            json.dumps(
                [self.model, self.prompt_hash, question, passages],
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        )
        if key not in self.values:
            self.calls += 1
            value = self.client.assess_evidence(question, passages)
            self.values[key] = value
            write_json(self.path, self.values)
        return self.values[key]


def scope_for(dataset, documents, mode, gate_mode):
    value = {
        "dataset": {
            "path": str(dataset.resolve()),
            "sha256": fingerprint(dataset.read_bytes()),
        },
        "documents": [
            {"path": str(p.resolve()), "sha256": fingerprint(p.read_bytes())}
            for p in sorted(documents.glob("*.md"))
        ],
        "mode": mode,
        "gate": gate_mode,
        "source_sha256": source_fingerprints(),
        "chunk_sizes": list(CHUNK_SIZES),
        "thresholds": {k: list(v) for k, v in THRESHOLDS.items()},
        "top_k": [1, 3],
    }
    if mode == "compare":
        settings = load_embedding_settings(ROOT / ".env")
        value["embedding"] = {
            "provider_host": urlsplit(settings.base_url).hostname,
            "model": settings.model,
        }
    if gate_mode == "model":
        settings = load_llm_settings(ROOT / ".env")
        value["judge"] = {
            "provider_host": urlsplit(settings.base_url).hostname,
            "model": settings.model,
        }
    return value


def markdown_summary(report):
    lines = [
        "# 扩展检索与证据核验评测",
        "",
        f"文档 {report['document_count']} 份；开发题 {report['dev_count']}；测试题 {report['test_count']}。",
        "各模式检索参数只使用开发组选择；核验提示修订与回归口径见运行记录。",
        "",
        "| 模式 | 分块数 / top-k | 阈值 | 测试原始证据覆盖 | 原始无答案空检索 | 核验后证据覆盖 | 核验后无答案空检索 | 核验异常数 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, item in report["selected_by_mode"].items():
        c, raw = item["configuration"], item["test_metrics"]
        guarded = item.get("test_gated_metrics")
        fmt = lambda value: f"{value:.1%}" if value is not None else "N/A"
        lines.append(
            f"| {name} | {c['chunk_count']} / {c['top_k']} | {c['min_score']:.2f} | "
            f"{fmt(raw['evidence_coverage_at_k'])} | {fmt(raw['unanswerable_empty_rate'])} | "
            f"{fmt(guarded['evidence_coverage_at_k']) if guarded else '未运行'} | "
            f"{fmt(guarded['unanswerable_empty_rate']) if guarded else '未运行'} | "
            f"{item.get('test_gate_errors', '未运行')} |"
        )
    lines += [
        "",
        "## 解释边界",
        "",
        "- 数据由同一作者编写，固定分组不等于外部独立数据；虚构契约不表示个人项目事实。",
        "- 不同知识库上的新旧分数不能作为同条件提升；看本轮相同输入上的原始/核验后对照。",
        "- 纯排序、证据核验和最终回答生成分别记录；本脚本不生成最终回答。",
        "- 核验异常与缺少证据分别记录，不能把服务故障造成的拒绝算成模型判断正确。",
        "- 原文引用核对证明出处存在，语义充分性仍依赖模型判断。",
        "- 所有候选池必须大于 top-k，开发组选择后保存冻结配置，再运行测试组。",
        "- 缓存使计时不可作为生产端到端延迟；报告不推测费用。",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "evaluation/benchmark_v2_cases.json"
    )
    parser.add_argument("--knowledge-dir", type=Path, default=ROOT / "knowledge")
    parser.add_argument("--mode", choices=["keyword", "compare"], default="keyword")
    parser.add_argument("--gate", choices=["off", "model"], default="off")
    parser.add_argument("--allow-live-calls", action="store_true")
    parser.add_argument("--scope-manifest", type=Path)
    parser.add_argument("--prepare-scope", type=Path)
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    live = args.mode == "compare" or args.gate == "model"
    if live and not args.allow_live_calls and not args.prepare_scope:
        parser.error("真实 Embedding/核验可能计费，需要 --allow-live-calls 和范围清单")
    cases = load_benchmark_cases(args.dataset)
    documents = load_knowledge_documents(args.knowledge_dir)
    validate_benchmark_labels(cases, documents)
    scope = scope_for(args.dataset, args.knowledge_dir, args.mode, args.gate)
    if args.prepare_scope:
        scope["case_count"] = len(cases)
        scope["maximum_judge_requests"] = len(cases) * (
            4 if args.mode == "compare" else 1
        )
        scope["maximum_embedding_requests"] = (
            (
                sum(
                    (
                        sum(
                            len(chunk_document(d, max_characters=size))
                            for d in documents
                        )
                        + 9
                    )
                    // 10
                    for size in CHUNK_SIZES
                )
                + len(cases)
            )
            if args.mode == "compare"
            else 0
        )
        scope["sdk_automatic_retries"] = 0
        scope["maximum_judge_output_tokens_per_request"] = 1800
        scope["final_answer_generation"] = False
        scope["personal_resume_or_runtime_databases"] = False
        write_json(args.prepare_scope, scope)
        print(f"仅准备范围清单，无网络调用：{args.prepare_scope}")
        return
    if live:
        if args.scope_manifest is None:
            parser.error("真实评测需要与输入、实现及模型相匹配的 --scope-manifest")
        approved = json.loads(args.scope_manifest.read_text(encoding="utf-8-sig"))
        if any(approved.get(key) != value for key, value in scope.items()):
            parser.error("范围清单与当前文件或模型不一致，请重新核对")
    directory = args.run_dir or ROOT / "data/reports" / f"evidence-{uuid4().hex}"
    directory.mkdir(parents=True, exist_ok=True)
    scope_path = directory / "scope.json"
    if scope_path.exists() and json.loads(scope_path.read_text("utf-8")) != scope:
        parser.error("不能用不同输入、实现或模型复用旧评测缓存")
    write_json(scope_path, scope)
    embedding, judge = None, None
    if args.mode == "compare":
        settings = load_embedding_settings(ROOT / ".env")
        client = OpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=30,
            max_retries=0,
        )
        embedding = CachedEmbedder(
            EmbeddingClient(settings, client=client), directory / "embedding-cache.json"
        )
    if args.gate == "model":
        settings = load_llm_settings(ROOT / ".env")
        client = OpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=30,
            max_retries=0,
        )
        judge = CachedJudge(
            LLMClient(settings, client=client),
            directory / "judge-cache.json",
            settings.model,
        )
    gate = EvidenceGate(judge) if judge else None
    base = runpy.run_path(str(ROOT / "scripts/benchmark_retrieval.py"))
    dev_cases = [c for c in cases if c.split == "dev"]
    test_cases = [c for c in cases if c.split == "test"]
    experiments, retrievers_by_size = {}, {}
    started = perf_counter()
    for size in CHUNK_SIZES:
        chunks = [c for d in documents for c in chunk_document(d, max_characters=size)]
        if len(chunks) <= 3:
            parser.error("候选片段必须大于最大 top-k=3；请扩大知识库")
        for name, retriever in base["build_retrievers"](
            chunks, mode=args.mode, embedder=embedding
        ).items():
            retrievers_by_size[(size, name)] = retriever
            snapshots = {
                c.case_id: retriever.search(c.question, top_k=3) for c in dev_cases
            }
            for k in (1, 3):
                for threshold in THRESHOLDS[name]:
                    metrics = evaluate_snapshot(
                        dev_cases, snapshots, top_k=k, min_score=threshold
                    )
                    experiments.setdefault(name, []).append(
                        {
                            "split": "dev",
                            "configuration": {
                                "max_characters": size,
                                "top_k": k,
                                "min_score": threshold,
                                "chunk_count": len(chunks),
                            },
                            "metrics": {
                                k: v for k, v in metrics.items() if k != "results"
                            },
                        }
                    )
    frozen = {
        name: select_development_configuration(options)["configuration"]
        for name, options in experiments.items()
    }
    write_json(directory / "frozen-configurations.json", frozen)
    selected = {}
    # No choices below use test labels; gate prompt is already fingerprinted.
    for name, config in frozen.items():
        retriever = retrievers_by_size[(config["max_characters"], name)]
        result = {"configuration": config}
        for split, group in (("dev", dev_cases), ("test", test_cases)):
            snapshots = {
                c.case_id: retriever.search(c.question, top_k=3) for c in group
            }
            result[split + "_metrics"] = evaluate_snapshot(
                group,
                snapshots,
                top_k=config["top_k"],
                min_score=config["min_score"],
            )
            if gate:
                guarded, decisions = {}, {}
                for i, case in enumerate(group, 1):
                    retained = [
                        h
                        for h in snapshots[case.case_id][: config["top_k"]]
                        if h.score >= config["min_score"]
                    ]
                    decision = gate.evaluate(case.question, retained)
                    allowed = set(decision.retained_chunk_ids)
                    guarded[case.case_id] = (
                        [h for h in retained if h.chunk.chunk_id in allowed]
                        if decision.status == "supported"
                        else []
                    )
                    decisions[case.case_id] = decision.model_dump()
                    write_json(directory / f"decisions-{name}-{split}.json", decisions)
                    if decision.status == "unavailable":
                        raise RuntimeError(
                            "Evidence service unavailable; stopped after first failure"
                        )
                    write_json(
                        directory / "progress.json",
                        {
                            "mode": name,
                            "split": split,
                            "completed": i,
                            "total": len(group),
                            "judge_requests": judge.calls,
                        },
                    )
                    print(f"{name}/{split}: {i}/{len(group)}", flush=True)
                result[split + "_gated_metrics"] = evaluate_snapshot(
                    group,
                    guarded,
                    top_k=config["top_k"],
                    min_score=0,
                )
                result[split + "_gate_decisions"] = decisions
                result[split + "_gate_errors"] = sum(
                    d["status"] in ("invalid", "unavailable")
                    for d in decisions.values()
                )
        selected[name] = result
        write_json(directory / "partial-results.json", selected)
    report = {
        "evaluation_scope": "retrieval_and_evidence_sufficiency_only",
        "document_count": len(documents),
        "dev_count": len(dev_cases),
        "test_count": len(test_cases),
        "case_count": len(cases),
        "mode": args.mode,
        "gate": args.gate,
        "generation_calls": False,
        "live_embedding_calls": embedding is not None,
        "live_judge_calls": judge is not None,
        "scope": scope,
        "dev_experiments": experiments,
        "selected_by_mode": selected,
        "new_embedding_requests": embedding.calls if embedding else 0,
        "new_embedded_texts": embedding.new_texts if embedding else 0,
        "new_judge_requests": judge.calls if judge else 0,
        "sdk_automatic_retries": 0,
        "elapsed_seconds": round(perf_counter() - started, 3),
    }
    write_json(directory / "report.json", report)
    (directory / "summary.md").write_text(markdown_summary(report), encoding="utf-8")
    print(f"报告：{directory}")


if __name__ == "__main__":
    try:
        main()
    except (OpenAIError, OSError, ValueError, RuntimeError) as error:
        # Do not echo model responses, local environment or credential-bearing URLs.
        print(f"评测未完成：{type(error).__name__}；已保留本地检查点。")
        raise SystemExit(1) from None
