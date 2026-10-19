import logging
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)
from pydantic import Field, field_validator

from career_pilot.history import PersistentKnowledgeStore
from career_pilot.llm import LLMClient, load_llm_settings
from career_pilot.models import (
    AnalysisRequest,
    InterviewQuestion,
    JobProfile,
    MatchResult,
    ResumeAdvice,
    ResumeProfile,
    StrictModel,
)
from career_pilot.multimodal.loader import load_document
from career_pilot.multimodal.models import SourceType
from career_pilot.rag.cache import SnapshotCache, snapshot_fingerprint
from career_pilot.rag.documents import (
    chunk_document,
    load_knowledge_documents,
)
from career_pilot.rag.embeddings import (
    EmbeddingClient,
    load_embedding_settings,
)
from career_pilot.rag.factory import DEFAULT_RAG_CONFIG, create_grounded_rag_service
from career_pilot.rag.models import ContextSource, KnowledgeChunk, RAGAnswer
from career_pilot.rag.retrieval import KeywordRetriever
from career_pilot.rag.service import ChunkRetriever, RAGService
from career_pilot.workflow import run_career_analysis

logger = logging.getLogger(__name__)
RetrievalMode = Literal["keyword", "hybrid"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIRECTORY = PROJECT_ROOT / "knowledge"
ENV_FILE = PROJECT_ROOT / ".env"
UPLOADED_KNOWLEDGE_STORE = PersistentKnowledgeStore()

ANALYSIS_EXAMPLE = {
    "resume_text": (
        "示例同学\n个人简介\n正在学习 Python 和 Agent 应用开发。\n"
        "技能\nPython、FastAPI、RAG\n项目经历\n"
        "CareerPilot Agent：使用多节点工作流分析简历和岗位要求。技术栈：LangGraph"
    ),
    "job_description": (
        "岗位职责\n负责 Agent 应用开发、知识检索和后端接口维护\n"
        "任职要求\nPython、RAG、FastAPI\n加分项\nLangGraph、MCP"
    ),
    "company": "示例科技",
    "role": "Agent 开发工程师",
}


class CareerAnalysisResponse(StrictModel):
    """Validated career-analysis results exposed to API and UI consumers."""

    request_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    retrieval_mode: RetrievalMode
    generation_mode: Literal["rules"] = "rules"
    resume_profile: ResumeProfile
    job_profile: JobProfile
    match_result: MatchResult
    advice: list[ResumeAdvice]
    interview_questions: list[InterviewQuestion]
    knowledge_sources: list[ContextSource]
    workflow_trace: list[str]
    warnings: list[str]
    report_markdown: str = Field(min_length=1)


class HealthResponse(StrictModel):
    """Health information returned by the API."""

    status: Literal["ok"]
    service: str
    version: str


class RAGQuestionRequest(StrictModel):
    """A user question submitted to the RAG service."""

    question: str = Field(min_length=1, max_length=2_000)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        """Reject empty or whitespace-only questions."""

        normalized_question = value.strip()

        if not normalized_question:
            raise ValueError("问题不能为空")

        return normalized_question


class KnowledgeUploadResult(StrictModel):
    """Summary returned after a document is ingested."""

    filename: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    page_count: int = Field(ge=1)
    chunk_count: int = Field(ge=1)
    total_document_count: int = Field(ge=1)
    total_chunk_count: int = Field(ge=1)


app = FastAPI(
    title="CareerPilot Agent API",
    description="API for career analysis and grounded RAG answers.",
    version="0.1.0",
)


def _load_current_knowledge_chunks() -> list[KnowledgeChunk]:
    """Read built-in knowledge plus a snapshot of the current uploads."""

    if KNOWLEDGE_DIRECTORY.is_dir() and not any(KNOWLEDGE_DIRECTORY.glob("*.md")):
        return UPLOADED_KNOWLEDGE_STORE.list_chunks()
    documents = load_knowledge_documents(KNOWLEDGE_DIRECTORY)
    chunks = [
        chunk
        for document in documents
        for chunk in chunk_document(
            document, max_characters=RAG_RETRIEVAL_CONFIG["max_characters"]
        )
    ]
    return chunks + UPLOADED_KNOWLEDGE_STORE.list_chunks()


REVIEW_RETRIEVAL_CONFIG = {
    "top_k": 3,
    "min_score": 0.05,
    "candidate_k": 6,
    "fusion_weight": 0.7,
    "lexical_weight": 0.3,
    "rank_constant": 60,
}


# Frozen from development evidence coverage before test metrics were inspected.
RAG_RETRIEVAL_CONFIG = dict(DEFAULT_RAG_CONFIG)


def retrieval_configuration(mode: RetrievalMode) -> dict:
    keys = REVIEW_RETRIEVAL_CONFIG if mode == "hybrid" else ("top_k", "min_score")
    return {
        "mode": mode,
        "pipeline_version": "career-review-v3",
        "max_characters": 300,
        **{k: REVIEW_RETRIEVAL_CONFIG[k] for k in keys},
    }


_RAG_SERVICE_CACHE = SnapshotCache()


def get_rag_service() -> RAGService:
    """Invalidate the service when knowledge, upload data or configuration changes."""
    chunks = _load_current_knowledge_chunks()
    llm_settings = load_llm_settings(ENV_FILE)
    embedding_settings = load_embedding_settings(ENV_FILE)
    key = snapshot_fingerprint(
        chunks,
        {"review": REVIEW_RETRIEVAL_CONFIG, "rag": RAG_RETRIEVAL_CONFIG},
        llm_settings,
        embedding_settings,
    )
    return _RAG_SERVICE_CACHE.get_or_create(
        key, lambda: _create_rag_service(chunks, llm_settings, embedding_settings)
    )


def _create_rag_service(chunks, llm_settings, embedding_settings) -> RAGService:
    return create_grounded_rag_service(
        chunks,
        LLMClient(llm_settings),
        EmbeddingClient(embedding_settings),
        configuration=RAG_RETRIEVAL_CONFIG,
    )


# Preserve the clearing hook used by uploads and existing integrations.
get_rag_service.cache_clear = _RAG_SERVICE_CACHE.clear


def get_validated_rag_service(request: RAGQuestionRequest) -> RAGService:
    """Resolve expensive dependencies only after the question passes validation."""
    return get_rag_service()


def get_career_retriever(retrieval_mode: RetrievalMode) -> ChunkRetriever:
    """Select retrieval only after the API has validated the request."""

    if retrieval_mode == "hybrid":
        try:
            return get_rag_service()
        except ValueError:
            logger.error("career_retriever_configuration_failed")
            raise HTTPException(
                status_code=503,
                detail="混合检索配置无效，请检查大模型与 Embedding 配置。",
            ) from None
    return KeywordRetriever(_load_current_knowledge_chunks())


def ingest_knowledge_file(
    path: str | Path,
) -> KnowledgeUploadResult:
    """Extract, chunk, and register an uploaded document."""

    document = load_document(path)
    added_chunks = UPLOADED_KNOWLEDGE_STORE.add_document(document)

    get_rag_service.cache_clear()

    return KnowledgeUploadResult(
        filename=document.filename,
        source_type=document.source_type,
        page_count=len(document.pages),
        chunk_count=len(added_chunks),
        total_document_count=(UPLOADED_KNOWLEDGE_STORE.document_count),
        total_chunk_count=(UPLOADED_KNOWLEDGE_STORE.chunk_count),
    )


@app.exception_handler(AuthenticationError)
async def handle_authentication_error(
    _request: Request,
    _error: AuthenticationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "大模型认证失败，请联系管理员检查 API Key。"},
    )


@app.exception_handler(RateLimitError)
async def handle_rate_limit_error(
    _request: Request,
    _error: RateLimitError,
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "大模型请求过于频繁，请稍后重试。"},
    )


@app.exception_handler(APIConnectionError)
async def handle_connection_error(
    _request: Request,
    _error: APIConnectionError,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "暂时无法连接大模型服务，请稍后重试。"},
    )


@app.exception_handler(APIStatusError)
async def handle_api_status_error(
    _request: Request,
    _error: APIStatusError,
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": "大模型服务返回异常，请稍后重试。"},
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
)
def health_check() -> HealthResponse:
    """Report whether the API process is running."""

    return HealthResponse(
        status="ok",
        service="career-pilot-agent",
        version=app.version,
    )


@app.post(
    "/api/rag/ask",
    response_model=RAGAnswer,
    tags=["rag"],
)
def ask_rag_question(
    request: RAGQuestionRequest,
    rag_service: Annotated[
        RAGService,
        Depends(get_validated_rag_service),
    ],
) -> RAGAnswer:
    """Answer one question using the project knowledge base."""

    return rag_service.answer(request.question)


@app.post(
    "/api/career/analyze",
    response_model=CareerAnalysisResponse,
    tags=["career"],
    summary="Analyze a resume against a job and produce a career report",
)
def analyze_career(
    request: Annotated[
        AnalysisRequest,
        Body(
            openapi_examples={
                "agent_developer": {
                    "summary": "Agent 开发岗位的示例分析",
                    "value": ANALYSIS_EXAMPLE,
                }
            }
        ),
    ],
    retrieval_mode: RetrievalMode = "keyword",
) -> CareerAnalysisResponse:
    """Return a complete analysis without automatically saving personal data."""

    request_id = uuid4().hex[:12]
    started_at = perf_counter()
    logger.info(
        "career_analysis_started request_id=%s retrieval_mode=%s "
        "resume_length=%d job_length=%d",
        request_id,
        retrieval_mode,
        len(request.resume_text),
        len(request.job_description),
    )
    try:
        retriever = get_career_retriever(retrieval_mode)
        result = run_career_analysis(request, retriever=retriever)
        response = CareerAnalysisResponse(
            request_id=request_id,
            retrieval_mode=retrieval_mode,
            resume_profile=result["resume_profile"],
            job_profile=result["job_profile"],
            match_result=result["match_result"],
            advice=result["advice"],
            interview_questions=result["interview_questions"],
            knowledge_sources=result["knowledge_context"].sources,
            workflow_trace=result["workflow_trace"],
            warnings=result["warnings"],
            report_markdown=result["report_markdown"],
        )
    except (APIConnectionError, APIStatusError, HTTPException):
        logger.warning("career_analysis_unavailable request_id=%s", request_id)
        raise
    except Exception:
        logger.exception("career_analysis_failed request_id=%s", request_id)
        raise HTTPException(
            status_code=500,
            detail=f"求职分析失败，请查看服务端日志。请求编号：{request_id}",
        ) from None

    logger.info(
        "career_analysis_finished request_id=%s node_count=%d "
        "source_count=%d elapsed_ms=%.2f",
        request_id,
        len(response.workflow_trace),
        len(response.knowledge_sources),
        (perf_counter() - started_at) * 1_000,
    )
    return response


def _register_review_routes():
    from career_pilot.review import install_routes

    install_routes(app)


_register_review_routes()
