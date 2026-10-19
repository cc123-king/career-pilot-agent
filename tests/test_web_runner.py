import runpy
from pathlib import Path

import pytest
import uvicorn

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_web.py"


def test_web_runner_starts_the_shared_app_factory_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr("sys.argv", [str(SCRIPT)])
    monkeypatch.setattr(
        uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs))
    )

    runpy.run_path(str(SCRIPT), run_name="__main__")

    assert calls == [
        (
            "career_pilot.web:create_web_app",
            {"factory": True, "host": "127.0.0.1", "port": 8001, "log_level": "info"},
        )
    ]


@pytest.mark.parametrize("port", ["0", "65536"])
def test_web_runner_rejects_invalid_ports(
    port: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--port", port])

    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(SCRIPT), run_name="__main__")

    assert error.value.code == 2
