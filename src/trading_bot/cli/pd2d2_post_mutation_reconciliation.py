"""Read-only reconciliation of the successful first personal-desktop operation."""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import UUID

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    inspect_paper_operation_root,
)
from trading_bot.domain import Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
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
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    parse_checkpointed_paper_cycle_report,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    derive_checkpointed_verified_snapshot_application_id,
    verified_prior_from_full_lineage,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    WindowsSelectedC3SnapshotReadAuthority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyPlanRequest,
    build_manual_paper_strategy_plan,
    verify_manual_paper_strategy_plan,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpointVerificationStatus,
    verify_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    parse_successor_paper_account_checkpoint,
)
from trading_bot.runtime.paper_operation import (
    PaperOperationArtifactEvidence,
    PaperOperationStatus,
    create_paper_operation_intent,
)
from trading_bot.runtime.paper_operation_execution_inputs import (
    VerifiedPaperOperationExecutionInputs,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    parse_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_provisioning import (
    prepare_personal_desktop_paper_account_bundle,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    read_personal_desktop_paper_account,
    require_validated_personal_desktop_paper_account,
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
    acquire_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_SCHEMA = "pd2d2-post-mutation-reconciliation-evidence/v1"
_PROFILE = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE
_EXPECTED_MACHINE_AUTHORITY_ID = "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1"
_EXPECTED_AUTHORITY_EPOCH_ID = "e6f3de5d-1412-40ad-a022-8b33e72a5f6d"
_EXPECTED_TRADING_SID = _PROFILE.approved_trading_sid
_EXPECTED_PAPER_ACCOUNT_ID = _PROFILE.paper_account_id
_EXPECTED_GENESIS_ID = _PROFILE.terminal_checkpoint_id
_EXPECTED_TERMINAL_ID = UUID("ed4640e5-0630-525d-b916-d50e31e3ba2a")
_EXPECTED_SELECTION_ID = UUID("36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280")
_EXPECTED_SELECTED_SNAPSHOT_ID = _PROFILE.selected_snapshot_id
_EXPECTED_SELECTED_SHA256 = (
    "31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d"
)
_EXPECTED_SELECTED_BYTE_LENGTH = 1291
_EXPECTED_SEED_ID = UUID("5dc95e10-ba22-5b91-94b2-0d851aa8e2d7")
_EXPECTED_SEED_SHA256 = (
    "40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64"
)
_EXPECTED_SEED_BYTE_LENGTH = 1060
_EXPECTED_CALLER_IDEMPOTENCY_KEY = _PROFILE.caller_idempotency_key
_EXPECTED_REQUEST_ID = _PROFILE.request_id
_EXPECTED_PLAN_ID = _PROFILE.plan_id
_EXPECTED_PLAN_SHA256 = _PROFILE.plan_sha256
_EXPECTED_PLAN_BYTE_LENGTH = _PROFILE.plan_byte_length
_EXPECTED_OPERATION_ID = _PROFILE.operation_id
_EXPECTED_APPLICATION_ID = _PROFILE.application_id
_EXPECTED_CYCLE_RESULT_ID = UUID("854f133e-d9cd-5a9d-be63-0eb4137787db")
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

_EXIT_USAGE = 2
_EXIT_GATE = 3
_EXIT_RECONCILIATION = 4

_PRODUCTION_ISSUER = object()
_DISPOSABLE_ISSUER = object()


class _CliUsageError(ValueError):
    pass


class _ReconciliationError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid reconciliation arguments")


class _Reader(Protocol):
    def read_selected_snapshot(self, selection_id: str) -> object: ...


@dataclass(frozen=True, slots=True)
class _FrozenInputs:
    history_seed: VerifiedStrategyHistorySeed
    strategy_config: MovingAverageCrossoverConfig
    caller_idempotency_key: UUID
    open_reference: CallerAssertedNextSessionOpenReference
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class _Dependencies:
    publication_preflight: Callable[[], None]
    history_seed_loader: Callable[[], object]
    authority_loader: Callable[[], object]
    selected_reader_factory: Callable[[object], _Reader]
    bundle_preparer: Callable[..., object]
    anchor_parser: Callable[[bytes], object]
    genesis_verifier: Callable[..., object]
    lineage_verifier: Callable[..., object]
    prior_deriver: Callable[[object], object]
    plan_builder: Callable[..., object]
    plan_verifier: Callable[..., object]
    account_reader: Callable[..., object]
    account_validator: Callable[[object], object]
    successor_parser: Callable[[bytes], object]
    report_parser: Callable[[bytes], object]
    intent_builder: Callable[..., object]
    application_id_deriver: Callable[..., object]
    execution_inputs_builder: Callable[..., object]
    inspector: Callable[..., object]


class _DisposableReconciliationAuthorityForTest:
    __slots__ = ("_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object) -> None:
        if _issuer is not _DISPOSABLE_ISSUER:
            raise TypeError("invalid disposable reconciliation authority")
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False

    def consume(self) -> None:
        with self._lock:
            if self._issuer is not _DISPOSABLE_ISSUER or self._used:
                raise TypeError(
                    "disposable reconciliation authority is invalid or used"
                )
            self._used = True


def build_parser() -> argparse.ArgumentParser:
    """Build a parser with no semantic arguments."""

    return _SanitizedArgumentParser(
        prog="reconcile_first_personal_desktop_paper_operation",
        description="Read back the frozen first Paper-v2 operation without effects.",
    )


def _gate_state_is_safe() -> bool:
    supervised_gate = execution_boundary.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED  # noqa: E501
    return (
        paper_security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
        and paper_security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
        and supervised_gate is False
    )


def _require_all_effect_gates_false() -> None:
    if not _gate_state_is_safe():
        raise _ReconciliationError("all Paper-v2 effect gates must be false")


def _require_frozen_publication() -> None:
    freeze = publication_freeze.require_production_paper_publication_freeze()
    observed = (
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
    expected = (
        _EXPECTED_MACHINE_AUTHORITY_ID,
        _EXPECTED_TRADING_SID,
        _EXPECTED_PAPER_ACCOUNT_ID,
        Decimal("25000"),
        _EXPECTED_GENESIS_AS_OF,
        _EXPECTED_GENESIS_SHA256,
        _EXPECTED_GENESIS_BYTE_LENGTH,
        _EXPECTED_ANCHOR_SHA256,
        _EXPECTED_ANCHOR_BYTE_LENGTH,
        _EXPECTED_MANIFEST_SHA256,
        _EXPECTED_MANIFEST_BYTE_LENGTH,
    )
    if observed != expected:
        raise _ReconciliationError("publication freeze differs from Architecture 108")


def _load_frozen_history_seed() -> VerifiedStrategyHistorySeed:
    path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "validation"
        / "evidence"
        / "pd2d1-spy-strategy-history-seed-2026-08-28.json"
    ).resolve(strict=True)
    if path != _EXPECTED_SEED_PATH:
        raise _ReconciliationError("strategy seed path differs from the freeze")
    payload = path.read_bytes()
    if (
        len(payload) != _EXPECTED_SEED_BYTE_LENGTH
        or sha256(payload).hexdigest() != _EXPECTED_SEED_SHA256
    ):
        raise _ReconciliationError("strategy seed bytes differ from the freeze")
    config = MovingAverageCrossoverConfig(3, 5, Decimal("1"))
    result = verify_strategy_history_seed(
        payload,
        expected_symbol=_EXPECTED_SYMBOL,
        target_session=_EXPECTED_TARGET_SESSION,
        strategy_config=config,
        calendar=_calendar(),
    )
    if (
        result.seed.seed_id != _EXPECTED_SEED_ID
        or result.artifact_sha256 != _EXPECTED_SEED_SHA256
        or result.artifact_byte_length != _EXPECTED_SEED_BYTE_LENGTH
    ):
        raise _ReconciliationError("strategy seed verification differs from the freeze")
    return result


def _calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _frozen_inputs(history_seed: VerifiedStrategyHistorySeed) -> _FrozenInputs:
    return _FrozenInputs(
        history_seed=history_seed,
        strategy_config=MovingAverageCrossoverConfig(3, 5, Decimal("1")),
        caller_idempotency_key=_EXPECTED_CALLER_IDEMPOTENCY_KEY,
        open_reference=CallerAssertedNextSessionOpenReference(
            _EXPECTED_SYMBOL, _EXPECTED_OPEN_SESSION, Decimal("767.33")
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
                slippage_basis_points=Decimal("0"), fixed_commission=Decimal("0")
            ),
            trading_enabled=True,
        ),
        planning_at=_EXPECTED_GENESIS_AS_OF,
        submitted_at=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
        filled_at=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
    )


def _require_authority(authority: object) -> None:
    if (
        getattr(authority, "machine_authority_id", None)
        != _EXPECTED_MACHINE_AUTHORITY_ID
        or getattr(authority, "authority_epoch_id", None)
        != _EXPECTED_AUTHORITY_EPOCH_ID
        or getattr(authority, "approved_account_sid", None) != _EXPECTED_TRADING_SID
    ):
        raise _ReconciliationError("production authority identity mismatch")


def _require_selected_snapshot(selected: object) -> None:
    try:
        audit = selected.audit
        payload = selected.snapshot_bytes
        snapshot = selected.verification.snapshot
        bars = tuple(item.bar.symbol for item in snapshot.bars)
    except (AttributeError, TypeError) as error:
        raise _ReconciliationError(
            "selected snapshot evidence is incomplete"
        ) from error
    if (
        audit.selection_id != _EXPECTED_SELECTION_ID
        or audit.snapshot_id != _EXPECTED_SELECTED_SNAPSHOT_ID
        or audit.artifact_sha256 != _EXPECTED_SELECTED_SHA256
        or audit.artifact_byte_length != _EXPECTED_SELECTED_BYTE_LENGTH
        or type(payload) is not bytes
        or sha256(payload).hexdigest() != _EXPECTED_SELECTED_SHA256
        or len(payload) != _EXPECTED_SELECTED_BYTE_LENGTH
        or snapshot.snapshot_id != _EXPECTED_SELECTED_SNAPSHOT_ID
        or snapshot.target_session != _EXPECTED_TARGET_SESSION
        or snapshot.request.symbols != (_EXPECTED_SYMBOL,)
        or bars != (_EXPECTED_SYMBOL,)
        or getattr(selected, "provider_call_performed", False) is not False
        or getattr(selected, "database_mutation_performed", False) is not False
    ):
        raise _ReconciliationError("selected snapshot differs from C3 call six")


def _require_genesis_bundle(
    bundle: object, anchor: object, verification: object
) -> object:
    try:
        checkpoint = verification.checkpoint
        state = checkpoint.account_state
        observed = (
            checkpoint.checkpoint_id,
            verification.checkpoint_sha256,
            verification.checkpoint_byte_length,
            bundle.genesis_bytes,
            sha256(bundle.anchor_bytes).hexdigest(),
            len(bundle.anchor_bytes),
            sha256(bundle.manifest_bytes).hexdigest(),
            len(bundle.manifest_bytes),
            state.as_of,
            state.cash,
            state.positions,
            state.realized_profit_loss,
            checkpoint.metadata,
            anchor.paper_account_id,
            anchor.machine_authority_id,
            anchor.approved_trading_sid,
            anchor.genesis_checkpoint_id,
            anchor.genesis_sha256,
            anchor.genesis_byte_length,
        )
    except AttributeError as error:
        raise _ReconciliationError(
            "reconstructed GENESIS evidence is incomplete"
        ) from error
    expected = (
        _EXPECTED_GENESIS_ID,
        _EXPECTED_GENESIS_SHA256,
        _EXPECTED_GENESIS_BYTE_LENGTH,
        bundle.genesis_bytes,
        _EXPECTED_ANCHOR_SHA256,
        _EXPECTED_ANCHOR_BYTE_LENGTH,
        _EXPECTED_MANIFEST_SHA256,
        _EXPECTED_MANIFEST_BYTE_LENGTH,
        _EXPECTED_GENESIS_AS_OF,
        Decimal("25000"),
        (),
        Decimal("0"),
        (),
        _EXPECTED_PAPER_ACCOUNT_ID,
        _EXPECTED_MACHINE_AUTHORITY_ID,
        _EXPECTED_TRADING_SID,
        str(_EXPECTED_GENESIS_ID),
        _EXPECTED_GENESIS_SHA256,
        _EXPECTED_GENESIS_BYTE_LENGTH,
    )
    if (
        getattr(verification, "status", None)
        is not PaperAccountCheckpointVerificationStatus.PASS
        or getattr(verification, "diagnostics", None) != ()
        or observed != expected
        or sha256(bundle.genesis_bytes).hexdigest() != _EXPECTED_GENESIS_SHA256
        or len(bundle.genesis_bytes) != _EXPECTED_GENESIS_BYTE_LENGTH
    ):
        raise _ReconciliationError("reconstructed GENESIS differs from the freeze")
    return checkpoint


def _artifact_evidence(artifact: object) -> PaperAccountLineageArtifactEvidence:
    return PaperAccountLineageArtifactEvidence(
        artifact.kind,
        artifact.artifact_id,
        artifact.sha256,
        artifact.byte_length,
    )


def _require_plan(
    plan: object, replayed: object, prior: object, selected: object
) -> None:
    try:
        observed = (
            plan.plan.plan_id,
            plan.checkpointed_request.request_id,
            plan.artifact_sha256,
            plan.artifact_byte_length,
            len(plan.artifact_bytes),
            sha256(plan.artifact_bytes).hexdigest(),
            plan.plan.caller_idempotency_key,
            plan.plan.selected_c3_assertion.selection_id,
            plan.plan.selected_c3_assertion.snapshot_id,
            plan.plan.prior_checkpoint.checkpoint_id,
        )
    except AttributeError as error:
        raise _ReconciliationError(
            "reconstructed plan evidence is incomplete"
        ) from error
    expected = (
        _EXPECTED_PLAN_ID,
        _EXPECTED_REQUEST_ID,
        _EXPECTED_PLAN_SHA256,
        _EXPECTED_PLAN_BYTE_LENGTH,
        _EXPECTED_PLAN_BYTE_LENGTH,
        _EXPECTED_PLAN_SHA256,
        str(_EXPECTED_CALLER_IDEMPOTENCY_KEY),
        _EXPECTED_SELECTION_ID,
        _EXPECTED_SELECTED_SNAPSHOT_ID,
        _EXPECTED_GENESIS_ID,
    )
    if (
        plan != replayed
        or observed != expected
        or getattr(prior, "checkpoint_id", None) != _EXPECTED_GENESIS_ID
        or getattr(selected.audit, "snapshot_id", None)
        != _EXPECTED_SELECTED_SNAPSHOT_ID
    ):
        raise _ReconciliationError("reconstructed plan differs from the freeze")


def _require_account(
    evidence: object, genesis: object, selected: object
) -> tuple[object, object, object]:
    try:
        successor_artifact = evidence.successors[0]
        report_artifact = evidence.reports[0]
        snapshot_artifact = evidence.snapshots[0]
        receipt = evidence.receipts[0]
        lineage = evidence.lineage
    except (AttributeError, IndexError) as error:
        raise _ReconciliationError(
            "installed account evidence is incomplete"
        ) from error
    if (
        evidence.anchor.paper_account_id != _EXPECTED_PAPER_ACCOUNT_ID
        or evidence.genesis != genesis
        or lineage.edge_count != 1
        or lineage.checkpoint_ids != (_EXPECTED_GENESIS_ID, _EXPECTED_TERMINAL_ID)
        or lineage.application_ids != (_EXPECTED_APPLICATION_ID,)
        or lineage.cycle_result_ids != (_EXPECTED_CYCLE_RESULT_ID,)
        or lineage.snapshot_ids != (_EXPECTED_SELECTED_SNAPSHOT_ID,)
        or lineage.terminal_checkpoint_id != _EXPECTED_TERMINAL_ID
        or evidence.prior_checkpoint.checkpoint_id != _EXPECTED_TERMINAL_ID
        or len(evidence.successors) != 1
        or len(evidence.reports) != 1
        or len(evidence.snapshots) != 1
        or len(evidence.receipts) != 1
        or snapshot_artifact.artifact_id != _EXPECTED_SELECTED_SNAPSHOT_ID
        or snapshot_artifact.payload != selected.snapshot_bytes
    ):
        raise _ReconciliationError("installed account inventory differs from one edge")
    return successor_artifact, report_artifact, receipt


def _require_transition(successor: object, report: object, selected: object) -> None:
    reference = report.evidence.request.snapshot_reference
    if (
        successor.checkpoint_id != _EXPECTED_TERMINAL_ID
        or successor.prior_checkpoint.checkpoint_id != _EXPECTED_GENESIS_ID
        or successor.application_id != _EXPECTED_APPLICATION_ID
        or successor.sequence != 1
        or report.evidence.application_id != _EXPECTED_APPLICATION_ID
        or report.evidence.cycle_result_id != _EXPECTED_CYCLE_RESULT_ID
        or reference.snapshot_id != _EXPECTED_SELECTED_SNAPSHOT_ID
        or reference.artifact_sha256 != selected.audit.artifact_sha256
        or reference.artifact_byte_length != selected.audit.artifact_byte_length
    ):
        raise _ReconciliationError("installed transition differs from frozen success")


def _require_receipt(
    receipt: object, prior_lineage: object, plan: object, selected: object
) -> None:
    intent = receipt.intent
    if (
        receipt.receipt_id != _EXPECTED_OPERATION_ID
        or intent.operation_id != _EXPECTED_OPERATION_ID
        or receipt.application_id != _EXPECTED_APPLICATION_ID
        or receipt.status is not PaperOperationStatus.COMPLETED
        or intent.caller_idempotency_key != _EXPECTED_CALLER_IDEMPOTENCY_KEY
        or intent.request != plan.checkpointed_request
        or intent.request.request_id != _EXPECTED_REQUEST_ID
        or intent.prior_lineage_evidence != prior_lineage
        or receipt.prior_lineage_evidence != prior_lineage
        or intent.terminal_checkpoint_artifact.artifact_id != _EXPECTED_GENESIS_ID
        or intent.completed_snapshot_artifact.artifact_id
        != _EXPECTED_SELECTED_SNAPSHOT_ID
        or intent.completed_snapshot_artifact.sha256 != selected.audit.artifact_sha256
        or intent.completed_snapshot_artifact.byte_length
        != selected.audit.artifact_byte_length
        or intent.cycle_configuration_artifact.sha256 != _EXPECTED_PLAN_SHA256
        or intent.cycle_configuration_artifact.byte_length != _EXPECTED_PLAN_BYTE_LENGTH
        or receipt.cycle_result_id != _EXPECTED_CYCLE_RESULT_ID
        or receipt.successor_checkpoint_artifact.artifact_id != _EXPECTED_TERMINAL_ID
    ):
        raise _ReconciliationError("installed receipt differs from frozen operation")


def _success_record(
    evidence: object, receipt: object, plan: object
) -> dict[str, object]:
    state = evidence.lineage.terminal_compact_state
    return {
        "account_cash": str(state.cash),
        "all_effect_gates_false": True,
        "application_id": str(_EXPECTED_APPLICATION_ID),
        "cycle_result_id": str(_EXPECTED_CYCLE_RESULT_ID),
        "genesis_checkpoint_id": str(_EXPECTED_GENESIS_ID),
        "inspection_classification": "ALREADY_APPLIED",
        "inspection_diagnostic": "ALREADY_APPLIED",
        "lineage_edge_count": 1,
        "operation_id": str(_EXPECTED_OPERATION_ID),
        "paper_account_id": _EXPECTED_PAPER_ACCOUNT_ID,
        "plan_byte_length": plan.artifact_byte_length,
        "plan_id": str(plan.plan.plan_id),
        "plan_sha256": plan.artifact_sha256,
        "position_count": len(state.positions),
        "receipt_outcome": receipt.outcome.value,
        "receipt_status": receipt.status.value,
        "result": "RECONCILED",
        "schema": _SCHEMA,
        "selected_snapshot_id": str(_EXPECTED_SELECTED_SNAPSHOT_ID),
        "selection_id": str(_EXPECTED_SELECTION_ID),
        "successor_checkpoint_id": str(_EXPECTED_TERMINAL_ID),
        "terminal_checkpoint_id": str(_EXPECTED_TERMINAL_ID),
    }


def _run(deps: _Dependencies, *, _issuer: object) -> dict[str, object]:
    if _issuer is not _PRODUCTION_ISSUER and _issuer is not _DISPOSABLE_ISSUER:
        raise TypeError("reconciliation issuer is invalid")
    _require_all_effect_gates_false()
    deps.publication_preflight()
    history_seed = deps.history_seed_loader()
    frozen = _frozen_inputs(history_seed)
    authority = deps.authority_loader()
    _require_authority(authority)
    selected = deps.selected_reader_factory(authority).read_selected_snapshot(
        str(_EXPECTED_SELECTION_ID)
    )
    _require_selected_snapshot(selected)

    bundle = deps.bundle_preparer(
        authority=authority,
        selected_snapshot=selected,
        starting_cash=Decimal("25000"),
    )
    anchor = deps.anchor_parser(bundle.anchor_bytes)
    genesis_verification = deps.genesis_verifier(
        bundle.genesis_bytes,
        expected_checkpoint_sha256=_EXPECTED_GENESIS_SHA256,
        expected_checkpoint_byte_length=_EXPECTED_GENESIS_BYTE_LENGTH,
    )
    _require_genesis_bundle(bundle, anchor, genesis_verification)
    genesis = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        _EXPECTED_GENESIS_ID,
        bundle.genesis_bytes,
        _EXPECTED_GENESIS_SHA256,
        _EXPECTED_GENESIS_BYTE_LENGTH,
    )
    calendar = _calendar()
    original_lineage = deps.lineage_verifier(
        genesis, _EXPECTED_GENESIS_ID, (), (), (), calendar
    )
    if (
        original_lineage.status is not PaperAccountLineageVerificationStatus.PASS
        or original_lineage.diagnostics != ()
        or original_lineage.evidence is None
        or original_lineage.evidence.edge_count != 0
        or original_lineage.evidence.checkpoint_ids != (_EXPECTED_GENESIS_ID,)
    ):
        raise _ReconciliationError("reconstructed GENESIS lineage did not verify")
    verified_prior = deps.prior_deriver(original_lineage)

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
        _EXPECTED_PAPER_ACCOUNT_ID,
        assertion,
        verified_prior,
        frozen.history_seed,
        frozen.strategy_config,
        str(frozen.caller_idempotency_key),
        frozen.open_reference,
        frozen.policies,
        frozen.planning_at,
        frozen.submitted_at,
        frozen.filled_at,
        (),
    )
    plan = deps.plan_builder(request, calendar)
    replayed = deps.plan_verifier(
        plan.artifact_bytes,
        calendar,
        expected_sha256=_EXPECTED_PLAN_SHA256,
        expected_byte_length=_EXPECTED_PLAN_BYTE_LENGTH,
        expected_checkpointed_request=plan.checkpointed_request,
    )
    _require_plan(plan, replayed, verified_prior, selected)

    account = deps.account_reader(
        authority, historical_cycle_configuration_payloads=(plan.artifact_bytes,)
    )
    evidence = deps.account_validator(account)
    successor_artifact, report_artifact, receipt = _require_account(
        evidence, genesis, selected
    )
    successor = deps.successor_parser(successor_artifact.payload)
    report = deps.report_parser(report_artifact.payload)
    _require_transition(successor, report, selected)
    _require_receipt(receipt, original_lineage.evidence, plan, selected)

    terminal_evidence = _artifact_evidence(genesis)
    snapshot_evidence = PaperAccountLineageArtifactEvidence(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        selected.audit.snapshot_id,
        selected.audit.artifact_sha256,
        selected.audit.artifact_byte_length,
    )
    configuration_evidence = PaperOperationArtifactEvidence(
        plan.artifact_sha256, plan.artifact_byte_length
    )
    rebuilt_intent = deps.intent_builder(
        _EXPECTED_CALLER_IDEMPOTENCY_KEY,
        original_lineage.evidence,
        terminal_evidence,
        snapshot_evidence,
        configuration_evidence,
        plan.checkpointed_request,
    )
    application_id = deps.application_id_deriver(
        _EXPECTED_GENESIS_ID, plan.checkpointed_request.request_id
    )
    if rebuilt_intent != receipt.intent or application_id != _EXPECTED_APPLICATION_ID:
        raise _ReconciliationError("original operation intent could not be rebuilt")
    execution_inputs = deps.execution_inputs_builder(
        receipt.intent,
        receipt.application_id,
        genesis,
        (),
        (),
        (),
        verified_prior,
        bundle.genesis_bytes,
        selected.snapshot_bytes,
        selected.verification,
        plan.artifact_bytes,
        plan.checkpointed_request,
        calendar,
    )
    inspection = deps.inspector(Path(_PROFILE.operation_root), execution_inputs)
    if (
        inspection.classification is not PaperOperationClassification.ALREADY_APPLIED
        or inspection.diagnostics != (PaperOperationInspectionCode.ALREADY_APPLIED,)
        or inspection.operation_id != _EXPECTED_OPERATION_ID
        or inspection.application_id != _EXPECTED_APPLICATION_ID
        or inspection.terminal_checkpoint_id != _EXPECTED_GENESIS_ID
    ):
        raise _ReconciliationError("A67 inspection is not exact ALREADY_APPLIED")

    second_account = deps.account_reader(
        authority, historical_cycle_configuration_payloads=(plan.artifact_bytes,)
    )
    second_evidence = deps.account_validator(second_account)
    if second_evidence != evidence:
        raise _ReconciliationError("account evidence drifted across A67 inspection")
    _require_all_effect_gates_false()
    return _success_record(second_evidence, receipt, plan)


def _production_dependencies() -> _Dependencies:
    return _Dependencies(
        _require_frozen_publication,
        _load_frozen_history_seed,
        acquire_validated_production_authority,
        WindowsSelectedC3SnapshotReadAuthority,
        prepare_personal_desktop_paper_account_bundle,
        parse_personal_desktop_paper_account_anchor,
        verify_genesis_paper_account_checkpoint,
        verify_paper_account_lineage,
        verified_prior_from_full_lineage,
        build_manual_paper_strategy_plan,
        verify_manual_paper_strategy_plan,
        read_personal_desktop_paper_account,
        require_validated_personal_desktop_paper_account,
        parse_successor_paper_account_checkpoint,
        parse_checkpointed_paper_cycle_report,
        create_paper_operation_intent,
        derive_checkpointed_verified_snapshot_application_id,
        VerifiedPaperOperationExecutionInputs,
        inspect_paper_operation_root,
    )


def _open_disposable_reconciliation_authority_for_test() -> (
    _DisposableReconciliationAuthorityForTest
):
    return _DisposableReconciliationAuthorityForTest(_issuer=_DISPOSABLE_ISSUER)


def _run_reconciliation_for_test(
    authority: _DisposableReconciliationAuthorityForTest,
    dependencies: _Dependencies,
) -> dict[str, object]:
    """Run a one-shot orchestration using only injected no-effect callables."""

    if type(authority) is not _DisposableReconciliationAuthorityForTest:
        raise TypeError("disposable reconciliation authority is invalid")
    production = _production_dependencies()
    genuine = {getattr(production, item.name) for item in fields(_Dependencies)}
    if any(
        getattr(dependencies, item.name) in genuine for item in fields(_Dependencies)
    ):
        raise TypeError("disposable reconciliation requires no-effect callables")
    authority.consume()
    return _run(dependencies, _issuer=_DISPOSABLE_ISSUER)


def _emit(record: dict[str, object], *, stream: object | None = None) -> None:
    print(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=sys.stdout if stream is None else stream,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the frozen, read-only post-mutation reconciliation."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        _emit({"reason": "INVALID_ARGUMENTS", "schema": _SCHEMA}, stream=sys.stderr)
        return _EXIT_USAGE
    if not _gate_state_is_safe():
        _emit(
            {"reason": "EFFECT_GATE_STATE_INVALID", "schema": _SCHEMA},
            stream=sys.stderr,
        )
        return _EXIT_GATE
    try:
        record = _run(_production_dependencies(), _issuer=_PRODUCTION_ISSUER)
    except Exception:
        _emit(
            {"reason": "RECONCILIATION_BLOCKED", "schema": _SCHEMA}, stream=sys.stderr
        )
        return _EXIT_RECONCILIATION
    _emit(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
