import pytest
from pydantic import ValidationError

from career_pilot.models import (
    AnalysisRequest,
    InterviewQuestion,
    JobProfile,
    ProjectEvidence,
    ResumeProfile,
)

VALID_RESUME = "掌握 Python、FastAPI 和 pytest，完成过 Agent 项目开发与测试。"
VALID_JOB_DESCRIPTION = (
    "负责 AI Agent 应用开发，要求掌握 Python、RAG、工具调用和接口开发。"
)


def test_analysis_request_accepts_valid_input() -> None:
    request = AnalysisRequest(
        resume_text=VALID_RESUME,
        job_description=VALID_JOB_DESCRIPTION,
        company=" 示例科技 ",
        role=" Agent 开发工程师 ",
    )

    assert request.company == "示例科技"
    assert request.role == "Agent 开发工程师"


def test_analysis_request_rejects_short_resume() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(
            resume_text="太短",
            job_description=VALID_JOB_DESCRIPTION,
            company="示例科技",
            role="Agent 开发工程师",
        )


def test_analysis_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(
            resume_text=VALID_RESUME,
            job_description=VALID_JOB_DESCRIPTION,
            company="示例科技",
            role="Agent 开发工程师",
            unknown_field="不应该被接受",
        )


def test_resume_profile_builds_nested_project_model() -> None:
    resume = ResumeProfile(
        candidate_name="示例候选人",
        skills=["Python", "FastAPI", "RAG"],
        projects=[
            {
                "name": "CareerPilot Agent",
                "description": "使用多 Agent 工作流分析简历和岗位要求。",
                "technologies": ["Python", "LangGraph"],
            }
        ],
    )

    assert resume.candidate_name == "示例候选人"
    assert resume.projects[0].name == "CareerPilot Agent"
    assert isinstance(resume.projects[0], ProjectEvidence)


def test_job_profile_stores_required_and_preferred_skills() -> None:
    job = JobProfile(
        company="示例科技",
        role="Agent 开发工程师",
        responsibilities=["开发和维护 Agent 应用"],
        required_skills=["Python", "RAG"],
        preferred_skills=["LangGraph"],
        keywords=["工具调用", "大模型应用"],
    )

    assert job.required_skills == ["Python", "RAG"]
    assert job.preferred_skills == ["LangGraph"]


def test_resume_profile_lists_are_not_shared() -> None:
    first_resume = ResumeProfile()
    second_resume = ResumeProfile()

    first_resume.skills.append("Python")

    assert first_resume.skills == ["Python"]
    assert second_resume.skills == []


@pytest.mark.parametrize(
    "overrides",
    [{"category": "invented"}, {"question": " "}, {"answer_points": []}],
)
def test_interview_question_rejects_invalid_output(overrides) -> None:
    values = {
        "category": "general",
        "question": "请介绍你与岗位相关的真实经历。",
        "reason": "了解候选人的背景。",
        "answer_points": ["说明真实背景与个人贡献。"],
    }
    values.update(overrides)

    with pytest.raises(ValidationError):
        InterviewQuestion(**values)
