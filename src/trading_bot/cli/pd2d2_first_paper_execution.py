"""One-shot PD2D2 harness for the frozen first Paper-v2 execution."""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections.abc import Callable
from ctypes import ArgumentError as CtypesArgumentError
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import UUID

from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
    PaperOperationExecutionDiagnosticCode,
)
from trading_bot.cli.paper_operation_inspection import PaperOperationInspectionCode
from trading_bot.domain import Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
)
from trading_bot.portfolio import PortfolioConstraints
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import (
    personal_desktop_paper_account_publication_freeze as publication_freeze,
)
from trading_bot.runtime import (
    personal_desktop_paper_account_security as paper_security,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as execution_boundary,
)
from trading_bot.runtime.exceptions import VerifiedSnapshotPaperCyclePreparationError
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadError,
    WindowsSelectedC3SnapshotReadAuthority,
)
from trading_bot.runtime.manual_paper_strategy_plan import ManualPaperStrategyPlanError
from trading_bot.runtime.paper_operation import PaperOperationError
from trading_bot.runtime.paper_operation_execution_inputs import (
    PaperOperationExecutionInputsError,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
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
    PaperAccountMutexWaitError,
)
from trading_bot.runtime.personal_desktop_supervised_paper_cycle import (
    SupervisedPersonalDesktopPaperCycleError,
)
from trading_bot.runtime.personal_desktop_supervised_paper_operation_execution import (  # noqa: E501
    SupervisedPaperOperationEffectsDisabledError,
    SupervisedPaperOperationExecutionError,
    SupervisedPaperOperationExecutionResult,
    SupervisedPaperOperationResultReconciliationError,
    SupervisedPaperOperationRootMismatchError,
    execute_supervised_personal_desktop_paper_operation,
)
from trading_bot.runtime.personal_desktop_supervised_paper_operation_preparation import (  # noqa: E501
    PaperOperationPreparationReconciliationRequiredError,
    SupervisedPaperOperationPreparationError,
)
from trading_bot.runtime.strategy_history_seed import (
    VerifiedStrategyHistorySeed,
    verify_strategy_history_seed,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority import (
    WindowsAuthorityError,
    WindowsNativeError,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_SCHEMA = "pd2d2-first-paper-execution-evidence/v1"

_EXPECTED_MACHINE_AUTHORITY_ID = "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1"
_EXPECTED_AUTHORITY_EPOCH_ID = "e6f3de5d-1412-40ad-a022-8b33e72a5f6d"
_EXPECTED_TRADING_SID = (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
)
_EXPECTED_PAPER_ACCOUNT_ID = (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.paper_account_id
)
_EXPECTED_TERMINAL_CHECKPOINT_ID = (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.terminal_checkpoint_id
)
_EXPECTED_SELECTION_ID = UUID("36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280")
_EXPECTED_SELECTED_SNAPSHOT_ID = (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.selected_snapshot_id
)
_EXPECTED_SELECTED_SHA256 = (
    "31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d"
)
_EXPECTED_SELECTED_BYTE_LENGTH = 1291
_EXPECTED_SEED_ID = UUID("5dc95e10-ba22-5b91-94b2-0d851aa8e2d7")
_EXPECTED_SEED_SHA256 = (
    "40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64"
)
_EXPECTED_SEED_BYTE_LENGTH = 1060
_EXPECTED_CALLER_IDEMPOTENCY_KEY = (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.caller_idempotency_key
)
_EXPECTED_REQUEST_ID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.request_id
_EXPECTED_PLAN_ID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.plan_id
_EXPECTED_PLAN_SHA256 = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.plan_sha256
_EXPECTED_PLAN_BYTE_LENGTH = (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.plan_byte_length
)
_EXPECTED_OPERATION_ID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.operation_id
_EXPECTED_APPLICATION_ID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.application_id
_EXPECTED_PUBLICATION_FREEZE_BLOB = "b125cbb1c80a827f74018cf2955b9a27ba69fa90"

_EXPECTED_GENESIS_SHA256 = (
    "d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548"
)
_EXPECTED_GENESIS_BYTE_LENGTH = 533
_EXPECTED_ANCHOR_SHA256 = (
    "16c4dba01835c5bc2def91f0103ad79c3da0b5d18af72091b4fdd37fe4353c85"
)
_EXPECTED_ANCHOR_BYTE_LENGTH = 465
_EXPECTED_MANIFEST_SHA256 = (
    "8fe1d705d59a79207ab6236af71becee0051042dc7b3ecaf23bb7f5531cb0029"
)
_EXPECTED_MANIFEST_BYTE_LENGTH = 532
_EXPECTED_GENESIS_AS_OF = datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC)
_EXPECTED_TARGET_SESSION = TradingSession(date(2026, 8, 28))
_EXPECTED_OPEN_SESSION = TradingSession(date(2026, 8, 31))
_EXPECTED_SYMBOL = Symbol("SPY")
_EXPECTED_SEED_PATH = Path(
    r"F:\AI\worktrees\ai-trading-bot-personal-desktop"
    r"\docs\validation\evidence"
    r"\pd2d1-spy-strategy-history-seed-2026-08-28.json"
)

_EXIT_INVALID_ARGUMENTS = 2
_EXIT_SUPERVISED_EXECUTION_GATE_DISABLED = 3
_EXIT_EFFECT_GATE_STATE_INVALID = 4
_EXIT_PREFLIGHT_BLOCKED = 5
_EXIT_PRODUCTION_AUTHORITY_BLOCKED = 6
_EXIT_AUTHORITY_IDENTITY_MISMATCH = 7
_EXIT_SELECTED_SNAPSHOT_BLOCKED = 8
_EXIT_SELECTED_SNAPSHOT_MISMATCH = 9
_EXIT_EXECUTION_BOUNDARY_EXCEPTION = 10
_EXIT_RESULT_TYPE_INVALID = 11
_EXIT_RESULT_IDENTITY_MISMATCH = 12
_EXIT_COMPLETED_RESULT_RECONCILIATION_BLOCKED = 13
_EXIT_BLOCKED = 14
_EXIT_CONFLICTING = 15
_EXIT_ALREADY_APPLIED = 16
_EXIT_EXECUTION_FAILED = 17
_EXIT_RECEIPT_RECOVERED = 18
_EXIT_UNEXPECTED_EXECUTION_CLASSIFICATION = 19

_PRODUCTION_ISSUER = object()
_DISPOSABLE_TEST_ISSUER = object()

_SAFE_NATIVE_OPERATION_ALLOWLIST = frozenset(
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
_SAFE_RESULT_DIAGNOSTICS = frozenset(
    value.value
    for enum_type in (
        PaperOperationExecutionDiagnosticCode,
        PaperOperationInspectionCode,
    )
    for value in enum_type
)


class _CliUsageError(ValueError):
    pass


class _HarnessReconciliationError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid PD2D2 execution arguments")


class _SelectedReader(Protocol):
    def read_selected_snapshot(self, selection_id: str) -> object: ...


class _SelectedReaderFactory(Protocol):
    def __call__(self, authority: object) -> _SelectedReader: ...


class _ExecutionBoundary(Protocol):
    def __call__(
        self, authority: object, selected_snapshot: object, **kwargs: object
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class _FrozenExecutionInputs:
    history_seed: VerifiedStrategyHistorySeed
    strategy_config: MovingAverageCrossoverConfig
    caller_idempotency_key: UUID
    open_reference: CallerAssertedNextSessionOpenReference
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime


class _DisposableFirstPaperExecutionHarnessAuthorityForTest:
    """Private one-shot authority for injected, no-effect orchestration tests."""

    __slots__ = ("_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer is not _DISPOSABLE_TEST_ISSUER:
            raise TypeError("disposable harness authority requires its test issuer")
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False

    def _consume(self) -> None:
        lock = getattr(self, "_lock", None)
        if not hasattr(lock, "__enter__"):
            raise TypeError("disposable harness authority is invalid")
        with lock:
            if getattr(self, "_issuer", None) is not _DISPOSABLE_TEST_ISSUER or getattr(
                self, "_used", True
            ):
                raise TypeError("disposable harness authority is invalid or consumed")
            self._used = True

    def __copy__(self) -> object:
        raise TypeError("disposable harness authorities cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("disposable harness authorities cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("disposable harness authorities cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("disposable harness authorities cannot be pickled")


def build_parser() -> argparse.ArgumentParser:
    """Build the zero-semantic-input one-shot parser."""

    return _SanitizedArgumentParser(
        prog="execute_first_personal_desktop_paper_operation",
        description="Execute the frozen first Paper-v2 operation exactly once.",
    )


def _gate_preflight_failure(
    production_gate: object,
    recovery_gate: object,
    supervised_gate: object,
) -> tuple[str, int] | None:
    if production_gate is not False or recovery_gate is not False:
        return "EFFECT_GATE_STATE_INVALID", _EXIT_EFFECT_GATE_STATE_INVALID
    if supervised_gate is not True:
        return (
            "SUPERVISED_EXECUTION_GATE_DISABLED",
            _EXIT_SUPERVISED_EXECUTION_GATE_DISABLED,
        )
    return None


def _require_frozen_publication() -> None:
    freeze = publication_freeze.require_production_paper_publication_freeze()
    if (
        freeze.machine_authority_id != _EXPECTED_MACHINE_AUTHORITY_ID
        or freeze.approved_trading_sid != _EXPECTED_TRADING_SID
        or freeze.paper_account_id != _EXPECTED_PAPER_ACCOUNT_ID
        or freeze.starting_cash != Decimal("25000")
        or freeze.genesis_as_of != _EXPECTED_GENESIS_AS_OF
        or freeze.genesis_sha256 != _EXPECTED_GENESIS_SHA256
        or freeze.genesis_byte_length != _EXPECTED_GENESIS_BYTE_LENGTH
        or freeze.anchor_sha256 != _EXPECTED_ANCHOR_SHA256
        or freeze.anchor_byte_length != _EXPECTED_ANCHOR_BYTE_LENGTH
        or freeze.manifest_sha256 != _EXPECTED_MANIFEST_SHA256
        or freeze.manifest_byte_length != _EXPECTED_MANIFEST_BYTE_LENGTH
    ):
        raise _HarnessReconciliationError(
            "Paper-v2 publication freeze differs from the frozen profile"
        )


def _resolve_frozen_seed_path() -> Path:
    candidate = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "validation"
        / "evidence"
        / "pd2d1-spy-strategy-history-seed-2026-08-28.json"
    ).resolve(strict=True)
    if candidate != _EXPECTED_SEED_PATH:
        raise _HarnessReconciliationError(
            "strategy-history seed is not at its frozen transport location"
        )
    return candidate


def _frozen_strategy_config() -> MovingAverageCrossoverConfig:
    return MovingAverageCrossoverConfig(3, 5, Decimal("1"))


def _load_frozen_history_seed() -> VerifiedStrategyHistorySeed:
    payload = _resolve_frozen_seed_path().read_bytes()
    if (
        type(payload) is not bytes
        or len(payload) != _EXPECTED_SEED_BYTE_LENGTH
        or sha256(payload).hexdigest() != _EXPECTED_SEED_SHA256
    ):
        raise _HarnessReconciliationError(
            "strategy-history seed bytes differ from the frozen evidence"
        )
    strategy_config = _frozen_strategy_config()
    verified = verify_strategy_history_seed(
        payload,
        expected_symbol=_EXPECTED_SYMBOL,
        target_session=_EXPECTED_TARGET_SESSION,
        strategy_config=strategy_config,
        calendar=BoundMarketCalendar(
            XNYS_CALENDAR_DESCRIPTOR,
            NYSEMarketCalendar(),
        ),
    )
    if (
        type(verified) is not VerifiedStrategyHistorySeed
        or verified.seed.seed_id != _EXPECTED_SEED_ID
        or verified.seed.symbol != _EXPECTED_SYMBOL
        or verified.target_session != _EXPECTED_TARGET_SESSION
        or verified.strategy_config != strategy_config
        or verified.artifact_sha256 != _EXPECTED_SEED_SHA256
        or verified.artifact_byte_length != _EXPECTED_SEED_BYTE_LENGTH
    ):
        raise _HarnessReconciliationError(
            "verified strategy-history seed differs from the frozen evidence"
        )
    return verified


def _frozen_inputs(history_seed: VerifiedStrategyHistorySeed) -> _FrozenExecutionInputs:
    return _FrozenExecutionInputs(
        history_seed=history_seed,
        strategy_config=_frozen_strategy_config(),
        caller_idempotency_key=_EXPECTED_CALLER_IDEMPOTENCY_KEY,
        open_reference=CallerAssertedNextSessionOpenReference(
            _EXPECTED_SYMBOL,
            _EXPECTED_OPEN_SESSION,
            Decimal("767.33"),
        ),
        policies=VerifiedSnapshotPaperCyclePolicies(
            rebalance_assumptions=RebalanceAssumptions(
                fixed_commission=Decimal("0"),
                allow_fractional_quantities=False,
                quantity_increment=Decimal("1"),
                minimum_trade_notional=Decimal("0"),
                minimum_trade_quantity=Decimal("1"),
                target_weight_tolerance=Decimal("0"),
                additional_execution_cash_buffer=Decimal("0"),
                use_planned_sell_proceeds=False,
            ),
            portfolio_constraints=PortfolioConstraints(
                minimum_cash_weight=Decimal("0.90"),
                maximum_cash_weight=Decimal("1"),
                maximum_position_weight=Decimal("0.10"),
                maximum_one_way_rebalance_turnover=Decimal("0.10"),
                minimum_position_weight=None,
                long_only=True,
                allow_leverage=False,
            ),
            proposal_policy=RebalanceProposalPolicy(allow_partial_plans=False),
            proposal_confidence=None,
            risk_limits=RiskLimits(
                max_position_percent=Decimal("0.10"),
                max_total_exposure_percent=Decimal("0.10"),
                max_order_notional=Decimal("2500"),
                max_new_position_percent=Decimal("0.10"),
                minimum_cash_reserve_percent=Decimal("0.90"),
                allow_fractional_shares=False,
                fractional_increment=Decimal("1"),
                allow_buying=True,
                allow_selling=True,
                estimated_commission=Decimal("0"),
            ),
            risk_policy=PortfolioRiskPolicy(allow_sell_proceeds_for_later_buys=False),
            fill_policy=PaperFillPolicy(
                slippage_basis_points=Decimal("0"),
                fixed_commission=Decimal("0"),
            ),
            trading_enabled=True,
        ),
        planning_at=_EXPECTED_GENESIS_AS_OF,
        submitted_at=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
        filled_at=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
    )


def _reconcile_authority(authority: object) -> None:
    if (
        getattr(authority, "machine_authority_id", None)
        != _EXPECTED_MACHINE_AUTHORITY_ID
        or getattr(authority, "authority_epoch_id", None)
        != _EXPECTED_AUTHORITY_EPOCH_ID
        or getattr(authority, "approved_account_sid", None) != _EXPECTED_TRADING_SID
    ):
        raise _HarnessReconciliationError(
            "current production authority differs from the frozen identity"
        )


def _reconcile_selected_snapshot(result: object) -> None:
    try:
        audit = result.audit
        snapshot_bytes = result.snapshot_bytes
        snapshot = result.verification.snapshot
        bars = tuple(item.bar.symbol for item in snapshot.bars)
    except (AttributeError, TypeError) as error:
        raise _HarnessReconciliationError(
            "P2 returned incomplete selected-snapshot evidence"
        ) from error
    if (
        audit.selection_id != _EXPECTED_SELECTION_ID
        or audit.snapshot_id != _EXPECTED_SELECTED_SNAPSHOT_ID
        or audit.artifact_sha256 != _EXPECTED_SELECTED_SHA256
        or audit.artifact_byte_length != _EXPECTED_SELECTED_BYTE_LENGTH
        or type(snapshot_bytes) is not bytes
        or len(snapshot_bytes) != _EXPECTED_SELECTED_BYTE_LENGTH
        or sha256(snapshot_bytes).hexdigest() != _EXPECTED_SELECTED_SHA256
        or snapshot is None
        or snapshot.snapshot_id != _EXPECTED_SELECTED_SNAPSHOT_ID
        or snapshot.target_session != _EXPECTED_TARGET_SESSION
        or snapshot.request.symbols != (_EXPECTED_SYMBOL,)
        or bars != (_EXPECTED_SYMBOL,)
        or getattr(result, "provider_call_performed", False) is not False
        or getattr(result, "database_mutation_performed", False) is not False
    ):
        raise _HarnessReconciliationError(
            "P2 selected snapshot differs from frozen call number six"
        )


def _emit(record: dict[str, object], *, stream: object | None = None) -> None:
    destination = sys.stdout if stream is None else stream
    print(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=destination,
    )


def _blocked(
    reason: str,
    exit_code: int,
    *,
    facts: dict[str, object] | None = None,
) -> int:
    record: dict[str, object] = {"reason": reason, "schema": _SCHEMA}
    if facts is not None:
        record.update(facts)
    _emit(record, stream=sys.stderr)
    return exit_code


def _exception_family(error: Exception) -> str:
    if isinstance(error, SupervisedPaperOperationEffectsDisabledError):
        return "SUPERVISED_EFFECTS_DISABLED"
    if isinstance(error, SupervisedPaperOperationRootMismatchError):
        return "SUPERVISED_ROOT_MISMATCH"
    if isinstance(error, SupervisedPaperOperationResultReconciliationError):
        return "SUPERVISED_RESULT_RECONCILIATION"
    if isinstance(error, SupervisedPaperOperationExecutionError):
        return "SUPERVISED_EXECUTION_ERROR"
    if isinstance(error, PaperOperationPreparationReconciliationRequiredError):
        return "PAPER_OPERATION_PREPARATION_RECONCILIATION_REQUIRED"
    if isinstance(error, PaperAccountMutexSecurityError):
        return "PAPER_MUTEX_SECURITY_ERROR"
    if isinstance(error, PaperAccountMutexBusyError):
        return "PAPER_MUTEX_BUSY_ERROR"
    if isinstance(error, PaperAccountMutexWaitError):
        return "PAPER_MUTEX_WAIT_ERROR"
    if isinstance(error, PaperAccountMutexReentrantError):
        return "PAPER_MUTEX_REENTRANT_ERROR"
    if isinstance(error, PaperAccountMutexReleaseError):
        return "PAPER_MUTEX_RELEASE_ERROR"
    if isinstance(error, PaperAccountMutexPoisonedError):
        return "PAPER_MUTEX_POISONED_ERROR"
    if isinstance(error, PaperAccountMutexError):
        return "PAPER_MUTEX_ERROR"
    if isinstance(error, ManualPaperStrategyPlanError):
        return "MANUAL_PAPER_STRATEGY_PLAN_ERROR"
    if isinstance(error, PaperOperationError):
        return "PAPER_OPERATION_ERROR"
    if isinstance(error, PaperOperationExecutionInputsError):
        return "PAPER_OPERATION_EXECUTION_INPUTS_ERROR"
    if isinstance(error, VerifiedSnapshotPaperCyclePreparationError):
        return "VERIFIED_SNAPSHOT_PREPARATION_ERROR"
    if isinstance(error, SupervisedPaperOperationPreparationError):
        return "SUPERVISED_PREPARATION_ERROR"
    if isinstance(error, SupervisedPersonalDesktopPaperCycleError):
        return "SUPERVISED_PAPER_CYCLE_ERROR"
    if isinstance(error, SelectedC3SnapshotReadError):
        return "SELECTED_SNAPSHOT_READ_ERROR"
    if isinstance(error, PersonalDesktopPaperAccountError):
        return "PAPER_ACCOUNT_ERROR"
    if isinstance(error, WindowsNativeError):
        return "WINDOWS_NATIVE_ERROR"
    if isinstance(error, WindowsAuthorityError):
        return "WINDOWS_AUTHORITY_ERROR"
    if isinstance(error, CtypesArgumentError):
        return "CTYPES_ARGUMENT_ERROR"
    if isinstance(error, TypeError):
        return "TYPE_ERROR"
    if isinstance(error, ValueError):
        return "VALUE_ERROR"
    if isinstance(error, OSError):
        return "OS_ERROR"
    if isinstance(error, RuntimeError):
        return "RUNTIME_ERROR"
    return "UNKNOWN_EXCEPTION"


def _execution_exception_record(error: Exception) -> dict[str, object]:
    record: dict[str, object] = {
        "exception_family": _exception_family(error),
        "reason": "EXECUTION_BOUNDARY_EXCEPTION",
        "schema": _SCHEMA,
    }
    if isinstance(error, WindowsNativeError):
        if (
            type(error.operation) is str
            and error.operation in _SAFE_NATIVE_OPERATION_ALLOWLIST
        ):
            record["native_operation"] = error.operation
        if type(error.error_code) is int or error.error_code is None:
            record["native_error_code"] = error.error_code
    return record


def _safe_result_facts(
    result: SupervisedPaperOperationExecutionResult,
) -> dict[str, object]:
    diagnostic = (
        result.diagnostic_code
        if result.diagnostic_code in _SAFE_RESULT_DIAGNOSTICS
        else "UNEXPECTED_DIAGNOSTIC"
    )
    return {
        "diagnostic_code": diagnostic,
        "execution_classification": result.execution_classification.value,
    }


def _success_record(
    selected_snapshot: object,
    inputs: _FrozenExecutionInputs,
    result: SupervisedPaperOperationExecutionResult,
) -> dict[str, object]:
    return {
        "application_id": str(result.application_id),
        "cycle_result_id": str(result.cycle_result_id),
        "diagnostic_code": result.diagnostic_code,
        "execution_classification": result.execution_classification.value,
        "executor_called": result.executor_called,
        "operation_id": str(result.operation_id),
        "paper_account_id": _EXPECTED_PAPER_ACCOUNT_ID,
        "production_effects_gate": False,
        "receipt_evidence_produced": result.receipt_evidence_produced,
        "recovery_effects_gate": False,
        "result": "COMPLETED",
        "schema": _SCHEMA,
        "seed_id": str(inputs.history_seed.seed.seed_id),
        "selected_snapshot_id": str(selected_snapshot.audit.snapshot_id),
        "selection_id": str(selected_snapshot.audit.selection_id),
        "successor_checkpoint_id": str(result.successor_checkpoint_id),
        "supervised_execution_gate": True,
        "transition_evidence_produced": result.transition_evidence_produced,
    }


def _handle_result(
    selected_snapshot: object,
    inputs: _FrozenExecutionInputs,
    raw_result: object,
) -> int:
    if type(raw_result) is not SupervisedPaperOperationExecutionResult:
        return _blocked("RESULT_TYPE_INVALID", _EXIT_RESULT_TYPE_INVALID)
    result = raw_result
    if (
        result.operation_id != _EXPECTED_OPERATION_ID
        or result.application_id != _EXPECTED_APPLICATION_ID
    ):
        return _blocked("RESULT_IDENTITY_MISMATCH", _EXIT_RESULT_IDENTITY_MISMATCH)

    classification_exits = {
        PaperOperationExecutionClassification.BLOCKED: ("BLOCKED", _EXIT_BLOCKED),
        PaperOperationExecutionClassification.CONFLICTING: (
            "CONFLICTING",
            _EXIT_CONFLICTING,
        ),
        PaperOperationExecutionClassification.ALREADY_APPLIED: (
            "ALREADY_APPLIED",
            _EXIT_ALREADY_APPLIED,
        ),
        PaperOperationExecutionClassification.EXECUTION_FAILED: (
            "EXECUTION_FAILED",
            _EXIT_EXECUTION_FAILED,
        ),
        PaperOperationExecutionClassification.RECEIPT_RECOVERED: (
            "RECEIPT_RECOVERED",
            _EXIT_RECEIPT_RECOVERED,
        ),
    }
    non_normal = classification_exits.get(result.execution_classification)
    if non_normal is not None:
        reason, exit_code = non_normal
        return _blocked(reason, exit_code, facts=_safe_result_facts(result))
    if (
        result.execution_classification
        is not PaperOperationExecutionClassification.COMPLETED
    ):
        return _blocked(
            "UNEXPECTED_EXECUTION_CLASSIFICATION",
            _EXIT_UNEXPECTED_EXECUTION_CLASSIFICATION,
        )
    if (
        result.diagnostic_code != PaperOperationExecutionDiagnosticCode.COMPLETED.value
        or type(result.cycle_result_id) is not UUID
        or type(result.successor_checkpoint_id) is not UUID
        or result.transition_evidence_produced is not True
        or result.receipt_evidence_produced is not True
        or result.executor_called is not True
    ):
        return _blocked(
            "COMPLETED_RESULT_RECONCILIATION_BLOCKED",
            _EXIT_COMPLETED_RESULT_RECONCILIATION_BLOCKED,
            facts=_safe_result_facts(result),
        )
    _emit(_success_record(selected_snapshot, inputs, result))
    return 0


def _run_after_gate_preflight(
    *,
    publication_preflight: Callable[[], None],
    history_seed_loader: Callable[[], VerifiedStrategyHistorySeed],
    authority_loader: Callable[[], object],
    selected_reader_factory: _SelectedReaderFactory,
    supervised_executor: _ExecutionBoundary,
    _issuer: object,
) -> int:
    if _issuer is not _PRODUCTION_ISSUER and _issuer is not _DISPOSABLE_TEST_ISSUER:
        raise TypeError("first-paper execution harness issuer is invalid")
    try:
        publication_preflight()
        history_seed = history_seed_loader()
        inputs = _frozen_inputs(history_seed)
    except Exception:
        return _blocked("PREFLIGHT_BLOCKED", _EXIT_PREFLIGHT_BLOCKED)

    try:
        authority = authority_loader()
        _reconcile_authority(authority)
    except _HarnessReconciliationError:
        return _blocked(
            "AUTHORITY_IDENTITY_MISMATCH",
            _EXIT_AUTHORITY_IDENTITY_MISMATCH,
        )
    except Exception:
        return _blocked(
            "PRODUCTION_AUTHORITY_BLOCKED",
            _EXIT_PRODUCTION_AUTHORITY_BLOCKED,
        )

    try:
        reader = selected_reader_factory(authority)
        selected_snapshot = reader.read_selected_snapshot(str(_EXPECTED_SELECTION_ID))
        _reconcile_selected_snapshot(selected_snapshot)
    except _HarnessReconciliationError:
        return _blocked(
            "SELECTED_SNAPSHOT_MISMATCH",
            _EXIT_SELECTED_SNAPSHOT_MISMATCH,
        )
    except Exception:
        return _blocked(
            "SELECTED_SNAPSHOT_BLOCKED",
            _EXIT_SELECTED_SNAPSHOT_BLOCKED,
        )

    try:
        result = supervised_executor(
            authority,
            selected_snapshot,
            history_seed=inputs.history_seed,
            strategy_config=inputs.strategy_config,
            caller_idempotency_key=inputs.caller_idempotency_key,
            open_reference=inputs.open_reference,
            policies=inputs.policies,
            planning_at=inputs.planning_at,
            submitted_at=inputs.submitted_at,
            filled_at=inputs.filled_at,
            metadata=(),
            historical_cycle_configuration_payloads=(),
        )
    except Exception as error:
        _emit(_execution_exception_record(error), stream=sys.stderr)
        return _EXIT_EXECUTION_BOUNDARY_EXCEPTION
    return _handle_result(selected_snapshot, inputs, result)


def _open_disposable_first_paper_execution_harness_authority_for_test() -> (
    _DisposableFirstPaperExecutionHarnessAuthorityForTest
):
    """Issue one private authority for an injected source-only test."""

    return _DisposableFirstPaperExecutionHarnessAuthorityForTest(
        _issuer=_DISPOSABLE_TEST_ISSUER
    )


def _run_after_gate_preflight_for_test(
    *,
    authority: _DisposableFirstPaperExecutionHarnessAuthorityForTest,
    publication_preflight: Callable[[], None],
    history_seed_loader: Callable[[], VerifiedStrategyHistorySeed],
    authority_loader: Callable[[], object],
    selected_reader_factory: _SelectedReaderFactory,
    supervised_executor: _ExecutionBoundary,
) -> int:
    """Run only injected post-gate orchestration without production authority."""

    if type(authority) is not _DisposableFirstPaperExecutionHarnessAuthorityForTest:
        raise TypeError("disposable harness authority is invalid")
    if (
        publication_preflight is _require_frozen_publication
        or history_seed_loader is _load_frozen_history_seed
        or authority_loader is acquire_validated_production_authority
        or selected_reader_factory is WindowsSelectedC3SnapshotReadAuthority
        or supervised_executor is execute_supervised_personal_desktop_paper_operation
    ):
        raise TypeError("disposable harness seam requires injected no-effect callables")
    authority._consume()
    return _run_after_gate_preflight(
        publication_preflight=publication_preflight,
        history_seed_loader=history_seed_loader,
        authority_loader=authority_loader,
        selected_reader_factory=selected_reader_factory,
        supervised_executor=supervised_executor,
        _issuer=_DISPOSABLE_TEST_ISSUER,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the zero-semantic first-paper harness exactly once when enabled."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        return _blocked("INVALID_ARGUMENTS", _EXIT_INVALID_ARGUMENTS)

    gate_failure = _gate_preflight_failure(
        paper_security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        paper_security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        execution_boundary.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
    )
    if gate_failure is not None:
        return _blocked(*gate_failure)

    return _run_after_gate_preflight(
        publication_preflight=_require_frozen_publication,
        history_seed_loader=_load_frozen_history_seed,
        authority_loader=acquire_validated_production_authority,
        selected_reader_factory=WindowsSelectedC3SnapshotReadAuthority,
        supervised_executor=execute_supervised_personal_desktop_paper_operation,
        _issuer=_PRODUCTION_ISSUER,
    )


if __name__ == "__main__":
    raise SystemExit(main())
