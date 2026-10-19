"""Validate the paid runner's boundaries using a fully local fake API."""

import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/evaluate_answer_pipeline.py"


def test_runner_requires_explicit_permission_before_loading_credentials(monkeypatch):
    monkeypatch.setattr("sys.argv", [str(SCRIPT)])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert error.value.code == 2


def test_dataset_and_anchors_validate_without_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("No network")

    monkeypatch.setattr("socket.socket.connect", deny)
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--validate-only"])
    runpy.run_path(str(SCRIPT), run_name="__main__")


def test_request_budget_survives_restart_and_counts_before_transmission(tmp_path):
    budget_cls = runpy.run_path(str(SCRIPT))["RequestBudget"]
    path = tmp_path / "ledger.json"
    budget_cls(path, 1, 1).consume("chat")
    resumed = budget_cls(path, 1, 1)
    with pytest.raises(RuntimeError, match="budget exhausted"):
        resumed.consume("chat")
    assert json.loads(path.read_text("utf-8"))["counts"]["chat"] == 1


@pytest.fixture
def local_runner(tmp_path, monkeypatch):
    from career_pilot.llm import LLMSettings
    from career_pilot.rag.embeddings import EmbeddingSettings

    namespace = runpy.run_path(str(SCRIPT))
    main = namespace["main"]
    globals_ = main.__globals__
    quote = "Atlas 只读状态查询最多重试 2 次，不代表其他服务的配置。"
    directory = tmp_path / "knowledge"
    directory.mkdir()
    (directory / "policy.md").write_text("# 演示契约\n\n" + quote, encoding="utf-8")
    dataset = tmp_path / "cases.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "case_id": "fixture-1",
                    "group": "known_regression",
                    "answerable": True,
                    "question": "Atlas 最多重试几次？",
                    "evidence": [{"source": "policy.md", "anchor": "最多重试 2 次"}],
                    "answer_checks": [["DO_NOT_SEND_LABEL_MARKER"]],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "result"
    scope = tmp_path / "scope.json"
    supported = {
        "answerable": True,
        "requirements": [
            {
                "question_part": "Atlas 最多重试几次？",
                "supported": True,
                "evidence": [{"citation_id": 1, "quote": quote}],
            }
        ],
        "missing_information": [],
    }
    responses = {
        globals_["PROMPTS"]["evidence"]: {
            "answerable": False,
            "requirements": [
                {
                    "question_part": "Atlas 最多重试几次？",
                    "supported": False,
                    "evidence": [],
                }
            ],
            "missing_information": ["首次受控误拒"],
        },
        globals_["PROMPTS"]["review"]: supported,
        globals_["PROMPTS"]["draft"]: {
            "claims": [
                {
                    "claim_id": 1,
                    "text": "Atlas 只读状态查询最多重试 2 次。",
                    "requirement_ids": [1],
                    "evidence": [{"citation_id": 1, "quote": quote}],
                }
            ]
        },
        globals_["PROMPTS"]["audit"]: {
            "fully_supported": True,
            "requirements_complete": True,
            "question_fully_answered": True,
            "requirement_checks": [
                {"requirement_id": 1, "answered": True, "reason": "已回答原问题"}
            ],
            "checks": [
                {
                    "claim_id": 1,
                    "supported": True,
                    "reason": "受控原文支持",
                }
            ],
        },
    }
    responses[globals_["PROMPTS"]["proposal"]] = {
        "answerable": True,
        "claims": responses[globals_["PROMPTS"]["draft"]]["claims"],
        "missing_information": [],
    }
    real_calls = []
    state = SimpleNamespace(fail_stage=None, failures_remaining=0)

    class FakeAPI:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self.chat_create)
            )
            self.embeddings = SimpleNamespace(create=self.embed_create)

        def embed_create(self, **request):
            real_calls.append(("embedding", request))
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=i, embedding=[1.0, 1.0])
                    for i, _ in enumerate(request["input"])
                ]
            )

        def chat_create(self, **request):
            real_calls.append(("chat", request))
            if (
                state.fail_stage is not None
                and request["messages"][0]["content"]
                == globals_["PROMPTS"][state.fail_stage]
                and state.failures_remaining > 0
            ):
                state.failures_remaining -= 1
                raise TimeoutError("temporary fixture outage")
            content = json.dumps(
                responses[request["messages"][0]["content"]], ensure_ascii=False
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=None,
            )

    monkeypatch.setitem(globals_, "OpenAI", FakeAPI)
    monkeypatch.setitem(
        globals_,
        "load_llm_settings",
        lambda *args: LLMSettings(
            provider="fixture",
            api_key="fake-test-key",
            base_url="https://example.invalid",
            model="test-model",
        ),
    )
    monkeypatch.setitem(
        globals_,
        "load_embedding_settings",
        lambda *args: EmbeddingSettings(
            api_key="fake-test-key",
            base_url="https://example.invalid",
            model="test-embedding",
        ),
    )

    def deny(*args, **kwargs):
        raise AssertionError("The fake runner cannot use the network")

    monkeypatch.setattr("socket.socket.connect", deny)
    common = [str(SCRIPT), "--dataset", str(dataset), "--knowledge-dir", str(directory)]
    monkeypatch.setattr("sys.argv", [*common, "--prepare-scope", str(scope)])
    main()
    assert real_calls == []
    execute = [
        *common,
        "--scope-manifest",
        str(scope),
        "--output-dir",
        str(output),
        "--allow-live-calls",
    ]
    monkeypatch.setattr("sys.argv", execute)
    return SimpleNamespace(
        main=main,
        output=output,
        calls=real_calls,
        prompts=globals_["PROMPTS"],
        responses=responses,
        supported=supported,
        state=state,
    )


def test_complete_runner_uses_shared_pipeline_has_no_label_leak_and_resumes_free(
    local_runner,
):
    main = local_runner.main
    output = local_runner.output
    real_calls = local_runner.calls
    main()
    report = json.loads((output / "report.json").read_text("utf-8"))
    assert report["request_counts"] == {"embedding": 1, "chat": 3}
    assert report["results"][0]["result"]["answer_status"] == "supported"
    assert report["results"][0]["result"]["evidence_recovery_used"] is True
    assert report["human_semantic_review_completed"] is False
    assert len(real_calls) == 4
    for kind, request in real_calls:
        if kind == "chat":
            sent = request["messages"][1]["content"]
            assert "DO_NOT_SEND_LABEL_MARKER" not in sent
            assert "fixture-1" not in sent
    main()
    assert len(real_calls) == 4


@pytest.mark.parametrize("failed_stage", ["evidence", "draft", "audit"])
def test_runner_resumes_unavailable_case_and_reuses_successful_stages(
    local_runner, failed_stage
):
    runner = local_runner
    runner.responses[runner.prompts["evidence"]] = runner.supported
    runner.state.fail_stage = failed_stage
    runner.state.failures_remaining = 1
    with pytest.raises(RuntimeError, match="Provider stage unavailable"):
        runner.main()
    saved = json.loads((runner.output / "case-results.json").read_text("utf-8"))
    unfinished = saved["fixture-1"]["result"]
    assert "unavailable" in (unfinished["evidence_status"], unfinished["answer_status"])
    assert not (runner.output / "report.json").exists()

    runner.main()
    report = json.loads((runner.output / "report.json").read_text("utf-8"))
    assert report["request_counts"] == {"embedding": 1, "chat": 4}
    assert report["results"][0]["result"]["answer_status"] == "supported"
    chat_requests = [r for kind, r in runner.calls if kind == "chat"]
    for stage in ("evidence", "draft", "audit"):
        assert sum(
            r["messages"][0]["content"] == runner.prompts[stage] for r in chat_requests
        ) == (2 if stage == failed_stage else 1)
    calls_after_completion = len(runner.calls)
    runner.main()
    assert len(runner.calls) == calls_after_completion


def test_resuming_provider_outages_does_not_reset_or_exceed_paid_budget(local_runner):
    runner = local_runner
    runner.state.fail_stage = "evidence"
    runner.state.failures_remaining = 10
    for _ in range(5):
        with pytest.raises(RuntimeError, match="Provider stage unavailable"):
            runner.main()
    ledger = json.loads((runner.output / "request-ledger.json").read_text("utf-8"))
    assert ledger["counts"] == {"embedding": 1, "chat": 4}
    assert ledger["limits"] == {"embedding": 1, "chat": 4}
    assert len([r for kind, r in runner.calls if kind == "chat"]) == 4
    assert not (runner.output / "report.json").exists()


def test_zero_embedding_budget_reuses_vectors_and_cannot_send_new_request(
    local_runner, monkeypatch
):
    runner = local_runner
    runner.main()
    before = len(runner.calls)
    args = list(__import__("sys").argv)
    scope_path = Path(args[args.index("--scope-manifest") + 1])
    scope = json.loads(scope_path.read_text("utf-8"))
    scope["maximum_embedding_requests"] = 0
    scope_path.write_text(json.dumps(scope, ensure_ascii=False), encoding="utf-8")
    (runner.output / "scope.json").write_text(
        json.dumps(scope, ensure_ascii=False), encoding="utf-8"
    )
    ledger_path = runner.output / "request-ledger.json"
    ledger = json.loads(ledger_path.read_text("utf-8"))
    ledger["counts"]["embedding"] = 0
    ledger["limits"]["embedding"] = 0
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [*args, "--embedding-request-limit", "0"])
    runner.main()
    assert len(runner.calls) == before
    (runner.output / "vectors.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="budget exhausted"):
        runner.main()
    assert len(runner.calls) == before


def test_expanded_official_document_dataset_is_valid_without_network(monkeypatch):
    from career_pilot.rag.documents import chunk_document, load_knowledge_documents

    namespace = runpy.run_path(str(SCRIPT))
    documents = load_knowledge_documents(ROOT / "evaluation/technical_corpus")
    cases = namespace["load_cases"](
        ROOT / "evaluation/technical_qa_v6_cases.json", documents
    )
    from types import SimpleNamespace

    from career_pilot import api

    monkeypatch.setattr(
        api, "KNOWLEDGE_DIRECTORY", ROOT / "evaluation/technical_corpus"
    )
    monkeypatch.setattr(
        api, "UPLOADED_KNOWLEDGE_STORE", SimpleNamespace(list_chunks=list)
    )
    assert len(api._load_current_knowledge_chunks()) == sum(
        len(chunk_document(d, max_characters=300)) for d in documents
    )
    assert len(documents) >= 30
    assert sum(len(chunk_document(d, max_characters=300)) for d in documents) >= 1000
    assert len(cases) == 36
    assert sum(c.group == "development" for c in cases) == 18
    assert sum(c.group == "heldout_author_labeled" for c in cases) == 18
    assert (ROOT / "evaluation/technical_corpus/LICENSE.txt").is_file()
