from pathlib import Path

from career_pilot.config import Settings
from career_pilot.reporting import export_analysis, render_analysis_markdown
from career_pilot.service import CareerPilotService

from test_parsers import JD, RESUME


def test_demo_workflow_runs_end_to_end():
    service = CareerPilotService(Settings(llm_provider="demo"))
    result = service.analyze(
        resume_text=RESUME,
        jd_text=JD,
        company="示例公司",
        role="AI Agent 开发工程师",
    )
    assert result.mode == "demo"
    assert 0 <= result.match_report.overall_score <= 100
    assert "LangGraph" in result.match_report.missing_skills
    assert result.advice
    assert len(result.interview_questions) >= 3
    assert len(result.workflow_trace) == 7


def test_report_export(tmp_path: Path):
    service = CareerPilotService(Settings(llm_provider="demo"))
    result = service.analyze(resume_text=RESUME, jd_text=JD)
    markdown = render_analysis_markdown(result)
    assert "人岗匹配报告" in markdown
    path = export_analysis(result, tmp_path)
    assert path.exists()
    assert "模拟面试题" in path.read_text(encoding="utf-8")

