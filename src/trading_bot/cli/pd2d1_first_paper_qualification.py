"""One-shot read-only PD2D1 qualification for the frozen first paper cycle."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
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
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as pd2c,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
    WindowsSelectedC3SnapshotReadAuthority,
)
from trading_bot.runtime.personal_desktop_supervised_paper_operation_qualification import (  # noqa: E501
    SupervisedPaperOperationQualificationResult,
    SupervisedPaperOperationQualificationStatus,
    qualify_supervised_personal_desktop_paper_operation,
)
from trading_bot.runtime.strategy_history_seed import (
    VerifiedStrategyHistorySeed,
    verify_strategy_history_seed,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    acquire_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_SCHEMA = "pd2d1-first-paper-qualification-evidence/v1"
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
_EXPECTED_GENESIS_SHA256 = (
    "d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548"
)
_EXPECTED_GENESIS_BYTE_LENGTH = 533
_EXPECTED_GENESIS_AS_OF = datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC)

_EXIT_USAGE = 2
_EXIT_PREFLIGHT = 3
_EXIT_AUTHORITY = 4
_EXIT_SELECTED_SNAPSHOT = 5
_EXIT_QUALIFICATION = 6
_EXIT_RECONCILIATION = 7
_EXIT_NOT_READY = 8


class _CliUsageError(ValueError):
    pass


class _HarnessReconciliationError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid PD2D1 qualification arguments")


@dataclass(frozen=True, slots=True)
class _FrozenQualificationInputs:
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
        prog="qualify_first_personal_desktop_paper_operation",
        description="Inspect the frozen first Paper-v2 operation read-only.",
    )


def _require_all_effect_gates_false() -> None:
    supervised_execution_gate = (
        pd2c.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
    )
    if (
        paper_security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False
        or paper_security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED
        is not False
        or supervised_execution_gate is not False
    ):
        raise _HarnessReconciliationError(
            "all Paper-v2 effect gates must remain exactly false"
        )


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
    ):
        raise _HarnessReconciliationError(
            "Paper-v2 publication freeze differs from the first-cycle profile"
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
) -> _FrozenQualificationInputs:
    return _FrozenQualificationInputs(
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
        planning_at=_EXPECTED_GENESIS_AS_OF,
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
            "current production authority differs from the frozen identity"
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


def _reconcile_qualification(
    result: SupervisedPaperOperationQualificationResult,
) -> None:
    if type(result) is not SupervisedPaperOperationQualificationResult:
        raise _HarnessReconciliationError(
            "qualification returned an invalid result type"
        )
    if (
        result.paper_account_id != _EXPECTED_PAPER_ACCOUNT_ID
        or result.terminal_checkpoint_id != _EXPECTED_TERMINAL_CHECKPOINT_ID
    ):
        raise _HarnessReconciliationError(
            "qualification account or terminal differs from frozen GENESIS"
        )


def _evidence_record(
    authority: ValidatedProductionAuthority,
    selected_snapshot: SelectedC3SnapshotReadResult,
    inputs: _FrozenQualificationInputs,
    result: SupervisedPaperOperationQualificationResult,
) -> dict[str, object]:
    return {
        "all_effect_gates_false": True,
        "application_id": str(result.application_id),
        "authority_epoch_id": authority.authority_epoch_id,
        "inspection_classification": result.inspection_classification.value,
        "inspection_diagnostic": result.inspection_diagnostic.value,
        "machine_authority_id": authority.machine_authority_id,
        "open_reference_price": str(
            inputs.open_reference.caller_asserted_open_reference_price
        ),
        "open_reference_session": (
            inputs.open_reference.session.session_date.isoformat()
        ),
        "open_reference_symbol": str(inputs.open_reference.symbol),
        "operation_id": str(result.operation_id),
        "paper_account_id": result.paper_account_id,
        "plan_id": str(result.plan_id),
        "qualification_status": result.qualification_status.value,
        "schema": _SCHEMA,
        "seed_byte_length": inputs.history_seed.artifact_byte_length,
        "seed_id": str(inputs.history_seed.seed.seed_id),
        "seed_sha256": inputs.history_seed.artifact_sha256,
        "selected_snapshot_id": str(selected_snapshot.audit.snapshot_id),
        "selection_id": str(selected_snapshot.audit.selection_id),
        "terminal_checkpoint_id": str(result.terminal_checkpoint_id),
    }


def _emit(record: dict[str, object], *, stream: object | None = None) -> None:
    destination = sys.stdout if stream is None else stream
    print(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=destination,
    )


def _blocked(reason: str, exit_code: int) -> int:
    _emit({"reason": reason, "schema": _SCHEMA}, stream=sys.stderr)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    """Run one frozen read-only qualification with no caller semantic inputs."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        return _blocked("INVALID_ARGUMENTS", _EXIT_USAGE)

    try:
        _require_all_effect_gates_false()
        _require_frozen_publication()
        history_seed = _load_frozen_history_seed()
        inputs = _frozen_inputs(history_seed)
    except Exception:
        return _blocked("PREFLIGHT_BLOCKED", _EXIT_PREFLIGHT)

    try:
        authority = acquire_validated_production_authority()
        _reconcile_authority(authority)
    except _HarnessReconciliationError:
        return _blocked("AUTHORITY_IDENTITY_MISMATCH", _EXIT_RECONCILIATION)
    except Exception:
        return _blocked("PRODUCTION_AUTHORITY_BLOCKED", _EXIT_AUTHORITY)

    try:
        selected_reader = WindowsSelectedC3SnapshotReadAuthority(authority)
        selected_snapshot = selected_reader.read_selected_snapshot(
            str(_EXPECTED_SELECTION_ID)
        )
        _reconcile_selected_snapshot(selected_snapshot)
    except _HarnessReconciliationError:
        return _blocked("SELECTED_SNAPSHOT_MISMATCH", _EXIT_RECONCILIATION)
    except Exception:
        return _blocked("SELECTED_SNAPSHOT_BLOCKED", _EXIT_SELECTED_SNAPSHOT)

    try:
        result = qualify_supervised_personal_desktop_paper_operation(
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
    except Exception:
        return _blocked("QUALIFICATION_BLOCKED", _EXIT_QUALIFICATION)

    try:
        _require_all_effect_gates_false()
        _reconcile_qualification(result)
    except Exception:
        return _blocked("QUALIFICATION_RECONCILIATION_BLOCKED", _EXIT_RECONCILIATION)

    _emit(_evidence_record(authority, selected_snapshot, inputs, result))
    if (
        result.inspection_classification.value == "PENDING"
        and result.inspection_diagnostic.value == "PENDING"
        and result.qualification_status
        is SupervisedPaperOperationQualificationStatus.READY
    ):
        return 0
    return _EXIT_NOT_READY


if __name__ == "__main__":
    raise SystemExit(main())
