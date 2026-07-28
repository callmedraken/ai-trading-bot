"""Focused strict paper-operation configuration loading coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_bot.cli.paper_operation_config import (
    MAX_PAPER_OPERATION_CONFIG_BYTES,
    PaperOperationConfigReadError,
    PaperOperationConfigSyntaxError,
    PaperOperationConfigValidationError,
    parse_paper_operation_config,
)


def _reference(name: str) -> dict[str, object]:
    return {
        "artifact_id": "00000000-0000-0000-0000-000000000001",
        "path": name,
        "sha256": "a" * 64,
        "byte_length": 1,
    }


def _tree() -> dict[str, object]:
    return {
        "schema_version": 1,
        "caller_idempotency_key": "00000000-0000-0000-0000-000000000002",
        "prior_lineage_manifest": _reference("lineage.json"),
        "terminal_checkpoint": _reference("checkpoint.json"),
        "completed_snapshot": _reference("snapshot.json"),
        "cycle_configuration": _reference("cycle.json"),
    }


def _payload(tree: object) -> bytes:
    return json.dumps(tree, separators=(",", ":")).encode()


def test_strict_configuration_accepts_exact_schema_and_resolves_paths(
    tmp_path: Path,
) -> None:
    config = parse_paper_operation_config(_payload(_tree()), base_directory=tmp_path)

    assert config.schema_version == 1
    assert config.prior_lineage_manifest.path == tmp_path / "lineage.json"
    assert config.terminal_checkpoint.path == tmp_path / "checkpoint.json"
    assert config.completed_snapshot.path == tmp_path / "snapshot.json"
    assert config.cycle_configuration.path == tmp_path / "cycle.json"


@pytest.mark.parametrize(
    "change",
    (
        lambda tree: tree.update(extra=True),
        lambda tree: tree.pop("completed_snapshot"),
        lambda tree: tree.update(schema_version=2),
        lambda tree: tree.update(caller_idempotency_key="NOT-A-UUID"),
        lambda tree: tree["completed_snapshot"].update(sha256="A" * 64),
        lambda tree: tree["completed_snapshot"].update(byte_length=0),
        lambda tree: tree["completed_snapshot"].update(path=" snapshot.json"),
        lambda tree: tree["completed_snapshot"].update(path="bad\x00path"),
        lambda tree: tree["completed_snapshot"].update(path="x" * 4097),
    ),
)
def test_configuration_rejects_unknown_missing_and_noncanonical_values(
    tmp_path: Path,
    change,
) -> None:
    tree = _tree()
    change(tree)

    with pytest.raises(PaperOperationConfigValidationError):
        parse_paper_operation_config(_payload(tree), base_directory=tmp_path)


@pytest.mark.parametrize(
    "payload",
    (
        b"\xef\xbb\xbf{}",
        b'{"schema_version":1,"schema_version":1}',
        b'{"schema_version":NaN}',
        b'{"schema_version":1.0}',
        b"\xff",
    ),
)
def test_configuration_rejects_non_strict_json(
    tmp_path: Path,
    payload: bytes,
) -> None:
    with pytest.raises(PaperOperationConfigSyntaxError):
        parse_paper_operation_config(payload, base_directory=tmp_path)


def test_configuration_byte_bound_is_enforced(tmp_path: Path) -> None:
    with pytest.raises(PaperOperationConfigReadError):
        parse_paper_operation_config(
            b"x" * (MAX_PAPER_OPERATION_CONFIG_BYTES + 1),
            base_directory=tmp_path,
        )
