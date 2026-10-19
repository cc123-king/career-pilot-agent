import json
import runpy
from pathlib import Path

import pytest

from career_pilot import report, workflow

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_acceptance_demo.py"


def run_demo(output: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--output-dir", str(output)])
    runpy.run_path(str(SCRIPT), run_name="__main__")


def test_demo_runs_three_real_offline_scenarios_from_any_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def forbid_network(*args, **kwargs):
        raise AssertionError("The acceptance demo must not use the network")

    monkeypatch.setattr("socket.socket.connect", forbid_network)
    run_demo(tmp_path, monkeypatch)
    directory = next(tmp_path.glob("demo-*"))
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    assert summary["scenario_count"] == summary["passed_count"] == 3
    assert summary["generation_mode"] == "rules"
    assert summary["synthetic_inputs_only"] is True
    assert [item["score"] for item in summary["results"]] == [85, 61.67, 85]
    assert all(item["node_count"] == 7 for item in summary["results"])
    assert all(all(item["checks"].values()) for item in summary["results"])
    for item in summary["results"]:
        scenario_dir = directory / item["scenario"]
        assert (scenario_dir / "input.json").is_file()
        assert (scenario_dir / "result.json").is_file()
        assert (
            Path(item["report_file"])
            .read_text(encoding="utf-8")
            .startswith("# CareerPilot")
        )
    missing = json.loads(
        (directory / "missing-fastapi" / "result.json").read_text(encoding="utf-8")
    )
    assert missing["match_result"]["missing_required_skills"] == ["FastAPI"]
    insufficient = json.loads(
        (directory / "no-knowledge" / "result.json").read_text(encoding="utf-8")
    )
    assert insufficient["knowledge_sources"] == []
    assert insufficient["warnings"]
    assert all(item["citation_id"] is None for item in insufficient["advice"])


def test_repeat_demo_preserves_previous_reports_and_reproduces_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_demo(tmp_path, monkeypatch)
    first = next(tmp_path.glob("demo-*"))
    first_report = next((first / "baseline").glob("*.md"))
    before = first_report.read_bytes()
    run_demo(tmp_path, monkeypatch)
    directories = list(tmp_path.glob("demo-*"))
    assert len(directories) == 2
    second = next(item for item in directories if item != first)
    assert first_report.read_bytes() == before
    assert next((second / "baseline").glob("*.md")).read_bytes() == before
    for name in ("baseline", "missing-fastapi", "no-knowledge"):
        assert (first / name / "input.json").read_bytes() == (
            second / name / "input.json"
        ).read_bytes()
        assert (first / name / "result.json").read_bytes() == (
            second / name / "result.json"
        ).read_bytes()


def test_demo_returns_failure_when_a_business_expectation_breaks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = workflow.run_career_analysis

    def wrong_score(*args, **kwargs):
        result = original(*args, **kwargs)
        result["match_result"] = result["match_result"].model_copy(update={"score": 0})
        return result

    monkeypatch.setattr(workflow, "run_career_analysis", wrong_score)
    with pytest.raises(SystemExit) as error:
        run_demo(tmp_path, monkeypatch)
    assert error.value.code == 1
    summary_path = next(tmp_path.glob("demo-*/summary.json"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["passed_count"] == 0
    assert all(not item["checks"]["expected_score"] for item in summary["results"])
    assert all(
        not item["checks"]["report_score_consistent"] for item in summary["results"]
    )


def test_demo_reports_export_failure_without_claiming_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_export(*args, **kwargs):
        raise PermissionError("Report directory is not writable")

    monkeypatch.setattr(report, "save_markdown_report", unavailable_export)
    with pytest.raises(SystemExit) as error:
        run_demo(tmp_path, monkeypatch)
    assert error.value.code == 1
    assert not list(tmp_path.glob("demo-*/summary.json"))
