from career_pilot.parsers import parse_job_text, parse_resume_text

RESUME_TEXT = """示例候选人
个人简介
苏州大学研究生，关注 AI Agent 应用开发。
技能
Python、FastAPI、RAG、LangGraph
教育经历
苏州大学 硕士
项目经历
CareerPilot Agent：使用多 Agent 工作流分析简历和岗位要求。技术栈：Python、LangGraph
"""


JOB_TEXT = """岗位职责
负责 AI Agent 应用开发和维护
任职要求
Python、RAG、FastAPI
加分项
LangGraph、MCP
"""


def test_parse_resume_text_returns_structured_profile() -> None:
    profile = parse_resume_text(RESUME_TEXT)

    assert profile.candidate_name == "示例候选人"
    assert "Python" in profile.skills
    assert profile.education == ["苏州大学 硕士"]
    assert profile.projects[0].name == "CareerPilot Agent"
    assert "LangGraph" in profile.projects[0].technologies


def test_parse_job_text_returns_structured_profile() -> None:
    profile = parse_job_text(
        JOB_TEXT,
        company="示例科技",
        role="Agent 开发工程师",
    )

    assert profile.company == "示例科技"
    assert profile.role == "Agent 开发工程师"
    assert profile.responsibilities == ["负责 AI Agent 应用开发和维护"]
    assert "Python" in profile.required_skills
    assert "MCP" in profile.preferred_skills
