from pathlib import Path

import gradio as gr
import pytest
from fastapi import HTTPException

from career_pilot import api, ui
from career_pilot.models import AnalysisRequest
from career_pilot.report import save_markdown_report


def test_analysis_ui_uses_the_shared_api_entry_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_request = AnalysisRequest(**api.ANALYSIS_EXAMPLE)
    response = api.analyze_career(expected_request)
    calls: list[tuple[AnalysisRequest, str]] = []

    def analyze(request: AnalysisRequest, *, retrieval_mode: str):
        calls.append((request, retrieval_mode))
        return response

    monkeypatch.setattr(ui, "analyze_career", analyze)
    outputs = ui.analyze_resume(*ui.load_analysis_example())

    assert calls == [(expected_request, "keyword")]
    score, required, preferred, report, status, session_report, export_button = outputs
    assert score == 85
    assert required == "未发现缺失"
    assert preferred == "MCP"
    assert report == response.report_markdown == session_report
    assert response.request_id in status
    assert "节点：7" in status
    assert export_button.interactive is True


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("resume_text", " ", "简历正文至少需要 20 个字符。"),
        ("job_description", "短", "岗位要求至少需要 20 个字符。"),
        ("company", " ", "公司至少需要 1 个字符。"),
        ("role", " ", "岗位至少需要 1 个字符。"),
        ("resume_text", "简" * 50_001, "简历正文不能超过 50000 个字符。"),
    ],
    ids=["blank-resume", "short-job", "blank-company", "blank-role", "long-resume"],
)
def test_analysis_ui_rejects_invalid_input_before_running_the_workflow(
    field: str, value: str, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbid_analysis(*args, **kwargs):
        raise AssertionError("Invalid input must not start analysis")

    monkeypatch.setattr(ui, "analyze_career", forbid_analysis)
    values = {**api.ANALYSIS_EXAMPLE, field: value, "retrieval_mode": "keyword"}

    with pytest.raises(gr.Error) as error:
        ui.analyze_resume(**values)

    assert error.value.message == message


def test_analysis_ui_rejects_unknown_retrieval_modes() -> None:
    with pytest.raises(gr.Error) as error:
        ui.analyze_resume(**api.ANALYSIS_EXAMPLE, retrieval_mode="unknown")

    assert error.value.message == "请选择有效的检索方式。"


def test_analysis_ui_displays_the_api_error_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*args, **kwargs):
        raise HTTPException(status_code=503, detail="混合检索配置无效。")

    monkeypatch.setattr(ui, "analyze_career", unavailable)

    with pytest.raises(gr.Error) as error:
        ui.analyze_resume(*ui.load_analysis_example())

    assert error.value.message == "混合检索配置无效。"


def test_example_and_clear_restore_a_valid_default_retrieval_mode() -> None:
    assert ui.load_analysis_example() == (
        api.ANALYSIS_EXAMPLE["resume_text"],
        api.ANALYSIS_EXAMPLE["job_description"],
        api.ANALYSIS_EXAMPLE["company"],
        api.ANALYSIS_EXAMPLE["role"],
        "keyword",
    )
    assert ui.clear_analysis_inputs() == ("", "", "", "", "keyword")
    cleared = ui.clear_analysis_results()
    assert cleared[:7] == (None, "", "", "", "", "", None)
    assert cleared[7].interactive is False


def test_report_export_preserves_independent_session_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ui,
        "save_markdown_report",
        lambda content: save_markdown_report(content, directory=tmp_path),
    )

    first = Path(ui.export_analysis_report("# 第一份报告\n中文内容。"))
    second = Path(ui.export_analysis_report("# 第二份报告\n不同的内容。"))

    assert first != second
    assert first.read_text(encoding="utf-8") == "# 第一份报告\n中文内容。"
    assert second.read_text(encoding="utf-8") == "# 第二份报告\n不同的内容。"


@pytest.mark.parametrize("report", [None, "", " \n "])
def test_report_export_requires_a_completed_analysis(report) -> None:
    with pytest.raises(gr.Error) as error:
        ui.export_analysis_report(report)

    assert error.value.message == "请先完成简历分析，再导出报告。"


def test_report_export_handles_filesystem_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_directory(_content):
        raise PermissionError("private local path")

    monkeypatch.setattr(ui, "save_markdown_report", unavailable_directory)

    with pytest.raises(gr.Error) as error:
        ui.export_analysis_report("# 测试报告")

    assert error.value.message == "报告保存失败，请检查目录权限后重试。"
