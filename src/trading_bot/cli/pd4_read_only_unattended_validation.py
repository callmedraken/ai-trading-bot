"""Read-only real-host acceptance for the frozen PD4-C startup qualifier."""

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
    personal_desktop_unattended_paper_startup_qualification as startup_qualification,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    verified_prior_from_full_lineage,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
    WindowsSelectedC3SnapshotReadAuthority,
    require_selected_c3_snapshot_matches_authority,
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
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
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
    require_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

type _PD4Result = (
    startup_qualification.PersonalDesktopUnattendedPaperStartupQualificationResult
)
_PD4_RESULT_TYPE = (
    startup_qualification.PersonalDesktopUnattendedPaperStartupQualificationResult
)
_SCHEMA = "pd4-read-only-unattended-validation-evidence/v1"
_PROFILE = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE
_EXPECTED_MACHINE_AUTHORITY_ID = "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1"
_EXPECTED_AUTHORITY_EPOCH_ID = "e6f3de5d-1412-40ad-a022-8b33e72a5f6d"
_EXPECTED_TRADING_SID = _PROFILE.approved_trading_sid
_EXPECTED_PAPER_ACCOUNT_ID = _PROFILE.paper_account_id
_EXPECTED_GENESIS_ID = _PROFILE.terminal_checkpoint_id
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

_EXIT_USAGE = 2
_EXIT_GATE = 3
_EXIT_VALIDATION = 4

_PRODUCTION_ISSUER = object()
_DISPOSABLE_ISSUER = object()


class _CliUsageError(ValueError):
    pass


class _ValidationError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid validation arguments")


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
class _EffectGateState:
    publication: bool
    provisioning_recovery: bool
    supervised_execution: bool
    receipt_recovery: bool
    unattended_execution: bool
    unattended_storage_provisioning: bool


@dataclass(frozen=True, slots=True)
class _Dependencies:
    publication_preflight: Callable[[], None]
    history_seed_loader: Callable[[], object]
    authority_loader: Callable[[], object]
    selected_reader_factory: Callable[[object], _Reader]
    provenance_validator: Callable[[object, object], None]
    bundle_preparer: Callable[..., object]
    anchor_parser: Callable[[bytes], object]
    genesis_verifier: Callable[..., object]
    lineage_verifier: Callable[..., object]
    prior_deriver: Callable[[object], object]
    plan_builder: Callable[..., object]
    plan_verifier: Callable[..., object]
    qualifier: Callable[..., object]
    gate_state: Callable[[], _EffectGateState]


class _DisposableValidationAuthorityForTest:
    __slots__ = ("_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object) -> None:
        if _issuer is not _DISPOSABLE_ISSUER:
            raise TypeError("invalid disposable validation authority")
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False

    def consume(self) -> None:
        with self._lock:
            if self._issuer is not _DISPOSABLE_ISSUER or self._used:
                raise TypeError("disposable validation authority is invalid or used")
            self._used = True


def build_parser() -> argparse.ArgumentParser:
    """Build the acceptance parser, which has no semantic arguments."""

    return _SanitizedArgumentParser(
        prog="validate_pd4_read_only_unattended",
        description="Validate the frozen PD4-C read-only unattended boundary.",
    )


def _effect_gate_state() -> _EffectGateState:
    from trading_bot.runtime import personal_desktop_paper_account_security as security
    from trading_bot.runtime import (
        personal_desktop_paper_receipt_recovery_execution as recovery,
    )
    from trading_bot.runtime import (
        personal_desktop_supervised_paper_operation_execution as supervised,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_operation_execution as unattended,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_storage_provisioning as provisioning,
    )

    return _EffectGateState(
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        supervised.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
        recovery.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        unattended.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
        provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )


def _all_effect_gates_are_closed(state: _EffectGateState | None = None) -> bool:
    observed = _effect_gate_state() if state is None else state
    return type(observed) is _EffectGateState and all(
        getattr(observed, item.name) is False for item in fields(_EffectGateState)
    )


def _require_all_effect_gates_false(deps: _Dependencies) -> None:
    if not _all_effect_gates_are_closed(deps.gate_state()):
        raise _ValidationError("all Paper-v2 effect gates must be false")


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
        raise _ValidationError("publication freeze differs from acceptance")


def _calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _load_frozen_history_seed() -> VerifiedStrategyHistorySeed:
    path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "validation"
        / "evidence"
        / "pd2d1-spy-strategy-history-seed-2026-08-28.json"
    ).resolve(strict=True)
    payload = path.read_bytes()
    if (
        len(payload) != _EXPECTED_SEED_BYTE_LENGTH
        or sha256(payload).hexdigest() != _EXPECTED_SEED_SHA256
    ):
        raise _ValidationError("strategy seed bytes differ from the freeze")
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
        raise _ValidationError("strategy seed verification differs from the freeze")
    return result


def _frozen_inputs(history_seed: VerifiedStrategyHistorySeed) -> _FrozenInputs:
    return _FrozenInputs(
        history_seed,
        MovingAverageCrossoverConfig(3, 5, Decimal("1")),
        _PROFILE.caller_idempotency_key,
        CallerAssertedNextSessionOpenReference(
            _EXPECTED_SYMBOL, _EXPECTED_OPEN_SESSION, Decimal("767.33")
        ),
        VerifiedSnapshotPaperCyclePolicies(
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
        _EXPECTED_GENESIS_AS_OF,
        datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
        datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
    )


def _require_authority(authority: object) -> None:
    if (
        getattr(authority, "machine_authority_id", None)
        != _EXPECTED_MACHINE_AUTHORITY_ID
        or getattr(authority, "authority_epoch_id", None)
        != _EXPECTED_AUTHORITY_EPOCH_ID
        or getattr(authority, "approved_account_sid", None) != _EXPECTED_TRADING_SID
    ):
        raise _ValidationError("production authority identity mismatch")


def _require_selected_snapshot(selected: object) -> None:
    try:
        audit = selected.audit
        payload = selected.snapshot_bytes
        snapshot = selected.verification.snapshot
        bars = tuple(item.bar.symbol for item in snapshot.bars)
    except (AttributeError, TypeError) as error:
        raise _ValidationError("selected snapshot evidence is incomplete") from error
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
        or getattr(selected, "provider_call_performed", None) is not False
        or getattr(selected, "database_mutation_performed", None) is not False
    ):
        raise _ValidationError("selected snapshot differs from C3 call six")


def _require_genuine_c1_p2(authority: object, selected: object) -> None:
    c1 = require_validated_production_authority(authority)
    if type(selected) is not SelectedC3SnapshotReadResult:
        raise _ValidationError("selected snapshot lacks exact P2 provenance")
    require_selected_c3_snapshot_matches_authority(selected.permit, selected.audit, c1)


def _require_genesis_bundle(
    bundle: object, anchor: object, verification: object
) -> PaperAccountLineageArtifact:
    try:
        checkpoint = verification.checkpoint
        state = checkpoint.account_state
        observed = (
            checkpoint.checkpoint_id,
            verification.checkpoint_sha256,
            verification.checkpoint_byte_length,
            sha256(bundle.genesis_bytes).hexdigest(),
            len(bundle.genesis_bytes),
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
        raise _ValidationError(
            "reconstructed GENESIS evidence is incomplete"
        ) from error
    expected = (
        _EXPECTED_GENESIS_ID,
        _EXPECTED_GENESIS_SHA256,
        _EXPECTED_GENESIS_BYTE_LENGTH,
        _EXPECTED_GENESIS_SHA256,
        _EXPECTED_GENESIS_BYTE_LENGTH,
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
    ):
        raise _ValidationError("reconstructed GENESIS differs from the freeze")
    return PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        _EXPECTED_GENESIS_ID,
        bundle.genesis_bytes,
        _EXPECTED_GENESIS_SHA256,
        _EXPECTED_GENESIS_BYTE_LENGTH,
    )


def _reconstruct_historical_plan(
    deps: _Dependencies,
    authority: object,
    selected: object,
    frozen: _FrozenInputs,
) -> bytes:
    bundle = deps.bundle_preparer(
        authority=authority,
        selected_snapshot=selected,
        starting_cash=Decimal("25000"),
    )
    genesis = _require_genesis_bundle(
        bundle,
        deps.anchor_parser(bundle.anchor_bytes),
        deps.genesis_verifier(
            bundle.genesis_bytes,
            expected_checkpoint_sha256=_EXPECTED_GENESIS_SHA256,
            expected_checkpoint_byte_length=_EXPECTED_GENESIS_BYTE_LENGTH,
        ),
    )
    calendar = _calendar()
    lineage = deps.lineage_verifier(genesis, _EXPECTED_GENESIS_ID, (), (), (), calendar)
    if (
        lineage.status is not PaperAccountLineageVerificationStatus.PASS
        or lineage.diagnostics != ()
        or lineage.evidence is None
        or lineage.evidence.edge_count != 0
        or lineage.evidence.checkpoint_ids != (_EXPECTED_GENESIS_ID,)
    ):
        raise _ValidationError("reconstructed GENESIS lineage did not verify")
    prior = deps.prior_deriver(lineage)
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
        prior,
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
        expected_sha256=_PROFILE.plan_sha256,
        expected_byte_length=_PROFILE.plan_byte_length,
        expected_checkpointed_request=plan.checkpointed_request,
    )
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
            prior.checkpoint_id,
        )
    except AttributeError as error:
        raise _ValidationError("reconstructed plan evidence is incomplete") from error
    expected = (
        _PROFILE.plan_id,
        _PROFILE.request_id,
        _PROFILE.plan_sha256,
        _PROFILE.plan_byte_length,
        _PROFILE.plan_byte_length,
        _PROFILE.plan_sha256,
        str(_PROFILE.caller_idempotency_key),
        _EXPECTED_SELECTION_ID,
        _EXPECTED_SELECTED_SNAPSHOT_ID,
        _EXPECTED_GENESIS_ID,
        _EXPECTED_GENESIS_ID,
    )
    if plan != replayed or observed != expected:
        raise _ValidationError("reconstructed plan differs from the freeze")
    return plan.artifact_bytes


def _optional_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    candidate = getattr(value, "value", None)
    return candidate if type(candidate) is str else value


def _success_record(
    result: _PD4Result,
) -> dict[str, object]:
    return {
        "all_effect_gates_false": True,
        "application_id": _optional_value(result.application_id),
        "database_mutation_performed": False,
        "execution_performed": False,
        "invocation_id": _optional_value(result.invocation_id),
        "invocation_published": False,
        "mutex_acquisition_state": _optional_value(result.mutex_acquisition_state),
        "operation_classification": _optional_value(result.operation_classification),
        "operation_diagnostic": _optional_value(result.operation_diagnostic),
        "operation_id": _optional_value(result.operation_id),
        "paper_account_id": result.paper_account_id,
        "provider_call_performed": False,
        "qualification_diagnostic": result.diagnostic.value,
        "qualification_status": result.status.value,
        "recovery_missing_application_id": _optional_value(
            result.recovery_missing_application_id
        ),
        "recovery_performed": False,
        "recovery_predecessor_checkpoint_id": _optional_value(
            result.recovery_predecessor_checkpoint_id
        ),
        "result": "VALIDATED",
        "scheduler_modified": False,
        "schema": _SCHEMA,
        "selected_snapshot_id": _optional_value(result.selected_snapshot_id),
        "selection_id": str(_EXPECTED_SELECTION_ID),
        "storage_classification": _optional_value(result.storage_classification),
        "terminal_checkpoint_id": _optional_value(result.terminal_checkpoint_id),
        "unattended_operation_authorized": False,
    }


def _run(deps: _Dependencies, *, _issuer: object) -> dict[str, object]:
    if _issuer is not _PRODUCTION_ISSUER and _issuer is not _DISPOSABLE_ISSUER:
        raise TypeError("validation issuer is invalid")
    _require_all_effect_gates_false(deps)
    deps.publication_preflight()
    history_seed = deps.history_seed_loader()
    frozen = _frozen_inputs(history_seed)  # type: ignore[arg-type]
    authority = deps.authority_loader()
    _require_authority(authority)
    reader = deps.selected_reader_factory(authority)
    selected = reader.read_selected_snapshot(str(_EXPECTED_SELECTION_ID))
    _require_selected_snapshot(selected)
    deps.provenance_validator(authority, selected)
    original_plan_bytes = _reconstruct_historical_plan(
        deps, authority, selected, frozen
    )
    _require_all_effect_gates_false(deps)
    result = deps.qualifier(
        authority,
        selected,
        history_seed=frozen.history_seed,
        strategy_config=frozen.strategy_config,
        caller_idempotency_key=frozen.caller_idempotency_key,
        open_reference=frozen.open_reference,
        policies=frozen.policies,
        planning_at=frozen.planning_at,
        submitted_at=frozen.submitted_at,
        filled_at=frozen.filled_at,
        metadata=(),
        historical_cycle_configuration_payloads=(original_plan_bytes,),
    )
    if type(result) is not _PD4_RESULT_TYPE:
        raise _ValidationError("PD4-C result type is invalid")
    _require_all_effect_gates_false(deps)
    _require_authority(authority)
    _require_selected_snapshot(selected)
    deps.provenance_validator(authority, selected)
    return _success_record(result)


def _production_dependencies() -> _Dependencies:
    return _Dependencies(
        _require_frozen_publication,
        _load_frozen_history_seed,
        acquire_validated_production_authority,
        WindowsSelectedC3SnapshotReadAuthority,
        _require_genuine_c1_p2,
        prepare_personal_desktop_paper_account_bundle,
        parse_personal_desktop_paper_account_anchor,
        verify_genesis_paper_account_checkpoint,
        verify_paper_account_lineage,
        verified_prior_from_full_lineage,
        build_manual_paper_strategy_plan,
        verify_manual_paper_strategy_plan,
        startup_qualification.qualify_personal_desktop_unattended_paper_startup,
        _effect_gate_state,
    )


def _open_disposable_validation_authority_for_test() -> (
    _DisposableValidationAuthorityForTest
):
    return _DisposableValidationAuthorityForTest(_issuer=_DISPOSABLE_ISSUER)


def _run_validation_for_test(
    authority: _DisposableValidationAuthorityForTest,
    dependencies: _Dependencies,
) -> dict[str, object]:
    """Run once using only injected, no-effect disposable callables."""

    if type(authority) is not _DisposableValidationAuthorityForTest:
        raise TypeError("disposable validation authority is invalid")
    production = _production_dependencies()
    genuine = {getattr(production, item.name) for item in fields(_Dependencies)}
    if any(
        getattr(dependencies, item.name) in genuine for item in fields(_Dependencies)
    ):
        raise TypeError("disposable validation requires no-effect callables")
    authority.consume()
    return _run(dependencies, _issuer=_DISPOSABLE_ISSUER)


def _emit(record: dict[str, object], *, stream: object | None = None) -> None:
    print(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=sys.stdout if stream is None else stream,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the frozen, read-only PD4-C unattended acceptance."""

    try:
        build_parser().parse_args(argv)
    except _CliUsageError:
        _emit({"reason": "INVALID_ARGUMENTS", "schema": _SCHEMA}, stream=sys.stderr)
        return _EXIT_USAGE
    if not _all_effect_gates_are_closed():
        _emit(
            {"reason": "EFFECT_GATE_STATE_INVALID", "schema": _SCHEMA},
            stream=sys.stderr,
        )
        return _EXIT_GATE
    try:
        record = _run(_production_dependencies(), _issuer=_PRODUCTION_ISSUER)
    except Exception:
        _emit({"reason": "VALIDATION_BLOCKED", "schema": _SCHEMA}, stream=sys.stderr)
        return _EXIT_VALIDATION
    _emit(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
