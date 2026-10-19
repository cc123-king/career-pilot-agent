import re

from career_pilot.models import (
    JobProfile,
    ProjectEvidence,
    ResumeProfile,
)
from career_pilot.text_utils import normalize_text

HEADING_ALIASES = {
    "个人简介": "summary",
    "简介": "summary",
    "summary": "summary",
    "技能": "skills",
    "技术栈": "skills",
    "skills": "skills",
    "教育经历": "education",
    "教育背景": "education",
    "education": "education",
    "工作经历": "experience",
    "工作经验": "experience",
    "experience": "experience",
    "项目经历": "projects",
    "项目经验": "projects",
    "projects": "projects",
    "岗位职责": "responsibilities",
    "工作职责": "responsibilities",
    "responsibilities": "responsibilities",
    "任职要求": "required",
    "必备技能": "required",
    "required skills": "required",
    "加分项": "preferred",
    "优先条件": "preferred",
    "preferred skills": "preferred",
}


def _heading_name(line: str) -> str | None:
    """Return the internal name of a recognized section heading."""
    cleaned = line.strip().lstrip("#").strip()
    cleaned = cleaned.rstrip(":：").strip()
    return HEADING_ALIASES.get(cleaned.lower())


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"root": []}
    current = "root"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = _heading_name(line)
        if heading is not None:
            current = heading
            sections.setdefault(current, [])
            continue

        sections.setdefault(current, []).append(line)

    return sections


def _split_items(lines: list[str]) -> list[str]:
    items: list[str] = []

    for line in lines:
        parts = re.split(r"[,，、;；|/]+", line)
        for part in parts:
            value = normalize_text(part)
            if value and value not in items:
                items.append(value)

    return items


def _parse_project(line: str) -> ProjectEvidence | None:
    name, separator, content = line.partition("：")
    if not separator:
        name, separator, content = line.partition(":")

    if not separator:
        return None

    technology_match = re.search(
        r"(?:技术栈|技术|technologies)\s*[:：]\s*(.+)$",
        content,
        flags=re.IGNORECASE,
    )

    technologies: list[str] = []
    if technology_match:
        technologies = _split_items([technology_match.group(1)])
        content = content[: technology_match.start()].rstrip("；; ")

    description = normalize_text(content)
    if len(description) < 10:
        return None

    return ProjectEvidence(
        name=normalize_text(name),
        description=description,
        technologies=technologies,
    )


def parse_resume_text(text: str) -> ResumeProfile:
    sections = _split_sections(text)
    root_lines = sections["root"]

    candidate_name = root_lines[0] if root_lines else None
    summary_lines = sections.get("summary", [])
    projects = [
        project
        for line in sections.get("projects", [])
        if (project := _parse_project(line)) is not None
    ]

    return ResumeProfile(
        candidate_name=candidate_name,
        summary=normalize_text(" ".join(summary_lines)) or None,
        skills=_split_items(sections.get("skills", [])),
        education=sections.get("education", []),
        work_experience=sections.get("experience", []),
        projects=projects,
    )


def parse_job_text(text: str, company: str, role: str) -> JobProfile:
    sections = _split_sections(text)
    required = _split_items(sections.get("required", []))
    preferred = _split_items(sections.get("preferred", []))

    keywords: list[str] = []
    for item in required + preferred:
        if item not in keywords:
            keywords.append(item)

    return JobProfile(
        company=company,
        role=role,
        responsibilities=sections.get("responsibilities", []),
        required_skills=required,
        preferred_skills=preferred,
        keywords=keywords,
    )
