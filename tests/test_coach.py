from career_pilot.coach import generate_resume_advice
from career_pilot.matching import calculate_match
from career_pilot.models import JobProfile, ProjectEvidence, ResumeProfile
from career_pilot.rag.context import build_retrieval_context
from career_pilot.rag.models import KnowledgeChunk, SearchHit


def make_resume() -> ResumeProfile:
    return ResumeProfile(
        skills=["Python", "FastAPI"],
        projects=[
            ProjectEvidence(
                name="CareerPilot Agent",
                description="使用 LangGraph 工作流分析简历与岗位要求。",
                technologies=["LangGraph"],
            )
        ],
    )


def make_job() -> JobProfile:
    return JobProfile(
        company="示例科技",
        role="Agent 开发工程师",
        required_skills=["Python", "RAG"],
        preferred_skills=["LangGraph", "MCP"],
    )


def make_hit() -> SearchHit:
    return SearchHit(
        chunk=KnowledgeChunk(
            chunk_id="guide-0",
            document_id="guide",
            title="简历项目指南",
            source="guide.md",
            content="项目描述应说明使用场景和验证方法；岗位可能要求 MCP。",
            position=0,
        ),
        score=0.9,
    )


def test_advice_prioritizes_gaps_without_claiming_missing_skills() -> None:
    resume, job = make_resume(), make_job()
    advice = generate_resume_advice(resume, job, calculate_match(resume, job))
    gaps = [item for item in advice if item.category == "skill_gap"]

    assert [(item.related_skills, item.priority) for item in gaps] == [
        (["RAG"], "high"),
        (["MCP"], "medium"),
    ]
    assert advice[0] == gaps[0]
    assert all("未找到" in item.reason for item in gaps)
    assert all("完成验证后再写入" in item.suggestion for item in gaps)
    assert all(not item.resume_evidence and item.citation_id is None for item in gaps)


def test_advice_distinguishes_skill_list_from_existing_project_evidence() -> None:
    resume, job = make_resume(), make_job()
    match = calculate_match(resume, job)
    advice = generate_resume_advice(resume, job, match)

    skills = [item for item in advice if item.category == "strengthen_evidence"]
    assert [item.related_skills for item in skills] == [["Python"]]
    project = next(item for item in advice if item.category == "highlight_project")
    assert project.related_skills == ["LangGraph"]
    expected_evidence = next(
        item for item in match.skill_evidence if item.source_type == "project"
    )
    assert project.resume_evidence[0].excerpt == expected_evidence.excerpt
    assert project.citation_id is None


def test_knowledge_reference_quotes_exact_text_and_preserves_candidate_facts() -> None:
    resume, job = make_resume(), make_job()
    match = calculate_match(resume, job)
    before = (resume.model_dump(), job.model_dump(), match.model_dump())
    hit = make_hit()
    context = build_retrieval_context("简历优化", [hit])

    advice = generate_resume_advice(
        resume,
        job,
        match,
        knowledge_hits=[hit],
        knowledge_sources=context.sources,
    )

    reference = next(item for item in advice if item.category == "knowledge_reference")
    assert reference.citation_id == 1
    assert reference.knowledge_excerpt == hit.chunk.content
    assert reference.resume_evidence == []
    assert reference.related_skills == []
    assert all(
        evidence.skill != "MCP"
        for item in advice
        for evidence in item.resume_evidence
    )
    assert before == (resume.model_dump(), job.model_dump(), match.model_dump())


def test_advice_omits_sources_that_have_no_retained_context() -> None:
    resume, job = make_resume(), make_job()
    hit = make_hit()

    # The oversized chunk is excluded by the context budget.
    hit.chunk.content = "很长的项目描述参考资料。" * 50
    context = build_retrieval_context("简历优化", [hit], max_characters=200)
    assert context.sources == []
    advice = generate_resume_advice(
        resume,
        job,
        calculate_match(resume, job),
        knowledge_hits=[hit],
        knowledge_sources=context.sources,
    )

    assert advice
    assert all(item.citation_id is None for item in advice)


def test_advice_requests_input_check_when_parsed_profiles_are_empty() -> None:
    resume = ResumeProfile()
    job = JobProfile(company="示例科技", role="Agent 开发工程师")

    advice = generate_resume_advice(resume, job, calculate_match(resume, job))

    assert len(advice) == 2
    assert all(item.category == "resume_structure" for item in advice)
    assert advice[0].priority == "high"
    assert all(item.resume_evidence == [] and item.citation_id is None for item in advice)


def test_existing_project_evidence_avoids_duplicate_skill_only_suggestion() -> None:
    resume = make_resume()
    resume.skills.append("LangGraph")
    job = make_job()

    advice = generate_resume_advice(resume, job, calculate_match(resume, job))

    assert not any(
        item.category == "strengthen_evidence" and item.related_skills == ["LangGraph"]
        for item in advice
    )
    assert sum(item.category == "highlight_project" for item in advice) == 1
