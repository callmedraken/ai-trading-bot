"""Offline CLIs for the first capture-provider authority milestone.

The commands consume already-produced canonical artifacts.  They do not read
environment variables, retrieve credentials, create processes, or contact a
provider.
"""

from __future__ import annotations

import argparse
import json
import stat
from collections.abc import Callable, Sequence
from pathlib import Path
from uuid import UUID

from trading_bot.runtime.capture_attempt_authority import (
    CaptureAttemptAuthorityError,
    allocate_capture_attempt,
    apply_capture_attempt_recovery,
    initialize_capture_attempt_history,
    parse_capture_attempt_allocation,
    parse_manual_capture_attempt_recovery,
    select_capture_attempt_terminal,
    verify_capture_attempt_history,
)
from trading_bot.runtime.guarded_capture_readiness import (
    parse_scheduled_capture_readiness_decision,
)


def main_initialize_capture_attempt_history(argv: Sequence[str] | None = None) -> int:
    return _run(argv, _initialize)


def main_allocate_capture_attempt(argv: Sequence[str] | None = None) -> int:
    return _run(argv, _allocate)


def main_verify_capture_attempt_history(argv: Sequence[str] | None = None) -> int:
    return _run(argv, _verify)


def main_select_capture_attempt_terminal(argv: Sequence[str] | None = None) -> int:
    return _run(argv, _select)


def main_apply_capture_attempt_recovery(argv: Sequence[str] | None = None) -> int:
    return _run(argv, _recovery)


def _run(
    argv: Sequence[str] | None,
    operation: Callable[[dict[str, object]], dict[str, object]],
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    try:
        config = _load_config(parser.parse_args(argv).config)
        result = operation(config)
    except (OSError, ValueError, CaptureAttemptAuthorityError, json.JSONDecodeError):
        return 4
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _initialize(config: dict[str, object]) -> dict[str, object]:
    root = _path(config, "authority_root")
    session_id = _uuid(config, "scheduled_session_id")
    head = initialize_capture_attempt_history(
        root,
        session_id,
        _uuid(config, "authority_epoch_id"),
        _text(config, "policy_version"),
    )
    return {
        "status": "INITIALIZED",
        "scheduled_session_id": str(session_id),
        "history_head_record_id": str(head.history_head_record_id),
        "generation": head.generation,
    }


def _allocate(config: dict[str, object]) -> dict[str, object]:
    root = _path(config, "authority_root")
    allocation = parse_capture_attempt_allocation(_read_path(config, "allocation_path"))
    decision = parse_scheduled_capture_readiness_decision(
        _read_path(config, "readiness_decision_path")
    )
    head = allocate_capture_attempt(root, allocation, decision)
    return {
        "status": "ALLOCATED",
        "scheduled_session_id": str(allocation.scheduled_session_id),
        "attempt_id": str(allocation.attempt_id),
        "attempt_ordinal": allocation.attempt_ordinal,
        "history_head_record_id": str(head.history_head_record_id),
    }


def _verify(config: dict[str, object]) -> dict[str, object]:
    session_id = _uuid(config, "scheduled_session_id")
    result = verify_capture_attempt_history(_path(config, "authority_root"), session_id)
    output: dict[str, object] = {
        "status": result.classification.value,
        "scheduled_session_id": str(session_id),
        "diagnostics": list(result.diagnostics),
    }
    if result.head is not None:
        output["history_head_record_id"] = str(result.head.history_head_record_id)
        output["generation"] = result.head.generation
    return output


def _select(config: dict[str, object]) -> dict[str, object]:
    session_id = _uuid(config, "scheduled_session_id")
    selection = select_capture_attempt_terminal(
        _path(config, "authority_root"),
        session_id,
        _text(config, "selection_policy_version"),
    )
    return {
        "status": selection.result,
        "scheduled_session_id": str(session_id),
        "selection_record_id": str(selection.selection_record_id),
    }


def _recovery(config: dict[str, object]) -> dict[str, object]:
    session_id = _uuid(config, "scheduled_session_id")
    recovery = parse_manual_capture_attempt_recovery(
        _read_path(config, "recovery_path")
    )
    head = apply_capture_attempt_recovery(
        _path(config, "authority_root"), recovery, session_id
    )
    return {
        "status": "RECOVERY_APPLIED",
        "scheduled_session_id": str(session_id),
        "history_head_record_id": str(head.history_head_record_id),
        "state": head.state.value,
    }


def _load_config(path: Path) -> dict[str, object]:
    payload = _read_file(path)
    root = json.loads(payload.decode("utf-8"), parse_constant=_reject_constant)
    if type(root) is not dict or root.get("schema_version") != 1:
        raise ValueError("config schema_version must be 1")
    if any(type(key) is not str for key in root):
        raise ValueError("config keys must be strings")
    return root


def _read_path(config: dict[str, object], key: str) -> bytes:
    return _read_file(_path(config, key))


def _read_file(path: Path) -> bytes:
    if not path.is_absolute():
        raise ValueError("paths must be absolute")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    ):
        raise ValueError("path must be a safe regular file")
    payload = path.read_bytes()
    if len(payload) > 512 * 1024:
        raise ValueError("file is too large")
    return payload


def _path(config: dict[str, object], key: str) -> Path:
    value = config.get(key)
    if type(value) is not str or not value:
        raise ValueError(f"{key} is required")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{key} must be absolute")
    return path


def _uuid(config: dict[str, object], key: str) -> UUID:
    value = config.get(key)
    if type(value) is not str:
        raise ValueError(f"{key} is required")
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError(f"{key} must be canonical")
    return parsed


def _text(config: dict[str, object], key: str) -> str:
    value = config.get(key)
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError(f"{key} is invalid")
    return value


def _reject_constant(_: str) -> None:
    raise ValueError("JSON constants are not permitted")
