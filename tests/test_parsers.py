from pathlib import Path

import pytest

from career_pilot.parsers import DocumentParseError, parse_job_description, parse_resume, read_document


RESUME = """
张三
zhangsan@example.com 13800138000
教育经历
示例大学 人工智能 硕士
技能
熟悉 Python、FastAPI、LangChain、RAG、SQLite 和 Git。
项目经历
使用 Python 和 FastAPI 构建 RAG 问答 API，并通过 SQLite 保存记录。
"""

JD = """
AI Agent 开发工程师
岗位职责：负责 Python 和 FastAPI 服务开发，构建 LangGraph 工作流和 RAG 模块。
任职要求：必须熟悉 Python、FastAPI、LangGraph、RAG、REST API 和 Git。
加分项：熟悉 Docker、MCP 者优先。
"""


def test_parse_resume_extracts_profile_and_skills():
    profile = parse_resume(RESUME)
    assert profile.name == "张三"
    assert profile.email == "zhangsan@example.com"
    assert "Python" in profile.skills
    assert "FastAPI" in profile.skills
    assert profile.projects


def test_parse_job_separates_required_and_preferred_skills():
    job = parse_job_description(JD, company="示例公司", role="AI Agent 开发工程师")
    assert job.company == "示例公司"
    assert "LangGraph" in job.required_skills
    assert "Docker" in job.preferred_skills
    assert "MCP" in job.preferred_skills


def test_parse_job_understands_multiline_preferred_section():
    text = """
    AI Agent 开发岗位
    任职要求
    必须熟悉 Python、FastAPI 和 LangGraph。
    加分项
    熟悉 Docker、MCP 者优先。
    """
    job = parse_job_description(text)
    assert "LangGraph" in job.required_skills
    assert "Docker" not in job.required_skills
    assert job.preferred_skills == ["MCP", "Docker"]


def test_read_document_reads_utf8_text(tmp_path: Path):
    path = tmp_path / "resume.txt"
    path.write_text(RESUME, encoding="utf-8")
    assert "FastAPI" in read_document(path)


def test_read_document_rejects_unknown_type(tmp_path: Path):
    path = tmp_path / "resume.xyz"
    path.write_text(RESUME, encoding="utf-8")
    with pytest.raises(DocumentParseError):
        read_document(path)
