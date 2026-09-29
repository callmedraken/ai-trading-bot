from __future__ import annotations

import ast
import json
from pathlib import Path

from scripts import d10_durable_wake_evidence_observe as observer


def test_observer_delegates_only_to_public_guard_boundary(monkeypatch) -> None:
    expected = {
        "schema": "personal-desktop-d10-evidence-observation/v1",
        "status": "OBSERVED",
        "terminal": False,
    }
    monkeypatch.setattr(
        observer.guard,
        "observe_fixed_d10_durable_wake_evidence",
        lambda: expected,
    )
    assert observer.observe() == expected


def test_observer_source_uses_no_private_guard_dependency() -> None:
    source = Path(observer.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "guard._" not in source
    assert "open_evidence_file" not in source
    assert "append_exact" not in source
    assert "WriteFile" not in source
    assert "FlushFileBuffers" not in source
    assert "subprocess" not in source
    calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert "guard.observe_fixed_d10_durable_wake_evidence" in calls


def test_main_emits_compact_sanitized_json(monkeypatch, capsys) -> None:
    expected = {
        "schema": "personal-desktop-d10-evidence-observation/v1",
        "status": "OBSERVED",
        "record_count": 2,
        "terminal": False,
    }
    monkeypatch.setattr(observer, "observe", lambda: expected)
    monkeypatch.setattr(observer.sys, "argv", ["observer"])
    assert observer.main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == expected
    assert captured.err == ""


def test_main_fails_closed_without_exception_details(monkeypatch, capsys) -> None:
    def blocked():
        raise RuntimeError("sensitive internal detail")

    monkeypatch.setattr(observer, "observe", blocked)
    monkeypatch.setattr(observer.sys, "argv", ["observer"])
    assert observer.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "d10_evidence_observation_blocked"
    assert "sensitive internal detail" not in captured.err
