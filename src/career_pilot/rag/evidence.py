"""Check answer sufficiency separately from a retriever's ranking score."""

import json
import logging
import re
from collections.abc import Sequence
from typing import Literal, Protocol

from openai import OpenAIError
from pydantic import Field, StrictBool, StrictInt, ValidationError, model_validator

from career_pilot.models import StrictModel
from career_pilot.rag.context import build_retrieval_context
from career_pilot.rag.diagnostics import provider_error_fields
from career_pilot.rag.models import SearchHit

logger = logging.getLogger(__name__)
NUMERIC_QUESTION = re.compile(
    r"多少|几次|几秒|几名|几人|多久|多长时间|百分之几|"
    r"\bhow\s+(?:many|much|long)\b|\bwhat\s+(?:percentage|percent|number)\b",
    re.IGNORECASE,
)
NUMERIC_SLOT = re.compile(
    NUMERIC_QUESTION.pattern
    + r"|数量|次数|人数|文件数|大小|上限|下限|时长|有效期|秒数|价格|费用|百分比",
    re.IGNORECASE,
)
NUMBER = re.compile(
    r"\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+"
    r"\s*(?:次|秒|分钟|小时|天|名|人|个|元|年|倍|成|%)"
)


EXPLICIT_VALUE = re.compile(
    r"立即|即时|马上|不自动重试|不重试|无需重试|不设上限|没有上限|无限制|无限期|永不|"
    r"\b(?:immediately|never|unlimited)\b",
    re.IGNORECASE,
)


class EvidenceQuote(StrictModel):
    citation_id: StrictInt = Field(ge=1)
    quote: str = Field(min_length=8, max_length=1200)


class EvidenceRequirement(StrictModel):
    question_part: str = Field(min_length=2, max_length=500)
    supported: StrictBool
    evidence: list[EvidenceQuote] = Field(default_factory=list, max_length=8)


class EvidenceVerdict(StrictModel):
    answerable: StrictBool
    requirements: list[EvidenceRequirement] = Field(min_length=1, max_length=8)
    missing_information: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def check_consistent_verdict(self):
        if self.answerable != all(part.supported for part in self.requirements):
            raise ValueError("整体可回答性与子项判断矛盾")
        if self.answerable and self.missing_information:
            raise ValueError("可回答时不能同时声明缺少事实")
        return self


class EvidenceDecision(StrictModel):
    status: Literal["supported", "insufficient", "invalid", "unavailable"]
    reason: str
    used_model: bool = False
    model_calls: int = 0
    recovery_used: bool = False
    retained_chunk_ids: list[str] = Field(default_factory=list)
    verdict: EvidenceVerdict | None = None


class EvidenceJudge(Protocol):
    def assess_evidence(self, question: str, passages: list[dict]) -> str: ...


def _compact(value: str) -> str:
    # Permit whitespace formatting changes, never added or paraphrased wording.
    return re.sub(r"\s+", "", value)


class EvidenceGate:
    """Fail closed on missing facts, untraceable quotes or unavailable checks.

    Exact quote validation proves provenance, not entailment. Semantic sufficiency
    remains a model judgement and needs evaluation on unseen questions.
    """

    def __init__(self, judge: EvidenceJudge, *, recover_once: bool = False):
        self._judge = judge
        self._recover_once = recover_once

    def evaluate(self, question: str, hits: Sequence[SearchHit]) -> EvidenceDecision:
        decision = self._evaluate_once(question, hits)
        decision.model_calls = int(decision.used_model)
        review = getattr(self._judge, "review_evidence", None)
        if (
            self._recover_once
            and decision.status == "insufficient"
            and decision.used_model
            and callable(review)
        ):
            reviewed = self._evaluate_once(question, hits, review=True)
            reviewed.model_calls = decision.model_calls + int(reviewed.used_model)
            reviewed.recovery_used = True
            return reviewed
        return decision

    def _evaluate_once(
        self,
        question: str,
        hits: Sequence[SearchHit],
        *,
        review: bool = False,
    ) -> EvidenceDecision:
        context = build_retrieval_context(question, hits)
        visible_ids = {s.chunk_id: s.citation_id for s in context.sources}
        visible_hits = [h for h in hits if h.chunk.chunk_id in visible_ids]
        if not visible_hits:
            return EvidenceDecision(status="insufficient", reason="no_visible_evidence")
        passages = [
            {
                "citation_id": visible_ids[h.chunk.chunk_id],
                "source": h.chunk.source,
                "text": h.chunk.content,
            }
            for h in visible_hits
        ]
        try:
            method = (
                self._judge.review_evidence if review else self._judge.assess_evidence
            )
            raw = method(question, passages)
        except (
            OpenAIError,
            RuntimeError,
            TimeoutError,
            ValueError,
            TypeError,
        ) as error:
            # Provider bodies and exception text may contain private information.
            logger.warning(
                "evidence_check_unavailable stage=evidence metadata=%s",
                json.dumps(provider_error_fields(error), sort_keys=True),
            )
            return EvidenceDecision(
                status="unavailable",
                reason="evidence_check_unavailable",
                used_model=True,
            )
        try:
            verdict = EvidenceVerdict.model_validate_json(raw)
        except (ValidationError, ValueError, TypeError):
            return EvidenceDecision(
                status="invalid", reason="invalid_evidence_response", used_model=True
            )
        if not verdict.answerable or any(not p.supported for p in verdict.requirements):
            return EvidenceDecision(
                status="insufficient",
                reason="missing_requested_facts",
                used_model=True,
                verdict=verdict,
            )
        by_citation = {visible_ids[h.chunk.chunk_id]: h for h in visible_hits}
        supported_ids = set()
        invalid = bool(verdict.missing_information)
        numeric_parts = 0
        for part in verdict.requirements:
            invalid |= not part.evidence
            for quote in part.evidence:
                hit = by_citation.get(quote.citation_id)
                if hit is None or _compact(quote.quote) not in _compact(
                    hit.chunk.content
                ):
                    invalid = True
                else:
                    supported_ids.add(hit.chunk.chunk_id)
            if NUMERIC_QUESTION.search(question) and NUMERIC_SLOT.search(
                part.question_part
            ):
                numeric_parts += 1
                # Generic text mentioning a metric/retry cannot justify its value.
                invalid |= not any(
                    NUMBER.search(q.quote) or EXPLICIT_VALUE.search(q.quote)
                    for q in part.evidence
                )
        if NUMERIC_QUESTION.search(question) and not numeric_parts:
            invalid = True
        if invalid or not supported_ids:
            return EvidenceDecision(
                status="invalid",
                reason="unsupported_or_untraceable_evidence",
                used_model=True,
                verdict=verdict,
            )
        return EvidenceDecision(
            status="supported",
            reason="all_requirements_have_verified_quotes",
            used_model=True,
            verdict=verdict,
            retained_chunk_ids=[
                h.chunk.chunk_id
                for h in visible_hits
                if h.chunk.chunk_id in supported_ids
            ],
        )
