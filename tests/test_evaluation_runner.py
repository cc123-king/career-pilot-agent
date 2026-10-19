import json
import runpy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_retrieval.py"


def test_runner_writes_an_offline_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "evaluation.json"
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--output", str(output)])

    def forbid_network(*args, **kwargs):
        raise AssertionError("The baseline must not make network calls")

    monkeypatch.setattr("socket.socket.connect", forbid_network)
    runpy.run_path(str(SCRIPT), run_name="__main__")

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["evaluation_scope"] == "retrieval_only"
    assert report["retriever"] == "keyword"
    assert report["case_count"] == 10
    assert len(report["results"]) == 10
    assert len(report["dataset_sha256"]) == 64
    assert {"interview_guidance.md", "resume_guidance.md"} <= set(
        report["knowledge_sha256"]
    )
    assert len(report["knowledge_sha256"]) == 12
    assert all(len(value) == 64 for value in report["knowledge_sha256"].values())


@pytest.mark.parametrize("option,value", [("--top-k", "0"), ("--min-score", "1.1")])
def test_runner_rejects_invalid_options(
    option: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", [str(SCRIPT), option, value])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert error.value.code == 2


def test_runner_rejects_nonexistent_standard_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "cases.json"
    output = tmp_path / "must-not-exist.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "case_id": "missing",
                    "question": "Question",
                    "expected_sources": ["typo.md"],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv", [str(SCRIPT), "--dataset", str(dataset), "--output", str(output)]
    )
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert error.value.code == 2
    assert not output.exists()
