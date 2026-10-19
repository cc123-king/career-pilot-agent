from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_pilot import api, ui
from career_pilot.rag.knowledge_store import InMemoryKnowledgeStore
from career_pilot.web import create_web_app


def test_combined_app_serves_ui_and_existing_api_routes() -> None:
    combined = create_web_app()
    assert combined is api.app
    assert create_web_app() is combined

    with TestClient(combined) as client:
        redirect = client.get("/", follow_redirects=False)
        assert redirect.status_code == 307
        assert redirect.headers["location"] == "/ui/"
        assert client.get("/ui/").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/health").json()["status"] == "ok"
        analysis = client.post("/api/career/analyze", json=api.ANALYSIS_EXAMPLE)
        assert analysis.status_code == 200
        assert analysis.json()["match_result"]["score"] == 85

        config = client.get("/ui/config").json()
        tabs = [
            item["props"]["label"]
            for item in config["components"]
            if item["type"] == "tabitem"
        ]
        assert tabs == ["简历分析", "文档核对与历史", "知识问答"]
        assert config["analytics_enabled"] is False
        functions = {item["api_name"] for item in config["dependencies"]}
        assert {"analyze_resume", "export_report", "upload_knowledge"} <= functions


def test_ui_upload_is_available_to_analysis_in_the_same_web_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    knowledge_directory = tmp_path / "knowledge"
    knowledge_directory.mkdir()
    monkeypatch.setattr(api, "KNOWLEDGE_DIRECTORY", knowledge_directory)
    monkeypatch.setattr(api, "UPLOADED_KNOWLEDGE_STORE", InMemoryKnowledgeStore())
    document = tmp_path / "shared-guide.md"
    document.write_text(
        "简历优化 面试准备 Agent 开发工程师 Python RAG FastAPI LangGraph MCP。"
        "项目介绍要说明业务目标、技术选择和测试方法。",
        encoding="utf-8",
    )

    with TestClient(create_web_app()) as client:
        before = client.post("/api/career/analyze", json=api.ANALYSIS_EXAMPLE).json()
        assert before["knowledge_sources"] == []

        status = ui.upload_knowledge_file(str(document))
        response = client.post("/api/career/analyze", json=api.ANALYSIS_EXAMPLE)

        assert "shared-guide.md" in status
        assert response.status_code == 200
        assert response.json()["knowledge_sources"][0]["source"] == "shared-guide.md"
        assert (
            ui.analyze_resume(*ui.load_analysis_example())[3]
            == response.json()["report_markdown"]
        )
