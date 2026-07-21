"""Deterministic orchestration of complete multi-symbol market frames."""

from copy import deepcopy
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from trading_bot.domain import (
    Order,
    OrderFill,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    TimeInForce,
    TradeProposal,
)
from trading_bot.execution import ExecutionInstruction, OrderEngine
from trading_bot.ledger import PaperLedger
from trading_bot.market_data import MultiSymbolHistoricalDataProvider
from trading_bot.multi_backtesting.exceptions import (
    IncompleteMarketFrameError,
    MultiSymbolBacktestAtomicityError,
    MultiSymbolBacktestExecutionError,
    MultiSymbolStrategyContractError,
)
from trading_bot.multi_backtesting.models import (
    MultiSymbolBacktestConfig,
    MultiSymbolBacktestResult,
    MultiSymbolBacktestStep,
    MultiSymbolStrategyContext,
    MultiSymbolUnexecutedReason,
    UnexecutedProposal,
)
from trading_bot.multi_backtesting.strategy import MultiSymbolBacktestStrategy
from trading_bot.risk import RiskContext, RiskManager, RiskOutcome

_ACTIVE = {OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}


class MultiSymbolBacktestEngine:
    def __init__(self, data_provider: MultiSymbolHistoricalDataProvider) -> None:
        if not hasattr(data_provider, "get_bars"):
            raise TypeError("data_provider must implement get_bars")
        self._data_provider = data_provider

    def run(
        self,
        config: MultiSymbolBacktestConfig,
        strategy: MultiSymbolBacktestStrategy,
    ) -> MultiSymbolBacktestResult:
        if not isinstance(config, MultiSymbolBacktestConfig):
            raise TypeError("config must be a MultiSymbolBacktestConfig")
        if not hasattr(strategy, "evaluate"):
            raise TypeError("strategy must implement evaluate")
        data = self._data_provider.get_bars(config.data_request)
        if data.request != config.data_request:
            raise MultiSymbolBacktestExecutionError(
                "provider result request does not match configuration"
            )
        frames = data.frames
        if any(not frame.is_complete for frame in frames):
            raise IncompleteMarketFrameError(
                "every actual market frame must contain every requested symbol"
            )

        ledger = PaperLedger(config.starting_cash)
        orders = OrderEngine()
        risk_manager = RiskManager(config.risk_limits)
        steps = []
        proposals_all = []
        decisions_all = []
        snapshots = []
        unexecuted_all = []
        proposal_ids: set[UUID] = set()
        pending: tuple[UUID, ...] = ()
        symbol_index = {symbol: index for index, symbol in enumerate(data.symbols)}

        for step_index, frame in enumerate(frames):
            opening_fills = self._build_fill_batch(
                config, orders, pending, frame, step_index, symbol_index
            )
            if opening_fills:
                orders, ledger = self._apply_fill_batch_atomically(
                    orders,
                    ledger,
                    opening_fills,
                    config.run_id,
                    step_index,
                    frame.timestamp,
                    set(data.symbols),
                )
            pending = ()
            prices = {
                symbol: frame.bars_by_symbol[symbol].close for symbol in data.symbols
            }
            snapshot = ledger.create_account_snapshot(prices, frame.timestamp)
            snapshots.append(snapshot)
            active_orders = tuple(
                order for order in orders.orders.values() if order.status in _ACTIVE
            )
            context = MultiSymbolStrategyContext(
                config.run_id,
                step_index,
                frame.timestamp,
                data.symbols,
                frame,
                frames[: step_index + 1],
                snapshot,
                ledger.positions,
                active_orders,
            )
            proposals = self._evaluate_strategy(strategy, context)
            proposals = self._validate_and_order_proposals(
                proposals, context, proposal_ids, active_orders, symbol_index
            )
            proposal_ids.update(item.proposal_id for item in proposals)
            decisions = self._evaluate_risk_batch(
                config, risk_manager, proposals, ledger, snapshot, prices
            )
            submitted: tuple[Order, ...] = ()
            unexecuted: tuple[UnexecutedProposal, ...] = ()
            if step_index == len(frames) - 1:
                unexecuted = tuple(
                    UnexecutedProposal(
                        decision.proposal,
                        decision,
                        MultiSymbolUnexecutedReason.END_OF_DATA,
                    )
                    for decision in decisions
                    if decision.outcome is not RiskOutcome.REJECTED
                )
            else:
                orders, submitted = self._submit_batch_atomically(
                    config, orders, decisions, frame.timestamp, step_index
                )
                pending = tuple(order.request.order_id for order in submitted)
            proposals_all.extend(proposals)
            decisions_all.extend(decisions)
            unexecuted_all.extend(unexecuted)
            steps.append(
                MultiSymbolBacktestStep(
                    step_index,
                    frame,
                    opening_fills,
                    snapshot,
                    proposals,
                    decisions,
                    submitted,
                    unexecuted,
                )
            )

        final_orders = tuple(orders.orders.values())
        return MultiSymbolBacktestResult(
            config,
            data.provider_name,
            frames,
            tuple(steps),
            tuple(proposals_all),
            tuple(decisions_all),
            final_orders,
            orders.get_events(),
            ledger.fills,
            tuple(snapshots),
            ledger.positions,
            snapshots[-1].equity,
            tuple(unexecuted_all),
            frames[0].timestamp,
            frames[-1].timestamp,
        )

    @staticmethod
    def _evaluate_strategy(strategy, context):  # type: ignore[no-untyped-def]
        try:
            return tuple(strategy.evaluate(context))
        except Exception as error:
            raise MultiSymbolStrategyContractError(
                f"strategy failed at step {context.step_index}"
            ) from error

    @classmethod
    def _validate_and_order_proposals(
        cls, proposals, context, known_ids, active_orders, symbol_index
    ):  # type: ignore[no-untyped-def]
        frame_ids = set()
        frame_symbols = set()
        active_symbols = {order.request.symbol for order in active_orders}
        for proposal in proposals:
            if not isinstance(proposal, TradeProposal):
                raise MultiSymbolStrategyContractError(
                    "strategy must return only TradeProposal values"
                )
            if proposal.symbol not in context.symbols:
                raise MultiSymbolStrategyContractError(
                    "proposal symbol is outside universe"
                )
            if proposal.created_at != context.timestamp:
                raise MultiSymbolStrategyContractError(
                    "proposal created_at must equal current frame timestamp"
                )
            if proposal.proposal_id in known_ids or proposal.proposal_id in frame_ids:
                raise MultiSymbolStrategyContractError("duplicate proposal ID")
            if proposal.symbol in frame_symbols:
                raise MultiSymbolStrategyContractError(
                    "only one proposal per symbol is allowed per frame"
                )
            if proposal.symbol in active_symbols:
                raise MultiSymbolStrategyContractError(
                    "proposal symbol has an unresolved active order"
                )
            frame_ids.add(proposal.proposal_id)
            frame_symbols.add(proposal.symbol)
        return tuple(
            sorted(
                proposals,
                key=lambda item: (
                    0 if item.side is OrderSide.SELL else 1,
                    symbol_index[item.symbol],
                    item.proposal_id.int,
                ),
            )
        )

    @staticmethod
    def _evaluate_risk_batch(config, manager, proposals, ledger, snapshot, prices):  # type: ignore[no-untyped-def]
        cash = ledger.cash
        exposure = snapshot.positions_market_value
        positions = dict(ledger.positions)
        decisions = []
        for proposal in proposals:
            context = RiskContext(
                cash,
                snapshot.equity,
                positions,
                prices[proposal.symbol],
                exposure,
                config.trading_enabled,
                proposal.created_at,
            )
            decision = manager.evaluate(proposal, context)
            if decision.proposal != proposal or decision.approved_quantity < 0:
                raise MultiSymbolBacktestExecutionError("invalid risk decision")
            decisions.append(decision)
            if decision.outcome is RiskOutcome.REJECTED:
                continue
            quantity = decision.approved_quantity
            price = prices[proposal.symbol]
            current = positions.get(proposal.symbol)
            if proposal.side is OrderSide.BUY:
                cash -= quantity * price + config.risk_limits.estimated_commission
                exposure += quantity * price
                old_quantity = current.quantity if current else Decimal("0")
                average = current.average_cost if current else price
                positions[proposal.symbol] = Position(
                    proposal.symbol, old_quantity + quantity, average
                )
            else:
                if current is None or quantity > current.quantity:
                    raise MultiSymbolBacktestExecutionError(
                        "risk decision oversells projected position"
                    )
                exposure -= quantity * price
                remaining = current.quantity - quantity
                if remaining:
                    positions[proposal.symbol] = Position(
                        proposal.symbol, remaining, current.average_cost
                    )
                else:
                    del positions[proposal.symbol]
        return tuple(decisions)

    @classmethod
    def _submit_batch_atomically(cls, config, orders, decisions, timestamp, step):  # type: ignore[no-untyped-def]
        try:
            shadow = deepcopy(orders)
        except Exception as error:
            raise MultiSymbolBacktestAtomicityError(
                "order engine copy failed"
            ) from error
        submitted = []
        try:
            for ordinal, decision in enumerate(decisions):
                if decision.outcome is RiskOutcome.REJECTED:
                    continue
                symbol = decision.proposal.symbol
                instruction = ExecutionInstruction(
                    OrderType.MARKET, TimeInForce.DAY, timestamp
                )
                order = shadow.create_order(
                    decision,
                    instruction,
                    order_id=cls._id(config.run_id, "order", step, symbol, ordinal),
                    event_id=cls._id(config.run_id, "created", step, symbol, ordinal),
                )
                submitted.append(
                    shadow.submit_order(
                        order.request.order_id,
                        timestamp,
                        event_id=cls._id(
                            config.run_id, "submitted", step, symbol, ordinal
                        ),
                    )
                )
        except Exception as error:
            raise MultiSymbolBacktestExecutionError(
                "order submission batch failed"
            ) from error
        return shadow, tuple(submitted)

    @classmethod
    def _build_fill_batch(cls, config, orders, pending, frame, step, symbol_index):  # type: ignore[no-untyped-def]
        selected = []
        for order_id in pending:
            order = orders.get_order(order_id)
            if order is None or order.status not in _ACTIVE:
                raise MultiSymbolBacktestExecutionError("pending order is not fillable")
            if order.request.symbol not in frame.bars_by_symbol:
                raise MultiSymbolBacktestExecutionError("pending symbol is absent")
            selected.append(order)
        selected.sort(
            key=lambda order: (
                0 if order.request.side is OrderSide.SELL else 1,
                symbol_index[order.request.symbol],
                order.request.order_id.int,
            )
        )
        fills = []
        slippage = config.slippage_basis_points / Decimal("10000")
        for ordinal, order in enumerate(selected):
            bar = frame.bars_by_symbol[order.request.symbol]
            multiplier = (
                Decimal("1") + slippage
                if order.request.side is OrderSide.BUY
                else Decimal("1") - slippage
            )
            fills.append(
                OrderFill(
                    cls._id(config.run_id, "fill", step, order.request.symbol, ordinal),
                    order.request.order_id,
                    order.request.symbol,
                    order.request.side,
                    order.request.quantity,
                    bar.open * multiplier,
                    config.fixed_commission,
                    frame.timestamp,
                )
            )
        return tuple(fills)

    @classmethod
    def _apply_fill_batch_atomically(
        cls, orders, ledger, fills, run_id, step, expected_timestamp, universe
    ):  # type: ignore[no-untyped-def]
        cls._preflight_fill_batch(orders, ledger, fills, expected_timestamp, universe)
        try:
            shadow_orders = deepcopy(orders)
            shadow_ledger = deepcopy(ledger)
        except Exception as error:
            raise MultiSymbolBacktestAtomicityError("component copy failed") from error
        try:
            for ordinal, fill in enumerate(fills):
                shadow_orders.apply_fill(
                    fill,
                    event_id=cls._id(run_id, "fill-event", step, fill.symbol, ordinal),
                )
                shadow_ledger.apply_fill(fill)
        except Exception as error:
            raise MultiSymbolBacktestExecutionError(
                "opening fill batch failed atomically"
            ) from error
        return shadow_orders, shadow_ledger

    @staticmethod
    def _preflight_fill_batch(orders, ledger, fills, expected_timestamp, universe):  # type: ignore[no-untyped-def]
        cash = ledger.cash
        quantities = {
            symbol: item.quantity for symbol, item in ledger.positions.items()
        }
        ids = {fill.fill_id for fill in ledger.fills}
        for fill in fills:
            order = orders.get_order(fill.order_id)
            if order is None or order.status not in _ACTIVE:
                raise MultiSymbolBacktestExecutionError("fill order is not active")
            if fill.symbol not in universe or fill.filled_at != expected_timestamp:
                raise MultiSymbolBacktestExecutionError(
                    "fill does not match the expected frame"
                )
            if (
                fill.symbol != order.request.symbol
                or fill.side is not order.request.side
                or fill.quantity != order.remaining_quantity
            ):
                raise MultiSymbolBacktestExecutionError(
                    "fill does not match its active order"
                )
            if fill.fill_id in ids or fill.quantity <= 0 or fill.price <= 0:
                raise MultiSymbolBacktestExecutionError("invalid or duplicate fill")
            ids.add(fill.fill_id)
            if fill.side is OrderSide.SELL:
                owned = quantities.get(fill.symbol, Decimal("0"))
                if fill.quantity > owned:
                    raise MultiSymbolBacktestExecutionError(
                        "projected sell exceeds position"
                    )
                quantities[fill.symbol] = owned - fill.quantity
                cash += fill.gross_amount - fill.commission
            else:
                cash -= fill.gross_amount + fill.commission
                quantities[fill.symbol] = (
                    quantities.get(fill.symbol, Decimal("0")) + fill.quantity
                )
            if cash < 0:
                raise MultiSymbolBacktestExecutionError("fill batch exceeds cash")

    @staticmethod
    def _id(run_id: UUID, kind: str, step: int, symbol, ordinal: int) -> UUID:  # type: ignore[no-untyped-def]
        namespace = uuid5(NAMESPACE_URL, str(run_id))
        return uuid5(namespace, f"multi:{kind}:{step}:{symbol}:{ordinal}")
