"""Source confirmation and history UI with recoverable drafts and retrieval settings."""

import gradio as gr
from fastapi import HTTPException
from openai import OpenAIError

from career_pilot.history import HistoryStore
from career_pilot.multimodal.loader import load_document
from career_pilot.review import (
    ReviewRequest,
    SourcePage,
    confirm_job,
    confirm_review,
    create_review,
)


def display(packet):
    rows = [
        [f["field"], f["value"], f["page_number"], f["quote"]] for f in packet["facts"]
    ]
    options = [
        (f["field"] + ": " + f["value"][:60], f["fact_id"]) for f in packet["facts"]
    ]
    job_facts = packet.get("job_facts", [])
    labels = {"required_skills": "必需", "preferred_skills": "加分"}

    def job_label(fact):
        return labels[fact["field"].split(".")[0]]

    confirmed_ids = set(packet.get("confirmed_job_fact_ids", []))
    exclusions = {
        item["fact_id"]: item["reason"] for item in packet.get("excluded_job_facts", [])
    }
    job_rows = [
        [
            job_label(f),
            f["value"],
            f.get("context", f["quote"]),
            "确认要求"
            if f["fact_id"] in confirmed_ids
            else "排除误提取"
            if f["fact_id"] in exclusions
            else "待核实",
            exclusions.get(f["fact_id"], ""),
        ]
        for f in job_facts
    ]
    job_options = [(job_label(f) + ": " + f["value"], f["fact_id"]) for f in job_facts]
    messages = packet["warnings"] + packet["clarification_questions"]
    if job_facts and packet.get("schema_version", 1) < 3:
        messages.append(
            "此记录使用旧版评分与核对规则；请重新核对全部岗位提取项后生成新版评分。"
        )
    if packet.get("pending_job_fact_ids"):
        messages.append(
            f"尚有 {len(packet['pending_job_fact_ids'])} 项岗位要求待核实，暂不评分。"
        )
    status = "记录：" + packet["review_id"] + " | 状态：" + packet["status"]
    if messages:
        status += "\n\n" + "\n\n".join(messages)
    report = (
        packet["analysis"]["report_markdown"]
        if packet["analysis"]
        else "请逐项核对岗位要求；未确认或排除的条目仍为待核实，暂不生成评分。排除误提取需填写原因；缺少信息时请先补充并重新提取。"
    )
    request = packet.get("request", {})
    return (
        packet["review_id"],
        status,
        rows,
        gr.CheckboxGroup(choices=options, value=packet["confirmed_fact_ids"]),
        report,
        packet.get("draft_markdown", ""),
        job_rows,
        gr.CheckboxGroup(
            choices=job_options, value=packet.get("confirmed_job_fact_ids", [])
        ),
        request.get("job_description", ""),
        request.get("company", ""),
        request.get("role", ""),
        request.get("parsing_mode", packet.get("parsing_mode", "rules")),
        request.get("retrieval_mode", "keyword"),
        gr.CheckboxGroup(choices=job_options, value=list(exclusions)),
        next(iter(exclusions.values())) if len(set(exclusions.values())) == 1 else "",
    )


def _show_error(error):
    if isinstance(error, HTTPException):
        raise gr.Error(error.detail) from None
    if isinstance(error, (ValueError, KeyError)):
        raise gr.Error(str(error)) from None
    raise gr.Error("处理失败，请检查文件、检索配置和本地服务日志。") from None


def analyze(path, job, company, role, mode, retrieval_mode="keyword"):
    if not path:
        raise gr.Error("请先选择简历文件。")
    try:
        document = load_document(path)
        request = ReviewRequest(
            filename=document.filename,
            pages=[
                SourcePage(page_number=p.page_number, text=p.text)
                for p in document.pages
            ],
            job_description=job,
            company=company,
            role=role,
            parsing_mode=mode,
            retrieval_mode=retrieval_mode,
        )
        return display(create_review(request))
    except (ValueError, RuntimeError, OSError, OpenAIError, HTTPException) as error:
        _show_error(error)


def load(review_id):
    packet = HistoryStore().get(review_id)
    if packet is None:
        raise gr.Error("没有找到该历史记录。")
    return display(packet)


def confirm_job_selection(review_id, fact_ids, excluded_ids=None, exclusion_reason=""):
    try:
        stored = HistoryStore().get(review_id)
        if stored is None:
            raise KeyError(review_id)
        existing = {
            item["fact_id"]: item["reason"]
            for item in stored.get("excluded_job_facts", [])
        }
        exclusions = [
            {
                "fact_id": fid,
                "reason": exclusion_reason.strip() or existing.get(fid, ""),
            }
            for fid in (excluded_ids or [])
        ]
        return display(confirm_job(review_id, fact_ids, exclusions=exclusions))
    except (
        ValueError,
        KeyError,
        RuntimeError,
        OSError,
        OpenAIError,
        HTTPException,
    ) as error:
        _show_error(error)


def confirm(
    review_id, fact_ids, job_fact_ids=None, excluded_ids=None, exclusion_reason=""
):
    try:
        packet = HistoryStore().get(review_id)
        if packet is None:
            raise KeyError(review_id)
        if job_fact_ids is not None and set(job_fact_ids) != set(
            packet.get("confirmed_job_fact_ids", [])
        ):
            raise ValueError("岗位勾选已变更，请先确认岗位要求并重新评分。")
        existing = {
            item["fact_id"]: item["reason"]
            for item in packet.get("excluded_job_facts", [])
        }
        if excluded_ids is not None and (
            set(excluded_ids) != set(existing)
            or (
                exclusion_reason.strip()
                and any(
                    existing[fid] != exclusion_reason.strip() for fid in excluded_ids
                )
            )
        ):
            raise ValueError("岗位排除项或原因已变更，请重新核对并评分。")
        packet = confirm_review(review_id, fact_ids)
    except (ValueError, KeyError) as error:
        _show_error(error)
    return packet["draft_markdown"], "已保存确认结果：" + packet["status"]


def history():
    return [
        [r["id"], r["title"], r["status"], r["updated_at"]]
        for r in HistoryStore().list()
    ]


def build_review_tab():
    with gr.Tab("文档核对与历史"):
        gr.Markdown(
            "上传简历后核对原文；将所有岗位条目标为确认要求或排除误提取后，再查看匹配评分和建议。勾选已确认的简历事实后生成草稿。简历提取文本、岗位正文、配置与结果保存在本机，支持按编号恢复。选择结构化模型提取时，简历文本及岗位正文会发送至已配置的模型服务。"
        )
        with gr.Row():
            file = gr.File(
                label="简历文件",
                file_types=[".txt", ".md", ".docx", ".pdf", ".png", ".jpg", ".jpeg"],
                type="filepath",
            )
            mode = gr.Radio(
                choices=[("规则提取", "rules"), ("结构化模型提取", "model")],
                value="rules",
                label="简历与岗位提取方式",
            )
            retrieval = gr.Radio(
                choices=[
                    ("关键词检索", "keyword"),
                    ("混合检索（需模型与向量服务配置）", "hybrid"),
                ],
                value="keyword",
                label="知识检索方式",
            )
        with gr.Row():
            company = gr.Textbox(label="公司名称")
            role = gr.Textbox(label="目标岗位")
        job = gr.Textbox(label="岗位要求正文", lines=5)
        start = gr.Button("提取并核对", variant="primary")
        record = gr.Textbox(label="记录编号")
        status = gr.Markdown()
        job_evidence = gr.Dataframe(
            headers=["分类", "技能", "岗位原文上下文", "核对状态", "排除原因"],
            interactive=False,
            wrap=True,
        )
        job_facts = gr.CheckboxGroup(
            label="确认是岗位要求（原文确有要求，即使自己暂不具备也应确认）"
        )
        excluded_jobs = gr.CheckboxGroup(
            label="排除误提取的岗位条目（不能与确认要求重复勾选）"
        )
        exclusion_reason = gr.Textbox(
            label="排除原因（应用于本次选择的排除项，至少3字）", lines=2
        )
        gr.Markdown(
            "两组都未勾选的条目为待核实，会暂停评分。排除用于纠正提取错误，报告会列出排除项及原因；如果自己不具备岗位要求的技能，仍应保留为确认要求。"
        )
        job_confirm = gr.Button("保存岗位核对；全部核对后生成评分", variant="primary")
        report = gr.Markdown()
        evidence = gr.Dataframe(
            headers=["字段", "提取值", "PDF页码或提取页序", "原文"],
            interactive=False,
            wrap=True,
        )
        facts = gr.CheckboxGroup(label="请根据上方原文勾选已确认的简历事实")
        confirm_button = gr.Button("保存确认并生成事实草稿")
        draft = gr.Markdown()
        outputs = [
            record,
            status,
            evidence,
            facts,
            report,
            draft,
            job_evidence,
            job_facts,
            job,
            company,
            role,
            mode,
            retrieval,
            excluded_jobs,
            exclusion_reason,
        ]
        start.click(
            analyze, inputs=[file, job, company, role, mode, retrieval], outputs=outputs
        )
        job_confirm.click(
            confirm_job_selection,
            inputs=[record, job_facts, excluded_jobs, exclusion_reason],
            outputs=outputs,
        )
        confirm_button.click(
            confirm,
            inputs=[record, facts, job_facts, excluded_jobs, exclusion_reason],
            outputs=[draft, status],
        )
        derived = [
            record,
            status,
            evidence,
            facts,
            report,
            draft,
            job_evidence,
            job_facts,
            excluded_jobs,
            exclusion_reason,
        ]

        def invalidate_review():
            return (
                "",
                "输入已变更，请重新提取并核对。",
                [],
                gr.CheckboxGroup(choices=[], value=[]),
                "",
                "",
                [],
                gr.CheckboxGroup(choices=[], value=[]),
                gr.CheckboxGroup(choices=[], value=[]),
                "",
            )

        file.change(invalidate_review, outputs=derived, queue=False)
        for component in [job, company, role, mode, retrieval]:
            component.input(invalidate_review, outputs=derived, queue=False)
        facts.input(lambda: "", outputs=draft, queue=False)
        for component in [job_facts, excluded_jobs, exclusion_reason]:
            component.input(
                lambda: ("岗位核对已变更，请保存核对；有待核实项时暂停评分。", "", ""),
                outputs=[status, report, draft],
                queue=False,
            )
        refresh = gr.Button("刷新历史记录")
        records = gr.Dataframe(
            headers=["记录编号", "文件", "状态", "更新时间"], interactive=False
        )
        restore = gr.Button("按编号恢复记录")
        refresh.click(history, outputs=records)
        restore.click(load, inputs=record, outputs=outputs)
