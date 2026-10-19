from career_pilot.models import (
    JobProfile,
    MatchResult,
    ResumeProfile,
    SkillEvidence,
)
from career_pilot.skill_names import canonical_skill_key

REQUIRED_SKILL_WEIGHT = 70
PREFERRED_SKILL_WEIGHT = 30


def _skill_key(skill: str) -> str:
    """Create a normalized key used for skill comparison."""
    return canonical_skill_key(skill)


def scoring_weights(has_required: bool, has_preferred: bool) -> tuple[int, int]:
    if has_required and has_preferred:
        return REQUIRED_SKILL_WEIGHT, PREFERRED_SKILL_WEIGHT
    if has_required:
        return 100, 0
    if has_preferred:
        return 0, 100
    return 0, 0


def _collect_resume_skill_evidence(
    resume: ResumeProfile,
) -> dict[str, list[SkillEvidence]]:
    evidence_by_skill: dict[str, list[SkillEvidence]] = {}

    for skill in resume.skills:
        key = _skill_key(skill)
        if not key:
            continue

        evidence_by_skill.setdefault(key, []).append(
            SkillEvidence(
                skill=skill,
                source_type="skills_section",
                source_name="技能栏",
                excerpt=f"技能栏：{skill}",
            )
        )

    for project in resume.projects:
        for skill in project.technologies:
            key = _skill_key(skill)
            if not key:
                continue

            evidence_by_skill.setdefault(key, []).append(
                SkillEvidence(
                    skill=skill,
                    source_type="project",
                    source_name=project.name,
                    excerpt=f"{project.name}：{project.description}",
                )
            )

    return evidence_by_skill


def _compare_skills(
    requirements: list[str],
    resume_skill_keys: set[str],
) -> tuple[list[str], list[str], float]:
    matched: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    for skill in requirements:
        key = _skill_key(skill)

        if not key or key in seen:
            continue

        seen.add(key)

        if key in resume_skill_keys:
            matched.append(skill)
        else:
            missing.append(skill)

    total = len(matched) + len(missing)
    coverage = len(matched) / total if total else 0.0

    return matched, missing, coverage


def _select_evidence(
    matched_skills: list[str],
    evidence_by_skill: dict[str, list[SkillEvidence]],
) -> list[SkillEvidence]:
    selected: list[SkillEvidence] = []
    seen: set[tuple[str, str, str]] = set()

    for skill in matched_skills:
        key = _skill_key(skill)

        for evidence in evidence_by_skill.get(key, []):
            identity = (
                evidence.skill,
                evidence.source_type,
                evidence.source_name,
            )

            if identity in seen:
                continue

            seen.add(identity)
            selected.append(evidence)

    return selected


def calculate_match(
    resume: ResumeProfile,
    job: JobProfile,
) -> MatchResult:
    """Calculate a deterministic and explainable skill match."""
    evidence_by_skill = _collect_resume_skill_evidence(resume)
    resume_skill_keys = set(evidence_by_skill)

    matched_required, missing_required, required_coverage = _compare_skills(
        job.required_skills,
        resume_skill_keys,
    )
    matched_preferred, missing_preferred, preferred_coverage = _compare_skills(
        job.preferred_skills,
        resume_skill_keys,
    )

    required_weight, preferred_weight = scoring_weights(
        bool(matched_required or missing_required),
        bool(matched_preferred or missing_preferred),
    )
    score = round(
        required_coverage * required_weight + preferred_coverage * preferred_weight,
        2,
    )

    matched_skills = matched_required + matched_preferred
    skill_evidence = _select_evidence(
        matched_skills,
        evidence_by_skill,
    )

    return MatchResult(
        score=score,
        required_coverage=required_coverage,
        preferred_coverage=preferred_coverage,
        matched_required_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        missing_preferred_skills=missing_preferred,
        skill_evidence=skill_evidence,
    )
