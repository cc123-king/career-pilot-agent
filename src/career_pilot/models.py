"""Typed data contracts shared by the workflow, API, UI, and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ResumeProfile(BaseModel):
    name: str = "未识别"
    email: str = ""
    phone: str = ""
    education: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experiences: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    raw_summary: str = ""


class JobProfile(BaseModel):
    role: str = "目标岗位"
    company: str = "目标公司"
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    experience_requirement: str = "未明确"
    education_requirement: str = "未明确"
    keywords: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    required_skills: int = Field(ge=0, le=100)
    preferred_skills: int = Field(ge=0, le=100)
    keyword_coverage: int = Field(ge=0, le=100)
    evidence_quality: int = Field(ge=0, le=100)


class SkillEvidence(BaseModel):
    skill: str
    evidence: list[str] = Field(default_factory=list)


class MatchReport(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    preferred_matches: list[str] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    breakdown: ScoreBreakdown
    evidence: list[SkillEvidence] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    summary: str = ""


class AdviceItem(BaseModel):
    priority: Literal["高", "中", "低"]
    section: str
    issue: str
    suggestion: str
    safe_example: str


class InterviewQuestion(BaseModel):
    category: Literal["项目深挖", "技术基础", "技能差距", "行为面试"]
    question: str
    why_asked: str
    answer_framework: str
    related_skills: list[str] = Field(default_factory=list)


class KnowledgeReference(BaseModel):
    title: str
    excerpt: str
    relevance: float = Field(ge=0.0, le=1.0)


class LLMEnhancement(BaseModel):
    executive_summary: str
    personalized_advice: list[str] = Field(default_factory=list, max_length=5)
    interview_focus: list[str] = Field(default_factory=list, max_length=5)


class AnalysisResult(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default_factory=utc_now_iso)
    mode: str = "demo"
    resume_profile: ResumeProfile
    job_profile: JobProfile
    match_report: MatchReport
    advice: list[AdviceItem] = Field(default_factory=list)
    interview_questions: list[InterviewQuestion] = Field(default_factory=list)
    knowledge_references: list[KnowledgeReference] = Field(default_factory=list)
    llm_enhancement: LLMEnhancement | None = None
    workflow_trace: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApplicationCreate(BaseModel):
    company: str
    role: str
    status: str = "准备投递"
    match_score: int = Field(default=0, ge=0, le=100)
    resume_name: str = ""
    jd_excerpt: str = ""
    notes: str = ""


class ApplicationRecord(ApplicationCreate):
    id: int
    created_at: str
    updated_at: str

