"""One-shot read-only isolation of P1 inside the genuine supervised B1 scope."""

from __future__ import annotations

import argparse
import ctypes
import json
import re
import sys
from typing import NoReturn
from uuid import UUID

from trading_bot.cli import pd2d1_preparation_readonly_diagnostic as frozen
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    VerifiedPriorCheckpointKind,
)
from trading_bot.runtime.exceptions import (
    CheckpointedVerifiedSnapshotPaperCycleError,
    VerifiedSnapshotPaperCyclePreparationError,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    WindowsSelectedC3SnapshotReadAuthority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperPriorCheckpointEvidence,
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyPlanError,
    ManualPaperStrategyPlanRequest,
    build_manual_paper_strategy_plan,
    verify_manual_paper_strategy_plan,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexBusyError,
    PaperAccountMutexError,
    PaperAccountMutexPoisonedError,
    PaperAccountMutexReentrantError,
    PaperAccountMutexReleaseError,
    PaperAccountMutexSecurityError,
    PaperAccountMutexState,
    PaperAccountMutexWaitError,
)
from trading_bot.runtime.personal_desktop_supervised_paper_cycle import (
    SupervisedPersonalDesktopPaperCycleError,
    supervised_personal_desktop_paper_cycle,
)
from trading_bot.runtime.windows_authority import (
    WindowsAuthorityError,
    WindowsNativeError,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
)

_SCHEMA = "pd2d1-p1-readonly-diagnostic/v1"
_EXPECTED_MACHINE_AUTHORITY_ID = frozen._EXPECTED_MACHINE_AUTHORITY_ID
_EXPECTED_AUTHORITY_EPOCH_ID = frozen._EXPECTED_AUTHORITY_EPOCH_ID
_EXPECTED_TRADING_SID = frozen._EXPECTED_TRADING_SID
_EXPECTED_PAPER_ACCOUNT_ID = frozen._EXPECTED_PAPER_ACCOUNT_ID
_EXPECTED_TERMINAL_CHECKPOINT_ID = frozen._EXPECTED_TERMINAL_CHECKPOINT_ID
_EXPECTED_SELECTION_ID = frozen._EXPECTED_SELECTION_ID
_EXPECTED_SELECTED_SNAPSHOT_ID = frozen._EXPECTED_SELECTED_SNAPSHOT_ID
_EXPECTED_SEED_ID = frozen._EXPECTED_SEED_ID
_EXPECTED_OPERATION_ROOT = frozen._EXPECTED_OPERATION_ROOT

_EXIT_USAGE = 2
_EXIT_PREFLIGHT = 3
_EXIT_C1 = 4
_EXIT_P2 = 5
_EXIT_B1_ENTER = 6
_EXIT_P1_REQUEST = 7
_EXIT_P1_BUILD = 8
_EXIT_P1_REPLAY = 9
_EXIT_P1_RECONCILIATION = 10
_EXIT_B1_RELEASE = 11

_NATIVE_OPERATION_ALLOWLIST = frozen._NATIVE_OPERATION_ALLOWLIST


class _CliUsageError(ValueError):
    pass


class _HarnessReconciliationError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise _CliUsageError("invalid PD2D1 P1 diagnostic arguments")


def build_parser() -> argparse.ArgumentParser:
    """Build the zero-semantic-input one-shot parser."""

    return _SanitizedArgumentParser(
        prog="diagnose_pd2d1_p1_readonly",
        description="Isolate frozen P1 build and replay inside genuine B1 only.",
    )


def _reconcile_cycle(cycle: object, active: object) -> tuple[object, str, object]:
    if active is not cycle:
        raise _HarnessReconciliationError("B1 scope did not return itself")
    acquisition = cycle.acquisition
    account = cycle.evidence
    paper_account_id = account.anchor.paper_account_id
    prior = account.prior_checkpoint
    if (
        acquisition.state is not PaperAccountMutexState.OWNED
        or acquisition.paper_account_id != _EXPECTED_PAPER_ACCOUNT_ID
        or paper_account_id != _EXPECTED_PAPER_ACCOUNT_ID
        or prior.kind is not VerifiedPriorCheckpointKind.GENESIS
        or prior.checkpoint_id != _EXPECTED_TERMINAL_CHECKPOINT_ID
        or prior.sequence != 0
        or account.lineage.terminal_checkpoint_id != _EXPECTED_TERMINAL_CHECKPOINT_ID
        or type(account.successors) is not tuple
        or account.successors != ()
        or type(account.reports) is not tuple
        or account.reports != ()
        or type(account.snapshots) is not tuple
        or account.snapshots != ()
        or type(account.receipts) is not tuple
        or account.receipts != ()
        or cycle.operation_root != _EXPECTED_OPERATION_ROOT
    ):
        raise _HarnessReconciliationError(
            "B1 evidence differs from exact owned GENESIS-only state"
        )
    return account, paper_account_id, prior


def _construct_request(
    selected: object,
    inputs: frozen._FrozenPreparationInputs,
    paper_account_id: str,
    prior: object,
) -> tuple[ManualPaperSelectedC3Assertion, ManualPaperStrategyPlanRequest]:
    assertion = ManualPaperSelectedC3Assertion(
        selected.audit.selection_id,
        selected.audit.session_id,
        selected.audit.terminal_id,
        selected.audit.snapshot_id,
        selected.audit.artifact_sha256,
        selected.audit.artifact_byte_length,
    )
    request = ManualPaperStrategyPlanRequest(
        selected.verification,
        paper_account_id,
        assertion,
        prior,
        inputs.history_seed,
        inputs.strategy_config,
        str(inputs.caller_idempotency_key),
        inputs.open_reference,
        inputs.policies,
        inputs.planning_at,
        inputs.submitted_at,
        inputs.filled_at,
        (),
    )
    return assertion, request


def _reconcile_plan(
    built: object,
    verified: object,
    *,
    paper_account_id: str,
    prior: object,
    assertion: ManualPaperSelectedC3Assertion,
    selected: object,
    caller_idempotency_key: UUID,
) -> dict[str, object]:
    if verified != built:
        raise _HarnessReconciliationError("P1 replay differs from built plan")
    plan = verified.plan
    request = verified.checkpointed_request
    artifact_sha256 = verified.artifact_sha256
    artifact_byte_length = verified.artifact_byte_length
    if (
        type(plan.plan_id) is not UUID
        or type(request.request_id) is not UUID
        or type(artifact_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", artifact_sha256) is None
        or type(artifact_byte_length) is not int
        or artifact_byte_length <= 0
        or plan.paper_account_id != paper_account_id
        or plan.selected_c3_assertion != assertion
        or plan.prior_checkpoint
        != ManualPaperPriorCheckpointEvidence.from_verified(prior)
        or plan.caller_idempotency_key != str(caller_idempotency_key)
        or request.snapshot_reference.snapshot_id != selected.audit.snapshot_id
        or request.snapshot_reference.artifact_sha256 != selected.audit.artifact_sha256
        or request.snapshot_reference.artifact_byte_length
        != selected.audit.artifact_byte_length
        or request.target != plan.target
    ):
        raise _HarnessReconciliationError(
            "P1 detached binding differs from exact frozen evidence"
        )
    return {
        "plan_artifact_byte_length": artifact_byte_length,
        "plan_artifact_sha256": artifact_sha256,
        "plan_id": str(plan.plan_id),
        "request_id": str(request.request_id),
    }


def _emit(record: dict[str, object], *, stream: object | None = None) -> None:
    destination = sys.stdout if stream is None else stream
    print(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=destination,
    )


def _exception_record(reason: str, error: Exception) -> dict[str, object]:
    if isinstance(error, ManualPaperStrategyPlanError):
        family = "MANUAL_PAPER_STRATEGY_PLAN_ERROR"
    elif isinstance(error, VerifiedSnapshotPaperCyclePreparationError):
        family = "VERIFIED_SNAPSHOT_PREPARATION_ERROR"
    elif isinstance(error, CheckpointedVerifiedSnapshotPaperCycleError):
        family = "CHECKPOINTED_VERIFIED_SNAPSHOT_CYCLE_ERROR"
    elif isinstance(error, PaperAccountMutexSecurityError):
        family = "PAPER_MUTEX_SECURITY_ERROR"
    elif isinstance(error, PaperAccountMutexBusyError):
        family = "PAPER_MUTEX_BUSY_ERROR"
    elif isinstance(error, PaperAccountMutexWaitError):
        family = "PAPER_MUTEX_WAIT_ERROR"
    elif isinstance(error, PaperAccountMutexReentrantError):
        family = "PAPER_MUTEX_REENTRANT_ERROR"
    elif isinstance(error, PaperAccountMutexReleaseError):
        family = "PAPER_MUTEX_RELEASE_ERROR"
    elif isinstance(error, PaperAccountMutexPoisonedError):
        family = "PAPER_MUTEX_POISONED_ERROR"
    elif isinstance(error, PaperAccountMutexError):
        family = "PAPER_MUTEX_ERROR"
    elif isinstance(error, SupervisedPersonalDesktopPaperCycleError):
        family = "SUPERVISED_CYCLE_ERROR"
    elif isinstance(error, PersonalDesktopPaperAccountError):
        family = "PAPER_ACCOUNT_ERROR"
    elif isinstance(error, WindowsNativeError):
        family = "WINDOWS_NATIVE_ERROR"
    elif isinstance(error, WindowsAuthorityError):
        family = "WINDOWS_AUTHORITY_ERROR"
    elif isinstance(error, ctypes.ArgumentError):
        family = "CTYPES_ARGUMENT_ERROR"
    elif isinstance(error, TypeError):
        family = "TYPE_ERROR"
    elif isinstance(error, ValueError):
        family = "VALUE_ERROR"
    elif isinstance(error, OSError):
        family = "OS_ERROR"
    elif isinstance(error, AttributeError):
        family = "ATTRIBUTE_ERROR"
    elif isinstance(error, KeyError):
        family = "KEY_ERROR"
    elif isinstance(error, IndexError):
        family = "INDEX_ERROR"
    elif isinstance(error, RuntimeError):
        family = "RUNTIME_ERROR"
    else:
        family = "UNKNOWN_EXCEPTION"

    record: dict[str, object] = {
        "exception_family": family,
        "reason": reason,
        "schema": _SCHEMA,
    }
    if isinstance(error, WindowsNativeError):
        if (
            type(error.operation) is str
            and error.operation in _NATIVE_OPERATION_ALLOWLIST
        ):
            record["native_operation"] = error.operation
        if type(error.error_code) is int or error.error_code is None:
            record["native_error_code"] = error.error_code
    return record


def _blocked(reason: str, exit_code: int, *, error: Exception | None = None) -> int:
    record = (
        {"reason": reason, "schema": _SCHEMA}
        if error is None
        else _exception_record(reason, error)
    )
    _emit(record, stream=sys.stderr)
    return exit_code


def _release(cycle: object) -> Exception | None:
    try:
        cycle.__exit__(None, None, None)
    except Exception as error:
        return error
    return None


def main(argv: list[str] | None = None) -> int:
    """Run the frozen P1-only diagnostic exactly once."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        return _blocked("INVALID_ARGUMENTS", _EXIT_USAGE)

    try:
        frozen._require_all_effect_gates_false()
        frozen._require_frozen_publication()
        history_seed = frozen._load_frozen_history_seed()
        inputs = frozen._frozen_inputs(history_seed)
    except Exception as error:
        return _blocked("PREFLIGHT_BLOCKED", _EXIT_PREFLIGHT, error=error)

    try:
        authority = acquire_validated_production_authority()
        frozen._reconcile_authority(authority)
    except Exception as error:
        return _blocked("C1_BLOCKED", _EXIT_C1, error=error)

    try:
        reader = WindowsSelectedC3SnapshotReadAuthority(authority)
        selected = reader.read_selected_snapshot(str(_EXPECTED_SELECTION_ID))
        frozen._reconcile_selected_snapshot(selected)
    except Exception as error:
        return _blocked("P2_BLOCKED", _EXIT_P2, error=error)

    try:
        cycle = supervised_personal_desktop_paper_cycle(
            authority,
            historical_cycle_configuration_payloads=(),
        )
        active = cycle.__enter__()
    except Exception as error:
        return _blocked("B1_ENTER_BLOCKED", _EXIT_B1_ENTER, error=error)

    primary_record: dict[str, object] | None = None
    primary_exit = _EXIT_B1_ENTER
    success_fields: dict[str, object] | None = None
    pending_base_exception: BaseException | None = None
    try:
        try:
            _, paper_account_id, prior = _reconcile_cycle(cycle, active)
        except Exception as error:
            primary_record = _exception_record("B1_ENTER_BLOCKED", error)

        assertion: ManualPaperSelectedC3Assertion | None = None
        request: ManualPaperStrategyPlanRequest | None = None
        if primary_record is None:
            primary_exit = _EXIT_P1_REQUEST
            try:
                assertion, request = _construct_request(
                    selected,
                    inputs,
                    paper_account_id,
                    prior,
                )
            except Exception as error:
                primary_record = _exception_record("P1_REQUEST_BLOCKED", error)

        built: object | None = None
        calendar: BoundMarketCalendar | None = None
        if primary_record is None:
            primary_exit = _EXIT_P1_BUILD
            try:
                calendar = BoundMarketCalendar(
                    XNYS_CALENDAR_DESCRIPTOR,
                    NYSEMarketCalendar(),
                )
                built = build_manual_paper_strategy_plan(request, calendar)
            except Exception as error:
                primary_record = _exception_record("P1_BUILD_BLOCKED", error)

        verified: object | None = None
        if primary_record is None:
            primary_exit = _EXIT_P1_REPLAY
            try:
                verified = verify_manual_paper_strategy_plan(
                    built.artifact_bytes,
                    calendar,
                    expected_sha256=built.artifact_sha256,
                    expected_byte_length=built.artifact_byte_length,
                    expected_checkpointed_request=built.checkpointed_request,
                )
            except Exception as error:
                primary_record = _exception_record("P1_REPLAY_BLOCKED", error)

        if primary_record is None:
            primary_exit = _EXIT_P1_RECONCILIATION
            try:
                assert assertion is not None
                success_fields = _reconcile_plan(
                    built,
                    verified,
                    paper_account_id=paper_account_id,
                    prior=prior,
                    assertion=assertion,
                    selected=selected,
                    caller_idempotency_key=inputs.caller_idempotency_key,
                )
            except Exception as error:
                primary_record = _exception_record("P1_RECONCILIATION_BLOCKED", error)
    except BaseException as error:
        pending_base_exception = error

    release_error = _release(cycle)
    if release_error is not None:
        return _blocked("B1_RELEASE_BLOCKED", _EXIT_B1_RELEASE, error=release_error)
    if pending_base_exception is not None:
        raise pending_base_exception.with_traceback(
            pending_base_exception.__traceback__
        )
    if primary_record is not None:
        _emit(primary_record, stream=sys.stderr)
        return primary_exit
    if success_fields is None:
        return _blocked("P1_RECONCILIATION_BLOCKED", _EXIT_P1_RECONCILIATION)

    _emit(
        {
            "all_effect_gates_false": True,
            "authority_epoch_id": authority.authority_epoch_id,
            "machine_authority_id": authority.machine_authority_id,
            "mutex_acquisition_state": "OWNED",
            "paper_account_id": paper_account_id,
            "result": "P1_READY",
            "schema": _SCHEMA,
            "seed_id": str(inputs.history_seed.seed.seed_id),
            "selected_snapshot_id": str(selected.audit.snapshot_id),
            "selection_id": str(selected.audit.selection_id),
            "terminal_checkpoint_id": str(prior.checkpoint_id),
            **success_fields,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
