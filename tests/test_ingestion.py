from pathlib import Path

from career_pilot.ingestion import (
    load_job_profile,
    load_resume_profile,
)


def test_load_resume_profile_from_file(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text(
        """示例候选人
个人简介
苏州大学研究生，关注 AI Agent 应用开发。
技能
Python、FastAPI、RAG
教育经历
苏州大学 硕士
项目经历
CareerPilot Agent：使用多 Agent 工作流分析简历和岗位要求。技术栈：Python、LangGraph
""",
        encoding="utf-8",
    )

    profile = load_resume_profile(resume_path)

    assert profile.candidate_name == "示例候选人"
    assert profile.skills == ["Python", "FastAPI", "RAG"]
    assert profile.projects[0].name == "CareerPilot Agent"


def test_load_job_profile_from_file(tmp_path: Path) -> None:
    job_path = tmp_path / "job.md"
    job_path.write_text(
        """# 岗位职责
负责 AI Agent 应用开发

# 任职要求
Python、RAG、FastAPI

# 加分项
LangGraph、MCP
""",
        encoding="utf-8",
    )

    profile = load_job_profile(
        job_path,
        company="示例科技",
        role="Agent 开发工程师",
    )

    assert profile.company == "示例科技"
    assert "Python" in profile.required_skills
    assert "MCP" in profile.preferred_skills
