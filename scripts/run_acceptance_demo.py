"""Run three offline acceptance scenarios through the existing career workflow."""

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from career_pilot.api import ANALYSIS_EXAMPLE
from career_pilot.models import AnalysisRequest, StrictModel
from career_pilot.rag.documents import chunk_document, load_knowledge_documents
from career_pilot.rag.retrieval import KeywordRetriever
from career_pilot.report import save_markdown_report
from career_pilot.workflow import CareerState, run_career_analysis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_NODES = [
    "ResumeAgent",
    "JobAgent",
    "RAGAgent",
    "MatchAgent",
    "ResumeCoachAgent",
    "InterviewAgent",
    "ReportAgent",
]


class DemoScenario(StrictModel):
    name: str
    label: str
    request: AnalysisRequest
    expected_score: float
    expected_missing_required: list[str]
    empty_knowledge: bool = False


def build_scenarios() -> list[DemoScenario]:
    baseline = AnalysisRequest(**ANALYSIS_EXAMPLE)
    missing_fastapi = AnalysisRequest(
        **{
            **ANALYSIS_EXAMPLE,
            "resume_text": baseline.resume_text.replace(
                "Python、FastAPI、RAG", "Python、RAG"
            ),
        }
    )
    return [
        DemoScenario(
            name="baseline",
            label="正常分析",
            request=baseline,
            expected_score=85,
            expected_missing_required=[],
        ),
        DemoScenario(
            name="missing-fastapi",
            label="缺少必备技能",
            request=missing_fastapi,
            expected_score=61.67,
            expected_missing_required=["FastAPI"],
        ),
        DemoScenario(
            name="no-knowledge",
            label="知识资料不足",
            request=baseline,
            expected_score=85,
            expected_missing_required=[],
            empty_knowledge=True,
        ),
    ]


def check_result(scenario: DemoScenario, result: CareerState) -> dict[str, bool]:
    match = result["match_result"]
    sources = result["knowledge_context"].sources
    citations = [
        item.citation_id for item in result["advice"] if item.citation_id is not None
    ]
    source_ids = {source.citation_id for source in sources}
    return {
        "expected_score": match.score == scenario.expected_score,
        "required_gaps": match.missing_required_skills
        == scenario.expected_missing_required,
        "preferred_gaps": match.missing_preferred_skills == ["MCP"],
        "node_order": [step.split(":", 1)[0] for step in result["workflow_trace"]]
        == EXPECTED_NODES,
        "advice_present": bool(result["advice"]),
        "interview_questions_present": bool(result["interview_questions"]),
        "report_score_consistent": f"匹配分数：{match.score:.2f} / 100"
        in result["report_markdown"],
        "knowledge_availability": not sources
        if scenario.empty_knowledge
        else bool(sources),
        "knowledge_warning": bool(result["warnings"])
        if scenario.empty_knowledge
        else not result["warnings"],
        "citation_integrity": all(citation in source_ids for citation in citations),
        "no_invented_citations": not citations
        if scenario.empty_knowledge
        else bool(citations),
    }


def save_scenario(
    directory: Path,
    scenario: DemoScenario,
    result: CareerState,
) -> Path:
    directory.mkdir()
    (directory / "input.json").write_text(
        scenario.request.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    snapshot = {
        "generation_mode": "rules",
        "knowledge_query": result["knowledge_query"],
        "resume_profile": result["resume_profile"].model_dump(),
        "job_profile": result["job_profile"].model_dump(),
        "match_result": result["match_result"].model_dump(),
        "advice": [item.model_dump() for item in result["advice"]],
        "interview_questions": [
            item.model_dump() for item in result["interview_questions"]
        ],
        "knowledge_sources": [
            item.model_dump() for item in result["knowledge_context"].sources
        ],
        "workflow_trace": result["workflow_trace"],
        "warnings": result["warnings"],
    }
    (directory / "result.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return save_markdown_report(result["report_markdown"], directory=directory)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "data" / "reports"
    )
    arguments = parser.parse_args()
    directory = arguments.output_dir.resolve() / f"demo-{uuid4().hex}"

    try:
        documents = load_knowledge_documents(PROJECT_ROOT / "knowledge")
        chunks = [chunk for document in documents for chunk in chunk_document(document)]
        retriever = KeywordRetriever(chunks)
        scenarios = build_scenarios()
        directory.mkdir(parents=True, exist_ok=False)
        summaries = []
        for scenario in scenarios:
            selected_retriever = (
                KeywordRetriever([]) if scenario.empty_knowledge else retriever
            )
            result = run_career_analysis(scenario.request, retriever=selected_retriever)
            checks = check_result(scenario, result)
            report_path = save_scenario(directory / scenario.name, scenario, result)
            passed = all(checks.values())
            summaries.append(
                {
                    "scenario": scenario.name,
                    "label": scenario.label,
                    "passed": passed,
                    "score": result["match_result"].score,
                    "missing_required_skills": result[
                        "match_result"
                    ].missing_required_skills,
                    "node_count": len(result["workflow_trace"]),
                    "source_count": len(result["knowledge_context"].sources),
                    "checks": checks,
                    "report_file": str(report_path.resolve()),
                }
            )
            print(
                f"{'PASS' if passed else 'FAIL'} {scenario.label} | 分数：{result['match_result'].score:.2f} | 节点：{len(result['workflow_trace'])} | 引用资料：{len(result['knowledge_context'].sources)}"
            )
            for name, success in checks.items():
                if not success:
                    print(f"  未通过检查：{name}")

        passed_count = sum(item["passed"] for item in summaries)
        summary = {
            "demo_scope": "offline_seven_node_workflow",
            "retrieval_mode": "keyword",
            "generation_mode": "rules",
            "synthetic_inputs_only": True,
            "knowledge_sha256": {
                document.source: sha256(document.content.encode("utf-8")).hexdigest()
                for document in documents
            },
            "scenario_count": len(scenarios),
            "passed_count": passed_count,
            "results": summaries,
        }
        (directory / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"演示失败：{error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"验收：{passed_count}/{len(scenarios)} 通过")
    print(f"演示目录：{directory}")
    print("本次未调用模型；知识不足场景使用空检索器模拟，没有删除知识文件。")
    if passed_count != len(scenarios):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
