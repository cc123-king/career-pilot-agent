"""Run the offline keyword-retrieval baseline against a labeled dataset."""

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

from career_pilot.rag.documents import chunk_document, load_knowledge_documents
from career_pilot.rag.evaluation import evaluate_retrieval, load_evaluation_cases
from career_pilot.rag.retrieval import KeywordRetriever

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "retrieval_cases.json",
    )
    parser.add_argument(
        "--knowledge-dir", type=Path, default=PROJECT_ROOT / "knowledge"
    )
    parser.add_argument("--top-k", type=int, default=1)
    parser.add_argument("--min-score", type=float, default=0.05)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "retrieval-evaluation.json",
    )
    arguments = parser.parse_args()
    if arguments.top_k < 1 or not 0 <= arguments.min_score <= 1:
        parser.error("top-k must be >= 1; min-score must be between 0 and 1")

    try:
        cases = load_evaluation_cases(arguments.dataset)
        documents = load_knowledge_documents(arguments.knowledge_dir)
        chunks = [chunk for document in documents for chunk in chunk_document(document)]
        expected = {source for case in cases for source in case.expected_sources}
        unknown_sources = expected - {chunk.source for chunk in chunks}
        if unknown_sources:
            raise ValueError(
                f"标准来源不在知识库中：{', '.join(sorted(unknown_sources))}"
            )
        report = evaluate_retrieval(
            cases,
            KeywordRetriever(chunks),
            top_k=arguments.top_k,
            min_score=arguments.min_score,
        )
        payload = {
            "evaluation_scope": "retrieval_only",
            "retriever": "keyword",
            "dataset": str(arguments.dataset.resolve()),
            "dataset_sha256": sha256(arguments.dataset.read_bytes()).hexdigest(),
            "knowledge_directory": str(arguments.knowledge_dir.resolve()),
            "knowledge_sha256": {
                document.source: sha256(document.content.encode("utf-8")).hexdigest()
                for document in documents
            },
            "document_count": len(documents),
            "chunk_count": len(chunks),
            **report.model_dump(),
        }
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(
        f"评测问题：{report.case_count}，可回答：{report.answerable_count}，无答案：{report.unanswerable_count}"
    )
    for label, value, format_spec in (
        (f"来源召回率 Recall@{report.top_k}", report.source_recall_at_k, ".2%"),
        (f"平均倒数排名 MRR@{report.top_k}", report.mrr_at_k, ".3f"),
        ("无答案问题空检索率", report.unanswerable_empty_rate, ".2%"),
    ):
        print(
            f"{label}：{value:{format_spec}}" if value is not None else f"{label}：N/A"
        )
    for result in report.results:
        if result.source_recall != 1.0 and result.unanswerable_empty is not True:
            found = ", ".join(item.source for item in result.retrieved) or "无"
            print(f"待检查 {result.case_id}：{result.question} | 返回来源：{found}")
    print(f"报告：{arguments.output.resolve()}")
    print("仅评估检索；不代表生成答案准确率或大模型拒答率。")


if __name__ == "__main__":
    main()
