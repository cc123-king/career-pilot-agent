import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from career_pilot import api
from career_pilot.history import HistoryStore, PersistentKnowledgeStore
from career_pilot.models import ResumeProfile
from career_pilot.multimodal.models import ExtractedDocument, ExtractedPage
from career_pilot.review import (
    JobRequirements,
    ReviewRequest,
    SourcePage,
    confirm_job,
    confirm_review,
    create_review,
    model_extract,
    model_extract_job,
    source_facts,
)


def request():
    return ReviewRequest(
        filename="resume.pdf",
        pages=[SourcePage(page_number=1, text=api.ANALYSIS_EXAMPLE["resume_text"])],
        job_description=api.ANALYSIS_EXAMPLE["job_description"],
        company="示例科技",
        role="Agent 开发工程师",
    )


def analyzed(req, store):
    packet = create_review(req, store)
    return confirm_job(
        packet["review_id"], [f["fact_id"] for f in packet["job_facts"]], store
    )


def test_source_offsets_preserve_actual_page_whitespace():
    pages = [SourcePage(page_number=2, text="技能：Fast API\n以及 Python。")]
    facts, missing = source_facts(
        ResumeProfile(skills=["FastAPI", "Python"]), pages, "x.pdf"
    )
    assert not missing and facts[0]["page_number"] == 2
    f = facts[0]
    assert pages[0].text[f["start"] : f["end"]] == f["quote"] == "Fast API"


def test_model_hallucinations_are_rejected_with_bounded_retry():
    calls = []

    class Fake:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps({"skills": ["Kubernetes"]})
                        )
                    )
                ]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Fake()))
    with pytest.raises(ValueError, match="Ungrounded"):
        model_extract(
            [SourcePage(page_number=1, text="实际只有Python")],
            client,
            SimpleNamespace(model="fake"),
        )
    assert len(calls) == 2


def test_review_confirmation_and_history_survive_restart(tmp_path):
    path = tmp_path / "state.db"
    store = HistoryStore(path)
    packet = analyzed(request(), store)
    assert packet["status"] == "needs_confirmation" and packet["analysis"]
    assert packet["facts"] and packet["analysis"]["match_result"]["score"] == 85
    fact_ids = [f["fact_id"] for f in packet["facts"]]
    confirmed = confirm_review(packet["review_id"], fact_ids, store)
    reloaded = HistoryStore(path).get(packet["review_id"])
    assert confirmed == reloaded and reloaded["status"] == "confirmed"
    assert all(f["value"] in reloaded["draft_markdown"] for f in reloaded["facts"])


def test_unrecognized_resume_routes_to_clarification(tmp_path):
    req = request()
    req.pages = [
        SourcePage(page_number=1, text="这是一份没有技能和项目字段的待补充简历文本。")
    ]
    packet = create_review(req, HistoryStore(tmp_path / "s.db"))
    assert packet["status"] == "needs_clarification" and packet["analysis"] is None
    assert packet["clarification_questions"]


def test_partial_selection_excludes_unconfirmed_facts(tmp_path):
    store = HistoryStore(tmp_path / "s.db")
    packet = analyzed(request(), store)
    fact = packet["facts"][0]
    result = confirm_review(packet["review_id"], [fact["fact_id"]], store)
    assert result["status"] == "partially_confirmed"
    assert result["draft_markdown"] == "# 已确认的简历事实\n\n" + fact["value"]


def test_forged_confirmation_does_not_modify_record(tmp_path):
    store = HistoryStore(tmp_path / "s.db")
    packet = analyzed(request(), store)
    with pytest.raises(ValueError):
        confirm_review(packet["review_id"], ["forged"], store)
    assert store.get(packet["review_id"])["status"] == "needs_confirmation"


def test_failed_model_falls_back_without_inventing_facts(tmp_path):
    req = request()
    req.parsing_mode = "model"

    def fail(_):
        raise RuntimeError("unavailable")

    packet = create_review(req, HistoryStore(tmp_path / "s.db"), fail, fail)
    assert packet["parsing_mode"] == "rules" and packet["warnings"]
    assert all("Kubernetes" not in f["value"] for f in packet["facts"])


def test_uploaded_knowledge_survives_restart_and_clear(tmp_path):
    path = tmp_path / "s.db"
    store = PersistentKnowledgeStore(path)
    doc = ExtractedDocument(
        filename="guide.pdf",
        source_path="guide.pdf",
        source_type="pdf",
        pages=[
            ExtractedPage(
                page_number=3,
                text="Python项目应提供可复现测试与来源。",
                extraction_method="native_text",
            )
        ],
    )
    store.add_document(doc)
    second = PersistentKnowledgeStore(path)
    assert second.document_count == 1 and second.list_chunks()[0].page_number == 3
    second.clear()
    assert store.document_count == 0


def test_review_api_history_confirm_and_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("CAREER_STATE_DB", str(tmp_path / "api.db"))
    client = TestClient(api.app)
    created = client.post("/api/career/reviews", json=request().model_dump()).json()
    rid = created["review_id"]
    assert client.get("/api/career/reviews").json()[0]["id"] == rid
    assert created["analysis"] is None
    assert (
        client.post(
            f"/api/career/reviews/{rid}/confirm-job",
            json={"fact_ids": [f["fact_id"] for f in created["job_facts"]]},
        ).status_code
        == 200
    )
    facts = [f["fact_id"] for f in created["facts"]]
    assert (
        client.post(
            f"/api/career/reviews/{rid}/confirm", json={"fact_ids": facts}
        ).json()["status"]
        == "confirmed"
    )
    assert client.get(f"/api/career/reviews/{rid}").json()["draft_markdown"]
    assert client.delete(f"/api/career/reviews/{rid}").status_code == 200
    assert client.get(f"/api/career/reviews/{rid}").status_code == 404


def test_duplicate_pages_and_unknown_mode_are_rejected():
    data = request().model_dump()
    data["pages"] *= 2
    with pytest.raises(ValueError):
        ReviewRequest.model_validate(data)
    data = request().model_dump()
    data["parsing_mode"] = "autonomous"
    with pytest.raises(ValueError):
        ReviewRequest.model_validate(data)


def test_document_review_page_callbacks_round_trip(tmp_path, monkeypatch):
    from career_pilot import review_ui

    monkeypatch.setenv("CAREER_STATE_DB", str(tmp_path / "page.db"))
    file = tmp_path / "resume.txt"
    file.write_text(api.ANALYSIS_EXAMPLE["resume_text"], encoding="utf-8")
    view = review_ui.analyze(
        str(file),
        api.ANALYSIS_EXAMPLE["job_description"],
        "示例科技",
        "Agent 开发工程师",
        "rules",
    )
    record_id, status, rows = view[:3]
    assert rows and "needs_job_confirmation" in status
    packet = HistoryStore().get(record_id)
    job_ids = [f["fact_id"] for f in packet["job_facts"]]
    view = review_ui.confirm_job_selection(record_id, job_ids)
    assert "85.00" in view[4]
    packet = HistoryStore().get(record_id)
    draft, status = review_ui.confirm(
        record_id, [f["fact_id"] for f in packet["facts"]]
    )
    assert draft and "confirmed" in status
    restored = review_ui.load(record_id)
    assert restored[0] == record_id and restored[5] == draft
    assert restored[8] == api.ANALYSIS_EXAMPLE["job_description"]
    assert restored[12] == "keyword"
    assert review_ui.history()[0][0] == record_id


def test_unrecognized_job_never_produces_a_zero_score(tmp_path):
    req = request()
    req.job_description = "我们正在招聘开发工程师，熟悉Python和FastAPI，了解RAG者优先。"
    store = HistoryStore(tmp_path / "s.db")
    packet = create_review(req, store)
    assert packet["analysis"] is None and packet["status"] == "needs_clarification"
    assert any("岗位" in q for q in packet["clarification_questions"])
    with pytest.raises(ValueError):
        confirm_review(
            packet["review_id"], [f["fact_id"] for f in packet["facts"]], store
        )


def test_no_retrieval_or_score_before_human_job_confirmation(tmp_path, monkeypatch):
    selected_modes = []
    real_selector = api.get_career_retriever

    def selector(mode):
        selected_modes.append(mode)
        return real_selector("keyword")

    monkeypatch.setattr(api, "get_career_retriever", selector)
    req = request()
    req.retrieval_mode = "hybrid"
    store = HistoryStore(tmp_path / "s.db")
    packet = create_review(req, store)
    assert packet["analysis"] is None and not selected_modes
    with pytest.raises(ValueError, match="先确认岗位"):
        confirm_review(
            packet["review_id"], [f["fact_id"] for f in packet["facts"]], store
        )
    packet = confirm_job(
        packet["review_id"], [f["fact_id"] for f in packet["job_facts"]], store
    )
    assert selected_modes == ["hybrid"]
    assert packet["analysis"]["retrieval"]["mode"] == "hybrid"
    assert packet["analysis"]["retrieval"]["candidate_k"] == 6
    assert packet["analysis"]["knowledge_sources"]
    assert (
        HistoryStore(tmp_path / "s.db").get(packet["review_id"])["request"][
            "retrieval_mode"
        ]
        == "hybrid"
    )


def test_hybrid_unavailable_does_not_fallback_or_change_saved_record(
    tmp_path, monkeypatch
):
    from fastapi import HTTPException

    def unavailable(_):
        raise HTTPException(503, "混合检索配置无效")

    monkeypatch.setattr(api, "get_career_retriever", unavailable)
    req = request()
    req.retrieval_mode = "hybrid"
    store = HistoryStore(tmp_path / "s.db")
    packet = create_review(req, store)
    with pytest.raises(HTTPException):
        confirm_job(
            packet["review_id"], [f["fact_id"] for f in packet["job_facts"]], store
        )
    assert store.get(packet["review_id"]) == packet


def test_job_model_extract_is_grounded_and_category_selection_controls_match(tmp_path):
    req = request()
    req.parsing_mode = "model"
    req.job_description = (
        "熟悉Python、FastAPI，具有RAG项目经验者优先；参与服务开发和测试。"
    )
    store = HistoryStore(tmp_path / "s.db")
    from career_pilot.parsers import parse_resume_text

    packet = create_review(
        req,
        store,
        lambda pages: parse_resume_text(pages[0].text),
        lambda _: JobRequirements(
            required_skills=["Python", "FastAPI"], preferred_skills=["RAG"]
        ),
    )
    assert (
        packet["job_parsing_mode"] == "model" and not packet["clarification_questions"]
    )
    assert all(
        req.job_description[f["start"] : f["end"]] == f["quote"]
        for f in packet["job_facts"]
    )
    python = next(f for f in packet["job_facts"] if f["value"] == "Python")
    pending = confirm_job(packet["review_id"], [python["fact_id"]], store)
    assert pending["analysis"] is None and pending["pending_job_fact_ids"]
    exclusions = [
        {"fact_id": f["fact_id"], "reason": "人工核对：示例排除原因，保留以供复核"}
        for f in packet["job_facts"]
        if f["fact_id"] != python["fact_id"]
    ]
    result = confirm_job(
        packet["review_id"], [python["fact_id"]], store, exclusions=exclusions
    )
    assert result["analysis"]["confirmed_job_profile"]["required_skills"] == ["Python"]
    assert not result["analysis"]["confirmed_job_profile"]["preferred_skills"]
    assert result["analysis"]["match_result"]["matched_required_skills"] == ["Python"]


def test_forged_job_confirmation_or_only_preferred_is_rejected(tmp_path):
    store = HistoryStore(tmp_path / "s.db")
    packet = create_review(request(), store)
    preferred = [
        f["fact_id"]
        for f in packet["job_facts"]
        if f["field"].startswith("preferred_skills.")
    ]
    partial = confirm_job(packet["review_id"], preferred, store)
    assert partial["analysis"] is None and not partial["job_review_complete"]
    packet = store.get(packet["review_id"])
    for ids in (["forged"], [packet["job_facts"][0]["fact_id"]] * 2):
        with pytest.raises(ValueError):
            confirm_job(packet["review_id"], ids, store)
        assert store.get(packet["review_id"]) == packet


def test_job_model_hallucinations_rejected_with_bounded_retry():
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"required_skills":["Kubernetes"]}'
                    )
                )
            ]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    with pytest.raises(ValueError, match="Ungrounded"):
        model_extract_job(
            [SourcePage(page_number=1, text="必须掌握Python和SQL")],
            client,
            SimpleNamespace(model="fake"),
        )
    assert len(calls) == 2


def test_changed_job_selection_blocks_stale_draft_and_reconfirmation_resets_it(
    tmp_path, monkeypatch
):
    from career_pilot import review_ui

    monkeypatch.setenv("CAREER_STATE_DB", str(tmp_path / "s.db"))
    packet = analyzed(request(), HistoryStore())
    fact_ids = [f["fact_id"] for f in packet["facts"]]
    with pytest.raises(Exception, match="岗位勾选已变更"):
        review_ui.confirm(packet["review_id"], fact_ids, [])
    confirm_review(packet["review_id"], fact_ids)
    assert review_ui.load(packet["review_id"])[5]
    again = confirm_job(packet["review_id"], packet["confirmed_job_fact_ids"])
    assert again["draft_markdown"] == "" and again["confirmed_fact_ids"] == []


def test_legacy_saved_draft_remains_readable(tmp_path, monkeypatch):
    from career_pilot import review_ui

    monkeypatch.setenv("CAREER_STATE_DB", str(tmp_path / "s.db"))
    packet = analyzed(request(), HistoryStore())
    packet = confirm_review(packet["review_id"], [packet["facts"][0]["fact_id"]])
    for field in ["request", "job_facts", "confirmed_job_fact_ids"]:
        del packet[field]
    HistoryStore().save(packet, packet["review_id"])
    assert review_ui.load(packet["review_id"])[5] == packet["draft_markdown"]


def test_unchecked_requirements_block_score_and_do_not_call_retrieval(
    tmp_path, monkeypatch
):
    def forbidden(_):
        raise AssertionError("No retrieval while requirements remain pending")

    store = HistoryStore(tmp_path / "s.db")
    packet = create_review(request(), store)
    monkeypatch.setattr(api, "get_career_retriever", forbidden)
    partial = confirm_job(
        packet["review_id"], [packet["job_facts"][0]["fact_id"]], store
    )
    assert partial["analysis"] is None and partial["status"] == "needs_job_confirmation"
    assert len(partial["pending_job_fact_ids"]) == len(packet["job_facts"]) - 1
    assert partial["job_scope"]["pending_count"] > 0
    assert HistoryStore(tmp_path / "s.db").get(packet["review_id"]) == partial
    with pytest.raises(ValueError, match="全部提取项"):
        confirm_review(packet["review_id"], [packet["facts"][0]["fact_id"]], store)


@pytest.mark.parametrize("kind", ["empty_reason", "overlap", "duplicate", "forged"])
def test_invalid_exclusions_do_not_change_record(tmp_path, kind):
    store = HistoryStore(tmp_path / "s.db")
    packet = create_review(request(), store)
    ids = [f["fact_id"] for f in packet["job_facts"]]
    confirmed = ids[:-1]
    exclusions = [{"fact_id": ids[-1], "reason": "该项为误提取"}]
    if kind == "empty_reason":
        exclusions[0]["reason"] = " "
    if kind == "overlap":
        confirmed = ids
    if kind == "duplicate":
        exclusions *= 2
    if kind == "forged":
        exclusions[0]["fact_id"] = "forged"
    with pytest.raises(ValueError):
        confirm_job(packet["review_id"], confirmed, store, exclusions=exclusions)
    assert store.get(packet["review_id"]) == packet


def test_exclusions_are_visible_in_report_api_and_restored_ui(tmp_path, monkeypatch):
    from career_pilot import review_ui

    monkeypatch.setenv("CAREER_STATE_DB", str(tmp_path / "api.db"))
    client = TestClient(api.app)
    packet = client.post("/api/career/reviews", json=request().model_dump()).json()
    ids = [f["fact_id"] for f in packet["job_facts"]]
    reason = "原文该项属于模板示例，人工核对排除<script>"
    response = client.post(
        f"/api/career/reviews/{packet['review_id']}/confirm-job",
        json={
            "fact_ids": ids[:-1],
            "exclusions": [{"fact_id": ids[-1], "reason": reason}],
        },
    )
    assert response.status_code == 200
    result = response.json()
    scope = result["analysis"]["job_scope"]
    assert scope["excluded_count"] == 1 and scope["pending_count"] == 0
    assert scope["entries"][-1]["reason"] == reason
    report = result["analysis"]["report_markdown"]
    assert report.startswith("# CareerPilot 求职分析报告\n")
    assert "排除误提取" in report and "排除原因" in report and "<script>" not in report
    assert "&lt;script&gt;" in report
    view = review_ui.load(result["review_id"])
    assert view[13].value == [ids[-1]] and view[14] == reason
    assert result["job_review_complete"]


def test_revisiting_job_review_clears_previous_score_and_draft(tmp_path):
    store = HistoryStore(tmp_path / "s.db")
    packet = analyzed(request(), store)
    packet = confirm_review(
        packet["review_id"], [f["fact_id"] for f in packet["facts"]], store
    )
    assert packet["draft_markdown"]
    pending = confirm_job(
        packet["review_id"], packet["confirmed_job_fact_ids"][:-1], store
    )
    assert (
        pending["analysis"] is None
        and not pending["draft_markdown"]
        and not pending["confirmed_fact_ids"]
    )


def test_all_required_excluded_is_not_a_complete_score(tmp_path):
    store = HistoryStore(tmp_path / "s.db")
    packet = create_review(request(), store)
    preferred = [
        f["fact_id"]
        for f in packet["job_facts"]
        if f["field"].startswith("preferred_skills.")
    ]
    exclusions = [
        {"fact_id": f["fact_id"], "reason": "人工核对为误提取"}
        for f in packet["job_facts"]
        if f["fact_id"] not in preferred
    ]
    with pytest.raises(ValueError, match="至少确认一项"):
        confirm_job(packet["review_id"], preferred, store, exclusions=exclusions)
    assert store.get(packet["review_id"]) == packet


def test_v2_records_require_reconfirmation_but_old_draft_is_readable(
    tmp_path, monkeypatch
):
    from career_pilot import review_ui

    monkeypatch.setenv("CAREER_STATE_DB", str(tmp_path / "s.db"))
    store = HistoryStore()
    packet = analyzed(request(), store)
    packet = confirm_review(packet["review_id"], [packet["facts"][0]["fact_id"]], store)
    packet["schema_version"] = 2
    for key in (
        "job_review_complete",
        "job_scope",
        "excluded_job_facts",
        "pending_job_fact_ids",
    ):
        packet.pop(key, None)
    store.save(packet, packet["review_id"])
    view = review_ui.load(packet["review_id"])
    assert view[5] == packet["draft_markdown"] and "旧版评分" in view[1]
    with pytest.raises(ValueError, match="旧版记录"):
        confirm_review(packet["review_id"], [packet["facts"][0]["fact_id"]], store)
    refreshed = confirm_job(
        packet["review_id"], packet["confirmed_job_fact_ids"], store
    )
    assert refreshed["schema_version"] == 3 and refreshed["job_review_complete"]
