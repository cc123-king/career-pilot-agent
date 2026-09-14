"""Explainable resume-to-job matching logic."""

from __future__ import annotations

from .models import JobProfile, MatchReport, ResumeProfile, ScoreBreakdown, SkillEvidence
from .text_utils import TRANSFERABLE_SKILLS, find_skill_evidence


def _percentage(numerator: int, denominator: int, default: int = 50) -> int:
    if denominator <= 0:
        return default
    return round(100 * numerator / denominator)


def match_resume_to_job(
    resume: ResumeProfile,
    job: JobProfile,
    resume_text: str,
) -> MatchReport:
    resume_skills = set(resume.skills)
    required = job.required_skills or job.keywords
    preferred = job.preferred_skills

    matched = [skill for skill in required if skill in resume_skills]
    missing = [skill for skill in required if skill not in resume_skills]
    preferred_matches = [skill for skill in preferred if skill in resume_skills]

    transferable: list[str] = []
    for missing_skill in missing:
        related = [skill for skill in TRANSFERABLE_SKILLS.get(missing_skill, ()) if skill in resume_skills]
        if related:
            transferable.append(f"{missing_skill} ← 可迁移能力：{', '.join(related)}")

    evidence = [
        SkillEvidence(skill=skill, evidence=find_skill_evidence(resume_text, skill))
        for skill in matched
    ]
    evidenced_count = sum(bool(item.evidence) for item in evidence)

    required_score = _percentage(len(matched), len(required))
    preferred_score = _percentage(len(preferred_matches), len(preferred), default=60)
    keyword_matches = len(set(job.keywords) & resume_skills)
    keyword_score = _percentage(keyword_matches, len(job.keywords), default=50)
    evidence_score = _percentage(evidenced_count, len(matched), default=20)

    overall = round(
        required_score * 0.55
        + preferred_score * 0.15
        + keyword_score * 0.15
        + evidence_score * 0.15
    )
    overall = max(0, min(overall, 100))

    risk_flags: list[str] = []
    if not resume.projects and not resume.experiences:
        risk_flags.append("未识别到明确的项目或工作经历，招聘方难以验证技能。")
    if missing:
        risk_flags.append(f"核心要求中仍有 {len(missing)} 项未在简历中出现。")
    if job.experience_requirement != "未明确" and not resume.experiences:
        risk_flags.append(f"JD 提到“{job.experience_requirement}”，但简历中未识别到工作/实习经历。")
    if matched and evidence_score < 70:
        risk_flags.append("虽然列出了部分技能，但项目描述中的使用证据不足。")
    if not job.required_skills:
        risk_flags.append("JD 没有清晰区分必备技能，当前分数主要基于关键词覆盖。")

    if overall >= 80:
        summary = "匹配度较高，可以优先投递；投递前应针对 JD 调整项目描述顺序。"
    elif overall >= 60:
        summary = "具备一定匹配基础，建议补强缺失关键词并突出可迁移的项目证据。"
    else:
        summary = "当前匹配度偏低，建议先补一个针对性项目或选择要求更接近的岗位。"

    return MatchReport(
        overall_score=overall,
        matched_skills=matched,
        missing_skills=missing,
        preferred_matches=preferred_matches,
        transferable_skills=transferable,
        breakdown=ScoreBreakdown(
            required_skills=required_score,
            preferred_skills=preferred_score,
            keyword_coverage=keyword_score,
            evidence_quality=evidence_score,
        ),
        evidence=evidence,
        risk_flags=risk_flags,
        summary=summary,
    )

