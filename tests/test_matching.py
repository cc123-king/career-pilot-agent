import pytest

from career_pilot.matching import calculate_match
from career_pilot.models import (
    JobProfile,
    ProjectEvidence,
    ResumeProfile,
)


def test_calculate_match_returns_explainable_result() -> None:
    resume = ResumeProfile(
        skills=["Python", "FastAPI"],
        projects=[
            ProjectEvidence(
                name="CareerPilot Agent",
                description="使用多 Agent 工作流分析简历和招聘岗位。",
                technologies=["LangGraph"],
            )
        ],
    )
    job = JobProfile(
        company="示例科技",
        role="Agent 开发工程师",
        required_skills=["Python", "RAG", "FastAPI"],
        preferred_skills=["LangGraph", "MCP"],
    )

    result = calculate_match(resume, job)

    assert result.matched_required_skills == ["Python", "FastAPI"]
    assert result.missing_required_skills == ["RAG"]
    assert result.matched_preferred_skills == ["LangGraph"]
    assert result.missing_preferred_skills == ["MCP"]
    assert result.required_coverage == pytest.approx(2 / 3)
    assert result.preferred_coverage == pytest.approx(1 / 2)
    assert result.score == pytest.approx(61.67)


def test_calculate_match_ignores_case_and_outer_spaces() -> None:
    resume = ResumeProfile(skills=[" Python ", "FASTAPI"])
    job = JobProfile(
        company="示例科技",
        role="后端开发工程师",
        required_skills=["python", "FastAPI"],
    )

    result = calculate_match(resume, job)

    assert result.required_coverage == 1
    assert result.score == 100


def test_calculate_match_handles_empty_requirements() -> None:
    resume = ResumeProfile(skills=["Python"])
    job = JobProfile(
        company="示例科技",
        role="未明确要求的岗位",
    )

    result = calculate_match(resume, job)

    assert result.score == 0
    assert result.required_coverage == 0
    assert result.preferred_coverage == 0


def test_calculate_match_returns_project_evidence() -> None:
    resume = ResumeProfile(
        skills=["Python"],
        projects=[
            ProjectEvidence(
                name="CareerPilot Agent",
                description="使用多 Agent 工作流完成简历与岗位的自动分析。",
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

    result = calculate_match(resume, job)

    langgraph_evidence = next(
        evidence for evidence in result.skill_evidence if evidence.skill == "LangGraph"
    )

    assert langgraph_evidence.source_type == "project"
    assert langgraph_evidence.source_name == "CareerPilot Agent"
    assert "多 Agent 工作流" in langgraph_evidence.excerpt
    assert all(evidence.skill != "MCP" for evidence in result.skill_evidence)


@pytest.mark.parametrize(
    "required,preferred,skills,expected",
    [
        (["Python", "FastAPI"], [], ["Python", "FastAPI"], 100),
        (["Python", "SQL"], [], ["Python"], 50),
        ([], ["Python"], ["Python"], 100),
        (["Python"], ["SQL"], ["Python"], 70),
        (["Python"], ["SQL"], ["Python", "SQL"], 100),
        ([], [], ["Python"], 0),
    ],
)
def test_weights_only_apply_to_requirement_groups_that_exist(
    required, preferred, skills, expected
):
    result = calculate_match(
        ResumeProfile(skills=skills),
        JobProfile(
            company="demo",
            role="dev",
            required_skills=required,
            preferred_skills=preferred,
        ),
    )
    assert result.score == expected


@pytest.mark.parametrize(
    "resume_name,job_name",
    [
        ("Fast API", "FastAPI"),
        ("Fast-API", "FASTAPI"),
        ("postgres", "PostgreSQL"),
        ("sklearn", "scikit-learn"),
        ("ＦａｓｔＡＰＩ", "FastAPI"),
    ],
)
def test_explicit_aliases_match_and_preserve_source_text(resume_name, job_name):
    result = calculate_match(
        ResumeProfile(skills=[resume_name]),
        JobProfile(company="demo", role="dev", required_skills=[job_name]),
    )
    assert result.score == 100 and result.matched_required_skills == [job_name]
    assert result.skill_evidence[0].skill == resume_name
    assert resume_name in result.skill_evidence[0].excerpt


@pytest.mark.parametrize(
    "resume_name,job_name",
    [
        ("Java", "JavaScript"),
        ("C", "C++"),
        ("RAG", "LangGraph"),
        (".NET", "NET"),
        ("SQL", "PostgreSQL"),
    ],
)
def test_related_or_similar_technologies_are_not_aliases(resume_name, job_name):
    result = calculate_match(
        ResumeProfile(skills=[resume_name]),
        JobProfile(company="demo", role="dev", required_skills=[job_name]),
    )
    assert result.score == 0 and result.missing_required_skills == [job_name]


def test_aliases_are_deduplicated_and_used_by_coaching_and_interview():
    from career_pilot.coach import generate_resume_advice
    from career_pilot.interview import generate_interview_questions

    resume = ResumeProfile(
        skills=["Fast API"],
        projects=[
            ProjectEvidence(
                name="demo",
                description="通过实际项目实现了可验证的后台服务功能。",
                technologies=["FastAPI"],
            )
        ],
    )
    job = JobProfile(
        company="demo", role="dev", required_skills=["FastAPI", "Fast API"]
    )
    result = calculate_match(resume, job)
    assert result.matched_required_skills == ["FastAPI"] and result.score == 100
    advice = generate_resume_advice(resume, job, result)
    assert not any(a.category == "strengthen_evidence" for a in advice)
    questions = generate_interview_questions(resume, job, result)
    assert any(q.resume_evidence for q in questions)
    assert not any(q.category == "skill_gap" for q in questions)
