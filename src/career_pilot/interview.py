"""Rule-based interview preparation grounded in job and resume evidence."""

from career_pilot.models import (
    InterviewQuestion,
    JobProfile,
    MatchResult,
    ResumeProfile,
    SkillEvidence,
)
from career_pilot.skill_names import canonical_skill_key


def _skill_key(skill: str) -> str:
    return canonical_skill_key(skill)


def _project_question(
    project_name: str, evidence: list[SkillEvidence]
) -> InterviewQuestion:
    skills = list(dict.fromkeys(item.skill for item in evidence))
    return InterviewQuestion(
        category="project",
        question=f"请介绍 {project_name} 的业务目标、你负责的模块和关键技术选择。",
        reason="简历中的项目技术栈与岗位要求匹配，需要进一步核实实现过程。",
        answer_points=[
            "结合项目原文说明要解决的问题、输入和输出。",
            "区分本人完成的工作与团队或开源组件提供的能力。",
            "说明技术选择理由、模块之间的数据流和验证方法。",
            "只引用实际运行记录或测试数据；没有量化结果时说明验证过程。",
        ],
        follow_ups=[
            "开发时遇到过什么具体问题？如何定位并验证修复效果？",
            "如果重新实现这个项目，你会优先改进哪个环节？为什么？",
        ],
        related_skills=skills,
        resume_evidence=[item.model_copy(deep=True) for item in evidence],
    )


def generate_interview_questions(
    resume: ResumeProfile,
    job: JobProfile,
    match: MatchResult,
    *,
    max_questions: int = 8,
) -> list[InterviewQuestion]:
    """Prepare bounded questions, prioritizing required over preferred skills."""

    if not 1 <= max_questions <= 20:
        raise ValueError("max_questions 必须在 1 到 20 之间")

    questions = [
        InterviewQuestion(
            category="general",
            question=f"请做一个面向 {job.role} 岗位的简短自我介绍。",
            reason="了解候选人的背景、真实经历与岗位目标之间的联系。",
            answer_points=[
                "根据简历说明教育或工作背景，不补写不存在的经历。",
                (
                    "挑选一个真实项目，概括业务目标、本人贡献和验证方式。"
                    if resume.projects
                    else "说明已掌握的知识和练习；若没有项目经历，明确说明。"
                ),
                "说明与岗位相关的优势，并区分已完成实践和后续学习计划。",
            ],
            follow_ups=["目前最希望补足哪项能力？准备怎样验证学习效果？"],
        )
    ]

    evidence_by_skill: dict[str, list[SkillEvidence]] = {}
    project_evidence: dict[str, list[SkillEvidence]] = {}
    for evidence in match.skill_evidence:
        evidence_by_skill.setdefault(_skill_key(evidence.skill), []).append(evidence)
        if evidence.source_type == "project":
            project_evidence.setdefault(evidence.source_name, []).append(evidence)

    missing_keys = {
        _skill_key(skill)
        for skill in [*match.missing_required_skills, *match.missing_preferred_skills]
    }
    seen_skills: set[str] = set()
    seen_projects: set[str] = set()

    for skill in [*job.required_skills, *job.preferred_skills]:
        if len(questions) >= max_questions:
            break
        key = _skill_key(skill)
        if not key or key in seen_skills:
            continue
        seen_skills.add(key)
        evidence = evidence_by_skill.get(key, [])

        if key in missing_keys:
            questions.append(
                InterviewQuestion(
                    category="skill_gap",
                    question=f"你如何理解 {skill}？如果需要补足这项能力，会怎样学习和验证？",
                    reason=f"岗位要求涉及 {skill}，当前解析结果中未找到对应简历证据。",
                    answer_points=[
                        "先核对是否存在解析遗漏，如实说明自己的掌握程度。",
                        "解释已理解的概念和用途，不把计划说成已完成的项目。",
                        "提出一个最小练习，说明输入、预期输出和验收方法。",
                    ],
                    follow_ups=[f"如果要在一个应用中尝试 {skill}，你会先验证什么？"],
                    related_skills=[skill],
                )
            )
            continue

        projects = [item for item in evidence if item.source_type == "project"]
        if projects:
            for item in projects:
                if len(questions) >= max_questions:
                    break
                if item.source_name in seen_projects:
                    continue
                seen_projects.add(item.source_name)
                questions.append(
                    _project_question(
                        item.source_name, project_evidence[item.source_name]
                    )
                )
        elif evidence:
            questions.append(
                InterviewQuestion(
                    category="matched_skill",
                    question=f"请解释 {skill} 的主要用途。如果用它设计一个模块，你会如何验证？",
                    reason="该技能命中来自技能栏，尚未找到对应的项目技术栈证据。",
                    answer_points=[
                        "用自己的语言说明概念和适用场景。",
                        "提出一个假设的设计，明确输入、输出和失败情况。",
                        "说明正常与异常测试方式；如有真实实践，再补充可核对的证据。",
                    ],
                    follow_ups=[f"什么情况下你不会选择 {skill}？有哪些替代方案？"],
                    related_skills=[skill],
                    resume_evidence=[item.model_copy(deep=True) for item in evidence],
                )
            )

    return questions
