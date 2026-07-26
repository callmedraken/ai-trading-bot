import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("script_name", "module_name"),
    [
        (
            "create_walk_forward_research_bundle_archive.py",
            "create_research_session_archive",
        ),
        (
            "verify_walk_forward_research_bundle_archive.py",
            "verify_research_session_archive",
        ),
        (
            "restore_walk_forward_research_bundle_archive.py",
            "restore_research_session_archive",
        ),
    ],
)
def test_archive_script_delegates(
    monkeypatch: pytest.MonkeyPatch,
    script_name: str,
    module_name: str,
) -> None:
    module = __import__(f"trading_bot.cli.{module_name}", fromlist=["main"])
    calls = []

    def fake_main():  # type: ignore[no-untyped-def]
        calls.append(True)
        return 0

    monkeypatch.setattr(module, "main", fake_main)
    script = ROOT / "scripts" / script_name
    monkeypatch.setattr(sys, "argv", [str(script)])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(script), run_name="__main__")
    assert caught.value.code == 0
    assert calls == [True]
