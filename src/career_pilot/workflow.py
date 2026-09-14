"""LangGraph orchestration for the specialist career agents."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .agents import generate_advice, generate_interview_questions
from .config import Settings
from .knowledge import LocalKnowledgeBase
from .llm import LLMEnhancer
from .matching import match_resume_to_job
from .models import (
    AdviceItem,
    InterviewQuestion,
    JobProfile,
    KnowledgeReference,
    LLMEnhancement,
    MatchReport,
    ResumeProfile,
)
from .parsers import parse_job_description, parse_resume


class CareerState(TypedDict, total=False):
    resume_text: str
    jd_text: str
    company: str
    role: str
    resume_profile: ResumeProfile
    job_profile: JobProfile
    match_report: MatchReport
    advice: list[AdviceItem]
    interview_questions: list[InterviewQuestion]
    knowledge_references: list[KnowledgeReference]
    llm_enhancement: LLMEnhancement | None
    workflow_trace: list[str]
    warnings: list[str]
    mode: str


def _next_trace(state: CareerState, label: str) -> list[str]:
    return [*state.get("workflow_trace", []), label]


def build_workflow(settings: Settings):
    knowledge_base = LocalKnowledgeBase(settings.knowledge_path)
    enhancer = LLMEnhancer(settings)

    def resume_agent(state: CareerState) -> dict[str, Any]:
        return {
            "resume_profile": parse_resume(state["resume_text"]),
            "workflow_trace": _next_trace(state, "1. ResumeAgent：解析简历并提取结构化信息"),
        }

    def job_agent(state: CareerState) -> dict[str, Any]:
        return {
            "job_profile": parse_job_description(
                state["jd_text"], state.get("company", ""), state.get("role", "")
            ),
            "workflow_trace": _next_trace(state, "2. JobAgent：解析 JD 和岗位要求"),
        }

    def rag_agent(state: CareerState) -> dict[str, Any]:
        profile = state["resume_profile"]
        job = state["job_profile"]
        query = " ".join([job.role, *profile.skills, *job.required_skills, *job.preferred_skills])
        return {
            "knowledge_references": knowledge_base.search(query),
            "workflow_trace": _next_trace(state, "3. RAGAgent：检索本地求职知识库"),
        }

    def matching_agent(state: CareerState) -> dict[str, Any]:
        report = match_resume_to_job(
            state["resume_profile"], state["job_profile"], state["resume_text"]
        )
        return {
            "match_report": report,
            "workflow_trace": _next_trace(state, "4. MatchAgent：计算可解释的人岗匹配度"),
        }

    def advice_agent(state: CareerState) -> dict[str, Any]:
        return {
            "advice": generate_advice(
                state["resume_profile"], state["job_profile"], state["match_report"]
            ),
            "workflow_trace": _next_trace(state, "5. ResumeCoachAgent：生成防编造的简历建议"),
        }

    def interview_agent(state: CareerState) -> dict[str, Any]:
        return {
            "interview_questions": generate_interview_questions(
                state["resume_profile"], state["job_profile"], state["match_report"]
            ),
            "workflow_trace": _next_trace(state, "6. InterviewAgent：生成针对性面试题"),
        }

    def route_after_interview(_: CareerState) -> str:
        return "enhance" if settings.ai_enabled else "finalize"

    def llm_agent(state: CareerState) -> dict[str, Any]:
        try:
            enhancement = enhancer.enhance(
                state["resume_profile"], state["job_profile"], state["match_report"]
            )
            return {
                "llm_enhancement": enhancement,
                "workflow_trace": _next_trace(state, "7. LLMAgent：生成个性化增强建议"),
            }
        except Exception as exc:
            return {
                "llm_enhancement": None,
                "warnings": [*state.get("warnings", []), f"大模型增强失败，已降级到规则模式：{exc}"],
                "workflow_trace": _next_trace(state, "7. LLMAgent：调用失败，自动降级"),
            }

    def finalize_agent(state: CareerState) -> dict[str, Any]:
        mode = settings.llm_provider if settings.ai_enabled else "demo"
        return {
            "mode": mode,
            "workflow_trace": _next_trace(state, "8. ReportAgent：汇总最终报告"),
        }

    graph = StateGraph(CareerState)
    graph.add_node("resume", resume_agent)
    graph.add_node("job", job_agent)
    graph.add_node("rag", rag_agent)
    graph.add_node("match", matching_agent)
    graph.add_node("advice", advice_agent)
    graph.add_node("interview", interview_agent)
    graph.add_node("enhance", llm_agent)
    graph.add_node("finalize", finalize_agent)

    graph.add_edge(START, "resume")
    graph.add_edge("resume", "job")
    graph.add_edge("job", "rag")
    graph.add_edge("rag", "match")
    graph.add_edge("match", "advice")
    graph.add_edge("advice", "interview")
    graph.add_conditional_edges(
        "interview", route_after_interview, {"enhance": "enhance", "finalize": "finalize"}
    )
    graph.add_edge("enhance", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()

