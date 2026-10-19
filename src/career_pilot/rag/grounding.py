"""Generate atomic, cited claims from verified quotes and audit each claim."""

import json
import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Literal, Protocol

from openai import OpenAIError
from pydantic import Field, StrictBool, StrictInt, ValidationError, model_validator

from career_pilot.models import StrictModel
from career_pilot.rag.evidence import EvidenceDecision, EvidenceQuote, _compact
from career_pilot.rag.models import ContextSource, SearchHit

logger = logging.getLogger(__name__)
ARABIC_NUMBER = re.compile(r"(?<![A-Za-z0-9_])\d+(?:[,.]\d+)*(?:[eE][+-]?\d+)?")
MODEL_ERRORS = (OpenAIError, RuntimeError, TimeoutError, ValueError, TypeError)


class VerifiedPassage(StrictModel):
    citation_id: StrictInt = Field(ge=1)
    chunk_id: str
    source: str
    quotes: list[str] = Field(min_length=1, max_length=64)


class AnswerMaterial(StrictModel):
    question: str = Field(min_length=1, max_length=2000)
    requirements: list[str] = Field(min_length=1, max_length=8)
    passages: list[VerifiedPassage] = Field(min_length=1, max_length=8)
    sources: list[ContextSource] = Field(min_length=1, max_length=8)

    def model_payload(self) -> dict:
        return self.model_dump(include={"question", "requirements", "passages"})


class AnswerClaim(StrictModel):
    claim_id: StrictInt = Field(ge=1, le=8)
    text: str = Field(min_length=2, max_length=800)
    requirement_ids: list[StrictInt] = Field(min_length=1, max_length=8)
    evidence: list[EvidenceQuote] = Field(min_length=1, max_length=8)


class GroundedDraft(StrictModel):
    claims: list[AnswerClaim] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def check_claim_ids(self):
        if [c.claim_id for c in self.claims] != list(range(1, len(self.claims) + 1)):
            raise ValueError("陈述编号必须连续且不能重复")
        return self


class GroundedProposal(StrictModel):
    answerable: StrictBool
    claims: list[AnswerClaim] = Field(max_length=8)
    missing_information: list[str] = Field(max_length=8)

    @model_validator(mode="after")
    def check_decision(self):
        if self.answerable != bool(self.claims):
            raise ValueError("可回答时必须有陈述，资料不足时不能保留部分陈述")
        if self.answerable and self.missing_information:
            raise ValueError("完整回答不能同时声明缺少信息")
        if not self.answerable and not self.missing_information:
            raise ValueError("资料不足时应说明缺少的信息")
        return self


class ClaimCheck(StrictModel):
    claim_id: StrictInt = Field(ge=1, le=8)
    supported: StrictBool
    reason: str = Field(min_length=1, max_length=400)


class RequirementCheck(StrictModel):
    # Some providers add a redundant claim association; validate rather than
    # silently ignore it. All other unexpected fields remain forbidden.
    claim_id: StrictInt | None = Field(default=None, ge=1, le=8)
    requirement_id: StrictInt = Field(ge=1, le=8)
    answered: StrictBool
    reason: str = Field(min_length=1, max_length=400)


class AnswerAudit(StrictModel):
    fully_supported: StrictBool
    requirements_complete: StrictBool
    question_fully_answered: StrictBool
    requirement_checks: list[RequirementCheck] = Field(min_length=1, max_length=8)
    checks: list[ClaimCheck] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def check_overall(self):
        if len({c.claim_id for c in self.checks}) != len(self.checks):
            raise ValueError("陈述核验编号重复")
        if self.fully_supported != all(c.supported for c in self.checks):
            raise ValueError("整体回答核验与分项结果矛盾")
        if len({r.requirement_id for r in self.requirement_checks}) != len(
            self.requirement_checks
        ):
            raise ValueError("问题核验编号重复")
        if self.requirements_complete != all(
            r.answered for r in self.requirement_checks
        ):
            raise ValueError("整体问题覆盖与分项结果矛盾")
        return self


class GroundedAnswerResult(StrictModel):
    status: Literal["supported", "insufficient", "invalid", "unavailable"]
    reason: str
    answer: str = ""
    sources: list[ContextSource] = Field(default_factory=list)
    claims: list[AnswerClaim] = Field(default_factory=list)
    generation_calls: int = 0
    audit_calls: int = 0
    audit: AnswerAudit | None = None


class GroundedAnswerClient(Protocol):
    def draft_grounded_answer(self, material: dict) -> str: ...
    def propose_grounded_answer(self, material: dict) -> str: ...
    def audit_grounded_answer(self, material: dict, claims: list[dict]) -> str: ...


def build_answer_material(
    question: str,
    decision: EvidenceDecision,
    hits: list[SearchHit],
) -> AnswerMaterial:
    """Expose only source-validated quotes, preserving their original IDs."""
    if decision.status != "supported" or decision.verdict is None:
        raise ValueError("回答需要已通过的证据核验")
    # Reconstruct exactly the same visible source map used by the evidence gate.
    from career_pilot.rag.context import build_retrieval_context

    context = build_retrieval_context(question, hits)
    sources = {s.citation_id: s for s in context.sources}
    by_chunk = {h.chunk.chunk_id: h for h in hits}
    quotes: dict[int, list[str]] = {}
    for requirement in decision.verdict.requirements:
        if not requirement.supported or not requirement.evidence:
            raise ValueError("回答要求缺少已核验原文")
        for evidence in requirement.evidence:
            source = sources.get(evidence.citation_id)
            if source is None or source.chunk_id not in by_chunk:
                raise ValueError("回答证据来源不在实际上下文中")
            if source.chunk_id not in decision.retained_chunk_ids:
                raise ValueError("回答证据来源未获核验")
            if _compact(evidence.quote) not in _compact(
                by_chunk[source.chunk_id].chunk.content
            ):
                raise ValueError("回答证据原文无法核对")
            existing = quotes.setdefault(evidence.citation_id, [])
            if evidence.quote not in existing:
                existing.append(evidence.quote)
    material = AnswerMaterial(
        question=question,
        requirements=[p.question_part for p in decision.verdict.requirements],
        passages=[
            VerifiedPassage(
                citation_id=i,
                chunk_id=sources[i].chunk_id,
                source=sources[i].source,
                quotes=q,
            )
            for i, q in quotes.items()
        ],
        sources=[s for i, s in sources.items() if i in quotes],
    )
    # Keep the complete evidence contract; never silently drop a requirement.
    if len(json.dumps(material.model_payload(), ensure_ascii=False)) > 16000:
        raise ValueError("已核验证据超过回答上下文上限")
    return material


def split_question_requirements(question: str) -> list[str]:
    """Keep separately punctuated questions visible without semantic guessing.

    Preserve every clause. A comma alone does not split an item. Excess clauses
    are merged into the last slot rather than dropped. Audit also sees the whole
    original question, so this is not assumed to be complete semantic parsing.
    """
    parts = [
        p.strip()
        for p in re.split(r"(?<=？)|(?<=\?)(?=\s|$)|\n+", question)
        if p.strip()
    ]
    return parts[:7] + [" ".join(parts[7:])] if len(parts) > 8 else parts


def build_candidate_answer_material(
    question: str, hits: list[SearchHit]
) -> AnswerMaterial:
    """Verify source provenance, leaving answer sufficiency to the final audit.

    This recovery material contains whole visible source chunks. They have not
    passed the earlier semantic gate; only the source text is verified. No draft
    is released until exact quotes, claim support and original-question coverage
    have all passed the same checks as the normal path.
    """
    from career_pilot.rag.context import build_retrieval_context

    context = build_retrieval_context(question, hits)
    by_chunk = {hit.chunk.chunk_id: hit for hit in hits}
    material = AnswerMaterial(
        question=question,
        requirements=split_question_requirements(question),
        passages=[
            VerifiedPassage(
                citation_id=source.citation_id,
                chunk_id=source.chunk_id,
                source=source.source,
                quotes=[by_chunk[source.chunk_id].chunk.content],
            )
            for source in context.sources
        ],
        sources=context.sources,
    )
    if len(json.dumps(material.model_payload(), ensure_ascii=False)) > 16000:
        raise ValueError("候选证据超过回答上下文上限")
    return material


def _numbers(text: str) -> set[str]:
    found = set()
    for value in ARABIC_NUMBER.findall(unicodedata.normalize("NFKC", text)):
        try:
            found.add(str(Decimal(value.replace(",", "")).normalize()))
        except InvalidOperation:
            found.add(value)
    return found


def validate_draft(draft: GroundedDraft, material: AnswerMaterial) -> None:
    by_id = {p.citation_id: p for p in material.passages}
    expected = set(range(1, len(material.requirements) + 1))
    covered = set()
    for claim in draft.claims:
        ids = set(claim.requirement_ids)
        if len(ids) != len(claim.requirement_ids) or not ids <= expected:
            raise ValueError("回答陈述的问题编号无效")
        covered |= ids
        if re.search(r"\[资料[^\]]*\]", claim.text):
            raise ValueError("引用编号由程序生成，陈述文本不得自行插入")
        for evidence in claim.evidence:
            passage = by_id.get(evidence.citation_id)
            if passage is None or not any(
                _compact(evidence.quote) in _compact(q) for q in passage.quotes
            ):
                raise ValueError("回答引用超出已核验的原文")
        supporting_text = " ".join(e.quote for e in claim.evidence)
        if not _numbers(claim.text) <= _numbers(supporting_text):
            raise ValueError("回答新增了引用中不存在的数值")
        for url in re.findall(r"https?://[^\s)\]}>]+", claim.text):
            if url not in supporting_text:
                raise ValueError("回答新增了无依据链接")
    if covered != expected:
        raise ValueError("回答遗漏了问题的部分要求")


class GroundedAnswerPipeline:
    """One bounded draft call and one semantic audit, without automatic retries."""

    def __init__(self, client: GroundedAnswerClient):
        self._client = client

    @property
    def supports_proposal(self) -> bool:
        return callable(getattr(self._client, "propose_grounded_answer", None))

    def answer(
        self, material: AnswerMaterial, *, proposal: bool = False
    ) -> GroundedAnswerResult:
        try:
            method = (
                self._client.propose_grounded_answer
                if proposal
                else self._client.draft_grounded_answer
            )
            raw = method(material.model_payload())
        except MODEL_ERRORS as error:
            logger.warning(
                "answer_draft_unavailable error_type=%s", type(error).__name__
            )
            return GroundedAnswerResult(
                status="unavailable",
                reason="answer_generation_unavailable",
                generation_calls=1,
            )
        try:
            if proposal:
                proposed = GroundedProposal.model_validate_json(raw)
                if not proposed.answerable:
                    return GroundedAnswerResult(
                        status="insufficient",
                        reason="no_complete_grounded_proposal",
                        generation_calls=1,
                    )
                draft = GroundedDraft(claims=proposed.claims)
            else:
                draft = GroundedDraft.model_validate_json(raw)
            validate_draft(draft, material)
        except (ValidationError, ValueError, TypeError):
            return GroundedAnswerResult(
                status="invalid",
                reason="invalid_or_untraceable_claims",
                generation_calls=1,
            )
        claims = [c.model_dump() for c in draft.claims]
        try:
            raw_audit = self._client.audit_grounded_answer(
                material.model_payload(), claims
            )
        except MODEL_ERRORS as error:
            logger.warning(
                "answer_audit_unavailable error_type=%s", type(error).__name__
            )
            return GroundedAnswerResult(
                status="unavailable",
                reason="answer_audit_unavailable",
                generation_calls=1,
                audit_calls=1,
            )
        try:
            audit = AnswerAudit.model_validate_json(raw_audit)
            if {r.requirement_id for r in audit.requirement_checks} != set(
                range(1, len(material.requirements) + 1)
            ):
                raise ValueError("问题覆盖审查未包含全部原问题要求")
            if {c.claim_id for c in audit.checks} != {c.claim_id for c in draft.claims}:
                raise ValueError("回答核验未完整覆盖所有陈述")
            by_claim_id = {c.claim_id: c for c in draft.claims}
            for check in audit.requirement_checks:
                if check.claim_id is not None:
                    claim = by_claim_id.get(check.claim_id)
                    if (
                        claim is None
                        or check.requirement_id not in claim.requirement_ids
                    ):
                        raise ValueError("问题核验关联了不存在或不对应的陈述")
        except (ValidationError, ValueError, TypeError):
            return GroundedAnswerResult(
                status="invalid",
                reason="invalid_answer_audit",
                generation_calls=1,
                audit_calls=1,
            )
        if not audit.fully_supported:
            return GroundedAnswerResult(
                status="invalid",
                reason="unsupported_answer_claim",
                generation_calls=1,
                audit_calls=1,
                claims=draft.claims,
                audit=audit,
            )
        if not audit.requirements_complete:
            return GroundedAnswerResult(
                status="invalid",
                reason="incomplete_question_coverage",
                generation_calls=1,
                audit_calls=1,
                claims=draft.claims,
                audit=audit,
            )
        if not audit.question_fully_answered:
            return GroundedAnswerResult(
                status="invalid",
                reason="original_question_incomplete",
                generation_calls=1,
                audit_calls=1,
                claims=draft.claims,
                audit=audit,
            )
        used_ids = {e.citation_id for c in draft.claims for e in c.evidence}
        answer = "\n\n".join(
            c.text
            + "".join(f"[资料{i}]" for i in sorted({e.citation_id for e in c.evidence}))
            for c in draft.claims
        )
        return GroundedAnswerResult(
            status="supported",
            reason="all_claims_have_verified_support",
            answer=answer,
            sources=[s for s in material.sources if s.citation_id in used_ids],
            claims=draft.claims,
            audit=audit,
            generation_calls=1,
            audit_calls=1,
        )
