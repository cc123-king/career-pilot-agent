"""Optional LLM enhancement using OpenAI or an OpenAI-compatible endpoint."""

from __future__ import annotations

import json

from .config import Settings
from .models import JobProfile, LLMEnhancement, MatchReport, ResumeProfile


class LLMEnhancer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def enhance(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        report: MatchReport,
    ) -> LLMEnhancement:
        if not self.settings.ai_enabled:
            raise RuntimeError("当前没有启用大模型。")

        payload = {
            "resume": resume.model_dump(exclude={"email", "phone"}),
            "job": job.model_dump(),
            "match_report": report.model_dump(),
        }
        system_prompt = (
            "你是一名谨慎的中文求职顾问。只能基于输入中已有的事实给建议；"
            "不得编造工作经历、指标、学历、技能或项目结果。输出简洁、可执行。"
        )
        user_prompt = "请对以下分析做个性化增强：\n" + json.dumps(
            payload, ensure_ascii=False, indent=2
        )

        from openai import OpenAI

        if self.settings.llm_provider == "openai":
            client = OpenAI(api_key=self.settings.openai_api_key)
            response = client.responses.parse(
                model=self.settings.openai_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=LLMEnhancement,
            )
            if response.output_parsed is None:
                raise RuntimeError("模型没有返回可解析的结构化结果。")
            return response.output_parsed

        client = OpenAI(
            api_key=self.settings.compatible_api_key,
            base_url=self.settings.compatible_base_url,
        )
        response = client.chat.completions.create(
            model=self.settings.compatible_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + "\n只返回 JSON 对象。"},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        return LLMEnhancement.model_validate_json(content)

