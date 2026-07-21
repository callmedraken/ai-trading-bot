"""Deterministic collective risk evaluation for ordered proposal batches."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, Position, Symbol, TradeProposal
from trading_bot.portfolio import MetadataEntry
from trading_bot.risk.exceptions import (
    InconsistentPortfolioRiskBatchResultError,
    InvalidPortfolioRiskBatchRequestError,
    PortfolioRiskDecisionError,
    PortfolioRiskReservationError,
)
from trading_bot.risk.manager import RiskManager
from trading_bot.risk.models import (
    RiskContext,
    RiskDecision,
    RiskLimits,
    RiskOutcome,
)

_ZERO = Decimal("0")
_NAMESPACE = UUID("5bacbbb3-87c2-523a-bc4f-4502950a04bc")


def _decimal(value: Decimal, name: str, error_type: type[ValueError]) -> Decimal:
    if not isinstance(value, Decimal):
        raise error_type(f"{name} must be a Decimal")
    if not value.is_finite():
        raise error_type(f"{name} must be finite")
    return _ZERO if value == _ZERO else value


@dataclass(frozen=True, slots=True)
class PortfolioRiskPrice:
    symbol: Symbol
    price: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise InvalidPortfolioRiskBatchRequestError("symbol must be a Symbol")
        price = _decimal(self.price, "price", InvalidPortfolioRiskBatchRequestError)
        if price <= _ZERO:
            raise InvalidPortfolioRiskBatchRequestError("price must be positive")
        object.__setattr__(self, "price", price)


@dataclass(frozen=True, slots=True)
class PortfolioRiskPolicy:
    allow_sell_proceeds_for_later_buys: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.allow_sell_proceeds_for_later_buys, bool):
            raise InvalidPortfolioRiskBatchRequestError(
                "allow_sell_proceeds_for_later_buys must be a bool"
            )


@dataclass(frozen=True, slots=True)
class PortfolioRiskBatchRequest:
    request_id: UUID
    proposals: tuple[TradeProposal, ...]
    base_context: RiskContext
    prices: tuple[PortfolioRiskPrice, ...]
    risk_limits: RiskLimits
    policy: PortfolioRiskPolicy = PortfolioRiskPolicy()
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidPortfolioRiskBatchRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if not isinstance(self.base_context, RiskContext):
            raise error("base_context must be a RiskContext")
        if not isinstance(self.risk_limits, RiskLimits):
            raise error("risk_limits must be RiskLimits")
        if not isinstance(self.policy, PortfolioRiskPolicy):
            raise error("policy must be PortfolioRiskPolicy")
        try:
            proposals = tuple(self.proposals)
            prices = tuple(self.prices)
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("tuple-like request fields must be iterable") from caught
        if not all(isinstance(item, TradeProposal) for item in proposals):
            raise error("proposals must contain TradeProposal values")
        if not all(isinstance(item, PortfolioRiskPrice) for item in prices):
            raise error("prices must contain PortfolioRiskPrice values")
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.proposal_id for item in proposals}) != len(proposals):
            raise error("proposal IDs must be unique")
        if len({item.symbol for item in proposals}) != len(proposals):
            raise error("proposal symbols must be unique")
        if len({item.symbol for item in prices}) != len(prices):
            raise error("price symbols must be unique")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        if any(item.created_at != self.base_context.as_of for item in proposals):
            raise error("proposal timestamps must equal base_context.as_of")
        for symbol, position in self.base_context.positions.items():
            if symbol != position.symbol or position.quantity <= _ZERO:
                raise error("base position mapping is inconsistent")
        if not proposals:
            if prices:
                raise error("an empty proposal batch requires an empty price tuple")
        else:
            expected_symbols = set(self.base_context.positions) | {
                item.symbol for item in proposals
            }
            if {item.symbol for item in prices} != expected_symbols:
                raise error(
                    "price symbols must exactly equal starting and proposal symbols"
                )
            price_by_symbol = {item.symbol: item.price for item in prices}
            exposure = sum(
                (
                    position.quantity * price_by_symbol[symbol]
                    for symbol, position in self.base_context.positions.items()
                ),
                start=_ZERO,
            )
            if exposure != self.base_context.total_market_exposure:
                raise error("starting exposure does not reconcile with prices")
        if self.base_context.equity != (
            self.base_context.cash + self.base_context.total_market_exposure
        ):
            raise error("starting equity must equal cash plus exposure")
        object.__setattr__(self, "proposals", proposals)
        object.__setattr__(self, "prices", prices)
        object.__setattr__(self, "metadata", metadata)


class PortfolioRiskBatchStatus(StrEnum):
    ALL_APPROVED = "ALL_APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    ALL_REJECTED = "ALL_REJECTED"
    NO_ACTION = "NO_ACTION"


class PortfolioRiskDiagnosticCode(StrEnum):
    NO_ACTION = "NO_ACTION"
    SELL_PROCEEDS_WITHHELD = "SELL_PROCEEDS_WITHHELD"


@dataclass(frozen=True, slots=True)
class PortfolioRiskDiagnostic:
    code: PortfolioRiskDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, PortfolioRiskDiagnosticCode):
            raise InconsistentPortfolioRiskBatchResultError(
                "diagnostic code must be PortfolioRiskDiagnosticCode"
            )
        if not isinstance(self.message, str) or not self.message.strip():
            raise InconsistentPortfolioRiskBatchResultError(
                "diagnostic message must be nonblank"
            )


@dataclass(frozen=True, slots=True)
class PortfolioRiskEvaluation:
    ordinal: int
    context: RiskContext
    decision: RiskDecision
    risk_available_cash_before: Decimal
    risk_available_cash_after: Decimal
    economic_cash_after: Decimal
    symbol_quantity_before: Decimal
    symbol_quantity_after: Decimal
    reserved_notional: Decimal
    reserved_commission: Decimal
    resulting_exposure: Decimal

    def __post_init__(self) -> None:
        error = InconsistentPortfolioRiskBatchResultError
        if (
            not isinstance(self.ordinal, int)
            or isinstance(self.ordinal, bool)
            or self.ordinal < 0
        ):
            raise error("ordinal must be a nonnegative integer")
        if not isinstance(self.context, RiskContext) or not isinstance(
            self.decision, RiskDecision
        ):
            raise error("evaluation requires RiskContext and RiskDecision")
        for name in (
            "risk_available_cash_before",
            "risk_available_cash_after",
            "economic_cash_after",
            "symbol_quantity_before",
            "symbol_quantity_after",
            "reserved_notional",
            "reserved_commission",
            "resulting_exposure",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value < _ZERO:
                raise error(f"{name} must be a finite nonnegative Decimal")
        if self.decision.outcome is RiskOutcome.REJECTED and (
            self.reserved_notional != _ZERO
            or self.reserved_commission != _ZERO
            or self.risk_available_cash_before != self.risk_available_cash_after
            or self.symbol_quantity_before != self.symbol_quantity_after
            or self.context.total_market_exposure != self.resulting_exposure
        ):
            raise error("rejected evaluations must not change reservations")


@dataclass(frozen=True, slots=True)
class PortfolioRiskBatchResult:
    result_id: UUID
    request: PortfolioRiskBatchRequest
    status: PortfolioRiskBatchStatus
    evaluations: tuple[PortfolioRiskEvaluation, ...]
    final_positions: tuple[Position, ...]
    final_risk_available_cash: Decimal
    final_economic_cash: Decimal
    final_exposure: Decimal
    final_economic_equity: Decimal
    withheld_sell_proceeds: Decimal
    total_reserved_commissions: Decimal
    total_approved_buy_notional: Decimal
    total_approved_sell_notional: Decimal
    approved_count: int
    resized_count: int
    rejected_count: int
    diagnostics: tuple[PortfolioRiskDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentPortfolioRiskBatchResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, PortfolioRiskBatchRequest):
            raise error("request must be PortfolioRiskBatchRequest")
        if not isinstance(self.status, PortfolioRiskBatchStatus):
            raise error("status must be PortfolioRiskBatchStatus")
        try:
            evaluations = tuple(self.evaluations)
            positions = tuple(self.final_positions)
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("result collections must be iterable") from caught
        if not all(isinstance(item, PortfolioRiskEvaluation) for item in evaluations):
            raise error("evaluations contain invalid values")
        if not all(isinstance(item, Position) for item in positions):
            raise error("final_positions contain invalid values")
        if not all(isinstance(item, PortfolioRiskDiagnostic) for item in diagnostics):
            raise error("diagnostics contain invalid values")
        if tuple(item.ordinal for item in evaluations) != tuple(
            range(len(evaluations))
        ):
            raise error("evaluation ordinals must be sequential")
        if len(evaluations) != len(self.request.proposals):
            raise error("one evaluation is required per proposal")
        if any(
            evaluation.decision.proposal != proposal
            for evaluation, proposal in zip(
                evaluations, self.request.proposals, strict=True
            )
        ):
            raise error("evaluations must preserve proposal order")
        counts = (
            sum(item.decision.outcome is RiskOutcome.APPROVED for item in evaluations),
            sum(item.decision.outcome is RiskOutcome.RESIZED for item in evaluations),
            sum(item.decision.outcome is RiskOutcome.REJECTED for item in evaluations),
        )
        if counts != (self.approved_count, self.resized_count, self.rejected_count):
            raise error("decision counts do not reconcile")
        for name in ("approved_count", "resized_count", "rejected_count"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise error(f"{name} must be a nonnegative integer")
        if self.status is not _status(evaluations):
            raise error("status does not match decisions")
        for name in (
            "final_risk_available_cash",
            "final_economic_cash",
            "final_exposure",
            "final_economic_equity",
            "withheld_sell_proceeds",
            "total_reserved_commissions",
            "total_approved_buy_notional",
            "total_approved_sell_notional",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value < _ZERO:
                raise error(f"{name} must be a finite nonnegative Decimal")
        if self.final_economic_equity != self.final_economic_cash + self.final_exposure:
            raise error("economic equity must equal cash plus exposure")
        if self.final_economic_equity != (
            self.request.base_context.equity - self.total_reserved_commissions
        ):
            raise error("economic equity must equal base equity less commissions")
        accepted = tuple(
            item
            for item in evaluations
            if item.decision.outcome in {RiskOutcome.APPROVED, RiskOutcome.RESIZED}
        )
        expected_commissions = sum(
            (item.reserved_commission for item in accepted), start=_ZERO
        )
        expected_buys = sum(
            (
                item.reserved_notional
                for item in accepted
                if item.decision.proposal.side is OrderSide.BUY
            ),
            start=_ZERO,
        )
        expected_sells = sum(
            (
                item.reserved_notional
                for item in accepted
                if item.decision.proposal.side is OrderSide.SELL
            ),
            start=_ZERO,
        )
        if (
            self.total_reserved_commissions != expected_commissions
            or self.total_approved_buy_notional != expected_buys
            or self.total_approved_sell_notional != expected_sells
        ):
            raise error("aggregate reservation totals do not reconcile")
        expected_withheld = (
            _ZERO
            if self.request.policy.allow_sell_proceeds_for_later_buys
            else expected_sells
        )
        if self.withheld_sell_proceeds != expected_withheld:
            raise error("withheld sell proceeds do not reconcile")
        expected_economic_cash = (
            self.request.base_context.cash
            + expected_sells
            - expected_buys
            - expected_commissions
        )
        expected_risk_cash = (
            self.request.base_context.cash
            + (
                expected_sells
                if self.request.policy.allow_sell_proceeds_for_later_buys
                else _ZERO
            )
            - expected_buys
            - expected_commissions
        )
        if (
            self.final_economic_cash != expected_economic_cash
            or self.final_risk_available_cash != expected_risk_cash
        ):
            raise error("final cash totals do not reconcile")
        if evaluations:
            if (
                self.final_risk_available_cash
                != evaluations[-1].risk_available_cash_after
            ):
                raise error("final risk cash does not match evaluations")
            if self.final_economic_cash != evaluations[-1].economic_cash_after:
                raise error("final economic cash does not match evaluations")
            if self.final_exposure != evaluations[-1].resulting_exposure:
                raise error("final exposure does not match evaluations")
        expected_order = tuple(item.symbol for item in self.request.prices)
        actual_order = tuple(item.symbol for item in positions)
        if self.request.prices:
            if actual_order != tuple(
                s for s in expected_order if s in set(actual_order)
            ):
                raise error("final positions must follow price order")
            price_map = {item.symbol: item.price for item in self.request.prices}
            if (
                sum(
                    (item.quantity * price_map[item.symbol] for item in positions),
                    start=_ZERO,
                )
                != self.final_exposure
            ):
                raise error("final positions do not reconcile with exposure")
        expected_codes = []
        if not evaluations:
            expected_codes.append(PortfolioRiskDiagnosticCode.NO_ACTION)
        if self.withheld_sell_proceeds > _ZERO:
            expected_codes.append(PortfolioRiskDiagnosticCode.SELL_PROCEEDS_WITHHELD)
        if tuple(item.code for item in diagnostics) != tuple(expected_codes):
            raise error("diagnostic codes do not reconcile")
        if self.result_id != _result_id(self):
            raise error("result_id does not match deterministic identity")
        object.__setattr__(self, "evaluations", evaluations)
        object.__setattr__(self, "final_positions", positions)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(slots=True)
class _ReservationState:
    positions: dict[Symbol, Position]
    risk_cash: Decimal
    economic_cash: Decimal
    exposure: Decimal
    withheld: Decimal = _ZERO
    commissions: Decimal = _ZERO
    buy_notional: Decimal = _ZERO
    sell_notional: Decimal = _ZERO


class PortfolioRiskOrchestrator:
    """Evaluate proposals sequentially against provisional reservations."""

    def __init__(self, *, _manager_factory=RiskManager) -> None:  # type: ignore[no-untyped-def]
        self._manager_factory = _manager_factory

    def evaluate(self, request: PortfolioRiskBatchRequest) -> PortfolioRiskBatchResult:
        if not isinstance(request, PortfolioRiskBatchRequest):
            raise TypeError("request must be PortfolioRiskBatchRequest")
        price_map = {item.symbol: item.price for item in request.prices}
        state = _ReservationState(
            dict(request.base_context.positions),
            request.base_context.cash,
            request.base_context.cash,
            request.base_context.total_market_exposure,
        )
        manager = self._manager_factory(request.risk_limits)
        evaluations = []
        for ordinal, proposal in enumerate(request.proposals):
            price = price_map[proposal.symbol]
            before_cash = state.risk_cash
            before_quantity = (
                state.positions[proposal.symbol].quantity
                if proposal.symbol in state.positions
                else _ZERO
            )
            context = RiskContext(
                state.risk_cash,
                request.base_context.equity,
                state.positions,
                price,
                state.exposure,
                request.base_context.new_trading_enabled,
                request.base_context.as_of,
            )
            try:
                decision = manager.evaluate(proposal, context)
            except (TypeError, ValueError, ArithmeticError) as caught:
                raise PortfolioRiskDecisionError(
                    f"risk evaluation failed for proposal {proposal.proposal_id}"
                ) from caught
            self._validate_decision(proposal, context, decision)
            notional = _ZERO
            commission = _ZERO
            if decision.outcome in {RiskOutcome.APPROVED, RiskOutcome.RESIZED}:
                notional = decision.approved_quantity * price
                commission = request.risk_limits.estimated_commission
                self._apply(
                    request, state, proposal, decision.approved_quantity, notional
                )
                self._reconcile(request, state, price_map)
            after_quantity = (
                state.positions[proposal.symbol].quantity
                if proposal.symbol in state.positions
                else _ZERO
            )
            evaluations.append(
                PortfolioRiskEvaluation(
                    ordinal,
                    context,
                    decision,
                    before_cash,
                    state.risk_cash,
                    state.economic_cash,
                    before_quantity,
                    after_quantity,
                    notional,
                    commission,
                    state.exposure,
                )
            )
        evaluation_tuple = tuple(evaluations)
        diagnostics = self._diagnostics(request, state, evaluation_tuple)
        final_positions = self._final_positions(request, state)
        counts = (
            sum(item.decision.outcome is RiskOutcome.APPROVED for item in evaluations),
            sum(item.decision.outcome is RiskOutcome.RESIZED for item in evaluations),
            sum(item.decision.outcome is RiskOutcome.REJECTED for item in evaluations),
        )
        values = dict(
            request=request,
            status=_status(evaluation_tuple),
            evaluations=evaluation_tuple,
            final_positions=final_positions,
            final_risk_available_cash=state.risk_cash,
            final_economic_cash=state.economic_cash,
            final_exposure=state.exposure,
            final_economic_equity=state.economic_cash + state.exposure,
            withheld_sell_proceeds=state.withheld,
            total_reserved_commissions=state.commissions,
            total_approved_buy_notional=state.buy_notional,
            total_approved_sell_notional=state.sell_notional,
            approved_count=counts[0],
            resized_count=counts[1],
            rejected_count=counts[2],
            diagnostics=diagnostics,
        )
        provisional = object.__new__(PortfolioRiskBatchResult)
        for name, value in values.items():
            object.__setattr__(provisional, name, value)
        result_id = _result_id(provisional)
        return PortfolioRiskBatchResult(result_id=result_id, **values)

    @staticmethod
    def _validate_decision(
        proposal: TradeProposal, context: RiskContext, decision: RiskDecision
    ) -> None:
        if not isinstance(decision, RiskDecision):
            raise PortfolioRiskDecisionError("manager must return RiskDecision")
        quantity = decision.approved_quantity
        if (
            decision.proposal != proposal
            or decision.evaluated_at != context.as_of
            or not isinstance(quantity, Decimal)
            or not quantity.is_finite()
        ):
            raise PortfolioRiskDecisionError("risk decision does not match evaluation")
        valid = (
            decision.outcome is RiskOutcome.APPROVED
            and quantity == proposal.desired_quantity
            or decision.outcome is RiskOutcome.RESIZED
            and _ZERO < quantity < proposal.desired_quantity
            or decision.outcome is RiskOutcome.REJECTED
            and quantity == _ZERO
        )
        if not valid:
            raise PortfolioRiskDecisionError(
                "risk outcome and quantity are inconsistent"
            )

    @staticmethod
    def _apply(
        request: PortfolioRiskBatchRequest,
        state: _ReservationState,
        proposal: TradeProposal,
        quantity: Decimal,
        notional: Decimal,
    ) -> None:
        commission = request.risk_limits.estimated_commission
        current = state.positions.get(proposal.symbol)
        if proposal.side is OrderSide.SELL:
            if current is None or quantity > current.quantity:
                raise PortfolioRiskReservationError("accepted sell exceeds ownership")
            if notional < commission:
                raise PortfolioRiskReservationError(
                    "accepted sell notional cannot cover commission"
                )
            remaining = current.quantity - quantity
            if remaining:
                state.positions[proposal.symbol] = Position(
                    proposal.symbol, remaining, current.average_cost
                )
            else:
                del state.positions[proposal.symbol]
            state.exposure -= notional
            state.economic_cash += notional - commission
            state.sell_notional += notional
            if request.policy.allow_sell_proceeds_for_later_buys:
                state.risk_cash += notional - commission
            else:
                state.risk_cash -= commission
                state.withheld += notional
        else:
            state.risk_cash -= notional + commission
            state.economic_cash -= notional + commission
            state.exposure += notional
            state.buy_notional += notional
            old_quantity = current.quantity if current else _ZERO
            average_cost = current.average_cost if current else (notional / quantity)
            state.positions[proposal.symbol] = Position(
                proposal.symbol, old_quantity + quantity, average_cost
            )
        state.commissions += commission
        for value in (
            state.risk_cash,
            state.economic_cash,
            state.exposure,
            state.withheld,
            state.commissions,
        ):
            if not value.is_finite() or value < _ZERO:
                raise PortfolioRiskReservationError(
                    "reservation produced negative or nonfinite state"
                )

    @staticmethod
    def _reconcile(
        request: PortfolioRiskBatchRequest,
        state: _ReservationState,
        price_map: dict[Symbol, Decimal],
    ) -> None:
        exposure = sum(
            (
                position.quantity * price_map[symbol]
                for symbol, position in state.positions.items()
            ),
            start=_ZERO,
        )
        economic = (
            request.base_context.cash
            + state.sell_notional
            - state.buy_notional
            - state.commissions
        )
        risk_cash = (
            request.base_context.cash
            + (
                state.sell_notional
                if request.policy.allow_sell_proceeds_for_later_buys
                else _ZERO
            )
            - state.buy_notional
            - state.commissions
        )
        if (
            exposure != state.exposure
            or economic != state.economic_cash
            or risk_cash != state.risk_cash
        ):
            raise PortfolioRiskReservationError(
                "provisional reservation state does not reconcile"
            )

    @staticmethod
    def _final_positions(
        request: PortfolioRiskBatchRequest, state: _ReservationState
    ) -> tuple[Position, ...]:
        if request.prices:
            return tuple(
                state.positions[item.symbol]
                for item in request.prices
                if item.symbol in state.positions
            )
        return tuple(
            sorted(state.positions.values(), key=lambda item: str(item.symbol))
        )

    @staticmethod
    def _diagnostics(
        request: PortfolioRiskBatchRequest,
        state: _ReservationState,
        evaluations: tuple[PortfolioRiskEvaluation, ...],
    ) -> tuple[PortfolioRiskDiagnostic, ...]:
        values = []
        if not evaluations:
            values.append(
                PortfolioRiskDiagnostic(
                    PortfolioRiskDiagnosticCode.NO_ACTION,
                    "proposal batch contains no risk evaluations",
                )
            )
        if (
            not request.policy.allow_sell_proceeds_for_later_buys
            and state.withheld > _ZERO
        ):
            values.append(
                PortfolioRiskDiagnostic(
                    PortfolioRiskDiagnosticCode.SELL_PROCEEDS_WITHHELD,
                    "accepted sell proceeds were withheld from later buying power",
                )
            )
        return tuple(values)


def _status(
    evaluations: tuple[PortfolioRiskEvaluation, ...],
) -> PortfolioRiskBatchStatus:
    if not evaluations:
        return PortfolioRiskBatchStatus.NO_ACTION
    outcomes = tuple(item.decision.outcome for item in evaluations)
    if all(item is RiskOutcome.APPROVED for item in outcomes):
        return PortfolioRiskBatchStatus.ALL_APPROVED
    if all(item is RiskOutcome.REJECTED for item in outcomes):
        return PortfolioRiskBatchStatus.ALL_REJECTED
    return PortfolioRiskBatchStatus.PARTIALLY_APPROVED


def _canonical(value: Decimal) -> str:
    normalized = _ZERO if value == _ZERO else value.normalize()
    return format(normalized, "f")


def _request_fingerprint(request: PortfolioRiskBatchRequest) -> str:
    context = request.base_context
    parts = [
        str(request.request_id),
        context.as_of.isoformat(),
        _canonical(context.cash),
        _canonical(context.equity),
        _canonical(context.total_market_exposure),
        str(context.new_trading_enabled),
    ]
    for proposal in request.proposals:
        parts.extend(
            (
                str(proposal.proposal_id),
                str(proposal.symbol),
                proposal.side.value,
                _canonical(proposal.desired_quantity),
                proposal.created_at.isoformat(),
                proposal.reason,
                "none"
                if proposal.confidence is None
                else _canonical(proposal.confidence),
            )
        )
    position_map = context.positions
    ordered_symbols = (
        tuple(item.symbol for item in request.prices)
        if request.prices
        else tuple(sorted(position_map, key=str))
    )
    for symbol in ordered_symbols:
        if symbol in position_map:
            position = position_map[symbol]
            parts.extend(
                (
                    str(symbol),
                    _canonical(position.quantity),
                    _canonical(position.average_cost),
                )
            )
    for item in request.prices:
        parts.extend((str(item.symbol), _canonical(item.price)))
    limits = request.risk_limits
    for name in (
        "max_position_percent",
        "max_total_exposure_percent",
        "max_order_notional",
        "max_new_position_percent",
        "minimum_cash_reserve_percent",
        "allow_fractional_shares",
        "fractional_increment",
        "allow_buying",
        "allow_selling",
        "estimated_commission",
    ):
        value = getattr(limits, name)
        parts.append(
            "none"
            if value is None
            else _canonical(value)
            if isinstance(value, Decimal)
            else str(value)
        )
    parts.append(str(request.policy.allow_sell_proceeds_for_later_buys))
    parts.extend(f"{item.key}={item.value}" for item in request.metadata)
    return "|".join(parts)


def _result_id(result: PortfolioRiskBatchResult) -> UUID:
    parts = [_request_fingerprint(result.request), result.status.value]
    for item in result.evaluations:
        parts.extend(
            (
                str(item.ordinal),
                str(item.decision.proposal.proposal_id),
                item.decision.outcome.value,
                _canonical(item.decision.approved_quantity),
                ",".join(reason.code.value for reason in item.decision.reasons),
                _canonical(item.risk_available_cash_after),
                _canonical(item.economic_cash_after),
                _canonical(item.symbol_quantity_after),
                _canonical(item.resulting_exposure),
            )
        )
    for name in (
        "final_risk_available_cash",
        "final_economic_cash",
        "final_exposure",
        "final_economic_equity",
        "withheld_sell_proceeds",
        "total_reserved_commissions",
        "total_approved_buy_notional",
        "total_approved_sell_notional",
        "approved_count",
        "resized_count",
        "rejected_count",
    ):
        value = getattr(result, name)
        parts.append(_canonical(value) if isinstance(value, Decimal) else str(value))
    parts.append(",".join(item.code.value for item in result.diagnostics))
    return uuid5(_NAMESPACE, "|".join(parts))
