from pathlib import Path
from uuid import UUID

import pytest

from career_pilot.coach import generate_resume_advice
from career_pilot.interview import generate_interview_questions
from career_pilot.matching import calculate_match
from career_pilot.models import JobProfile, ProjectEvidence, ResumeAdvice, ResumeProfile
from career_pilot.rag.context import build_retrieval_context
from career_pilot.rag.models import KnowledgeChunk, SearchHit
from career_pilot.report import generate_markdown_report, save_markdown_report


def make_profiles() -> tuple[ResumeProfile, JobProfile]:
    resume = ResumeProfile(
        candidate_name="示例同学",
        skills=["Python"],
        projects=[
            ProjectEvidence(
                name="CareerPilot Agent",
                description="使用 LangGraph 工作流分析简历与岗位要求。",
                technologies=["LangGraph"],
            )
        ],
    )
    job = JobProfile(
        company="示例科技",
        role="Agent 开发工程师",
        required_skills=["Python"],
        preferred_skills=["LangGraph", "MCP"],
    )
    return resume, job


def test_report_contains_existing_scores_evidence_advice_and_questions() -> None:
    resume, job = make_profiles()
    match = calculate_match(resume, job)
    advice = generate_resume_advice(resume, job, match)
    questions = generate_interview_questions(resume, job, match)

    report = generate_markdown_report(resume, job, match, advice, questions)

    assert report.startswith("# CareerPilot 求职分析报告\n")
    assert "候选人：示例同学" in report
    assert "公司：示例科技" in report
    assert "岗位：Agent 开发工程师" in report
    assert "匹配分数：85.00 / 100" in report
    assert "必备技能覆盖率：100.0%" in report
    assert "加分技能覆盖率：50.0%" in report
    assert "未找到证据的加分技能：MCP" in report
    assert "技能栏声明 / 技能栏" in report
    assert "项目记录 / CareerPilot Agent" in report
    assert "使用 LangGraph 工作流分析简历与岗位要求。" in report
    assert "核实并补充 MCP 的真实证据" in report
    assert "你如何理解 MCP？" in report
    assert "回答要点：" in report
    assert "追问：" in report
    assert "不代表录用概率" in report


def test_report_uses_the_supplied_score_without_recalculating_it() -> None:
    resume, job = make_profiles()
    match = calculate_match(resume, job)
    match.score = 42.25

    report = generate_markdown_report(resume, job, match, [], [])

    assert "匹配分数：42.25 / 100" in report
    assert match.score == 42.25


def test_report_preserves_citations_and_page_and_ocr_metadata() -> None:
    resume, job = make_profiles()
    match = calculate_match(resume, job)
    hit = SearchHit(
        chunk=KnowledgeChunk(
            chunk_id="guide-0",
            document_id="guide",
            title="面试资料",
            source="guide.pdf",
            content="项目描述应说明业务目标、本人贡献和验证方法。",
            position=0,
            page_number=2,
            source_type="pdf",
            extraction_method="ocr",
        ),
        score=0.9,
    )
    context = build_retrieval_context("面试准备", [hit])
    advice = generate_resume_advice(
        resume, job, match, knowledge_hits=[hit], knowledge_sources=context.sources
    )

    report = generate_markdown_report(
        resume, job, match, advice, [], knowledge_sources=context.sources
    )

    assert "参考来源：[资料1]" in report
    assert "### [资料1] 面试资料" in report
    assert "来源：guide.pdf" in report
    assert "分块：guide\\-0" in report
    assert "页码：2" in report
    assert "文件类型：pdf" in report
    assert "提取方式：OCR" in report
    assert "> " + hit.chunk.content in report
    assert "参考原文（非候选人经历）" in report


def test_report_does_not_publish_a_reference_without_a_retained_source() -> None:
    resume, job = make_profiles()
    advice = ResumeAdvice(
        category="knowledge_reference",
        priority="low",
        title="参考资料",
        reason="准备检查来源。",
        suggestion="核对资料。",
        citation_id=7,
        knowledge_excerpt="不能核对来源的引用内容。",
    )

    report = generate_markdown_report(
        resume, job, calculate_match(resume, job), [advice], []
    )

    assert "参考来源未保留" in report
    assert "[资料7]" not in report
    assert advice.knowledge_excerpt not in report


def test_report_handles_empty_profiles_and_keeps_warnings_and_trace() -> None:
    resume = ResumeProfile()
    job = JobProfile(company="示例科技", role="Agent 开发工程师")

    report = generate_markdown_report(
        resume,
        job,
        calculate_match(resume, job),
        [],
        [],
        warnings=["知识库证据不足。"],
        workflow_trace=["ReportAgent: assembled the career report"],
    )

    assert "未识别姓名" in report
    assert "未识别到必备技能要求" in report
    assert "未识别到加分技能要求" in report
    assert "暂无简历建议" in report
    assert "暂无面试问题" in report
    assert "未保留可引用资料" in report
    assert "提醒：知识库证据不足。" in report
    assert "1. ReportAgent: assembled the career report" in report


def test_report_treats_user_markdown_and_html_as_plain_text() -> None:
    resume, job = make_profiles()
    resume.candidate_name = "姓名\n## 伪造章节"
    job.company = "<script>alert(1)</script>"
    job.role = "[职位](https://example.com)"

    report = generate_markdown_report(resume, job, calculate_match(resume, job), [], [])

    assert "\n## 伪造章节" not in report
    assert "姓名 \\#\\# 伪造章节" in report
    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert "\\[职位\\]\\(https://example.com\\)" in report


def test_report_generation_is_deterministic_and_does_not_mutate_inputs() -> None:
    resume, job = make_profiles()
    match = calculate_match(resume, job)
    advice = generate_resume_advice(resume, job, match)
    questions = generate_interview_questions(resume, job, match)
    inputs = [resume, job, match, *advice, *questions]
    before = [item.model_dump() for item in inputs]

    first = generate_markdown_report(resume, job, match, advice, questions)
    second = generate_markdown_report(resume, job, match, advice, questions)

    assert first == second
    assert before == [item.model_dump() for item in inputs]
    assert first.endswith("\n")


def test_saved_reports_are_utf8_and_do_not_overwrite_each_other(tmp_path: Path) -> None:
    directory = tmp_path / "reports"
    content = "# 求职分析报告\n\n中文报告内容。\n"

    first = save_markdown_report(content, directory=directory)
    second = save_markdown_report(content, directory=directory)

    assert first.parent == directory
    assert first.suffix == ".md"
    assert first != second
    assert first.read_bytes() == content.encode("utf-8")
    assert second.read_text(encoding="utf-8") == content


def test_report_filename_collision_preserves_the_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("career_pilot.report.uuid4", lambda: UUID(int=0))
    first = save_markdown_report("原来的报告", directory=tmp_path)

    with pytest.raises(FileExistsError):
        save_markdown_report("新的报告", directory=tmp_path)

    assert first.read_text(encoding="utf-8") == "原来的报告"


def test_empty_report_is_rejected_before_creating_a_directory(tmp_path: Path) -> None:
    directory = tmp_path / "reports"

    with pytest.raises(ValueError, match="报告内容不能为空"):
        save_markdown_report(" \n ", directory=directory)

    assert not directory.exists()
