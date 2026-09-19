"""One-shot read-only isolation through active PD2B3 preparation."""

from __future__ import annotations

import argparse
import ast
import ctypes
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import NoReturn
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailyMarketDataSnapshot,
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
from trading_bot.runtime.exceptions import VerifiedSnapshotPaperCyclePreparationError
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadError,
    SelectedC3SnapshotReadResult,
    WindowsSelectedC3SnapshotReadAuthority,
)
from trading_bot.runtime.manual_paper_strategy_plan import ManualPaperStrategyPlanError
from trading_bot.runtime.paper_operation import PaperOperationError
from trading_bot.runtime.paper_operation_execution_inputs import (
    PaperOperationExecutionInputsError,
    VerifiedPaperOperationExecutionInputs,
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
)
from trading_bot.runtime.personal_desktop_supervised_paper_operation_preparation import (  # noqa: E501
    SupervisedPaperOperationPreparationError,
    _require_active_prepared_paper_operation_binding,
    supervised_personal_desktop_paper_operation_preparation,
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
    ValidatedProductionAuthority,
    acquire_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_SCHEMA = "pd2d1-preparation-readonly-diagnostic/v1"
_EXPECTED_MACHINE_AUTHORITY_ID = "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1"
_EXPECTED_AUTHORITY_EPOCH_ID = "e6f3de5d-1412-40ad-a022-8b33e72a5f6d"
_EXPECTED_TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"
_EXPECTED_PAPER_ACCOUNT_ID = "9415cd7b-bf36-5fba-bd58-a0f99119dc21"
_EXPECTED_TERMINAL_CHECKPOINT_ID = UUID("1832a2b5-8b63-501a-8f7d-f1722c32307b")
_EXPECTED_SELECTION_ID = UUID("36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280")
_EXPECTED_SELECTED_SNAPSHOT_ID = UUID("eba46838-44ae-5bec-97bf-98c6639ae6a7")
_EXPECTED_SELECTED_SHA256 = (
    "31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d"
)
_EXPECTED_SELECTED_BYTE_LENGTH = 1291
_EXPECTED_SEED_ID = UUID("5dc95e10-ba22-5b91-94b2-0d851aa8e2d7")
_EXPECTED_SEED_SHA256 = (
    "40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64"
)
_EXPECTED_SEED_BYTE_LENGTH = 1060
_EXPECTED_SEED_PATH = Path(
    r"F:\AI\worktrees\ai-trading-bot-personal-desktop"
    r"\docs\validation\evidence"
    r"\pd2d1-spy-strategy-history-seed-2026-08-28.json"
)
_EXPECTED_TARGET_SESSION = TradingSession(date(2026, 8, 28))
_EXPECTED_OPEN_SESSION = TradingSession(date(2026, 8, 31))
_EXPECTED_SYMBOL = Symbol("SPY")
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
_EXIT_P2 = 5
_EXIT_PREPARATION_CONSTRUCTION = 6
_EXIT_PREPARATION_ENTER = 7
_EXIT_ACTIVE_RECONCILIATION = 8
_EXIT_PREPARATION_RELEASE = 9

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
        raise _CliUsageError("invalid PD2D1 preparation diagnostic arguments")


@dataclass(frozen=True, slots=True)
class _FrozenPreparationInputs:
    history_seed: VerifiedStrategyHistorySeed
    strategy_config: MovingAverageCrossoverConfig
    caller_idempotency_key: UUID
    open_reference: CallerAssertedNextSessionOpenReference
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime


def build_parser() -> argparse.ArgumentParser:
    """Build the zero-semantic-input one-shot parser."""

    return _SanitizedArgumentParser(
        prog="diagnose_pd2d1_preparation_readonly",
        description="Isolate the frozen first cycle through active PD2B3 only.",
    )


def _require_all_effect_gates_false() -> None:
    if (
        paper_security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False
        or paper_security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED
        is not False
        or not _supervised_execution_gate_is_source_false()
    ):
        raise _HarnessReconciliationError(
            "all Paper-v2 effect gates must remain exactly false"
        )


def _supervised_execution_gate_is_source_false() -> bool:
    """Check the PD2C source gate without importing its executor module."""

    source_path = (
        Path(__file__).resolve().parents[1]
        / "runtime"
        / "personal_desktop_supervised_paper_operation_execution.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id
            == "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED"
            for target in node.targets
        )
    ]
    return (
        len(assignments) == 1
        and isinstance(assignments[0].value, ast.Constant)
        and assignments[0].value.value is False
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


def _read_frozen_seed_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _frozen_strategy_config() -> MovingAverageCrossoverConfig:
    return MovingAverageCrossoverConfig(3, 5, Decimal("1"))


def _load_frozen_history_seed() -> VerifiedStrategyHistorySeed:
    path = _resolve_frozen_seed_path()
    payload = _read_frozen_seed_bytes(path)
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


def _frozen_inputs(
    history_seed: VerifiedStrategyHistorySeed,
) -> _FrozenPreparationInputs:
    # These are the accepted F3 helper values. Importing that CLI module here would
    # transitively import the Architecture-67 qualifier/inspector this diagnostic
    # must stop before, so the frozen construction remains local and source-checked.
    return _FrozenPreparationInputs(
        history_seed=history_seed,
        strategy_config=_frozen_strategy_config(),
        caller_idempotency_key=UUID("c762ad22-8d10-43d7-a38b-7d95e730c5ea"),
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
        planning_at=datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC),
        submitted_at=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
        filled_at=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
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


def _reconcile_selected_snapshot(result: SelectedC3SnapshotReadResult) -> None:
    if type(result) is not SelectedC3SnapshotReadResult:
        raise _HarnessReconciliationError("P2 returned an invalid result type")
    snapshot = result.verification.snapshot
    if type(snapshot) is not DailyMarketDataSnapshot:
        raise _HarnessReconciliationError("P2 returned no exact verified snapshot")
    if (
        result.audit.selection_id != _EXPECTED_SELECTION_ID
        or result.audit.snapshot_id != _EXPECTED_SELECTED_SNAPSHOT_ID
        or result.audit.artifact_sha256 != _EXPECTED_SELECTED_SHA256
        or result.audit.artifact_byte_length != _EXPECTED_SELECTED_BYTE_LENGTH
        or len(result.snapshot_bytes) != _EXPECTED_SELECTED_BYTE_LENGTH
        or sha256(result.snapshot_bytes).hexdigest() != _EXPECTED_SELECTED_SHA256
        or snapshot.snapshot_id != _EXPECTED_SELECTED_SNAPSHOT_ID
        or snapshot.target_session != _EXPECTED_TARGET_SESSION
        or snapshot.request.symbols != (_EXPECTED_SYMBOL,)
        or tuple(item.bar.symbol for item in snapshot.bars) != (_EXPECTED_SYMBOL,)
    ):
        raise _HarnessReconciliationError(
            "P2 selected snapshot differs from frozen call number six"
        )


def _active_preparation_record(
    authority: ValidatedProductionAuthority,
    selected_snapshot: SelectedC3SnapshotReadResult,
    inputs: _FrozenPreparationInputs,
    preparation: object,
    active: object,
) -> dict[str, object]:
    _require_all_effect_gates_false()
    if active is not preparation:
        raise _HarnessReconciliationError("preparation did not return itself")

    paper_account_id = active.paper_account_id
    plan_id = active.plan_id
    operation_id = active.operation_id
    application_id = active.application_id
    selected_snapshot_id = active.selected_snapshot_id
    plan_artifact_sha256 = active.plan_artifact_sha256
    plan_artifact_byte_length = active.plan_artifact_byte_length
    mutex_state = active.mutex_acquisition_state
    if (
        type(paper_account_id) is not str
        or paper_account_id != _EXPECTED_PAPER_ACCOUNT_ID
        or type(selected_snapshot_id) is not UUID
        or selected_snapshot_id != _EXPECTED_SELECTED_SNAPSHOT_ID
        or mutex_state is not PaperAccountMutexState.OWNED
        or type(plan_id) is not UUID
        or type(operation_id) is not UUID
        or type(application_id) is not UUID
        or type(plan_artifact_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", plan_artifact_sha256) is None
        or type(plan_artifact_byte_length) is not int
        or plan_artifact_byte_length <= 0
    ):
        raise _HarnessReconciliationError("active preparation evidence differs")

    binding = _require_active_prepared_paper_operation_binding(active)
    execution_inputs = binding.execution_inputs
    if (
        type(binding.operation_root) is not str
        or binding.operation_root != _EXPECTED_OPERATION_ROOT
        or type(execution_inputs) is not VerifiedPaperOperationExecutionInputs
        or execution_inputs.intent.operation_id != operation_id
        or execution_inputs.application_id != application_id
        or execution_inputs.verified_prior.checkpoint_id
        != _EXPECTED_TERMINAL_CHECKPOINT_ID
    ):
        raise _HarnessReconciliationError("active private binding differs")

    return {
        "active_binding_verified": True,
        "all_effect_gates_false": True,
        "application_id": str(application_id),
        "authority_epoch_id": authority.authority_epoch_id,
        "machine_authority_id": authority.machine_authority_id,
        "mutex_acquisition_state": "OWNED",
        "operation_id": str(operation_id),
        "operation_root_matches": True,
        "paper_account_id": paper_account_id,
        "plan_id": str(plan_id),
        "result": "PREPARATION_READY",
        "schema": _SCHEMA,
        "seed_id": str(inputs.history_seed.seed.seed_id),
        "selected_snapshot_id": str(selected_snapshot.audit.snapshot_id),
        "selection_id": str(selected_snapshot.audit.selection_id),
        "terminal_checkpoint_id": str(_EXPECTED_TERMINAL_CHECKPOINT_ID),
    }


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
    elif isinstance(error, SupervisedPaperOperationPreparationError):
        family = "SUPERVISED_PREPARATION_ERROR"
    elif isinstance(error, SupervisedPersonalDesktopPaperCycleError):
        family = "SUPERVISED_CYCLE_ERROR"
    elif isinstance(error, PersonalDesktopPaperAccountError):
        family = "PERSONAL_DESKTOP_PAPER_ACCOUNT_ERROR"
    elif isinstance(error, SelectedC3SnapshotReadError):
        family = "SELECTED_C3_SNAPSHOT_READ_ERROR"
    elif isinstance(error, ManualPaperStrategyPlanError):
        family = "MANUAL_PAPER_STRATEGY_PLAN_ERROR"
    elif isinstance(error, VerifiedSnapshotPaperCyclePreparationError):
        family = "VERIFIED_CYCLE_PREPARATION_ERROR"
    elif isinstance(error, PaperOperationError):
        family = "PAPER_OPERATION_ERROR"
    elif isinstance(error, PaperOperationExecutionInputsError):
        family = "PAPER_OPERATION_EXECUTION_INPUTS_ERROR"
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


def _release(preparation: object) -> Exception | None:
    try:
        preparation.__exit__(None, None, None)
    except Exception as error:
        return error
    return None


def main(argv: list[str] | None = None) -> int:
    """Run the frozen preparation-only diagnostic exactly once."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        return _blocked("INVALID_ARGUMENTS", _EXIT_USAGE)

    try:
        _require_all_effect_gates_false()
        _require_frozen_publication()
        history_seed = _load_frozen_history_seed()
        inputs = _frozen_inputs(history_seed)
    except Exception as error:
        return _blocked("PREFLIGHT_BLOCKED", _EXIT_PREFLIGHT, error=error)

    try:
        authority = acquire_validated_production_authority()
        _reconcile_authority(authority)
    except Exception as error:
        return _blocked("C1_BLOCKED", _EXIT_C1, error=error)

    try:
        reader = WindowsSelectedC3SnapshotReadAuthority(authority)
        selected_snapshot = reader.read_selected_snapshot(str(_EXPECTED_SELECTION_ID))
        _reconcile_selected_snapshot(selected_snapshot)
    except Exception as error:
        return _blocked("P2_BLOCKED", _EXIT_P2, error=error)

    try:
        preparation = supervised_personal_desktop_paper_operation_preparation(
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
        return _blocked(
            "PREPARATION_CONSTRUCTION_BLOCKED",
            _EXIT_PREPARATION_CONSTRUCTION,
            error=error,
        )

    try:
        active = preparation.__enter__()
    except Exception as error:
        return _blocked(
            "PREPARATION_ENTER_BLOCKED", _EXIT_PREPARATION_ENTER, error=error
        )

    primary_record: dict[str, object] | None = None
    success_record: dict[str, object] | None = None
    pending_base_exception: BaseException | None = None
    try:
        try:
            success_record = _active_preparation_record(
                authority,
                selected_snapshot,
                inputs,
                preparation,
                active,
            )
        except Exception as error:
            primary_record = _exception_record(
                "ACTIVE_PREPARATION_RECONCILIATION_BLOCKED", error
            )
    except BaseException as error:
        pending_base_exception = error

    release_error = _release(preparation)
    if release_error is not None:
        return _blocked(
            "PREPARATION_RELEASE_BLOCKED",
            _EXIT_PREPARATION_RELEASE,
            error=release_error,
        )
    if pending_base_exception is not None:
        raise pending_base_exception.with_traceback(
            pending_base_exception.__traceback__
        )
    if primary_record is not None:
        _emit(primary_record, stream=sys.stderr)
        return _EXIT_ACTIVE_RECONCILIATION
    if success_record is None:
        return _blocked(
            "ACTIVE_PREPARATION_RECONCILIATION_BLOCKED",
            _EXIT_ACTIVE_RECONCILIATION,
        )

    _emit(success_record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
