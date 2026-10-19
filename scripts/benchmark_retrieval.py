"""Compare retrieval configurations without changing the running application."""

import argparse
import json
import sys
from hashlib import sha256
from itertools import product
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from openai import OpenAIError

from career_pilot.rag.benchmark import (
    evaluate_snapshot,
    load_benchmark_cases,
    select_development_configuration,
    validate_benchmark_labels,
)
from career_pilot.rag.documents import chunk_document, load_knowledge_documents
from career_pilot.rag.retrieval import KeywordRetriever

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_retrievers(chunks, *, mode: str, embedder=None) -> dict:
    retrievers = {"keyword": KeywordRetriever(chunks)}
    if mode == "keyword":
        return retrievers
    from career_pilot.rag.hybrid_retrieval import (
        HybridCandidateRetriever,
        HybridRetriever,
    )
    from career_pilot.rag.reranking import ScoreFusionReranker
    from career_pilot.rag.vector_index import InMemoryVectorIndex

    index = InMemoryVectorIndex(chunks, embedder)
    candidates = HybridCandidateRetriever(chunks, index, candidate_k=6)
    retrievers.update(
        vector=index,
        hybrid_rrf=HybridRetriever(candidates, rank_constant=60),
        hybrid_reranked=HybridRetriever(
            candidates, reranker=ScoreFusionReranker(), rank_constant=60
        ),
    )
    return retrievers


class CachedEmbedder:
    """Reuse text/query embeddings across ablations without storing credentials."""

    def __init__(self, client):
        self.client = client
        self.cache = {}

    def embed_texts(self, texts):
        missing = list(dict.fromkeys(text for text in texts if text not in self.cache))
        if missing:
            vectors = self.client.embed_texts(missing)
            self.cache.update(zip(missing, vectors, strict=True))
        return [self.cache[text] for text in texts]

    def embed_query(self, query):
        return self.embed_texts([query])[0]


def compact_metrics(metrics):
    return {key: value for key, value in metrics.items() if key != "results"}


def format_percent(value):
    return "N/A" if value is None else f"{value:.1%}"


def markdown_summary(payload):
    lines = [
        "# CareerPilot 检索评测报告",
        "",
        f"问题 {payload['case_count']} 道，开发组 {payload['dev_count']} 道，测试组 {payload['test_count']} 道。",
        f"知识文档 {payload['document_count']} 份；模式：{payload['mode']}。",
        "",
        "每种模式只使用开发组选择切片长度、top-k 和阈值，随后评估一次测试组。",
        "证据覆盖率要求返回片段包含标注的原文锚点；返回正确文件但错误片段不算证据命中。",
        "",
        "| 模式 | 分块长度 | k | 阈值 | 测试来源 Recall | 测试证据覆盖率 | 测试证据 MRR | 无答案空检索率 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for mode, selection in payload["selected_by_mode"].items():
        options = selection["configuration"]
        metrics = selection["test_metrics"]
        lines.append(
            f"| {mode} | {options['max_characters']} | {options['top_k']} | "
            f"{options['min_score']:.2f} | {format_percent(metrics['source_recall_at_k'])} | "
            f"{format_percent(metrics['evidence_coverage_at_k'])} | "
            f"{metrics['evidence_mrr_at_k']:.3f} | "
            f"{format_percent(metrics['unanswerable_empty_rate'])} |"
        )
    for mode, selection in payload["selected_by_mode"].items():
        metrics = selection["test_metrics"]
        lines.extend(["", f"## {mode} 测试组需检查的题目", ""])
        misses = [
            row
            for row in metrics["results"]
            if (row["evidence_coverage"] is not None and row["evidence_coverage"] < 1)
            or row["unanswerable_empty"] is False
        ]
        if not misses:
            lines.append("本组没有上述类型的错误；不代表真实业务没有错误。")
        for row in misses:
            lines.append(f"- {row['case_id']}：{row['question']}")
    lines.extend(
        [
            "",
            "## 范围与限制",
            "",
            "- 这是同一作者根据两份求职指南编写的小型开发/测试分组，不是外部独立业务测试集。",
            "- 当前不评估生成回答的事实正确性、引用正确性或模型拒答率。",
            "- 原文锚点是透明的自动检查规则，不能替代人工语义审阅。",
            "- 空检索率只是检索过滤行为；高阈值可能同时丢掉正确资料。",
            "- 切片配置与阈值实验不会改动网页实际参数；分数不是正确概率。",
            "- 计时仅为本次检索快照的耗时，不包含索引构建或回答生成；模型模式会复用向量缓存，不用于宣称端到端延迟。",
            "- mode=keyword 完全离线；compare 需要显式允许真实 Embedding 调用，可能计费。",
            "- 真实向量模式使用配置的 Embedding 接口，不等于已使用 BGE；重排序是分数融合，不是 Cross-Encoder。",
            "",
            "详细逐题片段、参数、知识指纹和开发组实验见 report.json。",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    for stream in (sys.stdout, sys.stderr):
        if getattr(stream, "reconfigure", None):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=PROJECT_ROOT / "evaluation/benchmark_cases.json"
    )
    parser.add_argument(
        "--knowledge-dir", type=Path, default=PROJECT_ROOT / "knowledge"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "data/reports"
    )
    parser.add_argument("--mode", choices=["keyword", "compare"], default="keyword")
    parser.add_argument("--allow-live-calls", action="store_true")
    arguments = parser.parse_args()
    if arguments.mode == "compare" and not arguments.allow_live_calls:
        parser.error(
            "compare 会调用真实 Embedding 服务，可能计费；需要 --allow-live-calls"
        )
    try:
        cases = load_benchmark_cases(arguments.dataset)
        documents = load_knowledge_documents(arguments.knowledge_dir)
        validate_benchmark_labels(cases, documents)
        dev_cases = [case for case in cases if case.split == "dev"]
        test_cases = [case for case in cases if case.split == "test"]
        embedder = None
        embedding_model = None
        if arguments.mode == "compare":
            from career_pilot.rag.embeddings import (
                EmbeddingClient,
                load_embedding_settings,
            )

            settings = load_embedding_settings(PROJECT_ROOT / ".env")
            embedding_model = settings.model
            embedder = CachedEmbedder(EmbeddingClient(settings))

        experiments = {}
        snapshots_by_size = {}
        elapsed_by_size = {}
        for size in (100, 250, 500):
            chunks = [
                chunk
                for document in documents
                for chunk in chunk_document(document, max_characters=size)
            ]
            retrievers = build_retrievers(
                chunks, mode=arguments.mode, embedder=embedder
            )
            for name, retriever in retrievers.items():
                snapshots = {}
                elapsed = {}
                # Query the development group only until its parameters are frozen.
                for case in dev_cases:
                    started = perf_counter()
                    snapshots[case.case_id] = retriever.search(case.question, top_k=3)
                    elapsed[case.case_id] = (perf_counter() - started) * 1000
                snapshots_by_size[(size, name)] = (retriever, snapshots)
                elapsed_by_size[(size, name)] = elapsed
                for k, threshold in product((1, 3), (0.05, 0.20, 0.35)):
                    metrics = evaluate_snapshot(
                        dev_cases,
                        snapshots,
                        top_k=k,
                        min_score=threshold,
                        elapsed_ms=elapsed,
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
                            "metrics": compact_metrics(metrics),
                        }
                    )
        selected = {}
        for name, options in experiments.items():
            best = select_development_configuration(options)
            config = best["configuration"]
            retriever, snapshots = snapshots_by_size[(config["max_characters"], name)]
            elapsed = elapsed_by_size[(config["max_characters"], name)]
            for case in test_cases:
                started = perf_counter()
                snapshots[case.case_id] = retriever.search(case.question, top_k=3)
                elapsed[case.case_id] = (perf_counter() - started) * 1000
            selected[name] = {
                "configuration": config,
                "dev_metrics": evaluate_snapshot(
                    dev_cases,
                    snapshots,
                    top_k=config["top_k"],
                    min_score=config["min_score"],
                    elapsed_ms=elapsed,
                ),
                "test_metrics": evaluate_snapshot(
                    test_cases,
                    snapshots,
                    top_k=config["top_k"],
                    min_score=config["min_score"],
                    elapsed_ms=elapsed,
                ),
            }
        payload = {
            "evaluation_scope": "retrieval_evidence_only",
            "mode": arguments.mode,
            "live_embedding_calls": arguments.mode == "compare",
            "generation_calls": False,
            "embedding_model": embedding_model,
            "case_count": len(cases),
            "dev_count": len(dev_cases),
            "test_count": len(test_cases),
            "document_count": len(documents),
            "dataset_sha256": sha256(arguments.dataset.read_bytes()).hexdigest(),
            "knowledge_sha256": {
                doc.source: sha256(doc.content.encode("utf-8")).hexdigest()
                for doc in documents
            },
            "selection_rule": "dev: maximize (evidence_coverage + unanswerable_empty_rate)/2; ties: coverage, empty rate, smaller k, smaller chunk, smaller threshold",
            "dev_experiments": experiments,
            "selected_by_mode": selected,
        }
        directory = arguments.output_dir.resolve() / f"benchmark-{uuid4().hex}"
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "report.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (directory / "summary.md").write_text(
            markdown_summary(payload), encoding="utf-8"
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    except (RuntimeError, OpenAIError) as error:
        # Do not echo a provider response or configuration containing secrets.
        print(
            f"评测未完成（{type(error).__name__}）；请检查本地配置和服务状态。",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print(f"问题：{len(cases)}；开发组：{len(dev_cases)}；测试组：{len(test_cases)}")
    for name, result in selected.items():
        metrics = result["test_metrics"]
        print(
            f"{name} | {result['configuration']} | 来源Recall={format_percent(metrics['source_recall_at_k'])} | 证据覆盖={format_percent(metrics['evidence_coverage_at_k'])} | 无答案空检索={format_percent(metrics['unanswerable_empty_rate'])}"
        )
    print(f"报告目录：{directory}")
    print("仅为小型检索评测，不是回答准确率或真实业务效果。")


if __name__ == "__main__":
    main()
