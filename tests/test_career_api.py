import logging
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from career_pilot import api
from career_pilot.rag.knowledge_store import InMemoryKnowledgeStore
from career_pilot.rag.models import KnowledgeChunk, SearchHit

client = TestClient(api.app)


def test_career_analysis_returns_the_seven_node_result_without_api_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbid_model_service():
        raise AssertionError("Local analysis must not initialize the model service")

    monkeypatch.setattr(api, "get_rag_service", forbid_model_service)
    response = client.post("/api/career/analyze", json=api.ANALYSIS_EXAMPLE)

    assert response.status_code == 200
    result = response.json()
    assert len(result["request_id"]) == 12
    assert result["retrieval_mode"] == "keyword"
    assert result["generation_mode"] == "rules"
    assert result["resume_profile"]["candidate_name"] == "示例同学"
    assert result["job_profile"]["role"] == "Agent 开发工程师"
    assert result["match_result"]["score"] == 85
    assert result["match_result"]["missing_preferred_skills"] == ["MCP"]
    assert result["advice"]
    assert result["interview_questions"]
    assert result["knowledge_sources"]
    assert len(result["workflow_trace"]) == 7
    assert result["workflow_trace"][-1] == "ReportAgent: assembled the career report"
    assert "匹配分数：85.00 / 100" in result["report_markdown"]
    assert result["warnings"] == []
    assert "resume_text" not in result
    api.CareerAnalysisResponse.model_validate(result)


@pytest.mark.parametrize(
    "overrides",
    [
        {"resume_text": "太短"},
        {"resume_text": " " * 30},
        {"resume_text": "简" * 50_001},
        {"job_description": "太短"},
        {"company": " "},
        {"role": " "},
        {"unexpected_field": "不接受额外字段"},
    ],
)
def test_invalid_analysis_input_is_rejected_before_retrieval(
    overrides: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbid_retrieval(_mode):
        raise AssertionError("Invalid input must not start retrieval")

    monkeypatch.setattr(api, "get_career_retriever", forbid_retrieval)
    response = client.post(
        "/api/career/analyze?retrieval_mode=hybrid",
        json={**api.ANALYSIS_EXAMPLE, **overrides},
    )

    assert response.status_code == 422


def test_missing_analysis_field_is_rejected() -> None:
    payload = dict(api.ANALYSIS_EXAMPLE)
    payload.pop("resume_text")

    response = client.post("/api/career/analyze", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "resume_text"]


def test_invalid_retrieval_mode_is_rejected_before_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbid_retrieval(_mode):
        raise AssertionError("Invalid mode must not start retrieval")

    monkeypatch.setattr(api, "get_career_retriever", forbid_retrieval)
    response = client.post(
        "/api/career/analyze?retrieval_mode=unknown", json=api.ANALYSIS_EXAMPLE
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "retrieval_mode"]


def test_hybrid_analysis_reuses_search_without_generating_a_model_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries: list[str] = []
    hit = SearchHit(
        chunk=KnowledgeChunk(
            chunk_id="guide-0",
            document_id="guide",
            title="Agent 面试资料",
            source="guide.pdf",
            content="项目描述应说明业务问题与测试方法。",
            position=0,
            page_number=2,
            source_type="pdf",
            extraction_method="ocr",
        ),
        score=0.9,
    )

    class FakeHybridService:
        def search(self, query: str, *, top_k: int = 3) -> list[SearchHit]:
            queries.append(query)
            return [hit][:top_k]

        def answer(self, _question: str):
            raise AssertionError("This endpoint must not generate a model answer")

    monkeypatch.setattr(api, "get_rag_service", lambda: FakeHybridService())
    response = client.post(
        "/api/career/analyze?retrieval_mode=hybrid", json=api.ANALYSIS_EXAMPLE
    )

    assert response.status_code == 200
    result = response.json()
    assert result["retrieval_mode"] == "hybrid"
    assert result["generation_mode"] == "rules"
    assert len(queries) == 1
    assert "MCP" in queries[0]
    assert "示例同学" not in queries[0]
    assert result["knowledge_sources"][0]["source"] == "guide.pdf"
    assert result["knowledge_sources"][0]["page_number"] == 2
    assert result["knowledge_sources"][0]["extraction_method"] == "ocr"
    assert "参考来源：[资料1]" in result["report_markdown"]


def test_analysis_continues_when_no_knowledge_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "_load_current_knowledge_chunks", list)

    response = client.post("/api/career/analyze", json=api.ANALYSIS_EXAMPLE)

    assert response.status_code == 200
    result = response.json()
    assert result["match_result"]["score"] == 85
    assert result["knowledge_sources"] == []
    assert len(result["warnings"]) == 1
    assert "未保留可引用资料" in result["report_markdown"]


def test_keyword_analysis_sees_new_uploads_without_model_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    knowledge_directory = tmp_path / "knowledge"
    knowledge_directory.mkdir()
    monkeypatch.setattr(api, "KNOWLEDGE_DIRECTORY", knowledge_directory)
    monkeypatch.setattr(api, "UPLOADED_KNOWLEDGE_STORE", InMemoryKnowledgeStore())
    path = tmp_path / "uploaded-guide.md"
    path.write_text(
        "简历优化 面试准备 Agent 开发工程师 Python RAG FastAPI LangGraph MCP。"
        "项目介绍要说明业务目标、技术选择和测试方法。",
        encoding="utf-8",
    )

    before = client.post("/api/career/analyze", json=api.ANALYSIS_EXAMPLE).json()
    assert before["knowledge_sources"] == []
    api.ingest_knowledge_file(path)
    after = client.post("/api/career/analyze", json=api.ANALYSIS_EXAMPLE)

    assert after.status_code == 200
    assert after.json()["knowledge_sources"][0]["source"] == "uploaded-guide.md"


def test_analysis_logs_lengths_and_request_id_instead_of_resume_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="career_pilot.api"):
        response = client.post("/api/career/analyze", json=api.ANALYSIS_EXAMPLE)

    assert response.status_code == 200
    assert "resume_length=" in caplog.text
    assert "elapsed_ms=" in caplog.text
    assert response.json()["request_id"] in caplog.text
    assert "示例同学" not in caplog.text
    assert "示例科技" not in caplog.text


def test_invalid_hybrid_configuration_returns_a_sanitized_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_settings():
        raise ValueError("configuration error containing private values")

    monkeypatch.setattr(api, "get_rag_service", invalid_settings)
    response = client.post(
        "/api/career/analyze?retrieval_mode=hybrid", json=api.ANALYSIS_EXAMPLE
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "混合检索配置无效，请检查大模型与 Embedding 配置。"
    }


@pytest.mark.parametrize(
    ("error_type", "upstream_status", "expected_status"),
    [
        (AuthenticationError, 401, 503),
        (RateLimitError, 429, 429),
        (APIStatusError, 500, 502),
    ],
)
def test_analysis_uses_existing_upstream_error_handlers(
    error_type: type[APIStatusError],
    upstream_status: int,
    expected_status: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_response = httpx.Response(
        upstream_status, request=httpx.Request("POST", "https://example.com/v1")
    )
    error = error_type("private upstream error", response=upstream_response, body=None)

    def unavailable_service():
        raise error

    monkeypatch.setattr(api, "get_rag_service", unavailable_service)
    response = client.post(
        "/api/career/analyze?retrieval_mode=hybrid", json=api.ANALYSIS_EXAMPLE
    )

    assert response.status_code == expected_status
    assert "private upstream error" not in response.text


def test_analysis_maps_connection_failure_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_service():
        raise APIConnectionError(request=httpx.Request("POST", "https://example.com"))

    monkeypatch.setattr(api, "get_rag_service", unavailable_service)
    response = client.post(
        "/api/career/analyze?retrieval_mode=hybrid", json=api.ANALYSIS_EXAMPLE
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "暂时无法连接大模型服务，请稍后重试。"


def test_unexpected_analysis_failure_returns_a_request_id_not_internal_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_analysis(_request, *, retriever):
        raise RuntimeError("private internal error")

    monkeypatch.setattr(api, "run_career_analysis", fail_analysis)
    response = client.post("/api/career/analyze", json=api.ANALYSIS_EXAMPLE)

    assert response.status_code == 500
    assert "请求编号：" in response.json()["detail"]
    assert "private internal error" not in response.text


def test_openapi_includes_an_editable_example_and_typed_analysis_response() -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/career/analyze"]["post"]
    content = operation["requestBody"]["content"]["application/json"]

    assert content["examples"]["agent_developer"]["value"] == api.ANALYSIS_EXAMPLE
    response_schema = operation["responses"]["200"]["content"]["application/json"]
    assert response_schema["schema"]["$ref"].endswith("CareerAnalysisResponse")
