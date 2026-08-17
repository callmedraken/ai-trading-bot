from __future__ import annotations

# ruff: noqa: I001

import json
from pathlib import Path
from uuid import UUID

from trading_bot.cli.capture_attempt_authority import (
    main_allocate_capture_attempt,
    main_apply_capture_attempt_recovery,
    main_initialize_capture_attempt_history,
    main_select_capture_attempt_terminal,
    main_verify_capture_attempt_history,
)


def _write_config(path: Path, values: dict[str, object]) -> None:
    path.write_text(
        json.dumps({"schema_version": 1, **values}),
        encoding="utf-8",
    )


def test_initialize_and_verify_cli_are_offline(tmp_path: Path, capsys) -> None:
    root = tmp_path / "authority"
    root.mkdir()
    session_id = UUID("11111111-1111-5111-8111-111111111111")
    config = tmp_path / "initialize.json"
    _write_config(
        config,
        {
            "authority_root": str(root),
            "scheduled_session_id": str(session_id),
            "authority_epoch_id": "33333333-3333-5333-8333-333333333333",
            "policy_version": "history-v1",
        },
    )
    assert main_initialize_capture_attempt_history(["--config", str(config)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "INITIALIZED"

    verify_config = tmp_path / "verify.json"
    _write_config(
        verify_config,
        {
            "authority_root": str(root),
            "scheduled_session_id": str(session_id),
        },
    )
    assert main_verify_capture_attempt_history(["--config", str(verify_config)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"


def test_cli_rejects_relative_config_path(tmp_path: Path) -> None:
    config = tmp_path / "bad.json"
    _write_config(
        config,
        {
            "authority_root": "relative",
            "scheduled_session_id": "11111111-1111-5111-8111-111111111111",
            "authority_epoch_id": "33333333-3333-5333-8333-333333333333",
            "policy_version": "history-v1",
        },
    )
    assert main_initialize_capture_attempt_history(["--config", str(config)]) == 4


def test_cli_authority_commands_fail_closed_without_required_artifacts(
    tmp_path: Path, capsys
) -> None:
    root = tmp_path / "authority"
    root.mkdir()
    session_id = "11111111-1111-5111-8111-111111111111"
    allocation = tmp_path / "allocate.json"
    _write_config(
        allocation,
        {
            "authority_root": str(root),
            "allocation_path": str(tmp_path / "missing-allocation.json"),
            "readiness_decision_path": str(tmp_path / "missing-decision.json"),
        },
    )
    assert main_allocate_capture_attempt(["--config", str(allocation)]) == 4
    assert capsys.readouterr().out == ""

    selection = tmp_path / "select.json"
    _write_config(
        selection,
        {
            "authority_root": str(root),
            "scheduled_session_id": session_id,
            "selection_policy_version": "selection-v1",
        },
    )
    assert main_select_capture_attempt_terminal(["--config", str(selection)]) == 4

    recovery = tmp_path / "recovery.json"
    _write_config(
        recovery,
        {
            "authority_root": str(root),
            "scheduled_session_id": session_id,
            "recovery_path": str(tmp_path / "missing-recovery.json"),
        },
    )
    assert main_apply_capture_attempt_recovery(["--config", str(recovery)]) == 4


def test_cli_verify_reports_missing_history_without_discovery(
    tmp_path: Path, capsys
) -> None:
    root = tmp_path / "authority"
    root.mkdir()
    config = tmp_path / "verify.json"
    _write_config(
        config,
        {
            "authority_root": str(root),
            "scheduled_session_id": "11111111-1111-5111-8111-111111111111",
        },
    )
    assert main_verify_capture_attempt_history(["--config", str(config)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED"
    assert result["diagnostics"] == ["HISTORY_POINTER_MISSING"]


def test_cli_rejects_bom_constants_and_noncanonical_config(tmp_path: Path) -> None:
    config = tmp_path / "invalid.json"
    config.write_bytes(b"\xef\xbb\xbf{}")
    assert main_verify_capture_attempt_history(["--config", str(config)]) == 4
    config.write_text('{"schema_version":1,"x":NaN}', encoding="utf-8")
    assert main_verify_capture_attempt_history(["--config", str(config)]) == 4
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "authority_root": str(tmp_path),
                "scheduled_session_id": "11111111-1111-5111-8111-111111111111",
            }
        ),
        encoding="utf-8",
    )
    assert main_verify_capture_attempt_history(["--config", str(config)]) == 0
