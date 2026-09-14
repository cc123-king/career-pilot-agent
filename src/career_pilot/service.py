"""Public service façade used by both the web UI and the API."""

from __future__ import annotations

from pathlib import Path

from .config import Settings
from .models import AnalysisResult
from .parsers import read_document
from .workflow import build_workflow


class CareerPilotService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.workflow = build_workflow(self.settings)

    def analyze(
        self,
        *,
        jd_text: str,
        resume_text: str = "",
        resume_path: str | Path | None = None,
        company: str = "",
        role: str = "",
    ) -> AnalysisResult:
        if resume_path:
            extracted = read_document(resume_path)
            if resume_text.strip():
                extracted = f"{extracted}\n{resume_text.strip()}"
            resume_text = extracted
        if len(resume_text.strip()) < 20:
            raise ValueError("请上传简历文件，或在简历文本框中粘贴至少 20 个字符。")
        if len(jd_text.strip()) < 20:
            raise ValueError("请粘贴完整的招聘 JD，至少需要 20 个字符。")

        final_state = self.workflow.invoke(
            {
                "resume_text": resume_text,
                "jd_text": jd_text,
                "company": company,
                "role": role,
                "workflow_trace": [],
                "warnings": [],
            }
        )
        return AnalysisResult(
            mode=final_state.get("mode", "demo"),
            resume_profile=final_state["resume_profile"],
            job_profile=final_state["job_profile"],
            match_report=final_state["match_report"],
            advice=final_state.get("advice", []),
            interview_questions=final_state.get("interview_questions", []),
            knowledge_references=final_state.get("knowledge_references", []),
            llm_enhancement=final_state.get("llm_enhancement"),
            workflow_trace=final_state.get("workflow_trace", []),
            warnings=final_state.get("warnings", []),
        )

