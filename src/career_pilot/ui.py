import logging

import gradio as gr
from fastapi import HTTPException
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)
from pydantic import ValidationError

from career_pilot.api import (
    ANALYSIS_EXAMPLE,
    analyze_career,
    get_rag_service,
    ingest_knowledge_file,
)
from career_pilot.models import AnalysisRequest
from career_pilot.rag.models import RAGAnswer
from career_pilot.report import save_markdown_report

logger = logging.getLogger(__name__)

SOURCE_TYPE_LABELS = {
    "text": "TXT",
    "markdown": "Markdown",
    "docx": "Word",
    "pdf": "PDF",
    "image": "图片",
}

EXTRACTION_METHOD_LABELS = {
    "native_text": "原生文本",
    "ocr": "OCR",
}


def format_sources(result: RAGAnswer) -> str:
    """Format retrieved sources for display in the UI."""

    if not result.sources:
        return "本次回答没有引用知识库资料。"

    lines: list[str] = []

    for source in result.sources:
        metadata: list[str] = []

        if source.page_number is not None:
            metadata.append(f"第 {source.page_number} 页")

        if source.source_type is not None:
            metadata.append(SOURCE_TYPE_LABELS[source.source_type])

        if source.extraction_method is not None:
            metadata.append(EXTRACTION_METHOD_LABELS[source.extraction_method])

        metadata_text = "".join(f" | {item}" for item in metadata)

        lines.append(
            f"- [资料{source.citation_id}] "
            f"**{source.title}**"
            f" | `{source.source}`"
            f"{metadata_text}"
            f" | 重排序分数：{source.score:.3f}"
        )

    return "\n".join(lines)


def upload_knowledge_file(
    file_path: str | None,
) -> str:
    """Ingest one uploaded file into the active knowledge base."""

    if not file_path:
        raise gr.Error("请先选择需要上传的文件。")

    try:
        result = ingest_knowledge_file(file_path)
    except FileNotFoundError:
        raise gr.Error("上传文件不存在，请重新选择。") from None
    except ValueError as exc:
        raise gr.Error(str(exc)) from None
    except RuntimeError:
        logger.exception("ui_document_ingestion_failed")
        raise gr.Error("文件解析失败，请检查文件内容后重试。") from None
    except Exception:
        logger.exception("ui_document_upload_failed")
        raise gr.Error("上传文件时发生异常，请查看终端日志。") from None

    source_label = SOURCE_TYPE_LABELS[result.source_type]

    return (
        f"已加入知识库：**{result.filename}**"
        f" | 类型：{source_label}"
        f" | 页数：{result.page_count}"
        f" | 新增分块：{result.chunk_count}"
        f" | 当前上传文档："
        f"{result.total_document_count} 个"
        f" | 上传分块总数："
        f"{result.total_chunk_count}"
    )


def answer_question(question: str) -> tuple[str, str, str]:
    """Run one RAG request and prepare values for the UI."""

    normalized_question = question.strip()

    if not normalized_question:
        raise gr.Error("请输入问题后再提交。")

    if len(normalized_question) > 2000:
        raise gr.Error("问题不能超过 2000 字符。")
    try:
        result = get_rag_service().answer(normalized_question)
    except AuthenticationError:
        raise gr.Error("大模型认证失败，请检查 API Key。") from None
    except RateLimitError:
        raise gr.Error("大模型请求过于频繁，请稍后重试。") from None
    except APIConnectionError:
        raise gr.Error("暂时无法连接大模型服务，请稍后重试。") from None
    except APIStatusError:
        raise gr.Error("大模型服务返回异常，请稍后重试。") from None
    except Exception:
        logger.exception("ui_rag_request_failed")
        raise gr.Error("处理问题时发生异常，请查看终端日志。") from None

    model_status = "已调用大模型" if result.used_model else "未调用大模型"
    status = f"检索结果：{result.retrieved_count} 条 | {model_status}"

    if result.evidence_status != "not_checked":
        labels = {
            "supported": "资料核验通过",
            "insufficient": "资料不足，未展示完整回答",
            "invalid": "资料或引用未通过核验",
            "unavailable": "暂时无法核验资料",
        }
        status += " | " + labels[result.evidence_status]
    if result.answer_status != "not_checked":
        labels = {
            "supported": "回答依据核验通过",
            "insufficient": "未找到完整的有依据回答",
            "invalid": "回答未通过依据核验",
            "unavailable": "暂时无法完成回答核验",
        }
        status += " | " + labels[result.answer_status]
    return result.answer, format_sources(result), status


def clear_form() -> tuple[str, str, str, str]:
    """Clear all interactive fields."""

    return "", "", "", ""


def analyze_resume(
    resume_text: str,
    job_description: str,
    company: str,
    role: str,
    retrieval_mode: str,
) -> tuple[float, str, str, str, str, str, gr.Button]:
    """Use the same validated analysis entry point as the FastAPI route."""

    if retrieval_mode not in {"keyword", "hybrid"}:
        raise gr.Error("请选择有效的检索方式。")
    try:
        request = AnalysisRequest(
            resume_text=resume_text,
            job_description=job_description,
            company=company,
            role=role,
        )
    except ValidationError as error:
        first = error.errors()[0]
        labels = {
            "resume_text": "简历正文",
            "job_description": "岗位要求",
            "company": "公司",
            "role": "岗位",
        }
        label = labels.get(first["loc"][0], "输入")
        context = first.get("ctx", {})
        if first["type"] == "string_too_short":
            message = f"{label}至少需要 {context['min_length']} 个字符。"
        elif first["type"] == "string_too_long":
            message = f"{label}不能超过 {context['max_length']} 个字符。"
        else:
            message = f"请检查{label}的格式。"
        raise gr.Error(message) from None

    try:
        result = analyze_career(request, retrieval_mode=retrieval_mode)
    except AuthenticationError:
        raise gr.Error("大模型认证失败，请检查 API Key。") from None
    except RateLimitError:
        raise gr.Error("大模型请求过于频繁，请稍后重试。") from None
    except APIConnectionError:
        raise gr.Error("暂时无法连接大模型服务，请稍后重试。") from None
    except APIStatusError:
        raise gr.Error("大模型服务返回异常，请稍后重试。") from None
    except HTTPException as error:
        raise gr.Error(str(error.detail)) from None
    except Exception:
        logger.exception("ui_career_analysis_failed")
        raise gr.Error("分析失败，请查看服务端日志。") from None

    missing_required = "、".join(result.match_result.missing_required_skills) or (
        "未发现缺失" if result.job_profile.required_skills else "未识别到必备技能要求"
    )
    missing_preferred = "、".join(result.match_result.missing_preferred_skills) or (
        "未发现缺失" if result.job_profile.preferred_skills else "未识别到加分技能要求"
    )
    status = (
        f"请求编号：{result.request_id} | 节点：{len(result.workflow_trace)}"
        f" | 引用资料：{len(result.knowledge_sources)}"
    )
    return (
        result.match_result.score,
        missing_required,
        missing_preferred,
        result.report_markdown,
        status,
        result.report_markdown,
        gr.Button(interactive=True),
    )


def load_analysis_example() -> tuple[str, str, str, str, str]:
    return (
        ANALYSIS_EXAMPLE["resume_text"],
        ANALYSIS_EXAMPLE["job_description"],
        ANALYSIS_EXAMPLE["company"],
        ANALYSIS_EXAMPLE["role"],
        "keyword",
    )


def clear_analysis_inputs() -> tuple[str, str, str, str, str]:
    return "", "", "", "", "keyword"


def clear_analysis_results() -> tuple[None, str, str, str, str, str, None, gr.Button]:
    """Invalidate the displayed result, session report, and old download together."""

    return None, "", "", "", "", "", None, gr.Button(interactive=False)


def export_analysis_report(report_markdown: str) -> str:
    """Export only the report stored in this browser session."""

    if not report_markdown or not report_markdown.strip():
        raise gr.Error("请先完成简历分析，再导出报告。")
    try:
        path = save_markdown_report(report_markdown)
    except OSError:
        logger.exception("ui_report_export_failed")
        raise gr.Error("报告保存失败，请检查目录权限后重试。") from None
    return str(path.resolve())


def build_ui() -> gr.Blocks:
    """Build the CareerPilot browser interface."""

    with gr.Blocks(
        title="CareerPilot Agent",
        analytics_enabled=False,
        theme=gr.themes.Default(
            primary_hue="green",
            secondary_hue="blue",
            neutral_hue="gray",
            font=["Microsoft YaHei", "Arial", "sans-serif"],
            font_mono=["Consolas", "monospace"],
        ),
    ) as demo:
        gr.Markdown("# CareerPilot Agent")
        with gr.Tab("简历分析"):
            report_state = gr.State("")
            with gr.Row():
                company = gr.Textbox(label="公司", elem_id="analysis-company")
                role = gr.Textbox(label="岗位", elem_id="analysis-role")
            with gr.Row():
                resume_text = gr.Textbox(
                    label="简历正文",
                    lines=8,
                    max_lines=12,
                    min_width=320,
                    elem_id="analysis-resume",
                )
                job_description = gr.Textbox(
                    label="岗位要求",
                    lines=8,
                    max_lines=12,
                    min_width=320,
                    elem_id="analysis-job",
                )
            retrieval_mode = gr.Radio(
                choices=[("本地关键词", "keyword"), ("混合检索", "hybrid")],
                value="keyword",
                label="检索方式",
            )
            with gr.Row():
                analyze_button = gr.Button(
                    "分析简历", variant="primary", elem_id="analyze-button"
                )
                example_button = gr.Button("载入示例", elem_id="example-button")
                clear_analysis_button = gr.Button("清空输入")
            analysis_status = gr.Markdown()
            with gr.Row():
                score = gr.Number(
                    value=None,
                    label="匹配分数",
                    placeholder="待分析",
                    precision=2,
                    interactive=False,
                )
                missing_required = gr.Textbox(label="必备技能缺口", interactive=False)
                missing_preferred = gr.Textbox(label="加分技能缺口", interactive=False)
            with gr.Row():
                export_button = gr.Button(
                    "导出报告", interactive=False, elem_id="export-button"
                )
                report_file = gr.File(
                    label="报告文件", interactive=False, elem_id="report-download"
                )
            report = gr.Markdown(elem_id="analysis-report")
            form_inputs = [resume_text, job_description, company, role, retrieval_mode]
            result_outputs = [
                score,
                missing_required,
                missing_preferred,
                report,
                analysis_status,
                report_state,
                report_file,
                export_button,
            ]
            analyze_button.click(
                fn=clear_analysis_results, outputs=result_outputs
            ).then(
                fn=analyze_resume,
                inputs=form_inputs,
                outputs=[*result_outputs[:6], export_button],
                api_name="analyze_resume",
            )
            example_button.click(fn=load_analysis_example, outputs=form_inputs).then(
                fn=clear_analysis_results, outputs=result_outputs
            )
            clear_analysis_button.click(
                fn=clear_analysis_inputs, outputs=form_inputs
            ).then(fn=clear_analysis_results, outputs=result_outputs)
            for component in form_inputs:
                component.input(
                    fn=clear_analysis_results,
                    outputs=result_outputs,
                    queue=False,
                )
            export_button.click(
                fn=export_analysis_report,
                inputs=report_state,
                outputs=report_file,
                api_name="export_report",
            )
        from career_pilot.review_ui import build_review_tab

        build_review_tab()
        with gr.Tab("知识问答"):
            with gr.Row():
                knowledge_file = gr.File(
                    label="知识文件",
                    file_types=[
                        ".txt",
                        ".md",
                        ".docx",
                        ".pdf",
                        ".png",
                        ".jpg",
                        ".jpeg",
                    ],
                    file_count="single",
                    type="filepath",
                )
                upload_button = gr.Button("加入知识库", variant="secondary")
            upload_status = gr.Markdown()
            upload_button.click(
                fn=upload_knowledge_file,
                inputs=knowledge_file,
                outputs=upload_status,
                api_name="upload_knowledge",
            ).then(fn=clear_analysis_results, outputs=result_outputs)
            question = gr.Textbox(label="问题", lines=4, max_lines=8)
            with gr.Row():
                submit_button = gr.Button("提交问题", variant="primary")
                clear_button = gr.Button("清空")
            gr.Markdown("### 回答")
            answer = gr.Markdown()
            gr.Markdown("### 引用资料")
            sources = gr.Markdown()
            status = gr.Markdown()
            submit_button.click(
                fn=answer_question,
                inputs=question,
                outputs=[answer, sources, status],
            )
            question.submit(
                fn=answer_question,
                inputs=question,
                outputs=[answer, sources, status],
            )
            clear_button.click(
                fn=clear_form,
                outputs=[question, answer, sources, status],
            )

    return demo


if __name__ == "__main__":
    build_ui().launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
    )
