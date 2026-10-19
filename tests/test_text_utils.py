from career_pilot.text_utils import normalize_text


def test_normalize_text_removes_extra_whitespace() -> None:
    result = normalize_text("  Python   Agent\n开发  ")

    assert result == "Python Agent 开发"


def test_normalize_text_returns_empty_string() -> None:
    result = normalize_text("   \n\t  ")

    assert result == ""
