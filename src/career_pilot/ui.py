"""Gradio user interface for CareerPilot Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import gradio as gr

from .config import Settings
from .database import ApplicationRepository
from .models import AnalysisResult, ApplicationCreate
from .reporting import applications_table, export_analysis, render_analysis_markdown
from .service import CareerPilotService


settings = Settings.from_env()
service = CareerPilotService(settings)
repository = ApplicationRepository(settings.database_path)

TABLE_HEADERS = ["ID", "公司", "岗位", "状态", "匹配度", "简历姓名", "更新时间", "备注"]
APP_CSS = """
.hero {text-align:center; padding: 18px 0 6px;}
.hero h1 {font-size: 2.2rem; margin-bottom: .35rem;}
.hint {background: #f5f7fb; border-radius: 12px; padding: 12px 16px;}
"""


def _sample_text(filename: str) -> str:
    path = settings.project_root / "examples" / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


def run_analysis(
    resume_file: Any,
    resume_text: str,
    company: str,
    role: str,
    jd_text: str,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    try:
        file_path = None
        if resume_file:
            file_path = getattr(resume_file, "name", resume_file)
        result = service.analyze(
            resume_path=file_path,
            resume_text=resume_text or "",
            company=company or "",
            role=role or "",
            jd_text=jd_text or "",
        )
        payload = {"analysis": result.model_dump(), "jd_text": jd_text}
        return render_analysis_markdown(result), payload, result.model_dump()
    except Exception as exc:
        return (
            "# 分析失败\n\n"
            f"> {exc}\n\n"
            "请检查：简历是否含有可复制文字、JD 是否完整、文件格式是否为 PDF/DOCX/TXT/MD。",
            None,
            None,
        )


def save_application(
    state: dict[str, Any] | None,
    status: str,
    notes: str,
) -> str:
    if not state or "analysis" not in state:
        return "请先完成一次分析。"
    result = AnalysisResult.model_validate(state["analysis"])
    data = ApplicationCreate(
        company=result.job_profile.company,
        role=result.job_profile.role,
        status=status,
        match_score=result.match_report.overall_score,
        resume_name=result.resume_profile.name,
        jd_excerpt=(state.get("jd_text") or "")[:500],
        notes=notes or "",
    )
    record = repository.create(data, result)
    return f"已保存投递记录 #{record.id}：{record.company} / {record.role}。请到“投递管理”页刷新。"


def refresh_applications() -> list[list[object]]:
    return applications_table(repository.list())


def update_application(record_id: float, status: str, notes: str) -> tuple[str, list[list[object]]]:
    try:
        record = repository.update_status(int(record_id), status, notes)
        return f"已更新记录 #{record.id}。", applications_table(repository.list())
    except Exception as exc:
        return f"更新失败：{exc}", applications_table(repository.list())


def export_report(state: dict[str, Any] | None) -> str | None:
    if not state or "analysis" not in state:
        return None
    result = AnalysisResult.model_validate(state["analysis"])
    path = export_analysis(result, settings.project_root / "outputs")
    return str(path)


def load_example() -> tuple[str, str, str, str]:
    return (
        _sample_text("resume_example.txt"),
        "星云智能科技",
        "AI Agent 应用开发工程师",
        _sample_text("jd_example.txt"),
    )


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="CareerPilot Agent") as demo:
        analysis_state = gr.State(None)
        gr.HTML(
            "<div class='hero'><h1>CareerPilot Agent</h1>"
            "<p>基于 LangGraph 的多智能体求职助手：读简历、拆 JD、算匹配、改简历、练面试</p></div>"
        )
        mode_text = "大模型增强已启用" if settings.ai_enabled else "演示模式：无需 API Key，不产生模型费用"
        gr.Markdown(f"> **当前模式：{mode_text}**　｜　所有匹配结论都提供可解释依据。")

        with gr.Tabs():
            with gr.Tab("智能分析"):
                with gr.Row():
                    with gr.Column(scale=1):
                        resume_file = gr.File(
                            label="上传简历（PDF / DOCX / TXT / MD）",
                            file_types=[".pdf", ".docx", ".txt", ".md"],
                            type="filepath",
                        )
                        resume_text = gr.Textbox(
                            label="或粘贴简历文字",
                            lines=11,
                            placeholder="上传文件后可以留空；扫描版 PDF 请把 OCR 文字粘贴到这里。",
                        )
                    with gr.Column(scale=1):
                        company = gr.Textbox(label="公司", placeholder="例如：星云智能科技")
                        role = gr.Textbox(label="岗位", placeholder="例如：AI Agent 应用开发工程师")
                        jd_text = gr.Textbox(
                            label="招聘 JD",
                            lines=13,
                            placeholder="粘贴岗位职责和任职要求……",
                        )

                with gr.Row():
                    example_button = gr.Button("载入示例", variant="secondary")
                    analyze_button = gr.Button("开始多 Agent 分析", variant="primary")
                report_output = gr.Markdown("在左侧输入资料后点击“开始多 Agent 分析”。")
                with gr.Accordion("查看结构化 JSON（面试时可用于讲结构化输出）", open=False):
                    json_output = gr.JSON(label="AnalysisResult")

                with gr.Row():
                    application_status = gr.Dropdown(
                        ["准备投递", "已投递", "笔试", "一面", "二面", "HR 面", "Offer", "已结束"],
                        value="准备投递",
                        label="投递状态",
                    )
                    application_notes = gr.Textbox(label="备注", placeholder="内推人、截止时间、下一步等")
                with gr.Row():
                    save_button = gr.Button("保存到投递管理")
                    export_button = gr.Button("导出 Markdown 报告")
                save_message = gr.Markdown()
                exported_file = gr.File(label="导出的报告", interactive=False)

                example_button.click(
                    load_example,
                    outputs=[resume_text, company, role, jd_text],
                )
                analyze_button.click(
                    run_analysis,
                    inputs=[resume_file, resume_text, company, role, jd_text],
                    outputs=[report_output, analysis_state, json_output],
                )
                save_button.click(
                    save_application,
                    inputs=[analysis_state, application_status, application_notes],
                    outputs=[save_message],
                )
                export_button.click(export_report, inputs=[analysis_state], outputs=[exported_file])

            with gr.Tab("投递管理"):
                gr.Markdown("记录每一次投递，并跟踪当前进度。SQLite 数据保存在本机。")
                tracker_table = gr.Dataframe(
                    headers=TABLE_HEADERS,
                    value=applications_table(repository.list()),
                    interactive=False,
                    wrap=True,
                )
                refresh_button = gr.Button("刷新记录")
                with gr.Row():
                    record_id = gr.Number(label="要更新的记录 ID", precision=0)
                    new_status = gr.Dropdown(
                        ["准备投递", "已投递", "笔试", "一面", "二面", "HR 面", "Offer", "已结束"],
                        value="已投递",
                        label="新状态",
                    )
                    new_notes = gr.Textbox(label="备注")
                update_button = gr.Button("更新状态")
                update_message = gr.Markdown()
                refresh_button.click(refresh_applications, outputs=[tracker_table])
                update_button.click(
                    update_application,
                    inputs=[record_id, new_status, new_notes],
                    outputs=[update_message, tracker_table],
                )

            with gr.Tab("项目说明"):
                gr.Markdown(
                    """
## 这个项目展示什么

- LangGraph 状态图与条件路由
- ResumeAgent、JobAgent、RAGAgent、MatchAgent、ResumeCoachAgent、InterviewAgent
- PDF/DOCX 文档工具、可解释匹配、轻量 RAG、SQLite 持久化
- Gradio 可视化页面与 FastAPI REST 接口
- Pydantic 结构化输出，以及有 API Key 时的模型增强与失败降级

系统默认不会调用付费模型。要启用大模型，请复制 `.env.example` 为 `.env` 并填写自己的配置。
                    """
                )
        return demo


def main() -> None:
    demo = build_demo()
    demo.launch(
        server_name=settings.app_host,
        server_port=settings.app_port,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(),
        css=APP_CSS,
    )


if __name__ == "__main__":
    main()
