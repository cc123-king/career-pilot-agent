"""Human-readable report rendering and export."""

from __future__ import annotations

import re
from pathlib import Path

from .models import AnalysisResult, ApplicationRecord


def _items(values: list[str], empty: str = "暂无") -> str:
    return "、".join(values) if values else empty


def _safe_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_analysis_markdown(result: AnalysisResult) -> str:
    report = result.match_report
    profile = result.resume_profile
    job = result.job_profile
    lines = [
        f"# {job.company} · {job.role} 人岗匹配报告",
        "",
        f"> 综合匹配度：**{report.overall_score}/100**　运行模式：`{result.mode}`",
        "",
        report.summary,
        "",
        "## 分项得分",
        "",
        "| 维度 | 得分 |",
        "|---|---:|",
        f"| 必备技能覆盖 | {report.breakdown.required_skills} |",
        f"| 加分技能覆盖 | {report.breakdown.preferred_skills} |",
        f"| JD 关键词覆盖 | {report.breakdown.keyword_coverage} |",
        f"| 项目证据质量 | {report.breakdown.evidence_quality} |",
        "",
        "## 简历画像",
        "",
        f"- 姓名：{profile.name}",
        f"- 已识别技能：{_items(profile.skills)}",
        f"- 教育信息：{_items(profile.education)}",
        f"- 项目条目数：{len(profile.projects)}；工作/实习条目数：{len(profile.experiences)}",
        "",
        "## 岗位画像",
        "",
        f"- 必备技能：{_items(job.required_skills)}",
        f"- 加分技能：{_items(job.preferred_skills)}",
        f"- 经验要求：{job.experience_requirement}",
        f"- 学历要求：{job.education_requirement}",
        "",
        "## 匹配结论",
        "",
        f"- 已匹配：{_items(report.matched_skills)}",
        f"- 待补齐：{_items(report.missing_skills)}",
        f"- 可迁移能力：{_items(report.transferable_skills)}",
    ]

    if report.risk_flags:
        lines.extend(["", "### 风险提示", ""])
        lines.extend(f"- {flag}" for flag in report.risk_flags)

    lines.extend(["", "## 简历优化建议", "", "| 优先级 | 位置 | 问题 | 建议 | 安全示例 |", "|---|---|---|---|---|"])
    for item in result.advice:
        lines.append(
            f"| {item.priority} | {_safe_cell(item.section)} | {_safe_cell(item.issue)} | "
            f"{_safe_cell(item.suggestion)} | {_safe_cell(item.safe_example)} |"
        )

    if result.llm_enhancement:
        lines.extend(
            [
                "",
                "## 大模型个性化增强",
                "",
                result.llm_enhancement.executive_summary,
                "",
                *[f"- {item}" for item in result.llm_enhancement.personalized_advice],
            ]
        )

    lines.extend(["", "## 模拟面试题", ""])
    for index, question in enumerate(result.interview_questions, 1):
        lines.extend(
            [
                f"### {index}. [{question.category}] {question.question}",
                "",
                f"- 为什么问：{question.why_asked}",
                f"- 回答框架：{question.answer_framework}",
                "",
            ]
        )

    if result.knowledge_references:
        lines.extend(["## RAG 检索参考", ""])
        for reference in result.knowledge_references:
            lines.append(
                f"- **{reference.title}**（相关度 {reference.relevance:.2f}）：{reference.excerpt}"
            )

    lines.extend(["", "## Agent 执行轨迹", ""])
    lines.extend(f"- {step}" for step in result.workflow_trace)
    if result.warnings:
        lines.extend(["", "## 运行警告", "", *[f"- {warning}" for warning in result.warnings]])
    lines.extend(
        [
            "",
            "---",
            "本报告只基于简历和 JD 中已有的信息，不应据此编造任何经历、数据或技能。",
        ]
    )
    return "\n".join(lines)


def export_analysis(result: AnalysisResult, output_dir: str | Path) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    raw_name = f"{result.job_profile.company}-{result.job_profile.role}-{result.run_id[:8]}"
    safe_name = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", raw_name).strip("-")
    path = output_path / f"{safe_name or 'career-report'}.md"
    path.write_text(render_analysis_markdown(result), encoding="utf-8")
    return path


def applications_table(records: list[ApplicationRecord]) -> list[list[object]]:
    return [
        [
            record.id,
            record.company,
            record.role,
            record.status,
            record.match_score,
            record.resume_name,
            record.updated_at,
            record.notes,
        ]
        for record in records
    ]

