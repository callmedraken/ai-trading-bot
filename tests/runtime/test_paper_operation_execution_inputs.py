"""PD2B2 path-independent Architecture-67 execution-input coverage."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from uuid import UUID

import pytest
from tests.cli.test_paper_operation_inspection import _setup

from trading_bot.cli.paper_operation_config import (
    PaperOperationArtifactReference,
    adapt_verified_paper_operation_execution_inputs,
)
from trading_bot.cli.paper_operation_execution import execute_paper_operation_once
from trading_bot.cli.paper_operation_inspection import inspect_paper_operation_root
from trading_bot.runtime import (
    PaperOperationExecutionInputsError,
    VerifiedPaperOperationExecutionInputs,
)


def test_execution_input_contract_is_immutable_and_has_no_path_authority(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    inputs = fixture.inputs

    assert type(inputs) is VerifiedPaperOperationExecutionInputs
    assert {field.name for field in fields(inputs)} == {
        "intent",
        "application_id",
        "prior_genesis_checkpoint",
        "prior_successor_checkpoints",
        "prior_cycle_reports",
        "prior_snapshots",
        "verified_prior",
        "terminal_checkpoint_payload",
        "completed_snapshot_payload",
        "snapshot_verification",
        "cycle_configuration_payload",
        "request",
        "calendar",
    }
    assert not any(
        isinstance(getattr(inputs, field.name), Path) for field in fields(inputs)
    )
    assert not hasattr(inputs, "config")
    assert not hasattr(inputs, "operation_root")
    assert not hasattr(inputs, "lineage_manifest")
    with pytest.raises(FrozenInstanceError):
        inputs.application_id = UUID(int=0)  # type: ignore[misc]


def test_cli_adapter_retains_exact_semantics_and_discards_transport_paths(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    cli_inputs = fixture.cli_inputs
    wrong_reference = PaperOperationArtifactReference(
        cli_inputs.config.completed_snapshot.artifact_id,
        (tmp_path / "caller-selected-other-snapshot.json").resolve(),
        cli_inputs.config.completed_snapshot.sha256,
        cli_inputs.config.completed_snapshot.byte_length,
    )
    altered_config = replace(
        cli_inputs.config,
        completed_snapshot=wrong_reference,
    )
    altered_cli_inputs = replace(cli_inputs, config=altered_config)

    adapted = adapt_verified_paper_operation_execution_inputs(altered_cli_inputs)

    assert adapted == fixture.inputs
    assert adapted.intent is cli_inputs.intent
    assert adapted.completed_snapshot_payload is cli_inputs.completed_snapshot_payload
    assert adapted.intent.completed_snapshot_artifact == (
        cli_inputs.intent.completed_snapshot_artifact
    )
    assert not hasattr(adapted, "config")


@pytest.mark.parametrize(
    ("change", "message"),
    (
        (
            {"application_id": UUID("00000000-0000-0000-0000-000000000001")},
            "application ID",
        ),
        ({"terminal_checkpoint_payload": b"wrong"}, "terminal checkpoint payload"),
        ({"cycle_configuration_payload": b"wrong"}, "cycle configuration payload"),
    ),
)
def test_execution_inputs_fail_closed_on_identity_hash_or_length_mismatch(
    tmp_path: Path,
    change: dict[str, object],
    message: str,
) -> None:
    inputs = _setup(tmp_path).inputs

    with pytest.raises(PaperOperationExecutionInputsError, match=message):
        replace(inputs, **change)


def test_completed_snapshot_id_hash_and_length_each_fail_closed(
    tmp_path: Path,
) -> None:
    inputs = _setup(tmp_path).inputs
    wrong_id_verification = deepcopy(inputs.snapshot_verification)
    assert wrong_id_verification.snapshot is not None
    object.__setattr__(
        wrong_id_verification.snapshot,
        "snapshot_id",
        UUID("00000000-0000-0000-0000-000000000001"),
    )
    wrong_hash_payload = inputs.completed_snapshot_payload[:-1] + bytes(
        [inputs.completed_snapshot_payload[-1] ^ 1]
    )

    with pytest.raises(PaperOperationExecutionInputsError, match="snapshot evidence"):
        replace(inputs, snapshot_verification=wrong_id_verification)
    with pytest.raises(PaperOperationExecutionInputsError, match="snapshot evidence"):
        replace(inputs, completed_snapshot_payload=wrong_hash_payload)
    with pytest.raises(PaperOperationExecutionInputsError, match="snapshot evidence"):
        replace(
            inputs,
            completed_snapshot_payload=inputs.completed_snapshot_payload + b"x",
        )


def test_execution_inputs_reconcile_exact_request_and_prior_authority(
    tmp_path: Path,
) -> None:
    first = _setup(tmp_path / "first").inputs
    invalid_prior = deepcopy(_setup(tmp_path / "second").inputs.verified_prior)
    changed_request = replace(
        first.request,
        request_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    with pytest.raises(PaperOperationExecutionInputsError, match="cycle request"):
        replace(first, request=changed_request)
    with pytest.raises(
        PaperOperationExecutionInputsError,
        match="verified prior checkpoint",
    ):
        object.__setattr__(invalid_prior, "checkpoint_sha256", "0" * 64)
        replace(first, verified_prior=invalid_prior)


def test_architecture_67_rejects_cli_transport_inputs_exactly(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)

    with pytest.raises(TypeError, match="inspection arguments"):
        inspect_paper_operation_root(fixture.operation_root, fixture.cli_inputs)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="execution arguments"):
        execute_paper_operation_once(fixture.operation_root, fixture.cli_inputs)  # type: ignore[arg-type]


def test_adapter_rejects_nonexact_cli_input_type() -> None:
    with pytest.raises(TypeError, match="verified CLI"):
        adapt_verified_paper_operation_execution_inputs(object())  # type: ignore[arg-type]
