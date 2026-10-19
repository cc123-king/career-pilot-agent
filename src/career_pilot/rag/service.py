import logging
import re
from collections.abc import Sequence
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from career_pilot.rag.context import build_retrieval_context
from career_pilot.rag.evidence import EvidenceGate
from career_pilot.rag.grounding import (
    GroundedAnswerPipeline,
    build_answer_material,
    build_candidate_answer_material,
)
from career_pilot.rag.models import (
    KnowledgeChunk,
    RAGAnswer,
    RetrievalContext,
    SearchHit,
)
from career_pilot.rag.retrieval import search_chunks
from career_pilot.text_utils import normalize_text

logger = logging.getLogger(__name__)


class ContextAnswerer(Protocol):
    def answer_with_context(self, question: str, context: RetrievalContext) -> str: ...


class ChunkRetriever(Protocol):
    def search(self, query: str, *, top_k: int = 3) -> list[SearchHit]: ...


class RAGService:
    """Retrieve candidates, check sufficiency, then generate a grounded answer.

    API and demo entry points supply an EvidenceGate. It is optional only for
    compatibility with custom answerers and isolated retrieval tests.
    """

    def __init__(
        self,
        chunks: Sequence[KnowledgeChunk],
        llm_client: ContextAnswerer,
        *,
        retriever: ChunkRetriever | None = None,
        top_k: int = 3,
        min_score: float = 0.05,
        evidence_gate: EvidenceGate | None = None,
        answer_guard: GroundedAnswerPipeline | None = None,
        answer_first_recovery: bool = False,
    ) -> None:
        if not chunks:
            raise ValueError("知识分块不能为空")
        if top_k < 1:
            raise ValueError("top_k 必须大于等于 1")
        if not 0 <= min_score <= 1:
            raise ValueError("min_score 必须在 0 到 1 之间")
        self._chunks = list(chunks)
        self._llm_client = llm_client
        self._retriever = retriever
        self._top_k = top_k
        self._min_score = min_score
        if answer_guard is not None and evidence_gate is None:
            raise ValueError("逐项回答核验需要先配置证据核验")
        self._evidence_gate = evidence_gate
        self._answer_guard = answer_guard
        if answer_first_recovery and answer_guard is None:
            raise ValueError("回答恢复必须配置完整的原文回答核验")
        if answer_first_recovery and getattr(evidence_gate, "_recover_once", False):
            raise ValueError("不能同时启用布尔复核和回答恢复")
        self._answer_first_recovery = answer_first_recovery

    def search(self, query: str, *, top_k: int = 3) -> list[SearchHit]:
        """Raw ranked retrieval for career advice, without a model judgement."""
        normalized_query = normalize_text(query)
        if not normalized_query:
            raise ValueError("查询不能为空")
        if len(normalized_query) > 2000:
            raise ValueError("查询不能超过 2000 字符")
        if top_k < 1:
            raise ValueError("top_k 必须大于等于 1")
        if self._retriever is not None:
            return self._retriever.search(normalized_query, top_k=top_k)
        return search_chunks(normalized_query, self._chunks, top_k=top_k)

    def answer(self, question: str) -> RAGAnswer:
        started_at = perf_counter()
        request_id = uuid4().hex[:12]
        question = normalize_text(question)
        if not question:
            logger.warning(
                "rag_request_rejected request_id=%s reason=empty_question", request_id
            )
            raise ValueError("问题不能为空")
        if len(question) > 2000:
            raise ValueError("问题不能超过 2000 字符")
        logger.info(
            "rag_request_started request_id=%s query_length=%d chunk_count=%d "
            "top_k=%d min_score=%.3f",
            request_id,
            len(question),
            len(self._chunks),
            self._top_k,
            self._min_score,
        )
        hits = self.search(question, top_k=self._top_k)
        relevant = [h for h in hits if h.score >= self._min_score]
        logger.info(
            "rag_retrieval_finished request_id=%s candidate_count=%d "
            "relevant_count=%d elapsed_ms=%.2f",
            request_id,
            len(hits),
            len(relevant),
            (perf_counter() - started_at) * 1000,
        )
        verification_used_model = False
        evidence_status = "not_checked"
        evidence_reason = None
        llm_request_count = 0
        recovery_used = False

        def abstain(message: str) -> RAGAnswer:
            logger.info(
                "rag_request_finished request_id=%s used_model=%s source_count=0 "
                "evidence_status=%s elapsed_ms=%.2f",
                request_id,
                str(verification_used_model).lower(),
                evidence_status,
                (perf_counter() - started_at) * 1000,
            )
            return RAGAnswer(
                question=question,
                answer=message,
                sources=[],
                retrieved_count=0,
                candidate_count=len(hits),
                used_model=verification_used_model,
                verification_used_model=verification_used_model,
                generation_used_model=False,
                evidence_status=evidence_status,
                evidence_reason=evidence_reason,
                llm_request_count=llm_request_count,
                evidence_recovery_used=recovery_used,
            )

        if not relevant:
            evidence_status = "insufficient"
            evidence_reason = "no_relevant_candidates"
            return abstain("当前知识库中没有足够相关的资料。")
        if self._evidence_gate is not None:
            decision = self._evidence_gate.evaluate(question, relevant)
            verification_used_model = decision.used_model
            llm_request_count += decision.model_calls
            recovery_used = decision.recovery_used
            evidence_status, evidence_reason = decision.status, decision.reason
            outcome = None
            if (
                self._answer_first_recovery
                and self._answer_guard.supports_proposal
                and decision.status == "insufficient"
                and decision.used_model
            ):
                recovery_used = True
                try:
                    material = build_candidate_answer_material(question, relevant)
                except ValueError:
                    evidence_status, evidence_reason = (
                        "invalid",
                        "invalid_recovery_material",
                    )
                    return abstain("候选资料未通过原文校验，本次未生成回答。")
                outcome = self._answer_guard.answer(material, proposal=True)
                evidence_status = outcome.status
                evidence_reason = "answer_first_recovery_" + outcome.status
            if outcome is None and decision.status != "supported":
                if decision.status == "unavailable":
                    message = "暂时无法完成资料核验，本次未生成回答，请稍后重试。"
                elif decision.status == "invalid":
                    message = "资料核验结果未通过格式或原文校验，本次未生成回答。"
                else:
                    message = "当前资料不足以回答该问题，缺少可核对的原文依据。"
                return abstain(message)
            if self._answer_guard is not None:
                if outcome is None:
                    try:
                        material = build_answer_material(question, decision, relevant)
                    except ValueError:
                        evidence_status, evidence_reason = (
                            "invalid",
                            "invalid_answer_material",
                        )
                        return abstain("资料未通过原文核对，本次未生成回答。")
                    outcome = self._answer_guard.answer(material)
                llm_request_count += outcome.generation_calls + outcome.audit_calls
                if outcome.status == "supported":
                    answer = outcome.answer
                    sources = outcome.sources
                else:
                    if outcome.status == "insufficient":
                        answer = "当前资料不足以完整回答该问题，缺少可核对的原文依据。"
                    elif outcome.status == "unavailable":
                        answer = "暂时无法完成回答核验，请稍后重试。"
                    else:
                        answer = "回答未通过原文依据核验，本次不展示未经支持的结论。"
                    sources = []
                logger.info(
                    "rag_request_finished request_id=%s used_model=true source_count=%d "
                    "answer_status=%s llm_requests=%d elapsed_ms=%.2f",
                    request_id,
                    len(sources),
                    outcome.status,
                    llm_request_count,
                    (perf_counter() - started_at) * 1000,
                )
                return RAGAnswer(
                    question=question,
                    answer=answer,
                    sources=sources,
                    retrieved_count=len(sources),
                    candidate_count=len(hits),
                    used_model=True,
                    verification_used_model=verification_used_model,
                    generation_used_model=bool(outcome.generation_calls),
                    answer_check_used_model=bool(outcome.audit_calls),
                    evidence_status=evidence_status,
                    evidence_reason=evidence_reason,
                    evidence_recovery_used=recovery_used,
                    answer_status=outcome.status,
                    answer_reason=outcome.reason,
                    answer_claim_count=len(outcome.claims) if sources else 0,
                    llm_request_count=llm_request_count,
                )
            retained = set(decision.retained_chunk_ids)
            relevant = [h for h in relevant if h.chunk.chunk_id in retained]
        context = build_retrieval_context(question, relevant)
        if not context.sources:
            evidence_status, evidence_reason = "insufficient", "no_visible_evidence"
            return abstain("当前知识库中没有足够相关的资料。")
        model_answer = self._llm_client.answer_with_context(question, context)
        llm_request_count += 1
        if self._evidence_gate is not None:
            citations = {
                int(value) for value in re.findall(r"\[资料(\d+)\]", model_answer)
            }
            allowed = {s.citation_id for s in context.sources}
            if not citations or not citations <= allowed:
                return RAGAnswer(
                    question=question,
                    answer="回答未通过引用核对，请补充资料后重试。",
                    sources=[],
                    retrieved_count=0,
                    candidate_count=len(hits),
                    used_model=True,
                    verification_used_model=verification_used_model,
                    generation_used_model=True,
                    evidence_status="invalid",
                    evidence_reason="invalid_answer_citations",
                    llm_request_count=llm_request_count,
                    evidence_recovery_used=recovery_used,
                )
        logger.info(
            "rag_request_finished request_id=%s used_model=true source_count=%d "
            "evidence_status=%s elapsed_ms=%.2f",
            request_id,
            len(context.sources),
            evidence_status,
            (perf_counter() - started_at) * 1000,
        )
        return RAGAnswer(
            question=question,
            answer=model_answer,
            sources=context.sources,
            retrieved_count=len(context.sources),
            candidate_count=len(hits),
            used_model=True,
            verification_used_model=verification_used_model,
            generation_used_model=True,
            evidence_status=evidence_status,
            evidence_reason=evidence_reason,
            llm_request_count=llm_request_count,
            evidence_recovery_used=recovery_used,
        )
