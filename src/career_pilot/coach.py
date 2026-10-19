"""Rule-based resume coaching grounded in matching and retrieved evidence."""

from collections.abc import Sequence

from career_pilot.models import (
    JobProfile,
    MatchResult,
    ResumeAdvice,
    ResumeProfile,
    SkillEvidence,
)
from career_pilot.rag.models import ContextSource, SearchHit
from career_pilot.skill_names import canonical_skill_key


def generate_resume_advice(
    resume: ResumeProfile,
    job: JobProfile,
    match: MatchResult,
    *,
    knowledge_hits: Sequence[SearchHit] = (),
    knowledge_sources: Sequence[ContextSource] = (),
) -> list[ResumeAdvice]:
    """Suggest edits while preserving the candidate's existing facts."""

    advice: list[ResumeAdvice] = []

    for skills, priority, requirement in (
        (match.missing_required_skills, "high", "必备技能"),
        (match.missing_preferred_skills, "medium", "加分技能"),
    ):
        for skill in skills:
            advice.append(
                ResumeAdvice(
                    category="skill_gap",
                    priority=priority,
                    title=f"核实并补充 {skill} 的真实证据",
                    reason=(
                        f"{job.role}将 {skill} 列为{requirement}，"
                        "当前解析结果中未找到对应技能证据。"
                    ),
                    suggestion=(
                        "先检查简历是否漏写了已有实践；如果确有相关经历，"
                        "补充使用场景、本人负责的工作和可验证结果。"
                        "如果尚未实践，将其列入学习计划，完成验证后再写入简历。"
                    ),
                    related_skills=[skill],
                )
            )

    project_evidence: dict[str, list[SkillEvidence]] = {}
    project_skill_keys: set[str] = set()
    for evidence in match.skill_evidence:
        if evidence.source_type == "project":
            project_evidence.setdefault(evidence.source_name, []).append(evidence)
            project_skill_keys.add(canonical_skill_key(evidence.skill))

    seen_skills: set[str] = set()
    for evidence in match.skill_evidence:
        key = canonical_skill_key(evidence.skill)
        if evidence.source_type != "skills_section":
            continue
        if key in project_skill_keys or key in seen_skills:
            continue
        seen_skills.add(key)
        advice.append(
            ResumeAdvice(
                category="strengthen_evidence",
                priority="medium",
                title=f"为 {evidence.skill} 补充项目使用场景",
                reason="当前技能命中来自技能栏，尚未找到对应的项目技术栈证据。",
                suggestion=(
                    "检查已有项目中是否使用过该技术。若确实使用过，"
                    "补充具体模块、技术选择理由和测试方式；"
                    "若没有项目实践，保持技能描述与实际掌握程度一致。"
                ),
                related_skills=[evidence.skill],
                resume_evidence=[evidence.model_copy(deep=True)],
            )
        )

    for project_name, evidence_items in project_evidence.items():
        skills = list(dict.fromkeys(item.skill for item in evidence_items))
        advice.append(
            ResumeAdvice(
                category="highlight_project",
                priority="medium",
                title=f"突出项目：{project_name}",
                reason="该项目的技术栈与岗位要求匹配，已有原文证据可以支持表述。",
                suggestion=(
                    "保留已有项目事实，围绕业务目标、本人负责的模块、"
                    "关键方案和验证方式整理描述。结果只填写实际测试或记录的数据。"
                ),
                related_skills=skills,
                resume_evidence=[item.model_copy(deep=True) for item in evidence_items],
            )
        )

    if not resume.projects:
        advice.append(
            ResumeAdvice(
                category="resume_structure",
                priority="medium",
                title="检查项目经历是否成功解析",
                reason="当前结构化简历中没有识别到项目经历。",
                suggestion=(
                    "检查原文是否包含“项目经历”章节，以及项目名称、描述和技术栈。"
                    "只补充真实完成的项目；若原文已有内容，先修正格式或解析问题。"
                ),
            )
        )

    if not job.required_skills and not job.preferred_skills:
        advice.append(
            ResumeAdvice(
                category="resume_structure",
                priority="high",
                title="检查岗位技能要求是否成功解析",
                reason="当前岗位画像中没有识别到必备技能或加分技能。",
                suggestion=(
                    "核对 JD 的“任职要求”和“加分项”章节，确认技能提取结果。"
                    "要求不明确时，先补充岗位信息再判断匹配程度。"
                ),
            )
        )

    # Cite only retained context sources; keep reference text separate from experience.
    hits_by_id = {hit.chunk.chunk_id: hit for hit in knowledge_hits}
    for source in knowledge_sources:
        hit = hits_by_id.get(source.chunk_id)
        if hit is None:
            continue
        advice.append(
            ResumeAdvice(
                category="knowledge_reference",
                priority="low",
                title=f"参考资料：{source.title}",
                reason=f"检索到求职参考资料，来源：{source.source}。",
                suggestion=(
                    "参考下方原文检查项目描述和面试准备。"
                    "资料中的案例与技术要求不能作为本人经历写入简历。"
                ),
                citation_id=source.citation_id,
                knowledge_excerpt=hit.chunk.content,
            )
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    advice.sort(key=lambda item: priority_order[item.priority])
    return advice
