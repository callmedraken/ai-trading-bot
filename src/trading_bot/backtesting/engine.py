"""Deterministic single-symbol daily-bar backtest orchestration."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.backtesting.exceptions import (
    ActiveOrderError,
    BacktestAtomicityError,
    BacktestCalendarAlignmentError,
    BacktestExecutionError,
    InsufficientHistoricalDataError,
    StrategyContractError,
)
from trading_bot.backtesting.models import (
    BacktestConfig,
    BacktestContext,
    BacktestResult,
    BacktestStep,
    BacktestUnexecutedReason,
)
from trading_bot.backtesting.strategy import BacktestStrategy
from trading_bot.domain import Order, OrderFill, OrderSide, OrderStatus, TradeProposal
from trading_bot.domain.enums import OrderType, TimeInForce
from trading_bot.execution import ExecutionInstruction, OrderEngine
from trading_bot.ledger import PaperLedger
from trading_bot.market_calendar import MarketCalendar, TradingSession
from trading_bot.market_data import HistoricalDataProvider
from trading_bot.risk import RiskContext, RiskManager, RiskOutcome

_NEW_YORK = ZoneInfo("America/New_York")
_ACTIVE_STATUSES = {
    OrderStatus.PENDING,
    OrderStatus.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED,
}


class BacktestEngine:
    """Coordinate existing components without assuming broker connectivity."""

    def __init__(
        self,
        data_provider: HistoricalDataProvider,
        market_calendar: MarketCalendar,
    ) -> None:
        if not hasattr(data_provider, "get_bars"):
            raise TypeError("data_provider must implement HistoricalDataProvider")
        for method_name in (
            "is_trading_session",
            "next_session",
            "previous_session",
            "sessions_between",
        ):
            if not hasattr(market_calendar, method_name):
                raise TypeError("market_calendar must implement MarketCalendar")
        self._data_provider = data_provider
        self._market_calendar = market_calendar

    def run(self, config: BacktestConfig, strategy: BacktestStrategy) -> BacktestResult:
        """Run a fresh deterministic backtest and return its immutable audit."""
        if not isinstance(config, BacktestConfig):
            raise TypeError("config must be a BacktestConfig")
        if not hasattr(strategy, "evaluate"):
            raise TypeError("strategy must implement BacktestStrategy")

        data = self._data_provider.get_bars(config.data_request)
        bars = data.bars
        if not bars:
            raise InsufficientHistoricalDataError(
                "the historical-data provider returned no bars"
            )
        sessions = self._validate_calendar_alignment(config, bars)

        ledger = PaperLedger(config.starting_cash)
        order_engine = OrderEngine()
        risk_manager = RiskManager(config.risk_limits)
        steps: list[BacktestStep] = []
        proposals: list[TradeProposal] = []
        decisions = []
        snapshots = []
        unexecuted: list[TradeProposal] = []
        proposal_ids: set[UUID] = set()
        active_order_id: UUID | None = None

        for step_index, (bar, session) in enumerate(zip(bars, sessions, strict=True)):
            opening_fill = None
            if active_order_id is not None:
                active_order = order_engine.get_order(active_order_id)
                if active_order is None:
                    raise BacktestExecutionError("active order disappeared")
                opening_fill = self._create_fill(
                    config, active_order, bar.open, bar.timestamp, step_index
                )
                order_engine, ledger = self._apply_fill_atomically(
                    order_engine,
                    ledger,
                    opening_fill,
                    self._derived_id(config.run_id, "fill-event", step_index),
                )
                active_order_id = None

            snapshot = ledger.create_account_snapshot(
                {config.data_request.symbol: bar.close}, bar.timestamp
            )
            snapshots.append(snapshot)
            context = BacktestContext(
                run_id=config.run_id,
                step_index=step_index,
                session=session,
                current_bar=bar,
                history=bars[: step_index + 1],
                account_snapshot=snapshot,
                positions=ledger.positions,
            )
            proposal = self._evaluate_strategy(strategy, context)
            risk_decision = None
            submitted_order = None
            unexecuted_reason = None

            if proposal is not None:
                self._validate_proposal(config, proposal, bar.timestamp, proposal_ids)
                if self._has_active_order(order_engine):
                    raise ActiveOrderError(
                        "only one pending, submitted, or partially filled order "
                        "is supported"
                    )
                proposal_ids.add(proposal.proposal_id)
                proposals.append(proposal)
                risk_context = RiskContext(
                    cash=ledger.cash,
                    equity=snapshot.equity,
                    positions=ledger.positions,
                    current_price=bar.close,
                    total_market_exposure=snapshot.positions_market_value,
                    new_trading_enabled=config.trading_enabled,
                    as_of=bar.timestamp,
                )
                risk_decision = risk_manager.evaluate(proposal, risk_context)
                decisions.append(risk_decision)

                if step_index == len(bars) - 1:
                    unexecuted_reason = BacktestUnexecutedReason.END_OF_DATA
                    unexecuted.append(proposal)
                elif risk_decision.outcome is not RiskOutcome.REJECTED:
                    submitted_order = self._create_and_submit_order(
                        config, order_engine, risk_decision, bar.timestamp, step_index
                    )
                    active_order_id = submitted_order.request.order_id

            steps.append(
                BacktestStep(
                    step_index=step_index,
                    session=session,
                    bar=bar,
                    opening_fill=opening_fill,
                    account_snapshot=snapshot,
                    proposal=proposal,
                    risk_decision=risk_decision,
                    submitted_order=submitted_order,
                    unexecuted_reason=unexecuted_reason,
                )
            )

        final_orders = tuple(order_engine.orders.values())
        return BacktestResult(
            config=config,
            provider_name=data.provider_name,
            bars=bars,
            steps=tuple(steps),
            proposals=tuple(proposals),
            risk_decisions=tuple(decisions),
            orders=final_orders,
            order_events=order_engine.get_events(),
            fills=ledger.fills,
            account_snapshots=tuple(snapshots),
            final_positions=ledger.positions,
            final_equity=snapshots[-1].equity,
            unexecuted_final_bar_proposals=tuple(unexecuted),
            start_timestamp=bars[0].timestamp,
            end_timestamp=bars[-1].timestamp,
        )

    def _validate_calendar_alignment(
        self, config: BacktestConfig, bars: tuple
    ) -> tuple[TradingSession, ...]:
        expected_range = self._market_calendar.sessions_between(
            config.data_request.start, config.data_request.end
        )
        expected = {
            session.session_date: session for session in expected_range.sessions
        }
        actual: dict[date, TradingSession] = {}
        aligned = []
        for bar in bars:
            if not self._market_calendar.is_trading_session(bar.timestamp):
                raise BacktestCalendarAlignmentError(
                    f"bar {bar.timestamp.isoformat()} is not an NYSE trading session"
                )
            session_date = bar.timestamp.astimezone(_NEW_YORK).date()
            if session_date in actual:
                raise BacktestCalendarAlignmentError(
                    f"multiple bars map to session {session_date.isoformat()}"
                )
            session = expected.get(session_date)
            if session is None:
                raise BacktestCalendarAlignmentError(
                    f"bar session {session_date.isoformat()} is outside expected range"
                )
            actual[session_date] = session
            aligned.append(session)
        missing = set(expected) - set(actual)
        if missing and not config.allow_missing_sessions:
            rendered = ", ".join(item.isoformat() for item in sorted(missing))
            raise BacktestCalendarAlignmentError(
                f"historical data is missing trading sessions: {rendered}"
            )
        return tuple(aligned)

    @staticmethod
    def _evaluate_strategy(
        strategy: BacktestStrategy, context: BacktestContext
    ) -> TradeProposal | None:
        try:
            proposal = strategy.evaluate(context)
        except Exception as error:
            raise StrategyContractError(
                f"strategy failed at step {context.step_index}"
            ) from error
        if proposal is not None and not isinstance(proposal, TradeProposal):
            raise StrategyContractError("strategy must return TradeProposal or None")
        return proposal

    @staticmethod
    def _validate_proposal(
        config: BacktestConfig,
        proposal: TradeProposal,
        current_timestamp,
        proposal_ids: set[UUID],
    ) -> None:
        if proposal.symbol != config.data_request.symbol:
            raise StrategyContractError("proposal symbol does not match the backtest")
        if proposal.created_at != current_timestamp:
            raise StrategyContractError(
                "proposal created_at must equal current_bar.timestamp"
            )
        if proposal.proposal_id in proposal_ids:
            raise StrategyContractError(f"duplicate proposal_id {proposal.proposal_id}")

    @staticmethod
    def _has_active_order(order_engine: OrderEngine) -> bool:
        return any(
            order.status in _ACTIVE_STATUSES for order in order_engine.orders.values()
        )

    @classmethod
    def _create_and_submit_order(
        cls,
        config: BacktestConfig,
        order_engine: OrderEngine,
        decision,
        timestamp,
        step_index: int,
    ) -> Order:
        instruction = ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, timestamp)
        order = order_engine.create_order(
            decision,
            instruction,
            order_id=cls._derived_id(config.run_id, "order", step_index),
            event_id=cls._derived_id(config.run_id, "created-event", step_index),
        )
        return order_engine.submit_order(
            order.request.order_id,
            timestamp,
            event_id=cls._derived_id(config.run_id, "submitted-event", step_index),
        )

    @classmethod
    def _create_fill(
        cls,
        config: BacktestConfig,
        order: Order,
        open_price: Decimal,
        timestamp,
        step_index: int,
    ) -> OrderFill:
        slippage = config.slippage_basis_points / Decimal("10000")
        multiplier = (
            Decimal("1") + slippage
            if order.request.side is OrderSide.BUY
            else Decimal("1") - slippage
        )
        return OrderFill(
            fill_id=cls._derived_id(config.run_id, "fill", step_index),
            order_id=order.request.order_id,
            symbol=order.request.symbol,
            side=order.request.side,
            quantity=order.request.quantity,
            price=open_price * multiplier,
            commission=config.fixed_commission,
            filled_at=timestamp,
        )

    @staticmethod
    def _apply_fill_atomically(
        order_engine: OrderEngine,
        ledger: PaperLedger,
        fill: OrderFill,
        event_id: UUID,
    ) -> tuple[OrderEngine, PaperLedger]:
        try:
            shadow_orders = deepcopy(order_engine)
            shadow_ledger = deepcopy(ledger)
        except Exception as error:
            raise BacktestAtomicityError(
                "order engine and ledger could not be copied safely"
            ) from error
        try:
            shadow_orders.apply_fill(fill, event_id=event_id)
            shadow_ledger.apply_fill(fill)
        except Exception as error:
            raise BacktestExecutionError(
                f"next-open fill {fill.fill_id} could not be applied"
            ) from error
        return shadow_orders, shadow_ledger

    @staticmethod
    def _derived_id(run_id: UUID, kind: str, step_index: int) -> UUID:
        namespace = uuid5(NAMESPACE_URL, str(run_id))
        return uuid5(namespace, f"{kind}:{step_index}")
