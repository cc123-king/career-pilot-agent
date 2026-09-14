"""Resume and job-description parsing tools."""

from __future__ import annotations

import re
from pathlib import Path

from .models import JobProfile, ResumeProfile
from .text_utils import extract_skills, nonempty_lines, normalize_space, unique


class DocumentParseError(ValueError):
    """Raised when an uploaded resume cannot be converted to text."""


def read_document(path_value: str | Path) -> str:
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        raise DocumentParseError(f"找不到文件：{path}")

    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == ".docx":
            from docx import Document

            document = Document(str(path))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        elif suffix in {".txt", ".md"}:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="gb18030")
        else:
            raise DocumentParseError("仅支持 PDF、DOCX、TXT 和 Markdown 文件。")
    except DocumentParseError:
        raise
    except Exception as exc:  # pragma: no cover - depends on third-party file parsing
        raise DocumentParseError(f"读取简历失败：{exc}") from exc

    text = normalize_space(text)
    if len(text) < 20:
        raise DocumentParseError(
            "没有提取到足够文字。若这是扫描版 PDF，请先进行 OCR，或将简历内容粘贴到文本框。"
        )
    return text


SECTION_HEADINGS = {
    "education": ("教育经历", "教育背景", "education"),
    "experiences": ("工作经历", "实习经历", "工作经验", "experience", "employment"),
    "projects": ("项目经历", "科研经历", "项目经验", "projects", "research"),
    "achievements": ("获奖", "证书", "荣誉", "achievements", "awards", "certificates"),
}

STOP_HEADINGS = (
    "技能",
    "专业技能",
    "技术栈",
    "个人信息",
    "个人总结",
    "自我评价",
    "skills",
    "summary",
)


def _heading_kind(line: str) -> str | None:
    cleaned = re.sub(r"[\s:：|/\\-]", "", line).lower()
    if len(cleaned) > 18:
        return None
    for kind, headings in SECTION_HEADINGS.items():
        if any(re.sub(r"\s", "", heading.lower()) in cleaned for heading in headings):
            return kind
    if any(re.sub(r"\s", "", heading.lower()) == cleaned for heading in STOP_HEADINGS):
        return "__stop__"
    return None


def _extract_sections(lines: list[str]) -> dict[str, list[str]]:
    sections = {key: [] for key in SECTION_HEADINGS}
    current: str | None = None
    for line in lines:
        heading = _heading_kind(line)
        if heading:
            current = None if heading == "__stop__" else heading
            continue
        if current and len(line) >= 4:
            sections[current].append(line)
    return {key: value[:12] for key, value in sections.items()}


def parse_resume(text: str) -> ResumeProfile:
    text = normalize_space(text)
    lines = nonempty_lines(text)
    if not lines:
        raise DocumentParseError("简历文本为空。")

    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    phone_match = re.search(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", text)
    name = "未识别"
    for line in lines[:6]:
        candidate = re.sub(r"\s+", "", line)
        if (
            2 <= len(candidate) <= 20
            and "简历" not in candidate
            and "resume" not in candidate.lower()
            and "@" not in candidate
            and not re.search(r"\d{4,}", candidate)
        ):
            name = line
            break

    sections = _extract_sections(lines)
    fallback_education = [
        line
        for line in lines
        if any(word in line.lower() for word in ("大学", "学院", "本科", "硕士", "博士", "university", "bachelor", "master"))
    ]

    return ResumeProfile(
        name=name,
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(0) if phone_match else "",
        education=unique(sections["education"] or fallback_education)[:8],
        skills=extract_skills(text),
        experiences=unique(sections["experiences"])[:12],
        projects=unique(sections["projects"])[:12],
        achievements=unique(sections["achievements"])[:8],
        raw_summary="\n".join(lines[:18])[:1200],
    )


def parse_job_description(text: str, company: str = "", role: str = "") -> JobProfile:
    text = normalize_space(text)
    lines = nonempty_lines(text)
    if len(text) < 20:
        raise ValueError("招聘 JD 内容过短，请粘贴完整的岗位描述。")

    all_skills = extract_skills(text)
    preferred_lines = [
        line
        for line in lines
        if any(word in line.lower() for word in ("加分", "优先", "preferred", "plus", "nice to have"))
    ]
    in_preferred_section = False
    for line in lines:
        compact = re.sub(r"[\s:：]", "", line).lower()
        if compact in {"加分项", "优先条件", "preferredqualifications", "nicetohave"}:
            in_preferred_section = True
            continue
        if compact in {"岗位职责", "工作职责", "任职要求", "职位要求", "responsibilities", "requirements"}:
            in_preferred_section = False
            continue
        if in_preferred_section:
            preferred_lines.append(line)
    required_lines = [
        line
        for line in lines
        if any(word in line.lower() for word in ("要求", "必须", "熟悉", "掌握", "精通", "required", "must", "proficient"))
    ]
    preferred = extract_skills("\n".join(preferred_lines))
    required = [skill for skill in extract_skills("\n".join(required_lines)) if skill not in preferred]
    if not required:
        required = [skill for skill in all_skills if skill not in preferred]

    responsibilities = [
        line
        for line in lines
        if any(word in line.lower() for word in ("负责", "参与", "设计", "开发", "构建", "responsib", "design", "develop", "build"))
    ][:10]

    experience_match = re.search(
        r"(?:至少|具有|拥有)?\s*(\d+\s*[-–至]\s*\d+|\d+)\s*年(?:以上)?[^。；\n]{0,15}(?:经验|工作)|(?:[1-9]\+?\s*years?)",
        text,
        flags=re.IGNORECASE,
    )
    education_line = next(
        (
            line
            for line in lines
            if any(word in line.lower() for word in ("本科", "硕士", "博士", "学历", "bachelor", "master", "phd"))
        ),
        "未明确",
    )

    inferred_role = role.strip()
    if not inferred_role:
        inferred_role = next(
            (line for line in lines[:8] if any(word in line.lower() for word in ("工程师", "开发", "算法", "agent", "engineer"))),
            "目标岗位",
        )

    return JobProfile(
        role=inferred_role,
        company=company.strip() or "目标公司",
        required_skills=unique(required),
        preferred_skills=unique(preferred),
        responsibilities=unique(responsibilities),
        experience_requirement=experience_match.group(0) if experience_match else "未明确",
        education_requirement=education_line,
        keywords=unique(all_skills),
    )
