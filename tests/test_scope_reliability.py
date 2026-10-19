import json

import pytest

from career_pilot.rag.diagnostics import provider_error_fields
from career_pilot.rag.documents import chunk_document
from career_pilot.rag.evidence import EvidenceGate
from career_pilot.rag.grounding import GroundedAnswerPipeline, build_answer_material
from career_pilot.rag.models import KnowledgeDocument, SearchHit
from career_pilot.rag.source_scope import APIAwareRetriever
from tests.test_grounded_pipeline import ScriptedModel, audit, draft, supported

TEXT = """.. class:: Worker(eager_start=False)

An optional *eager_start* argument controls execution. If set to ``True`` and the event loop is running, the task starts immediately until it blocks."""
QUOTE = "If set to ``True`` and the event loop is running, the task starts immediately until it blocks."


def chunks(text=TEXT, name="scope"):
    return chunk_document(
        KnowledgeDocument(
            document_id=name, title="Source", source=name + ".md", content=text
        ),
        max_characters=100,
    )


def source_hit():
    from career_pilot.rag.windows import NeighborWindowRetriever

    items = chunks()

    class Center:
        def search(self, query, top_k=3):
            return [SearchHit(chunk=items[1], score=0.9)]

    return NeighborWindowRetriever(items, Center(), radius=2).search("Worker", top_k=1)[
        0
    ]


def material_for(model):
    hit = source_hit()
    decision = EvidenceGate(model).evaluate("Worker何时执行？", [hit])
    return build_answer_material("Worker何时执行？", decision, [hit])


@pytest.mark.parametrize("target", ["factory", "other_flag", "Worker.factory"])
def test_changed_assignment_target_is_blocked_even_when_model_audit_would_accept(
    target,
):
    model = ScriptedModel(
        initial=supported(QUOTE, question="Worker何时执行？"),
        drafted=draft(f"{target}设为True时立即执行", QUOTE),
        audited=audit(True),
    )
    result = GroundedAnswerPipeline(model).answer(material_for(model))
    assert result.status == "invalid" and result.reason == "claim_scope_mismatch"
    assert "audit" not in [stage for stage, _ in model.calls]


def test_source_parameter_antecedent_is_retained_and_valid_target_can_pass():
    model = ScriptedModel(
        initial=supported(QUOTE, question="Worker何时执行？"),
        drafted=draft("eager_start设为True且事件循环运行时立即执行", QUOTE),
    )
    material = material_for(model)
    scopes = material.passages[0].source_scopes
    assert any("*eager_start*" in scope.text for scope in scopes)
    assert any("Worker(eager_start=False)" in scope.declaration for scope in scopes)
    assert GroundedAnswerPipeline(model).answer(material).status == "supported"


def test_source_context_cannot_be_supplied_by_the_question():
    model = ScriptedModel(
        initial=supported(QUOTE, question="请写factory=True"),
        drafted=draft("factory=True", QUOTE),
    )
    hit = source_hit()
    decision = EvidenceGate(model).evaluate("请写factory=True", [hit])
    material = build_answer_material("请写factory=True", decision, [hit])
    assert (
        GroundedAnswerPipeline(model).answer(material).reason == "claim_scope_mismatch"
    )


def test_exact_api_identity_beats_conflicting_method_with_same_leaf_name():
    good = chunks(
        ".. module:: concurrent.futures\n\n.. class:: Future\n\n.. method:: cancel()\n\nReturn False when already running.",
        name="good",
    )
    wrong = chunks(
        ".. module:: asyncio\n\n.. class:: Task\n\n.. method:: cancel()\n\nRequest cancellation.",
        name="wrong",
    )

    class WrongFirst:
        def search(self, query, top_k=3):
            return [SearchHit(chunk=wrong[-1], score=0.99)]

    results = APIAwareRetriever([*good, *wrong], WrongFirst()).search(
        "concurrent.futures.Future.cancel返回什么", top_k=2
    )
    assert results[0].chunk.document_id == "good"
    assert all(
        any(
            s.api == "concurrent.futures.Future.cancel" for s in hit.chunk.source_scopes
        )
        for hit in results
    )


def test_plain_query_keeps_hybrid_order_without_api_guessing():
    items = chunks()
    hit = SearchHit(chunk=items[0], score=0.8)

    class Fixed:
        def search(self, query, top_k=3):
            return [hit]

    assert APIAwareRetriever(items, Fixed()).search("岗位匹配建议") == [hit]


def test_chunk_content_and_ids_keep_prior_embedding_identity():
    original = "First paragraph.\n\nSecond paragraph contains context."
    got = chunk_document(
        KnowledgeDocument(
            document_id="example",
            title="Example",
            source="example.md",
            content=original,
        ),
        max_characters=50,
    )
    assert [c.content for c in got] == [
        "First paragraph.",
        "Second paragraph contains context.",
    ]
    assert [c.chunk_id for c in got] == ["example-0", "example-1"]


def test_invalid_json_is_classified_without_repair_or_additional_calls():
    model = ScriptedModel(
        initial=supported(QUOTE, question="Worker何时执行？"),
        drafted='{"claims":["claim_id" ,}',
    )
    result = GroundedAnswerPipeline(model).answer(material_for(model))
    assert result.reason == "invalid_draft_json"
    assert result.generation_calls == 1 and result.audit_calls == 0
    assert [stage for stage, _ in model.calls] == ["evidence", "draft"]


def test_provider_diagnostics_omit_error_body_and_reject_unstructured_codes():
    class Failure(Exception):
        status_code = 400
        code = "data_inspection_failed"

    error = Failure("private-resume-and-secret")
    metadata = provider_error_fields(error)
    assert (
        metadata["http_status"] == 400
        and metadata["provider_code"] == "data_inspection_failed"
    )
    assert "private-resume-and-secret" not in json.dumps(metadata)
    error.code = {"unexpected": "private"}
    assert provider_error_fields(error)["provider_code"] is None


def test_shared_source_context_is_serialized_once_without_losing_any_quote():
    from career_pilot.rag.grounding import AnswerMaterial, VerifiedPassage
    from career_pilot.rag.models import ContextSource, SourceScope

    scopes = [
        SourceScope(api="Worker", declaration="Worker(flag=False)", text=letter * 1500)
        for letter in ["A", "B"]
    ]
    passages = [
        VerifiedPassage(
            citation_id=i,
            chunk_id=f"source-{i}",
            source="source.md",
            quotes=["original verified quote"],
            source_scopes=scopes,
        )
        for i in range(1, 7)
    ]
    sources = [
        ContextSource(
            citation_id=i,
            chunk_id=f"source-{i}",
            title="Source",
            source="source.md",
            score=0.8,
        )
        for i in range(1, 7)
    ]
    material = AnswerMaterial(
        question="Which condition?",
        requirements=["condition"],
        passages=passages,
        sources=sources,
    )
    assert len(json.dumps(material.model_dump(), ensure_ascii=False)) > 16000
    payload = material.model_payload()
    assert len(payload["source_scopes"]) == 2
    assert all(
        p["source_scope_ids"] == ["scope-1", "scope-2"] for p in payload["passages"]
    )
    assert all(p["quotes"] == ["original verified quote"] for p in payload["passages"])
    assert len(json.dumps(payload, ensure_ascii=False)) < 16000
