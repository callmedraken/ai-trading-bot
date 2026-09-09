"""Architecture-107 frozen first-operation admission coverage."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.runtime.paper_operation_execution_inputs import (
    VerifiedPaperOperationExecutionInputs,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
    PersonalDesktopFirstPaperOperationMismatchError,
    reconcile_personal_desktop_first_paper_operation,
)


def _inputs(**changes: object) -> VerifiedPaperOperationExecutionInputs:
    profile = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE
    values = {
        "terminal_checkpoint_id": profile.terminal_checkpoint_id,
        "verified_prior_checkpoint_id": profile.terminal_checkpoint_id,
        "completed_snapshot_id": profile.selected_snapshot_id,
        "caller_idempotency_key": profile.caller_idempotency_key,
        "request_id": profile.request_id,
        "configuration_sha256": profile.plan_sha256,
        "configuration_byte_length": profile.plan_byte_length,
        "operation_id": profile.operation_id,
        "application_id": profile.application_id,
    }
    values.update(changes)
    inputs = object.__new__(VerifiedPaperOperationExecutionInputs)
    object.__setattr__(
        inputs,
        "intent",
        SimpleNamespace(
            terminal_checkpoint_artifact=SimpleNamespace(
                artifact_id=values["terminal_checkpoint_id"]
            ),
            caller_idempotency_key=values["caller_idempotency_key"],
            operation_id=values["operation_id"],
            completed_snapshot_artifact=SimpleNamespace(
                artifact_id=values["completed_snapshot_id"]
            ),
            cycle_configuration_artifact=SimpleNamespace(
                sha256=values["configuration_sha256"],
                byte_length=values["configuration_byte_length"],
            ),
        ),
    )
    object.__setattr__(
        inputs,
        "request",
        SimpleNamespace(request_id=values["request_id"]),
    )
    object.__setattr__(inputs, "application_id", values["application_id"])
    object.__setattr__(
        inputs,
        "verified_prior",
        SimpleNamespace(checkpoint_id=values["verified_prior_checkpoint_id"]),
    )
    return inputs


def _admit(**changes: object) -> None:
    profile = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE
    values = {
        "paper_account_id": profile.paper_account_id,
        "plan_id": profile.plan_id,
        "selected_snapshot_id": profile.selected_snapshot_id,
        "plan_sha256": profile.plan_sha256,
        "plan_byte_length": profile.plan_byte_length,
        "operation_root": profile.operation_root,
        "inputs": _inputs(),
    }
    input_fields = {
        "terminal_checkpoint_id",
        "verified_prior_checkpoint_id",
        "completed_snapshot_id",
        "caller_idempotency_key",
        "request_id",
        "configuration_sha256",
        "configuration_byte_length",
        "operation_id",
        "application_id",
    }
    input_changes = {
        name: changes.pop(name) for name in tuple(changes) if name in input_fields
    }
    if input_changes:
        values["inputs"] = _inputs(**input_changes)
    values.update(changes)
    reconcile_personal_desktop_first_paper_operation(**values)


def test_exact_source_owned_first_operation_profile_is_admitted() -> None:
    _admit()


def test_reconciliation_exposes_no_expected_profile_override() -> None:
    parameters = inspect.signature(
        reconcile_personal_desktop_first_paper_operation
    ).parameters
    assert "profile" not in parameters
    assert "expected" not in parameters


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("paper_account_id", "00000000-0000-0000-0000-000000000000"),
        ("terminal_checkpoint_id", UUID(int=1)),
        ("verified_prior_checkpoint_id", UUID(int=11)),
        ("selected_snapshot_id", UUID(int=2)),
        ("completed_snapshot_id", UUID(int=12)),
        ("caller_idempotency_key", UUID(int=3)),
        ("request_id", UUID(int=4)),
        ("plan_id", UUID(int=5)),
        ("plan_sha256", "0" * 64),
        ("plan_byte_length", 6200),
        ("configuration_sha256", "1" * 64),
        ("configuration_byte_length", 6201),
        ("operation_id", UUID(int=6)),
        ("application_id", UUID(int=7)),
        ("operation_root", r"F:\AITradingBot\Paper-v2\alternate"),
    ],
)
def test_each_frozen_first_operation_mismatch_fails_closed(
    field: str,
    replacement: object,
) -> None:
    with pytest.raises(PersonalDesktopFirstPaperOperationMismatchError):
        _admit(**{field: replacement})
