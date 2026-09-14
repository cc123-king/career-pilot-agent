"""Deterministic specialist agents used in demo mode and as LLM guardrails."""

from __future__ import annotations

from .models import AdviceItem, InterviewQuestion, JobProfile, MatchReport, ResumeProfile


def generate_advice(
    resume: ResumeProfile,
    job: JobProfile,
    report: MatchReport,
) -> list[AdviceItem]:
    advice: list[AdviceItem] = []

    for skill in report.missing_skills[:4]:
        advice.append(
            AdviceItem(
                priority="高",
                section="技能差距",
                issue=f"JD 要求 {skill}，简历中没有可验证证据。",
                suggestion=(
                    f"不要直接把 {skill} 填进技能栏。先完成一个可运行的小功能，"
                    "再把代码链接、使用场景和测试结果写入项目经历。"
                ),
                safe_example=(
                    f"基于 {skill} 完成【真实功能】，解决【真实问题】，"
                    "并通过【真实测试方法】验证；方括号内容完成后再替换。"
                ),
            )
        )

    for item in report.evidence[:4]:
        if not any(any(char.isdigit() for char in evidence) for evidence in item.evidence):
            advice.append(
                AdviceItem(
                    priority="中",
                    section="项目证据",
                    issue=f"简历提到了 {item.skill}，但缺少结果或验证方式。",
                    suggestion="补充你的动作、技术选择、解决的问题，以及真实可核验的结果。",
                    safe_example=(
                        f"使用 {item.skill} 实现【具体模块】，通过【测试数量/响应时间/准确率等真实指标】"
                        "验证效果。没有测量过的数据不要填写。"
                    ),
                )
            )

    if not resume.projects:
        advice.append(
            AdviceItem(
                priority="高",
                section="项目经历",
                issue="没有识别到清晰的项目经历板块。",
                suggestion="增加 2 个与目标岗位相关、可以运行和演示的项目，每个项目写清问题、动作和结果。",
                safe_example="项目名称｜技术栈｜你负责的模块｜运行结果｜GitHub 地址。",
            )
        )

    advice.append(
        AdviceItem(
            priority="中",
            section="关键词布局",
            issue="通用简历通常不能突出不同 JD 最关心的内容。",
            suggestion=(
                "把已真实掌握且与岗位相关的技能前置；项目描述按“动作 + 技术 + 结果”重写，"
                "但不要复制 JD 或添加没有做过的经历。"
            ),
            safe_example=f"针对“{job.role}”版本，把匹配技能放到项目要点的前两条。",
        )
    )
    return advice[:8]


def generate_interview_questions(
    resume: ResumeProfile,
    job: JobProfile,
    report: MatchReport,
) -> list[InterviewQuestion]:
    questions: list[InterviewQuestion] = []
    matched = report.matched_skills[:4] or resume.skills[:3]
    missing = report.missing_skills[:3]

    for skill in matched:
        questions.append(
            InterviewQuestion(
                category="项目深挖",
                question=f"请结合一个真实项目说明你是如何使用 {skill} 的，为什么选择它？",
                why_asked="确认简历中的技能是否有真实项目支撑，而不只是关键词。",
                answer_framework="背景与目标 → 你的职责 → 技术选择 → 遇到的问题 → 验证结果 → 复盘",
                related_skills=[skill],
            )
        )

    for skill in missing:
        questions.append(
            InterviewQuestion(
                category="技能差距",
                question=f"岗位需要 {skill}。如果让你一周内用它完成一个功能，你会怎么学习和交付？",
                why_asked="考察面对陌生技术时的拆解、学习和交付能力。",
                answer_framework="承认当前边界 → 对照官方资料 → 最小实验 → 测试 → 集成 → 风险和时间安排",
                related_skills=[skill],
            )
        )

    questions.extend(
        [
            InterviewQuestion(
                category="技术基础",
                question="LLM、RAG、工具调用和 Agent 分别解决什么问题？它们如何协作？",
                why_asked="这是 AI Agent 应用开发岗位的基础概念。",
                answer_framework="先定义四个概念，再用一个端到端请求说明数据和控制流。",
                related_skills=["LLM", "RAG", "Tool Calling", "AI Agent"],
            ),
            InterviewQuestion(
                category="技术基础",
                question="你的 Agent 在模型输出格式错误、工具超时或检索无结果时如何处理？",
                why_asked="考察工程可靠性，而不仅是模型调用。",
                answer_framework="输入校验 → 结构化输出 → 超时与重试 → 降级 → 日志追踪 → 人工确认",
                related_skills=["Pydantic", "AI Agent"],
            ),
            InterviewQuestion(
                category="行为面试",
                question="请讲一次你从不会到完成交付的经历，你如何拆解问题并验证结果？",
                why_asked="秋招会重点考察学习能力和项目真实性。",
                answer_framework="使用 STAR：情境、任务、行动、结果；最后补充复盘。",
                related_skills=[],
            ),
        ]
    )
    return questions[:10]

