"""Real end-to-end QA evaluation with bounded requests and no label leakage."""

import argparse
import csv
import hashlib
import json
from math import ceil
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from urllib.parse import urlsplit

from openai import OpenAI, OpenAIError
from pydantic import Field, StrictBool, TypeAdapter, model_validator

from career_pilot.llm import (
    ANSWER_AUDIT_PROMPT,
    EVIDENCE_REVIEW_PROMPT,
    EVIDENCE_SYSTEM_PROMPT,
    GROUNDED_DRAFT_PROMPT,
    GROUNDED_PROPOSAL_PROMPT,
    LLMClient,
    load_llm_settings,
)
from career_pilot.models import StrictModel
from career_pilot.rag.benchmark import EvidenceLabel, canonical_text
from career_pilot.rag.documents import chunk_document, load_knowledge_documents
from career_pilot.rag.embeddings import EmbeddingClient, load_embedding_settings
from career_pilot.rag.factory import DEFAULT_RAG_CONFIG, create_grounded_rag_service
from career_pilot.text_utils import normalize_text

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {
    "evidence": EVIDENCE_SYSTEM_PROMPT,
    "review": EVIDENCE_REVIEW_PROMPT,
    "draft": GROUNDED_DRAFT_PROMPT,
    "proposal": GROUNDED_PROPOSAL_PROMPT,
    "audit": ANSWER_AUDIT_PROMPT,
}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temp.replace(path)


class AnswerCase(StrictModel):
    case_id: str
    group: str
    answerable: StrictBool
    question: str = Field(min_length=1, max_length=2000)
    evidence: list[EvidenceLabel]
    answer_checks: list[list[str]]

    @model_validator(mode="after")
    def check_labels(self):
        if self.answerable != bool(self.evidence):
            raise ValueError("可回答标签与原文锚点不一致")
        if any(not group for group in self.answer_checks):
            raise ValueError("答案检查组不能为空")
        return self


def load_cases(dataset, documents):
    cases = TypeAdapter(list[AnswerCase]).validate_json(dataset.read_text("utf-8"))
    if not cases or len({c.case_id for c in cases}) != len(cases):
        raise ValueError("题集为空或编号重复")
    if len({normalize_text(c.question) for c in cases}) != len(cases):
        raise ValueError("题目重复")
    content = {d.source: canonical_text(d.content) for d in documents}
    for case in cases:
        for label in case.evidence:
            if (
                label.source not in content
                or canonical_text(label.anchor) not in content[label.source]
            ):
                raise ValueError("标注原文不存在：" + case.case_id)
    return cases


class RequestBudget:
    def __init__(self, path, embedding_limit, chat_limit):
        self.path = path
        self.limits = {"embedding": embedding_limit, "chat": chat_limit}
        self.counts = (
            json.loads(path.read_text("utf-8"))["counts"]
            if path.exists()
            else {"embedding": 0, "chat": 0}
        )
        if any(self.counts[k] > self.limits[k] for k in self.limits):
            raise ValueError("既有请求账本超出限额")

    def consume(self, kind):
        if self.counts[kind] >= self.limits[kind]:
            raise RuntimeError("Approved request budget exhausted")
        self.counts[kind] += 1
        write_json(
            self.path,
            {
                "counts": self.counts,
                "limits": self.limits,
                "counted_before_transmission": True,
            },
        )


class RecordingCompletions:
    def __init__(self, real_client, directory, budget):
        self.real = real_client
        self.directory, self.budget = directory, budget
        self.path = directory / "model-responses.json"
        self.values = (
            json.loads(self.path.read_text("utf-8")) if self.path.exists() else {}
        )
        self.events = []

    def create(self, **request):
        prompt = request["messages"][0]["content"]
        stage = next((name for name, p in PROMPTS.items() if p == prompt), None)
        if stage is None:
            raise ValueError("未批准的模型阶段")
        key = sha(
            json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
        )
        cached = key in self.values
        transport_elapsed_ms = None
        if not cached:
            self.budget.consume("chat")
            request_started = perf_counter()
            response = self.real.chat.completions.create(**request)
            transport_elapsed_ms = (perf_counter() - request_started) * 1000
            content = response.choices[0].message.content if response.choices else None
            usage = (
                response.usage.model_dump()
                if getattr(response, "usage", None)
                else None
            )
            self.values[key] = {
                "stage": stage,
                "request": request,
                "content": content,
                "usage": usage,
            }
            write_json(self.path, self.values)
        value = self.values[key]
        self.events.append(
            {
                "stage": stage,
                "request_sha256": key,
                "cached": cached,
                "transport_elapsed_ms": transport_elapsed_ms,
                "request": request,
            }
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=value["content"]))]
        )


class PrefilledEmbedder:
    def __init__(self, values):
        self.values = values

    def embed_texts(self, texts):
        return [self.values[normalize_text(t)] for t in texts]

    def embed_query(self, query):
        return self.values[normalize_text(query)]


class BudgetedEmbeddingAPI:
    def __init__(self, client, budget):
        self.client, self.budget = client, budget

    def create(self, **request):
        self.budget.consume("embedding")
        return self.client.embeddings.create(**request)


def prepare_scope(dataset, knowledge_dir, cases, chunks):
    llm = load_llm_settings(ROOT / ".env")
    embedding = load_embedding_settings(ROOT / ".env")
    paths = [
        "scripts/evaluate_answer_pipeline.py",
        "src/career_pilot/llm.py",
        "src/career_pilot/rag/factory.py",
        "src/career_pilot/rag/evidence.py",
        "src/career_pilot/rag/grounding.py",
        "src/career_pilot/rag/service.py",
        "src/career_pilot/rag/context.py",
        "src/career_pilot/rag/models.py",
        "src/career_pilot/rag/embeddings.py",
        "src/career_pilot/rag/vector_index.py",
        "src/career_pilot/rag/retrieval.py",
        "src/career_pilot/rag/rrf.py",
        "src/career_pilot/rag/reranking.py",
        "src/career_pilot/rag/hybrid_retrieval.py",
        "src/career_pilot/rag/windows.py",
    ]
    paths = sorted(
        set(paths)
        | {
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in (ROOT / "src/career_pilot/rag").glob("*.py")
        }
    )
    unique_texts = list(
        dict.fromkeys(
            normalize_text(text)
            for text in [*(c.content for c in chunks), *(c.question for c in cases)]
        )
    )
    return {
        "dataset": {
            "path": str(dataset.resolve()),
            "sha256": sha(dataset.read_bytes()),
        },
        "documents": [
            {"path": str(p.resolve()), "sha256": sha(p.read_bytes())}
            for p in sorted(knowledge_dir.glob("*.md"))
        ],
        "case_count": len(cases),
        "chunk_count": len(chunks),
        "new_authored_cases": sum(c.group == "new_authored" for c in cases),
        "known_regression_cases": sum(c.group == "known_regression" for c in cases),
        "configuration": DEFAULT_RAG_CONFIG,
        "embedding": {
            "provider_host": urlsplit(embedding.base_url).hostname,
            "model": embedding.model,
        },
        "llm": {"provider_host": urlsplit(llm.base_url).hostname, "model": llm.model},
        "source_sha256": {p: sha((ROOT / p).read_bytes()) for p in paths},
        "prompt_sha256": {
            name: sha(value.encode("utf-8")) for name, value in PROMPTS.items()
        },
        "maximum_embedding_requests": ceil(len(unique_texts) / 10),
        "maximum_chat_requests": 4 * len(cases),
        "maximum_calls_per_question": {
            "evidence": 1,
            "review": 1,
            "draft_or_proposal": 1,
            "audit": 1,
        },
        "maximum_output_tokens": {
            "evidence": 1800,
            "review": 1800,
            "draft": 2200,
            "proposal": 2200,
            "audit": 1200,
        },
        "sdk_automatic_retries": 0,
        "final_answer_generation": True,
        "personal_resume_or_runtime_databases": False,
        "labels_and_answer_patterns_sent_to_model": False,
    }


def group_summary(rows):
    answerable = [r for r in rows if r["answerable"]]
    negatives = [r for r in rows if not r["answerable"]]
    accepted = [r for r in answerable if r["result"]["answer_status"] == "supported"]
    valid_refusals = [
        r
        for r in negatives
        if r["result"]["evidence_status"] == "insufficient"
        and r["result"]["answer_status"] in ("not_checked", "insufficient")
        and not r["result"]["sources"]
    ]
    invalid = [
        r
        for r in rows
        if r["result"]["evidence_status"] in ("invalid", "unavailable")
        or r["result"]["answer_status"] in ("invalid", "unavailable")
    ]
    return {
        "case_count": len(rows),
        "answerable_count": len(answerable),
        "unanswerable_count": len(negatives),
        "answerable_completed": len(accepted),
        "answerable_completion_rate": len(accepted) / len(answerable)
        if answerable
        else None,
        "valid_unanswerable_refusals": len(valid_refusals),
        "valid_unanswerable_refusal_rate": len(valid_refusals) / len(negatives)
        if negatives
        else None,
        "invalid_or_unavailable_count": len(invalid),
        "accepted_pattern_checks_passed": sum(
            r["answer_pattern_checks_passed"] for r in accepted
        ),
        "warning": "Completion, model-audit agreement and lexical checks are not independent factual accuracy.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "evaluation/answer_pipeline_v5_cases.json",
    )
    p.add_argument("--knowledge-dir", type=Path, default=ROOT / "knowledge")
    p.add_argument("--prepare-scope", type=Path)
    p.add_argument("--scope-manifest", type=Path)
    p.add_argument("--allow-live-calls", action="store_true")
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--embedding-request-limit", type=int)
    args = p.parse_args()
    if args.embedding_request_limit is not None and args.embedding_request_limit < 0:
        p.error("向量请求上限不能为负数")
    if not (args.prepare_scope or args.validate_only or args.allow_live_calls):
        p.error("完整问答会真实生成与核验，须显式允许并提供范围清单")
    documents = load_knowledge_documents(args.knowledge_dir)
    cases = load_cases(args.dataset, documents)
    chunks = [
        c
        for d in documents
        for c in chunk_document(d, max_characters=DEFAULT_RAG_CONFIG["max_characters"])
    ]
    if args.validate_only:
        print(
            json.dumps(
                {
                    "validated_cases": len(cases),
                    "documents": len(documents),
                    "chunks": len(chunks),
                    "network_calls": 0,
                },
                ensure_ascii=False,
            )
        )
        return
    scope = prepare_scope(args.dataset, args.knowledge_dir, cases, chunks)
    if args.embedding_request_limit is not None:
        scope["maximum_embedding_requests"] = min(
            scope["maximum_embedding_requests"], args.embedding_request_limit
        )
    if args.prepare_scope:
        write_json(args.prepare_scope, scope)
        print("仅准备范围，无网络调用：" + str(args.prepare_scope))
        return
    if args.scope_manifest is None or args.output_dir is None:
        p.error("真实评测需要 --scope-manifest 与 --output-dir")
    if json.loads(args.scope_manifest.read_text("utf-8-sig")) != scope:
        p.error("当前输入、实现或模型与范围清单不一致")
    directory = args.output_dir
    directory.mkdir(parents=True, exist_ok=True)
    frozen = directory / "scope.json"
    if frozen.exists() and json.loads(frozen.read_text("utf-8")) != scope:
        p.error("不能以不同范围复用旧缓存")
    write_json(frozen, scope)
    budget = RequestBudget(
        directory / "request-ledger.json",
        scope["maximum_embedding_requests"],
        scope["maximum_chat_requests"],
    )
    llm_settings = load_llm_settings(ROOT / ".env")
    embedding_settings = load_embedding_settings(ROOT / ".env")
    real = OpenAI(
        api_key=llm_settings.api_key.get_secret_value(),
        base_url=llm_settings.base_url,
        timeout=30,
        max_retries=0,
    )
    recorder = RecordingCompletions(real, directory, budget)
    model = LLMClient(
        llm_settings, client=SimpleNamespace(chat=SimpleNamespace(completions=recorder))
    )
    vectors_path = directory / "vectors.json"
    vectors = (
        json.loads(vectors_path.read_text("utf-8")) if vectors_path.exists() else {}
    )
    texts = list(
        dict.fromkeys(
            normalize_text(t)
            for t in [*(c.content for c in chunks), *(c.question for c in cases)]
        )
    )
    missing = [t for t in texts if t not in vectors]
    embedding_sdk = OpenAI(
        api_key=embedding_settings.api_key.get_secret_value(),
        base_url=embedding_settings.base_url,
        timeout=30,
        max_retries=0,
    )
    embedder = EmbeddingClient(
        embedding_settings,
        client=SimpleNamespace(embeddings=BudgetedEmbeddingAPI(embedding_sdk, budget)),
    )
    for start in range(0, len(missing), 10):
        batch = missing[start : start + 10]
        vectors.update(zip(batch, embedder.embed_texts(batch), strict=True))
        write_json(vectors_path, vectors)
    service = create_grounded_rag_service(
        chunks, model, PrefilledEmbedder(vectors), configuration=DEFAULT_RAG_CONFIG
    )
    results_path = directory / "case-results.json"
    results = (
        json.loads(results_path.read_text("utf-8")) if results_path.exists() else {}
    )
    for index, case in enumerate(cases, 1):
        if case.case_id in results:
            saved = results[case.case_id]["result"]
            if (
                saved["evidence_status"] != "unavailable"
                and saved["answer_status"] != "unavailable"
            ):
                continue
            # Retry only unfinished cases. Successful stages remain cached and
            # every new attempt still consumes the original persisted budget.
        event_start = len(recorder.events)
        case_started = perf_counter()
        result = service.answer(case.question)
        case_elapsed_ms = (perf_counter() - case_started) * 1000
        events = recorder.events[event_start:]
        checks = all(
            any(
                canonical_text(pattern) in canonical_text(result.answer)
                for pattern in group
            )
            for group in case.answer_checks
        )
        results[case.case_id] = {
            "case_id": case.case_id,
            "case_elapsed_ms": case_elapsed_ms,
            "contains_cached_model_stages": any(e["cached"] for e in events),
            "group": case.group,
            "question": case.question,
            "answerable": case.answerable,
            "expected_evidence": [e.model_dump() for e in case.evidence],
            "answer_pattern_checks_passed": checks if case.answerable else None,
            "result": result.model_dump(),
            "stage_events": events,
        }
        write_json(results_path, results)
        print(
            f"{index}/{len(cases)} | {case.case_id} | evidence={result.evidence_status} "
            f"answer={result.answer_status} | chat_requests={budget.counts['chat']}",
            flush=True,
        )
        if (
            result.evidence_status == "unavailable"
            or result.answer_status == "unavailable"
        ):
            raise RuntimeError(
                "Provider stage unavailable; stopped after first failure"
            )
    rows = list(results.values())
    report = {
        "evaluation_scope": "complete_grounded_answer_pipeline",
        "scope": scope,
        "request_counts": budget.counts,
        "summary": group_summary(rows),
        "by_group": {
            group: group_summary([r for r in rows if r["group"] == group])
            for group in sorted({r["group"] for r in rows})
        },
        "results": rows,
        "human_semantic_review_completed": False,
        "independent_external_dataset": False,
    }
    write_json(directory / "report.json", report)
    with (directory / "manual-review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "case_id",
                "expected_answerable",
                "answer",
                "evidence_status",
                "answer_status",
                "sources",
                "human_fact_correct",
                "human_citations_supported",
                "human_question_fully_answered",
            ]
        )
        for row in rows:
            r = row["result"]
            writer.writerow(
                [
                    row["case_id"],
                    row["answerable"],
                    r["answer"],
                    r["evidence_status"],
                    r["answer_status"],
                    "; ".join(s["source"] for s in r["sources"]),
                    "",
                    "",
                    "",
                ]
            )
    lines = [
        "# 完整问答真实评测",
        "",
        "新写题与已知回归题分开统计；不把模型自审通过当作事实准确率。",
        "",
        "| 分组 | 可回答完成 | 有效无答案拒绝 | 格式/服务异常 |",
        "| --- | --- | --- | --- |",
    ]
    for group, s in report["by_group"].items():
        lines.append(
            f"| {group} | {s['answerable_completed']}/{s['answerable_count']} | "
            f"{s['valid_unanswerable_refusals']}/{s['unanswerable_count']} | "
            f"{s['invalid_or_unavailable_count']} |"
        )
    lines += [
        "",
        f"实际请求：Embedding {budget.counts['embedding']}，聊天 {budget.counts['chat']}。",
        "本轮生成最终回答，原文引用与模型逐陈述审查均保留；人工语义复核表尚未填写。",
        "答案模式词仅作辅助文本检查，不等于语义正确率。",
    ]
    (directory / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (OpenAIError, OSError, ValueError, RuntimeError, KeyError) as error:
        print(f"评测未完成：{type(error).__name__}；检查点与请求账本已保留。")
        raise SystemExit(1) from None
