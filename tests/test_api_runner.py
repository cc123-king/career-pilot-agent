import runpy
from pathlib import Path

import pytest
import uvicorn

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_api.py"


def test_api_runner_binds_only_to_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--port", "8001"])
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append(kwargs))

    runpy.run_path(str(SCRIPT), run_name="__main__")

    assert calls == [{"host": "127.0.0.1", "port": 8001, "log_level": "info"}]


@pytest.mark.parametrize("port", ["0", "65536"])
def test_api_runner_rejects_invalid_ports(
    port: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--port", port])

    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(SCRIPT), run_name="__main__")

    assert error.value.code == 2
