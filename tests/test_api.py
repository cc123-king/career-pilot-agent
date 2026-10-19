import httpx
import pytest
from fastapi.testclient import TestClient
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from career_pilot.api import app
from career_pilot.api import get_validated_rag_service as get_rag_service
from career_pilot.rag.models import (
    ContextSource,
    RAGAnswer,
)

client = TestClient(app)


class FakeRAGService:
    def __init__(self) -> None:
        self.last_question: str | None = None

    def answer(self, question: str) -> RAGAnswer:
        self.last_question = question

        return RAGAnswer(
            question=question,
            answer="应介绍业务问题、系统架构和测试结果。[资料1]",
            sources=[
                ContextSource(
                    citation_id=1,
                    chunk_id="interview-0",
                    title="Agent岗位面试指南",
                    source="interview_guidance.md",
                    score=0.8,
                )
            ],
            retrieved_count=1,
            used_model=True,
        )


class ErrorRAGService:
    """A fake service that raises a configured error."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def answer(self, _question: str) -> RAGAnswer:
        raise self._error


def post_question_with_service(
    service: FakeRAGService | ErrorRAGService,
    question: str = "面试时怎样介绍Agent项目？",
) -> httpx.Response:
    app.dependency_overrides[get_rag_service] = lambda: service

    try:
        return client.post(
            "/api/rag/ask",
            json={"question": question},
        )
    finally:
        app.dependency_overrides.clear()


def build_status_error(
    error_type: type[APIStatusError],
    status_code: int,
) -> APIStatusError:
    request = httpx.Request(
        "POST",
        "https://example.com/v1/chat/completions",
    )
    response = httpx.Response(
        status_code=status_code,
        request=request,
    )

    return error_type(
        "simulated upstream error",
        response=response,
        body=None,
    )


def test_health_check_returns_service_information() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "career-pilot-agent",
        "version": "0.1.0",
    }


def test_ask_rag_question_returns_grounded_answer() -> None:
    fake_service = FakeRAGService()

    app.dependency_overrides[get_rag_service] = lambda: fake_service

    try:
        response = client.post(
            "/api/rag/ask",
            json={"question": "面试时怎样介绍Agent项目？"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["used_model"] is True
    assert result["retrieved_count"] == 1
    assert result["sources"][0]["citation_id"] == 1
    assert "[资料1]" in result["answer"]
    assert fake_service.last_question == ("面试时怎样介绍Agent项目？")


def test_ask_rag_question_rejects_blank_question() -> None:
    fake_service = FakeRAGService()

    response = post_question_with_service(
        fake_service,
        question="   ",
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == [
        "body",
        "question",
    ]
    assert fake_service.last_question is None


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            build_status_error(AuthenticationError, 401),
            503,
            "大模型认证失败，请联系管理员检查 API Key。",
        ),
        (
            build_status_error(RateLimitError, 429),
            429,
            "大模型请求过于频繁，请稍后重试。",
        ),
        (
            APIConnectionError(
                message="simulated connection error",
                request=httpx.Request(
                    "POST",
                    "https://example.com/v1/chat/completions",
                ),
            ),
            503,
            "暂时无法连接大模型服务，请稍后重试。",
        ),
        (
            build_status_error(APIStatusError, 500),
            502,
            "大模型服务返回异常，请稍后重试。",
        ),
    ],
    ids=[
        "authentication-error",
        "rate-limit-error",
        "connection-error",
        "api-status-error",
    ],
)
def test_ask_rag_question_maps_model_errors(
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    response = post_question_with_service(ErrorRAGService(error))

    assert response.status_code == expected_status
    assert response.json() == {
        "detail": expected_detail,
    }
