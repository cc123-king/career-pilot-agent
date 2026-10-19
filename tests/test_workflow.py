import pytest

from career_pilot.models import AnalysisRequest
from career_pilot.rag.hybrid_retrieval import (
    HybridCandidateRetriever,
    HybridRetriever,
)
from career_pilot.rag.models import KnowledgeChunk, SearchHit
from career_pilot.rag.reranking import ScoreFusionReranker
from career_pilot.workflow import build_career_workflow, run_career_analysis

RESUME_TEXT = """示例候选人
个人简介
苏州大学研究生，关注 AI Agent 应用开发。
技能
Python、FastAPI、RAG
项目经历
CareerPilot Agent：使用多 Agent 工作流分析简历和岗位要求。技术栈：LangGraph
"""


JOB_TEXT = """岗位职责
负责 AI Agent 应用开发和维护
任职要求
Python、RAG、FastAPI
加分项
LangGraph、MCP
"""


def test_workflow_runs_agents_in_order() -> None:
    result = run_career_analysis(
        AnalysisRequest(
            resume_text=RESUME_TEXT,
            job_description=JOB_TEXT,
            company="示例科技",
            role="Agent 开发工程师",
        )
    )

    assert result["resume_profile"].candidate_name == "示例候选人"
    assert result["job_profile"].company == "示例科技"
    assert result["match_result"].matched_required_skills == [
        "Python",
        "RAG",
        "FastAPI",
    ]
    assert result["match_result"].matched_preferred_skills == [
        "LangGraph"
    ]
    assert result["workflow_trace"] == [
        "ResumeAgent: parsed the resume",
        "JobAgent: parsed the job description",
        "RAGAgent: retrieved career knowledge",
        "MatchAgent: calculated the explainable match",
        "ResumeCoachAgent: generated evidence-based resume advice",
        "InterviewAgent: generated evidence-based interview questions",
        "ReportAgent: assembled the career report",
    ]
    assert result["knowledge_context"].sources
    assert result["warnings"] == []
    assert any(item.category == "highlight_project" for item in result["advice"])
    assert any(item.category == "project" for item in result["interview_questions"])
    assert "匹配分数：85.00 / 100" in result["report_markdown"]
    assert "## 4. 面试准备" in result["report_markdown"]
    assert "ReportAgent: assembled the career report" in result["report_markdown"]


def test_workflow_preserves_missing_skill_information() -> None:
    result = run_career_analysis(
        AnalysisRequest(
            resume_text=RESUME_TEXT,
            job_description=JOB_TEXT,
            company="示例科技",
            role="Agent 开发工程师",
        )
    )

    assert result["match_result"].missing_preferred_skills == ["MCP"]
    assert result["match_result"].score == 85
    assert any(item.related_skills == ["MCP"] for item in result["advice"])
    mcp_question = next(
        item for item in result["interview_questions"] if item.related_skills == ["MCP"]
    )
    assert mcp_question.category == "skill_gap"
    assert mcp_question.resume_evidence == []


class FakeRetriever:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.queries: list[str] = []

    def search(self, query: str, *, top_k: int = 3) -> list[SearchHit]:
        self.queries.append(query)
        return self.hits[:top_k]


def make_request() -> AnalysisRequest:
    return AnalysisRequest(
        resume_text=RESUME_TEXT,
        job_description=JOB_TEXT,
        company="示例科技",
        role="Agent 开发工程师",
    )


def make_knowledge_hit(score: float) -> SearchHit:
    return SearchHit(
        chunk=KnowledgeChunk(
            chunk_id="career-guide-0",
            document_id="career-guide",
            title="Agent 面试资料",
            source="career-guide.pdf",
            content="简历优化和面试准备需要说明 Python、RAG 和 LangGraph 项目证据。",
            position=0,
            page_number=2,
            source_type="pdf",
            extraction_method="ocr",
        ),
        score=score,
    )


def test_workflow_uses_hybrid_retrieval_and_preserves_citations() -> None:
    hit = make_knowledge_hit(0.9)
    vector_searcher = FakeRetriever([hit])
    retriever = HybridRetriever(
        HybridCandidateRetriever([hit.chunk], vector_searcher),
        reranker=ScoreFusionReranker(),
    )

    result = run_career_analysis(make_request(), retriever=retriever)

    query = result["knowledge_query"]
    assert vector_searcher.queries == [query]
    assert "MCP" in query
    assert "LangGraph" in query
    assert query.count("Python") == 1
    assert "示例候选人" not in query
    source = result["knowledge_context"].sources[0]
    assert source.source == "career-guide.pdf"
    assert source.page_number == 2
    assert source.extraction_method == "ocr"
    assert "[资料1]" in result["knowledge_context"].content
    assert result["match_result"].score == 85
    reference = next(
        item for item in result["advice"] if item.category == "knowledge_reference"
    )
    assert reference.citation_id == source.citation_id
    assert reference.knowledge_excerpt == hit.chunk.content
    assert "### [资料1] Agent 面试资料" in result["report_markdown"]
    assert "来源：career\\-guide.pdf" in result["report_markdown"]
    assert "页码：2" in result["report_markdown"]
    assert "提取方式：OCR" in result["report_markdown"]


@pytest.mark.parametrize("hits", [[], [make_knowledge_hit(0.01)]])
def test_workflow_continues_matching_when_knowledge_is_insufficient(
    hits: list[SearchHit],
) -> None:
    result = run_career_analysis(make_request(), retriever=FakeRetriever(hits))

    assert result["knowledge_context"].sources == []
    assert "信息不足" in result["knowledge_context"].content
    assert len(result["warnings"]) == 1
    assert result["match_result"].score == 85
    assert result["advice"]
    assert result["interview_questions"]
    assert all(item.citation_id is None for item in result["advice"])
    assert "提醒：知识库证据不足" in result["report_markdown"]
    assert "未保留可引用资料" in result["report_markdown"]


@pytest.mark.parametrize(
    "settings",
    [{"top_k": 0}, {"min_score": -0.1}, {"min_score": 1.1}],
)
def test_workflow_rejects_invalid_retrieval_configuration(settings) -> None:
    with pytest.raises(ValueError):
        build_career_workflow(retriever=FakeRetriever([]), **settings)
