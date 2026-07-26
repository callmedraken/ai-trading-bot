import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "create_walk_forward_research_bundle.py"


def test_script_delegates_to_cli_main(monkeypatch: pytest.MonkeyPatch) -> None:
    from trading_bot.cli import create_research_session_bundle

    calls = []

    def fake_main():  # type: ignore[no-untyped-def]
        calls.append(True)
        return 0

    monkeypatch.setattr(create_research_session_bundle, "main", fake_main)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert caught.value.code == 0
    assert calls == [True]
