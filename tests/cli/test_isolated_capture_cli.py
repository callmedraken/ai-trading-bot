from __future__ import annotations

import json

import pytest
from tests.runtime.test_isolated_capture_process_and_launcher import _launcher_case

from trading_bot.cli.isolated_capture_child import main as child_main
from trading_bot.runtime.windows_isolated_capture_launcher import (
    IsolatedCaptureLauncherConfigError,
    load_isolated_capture_launcher_config,
)


def _artifact_tree(value) -> dict[str, object]:
    return {
        "artifact_id": str(value.artifact_id),
        "sha256": value.sha256,
        "byte_length": value.byte_length,
    }


def _config_tree(config) -> dict[str, object]:
    return {
        "schema_version": config.schema_version,
        "child_request": _artifact_tree(config.child_request),
        "child_request_path": str(config.child_request_path),
        "approved_python_executable": str(config.approved_python_executable),
        "approved_python_executable_evidence": _artifact_tree(
            config.approved_python_executable_evidence
        ),
        "approved_child_script": str(config.approved_child_script),
        "approved_child_script_evidence": _artifact_tree(
            config.approved_child_script_evidence
        ),
        "process_evidence_directory": str(config.process_evidence_directory),
        "controlled_temp_directory": str(config.controlled_temp_directory),
        "environment_policy_version": config.environment_policy_version,
        "termination_grace_seconds": config.termination_grace_seconds,
    }


def test_launcher_config_is_strict_and_nonsecret(tmp_path) -> None:
    _, config = _launcher_case(tmp_path)
    path = tmp_path / "launcher-config.json"
    tree = _config_tree(config)
    payload = json.dumps(tree, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(payload)

    assert load_isolated_capture_launcher_config(path) == config
    assert b"APCA_API_KEY_ID" not in payload
    assert b"APCA_API_SECRET_KEY" not in payload


@pytest.mark.parametrize(
    "change",
    [
        lambda payload: b"\xef\xbb\xbf" + payload,
        lambda payload: payload.replace(b'"schema_version":1', b'"schema_version":1.0'),
        lambda payload: payload.replace(
            b'"schema_version":1',
            b'"schema_version":1,"schema_version":1',
        ),
        lambda payload: payload.replace(
            b'"schema_version":1', b'"unknown":1,"schema_version":1'
        ),
    ],
)
def test_launcher_config_rejects_hostile_json(tmp_path, change) -> None:
    _, config = _launcher_case(tmp_path)
    path = tmp_path / "launcher-config.json"
    payload = json.dumps(
        _config_tree(config), sort_keys=True, separators=(",", ":")
    ).encode()
    path.write_bytes(change(payload))

    with pytest.raises(IsolatedCaptureLauncherConfigError):
        load_isolated_capture_launcher_config(path)


def test_child_cli_invalid_request_has_stable_sanitized_failure(
    tmp_path, capsys
) -> None:
    secret = "CLI-SECRET-SENTINEL"
    path = tmp_path / secret

    assert child_main(["--request", str(path)]) == 8
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert captured.err == "error: isolated capture child failed safely\n"
