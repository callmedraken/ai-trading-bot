"""One-shot execution of an immutable prepared verified-snapshot paper cycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderFill, OrderSide, Position
from trading_bot.execution import (
    OrderEngine,
    current_order_engine_state_id,
    current_paper_ledger_state_id,
)
from trading_bot.ledger import (
    InsufficientCashError,
    LedgerError,
    PaperLedgerInitializationEvidence,
    PaperLedgerInitializationMode,
    PaperLedgerInitializationPosition,
    PaperLedgerInitializationRequest,
    initialize_paper_ledger,
)
from trading_bot.runtime.exceptions import (
    InconsistentPaperPortfolioCycleResultError,
    InconsistentVerifiedSnapshotPaperCycleResultError,
    InvalidPaperPortfolioCycleRequestError,
    InvalidPreparedVerifiedSnapshotPaperCycleError,
    PaperPortfolioFillApplicationError,
    PaperPortfolioRuntimeError,
    VerifiedSnapshotPaperCycleApplicationError,
    VerifiedSnapshotPaperCycleInitializationError,
    VerifiedSnapshotPaperCycleInsufficientCashError,
    VerifiedSnapshotPaperCycleReconciliationError,
    VerifiedSnapshotPaperCycleRequestReconstructionError,
    VerifiedSnapshotPaperCycleRuntimeExecutionError,
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
    PreparedVerifiedSnapshotPaperCycle,
)

VERIFIED_SNAPSHOT_PAPER_CYCLE_RESULT_MATERIAL_VERSION = (
    "verified-snapshot-paper-cycle-result-v1"
)
VERIFIED_SNAPSHOT_PAPER_CYCLE_RESULT_NAMESPACE = UUID(
    "67f78288-8626-51d0-ba3e-0ec47f7f04c3"
)

_BOOTSTRAP_MATERIAL_VERSION = "verified-snapshot-paper-cycle-bootstrap-v1"
_ZERO = Decimal("0")
_ARITHMETIC_CONTEXT = Context(prec=1024, Emax=999_999, Emin=-999_999)


class VerifiedSnapshotPaperCycleStatus(StrEnum):
    """Stable one-shot adapter result status."""

    APPLIED = "APPLIED"
    NO_ACTION = "NO_ACTION"


class VerifiedSnapshotPaperCycleDiagnosticCode(StrEnum):
    """Stable successful-result diagnostic codes."""

    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCycleDiagnostic:
    """One stable result code with non-identity explanatory text."""

    code: VerifiedSnapshotPaperCycleDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        if type(self.code) is not VerifiedSnapshotPaperCycleDiagnosticCode:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "diagnostic code must be VerifiedSnapshotPaperCycleDiagnosticCode"
            )
        if type(self.message) is not str or not self.message.strip():
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "diagnostic message must be nonblank"
            )


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCycleAccountState:
    """Final immutable public paper-account state after the retrospective cycle."""

    as_of: datetime
    cash: Decimal
    positions: tuple[Position, ...]
    realized_profit_loss: Decimal

    def __post_init__(self) -> None:
        as_of = _utc(self.as_of, "final account as_of")
        cash = _finite_decimal(self.cash, "final account cash")
        realized = _finite_decimal(
            self.realized_profit_loss,
            "final account realized_profit_loss",
            allow_negative=True,
        )
        try:
            positions = tuple(self.positions)
        except TypeError as error:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "final account positions must be iterable"
            ) from error
        if any(type(item) is not Position for item in positions):
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "final account positions must contain exact Position values"
            )
        if len({item.symbol for item in positions}) != len(positions):
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "final account position symbols must be unique"
            )
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "realized_profit_loss", realized)


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCycleResult:
    """Immutable evidence for one retrospective caller-asserted next-open cycle.

    This result records deterministic local paper execution. It is not evidence
    of a live broker submission or an independently verified official open.
    """

    result_id: UUID
    preparation: PreparedVerifiedSnapshotPaperCycle
    bootstrap_evidence: PaperLedgerInitializationEvidence
    runtime_result: PaperPortfolioCycleResult
    status: VerifiedSnapshotPaperCycleStatus
    final_account_state: VerifiedSnapshotPaperCycleAccountState
    diagnostics: tuple[VerifiedSnapshotPaperCycleDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.result_id) is not UUID:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "result_id must be a UUID"
            )
        if type(self.preparation) is not PreparedVerifiedSnapshotPaperCycle:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "preparation must be an exact PreparedVerifiedSnapshotPaperCycle"
            )
        if type(self.bootstrap_evidence) is not PaperLedgerInitializationEvidence:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "bootstrap_evidence must be exact initialization evidence"
            )
        if type(self.runtime_result) is not PaperPortfolioCycleResult:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "runtime_result must be an exact PaperPortfolioCycleResult"
            )
        if type(self.status) is not VerifiedSnapshotPaperCycleStatus:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "status must be VerifiedSnapshotPaperCycleStatus"
            )
        if type(self.final_account_state) is not VerifiedSnapshotPaperCycleAccountState:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "final_account_state must be exact adapter account state"
            )
        try:
            diagnostics = tuple(self.diagnostics)
        except TypeError as error:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "diagnostics must be iterable"
            ) from error
        if any(
            type(item) is not VerifiedSnapshotPaperCycleDiagnostic
            for item in diagnostics
        ):
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "diagnostics contain invalid values"
            )
        _validate_result(self, diagnostics)
        expected_id = _result_id(
            self.preparation,
            self.bootstrap_evidence,
            self.runtime_result,
            self.status,
            self.final_account_state,
            diagnostics,
        )
        if self.result_id != expected_id:
            raise InconsistentVerifiedSnapshotPaperCycleResultError(
                "result_id does not match deterministic adapter identity"
            )
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def initial_cash(self) -> Decimal:
        """Return explicit cash before the one paper-runtime cycle."""
        return self.bootstrap_evidence.request.available_cash

    @property
    def cycle_fills(self) -> tuple[OrderFill, ...]:
        """Return only runtime-cycle fills, excluding synthetic bootstrap fills."""
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


def execute_prepared_verified_snapshot_paper_cycle(
    preparation: PreparedVerifiedSnapshotPaperCycle,
) -> VerifiedSnapshotPaperCycleResult:
    """Execute exactly one existing paper-runtime cycle using fresh private state."""
    if type(preparation) is not PreparedVerifiedSnapshotPaperCycle:
        raise InvalidPreparedVerifiedSnapshotPaperCycleError(
            "preparation must be an exact PreparedVerifiedSnapshotPaperCycle"
        )
    try:
        initialization_request = _initialization_request(preparation)
        with localcontext(_ARITHMETIC_CONTEXT):
            ledger, bootstrap_evidence = initialize_paper_ledger(initialization_request)
    except LedgerError as error:
        raise VerifiedSnapshotPaperCycleInitializationError(
            "fresh private paper-ledger initialization failed"
        ) from error
    try:
        runtime_request = _runtime_request(preparation)
    except (InvalidPaperPortfolioCycleRequestError, TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleRequestReconstructionError(
            "exact paper-runtime request reconstruction failed"
        ) from error

    engine = OrderEngine()
    with localcontext(_ARITHMETIC_CONTEXT):
        expected_pre_engine_state_id = current_order_engine_state_id(engine)
        expected_pre_ledger_state_id = current_paper_ledger_state_id(ledger)
    runtime = PaperPortfolioRuntime(engine, ledger)
    try:
        with localcontext(_ARITHMETIC_CONTEXT):
            runtime_result = runtime.run_cycle(runtime_request)
    except InconsistentPaperPortfolioCycleResultError as error:
        raise VerifiedSnapshotPaperCycleReconciliationError(
            "existing paper-runtime result reconciliation failed"
        ) from error
    except PaperPortfolioFillApplicationError as error:
        if _has_cause(error, InsufficientCashError):
            raise VerifiedSnapshotPaperCycleInsufficientCashError(
                "asserted next-open fill prices exceed available paper cash"
            ) from error
        raise VerifiedSnapshotPaperCycleApplicationError(
            "existing atomic paper-fill application failed"
        ) from error
    except PaperPortfolioRuntimeError as error:
        raise VerifiedSnapshotPaperCycleRuntimeExecutionError(
            "existing paper runtime failed"
        ) from error

    try:
        with localcontext(_ARITHMETIC_CONTEXT):
            _reconcile_private_runtime(
                preparation,
                bootstrap_evidence,
                runtime_result,
                runtime,
                expected_pre_engine_state_id,
                expected_pre_ledger_state_id,
            )
            final_account_state = _final_account_state(preparation, runtime)
            status = (
                VerifiedSnapshotPaperCycleStatus.APPLIED
                if runtime_result.status is PaperPortfolioCycleStatus.APPLIED
                else VerifiedSnapshotPaperCycleStatus.NO_ACTION
            )
            diagnostics = (
                ()
                if status is VerifiedSnapshotPaperCycleStatus.APPLIED
                else (
                    VerifiedSnapshotPaperCycleDiagnostic(
                        VerifiedSnapshotPaperCycleDiagnosticCode.NO_ACTION,
                        "the complete one-shot paper cycle produced no applied fills",
                    ),
                )
            )
            result_id = _result_id(
                preparation,
                bootstrap_evidence,
                runtime_result,
                status,
                final_account_state,
                diagnostics,
            )
            return VerifiedSnapshotPaperCycleResult(
                result_id,
                preparation,
                bootstrap_evidence,
                runtime_result,
                status,
                final_account_state,
                diagnostics,
            )
    except InconsistentVerifiedSnapshotPaperCycleResultError:
        raise
    except (TypeError, ValueError, ArithmeticError, LedgerError) as error:
        raise VerifiedSnapshotPaperCycleReconciliationError(
            "private runtime state does not reconcile with immutable evidence"
        ) from error


def _initialization_request(
    preparation: PreparedVerifiedSnapshotPaperCycle,
) -> PaperLedgerInitializationRequest:
    positions = tuple(
        PaperLedgerInitializationPosition(
            item.symbol,
            item.quantity,
            item.average_cost,
        )
        for item in preparation.account_state.positions
        if item.quantity > _ZERO
    )
    mode = (
        PaperLedgerInitializationMode.BOOTSTRAP_FILLS
        if positions
        else PaperLedgerInitializationMode.CASH_ONLY
    )
    return PaperLedgerInitializationRequest(
        mode,
        preparation.account_state.as_of,
        preparation.account_state.cash,
        positions,
        VERIFIED_SNAPSHOT_PAPER_CYCLE_RESULT_NAMESPACE,
        (
            _BOOTSTRAP_MATERIAL_VERSION,
            str(preparation.preparation_id),
            str(preparation.account_state.account_state_id),
        ),
    )


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
    return PaperPortfolioCycleRequest(
        preparation.request_id,
        inputs,
        preparation.metadata,
    )


def _reconcile_private_runtime(
    preparation: PreparedVerifiedSnapshotPaperCycle,
    bootstrap_evidence: PaperLedgerInitializationEvidence,
    runtime_result: PaperPortfolioCycleResult,
    runtime: PaperPortfolioRuntime,
    expected_pre_engine_state_id: UUID,
    expected_pre_ledger_state_id: UUID,
) -> None:
    if runtime_result.request != _runtime_request(preparation):
        raise VerifiedSnapshotPaperCycleReconciliationError(
            "runtime request differs from exact prepared inputs"
        )
    if bootstrap_evidence.request != _initialization_request(preparation):
        raise VerifiedSnapshotPaperCycleReconciliationError(
            "bootstrap request differs from prepared account state"
        )
    with localcontext(_ARITHMETIC_CONTEXT):
        if (
            runtime_result.pre_engine_state_id != expected_pre_engine_state_id
            or runtime_result.pre_ledger_state_id != expected_pre_ledger_state_id
            or runtime_result.post_engine_state_id
            != current_order_engine_state_id(runtime.engine)
            or runtime_result.post_ledger_state_id
            != current_paper_ledger_state_id(runtime.ledger)
        ):
            raise VerifiedSnapshotPaperCycleReconciliationError(
                "runtime pre/post component state IDs do not reconcile"
            )
    cycle_fills = runtime_result.fill_result.fills
    if runtime.ledger.fills != bootstrap_evidence.bootstrap_fills + cycle_fills:
        raise VerifiedSnapshotPaperCycleReconciliationError(
            "final ledger fill history does not reconcile with bootstrap and cycle"
        )
    if runtime_result.application_result.evaluations:
        final_evaluation = runtime_result.application_result.evaluations[-1]
        if (
            final_evaluation.ledger_cash_after != runtime.ledger.cash
            or final_evaluation.ledger_realized_profit_loss_after
            != runtime.ledger.realized_profit_loss
        ):
            raise VerifiedSnapshotPaperCycleReconciliationError(
                "final application evaluation differs from private ledger"
            )
    elif (
        runtime.ledger.cash != preparation.account_state.cash
        or runtime.ledger.realized_profit_loss != _ZERO
    ):
        raise VerifiedSnapshotPaperCycleReconciliationError(
            "empty cycle changed private ledger accounting"
        )
    orders = tuple(runtime.engine.orders.values())
    expected_orders = tuple(
        item.updated_order for item in runtime_result.application_result.evaluations
    )
    if orders != expected_orders:
        raise VerifiedSnapshotPaperCycleReconciliationError(
            "private engine orders differ from application evidence"
        )
    for order, fill in zip(orders, cycle_fills, strict=True):
        if runtime.engine.get_fills(order.request.order_id) != (fill,):
            raise VerifiedSnapshotPaperCycleReconciliationError(
                "private engine fill history differs from cycle evidence"
            )
    _validate_stage_ordering(runtime_result)


def _validate_stage_ordering(runtime_result: PaperPortfolioCycleResult) -> None:
    accepted = tuple(
        item.decision
        for item in runtime_result.risk_result.evaluations
        if item.decision.approved_quantity > _ZERO
    )
    order_requests = tuple(item.request for item in runtime_result.order_result.orders)
    fills = runtime_result.fill_result.fills
    applications = runtime_result.application_result.evaluations
    if (
        tuple(
            (item.proposal.symbol, item.proposal.side, item.approved_quantity)
            for item in accepted
        )
        != tuple((item.symbol, item.side, item.quantity) for item in order_requests)
        or tuple(
            (item.symbol, item.side, item.quantity, item.order_id) for item in fills
        )
        != tuple(
            (
                item.symbol,
                item.side,
                item.quantity,
                item.order_id,
            )
            for item in order_requests
        )
        or tuple(item.fill for item in applications) != fills
    ):
        raise VerifiedSnapshotPaperCycleReconciliationError(
            "proposal, risk, order, fill, and application ordering differs"
        )
    seen_buy = False
    for fill in fills:
        if fill.side is OrderSide.BUY:
            seen_buy = True
        elif seen_buy:
            raise VerifiedSnapshotPaperCycleReconciliationError(
                "sell fills must precede buy fills"
            )


def _final_account_state(
    preparation: PreparedVerifiedSnapshotPaperCycle,
    runtime: PaperPortfolioRuntime,
) -> VerifiedSnapshotPaperCycleAccountState:
    positions_by_symbol = runtime.ledger.positions
    symbols = tuple(item.symbol for item in preparation.close_marks)
    if any(symbol not in set(symbols) for symbol in positions_by_symbol):
        raise VerifiedSnapshotPaperCycleReconciliationError(
            "final ledger contains a symbol outside the prepared universe"
        )
    positions = tuple(
        positions_by_symbol[symbol]
        for symbol in symbols
        if symbol in positions_by_symbol
    )
    return VerifiedSnapshotPaperCycleAccountState(
        preparation.filled_at,
        runtime.ledger.cash,
        positions,
        runtime.ledger.realized_profit_loss,
    )


def _validate_result(
    result: VerifiedSnapshotPaperCycleResult,
    diagnostics: tuple[VerifiedSnapshotPaperCycleDiagnostic, ...],
) -> None:
    expected_request = _runtime_request(result.preparation)
    if result.runtime_result.request != expected_request:
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            "runtime request does not match preparation"
        )
    expected_status = (
        VerifiedSnapshotPaperCycleStatus.APPLIED
        if result.runtime_result.status is PaperPortfolioCycleStatus.APPLIED
        else VerifiedSnapshotPaperCycleStatus.NO_ACTION
    )
    if result.status is not expected_status:
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            "adapter status does not match existing runtime status"
        )
    expected_codes = (
        ()
        if result.status is VerifiedSnapshotPaperCycleStatus.APPLIED
        else (VerifiedSnapshotPaperCycleDiagnosticCode.NO_ACTION,)
    )
    if tuple(item.code for item in diagnostics) != expected_codes:
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            "diagnostics do not match adapter status"
        )
    fills = result.runtime_result.fill_result.fills
    if (result.status is VerifiedSnapshotPaperCycleStatus.APPLIED) != bool(fills):
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            "APPLIED requires fills and NO_ACTION prohibits fills"
        )
    expected_initialization = _initialization_request(result.preparation)
    if result.bootstrap_evidence.request != expected_initialization:
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            "bootstrap evidence does not match prepared account state"
        )
    try:
        with localcontext(_ARITHMETIC_CONTEXT):
            replay_ledger, replay_evidence = initialize_paper_ledger(
                expected_initialization
            )
            if replay_evidence != result.bootstrap_evidence:
                raise InconsistentVerifiedSnapshotPaperCycleResultError(
                    "bootstrap evidence is not deterministic"
                )
            if (
                result.runtime_result.pre_engine_state_id
                != current_order_engine_state_id(OrderEngine())
                or result.runtime_result.pre_ledger_state_id
                != current_paper_ledger_state_id(replay_ledger)
            ):
                raise InconsistentVerifiedSnapshotPaperCycleResultError(
                    "runtime pre-state IDs do not match fresh initialized state"
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
                    raise InconsistentVerifiedSnapshotPaperCycleResultError(
                        "application accounting evidence does not replay exactly"
                    )
            if result.runtime_result.post_ledger_state_id != (
                current_paper_ledger_state_id(replay_ledger)
            ):
                raise InconsistentVerifiedSnapshotPaperCycleResultError(
                    "runtime post-ledger state ID does not match replayed ledger"
                )
            expected_positions = _ordered_positions(
                result.preparation,
                replay_ledger.positions,
            )
    except InconsistentVerifiedSnapshotPaperCycleResultError:
        raise
    except (LedgerError, TypeError, ValueError, ArithmeticError) as error:
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            "cycle fills cannot be replayed from bootstrap evidence"
        ) from error
    if (
        result.final_account_state.as_of != result.preparation.filled_at
        or result.final_account_state.cash != replay_ledger.cash
        or result.final_account_state.positions != expected_positions
        or result.final_account_state.realized_profit_loss
        != replay_ledger.realized_profit_loss
    ):
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            "final public account state does not match replayed ledger"
        )
    _validate_stage_ordering(result.runtime_result)


def _ordered_positions(
    preparation: PreparedVerifiedSnapshotPaperCycle,
    positions_by_symbol,
) -> tuple[Position, ...]:  # type: ignore[no-untyped-def]
    symbols = tuple(item.symbol for item in preparation.close_marks)
    if any(symbol not in set(symbols) for symbol in positions_by_symbol):
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            "account state contains a symbol outside the prepared universe"
        )
    return tuple(
        positions_by_symbol[symbol]
        for symbol in symbols
        if symbol in positions_by_symbol
    )


def _result_id(
    preparation: PreparedVerifiedSnapshotPaperCycle,
    bootstrap: PaperLedgerInitializationEvidence,
    runtime_result: PaperPortfolioCycleResult,
    status: VerifiedSnapshotPaperCycleStatus,
    final_state: VerifiedSnapshotPaperCycleAccountState,
    diagnostics: tuple[VerifiedSnapshotPaperCycleDiagnostic, ...],
) -> UUID:
    parts = [
        VERIFIED_SNAPSHOT_PAPER_CYCLE_RESULT_MATERIAL_VERSION,
        str(preparation.preparation_id),
        str(bootstrap.initialization_id),
        str(len(bootstrap.bootstrap_fills)),
    ]
    for fill in bootstrap.bootstrap_fills:
        parts.extend(("bootstrap-fill", *_fill_material(fill)))
    parts.extend(
        (
            str(runtime_result.result_id),
            str(runtime_result.request.request_id),
            str(runtime_result.pre_engine_state_id),
            str(runtime_result.pre_ledger_state_id),
            str(runtime_result.post_engine_state_id),
            str(runtime_result.post_ledger_state_id),
            status.value,
            final_state.as_of.isoformat(),
            _canonical_decimal(final_state.cash),
            _canonical_decimal(final_state.realized_profit_loss),
            str(len(final_state.positions)),
        )
    )
    for position in final_state.positions:
        parts.extend(
            (
                "final-position",
                str(position.symbol),
                _canonical_decimal(position.quantity),
                _canonical_decimal(position.average_cost),
            )
        )
    fills = runtime_result.fill_result.fills
    parts.append(str(len(fills)))
    for fill in fills:
        parts.extend(("cycle-fill", *_fill_material(fill)))
    parts.append(str(len(diagnostics)))
    parts.extend(item.code.value for item in diagnostics)
    return uuid5(
        VERIFIED_SNAPSHOT_PAPER_CYCLE_RESULT_NAMESPACE,
        _framed_material(tuple(parts)),
    )


def _fill_material(fill: OrderFill) -> tuple[str, ...]:
    return (
        str(fill.fill_id),
        str(fill.order_id),
        str(fill.symbol),
        fill.side.value,
        _canonical_decimal(fill.quantity),
        _canonical_decimal(fill.price),
        _canonical_decimal(fill.commission),
        fill.filled_at.isoformat(),
    )


def _canonical_decimal(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            "identity Decimal must be exact and finite"
        )
    if value == _ZERO:
        return "0"
    sign, digits, exponent = value.as_tuple()
    coefficient = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        text = coefficient + ("0" * exponent)
    else:
        point = len(coefficient) + exponent
        text = (
            ("0." + ("0" * (-point)) + coefficient)
            if point <= 0
            else coefficient[:point] + "." + coefficient[point:]
        )
        text = text.rstrip("0").rstrip(".")
    return f"-{text}" if sign else text


def _framed_material(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)


def _finite_decimal(
    value: object,
    name: str,
    *,
    allow_negative: bool = False,
) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            f"{name} must be an exact finite Decimal"
        )
    normalized = _ZERO if value == _ZERO else value
    if not allow_negative and normalized < _ZERO:
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            f"{name} must be nonnegative"
        )
    return normalized


def _utc(value: object, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise InconsistentVerifiedSnapshotPaperCycleResultError(
            f"{name} must be timezone-aware datetime"
        )
    return value.astimezone(UTC)


def _has_cause(error: BaseException, expected: type[BaseException]) -> bool:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, expected):
            return True
        current = current.__cause__
    return False
