"""Execute one verified-snapshot paper cycle from an exact prior checkpoint."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderFill, OrderSide
from trading_bot.execution import (
    OrderEngine,
    current_order_engine_state_id,
    current_paper_ledger_state_id,
)
from trading_bot.ledger import (
    CompactPaperLedgerRestorationEvidence,
    CompactPaperLedgerState,
    InsufficientCashError,
    LedgerError,
    export_compact_paper_ledger_state,
    restore_paper_ledger_from_compact_state,
)
from trading_bot.market_data import (
    DailySnapshotVerificationResult,
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    canonical_decimal,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime.exceptions import (
    CheckpointedVerifiedSnapshotPaperCycleApplicationError,
    CheckpointedVerifiedSnapshotPaperCycleCheckpointError,
    CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    CheckpointedVerifiedSnapshotPaperCycleReconciliationError,
    CheckpointedVerifiedSnapshotPaperCycleRestorationError,
    CheckpointedVerifiedSnapshotPaperCycleRuntimeExecutionError,
    InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError,
    InconsistentPaperPortfolioCycleResultError,
    InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError,
    InvalidPaperPortfolioCycleRequestError,
    PaperPortfolioFillApplicationError,
    PaperPortfolioRuntimeError,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpointVerificationResult,
    PaperAccountCheckpointVerificationStatus,
    replay_verified_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.paper_portfolio import (
    PaperPortfolioCycleInputs,
    PaperPortfolioCyclePrice,
    PaperPortfolioCycleRequest,
    PaperPortfolioCycleResult,
    PaperPortfolioCycleStatus,
    PaperPortfolioRuntime,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    ExplicitQuantityTargetPortfolio,
    PreparedVerifiedSnapshotPaperCycle,
    VerifiedDailySnapshotReference,
    VerifiedSnapshotAccountPosition,
    VerifiedSnapshotAccountState,
    VerifiedSnapshotPaperCyclePolicies,
    VerifiedSnapshotPaperCyclePreparationRequest,
    prepare_verified_snapshot_paper_cycle,
)

CHECKPOINTED_VERIFIED_SNAPSHOT_APPLICATION_MATERIAL_VERSION = (
    "checkpointed-verified-snapshot-application-v1"
)
CHECKPOINTED_VERIFIED_SNAPSHOT_APPLICATION_NAMESPACE = UUID(
    "dd557a2f-1390-5a0b-a69c-476d81f38a10"
)
CHECKPOINTED_VERIFIED_SNAPSHOT_PAPER_CYCLE_RESULT_MATERIAL_VERSION = (
    "checkpointed-verified-snapshot-paper-cycle-result-v1"
)
CHECKPOINTED_VERIFIED_SNAPSHOT_PAPER_CYCLE_RESULT_NAMESPACE = UUID(
    "57124067-a5d5-5903-a80d-ddfbf3c3c77b"
)

CHECKPOINT_PRIOR_ID_METADATA_KEY = "checkpoint.prior_checkpoint_id"
CHECKPOINT_PRIOR_SEQUENCE_METADATA_KEY = "checkpoint.prior_sequence"
LINEAGE_PRIOR_ID_METADATA_KEY = "lineage.prior_lineage_id"
APPLICATION_ID_METADATA_KEY = "application.application_id"

_RESERVED_METADATA_PREFIXES = ("checkpoint.", "lineage.", "application.")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ZERO = Decimal("0")
_ARITHMETIC_CONTEXT = Context(prec=1024, Emax=999_999, Emin=-999_999)


class CheckpointedVerifiedSnapshotPaperCycleStatus(StrEnum):
    """Stable result status for one checkpoint-restored paper cycle."""

    APPLIED = "APPLIED"
    NO_ACTION = "NO_ACTION"


class CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode(StrEnum):
    """Stable successful-result diagnostic codes."""

    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class CheckpointedVerifiedSnapshotPaperCycleDiagnostic:
    """One stable code with non-identity explanatory text."""

    code: CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        if type(self.code) is not CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode:
            raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                "diagnostic code is invalid"
            )
        if type(self.message) is not str or not self.message.strip():
            raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                "diagnostic message must be nonblank"
            )


@dataclass(frozen=True, slots=True)
class CheckpointedVerifiedSnapshotPaperCycleRequest:
    """Caller-authored cycle intent with account state deliberately excluded."""

    request_id: UUID
    snapshot_reference: VerifiedDailySnapshotReference
    target: ExplicitQuantityTargetPortfolio
    open_references: tuple[CallerAssertedNextSessionOpenReference, ...]
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        if type(self.request_id) is not UUID:
            raise InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError(
                "request_id must be an exact UUID"
            )
        for name, expected in (
            ("snapshot_reference", VerifiedDailySnapshotReference),
            ("target", ExplicitQuantityTargetPortfolio),
            ("policies", VerifiedSnapshotPaperCyclePolicies),
        ):
            if type(getattr(self, name)) is not expected:
                raise InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError(
                    f"{name} must be an exact {expected.__name__}"
                )
        open_references = _exact_tuple(
            self.open_references,
            CallerAssertedNextSessionOpenReference,
            "open_references",
        )
        metadata = _exact_tuple(self.metadata, MetadataEntry, "metadata")
        if len({item.key for item in metadata}) != len(metadata):
            raise InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError(
                "metadata keys must be unique"
            )
        if any(item.key.startswith(_RESERVED_METADATA_PREFIXES) for item in metadata):
            raise InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError(
                "checkpoint., lineage., and application. metadata keys are reserved"
            )
        object.__setattr__(self, "open_references", open_references)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "planning_at", _request_utc(self.planning_at))
        object.__setattr__(self, "submitted_at", _request_utc(self.submitted_at))
        object.__setattr__(self, "filled_at", _request_utc(self.filled_at))


@dataclass(frozen=True, slots=True)
class CheckpointedVerifiedSnapshotPaperCycleResult:
    """Immutable evidence for one exact checkpoint-restored paper cycle.

    Asserted next-session open references remain caller-supplied values. They
    are not evidence of independently verified official opening prints.
    """

    result_id: UUID
    prior_checkpoint_id: UUID
    prior_sequence: int
    prior_lineage_id: UUID
    prior_account_state_id: UUID
    prior_checkpoint_sha256: str
    prior_checkpoint_byte_length: int
    application_id: UUID
    restoration_evidence: CompactPaperLedgerRestorationEvidence
    opening_compact_state: CompactPaperLedgerState
    preparation: PreparedVerifiedSnapshotPaperCycle
    runtime_result: PaperPortfolioCycleResult
    final_compact_state: CompactPaperLedgerState
    opening_realized_profit_loss: Decimal
    final_realized_profit_loss: Decimal
    status: CheckpointedVerifiedSnapshotPaperCycleStatus
    diagnostics: tuple[CheckpointedVerifiedSnapshotPaperCycleDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "result_id",
            "prior_checkpoint_id",
            "prior_lineage_id",
            "prior_account_state_id",
            "application_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                    f"{name} must be an exact UUID"
                )
        if type(self.prior_sequence) is not int or self.prior_sequence < 0:
            raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                "prior_sequence must be a nonnegative integer"
            )
        if (
            type(self.prior_checkpoint_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.prior_checkpoint_sha256) is None
            or type(self.prior_checkpoint_byte_length) is not int
            or self.prior_checkpoint_byte_length < 0
        ):
            raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                "prior checkpoint artifact evidence is invalid"
            )
        for name, expected in (
            ("restoration_evidence", CompactPaperLedgerRestorationEvidence),
            ("opening_compact_state", CompactPaperLedgerState),
            ("preparation", PreparedVerifiedSnapshotPaperCycle),
            ("runtime_result", PaperPortfolioCycleResult),
            ("final_compact_state", CompactPaperLedgerState),
        ):
            if type(getattr(self, name)) is not expected:
                raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                    f"{name} must be an exact {expected.__name__}"
                )
        if type(self.status) is not CheckpointedVerifiedSnapshotPaperCycleStatus:
            raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                "status is invalid"
            )
        for name in ("opening_realized_profit_loss", "final_realized_profit_loss"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite():
                raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                    f"{name} must be an exact finite Decimal"
                )
        diagnostics = _result_tuple(self.diagnostics)
        with localcontext(_ARITHMETIC_CONTEXT):
            _validate_result(self, diagnostics)
            expected_id = _result_id(
                self.prior_checkpoint_id,
                self.prior_sequence,
                self.prior_lineage_id,
                self.prior_account_state_id,
                self.prior_checkpoint_sha256,
                self.prior_checkpoint_byte_length,
                self.application_id,
                self.opening_compact_state,
                self.preparation,
                self.runtime_result,
                self.final_compact_state,
                self.status,
                diagnostics,
            )
        if self.result_id != expected_id:
            raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                "result_id does not match canonical checkpointed-cycle material"
            )
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def request_id(self) -> UUID:
        return self.preparation.request_id

    @property
    def snapshot_reference(self) -> VerifiedDailySnapshotReference:
        return self.preparation.snapshot_reference

    @property
    def cycle_fills(self) -> tuple[OrderFill, ...]:
        return self.runtime_result.fill_result.fills

    @property
    def pre_engine_state_id(self) -> UUID:
        return self.runtime_result.pre_engine_state_id

    @property
    def pre_ledger_state_id(self) -> UUID:
        return self.runtime_result.pre_ledger_state_id

    @property
    def post_engine_state_id(self) -> UUID:
        return self.runtime_result.post_engine_state_id

    @property
    def post_ledger_state_id(self) -> UUID:
        return self.runtime_result.post_ledger_state_id


def derive_checkpointed_verified_snapshot_application_id(
    prior_checkpoint_id: UUID,
    request_id: UUID,
) -> UUID:
    """Derive the coordinator application identity from exactly two UUIDs."""
    if type(prior_checkpoint_id) is not UUID or type(request_id) is not UUID:
        raise TypeError("prior_checkpoint_id and request_id must be exact UUIDs")
    return uuid5(
        CHECKPOINTED_VERIFIED_SNAPSHOT_APPLICATION_NAMESPACE,
        _framed(
            (
                CHECKPOINTED_VERIFIED_SNAPSHOT_APPLICATION_MATERIAL_VERSION,
                str(prior_checkpoint_id),
                str(request_id),
            )
        ),
    )


def execute_checkpointed_verified_snapshot_paper_cycle(
    request: CheckpointedVerifiedSnapshotPaperCycleRequest,
    checkpoint_verification: PaperAccountCheckpointVerificationResult,
    snapshot_verification: DailySnapshotVerificationResult,
    calendar: IdentifiedMarketCalendar,
) -> CheckpointedVerifiedSnapshotPaperCycleResult:
    """Restore, prepare, and execute exactly one private paper-runtime cycle."""
    if type(request) is not CheckpointedVerifiedSnapshotPaperCycleRequest:
        raise InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError(
            "request must be an exact CheckpointedVerifiedSnapshotPaperCycleRequest"
        )
    _require_complete_snapshot_verification(snapshot_verification)
    checkpoint, opening_state, ledger, restoration = _restore_verified_checkpoint(
        checkpoint_verification
    )
    application_id = derive_checkpointed_verified_snapshot_application_id(
        checkpoint.checkpoint_id,
        request.request_id,
    )
    metadata = request.metadata + (
        MetadataEntry(
            CHECKPOINT_PRIOR_ID_METADATA_KEY,
            str(checkpoint.checkpoint_id),
        ),
        MetadataEntry(
            CHECKPOINT_PRIOR_SEQUENCE_METADATA_KEY,
            str(checkpoint.sequence),
        ),
        MetadataEntry(LINEAGE_PRIOR_ID_METADATA_KEY, str(checkpoint.lineage_id)),
        MetadataEntry(APPLICATION_ID_METADATA_KEY, str(application_id)),
    )
    account_state = VerifiedSnapshotAccountState(
        checkpoint.account_state.account_state_id,
        opening_state.as_of,
        opening_state.cash,
        tuple(
            VerifiedSnapshotAccountPosition(
                position.symbol,
                position.quantity,
                position.average_cost,
            )
            for position in opening_state.positions
        ),
    )
    preparation_request = VerifiedSnapshotPaperCyclePreparationRequest(
        request.request_id,
        request.snapshot_reference,
        account_state,
        request.target,
        request.open_references,
        request.policies,
        request.planning_at,
        request.submitted_at,
        request.filled_at,
        metadata,
    )
    preparation = prepare_verified_snapshot_paper_cycle(
        preparation_request,
        snapshot_verification,
        calendar,
    )
    with localcontext(_ARITHMETIC_CONTEXT):
        _reconcile_preparation_account(
            preparation,
            opening_state,
            checkpoint.account_state.account_state_id,
        )
        runtime_request = _runtime_request(preparation)
        engine = OrderEngine()
        if engine.orders or engine.get_events():
            raise CheckpointedVerifiedSnapshotPaperCycleRestorationError(
                "fresh order engine is not empty"
            )
        expected_pre_engine_id = current_order_engine_state_id(engine)
        expected_pre_ledger_id = current_paper_ledger_state_id(ledger)
        if (
            checkpoint.empty_engine_state_id != expected_pre_engine_id
            or restoration.restored_ledger_state_id != expected_pre_ledger_id
        ):
            raise CheckpointedVerifiedSnapshotPaperCycleRestorationError(
                "fresh engine or restored ledger fingerprint does not reconcile"
            )
        runtime = PaperPortfolioRuntime(engine, ledger)
        try:
            runtime_result = runtime.run_cycle(runtime_request)
        except InconsistentPaperPortfolioCycleResultError as error:
            raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
                "paper-runtime result reconciliation failed"
            ) from error
        except PaperPortfolioFillApplicationError as error:
            if _has_cause(error, InsufficientCashError):
                raise CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError(
                    "asserted next-open fills exceed available checkpoint cash"
                ) from error
            raise CheckpointedVerifiedSnapshotPaperCycleApplicationError(
                "atomic checkpointed fill application failed"
            ) from error
        except PaperPortfolioRuntimeError as error:
            raise CheckpointedVerifiedSnapshotPaperCycleRuntimeExecutionError(
                "paper runtime failed during checkpointed execution"
            ) from error
        try:
            final_state = _reconcile_runtime_and_export(
                opening_state,
                preparation,
                runtime_request,
                runtime_result,
                runtime,
                expected_pre_engine_id,
                expected_pre_ledger_id,
            )
            status = (
                CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED
                if runtime_result.status is PaperPortfolioCycleStatus.APPLIED
                else CheckpointedVerifiedSnapshotPaperCycleStatus.NO_ACTION
            )
            diagnostics = (
                ()
                if status is CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED
                else (
                    CheckpointedVerifiedSnapshotPaperCycleDiagnostic(
                        CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode.NO_ACTION,
                        "the complete checkpointed paper cycle applied no fills",
                    ),
                )
            )
            result_id = _result_id(
                checkpoint.checkpoint_id,
                checkpoint.sequence,
                checkpoint.lineage_id,
                checkpoint.account_state.account_state_id,
                checkpoint_verification.checkpoint_sha256,
                checkpoint_verification.checkpoint_byte_length,
                application_id,
                opening_state,
                preparation,
                runtime_result,
                final_state,
                status,
                diagnostics,
            )
            return CheckpointedVerifiedSnapshotPaperCycleResult(
                result_id,
                checkpoint.checkpoint_id,
                checkpoint.sequence,
                checkpoint.lineage_id,
                checkpoint.account_state.account_state_id,
                checkpoint_verification.checkpoint_sha256,
                checkpoint_verification.checkpoint_byte_length,
                application_id,
                restoration,
                opening_state,
                preparation,
                runtime_result,
                final_state,
                opening_state.realized_profit_loss,
                final_state.realized_profit_loss,
                status,
                diagnostics,
            )
        except InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError:
            raise
        except (LedgerError, TypeError, ValueError, ArithmeticError) as error:
            raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
                "final checkpointed runtime state does not reconcile"
            ) from error


def _require_complete_snapshot_verification(
    verification: DailySnapshotVerificationResult,
) -> None:
    if (
        type(verification) is not DailySnapshotVerificationResult
        or verification.status is not DailySnapshotVerificationStatus.PASS
        or verification.snapshot is None
        or verification.diagnostics
    ):
        raise InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError(
            "snapshot_verification must be one complete PASS result"
        )


def _restore_verified_checkpoint(
    verification: PaperAccountCheckpointVerificationResult,
):
    if (
        type(verification) is not PaperAccountCheckpointVerificationResult
        or verification.status is not PaperAccountCheckpointVerificationStatus.PASS
        or verification.checkpoint is None
        or verification.restored_ledger is None
        or verification.restoration_evidence is None
        or verification.diagnostics
    ):
        raise CheckpointedVerifiedSnapshotPaperCycleCheckpointError(
            "checkpoint_verification must be one complete PASS result"
        )
    try:
        checkpoint, verified_ledger, verified_evidence = (
            replay_verified_genesis_paper_account_checkpoint(verification)
        )
        opening_state = checkpoint.account_state.compact_state()
        verified_state = export_compact_paper_ledger_state(
            verified_ledger,
            as_of=opening_state.as_of,
        )
        if (
            verified_state != opening_state
            or verified_ledger.fills
            or not verified_ledger.is_compact_restored
            or verified_evidence.compact_state_id != opening_state.compact_state_id
        ):
            raise CheckpointedVerifiedSnapshotPaperCycleCheckpointError(
                "verified checkpoint replay no longer reconciles"
            )
        ledger, restoration = restore_paper_ledger_from_compact_state(opening_state)
    except CheckpointedVerifiedSnapshotPaperCycleCheckpointError:
        raise
    except (LedgerError, TypeError, ValueError, ArithmeticError) as error:
        raise CheckpointedVerifiedSnapshotPaperCycleRestorationError(
            "public compact-ledger restoration failed"
        ) from error
    if (
        not ledger.is_compact_restored
        or ledger.fills
        or restoration != verified_evidence
        or export_compact_paper_ledger_state(ledger, as_of=opening_state.as_of)
        != opening_state
    ):
        raise CheckpointedVerifiedSnapshotPaperCycleRestorationError(
            "fresh compact-restored ledger does not reconcile exactly"
        )
    return checkpoint, opening_state, ledger, restoration


def _runtime_request(
    preparation: PreparedVerifiedSnapshotPaperCycle,
) -> PaperPortfolioCycleRequest:
    policies = preparation.policies
    prices = tuple(
        PaperPortfolioCyclePrice(
            close_mark.symbol,
            close_mark.planning_close,
            open_reference.caller_asserted_open_reference_price,
        )
        for close_mark, open_reference in zip(
            preparation.close_marks,
            preparation.open_references,
            strict=True,
        )
    )
    inputs = PaperPortfolioCycleInputs(
        preparation.portfolio_state,
        preparation.target_portfolio,
        policies.rebalance_assumptions,
        policies.portfolio_constraints,
        policies.proposal_policy,
        policies.proposal_confidence,
        policies.risk_limits,
        policies.risk_policy,
        prices,
        policies.fill_policy,
        policies.trading_enabled,
        preparation.submitted_at,
        preparation.filled_at,
    )
    try:
        return PaperPortfolioCycleRequest(
            preparation.request_id,
            inputs,
            preparation.metadata,
        )
    except (InvalidPaperPortfolioCycleRequestError, TypeError, ValueError) as error:
        raise CheckpointedVerifiedSnapshotPaperCycleRuntimeExecutionError(
            "exact paper-runtime request reconstruction failed"
        ) from error


def _reconcile_preparation_account(
    preparation: PreparedVerifiedSnapshotPaperCycle,
    opening_state: CompactPaperLedgerState,
    expected_account_state_id: UUID,
) -> None:
    account = preparation.account_state
    if (
        account.as_of != opening_state.as_of
        or account.cash != opening_state.cash
        or account.account_state_id != expected_account_state_id
    ):
        raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
            "prepared account identity, time, or cash differs from checkpoint"
        )
    expected = {position.symbol: position for position in opening_state.positions}
    prepared = {
        position.symbol: position
        for position in account.positions
        if position.quantity > _ZERO
    }
    if set(expected) != set(prepared):
        raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
            "prepared holdings differ from exact compact checkpoint holdings"
        )
    for symbol, compact_position in expected.items():
        prepared_position = prepared[symbol]
        if (
            prepared_position.quantity != compact_position.quantity
            or prepared_position.average_cost != compact_position.average_cost
        ):
            raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
                "prepared holding differs from exact checkpoint accounting"
            )


def _reconcile_runtime_and_export(
    opening_state: CompactPaperLedgerState,
    preparation: PreparedVerifiedSnapshotPaperCycle,
    runtime_request: PaperPortfolioCycleRequest,
    runtime_result: PaperPortfolioCycleResult,
    runtime: PaperPortfolioRuntime,
    expected_pre_engine_id: UUID,
    expected_pre_ledger_id: UUID,
) -> CompactPaperLedgerState:
    if runtime_result.request != runtime_request:
        raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
            "runtime request differs from prepared checkpoint inputs"
        )
    if (
        runtime_result.pre_engine_state_id != expected_pre_engine_id
        or runtime_result.pre_ledger_state_id != expected_pre_ledger_id
        or runtime_result.post_engine_state_id
        != current_order_engine_state_id(runtime.engine)
        or runtime_result.post_ledger_state_id
        != current_paper_ledger_state_id(runtime.ledger)
        or not runtime.ledger.is_compact_restored
    ):
        raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
            "runtime component state fingerprints do not reconcile"
        )
    fills = runtime_result.fill_result.fills
    if runtime.ledger.fills != fills:
        raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
            "checkpoint restoration synthesized history or cycle fills differ"
        )
    orders = tuple(runtime.engine.orders.values())
    expected_orders = tuple(
        item.updated_order for item in runtime_result.application_result.evaluations
    )
    if orders != expected_orders:
        raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
            "private engine orders differ from application evidence"
        )
    for order, fill in zip(orders, fills, strict=True):
        if runtime.engine.get_fills(order.request.order_id) != (fill,):
            raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
                "private engine fill membership differs from cycle evidence"
            )
    _validate_fill_order(runtime_result)
    final_state = export_compact_paper_ledger_state(
        runtime.ledger,
        as_of=preparation.filled_at,
    )
    if (
        final_state.cash != runtime.ledger.cash
        or final_state.realized_profit_loss != runtime.ledger.realized_profit_loss
    ):
        raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
            "final compact state differs from authoritative runtime ledger"
        )
    if runtime_result.application_result.evaluations:
        final_evaluation = runtime_result.application_result.evaluations[-1]
        if (
            final_evaluation.ledger_cash_after != final_state.cash
            or final_evaluation.ledger_realized_profit_loss_after
            != final_state.realized_profit_loss
        ):
            raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
                "final application accounting differs from compact state"
            )
    elif not _same_account_values(opening_state, final_state):
        raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
            "NO_ACTION changed compact checkpoint accounting"
        )
    return final_state


def _validate_result(
    result: CheckpointedVerifiedSnapshotPaperCycleResult,
    diagnostics: tuple[CheckpointedVerifiedSnapshotPaperCycleDiagnostic, ...],
) -> None:
    expected_application_id = derive_checkpointed_verified_snapshot_application_id(
        result.prior_checkpoint_id,
        result.preparation.request_id,
    )
    if result.application_id != expected_application_id:
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "application_id does not match prior checkpoint and caller request"
        )
    expected_metadata = (
        MetadataEntry(
            CHECKPOINT_PRIOR_ID_METADATA_KEY,
            str(result.prior_checkpoint_id),
        ),
        MetadataEntry(
            CHECKPOINT_PRIOR_SEQUENCE_METADATA_KEY,
            str(result.prior_sequence),
        ),
        MetadataEntry(LINEAGE_PRIOR_ID_METADATA_KEY, str(result.prior_lineage_id)),
        MetadataEntry(APPLICATION_ID_METADATA_KEY, str(result.application_id)),
    )
    if result.preparation.metadata[-4:] != expected_metadata:
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "coordinator-owned metadata bindings are missing or reordered"
        )
    if any(
        item.key.startswith(_RESERVED_METADATA_PREFIXES)
        for item in result.preparation.metadata[:-4]
    ):
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "caller metadata uses a coordinator-reserved prefix"
        )
    if (
        result.restoration_evidence.compact_state_id
        != result.opening_compact_state.compact_state_id
        or result.opening_realized_profit_loss
        != result.opening_compact_state.realized_profit_loss
        or result.final_realized_profit_loss
        != result.final_compact_state.realized_profit_loss
        or result.final_compact_state.as_of != result.preparation.filled_at
    ):
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "retained compact or realized-profit-and-loss evidence differs"
        )
    _reconcile_preparation_account(
        result.preparation,
        result.opening_compact_state,
        result.prior_account_state_id,
    )
    runtime_request = _runtime_request(result.preparation)
    if result.runtime_result.request != runtime_request:
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "runtime request does not match retained preparation"
        )
    try:
        replay_ledger, evidence = restore_paper_ledger_from_compact_state(
            result.opening_compact_state
        )
        if (
            evidence != result.restoration_evidence
            or result.runtime_result.pre_engine_state_id
            != current_order_engine_state_id(OrderEngine())
            or result.runtime_result.pre_ledger_state_id
            != current_paper_ledger_state_id(replay_ledger)
        ):
            raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                "runtime pre-state differs from compact restoration"
            )
        for evaluation in result.runtime_result.application_result.evaluations:
            replay_ledger.apply_fill(evaluation.fill)
            if (
                replay_ledger.cash != evaluation.ledger_cash_after
                or replay_ledger.realized_profit_loss
                != evaluation.ledger_realized_profit_loss_after
                or replay_ledger.get_position(evaluation.fill.symbol)
                != evaluation.ledger_position_after
            ):
                raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
                    "application accounting does not replay exactly"
                )
        replay_final = export_compact_paper_ledger_state(
            replay_ledger,
            as_of=result.preparation.filled_at,
        )
    except InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError:
        raise
    except (LedgerError, TypeError, ValueError, ArithmeticError) as error:
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "cycle fills cannot be replayed from opening compact state"
        ) from error
    if (
        replay_final != result.final_compact_state
        or result.runtime_result.post_ledger_state_id
        != current_paper_ledger_state_id(replay_ledger)
    ):
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "final compact state does not match replayed authoritative ledger"
        )
    expected_status = (
        CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED
        if result.runtime_result.status is PaperPortfolioCycleStatus.APPLIED
        else CheckpointedVerifiedSnapshotPaperCycleStatus.NO_ACTION
    )
    expected_codes = (
        ()
        if expected_status is CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED
        else (CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode.NO_ACTION,)
    )
    fills = result.runtime_result.fill_result.fills
    if (
        result.status is not expected_status
        or tuple(item.code for item in diagnostics) != expected_codes
        or (result.status is CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED)
        != bool(fills)
    ):
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "checkpointed status, fills, or diagnostics do not reconcile"
        )
    if (
        result.status is CheckpointedVerifiedSnapshotPaperCycleStatus.NO_ACTION
        and not _same_account_values(
            result.opening_compact_state,
            result.final_compact_state,
        )
    ):
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "NO_ACTION must preserve exact compact accounting values"
        )
    _validate_fill_order(result.runtime_result)


def _validate_fill_order(runtime_result: PaperPortfolioCycleResult) -> None:
    seen_buy = False
    for fill in runtime_result.fill_result.fills:
        if fill.side is OrderSide.BUY:
            seen_buy = True
        elif seen_buy:
            raise CheckpointedVerifiedSnapshotPaperCycleReconciliationError(
                "sell fills must precede buy fills"
            )


def _result_id(
    prior_checkpoint_id: UUID,
    prior_sequence: int,
    prior_lineage_id: UUID,
    prior_account_state_id: UUID,
    prior_checkpoint_sha256: str,
    prior_checkpoint_byte_length: int,
    application_id: UUID,
    opening_state: CompactPaperLedgerState,
    preparation: PreparedVerifiedSnapshotPaperCycle,
    runtime_result: PaperPortfolioCycleResult,
    final_state: CompactPaperLedgerState,
    status: CheckpointedVerifiedSnapshotPaperCycleStatus,
    diagnostics: tuple[CheckpointedVerifiedSnapshotPaperCycleDiagnostic, ...],
) -> UUID:
    snapshot = preparation.snapshot_reference
    parts = [
        CHECKPOINTED_VERIFIED_SNAPSHOT_PAPER_CYCLE_RESULT_MATERIAL_VERSION,
        str(prior_checkpoint_id),
        str(prior_sequence),
        str(prior_lineage_id),
        str(prior_account_state_id),
        prior_checkpoint_sha256,
        str(prior_checkpoint_byte_length),
        str(application_id),
        str(preparation.request_id),
        str(snapshot.snapshot_id),
        snapshot.artifact_sha256,
        str(snapshot.artifact_byte_length),
        preparation.snapshot_audit_sha256,
        preparation.snapshot_canonical_bars_sha256,
        str(preparation.preparation_id),
        str(runtime_result.result_id),
        str(runtime_result.application_result.result_id),
        str(runtime_result.pre_engine_state_id),
        str(runtime_result.pre_ledger_state_id),
        str(runtime_result.post_engine_state_id),
        str(runtime_result.post_ledger_state_id),
        str(opening_state.compact_state_id),
        str(final_state.compact_state_id),
        str(len(runtime_result.fill_result.fills)),
    ]
    for fill in runtime_result.fill_result.fills:
        parts.extend(("fill", *_fill_material(fill)))
    parts.extend(
        (
            status.value,
            str(len(diagnostics)),
            *(item.code.value for item in diagnostics),
        )
    )
    return uuid5(
        CHECKPOINTED_VERIFIED_SNAPSHOT_PAPER_CYCLE_RESULT_NAMESPACE,
        _framed(tuple(parts)),
    )


def _fill_material(fill: OrderFill) -> tuple[str, ...]:
    return (
        str(fill.fill_id),
        str(fill.order_id),
        str(fill.symbol),
        fill.side.value,
        canonical_decimal(fill.quantity),
        canonical_decimal(fill.price),
        canonical_decimal(fill.commission),
        fill.filled_at.isoformat(),
    )


def _same_account_values(
    opening: CompactPaperLedgerState,
    final: CompactPaperLedgerState,
) -> bool:
    return (
        opening.cash == final.cash
        and opening.positions == final.positions
        and opening.realized_profit_loss == final.realized_profit_loss
    )


def _exact_tuple(value: object, expected: type, name: str):
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError(
            f"{name} must be iterable"
        ) from error
    if any(type(item) is not expected for item in items):
        raise InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError(
            f"{name} contains an invalid value"
        )
    return items


def _result_tuple(
    value: object,
) -> tuple[CheckpointedVerifiedSnapshotPaperCycleDiagnostic, ...]:
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "diagnostics must be iterable"
        ) from error
    if any(
        type(item) is not CheckpointedVerifiedSnapshotPaperCycleDiagnostic
        for item in items
    ):
        raise InconsistentCheckpointedVerifiedSnapshotPaperCycleResultError(
            "diagnostics contain invalid values"
        )
    return items


def _request_utc(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise InvalidCheckpointedVerifiedSnapshotPaperCycleRequestError(
            "cycle timestamps must be exact timezone-aware datetimes"
        )
    return value.astimezone(UTC)


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)


def _has_cause(error: BaseException, expected: type[BaseException]) -> bool:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, expected):
            return True
        current = current.__cause__
    return False
