import pytest

from career_pilot.interview import generate_interview_questions
from career_pilot.matching import calculate_match
from career_pilot.models import JobProfile, ProjectEvidence, ResumeProfile


def make_resume() -> ResumeProfile:
    return ResumeProfile(
        skills=["Python", "LangGraph"],
        projects=[
            ProjectEvidence(
                name="CareerPilot Agent",
                description="使用 LangGraph 工作流分析简历与岗位要求。",
                technologies=["LangGraph", "FastAPI"],
            )
        ],
    )


def make_job() -> JobProfile:
    return JobProfile(
        company="示例科技",
        role="Agent 开发工程师",
        required_skills=["Python", "RAG", "LangGraph"],
        preferred_skills=["FastAPI", "MCP"],
    )


def test_missing_skills_get_learning_questions_without_project_claims() -> None:
    resume, job = make_resume(), make_job()
    questions = generate_interview_questions(resume, job, calculate_match(resume, job))
    gaps = [item for item in questions if item.category == "skill_gap"]

    assert [item.related_skills for item in gaps] == [["RAG"], ["MCP"]]
    assert all("未找到" in item.reason for item in gaps)
    assert all("怎样学习和验证" in item.question for item in gaps)
    assert all(not item.resume_evidence for item in gaps)
    assert all("不把计划说成已完成" in " ".join(item.answer_points) for item in gaps)


def test_project_questions_and_skill_only_questions_have_distinct_evidence() -> None:
    resume, job = make_resume(), make_job()
    match = calculate_match(resume, job)
    questions = generate_interview_questions(resume, job, match)

    skill_questions = [item for item in questions if item.category == "matched_skill"]
    assert [item.related_skills for item in skill_questions] == [["Python"]]
    assert all(
        item.source_type == "skills_section"
        for question in skill_questions
        for item in question.resume_evidence
    )
    projects = [item for item in questions if item.category == "project"]
    assert len(projects) == 1
    assert "CareerPilot Agent" in projects[0].question
    assert projects[0].related_skills == ["LangGraph", "FastAPI"]
    assert projects[0].resume_evidence == [
        item for item in match.skill_evidence if item.source_type == "project"
    ]
    assert projects[0].answer_points
    assert projects[0].follow_ups


def test_case_variants_and_overlapping_requirements_do_not_duplicate_questions() -> None:
    resume, job = make_resume(), make_job()
    job.required_skills.extend([" python ", "RAG"])
    job.preferred_skills.extend(["PYTHON", "langgraph", "mcp"])

    questions = generate_interview_questions(resume, job, calculate_match(resume, job))

    assert len(questions) == 5
    assert sum(item.category == "project" for item in questions) == 1
    assert sum(item.related_skills == ["Python"] for item in questions) == 1
    assert sum(item.related_skills == ["MCP"] for item in questions) == 1


def test_question_budget_prioritizes_required_skills_over_preferred_skills() -> None:
    resume = ResumeProfile()
    job = JobProfile(
        company="示例科技",
        role="Agent 开发工程师",
        required_skills=["Python", "RAG"],
        preferred_skills=["MCP"],
    )
    match = calculate_match(resume, job)

    questions = generate_interview_questions(resume, job, match, max_questions=3)

    assert len(questions) == 3
    assert questions[0].category == "general"
    assert [item.related_skills for item in questions[1:]] == [["Python"], ["RAG"]]
    assert len(generate_interview_questions(resume, job, match, max_questions=1)) == 1


def test_empty_profiles_return_an_honest_general_question() -> None:
    resume = ResumeProfile()
    job = JobProfile(company="示例科技", role="Agent 开发工程师")

    questions = generate_interview_questions(resume, job, calculate_match(resume, job))

    assert len(questions) == 1
    assert questions[0].category == "general"
    assert "Agent 开发工程师" in questions[0].question
    assert "没有项目经历" in " ".join(questions[0].answer_points)
    assert questions[0].resume_evidence == []


def test_question_generation_preserves_inputs_and_copies_evidence() -> None:
    resume, job = make_resume(), make_job()
    match = calculate_match(resume, job)
    before = (resume.model_dump(), job.model_dump(), match.model_dump())

    questions = generate_interview_questions(resume, job, match)
    project = next(item for item in questions if item.category == "project")
    project.resume_evidence[0].excerpt = "修改输出中的证据，不应影响原始输入。"

    assert before == (resume.model_dump(), job.model_dump(), match.model_dump())


@pytest.mark.parametrize("max_questions", [0, 21])
def test_invalid_question_budget_is_rejected(max_questions: int) -> None:
    resume, job = make_resume(), make_job()

    with pytest.raises(ValueError, match="max_questions"):
        generate_interview_questions(
            resume, job, calculate_match(resume, job), max_questions=max_questions
        )


def test_default_budget_bounds_a_large_job_description() -> None:
    resume = ResumeProfile()
    job = JobProfile(
        company="示例科技",
        role="Agent 开发工程师",
        required_skills=[f"skill-{index}" for index in range(30)],
    )

    questions = generate_interview_questions(resume, job, calculate_match(resume, job))

    assert len(questions) == 8
    assert questions[-1].related_skills == ["skill-6"]
