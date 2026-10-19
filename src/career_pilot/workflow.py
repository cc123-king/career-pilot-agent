"""LangGraph workflow for resume and job analysis."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from career_pilot.coach import generate_resume_advice
from career_pilot.interview import generate_interview_questions
from career_pilot.matching import calculate_match
from career_pilot.models import (
    AnalysisRequest,
    InterviewQuestion,
    JobProfile,
    MatchResult,
    ResumeAdvice,
    ResumeProfile,
)
from career_pilot.parsers import parse_job_text, parse_resume_text
from career_pilot.rag.context import build_retrieval_context
from career_pilot.rag.documents import chunk_document, load_knowledge_documents
from career_pilot.rag.models import RetrievalContext, SearchHit
from career_pilot.rag.retrieval import search_chunks
from career_pilot.rag.service import ChunkRetriever
from career_pilot.report import generate_markdown_report
from career_pilot.text_utils import normalize_text

KNOWLEDGE_DIRECTORY = Path(__file__).resolve().parents[2] / "knowledge"


class CareerState(TypedDict, total=False):
    """Shared state passed between the specialist Agent nodes."""

    request: AnalysisRequest
    validated_job_profile: JobProfile
    validated_resume_profile: ResumeProfile
    resume_profile: ResumeProfile
    job_profile: JobProfile
    knowledge_query: str
    knowledge_context: RetrievalContext
    knowledge_hits: list[SearchHit]
    match_result: MatchResult
    advice: list[ResumeAdvice]
    interview_questions: list[InterviewQuestion]
    report_markdown: str
    workflow_trace: list[str]
    warnings: list[str]


def _append_trace(state: CareerState, message: str) -> list[str]:
    """Return a new trace list without mutating the incoming state."""

    return [*state.get("workflow_trace", []), message]


def resume_agent(state: CareerState) -> dict[str, object]:
    """Parse the resume into a validated profile."""

    request = state["request"]
    return {
        "resume_profile": state.get("validated_resume_profile")
        or parse_resume_text(request.resume_text),
        "workflow_trace": _append_trace(
            state,
            "ResumeAgent: parsed the resume",
        ),
    }


def job_agent(state: CareerState) -> dict[str, object]:
    """Parse the job description into structured requirements."""

    request = state["request"]
    return {
        "job_profile": state.get("validated_job_profile")
        or parse_job_text(
            request.job_description,
            company=request.company,
            role=request.role,
        ),
        "workflow_trace": _append_trace(
            state,
            "JobAgent: parsed the job description",
        ),
    }


def match_agent(state: CareerState) -> dict[str, object]:
    """Calculate a deterministic, evidence-backed match result."""

    return {
        "match_result": calculate_match(
            state["resume_profile"],
            state["job_profile"],
        ),
        "workflow_trace": _append_trace(
            state,
            "MatchAgent: calculated the explainable match",
        ),
    }


def build_knowledge_query(state: CareerState) -> str:
    """Retrieve career guidance using job requirements and candidate skills."""

    job = state["job_profile"]
    resume = state["resume_profile"]
    skills = [
        *job.required_skills,
        *job.preferred_skills,
        *resume.skills,
        *(skill for project in resume.projects for skill in project.technologies),
    ]
    unique_skills: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        normalized = normalize_text(skill)
        if normalized and normalized.casefold() not in seen:
            seen.add(normalized.casefold())
            unique_skills.append(normalized)

    query = " ".join(["简历优化 面试准备", job.role, *unique_skills])
    return normalize_text(query)[:2_000]


def resume_coach_agent(state: CareerState) -> dict[str, object]:
    """Generate actionable suggestions from match and knowledge evidence."""

    return {
        "advice": generate_resume_advice(
            state["resume_profile"],
            state["job_profile"],
            state["match_result"],
            knowledge_hits=state["knowledge_hits"],
            knowledge_sources=state["knowledge_context"].sources,
        ),
        "workflow_trace": _append_trace(
            state,
            "ResumeCoachAgent: generated evidence-based resume advice",
        ),
    }


def interview_agent(state: CareerState) -> dict[str, object]:
    """Prepare interview questions without inventing candidate experience."""

    return {
        "interview_questions": generate_interview_questions(
            state["resume_profile"],
            state["job_profile"],
            state["match_result"],
        ),
        "workflow_trace": _append_trace(
            state,
            "InterviewAgent: generated evidence-based interview questions",
        ),
    }


def report_agent(state: CareerState) -> dict[str, object]:
    """Render the existing results without modifying the underlying facts."""

    trace = _append_trace(state, "ReportAgent: assembled the career report")
    return {
        "report_markdown": generate_markdown_report(
            state["resume_profile"],
            state["job_profile"],
            state["match_result"],
            state["advice"],
            state["interview_questions"],
            knowledge_sources=state["knowledge_context"].sources,
            warnings=state.get("warnings", []),
            workflow_trace=trace,
        ),
        "workflow_trace": trace,
    }


def build_career_workflow(
    *,
    retriever: ChunkRetriever | None = None,
    knowledge_directory: str | Path = KNOWLEDGE_DIRECTORY,
    top_k: int = 3,
    min_score: float = 0.05,
):
    """Build a workflow with an injectable knowledge retrieval node."""

    if top_k < 1:
        raise ValueError("top_k 必须大于等于 1")
    if not 0 <= min_score <= 1:
        raise ValueError("min_score 必须在 0 到 1 之间")

    chunks = []
    if retriever is None:
        documents = load_knowledge_documents(knowledge_directory)
        chunks = [chunk for document in documents for chunk in chunk_document(document)]

    def rag_agent(state: CareerState) -> dict[str, object]:
        query = build_knowledge_query(state)
        if retriever is None:
            hits = search_chunks(query, chunks, top_k=top_k)
        else:
            hits = retriever.search(query, top_k=top_k)

        relevant_hits = [hit for hit in hits if hit.score >= min_score]
        context = build_retrieval_context(query, relevant_hits)
        warnings = list(state.get("warnings", []))
        if not context.sources:
            warnings.append("知识库证据不足，后续建议只能基于简历和岗位信息。")

        return {
            "knowledge_query": query,
            "knowledge_context": context,
            "knowledge_hits": relevant_hits,
            "warnings": warnings,
            "workflow_trace": _append_trace(
                state,
                "RAGAgent: retrieved career knowledge",
            ),
        }

    graph = StateGraph(CareerState)
    graph.add_node("resume", resume_agent)
    graph.add_node("job", job_agent)
    graph.add_node("rag", rag_agent)
    graph.add_node("match", match_agent)
    graph.add_node("coach", resume_coach_agent)
    graph.add_node("interview", interview_agent)
    graph.add_node("report", report_agent)

    graph.add_edge(START, "resume")
    graph.add_edge("resume", "job")
    graph.add_edge("job", "rag")
    graph.add_edge("rag", "match")
    graph.add_edge("match", "coach")
    graph.add_edge("coach", "interview")
    graph.add_edge("interview", "report")
    graph.add_edge("report", END)

    return graph.compile()


def run_career_analysis(
    request: AnalysisRequest,
    *,
    retriever: ChunkRetriever | None = None,
    resume_profile: ResumeProfile | None = None,
    job_profile: JobProfile | None = None,
    top_k: int = 3,
    min_score: float = 0.05,
) -> CareerState:
    """Run analysis with local keyword or supplied hybrid retrieval."""

    workflow = build_career_workflow(
        retriever=retriever, top_k=top_k, min_score=min_score
    )
    return workflow.invoke(
        {
            "request": request,
            **(
                {"validated_resume_profile": resume_profile}
                if resume_profile is not None
                else {}
            ),
            **(
                {"validated_job_profile": job_profile}
                if job_profile is not None
                else {}
            ),
            "workflow_trace": [],
            "warnings": [],
        }
    )
