from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model shared by all strictly validated project models."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class AnalysisRequest(StrictModel):
    """Input data required to analyze a resume against a job."""

    resume_text: str = Field(min_length=20, max_length=50_000)
    job_description: str = Field(min_length=20, max_length=20_000)
    company: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)


class ProjectEvidence(StrictModel):
    """A project found in the candidate's resume."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=10, max_length=2_000)
    technologies: list[str] = Field(default_factory=list, max_length=50)


class ResumeProfile(StrictModel):
    """Structured information extracted from a resume."""

    candidate_name: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=1_000)
    skills: list[str] = Field(default_factory=list, max_length=100)
    education: list[str] = Field(default_factory=list, max_length=20)
    work_experience: list[str] = Field(default_factory=list, max_length=50)
    projects: list[ProjectEvidence] = Field(default_factory=list, max_length=30)


class JobProfile(StrictModel):
    """Structured requirements extracted from a job description."""

    company: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    responsibilities: list[str] = Field(default_factory=list, max_length=50)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=100)


class SkillEvidence(StrictModel):
    """Traceable resume evidence for a matched skill."""

    skill: str = Field(min_length=1, max_length=100)
    source_type: Literal["skills_section", "project"]
    source_name: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(min_length=1, max_length=2_500)


class MatchResult(StrictModel):
    """Explainable skill-matching result."""

    score: float = Field(ge=0, le=100)
    required_coverage: float = Field(ge=0, le=1)
    preferred_coverage: float = Field(ge=0, le=1)
    matched_required_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    skill_evidence: list[SkillEvidence] = Field(default_factory=list)


class ResumeAdvice(StrictModel):
    """An actionable suggestion with separate resume and knowledge evidence."""

    category: Literal[
        "skill_gap",
        "strengthen_evidence",
        "highlight_project",
        "resume_structure",
        "knowledge_reference",
    ]
    priority: Literal["high", "medium", "low"]
    title: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=2_000)
    suggestion: str = Field(min_length=1, max_length=3_000)
    related_skills: list[str] = Field(default_factory=list)
    resume_evidence: list[SkillEvidence] = Field(default_factory=list)
    citation_id: int | None = Field(default=None, ge=1)
    knowledge_excerpt: str | None = Field(default=None, max_length=10_000)


class InterviewQuestion(StrictModel):
    """An interview prompt with preparation points and traceable resume evidence."""

    category: Literal["project", "matched_skill", "skill_gap", "general"]
    question: str = Field(min_length=1, max_length=1_000)
    reason: str = Field(min_length=1, max_length=2_000)
    answer_points: list[str] = Field(min_length=1, max_length=8)
    follow_ups: list[str] = Field(default_factory=list, max_length=5)
    related_skills: list[str] = Field(default_factory=list)
    resume_evidence: list[SkillEvidence] = Field(default_factory=list)
