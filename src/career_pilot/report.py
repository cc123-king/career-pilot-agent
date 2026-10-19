"""Render workflow results as Markdown and optionally save them locally."""

from collections.abc import Sequence
from html import escape
from pathlib import Path
from uuid import uuid4

from career_pilot.matching import scoring_weights
from career_pilot.models import (
    InterviewQuestion,
    JobProfile,
    MatchResult,
    ResumeAdvice,
    ResumeProfile,
    SkillEvidence,
)
from career_pilot.rag.models import ContextSource
from career_pilot.text_utils import normalize_text

REPORT_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "reports"


def _text(value: str) -> str:
    """Keep user-provided text from becoming Markdown or raw HTML markup."""

    value = escape(normalize_text(value), quote=False).replace("\\", "\\\\")
    for character in "`*_{}[]()#+!|~-":
        value = value.replace(character, "\\" + character)
    return value


def _skills(skills: Sequence[str], empty_label: str) -> str:
    return "、".join(_text(skill) for skill in skills) if skills else empty_label


def _evidence_lines(evidence: Sequence[SkillEvidence]) -> list[str]:
    lines: list[str] = []
    for item in evidence:
        label = "项目记录" if item.source_type == "project" else "技能栏声明"
        lines.extend(
            [
                f"简历证据（{label} / {_text(item.source_name)}）：",
                "",
                f"> {_text(item.excerpt)}",
                "",
            ]
        )
    return lines


def generate_markdown_report(
    resume: ResumeProfile,
    job: JobProfile,
    match: MatchResult,
    advice: Sequence[ResumeAdvice],
    interview_questions: Sequence[InterviewQuestion],
    *,
    knowledge_sources: Sequence[ContextSource] = (),
    warnings: Sequence[str] = (),
    workflow_trace: Sequence[str] = (),
) -> str:
    """Assemble existing results without recalculating scores or inventing facts."""

    weights = scoring_weights(
        bool(match.matched_required_skills or match.missing_required_skills),
        bool(match.matched_preferred_skills or match.missing_preferred_skills),
    )
    lines = [
        "# CareerPilot 求职分析报告",
        "",
        "## 1. 分析对象",
        "",
        f"- 候选人：{_text(resume.candidate_name or '未识别姓名')}",
        f"- 公司：{_text(job.company)}",
        f"- 岗位：{_text(job.role)}",
        "",
        "本报告基于输入简历和岗位的解析结果。简历记录不等于已核实的经历。",
        "当前建议与面试问题由规则生成；参考资料不能作为候选人的个人经历。",
        "",
        "## 2. 岗位匹配",
        "",
        f"- 匹配分数：{match.score:.2f} / 100",
        f"- 本次评分权重：必需项 {weights[0]}%，加分项 {weights[1]}%",
        (
            f"- 必备技能覆盖率：{match.required_coverage:.1%}"
            if weights[0]
            else "- 必备技能覆盖率：不适用（未设置必需项）"
        ),
        (
            f"- 加分技能覆盖率：{match.preferred_coverage:.1%}"
            if weights[1]
            else "- 加分技能覆盖率：不适用（未设置加分项）"
        ),
        "",
        "这是既定技能覆盖规则得分，不代表录用概率。报告沿用匹配节点的结果。",
        "未识别到岗位技能要求时，应先核对原文和解析结果。",
        "",
        "- 已匹配必备技能：" + _skills(match.matched_required_skills, "暂无命中"),
        "- 未找到证据的必备技能："
        + _skills(
            match.missing_required_skills,
            "未发现缺失" if job.required_skills else "未识别到必备技能要求",
        ),
        "- 已匹配加分技能：" + _skills(match.matched_preferred_skills, "暂无命中"),
        "- 未找到证据的加分技能："
        + _skills(
            match.missing_preferred_skills,
            "未发现缺失" if job.preferred_skills else "未识别到加分技能要求",
        ),
        "",
        "### 匹配证据",
        "",
    ]
    lines.extend(_evidence_lines(match.skill_evidence))
    if not match.skill_evidence:
        lines.extend(["没有可展示的匹配证据，请检查输入与解析结果。", ""])

    lines.extend(["## 3. 简历改进建议", ""])
    priority_labels = {"high": "高", "medium": "中", "low": "低"}
    sources_by_id = {source.citation_id: source for source in knowledge_sources}
    for index, item in enumerate(advice, start=1):
        lines.extend(
            [
                f"### {index}. [{priority_labels[item.priority]}] {_text(item.title)}",
                "",
                f"- 原因：{_text(item.reason)}",
                f"- 建议：{_text(item.suggestion)}",
                "",
                *_evidence_lines(item.resume_evidence),
            ]
        )
        if item.citation_id is not None:
            if item.citation_id not in sources_by_id:
                lines.extend(["参考来源未保留，无法核对该建议的引用。", ""])
                continue
            lines.extend([f"参考来源：[资料{item.citation_id}]，见资料来源章节。", ""])
            if item.knowledge_excerpt:
                lines.extend(["参考原文（非候选人经历）：", ""])
                lines.extend(
                    "> " + _text(line) for line in item.knowledge_excerpt.splitlines()
                )
                lines.append("")
    if not advice:
        lines.extend(["暂无简历建议。", ""])

    lines.extend(["## 4. 面试准备", "", "回答要点是准备思路，不是代写的个人经历。", ""])
    category_labels = {
        "general": "自我介绍",
        "project": "项目细节",
        "matched_skill": "技能理解",
        "skill_gap": "能力补足",
    }
    for index, item in enumerate(interview_questions, start=1):
        lines.extend(
            [
                f"### {index}. [{category_labels[item.category]}] {_text(item.question)}",
                "",
                "考察原因：" + _text(item.reason),
                "",
                "回答要点：",
                "",
                *(f"- {_text(point)}" for point in item.answer_points),
                "",
            ]
        )
        if item.follow_ups:
            lines.extend(
                ["追问：", "", *(f"- {_text(point)}" for point in item.follow_ups), ""]
            )
        lines.extend(_evidence_lines(item.resume_evidence))
    if not interview_questions:
        lines.extend(["暂无面试问题。", ""])

    lines.extend(["## 5. 资料来源", ""])
    for source in knowledge_sources:
        lines.extend(
            [
                f"### [资料{source.citation_id}] {_text(source.title)}",
                "",
                "- 来源：" + _text(source.source),
                "- 分块：" + _text(source.chunk_id),
                f"- 检索得分：{source.score:.3f}（不代表答案正确率）",
            ]
        )
        if source.page_number is not None:
            lines.append(f"- 页码：{source.page_number}")
        if source.source_type is not None:
            lines.append("- 文件类型：" + _text(source.source_type))
        if source.extraction_method is not None:
            label = {"native_text": "原生文本", "ocr": "OCR"}[source.extraction_method]
            lines.append("- 提取方式：" + label)
        lines.append("")
    if not knowledge_sources:
        lines.extend(["未保留可引用资料，当前结果仅基于简历和岗位解析。", ""])

    lines.extend(["## 6. 提醒与执行记录", ""])
    lines.extend(f"- 提醒：{_text(warning)}" for warning in warnings)
    if not warnings:
        lines.append("本次流程没有额外提醒；这不等于内容已通过真实性审核。")
    if workflow_trace:
        lines.extend(["", "执行记录：", ""])
        lines.extend(
            f"{index}. {_text(step)}" for index, step in enumerate(workflow_trace, 1)
        )

    return "\n".join(lines).rstrip() + "\n"


def save_markdown_report(
    report_markdown: str, *, directory: str | Path = REPORT_DIRECTORY
) -> Path:
    """Save UTF-8 Markdown using an exclusive filename to preserve prior reports."""

    if not report_markdown.strip():
        raise ValueError("报告内容不能为空")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"career-report-{uuid4().hex}.md"
    with path.open("x", encoding="utf-8", newline="\n") as file:
        file.write(report_markdown)
    return path


def render_requirement_scope(scope: dict) -> str:
    """Render all extracted requirements, including documented exclusions."""
    labels = {"required_skills": "必需", "preferred_skills": "加分"}
    decisions = {"confirmed": "确认要求", "excluded": "排除误提取", "pending": "待核实"}
    lines = [
        "## 岗位要求核对范围",
        "",
        f"提取 {scope['total_count']} 项：确认 {scope['confirmed_count']} 项，排除 {scope['excluded_count']} 项，待核实 {scope['pending_count']} 项。",
        "",
        "分数仅基于下列已确认的技能要求；排除项不计入分母。已核对全部提取项不代表已证明完整理解岗位正文。",
        "",
    ]
    for entry in scope["entries"]:
        lines.append(
            f"- {decisions[entry['decision']]}｜{labels[entry['field'].split('.')[0]]}：{_text(entry['value'])}"
        )
        lines.append(f"  原文：{_text(entry['quote'])}")
        if entry["decision"] == "excluded":
            lines.append(f"  排除原因：{_text(entry['reason'])}")
    return "\n".join(lines) + "\n\n"
