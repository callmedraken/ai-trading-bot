"""Deterministic financial evaluation for a single simulated-paper cycle."""

from __future__ import annotations

from decimal import Context, Decimal, localcontext
from uuid import UUID, uuid5

from trading_bot.desktop_paper.models import (
    PaperAccountState,
    PaperControlState,
    PaperCycleInput,
    PaperCycleKind,
    PaperCycleResult,
    PaperRuntimePolicy,
)
from trading_bot.domain import (
    OrderFill,
    OrderSide,
    OrderType,
    TimeInForce,
    TradeProposal,
)
from trading_bot.execution import ExecutionInstruction, OrderEngine
from trading_bot.ledger import PaperLedger
from trading_bot.risk import RiskContext, RiskLimits, RiskManager, RiskOutcome

_FINANCIAL_ID_NAMESPACE = UUID("96bb6607-92c9-53d9-a2b7-d1709a7da36f")
_ARITHMETIC_CONTEXT = Context(prec=1024, Emax=999_999, Emin=-999_999)


def financial_identity(name: str, semantic_material: str) -> UUID:
    """Return a versioned stable identity for an explicit semantic role."""
    if not isinstance(name, str) or not name:
        raise ValueError("identity name must be nonblank")
    if not isinstance(semantic_material, str):
        raise TypeError("semantic_material must be a string")
    return uuid5(
        _FINANCIAL_ID_NAMESPACE,
        f"desktop-paper-financial/v1|{name}|{semantic_material}",
    )


def cycle_identity(
    account_id: UUID, source_lane: str, symbol: str, execution_session_id: str
) -> UUID:
    """Identify the account/source/symbol/session slot independent of config."""
    return financial_identity(
        "slot",
        "|".join((str(account_id), source_lane, symbol, execution_session_id)),
    )


class PaperCycleEngine:
    """Apply existing risk, order, and ledger authority to one source session."""

    def __init__(
        self,
        *,
        account_id: UUID,
        source_lane: str,
        policy: PaperRuntimePolicy,
        configuration_revision_id: UUID,
    ) -> None:
        if not isinstance(account_id, UUID):
            raise TypeError("account_id must be a UUID")
        if not isinstance(source_lane, str) or not source_lane:
            raise ValueError("source_lane must be nonblank")
        if not isinstance(policy, PaperRuntimePolicy):
            raise TypeError("policy must be a PaperRuntimePolicy")
        if not isinstance(configuration_revision_id, UUID):
            raise TypeError("configuration_revision_id must be a UUID")
        self._account_id = account_id
        self._source_lane = source_lane
        self._policy = policy
        self._configuration_revision_id = configuration_revision_id
        self._risk_manager = RiskManager(_risk_limits(policy))

    def process(
        self,
        cycle: PaperCycleInput,
        ledger: PaperLedger,
        control: PaperControlState,
    ) -> PaperCycleResult:
        """Evaluate and apply one cycle to the caller's transaction-local ledger."""
        with localcontext(_ARITHMETIC_CONTEXT):
            return self._process(cycle, ledger, control)

    def _process(
        self,
        cycle: PaperCycleInput,
        ledger: PaperLedger,
        control: PaperControlState,
    ) -> PaperCycleResult:
        if not isinstance(cycle, PaperCycleInput):
            raise TypeError("cycle must be a PaperCycleInput")
        if not isinstance(ledger, PaperLedger):
            raise TypeError("ledger must be a PaperLedger")
        if not isinstance(control, PaperControlState):
            raise TypeError("control must be a PaperControlState")
        slot_id = cycle_identity(
            self._account_id,
            self._source_lane,
            cycle.symbol.value,
            cycle.execution_session_id,
        )
        if cycle.warmup:
            return self._result(
                slot_id,
                PaperCycleKind.WARMUP,
                cycle,
                ledger,
                control,
                diagnostic=cycle.no_signal_reason or "INSUFFICIENT_HISTORY",
            )
        if cycle.proposal is None:
            return self._result(
                slot_id,
                PaperCycleKind.NO_SIGNAL,
                cycle,
                ledger,
                control,
                diagnostic=cycle.no_signal_reason,
            )

        proposal = _deterministic_proposal(cycle.proposal, slot_id)
        fill_price = _synthetic_fill_price(
            cycle.observation_open, proposal.side, self._policy.adverse_slippage_bps
        )
        risk_context = _risk_context(
            ledger=ledger,
            cycle=cycle,
            fill_price=fill_price,
            new_buys_enabled=control.new_buys_enabled,
            side=proposal.side,
        )
        decision = self._risk_manager.evaluate(proposal, risk_context)
        if decision.outcome is RiskOutcome.REJECTED:
            return self._result(
                slot_id,
                PaperCycleKind.RISK_REJECTED,
                cycle,
                ledger,
                control,
                risk_context=risk_context,
                risk_decision=decision,
            )

        semantic_slot = str(slot_id)
        order_id = financial_identity("order", semantic_slot)
        created_event_id = financial_identity("order-created-event", semantic_slot)
        submitted_event_id = financial_identity("order-submitted-event", semantic_slot)
        fill_id = financial_identity("fill", semantic_slot)
        filled_event_id = financial_identity("fill-event", semantic_slot)
        engine = OrderEngine()
        order = engine.create_order(
            decision,
            ExecutionInstruction(
                order_type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
                created_at=cycle.executed_at,
            ),
            order_id=order_id,
            event_id=created_event_id,
        )
        engine.submit_order(
            order_id,
            cycle.executed_at,
            event_id=submitted_event_id,
        )
        fill = OrderFill(
            fill_id=fill_id,
            order_id=order_id,
            symbol=proposal.symbol,
            side=proposal.side,
            quantity=decision.approved_quantity,
            price=fill_price,
            commission=self._policy.fill_commission,
            filled_at=cycle.executed_at,
        )
        order = engine.apply_fill(fill, event_id=filled_event_id)
        with localcontext(_ARITHMETIC_CONTEXT):
            ledger.apply_fill(fill)
        return self._result(
            slot_id,
            PaperCycleKind.FILLED,
            cycle,
            ledger,
            control,
            risk_context=risk_context,
            risk_decision=decision,
            order=order,
            fill=fill,
            order_events=engine.get_events(order_id),
        )

    def _result(
        self,
        cycle_id: UUID,
        kind: PaperCycleKind,
        cycle: PaperCycleInput,
        ledger: PaperLedger,
        control: PaperControlState,
        *,
        risk_context: RiskContext | None = None,
        risk_decision=None,
        order=None,
        fill=None,
        order_events=(),
        diagnostic: str | None = None,
    ) -> PaperCycleResult:
        return PaperCycleResult(
            cycle_id=cycle_id,
            kind=kind,
            input=cycle,
            configuration_revision_id=self._configuration_revision_id,
            risk_context=risk_context,
            risk_decision=risk_decision,
            order=order,
            fill=fill,
            order_events=tuple(order_events),
            account=_account_state(ledger, cycle),
            cursor_index=cycle.execution_index,
            control=control,
            diagnostic=diagnostic,
        )


def _risk_limits(policy: PaperRuntimePolicy) -> RiskLimits:
    return RiskLimits(
        max_position_percent=policy.max_position_percent,
        max_total_exposure_percent=policy.max_total_exposure_percent,
        max_order_notional=policy.max_order_notional,
        max_new_position_percent=policy.max_new_position_percent,
        minimum_cash_reserve_percent=policy.minimum_cash_reserve_percent,
        allow_fractional_shares=policy.allow_fractional_shares,
        allow_buying=policy.allow_buying,
        allow_selling=policy.allow_selling,
        estimated_commission=policy.estimated_commission,
    )


def _deterministic_proposal(proposal: TradeProposal, cycle_id: UUID) -> TradeProposal:
    return TradeProposal(
        proposal_id=financial_identity("proposal", str(cycle_id)),
        symbol=proposal.symbol,
        side=proposal.side,
        desired_quantity=proposal.desired_quantity,
        created_at=proposal.created_at,
        reason=proposal.reason,
        confidence=proposal.confidence,
    )


def _synthetic_fill_price(
    observation_open: Decimal, side: OrderSide, adverse_slippage_bps: Decimal
) -> Decimal:
    with localcontext(_ARITHMETIC_CONTEXT):
        slippage = adverse_slippage_bps / Decimal("10000")
        multiplier = (
            Decimal("1") + slippage
            if side is OrderSide.BUY
            else Decimal("1") - slippage
        )
        price = observation_open * multiplier
    if price <= Decimal("0"):
        raise ValueError("synthetic execution price must be positive")
    return price


def _risk_context(
    *,
    ledger: PaperLedger,
    cycle: PaperCycleInput,
    fill_price: Decimal,
    new_buys_enabled: bool,
    side: OrderSide,
) -> RiskContext:
    positions = ledger.positions
    marks = dict(cycle.current_marks or {})
    marks[cycle.symbol] = fill_price
    complete = all(symbol in marks for symbol in positions)
    if complete:
        account_snapshot = ledger.create_account_snapshot(marks, cycle.executed_at)
        equity = account_snapshot.equity
        total_exposure = account_snapshot.positions_market_value
    else:
        with localcontext(_ARITHMETIC_CONTEXT):
            held_cost = sum(
                (
                    position.quantity * position.average_cost
                    for position in positions.values()
                ),
                Decimal("0"),
            )
            equity = ledger.cash + held_cost
            total_exposure = held_cost
    if equity <= Decimal("0"):
        raise ValueError("PAPER_ACCOUNT_EQUITY_NONPOSITIVE")
    current_price = fill_price
    if not complete and side is OrderSide.BUY:
        # Existing portfolio exposure is unmarked; let RiskManager reject the
        # buy through its existing unavailable-price reason path.
        current_price = None
    return RiskContext(
        cash=ledger.cash,
        equity=equity,
        positions=positions,
        current_price=current_price,
        total_market_exposure=total_exposure,
        new_trading_enabled=new_buys_enabled,
        as_of=cycle.executed_at,
    )


def _account_state(ledger: PaperLedger, cycle: PaperCycleInput) -> PaperAccountState:
    positions = ledger.positions
    marks = dict(cycle.current_marks or {})
    complete = all(symbol in marks for symbol in positions)
    if complete:
        snapshot = ledger.create_account_snapshot(marks, cycle.executed_at)
        marked_equity = snapshot.equity
        unrealized = snapshot.unrealized_profit_loss
    else:
        marked_equity = None
        unrealized = None
    return PaperAccountState(
        cash=ledger.cash,
        positions=positions,
        realized_profit_loss=ledger.realized_profit_loss,
        marked_equity=marked_equity,
        unrealized_profit_loss=unrealized,
        fills=ledger.fills,
    )
