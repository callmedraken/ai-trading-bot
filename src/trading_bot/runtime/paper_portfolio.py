"""End-to-end deterministic orchestration for one paper portfolio cycle."""

from copy import Error as CopyError
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderType, Position, Symbol, TimeInForce
from trading_bot.domain._validation import normalize_utc
from trading_bot.execution import (
    ExecutionInstruction,
    OrderEngine,
    PaperFillApplicationBatchRequest,
    PaperFillApplicationBatchResult,
    PaperFillApplicationBatchStatus,
    PaperFillApplicationError,
    PaperFillApplier,
    PaperFillBatchRequest,
    PaperFillBatchResult,
    PaperFillGenerationError,
    PaperFillGenerator,
    PaperFillPolicy,
    PaperFillPrice,
    PaperOrderSubmitter,
    PaperSubmissionBatchRequest,
    PaperSubmissionBatchResult,
    PaperSubmissionOrchestrationError,
    PortfolioOrderBatchRequest,
    PortfolioOrderBatchResult,
    PortfolioOrderOrchestrationError,
    PortfolioOrderOrchestrator,
)
from trading_bot.execution.state_fingerprints import (
    canonical_decimal,
    engine_snapshot,
    engine_state_id,
    ledger_snapshot,
    ledger_state_id,
)
from trading_bot.ledger import PaperLedger
from trading_bot.portfolio import (
    MetadataEntry,
    PortfolioConstraints,
    PortfolioState,
    TargetPortfolio,
)
from trading_bot.rebalancing import (
    RebalanceAssumptions,
    RebalanceError,
    RebalancePlan,
    RebalancePlanner,
    RebalancePlanRequest,
    RebalanceProposalFactory,
    RebalanceProposalPolicy,
    RebalanceProposalRequest,
    RebalanceProposalResult,
)
from trading_bot.risk import (
    PortfolioRiskBatchRequest,
    PortfolioRiskBatchResult,
    PortfolioRiskOrchestrationError,
    PortfolioRiskOrchestrator,
    PortfolioRiskPolicy,
    PortfolioRiskPrice,
    RiskContext,
    RiskLimits,
)
from trading_bot.runtime.exceptions import (
    InconsistentPaperPortfolioCycleResultError,
    InconsistentPaperPortfolioRuntimeStateError,
    InvalidPaperPortfolioCycleRequestError,
    PaperPortfolioCycleEngineCopyError,
    PaperPortfolioCycleLedgerCopyError,
    PaperPortfolioFillApplicationError,
    PaperPortfolioFillGenerationError,
    PaperPortfolioOrderError,
    PaperPortfolioPlanningError,
    PaperPortfolioProposalError,
    PaperPortfolioRiskError,
    PaperPortfolioSubmissionError,
)

_ZERO = Decimal("0")
_VERSION = "paper-portfolio-runtime-v1"
_NAMESPACE = UUID("ca7ba2df-59bd-5ee4-87cd-a16967b965c2")
_CYCLE_METADATA_KEY = "paper_portfolio_cycle_id"


def _finite_positive(value: Decimal, name: str) -> Decimal:
    error = InvalidPaperPortfolioCycleRequestError
    if not isinstance(value, Decimal):
        raise error(f"{name} must be a Decimal")
    if not value.is_finite() or value <= _ZERO:
        raise error(f"{name} must be finite and positive")
    return value


@dataclass(frozen=True, slots=True)
class PaperPortfolioCyclePrice:
    symbol: Symbol
    risk_price: Decimal
    fill_reference_price: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise InvalidPaperPortfolioCycleRequestError("symbol must be a Symbol")
        object.__setattr__(
            self,
            "risk_price",
            _finite_positive(self.risk_price, "risk_price"),
        )
        object.__setattr__(
            self,
            "fill_reference_price",
            _finite_positive(self.fill_reference_price, "fill_reference_price"),
        )


@dataclass(frozen=True, slots=True)
class PaperPortfolioCycleInputs:
    state: PortfolioState
    target: TargetPortfolio
    rebalance_assumptions: RebalanceAssumptions
    portfolio_constraints: PortfolioConstraints | None
    proposal_policy: RebalanceProposalPolicy
    proposal_confidence: Decimal | None
    risk_limits: RiskLimits
    risk_policy: PortfolioRiskPolicy
    prices: tuple[PaperPortfolioCyclePrice, ...]
    fill_policy: PaperFillPolicy
    trading_enabled: bool
    submitted_at: datetime
    filled_at: datetime

    def __post_init__(self) -> None:
        error = InvalidPaperPortfolioCycleRequestError
        for name, expected in (
            ("state", PortfolioState),
            ("target", TargetPortfolio),
            ("rebalance_assumptions", RebalanceAssumptions),
            ("proposal_policy", RebalanceProposalPolicy),
            ("risk_limits", RiskLimits),
            ("risk_policy", PortfolioRiskPolicy),
            ("fill_policy", PaperFillPolicy),
        ):
            if not isinstance(getattr(self, name), expected):
                raise error(f"{name} must be {expected.__name__}")
        if self.portfolio_constraints is not None and not isinstance(
            self.portfolio_constraints, PortfolioConstraints
        ):
            raise error("portfolio_constraints must be PortfolioConstraints or None")
        if self.proposal_confidence is not None:
            confidence = self.proposal_confidence
            if (
                not isinstance(confidence, Decimal)
                or not confidence.is_finite()
                or not _ZERO <= confidence <= Decimal("1")
            ):
                raise error("proposal_confidence must be a finite Decimal from 0 to 1")
            object.__setattr__(
                self,
                "proposal_confidence",
                _ZERO if confidence == _ZERO else confidence,
            )
        if not isinstance(self.trading_enabled, bool):
            raise error("trading_enabled must be a bool")
        try:
            prices = tuple(self.prices)
        except TypeError as caught:
            raise error("prices must be iterable") from caught
        if not all(isinstance(item, PaperPortfolioCyclePrice) for item in prices):
            raise error("prices must contain PaperPortfolioCyclePrice values")
        if len({item.symbol for item in prices}) != len(prices):
            raise error("cycle price symbols must be unique")
        if self.state.symbols != self.target.symbols:
            raise error("state and target universes must match planner semantics")
        if self.state.as_of != self.target.as_of:
            raise error("state and target timestamps must match")
        if tuple(item.symbol for item in prices) != self.state.symbols:
            raise error("cycle prices must exactly match state universe order")
        for position, price in zip(self.state.positions, prices, strict=True):
            if price.risk_price != position.current_price:
                raise error("risk prices must equal state current prices")
        if not (
            self.rebalance_assumptions.fixed_commission
            == self.risk_limits.estimated_commission
            == self.fill_policy.fixed_commission
        ):
            raise error("planner, risk, and fill fixed commissions must match")
        try:
            submitted_at = normalize_utc(self.submitted_at, "submitted_at")
            filled_at = normalize_utc(self.filled_at, "filled_at")
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        if submitted_at < self.state.as_of or filled_at < submitted_at:
            raise error("timestamps must satisfy state <= submission <= fill")
        object.__setattr__(self, "prices", prices)
        object.__setattr__(self, "submitted_at", submitted_at)
        object.__setattr__(self, "filled_at", filled_at)


@dataclass(frozen=True, slots=True)
class PaperPortfolioCycleRequest:
    request_id: UUID
    inputs: PaperPortfolioCycleInputs
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidPaperPortfolioCycleRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if not isinstance(self.inputs, PaperPortfolioCycleInputs):
            raise error("inputs must be PaperPortfolioCycleInputs")
        try:
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("metadata must be iterable") from caught
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        if any(item.key.startswith("paper_portfolio_") for item in metadata):
            raise error("paper_portfolio_ metadata keys are reserved")
        object.__setattr__(self, "metadata", metadata)


class PaperPortfolioCycleStatus(StrEnum):
    APPLIED = "APPLIED"
    NO_ACTION = "NO_ACTION"


class PaperPortfolioCycleDiagnosticCode(StrEnum):
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class PaperPortfolioCycleDiagnostic:
    code: PaperPortfolioCycleDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        error = InconsistentPaperPortfolioCycleResultError
        if not isinstance(self.code, PaperPortfolioCycleDiagnosticCode):
            raise error("diagnostic code must be PaperPortfolioCycleDiagnosticCode")
        if not isinstance(self.message, str) or not self.message.strip():
            raise error("diagnostic message must be nonblank")


@dataclass(frozen=True, slots=True)
class PaperPortfolioCycleResult:
    result_id: UUID
    request: PaperPortfolioCycleRequest
    status: PaperPortfolioCycleStatus
    plan: RebalancePlan
    proposal_result: RebalanceProposalResult
    risk_result: PortfolioRiskBatchResult
    order_result: PortfolioOrderBatchResult
    submission_result: PaperSubmissionBatchResult
    fill_result: PaperFillBatchResult
    application_result: PaperFillApplicationBatchResult
    pre_engine_state_id: UUID
    pre_ledger_state_id: UUID
    post_engine_state_id: UUID
    post_ledger_state_id: UUID
    diagnostics: tuple[PaperPortfolioCycleDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentPaperPortfolioCycleResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, PaperPortfolioCycleRequest):
            raise error("request must be PaperPortfolioCycleRequest")
        if not isinstance(self.status, PaperPortfolioCycleStatus):
            raise error("status must be PaperPortfolioCycleStatus")
        for name, expected in (
            ("plan", RebalancePlan),
            ("proposal_result", RebalanceProposalResult),
            ("risk_result", PortfolioRiskBatchResult),
            ("order_result", PortfolioOrderBatchResult),
            ("submission_result", PaperSubmissionBatchResult),
            ("fill_result", PaperFillBatchResult),
            ("application_result", PaperFillApplicationBatchResult),
        ):
            if not isinstance(getattr(self, name), expected):
                raise error(f"{name} has an invalid type")
        for name in (
            "pre_engine_state_id",
            "pre_ledger_state_id",
            "post_engine_state_id",
            "post_ledger_state_id",
        ):
            if not isinstance(getattr(self, name), UUID):
                raise error(f"{name} must be a UUID")
        try:
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("diagnostics must be iterable") from caught
        if not all(
            isinstance(item, PaperPortfolioCycleDiagnostic) for item in diagnostics
        ):
            raise error("diagnostics contain invalid values")
        _validate_cycle_chain(self)
        expected_codes = (
            ()
            if self.status is PaperPortfolioCycleStatus.APPLIED
            else (PaperPortfolioCycleDiagnosticCode.NO_ACTION,)
        )
        if tuple(item.code for item in diagnostics) != expected_codes:
            raise error("diagnostics do not match cycle status")
        expected_id = _cycle_result_id(
            self.request,
            self.status,
            self.plan,
            self.proposal_result,
            self.risk_result,
            self.order_result,
            self.submission_result,
            self.fill_result,
            self.application_result,
            self.pre_engine_state_id,
            self.pre_ledger_state_id,
            self.post_engine_state_id,
            self.post_ledger_state_id,
            expected_codes,
        )
        if self.result_id != expected_id:
            raise error("result_id does not match deterministic identity")
        object.__setattr__(self, "diagnostics", diagnostics)


class PaperPortfolioRuntime:
    """Own authoritative state and run one complete deterministic paper cycle."""

    _planner_type = RebalancePlanner
    _proposal_factory_type = RebalanceProposalFactory
    _risk_orchestrator_type = PortfolioRiskOrchestrator
    _order_orchestrator_type = PortfolioOrderOrchestrator
    _submitter_type = PaperOrderSubmitter
    _fill_generator_type = PaperFillGenerator
    _fill_applier_type = PaperFillApplier

    def __init__(self, engine: OrderEngine, ledger: PaperLedger) -> None:
        if not isinstance(engine, OrderEngine):
            raise TypeError("engine must be an OrderEngine")
        if not isinstance(ledger, PaperLedger):
            raise TypeError("ledger must be a PaperLedger")
        self._engine = engine
        self._ledger = ledger

    @property
    def engine(self) -> OrderEngine:
        return self._engine

    @property
    def ledger(self) -> PaperLedger:
        return self._ledger

    def run_cycle(
        self, request: PaperPortfolioCycleRequest
    ) -> PaperPortfolioCycleResult:
        if not isinstance(request, PaperPortfolioCycleRequest):
            raise TypeError("request must be PaperPortfolioCycleRequest")
        _validate_runtime_state(request.inputs, self._ledger)
        metadata = _stage_metadata(request)
        inputs = request.inputs
        try:
            plan_request = RebalancePlanRequest(
                _stage_id(request, "rebalance-plan", _inputs_fingerprint(inputs)),
                inputs.state,
                inputs.target,
                inputs.rebalance_assumptions,
                inputs.portfolio_constraints,
                metadata,
            )
            plan = self._planner_type().plan(plan_request)
        except RebalanceError as caught:
            raise PaperPortfolioPlanningError("rebalance planning failed") from caught
        try:
            proposal_request = RebalanceProposalRequest(
                _stage_id(request, "rebalance-proposal", str(plan.plan_id)),
                plan,
                inputs.state.as_of,
                inputs.proposal_policy,
                inputs.proposal_confidence,
                metadata,
            )
            proposal_result = self._proposal_factory_type().create(proposal_request)
        except RebalanceError as caught:
            raise PaperPortfolioProposalError("proposal conversion failed") from caught
        risk_context, risk_prices = _risk_inputs(inputs, proposal_result)
        try:
            risk_request = PortfolioRiskBatchRequest(
                _stage_id(request, "portfolio-risk", str(proposal_result.result_id)),
                proposal_result.proposals,
                risk_context,
                risk_prices,
                inputs.risk_limits,
                inputs.risk_policy,
                metadata,
            )
            risk_result = self._risk_orchestrator_type().evaluate(risk_request)
        except PortfolioRiskOrchestrationError as caught:
            raise PaperPortfolioRiskError(
                "collective risk evaluation failed"
            ) from caught
        accepted_count = risk_result.approved_count + risk_result.resized_count
        pre_engine_id = engine_state_id(engine_snapshot(self._engine))
        pre_ledger_id = ledger_state_id(ledger_snapshot(self._ledger))
        if accepted_count:
            try:
                local_engine = deepcopy(self._engine)
            except (CopyError, TypeError, ValueError, RuntimeError) as caught:
                raise PaperPortfolioCycleEngineCopyError(
                    "runtime engine copy failed"
                ) from caught
            try:
                local_ledger = deepcopy(self._ledger)
            except (CopyError, TypeError, ValueError, RuntimeError) as caught:
                raise PaperPortfolioCycleLedgerCopyError(
                    "runtime ledger copy failed"
                ) from caught
        else:
            local_engine = self._engine
            local_ledger = self._ledger
        try:
            order_request = PortfolioOrderBatchRequest(
                _stage_id(request, "portfolio-order", str(risk_result.result_id)),
                risk_result,
                ExecutionInstruction(
                    OrderType.MARKET, TimeInForce.DAY, inputs.state.as_of
                ),
                metadata,
            )
            orderer = self._order_orchestrator_type(local_engine)
            order_result = orderer.create(order_request)
        except PortfolioOrderOrchestrationError as caught:
            raise PaperPortfolioOrderError(
                "portfolio order creation failed"
            ) from caught
        local_engine = orderer.engine
        try:
            submission_request = PaperSubmissionBatchRequest(
                _stage_id(request, "paper-submission", str(order_result.result_id)),
                order_result,
                inputs.submitted_at,
                metadata,
            )
            submitter = self._submitter_type(local_engine)
            submission_result = submitter.submit(submission_request)
        except PaperSubmissionOrchestrationError as caught:
            raise PaperPortfolioSubmissionError("paper submission failed") from caught
        local_engine = submitter.engine
        fill_prices_by_symbol = {
            item.symbol: item.fill_reference_price for item in inputs.prices
        }
        try:
            fill_request = PaperFillBatchRequest(
                _stage_id(request, "paper-fill", str(submission_result.result_id)),
                submission_result,
                inputs.filled_at,
                tuple(
                    PaperFillPrice(
                        order.request.order_id,
                        fill_prices_by_symbol[order.request.symbol],
                    )
                    for order in submission_result.orders
                ),
                inputs.fill_policy,
                metadata,
            )
            fill_result = self._fill_generator_type().generate(fill_request)
        except PaperFillGenerationError as caught:
            raise PaperPortfolioFillGenerationError(
                "paper fill generation failed"
            ) from caught
        try:
            application_request = PaperFillApplicationBatchRequest(
                _stage_id(
                    request, "paper-fill-application", str(fill_result.result_id)
                ),
                fill_result,
                metadata,
            )
            applier = self._fill_applier_type(local_engine, local_ledger)
            application_result = applier.apply(application_request)
        except PaperFillApplicationError as caught:
            raise PaperPortfolioFillApplicationError(
                "atomic paper fill application failed"
            ) from caught
        final_engine = applier.engine
        final_ledger = applier.ledger
        post_engine_id = engine_state_id(engine_snapshot(final_engine))
        post_ledger_id = ledger_state_id(ledger_snapshot(final_ledger))
        status = (
            PaperPortfolioCycleStatus.APPLIED
            if application_result.status is PaperFillApplicationBatchStatus.APPLIED
            else PaperPortfolioCycleStatus.NO_ACTION
        )
        diagnostics = (
            ()
            if status is PaperPortfolioCycleStatus.APPLIED
            else (
                PaperPortfolioCycleDiagnostic(
                    PaperPortfolioCycleDiagnosticCode.NO_ACTION,
                    "cycle produced no authoritative state change",
                ),
            )
        )
        result = _build_cycle_result(
            request,
            status,
            plan,
            proposal_result,
            risk_result,
            order_result,
            submission_result,
            fill_result,
            application_result,
            pre_engine_id,
            pre_ledger_id,
            post_engine_id,
            post_ledger_id,
            diagnostics,
        )
        if status is PaperPortfolioCycleStatus.NO_ACTION:
            return result
        self._engine = final_engine
        self._ledger = final_ledger
        return result


def _stage_metadata(request: PaperPortfolioCycleRequest) -> tuple[MetadataEntry, ...]:
    return request.metadata + (
        MetadataEntry(_CYCLE_METADATA_KEY, str(request.request_id)),
    )


def _stage_id(request: PaperPortfolioCycleRequest, stage: str, upstream: str) -> UUID:
    return uuid5(
        _NAMESPACE,
        "|".join((_VERSION, str(request.request_id), stage, upstream)),
    )


def _position_material(position) -> str:  # type: ignore[no-untyped-def]
    return ":".join(
        (
            str(position.symbol),
            canonical_decimal(position.quantity),
            canonical_decimal(position.average_cost),
            canonical_decimal(position.current_price),
        )
    )


def _inputs_fingerprint(inputs: PaperPortfolioCycleInputs) -> str:
    constraints = inputs.portfolio_constraints
    constraint_material = (
        "none"
        if constraints is None
        else ":".join(
            (
                canonical_decimal(constraints.minimum_cash_weight),
                canonical_decimal(constraints.maximum_cash_weight),
                canonical_decimal(constraints.maximum_position_weight),
                "none"
                if constraints.maximum_one_way_rebalance_turnover is None
                else canonical_decimal(constraints.maximum_one_way_rebalance_turnover),
                "none"
                if constraints.minimum_position_weight is None
                else canonical_decimal(constraints.minimum_position_weight),
                str(constraints.long_only),
                str(constraints.allow_leverage),
            )
        )
    )
    assumptions = inputs.rebalance_assumptions
    limits = inputs.risk_limits
    return "|".join(
        (
            _VERSION,
            inputs.state.as_of.isoformat(),
            canonical_decimal(inputs.state.cash),
            canonical_decimal(inputs.state.equity),
            *(f"state={_position_material(item)}" for item in inputs.state.positions),
            str(inputs.target.target_id),
            canonical_decimal(inputs.target.cash_weight),
            *(
                f"target={item.symbol}:{canonical_decimal(item.weight)}"
                for item in inputs.target.allocations
            ),
            inputs.target.source.value,
            "none" if inputs.target.source_name is None else inputs.target.source_name,
            *(
                f"target-meta={item.key}={item.value}"
                for item in inputs.target.metadata
            ),
            canonical_decimal(assumptions.fixed_commission),
            str(assumptions.allow_fractional_quantities),
            canonical_decimal(assumptions.quantity_increment),
            canonical_decimal(assumptions.minimum_trade_notional),
            canonical_decimal(assumptions.minimum_trade_quantity),
            canonical_decimal(assumptions.target_weight_tolerance),
            canonical_decimal(assumptions.additional_execution_cash_buffer),
            str(assumptions.use_planned_sell_proceeds),
            constraint_material,
            str(inputs.proposal_policy.allow_partial_plans),
            "none"
            if inputs.proposal_confidence is None
            else canonical_decimal(inputs.proposal_confidence),
            canonical_decimal(limits.max_position_percent),
            canonical_decimal(limits.max_total_exposure_percent),
            "none"
            if limits.max_order_notional is None
            else canonical_decimal(limits.max_order_notional),
            "none"
            if limits.max_new_position_percent is None
            else canonical_decimal(limits.max_new_position_percent),
            canonical_decimal(limits.minimum_cash_reserve_percent),
            str(limits.allow_fractional_shares),
            canonical_decimal(limits.fractional_increment),
            str(limits.allow_buying),
            str(limits.allow_selling),
            canonical_decimal(limits.estimated_commission),
            str(inputs.risk_policy.allow_sell_proceeds_for_later_buys),
            *(
                f"price={item.symbol}:{canonical_decimal(item.risk_price)}:{canonical_decimal(item.fill_reference_price)}"
                for item in inputs.prices
            ),
            canonical_decimal(inputs.fill_policy.slippage_basis_points),
            canonical_decimal(inputs.fill_policy.fixed_commission),
            str(inputs.trading_enabled),
            inputs.submitted_at.isoformat(),
            inputs.filled_at.isoformat(),
        )
    )


def _request_fingerprint(request: PaperPortfolioCycleRequest) -> str:
    return "|".join(
        (
            _inputs_fingerprint(request.inputs),
            str(request.request_id),
            *(f"{item.key}={item.value}" for item in request.metadata),
        )
    )


def _validate_runtime_state(
    inputs: PaperPortfolioCycleInputs, ledger: PaperLedger
) -> None:
    error = InconsistentPaperPortfolioRuntimeStateError
    if not ledger.cash.is_finite() or ledger.cash < _ZERO:
        raise error("ledger cash must be finite and nonnegative")
    if not ledger.realized_profit_loss.is_finite():
        raise error("ledger realized P&L must be finite")
    if inputs.state.cash != ledger.cash:
        raise error("cycle state cash must equal authoritative ledger cash")
    state_positions = {
        item.symbol: item for item in inputs.state.positions if item.quantity > _ZERO
    }
    ledger_positions = dict(ledger.positions)
    if set(state_positions) != set(ledger_positions):
        raise error("cycle state holdings must exactly match ledger holdings")
    for symbol, ledger_position in ledger_positions.items():
        state_position = state_positions[symbol]
        if (
            not ledger_position.quantity.is_finite()
            or not ledger_position.average_cost.is_finite()
            or state_position.quantity != ledger_position.quantity
            or state_position.average_cost != ledger_position.average_cost
        ):
            raise error("cycle state position does not equal ledger position")
    exposure = sum(
        (
            position.quantity * price.risk_price
            for position, price in zip(
                inputs.state.positions, inputs.prices, strict=True
            )
        ),
        start=_ZERO,
    )
    if inputs.state.equity != inputs.state.cash + exposure:
        raise error("cycle equity must equal cash plus risk-priced exposure")


def _risk_inputs(
    inputs: PaperPortfolioCycleInputs,
    proposal_result: RebalanceProposalResult,
) -> tuple[RiskContext, tuple[PortfolioRiskPrice, ...]]:
    positions = {
        item.symbol: Position(item.symbol, item.quantity, item.average_cost)
        for item in inputs.state.positions
        if item.quantity > _ZERO
    }
    price_by_symbol = {item.symbol: item.risk_price for item in inputs.prices}
    exposure = sum(
        (
            position.quantity * price_by_symbol[symbol]
            for symbol, position in positions.items()
        ),
        start=_ZERO,
    )
    context = RiskContext(
        inputs.state.cash,
        inputs.state.equity,
        positions,
        None,
        exposure,
        inputs.trading_enabled,
        inputs.state.as_of,
    )
    if not proposal_result.proposals:
        return context, ()
    required = set(positions) | {item.symbol for item in proposal_result.proposals}
    prices = tuple(
        PortfolioRiskPrice(item.symbol, item.risk_price)
        for item in inputs.prices
        if item.symbol in required
    )
    return context, prices


def _validate_cycle_chain(result: PaperPortfolioCycleResult) -> None:
    error = InconsistentPaperPortfolioCycleResultError
    request = result.request
    inputs = request.inputs
    metadata = _stage_metadata(request)
    if (
        result.plan.request.request_id
        != _stage_id(request, "rebalance-plan", _inputs_fingerprint(inputs))
        or result.plan.request.state != inputs.state
        or result.plan.request.target != inputs.target
        or result.plan.request.metadata != metadata
    ):
        raise error("rebalance plan does not match cycle input")
    if (
        result.proposal_result.request.plan != result.plan
        or result.proposal_result.request.request_id
        != _stage_id(request, "rebalance-proposal", str(result.plan.plan_id))
        or result.proposal_result.request.metadata != metadata
        or result.proposal_result.request.proposal_created_at != inputs.state.as_of
    ):
        raise error("proposal stage does not chain from the plan")
    if (
        result.risk_result.request.proposals != result.proposal_result.proposals
        or result.risk_result.request.request_id
        != _stage_id(request, "portfolio-risk", str(result.proposal_result.result_id))
        or result.risk_result.request.metadata != metadata
        or result.risk_result.request.base_context.as_of != inputs.state.as_of
    ):
        raise error("risk stage does not chain from proposals")
    if (
        result.order_result.request.risk_batch != result.risk_result
        or result.order_result.request.request_id
        != _stage_id(request, "portfolio-order", str(result.risk_result.result_id))
        or result.order_result.request.metadata != metadata
        or result.order_result.request.instruction.created_at != inputs.state.as_of
    ):
        raise error("order stage does not chain from risk")
    if (
        result.submission_result.request.order_batch != result.order_result
        or result.submission_result.request.request_id
        != _stage_id(request, "paper-submission", str(result.order_result.result_id))
        or result.submission_result.request.metadata != metadata
        or result.submission_result.request.submitted_at != inputs.submitted_at
    ):
        raise error("submission stage does not chain from orders")
    if (
        result.fill_result.request.submission_batch != result.submission_result
        or result.fill_result.request.request_id
        != _stage_id(request, "paper-fill", str(result.submission_result.result_id))
        or result.fill_result.request.metadata != metadata
        or result.fill_result.request.filled_at != inputs.filled_at
    ):
        raise error("fill stage does not chain from submission")
    if (
        result.application_result.request.fill_batch != result.fill_result
        or result.application_result.request.request_id
        != _stage_id(
            request, "paper-fill-application", str(result.fill_result.result_id)
        )
        or result.application_result.request.metadata != metadata
    ):
        raise error("application stage does not chain from fills")
    accepted = result.risk_result.approved_count + result.risk_result.resized_count
    counts = (
        accepted,
        len(result.order_result.orders),
        len(result.submission_result.orders),
        len(result.fill_result.fills),
        len(result.application_result.evaluations),
    )
    if len(set(counts)) != 1:
        raise error("accepted, order, submission, fill, and application counts differ")
    order_ids = tuple(item.request.order_id for item in result.order_result.orders)
    if (
        tuple(item.request.order_id for item in result.submission_result.orders)
        != order_ids
        or tuple(item.order_id for item in result.fill_result.fills) != order_ids
        or tuple(
            item.updated_order.request.order_id
            for item in result.application_result.evaluations
        )
        != order_ids
    ):
        raise error("source order changed across cycle stages")
    if (
        result.post_engine_state_id != result.application_result.post_engine_state_id
        or (
            result.post_ledger_state_id
            != result.application_result.post_ledger_state_id
        )
    ):
        raise error("cycle post-state IDs must equal application post-state IDs")
    if result.status is PaperPortfolioCycleStatus.APPLIED:
        if (
            not counts[0]
            or result.application_result.status
            is not PaperFillApplicationBatchStatus.APPLIED
        ):
            raise error("APPLIED cycle requires applied fills")
    elif (
        counts[0]
        or result.application_result.status
        is not PaperFillApplicationBatchStatus.NO_ACTION
        or result.pre_engine_state_id != result.post_engine_state_id
        or result.pre_ledger_state_id != result.post_ledger_state_id
    ):
        raise error("NO_ACTION cycle must preserve empty state")


def _cycle_result_id(
    request,
    status,
    plan,
    proposal_result,
    risk_result,
    order_result,
    submission_result,
    fill_result,
    application_result,
    pre_engine_id,
    pre_ledger_id,
    post_engine_id,
    post_ledger_id,
    codes,
) -> UUID:  # type: ignore[no-untyped-def]
    material = "|".join(
        (
            _VERSION,
            _request_fingerprint(request),
            str(plan.plan_id),
            str(proposal_result.result_id),
            str(risk_result.result_id),
            str(order_result.result_id),
            str(submission_result.result_id),
            str(fill_result.result_id),
            str(application_result.result_id),
            str(pre_engine_id),
            str(pre_ledger_id),
            str(post_engine_id),
            str(post_ledger_id),
            status.value,
            *(item.value for item in codes),
        )
    )
    return uuid5(_NAMESPACE, material)


def _build_cycle_result(
    request,
    status,
    plan,
    proposal_result,
    risk_result,
    order_result,
    submission_result,
    fill_result,
    application_result,
    pre_engine_id,
    pre_ledger_id,
    post_engine_id,
    post_ledger_id,
    diagnostics,
) -> PaperPortfolioCycleResult:  # type: ignore[no-untyped-def]
    codes = tuple(item.code for item in diagnostics)
    return PaperPortfolioCycleResult(
        _cycle_result_id(
            request,
            status,
            plan,
            proposal_result,
            risk_result,
            order_result,
            submission_result,
            fill_result,
            application_result,
            pre_engine_id,
            pre_ledger_id,
            post_engine_id,
            post_ledger_id,
            codes,
        ),
        request,
        status,
        plan,
        proposal_result,
        risk_result,
        order_result,
        submission_result,
        fill_result,
        application_result,
        pre_engine_id,
        pre_ledger_id,
        post_engine_id,
        post_ledger_id,
        diagnostics,
    )
