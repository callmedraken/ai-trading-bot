"""One-shot read-only stage isolation for the genuine PD2B1 composition."""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import NoReturn
from uuid import UUID

from trading_bot.runtime import (
    personal_desktop_paper_account_publication_freeze as publication_freeze,
)
from trading_bot.runtime import (
    personal_desktop_paper_account_security as paper_security,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as pd2c,
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
    supervised_paper_cycle_admission,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    read_personal_desktop_paper_account,
    require_validated_personal_desktop_paper_account,
)
from trading_bot.runtime.windows_authority import (
    WindowsAuthorityError,
    WindowsNativeError,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    acquire_validated_production_authority,
)

_SCHEMA = "pd2d1-b1-readonly-diagnostic/v1"
_EXPECTED_MACHINE_AUTHORITY_ID = "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1"
_EXPECTED_AUTHORITY_EPOCH_ID = "e6f3de5d-1412-40ad-a022-8b33e72a5f6d"
_EXPECTED_TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"
_EXPECTED_PAPER_ACCOUNT_ID = "9415cd7b-bf36-5fba-bd58-a0f99119dc21"
_EXPECTED_TERMINAL_CHECKPOINT_ID = UUID("1832a2b5-8b63-501a-8f7d-f1722c32307b")
_EXPECTED_OPERATION_ROOT = r"F:\AITradingBot\Paper-v2\runtime"

_EXPECTED_PUBLICATION_FREEZE = (
    _EXPECTED_MACHINE_AUTHORITY_ID,
    _EXPECTED_TRADING_SID,
    _EXPECTED_PAPER_ACCOUNT_ID,
    Decimal("25000"),
    datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC),
    "d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548",
    533,
    "16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85",
    465,
    "8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029",
    532,
)

_EXIT_USAGE = 2
_EXIT_PREFLIGHT = 3
_EXIT_C1 = 4
_EXIT_PRE_LOCK_READ = 5
_EXIT_ADMISSION_CONSTRUCTION = 6
_EXIT_MUTEX_ACQUIRE = 7
_EXIT_POST_LOCK_READ = 8
_EXIT_MUTEX_RELEASE = 9

_NATIVE_OPERATION_ALLOWLIST = frozenset(
    {
        "AddAccessAllowedAceEx",
        "ConvertSidToStringSidW",
        "ConvertStringSidToSidW",
        "GetAce",
        "GetAclInformation",
        "GetFileInformationByHandleEx(FileAttributeTagInfo)",
        "GetFinalPathNameByHandleW",
        "GetSecurityDescriptorControl",
        "GetSecurityInfo",
        "GetTokenInformation(TokenUser size)",
        "GetTokenInformation(TokenUser)",
        "GetVolumeInformationW",
        "GetVolumePathNameW",
        "InitializeAcl",
        "InitializeSecurityDescriptor",
        "OpenProcessToken",
        "SetSecurityDescriptorControl",
        "SetSecurityDescriptorDacl",
        "SetSecurityDescriptorOwner",
    }
)


class _CliUsageError(ValueError):
    pass


class _HarnessReconciliationError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise _CliUsageError("invalid PD2D1 B1 diagnostic arguments")


def build_parser() -> argparse.ArgumentParser:
    """Build the zero-semantic-input one-shot parser."""

    return _SanitizedArgumentParser(
        prog="diagnose_pd2d1_b1_readonly",
        description="Isolate genuine C1, Paper-v2 reads, and PD2A admission only.",
    )


def _require_all_effect_gates_false() -> None:
    if (
        paper_security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False
        or paper_security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED
        is not False
        or pd2c.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is not False
    ):
        raise _HarnessReconciliationError(
            "all Paper-v2 effect gates must remain exactly false"
        )


def _require_frozen_publication() -> None:
    freeze = publication_freeze.require_production_paper_publication_freeze()
    actual = (
        freeze.machine_authority_id,
        freeze.approved_trading_sid,
        freeze.paper_account_id,
        freeze.starting_cash,
        freeze.genesis_as_of,
        freeze.genesis_sha256,
        freeze.genesis_byte_length,
        freeze.anchor_sha256,
        freeze.anchor_byte_length,
        freeze.manifest_sha256,
        freeze.manifest_byte_length,
    )
    if actual != _EXPECTED_PUBLICATION_FREEZE:
        raise _HarnessReconciliationError(
            "Paper-v2 publication freeze differs from the accepted publication"
        )


def _reconcile_authority(authority: ValidatedProductionAuthority) -> None:
    if (
        authority.machine_authority_id != _EXPECTED_MACHINE_AUTHORITY_ID
        or authority.authority_epoch_id != _EXPECTED_AUTHORITY_EPOCH_ID
        or authority.approved_account_sid != _EXPECTED_TRADING_SID
    ):
        raise _HarnessReconciliationError(
            "production authority differs from the frozen identity"
        )


def _reconcile_account(account: object, evidence: object) -> str:
    anchor = evidence.anchor
    lineage = evidence.lineage
    if (
        anchor.paper_account_id != _EXPECTED_PAPER_ACCOUNT_ID
        or lineage.terminal_checkpoint_id != _EXPECTED_TERMINAL_CHECKPOINT_ID
        or type(evidence.successors) is not tuple
        or evidence.successors != ()
        or type(evidence.reports) is not tuple
        or evidence.reports != ()
        or type(evidence.snapshots) is not tuple
        or evidence.snapshots != ()
        or type(evidence.receipts) is not tuple
        or evidence.receipts != ()
        or account.operation_root != _EXPECTED_OPERATION_ROOT
    ):
        raise _HarnessReconciliationError(
            "Paper-v2 account differs from exact GENESIS-only state"
        )
    return anchor.paper_account_id


def _emit(record: dict[str, object], *, stream: object | None = None) -> None:
    destination = sys.stdout if stream is None else stream
    print(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=destination,
    )


def _exception_record(reason: str, error: Exception) -> dict[str, object]:
    if isinstance(error, PaperAccountMutexSecurityError):
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
    elif isinstance(error, PersonalDesktopPaperAccountError):
        family = "PERSONAL_DESKTOP_PAPER_ACCOUNT_ERROR"
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


def _release(admission: object) -> Exception | None:
    try:
        admission.__exit__(None, None, None)
    except Exception as error:
        return error
    return None


def main(argv: list[str] | None = None) -> int:
    """Run the six-stage read-only B1 diagnostic exactly once."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        return _blocked("INVALID_ARGUMENTS", _EXIT_USAGE)

    try:
        _require_all_effect_gates_false()
        _require_frozen_publication()
    except Exception as error:
        return _blocked("PREFLIGHT_BLOCKED", _EXIT_PREFLIGHT, error=error)

    try:
        authority = acquire_validated_production_authority()
        _reconcile_authority(authority)
    except Exception as error:
        return _blocked("C1_BLOCKED", _EXIT_C1, error=error)

    try:
        pre_lock_account = read_personal_desktop_paper_account(
            authority,
            historical_cycle_configuration_payloads=(),
        )
        pre = require_validated_personal_desktop_paper_account(pre_lock_account)
        pre_account_id = _reconcile_account(pre_lock_account, pre)
    except Exception as error:
        return _blocked(
            "PRE_LOCK_ACCOUNT_READ_BLOCKED", _EXIT_PRE_LOCK_READ, error=error
        )

    try:
        admission = supervised_paper_cycle_admission(pre_lock_account)
    except Exception as error:
        return _blocked(
            "MUTEX_ADMISSION_CONSTRUCTION_BLOCKED",
            _EXIT_ADMISSION_CONSTRUCTION,
            error=error,
        )

    try:
        held = admission.__enter__()
    except Exception as error:
        return _blocked("MUTEX_ACQUIRE_BLOCKED", _EXIT_MUTEX_ACQUIRE, error=error)

    primary_record: dict[str, object] | None = None
    primary_exit = _EXIT_MUTEX_ACQUIRE
    pending_base_exception: BaseException | None = None
    try:
        try:
            acquisition = held.acquisition
            if (
                held is not admission
                or acquisition is None
                or acquisition.paper_account_id != _EXPECTED_PAPER_ACCOUNT_ID
            ):
                primary_record = {
                    "reason": "MUTEX_ACQUIRE_RECONCILIATION_BLOCKED",
                    "schema": _SCHEMA,
                }
            elif acquisition.state is PaperAccountMutexState.ABANDONED_OWNER:
                primary_record = {
                    "reason": "ABANDONED_OWNER_RECONCILIATION_REQUIRED",
                    "schema": _SCHEMA,
                }
            elif acquisition.state is not PaperAccountMutexState.OWNED:
                primary_record = {
                    "reason": "MUTEX_ACQUIRE_RECONCILIATION_BLOCKED",
                    "schema": _SCHEMA,
                }
        except Exception as error:
            primary_record = _exception_record(
                "MUTEX_ACQUIRE_RECONCILIATION_BLOCKED", error
            )

        if primary_record is None:
            primary_exit = _EXIT_POST_LOCK_READ
            try:
                post_lock_account = read_personal_desktop_paper_account(
                    authority,
                    historical_cycle_configuration_payloads=(),
                )
                post = require_validated_personal_desktop_paper_account(
                    post_lock_account
                )
            except Exception as error:
                primary_record = _exception_record(
                    "POST_LOCK_ACCOUNT_READ_BLOCKED", error
                )
            else:
                try:
                    post_account_id = _reconcile_account(post_lock_account, post)
                    if not (
                        post_account_id
                        == pre_account_id
                        == acquisition.paper_account_id
                    ):
                        raise _HarnessReconciliationError(
                            "pre-lock, mutex, and post-lock account identities differ"
                        )
                except Exception as error:
                    primary_record = _exception_record(
                        "POST_LOCK_ACCOUNT_RECONCILIATION_BLOCKED", error
                    )
    except BaseException as error:
        pending_base_exception = error

    release_error = _release(admission)
    if release_error is not None:
        return _blocked(
            "MUTEX_RELEASE_BLOCKED", _EXIT_MUTEX_RELEASE, error=release_error
        )
    if pending_base_exception is not None:
        raise pending_base_exception.with_traceback(
            pending_base_exception.__traceback__
        )

    if primary_record is not None:
        _emit(primary_record, stream=sys.stderr)
        return primary_exit

    _emit(
        {
            "all_effect_gates_false": True,
            "authority_epoch_id": authority.authority_epoch_id,
            "machine_authority_id": authority.machine_authority_id,
            "mutex_acquisition_state": "OWNED",
            "operation_root_matches": True,
            "paper_account_id": post_account_id,
            "post_lock_genesis_only": True,
            "pre_lock_genesis_only": True,
            "result": "B1_READY",
            "schema": _SCHEMA,
            "terminal_checkpoint_id": str(post.lineage.terminal_checkpoint_id),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
