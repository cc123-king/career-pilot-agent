"""Demonstrate the seven-node CareerPilot analysis and report workflow."""

import argparse
import sys

from career_pilot.models import AnalysisRequest
from career_pilot.report import save_markdown_report
from career_pilot.workflow import run_career_analysis

RESUME_TEXT = """示例同学
个人简介
正在学习 Python 和 Agent 应用开发。
技能
Python、FastAPI、RAG
项目经历
CareerPilot Agent：使用多节点工作流分析简历和岗位要求。技术栈：LangGraph
"""

JOB_TEXT = """岗位职责
负责 Agent 应用开发、知识检索和后端接口维护
任职要求
Python、RAG、FastAPI
加分项
LangGraph、MCP
"""


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Use the configured embedding API, RRF, and reranker.",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save the Markdown report to the project's data/reports directory.",
    )
    arguments = parser.parse_args()

    retriever = None
    if arguments.hybrid:
        from career_pilot.api import get_rag_service

        retriever = get_rag_service()

    result = run_career_analysis(
        AnalysisRequest(
            resume_text=RESUME_TEXT,
            job_description=JOB_TEXT,
            company="示例科技",
            role="Agent 开发工程师",
        ),
        retriever=retriever,
    )

    print("检索模式：" + ("混合检索" if arguments.hybrid else "本地关键词检索"))
    print("\n" + result["report_markdown"])
    if arguments.save_report:
        try:
            path = save_markdown_report(result["report_markdown"])
        except OSError as error:
            print(f"报告已生成，但保存失败：{error}", file=sys.stderr)
            raise SystemExit(1) from error
        print("报告已保存：" + str(path.resolve()))


if __name__ == "__main__":
    main()
