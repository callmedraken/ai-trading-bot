"""Fixed, source-only Architecture 149 monthly rotation replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_FLOOR, Decimal, localcontext
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import (
    Bar,
    OrderFill,
    OrderSide,
    OrderType,
    Symbol,
    TimeInForce,
    TradeProposal,
)
from trading_bot.execution import ExecutionInstruction, OrderEngine
from trading_bot.experiments.filtered_trend_campaign import (
    ALLOCATION,
    BASE_COSTS,
    CONTEXT,
    STARTING_CASH,
    STRESS_COSTS,
    Costs,
)
from trading_bot.experiments.filtered_trend_data import (
    DATA_END_EXCLUSIVE,
    DATA_START,
    PRICE_BASIS,
    UNIVERSE,
    MultiAssetDataset,
    SymbolDataset,
)
from trading_bot.ledger import PaperLedger
from trading_bot.risk import RiskContext, RiskLimits, RiskManager, RiskOutcome

STRATEGY_ID = "MONTHLY_CROSS_ASSET_DEFENSIVE_ROTATION_V1"
IDENTITY_VERSION = "arch149-monthly-defensive-rotation-identity/v1"
DECIMAL_CONTEXT = CONTEXT.copy()
NY = ZoneInfo("America/New_York")
CASH = "CASH"
SIGNAL_LOOKBACK = 21
RANK_LOOKBACK = 252
EXPLORATION_START = date(2017, 1, 1)
EXPLORATION_END = date(2024, 1, 1)


class TargetResolution(StrEnum):
    """Resolution of a month-end target at its next qualified open."""

    MISSING_INPUT = "MISSING_INPUT"
    END_OF_EXPLORATION = "END_OF_EXPLORATION"
    UNCHANGED_TARGET = "UNCHANGED_TARGET"
    REBALANCED = "REBALANCED"
    INSUFFICIENT_WHOLE_SHARES = "INSUFFICIENT_WHOLE_SHARES"


def _decimal_text(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError("identity decimals must be finite Decimal values")
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _frame(value: object) -> str:
    if value is None:
        return "n"
    if type(value) is bool:
        return "b1" if value else "b0"
    if type(value) is int:
        return f"i{value};"
    if type(value) is Decimal:
        return _frame(("decimal", _decimal_text(value)))
    if type(value) is datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("identity timestamps must be timezone-aware")
        return _frame(("datetime", value.astimezone(UTC).isoformat()))
    if type(value) is date:
        return _frame(("date", value.isoformat()))
    if isinstance(value, StrEnum):
        return _frame(value.value)
    if type(value) is str:
        return f"s{len(value)}:{value}"
    if type(value) in (tuple, list):
        return f"a{len(value)}:" + "".join(_frame(item) for item in value)
    raise TypeError(
        f"unsupported monthly-rotation identity value: {type(value).__name__}"
    )


def monthly_rotation_identity(kind: str, material: object) -> str:
    """Return a stable UUID5 identity for explicit, versioned semantic material."""
    if type(kind) is not str or not kind:
        raise ValueError("identity kind must be nonblank text")
    return str(uuid5(NAMESPACE_URL, _frame((IDENTITY_VERSION, kind, material))))


@dataclass(frozen=True, slots=True)
class MonthlyTarget:
    """One month-end signal fact and its next-open resolution."""

    signal_date: date
    ranked_scores: tuple[tuple[str, Decimal], ...]
    target: str | None
    next_session: date | None
    resolution: TargetResolution
    missing_symbols: tuple[str, ...] = ()
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.signal_date) is not date:
            raise TypeError("signal_date must be a date")
        if type(self.ranked_scores) is not tuple:
            raise TypeError("ranked_scores must be an immutable tuple")
        if type(self.missing_symbols) is not tuple or any(
            type(symbol) is not str or symbol not in UNIVERSE
            for symbol in self.missing_symbols
        ):
            raise TypeError("missing_symbols must be a tuple of universe symbols")
        if len({symbol for symbol, _ in self.ranked_scores}) != len(
            self.ranked_scores
        ) or any(
            symbol not in UNIVERSE
            or type(score) is not Decimal
            or not score.is_finite()
            for symbol, score in self.ranked_scores
        ):
            raise ValueError("ranked scores must contain unique finite universe values")
        if self.ranked_scores and (
            len(self.ranked_scores) != len(UNIVERSE)
            or self.ranked_scores
            != tuple(
                sorted(
                    self.ranked_scores,
                    key=lambda item: (-item[1], UNIVERSE.index(item[0])),
                )
            )
        ):
            raise ValueError("ranked scores must be the complete deterministic ranking")
        if not isinstance(self.resolution, TargetResolution):
            raise TypeError("resolution must be a TargetResolution")
        if self.resolution is TargetResolution.MISSING_INPUT:
            if (
                self.target is not None
                or self.ranked_scores
                or self.next_session is not None
                or not self.missing_symbols
            ):
                raise ValueError("missing-input decisions cannot carry a target")
        elif self.resolution is TargetResolution.END_OF_EXPLORATION:
            if self.target not in (*UNIVERSE, CASH) or self.next_session is not None:
                raise ValueError("terminal targets must be valid and non-executable")
        elif (
            self.target not in (*UNIVERSE, CASH)
            or self.next_session is None
            or self.next_session <= self.signal_date
            or self.missing_symbols
        ):
            raise ValueError("resolved targets need a qualified later session")
        if self.ranked_scores and self.target in (*UNIVERSE, CASH):
            best_symbol, best_score = self.ranked_scores[0]
            expected_target = best_symbol if best_score > 0 else CASH
            if self.target != expected_target:
                raise ValueError("target does not match the positive-score gate")
        object.__setattr__(
            self,
            "identity",
            monthly_rotation_identity("monthly-target", self.identity_material),
        )

    @property
    def identity_material(self) -> tuple[object, ...]:
        return (
            self.signal_date,
            self.ranked_scores,
            self.target,
            self.next_session,
            self.resolution.value,
            self.missing_symbols,
        )


@dataclass(frozen=True, slots=True)
class RotationFill:
    """One deterministic paper fill using a qualified adjusted OPEN."""

    timestamp: datetime
    signal_date: date
    symbol: str
    side: str
    quantity: Decimal
    execution_open: Decimal
    price: Decimal
    commission: Decimal
    cash_after: Decimal
    risk_outcome: str
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.timestamp) is not datetime or self.timestamp.tzinfo is None:
            raise TypeError("fill timestamp must be timezone-aware")
        if type(self.signal_date) is not date:
            raise TypeError("fill signal_date must be a date")
        if (
            type(self.symbol) is not str
            or self.symbol not in UNIVERSE
            or type(self.side) is not str
            or self.side not in ("BUY", "SELL")
        ):
            raise ValueError("fill symbol or side is outside the frozen universe")
        if type(self.quantity) is not Decimal or self.quantity <= 0:
            raise ValueError("fill quantity must be positive Decimal")
        if self.quantity != self.quantity.to_integral_value():
            raise ValueError("monthly rotation fills require whole shares")
        for name in ("execution_open", "price"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite() or value <= 0:
                raise ValueError(f"{name} must be a positive finite Decimal")
        if (
            type(self.commission) is not Decimal
            or not self.commission.is_finite()
            or self.commission < 0
        ):
            raise ValueError("commission must be a nonnegative Decimal")
        if (
            type(self.cash_after) is not Decimal
            or not self.cash_after.is_finite()
            or self.cash_after < 0
        ):
            raise ValueError("cash_after must be a nonnegative Decimal")
        if self.risk_outcome not in (
            RiskOutcome.APPROVED.value,
            RiskOutcome.RESIZED.value,
        ):
            raise ValueError("a fill requires an approved or resized risk outcome")
        object.__setattr__(
            self,
            "identity",
            monthly_rotation_identity("trade-fill", self.identity_material),
        )

    @property
    def turnover_notional(self) -> Decimal:
        return self.quantity * self.price

    @property
    def identity_material(self) -> tuple[object, ...]:
        return (
            self.timestamp,
            self.signal_date,
            self.symbol,
            self.side,
            self.quantity,
            self.execution_open,
            self.price,
            self.commission,
            self.cash_after,
            self.risk_outcome,
        )


@dataclass(frozen=True, slots=True)
class DailyEquityMark:
    """An immutable end-of-session portfolio mark."""

    timestamp: datetime
    session_date: date
    cash: Decimal
    held_symbol: str | None
    held_quantity: Decimal
    held_close: Decimal | None
    equity: Decimal

    def __post_init__(self) -> None:
        if type(self.timestamp) is not datetime or self.timestamp.tzinfo is None:
            raise TypeError("mark timestamp must be timezone-aware")
        if type(self.session_date) is not date:
            raise TypeError("mark session_date must be a date")
        if type(self.cash) is not Decimal or not self.cash.is_finite() or self.cash < 0:
            raise ValueError("mark cash must be nonnegative Decimal")
        if (
            type(self.equity) is not Decimal
            or not self.equity.is_finite()
            or self.equity <= 0
        ):
            raise ValueError("mark equity must be positive Decimal")
        if self.held_symbol is None:
            if self.held_quantity != 0 or self.held_close is not None:
                raise ValueError("cash marks cannot include a position")
            market_value = Decimal(0)
        else:
            if self.held_symbol not in UNIVERSE:
                raise ValueError("mark symbol is outside the frozen universe")
            if (
                type(self.held_quantity) is not Decimal
                or self.held_quantity <= 0
                or self.held_quantity != self.held_quantity.to_integral_value()
                or type(self.held_close) is not Decimal
                or not self.held_close.is_finite()
                or self.held_close <= 0
            ):
                raise ValueError("held marks require positive whole shares and a close")
            market_value = self.held_quantity * self.held_close
        if self.cash + market_value != self.equity:
            raise ValueError("equity mark does not reconcile to cash and holdings")

    @property
    def identity_material(self) -> tuple[object, ...]:
        return (
            self.timestamp,
            self.session_date,
            self.cash,
            self.held_symbol,
            self.held_quantity,
            self.held_close,
            self.equity,
        )


@dataclass(frozen=True, slots=True)
class RotationReplay:
    """Immutable continuous 2017-2023 portfolio replay capture."""

    strategy_id: str
    dataset_identity: str
    costs: Costs
    initial_equity: Decimal
    targets: tuple[MonthlyTarget, ...]
    fills: tuple[RotationFill, ...]
    fill_turnovers: tuple[Decimal, ...]
    daily_marks: tuple[DailyEquityMark, ...]
    turnover: Decimal
    time_invested: Decimal
    months_held: tuple[tuple[str, int], ...]
    entry_counts: tuple[tuple[str, int], ...]
    target_sequence_identity: str
    trade_audit_identity: str
    daily_equity_identity: str
    identity: str

    def __post_init__(self) -> None:
        if self.strategy_id != STRATEGY_ID or not self.dataset_identity:
            raise ValueError("replay is not bound to the frozen candidate and dataset")
        if type(self.costs) is not Costs or self.costs not in (
            BASE_COSTS,
            STRESS_COSTS,
        ):
            raise ValueError("only the exact frozen BASE or STRESS costs are supported")
        if self.initial_equity != STARTING_CASH:
            raise ValueError("the replay must start with the fixed $100,000 cash")
        if not self.targets or not self.daily_marks:
            raise ValueError("replay evidence cannot be empty")
        if (
            any(type(target) is not MonthlyTarget for target in self.targets)
            or any(type(fill) is not RotationFill for fill in self.fills)
            or any(type(mark) is not DailyEquityMark for mark in self.daily_marks)
        ):
            raise TypeError("replay collections must contain exact immutable records")
        if tuple(fill.turnover_notional for fill in self.fills) != self.fill_turnovers:
            raise ValueError("fill turnover values must align with the trade audit")
        target_dates = tuple(target.signal_date for target in self.targets)
        if tuple(sorted(set(target_dates))) != target_dates:
            raise ValueError("targets must be unique and chronologically ordered")
        mark_dates = tuple(mark.session_date for mark in self.daily_marks)
        if tuple(sorted(set(mark_dates))) != mark_dates or any(
            not EXPLORATION_START <= day < EXPLORATION_END for day in mark_dates
        ):
            raise ValueError("daily marks must be ordered and bounded to 2017-2023")
        if any(
            not EXPLORATION_START
            <= fill.timestamp.astimezone(NY).date()
            < EXPLORATION_END
            for fill in self.fills
        ):
            raise ValueError("fills must remain inside the 2017-2023 scoring interval")
        if (
            tuple(symbol for symbol, _ in self.months_held) != UNIVERSE
            or tuple(symbol for symbol, _ in self.entry_counts) != UNIVERSE
        ):
            raise ValueError(
                "per-symbol metrics must preserve the frozen universe order"
            )
        expected_turnover_identity = monthly_rotation_identity(
            "target-sequence", tuple(target.identity for target in self.targets)
        )
        expected_trade_identity = monthly_rotation_identity(
            "trade-audit", tuple(fill.identity for fill in self.fills)
        )
        expected_equity_identity = monthly_rotation_identity(
            "daily-equity-series",
            (
                self.initial_equity,
                tuple(mark.identity_material for mark in self.daily_marks),
            ),
        )
        if (
            self.target_sequence_identity != expected_turnover_identity
            or self.trade_audit_identity != expected_trade_identity
            or self.daily_equity_identity != expected_equity_identity
        ):
            raise ValueError("replay component identity does not match captured facts")
        expected_identity = monthly_rotation_identity(
            "portfolio-replay", self.identity_material
        )
        if self.identity != expected_identity:
            raise ValueError("replay identity does not match captured facts")

    @property
    def identity_material(self) -> tuple[object, ...]:
        return (
            self.strategy_id,
            self.dataset_identity,
            (self.costs.commission, self.costs.slippage_bps),
            self.initial_equity,
            self.target_sequence_identity,
            self.trade_audit_identity,
            self.daily_equity_identity,
            self.turnover,
            self.time_invested,
            self.months_held,
            self.entry_counts,
        )

    @property
    def final_equity(self) -> Decimal:
        return self.daily_marks[-1].equity


def verify_rotation_replay_identity(replay: RotationReplay) -> bool:
    """Independently recompute every public component and aggregate identity."""
    if type(replay) is not RotationReplay:
        return False
    if any(
        target.identity
        != monthly_rotation_identity("monthly-target", target.identity_material)
        for target in replay.targets
    ):
        return False
    if any(
        fill.identity != monthly_rotation_identity("trade-fill", fill.identity_material)
        for fill in replay.fills
    ):
        return False
    target_identity = monthly_rotation_identity(
        "target-sequence", tuple(target.identity for target in replay.targets)
    )
    trade_identity = monthly_rotation_identity(
        "trade-audit", tuple(fill.identity for fill in replay.fills)
    )
    equity_identity = monthly_rotation_identity(
        "daily-equity-series",
        (
            replay.initial_equity,
            tuple(mark.identity_material for mark in replay.daily_marks),
        ),
    )
    return (
        replay.target_sequence_identity == target_identity
        and replay.trade_audit_identity == trade_identity
        and replay.daily_equity_identity == equity_identity
        and replay.identity
        == monthly_rotation_identity("portfolio-replay", replay.identity_material)
    )


@dataclass(frozen=True, slots=True)
class _Signal:
    index: int
    signal_date: date
    ranked_scores: tuple[tuple[str, Decimal], ...]
    target: str | None
    next_session: date | None
    missing_symbols: tuple[str, ...]


def _session_date(bar: Bar) -> date:
    return bar.timestamp.astimezone(NY).date()


def _validated_bars(dataset: MultiAssetDataset) -> tuple[tuple[Bar, ...], ...]:
    if type(dataset) is not MultiAssetDataset:
        raise TypeError("exact validated MultiAssetDataset required")
    if dataset.price_basis != PRICE_BASIS:
        raise ValueError(
            "dataset price basis or universe differs from the frozen input"
        )
    if (
        type(dataset.datasets) is not tuple
        or len(dataset.datasets) != len(UNIVERSE)
        or any(type(item) is not SymbolDataset for item in dataset.datasets)
        or tuple(item.symbol for item in dataset.datasets) != UNIVERSE
    ):
        raise ValueError("dataset must contain all eight frozen symbols in order")
    series = tuple(item.bars for item in dataset.datasets)
    reference = tuple(bar.timestamp for bar in series[0])
    if not reference:
        raise ValueError("empty dataset histories are not supported")
    if any(tuple(bar.timestamp for bar in bars) != reference for bars in series[1:]):
        raise ValueError("all universe symbols must share exact qualified sessions")
    dates = tuple(_session_date(bar) for bar in series[0])
    if any(not DATA_START.date() <= day < DATA_END_EXCLUSIVE.date() for day in dates):
        raise ValueError(
            "input contains a session outside the accepted 2016-2023 range"
        )
    if dates != tuple(sorted(set(dates))):
        raise ValueError("dataset sessions must be unique and chronological")
    if (
        dates[0].year != 2016
        or dates[0] < DATA_START.date()
        or dates[-1].year != 2023
        or dates[-1] >= EXPLORATION_END
    ):
        raise ValueError("dataset must retain the bounded 2016-2023 accepted interval")
    return series


def _month_end_indices(dates: tuple[date, ...]) -> tuple[int, ...]:
    return tuple(
        index
        for index, session in enumerate(dates)
        if session >= EXPLORATION_START
        and (
            index + 1 == len(dates)
            or (dates[index + 1].year, dates[index + 1].month)
            != (session.year, session.month)
        )
    )


def _signals(series: tuple[tuple[Bar, ...], ...]) -> tuple[_Signal, ...]:
    dates = tuple(_session_date(bar) for bar in series[0])
    signals: list[_Signal] = []
    for index in _month_end_indices(dates):
        signal_date = dates[index]
        if index < RANK_LOOKBACK:
            raise ValueError(
                "the 2017 signal window lacks the fixed 252-session warmup"
            )
        scores: list[tuple[str, Decimal]] = []
        missing: list[str] = []
        for symbol_index, symbol in enumerate(UNIVERSE):
            bars = series[symbol_index]
            prior = bars[index - RANK_LOOKBACK].close
            recent = bars[index - SIGNAL_LOOKBACK].close
            if (
                type(prior) is not Decimal
                or not prior.is_finite()
                or prior <= 0
                or type(recent) is not Decimal
                or not recent.is_finite()
                or recent <= 0
            ):
                missing.append(symbol)
                continue
            score = recent / prior - Decimal(1)
            if not score.is_finite():
                missing.append(symbol)
                continue
            scores.append((symbol, score))
        if missing:
            signals.append(_Signal(index, signal_date, (), None, None, tuple(missing)))
            continue
        ranked = tuple(
            sorted(
                scores,
                key=lambda item: (-item[1], UNIVERSE.index(item[0])),
            )
        )
        target = ranked[0][0] if ranked[0][1] > 0 else CASH
        next_session = (
            dates[index + 1]
            if index + 1 < len(dates) and dates[index + 1] < EXPLORATION_END
            else None
        )
        signals.append(_Signal(index, signal_date, ranked, target, next_session, ()))
    return tuple(signals)


def _paper_fill(
    ledger: PaperLedger,
    engine: OrderEngine,
    manager: RiskManager,
    *,
    timestamp: datetime,
    symbol: str,
    side: OrderSide,
    quantity: Decimal,
    execution_open: Decimal,
    price: Decimal,
    costs: Costs,
    signal_date: date,
    sequence: int,
) -> RotationFill:
    symbol_value = Symbol(symbol)
    snapshot = ledger.create_account_snapshot(
        {symbol_value: execution_open} if symbol_value in ledger.positions else {},
        timestamp,
    )
    proposal_material = (signal_date, timestamp, symbol, side.value, sequence)
    proposal = TradeProposal(
        UUID(monthly_rotation_identity("order-proposal", proposal_material)),
        symbol_value,
        side,
        quantity,
        timestamp,
        "frozen Architecture 149 monthly rotation replay",
    )
    decision = manager.evaluate(
        proposal,
        RiskContext(
            ledger.cash,
            snapshot.equity,
            ledger.positions,
            price,
            snapshot.positions_market_value,
            True,
            timestamp,
        ),
    )
    if (
        decision.outcome is RiskOutcome.REJECTED
        or decision.approved_quantity != quantity
    ):
        raise ValueError("frozen whole-share sizing disagrees with A147 risk checks")
    order_id = UUID(monthly_rotation_identity("order", proposal_material))
    order = engine.create_order(
        decision,
        ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, timestamp),
        order_id=order_id,
        event_id=UUID(monthly_rotation_identity("order-created", proposal_material)),
    )
    engine.submit_order(
        order.request.order_id,
        timestamp,
        event_id=UUID(monthly_rotation_identity("order-submitted", proposal_material)),
    )
    fill = OrderFill(
        UUID(monthly_rotation_identity("paper-fill", proposal_material)),
        order.request.order_id,
        symbol_value,
        side,
        quantity,
        price,
        costs.commission,
        timestamp,
    )
    engine.apply_fill(
        fill,
        event_id=UUID(monthly_rotation_identity("fill-applied", proposal_material)),
    )
    ledger.apply_fill(fill)
    return RotationFill(
        timestamp,
        signal_date,
        symbol,
        side.value,
        quantity,
        execution_open,
        price,
        costs.commission,
        ledger.cash,
        decision.outcome.value,
    )


def replay_monthly_defensive_rotation(
    dataset: MultiAssetDataset, *, costs: Costs
) -> RotationReplay:
    """Replay the one frozen candidate over synthetic or accepted in-memory bars.

    The function performs no file, network, provider, broker, or holdout access.
    It accepts only the exact validated A147 2016-2023 dataset type and never
    looks up a session beyond that supplied interval.
    """
    if type(costs) is not Costs or costs not in (BASE_COSTS, STRESS_COSTS):
        raise ValueError("only the frozen BASE and STRESS cost cases are supported")
    series = _validated_bars(dataset)
    dates = tuple(_session_date(bar) for bar in series[0])
    with localcontext(DECIMAL_CONTEXT):
        signals = _signals(series)
    by_action_index = {
        signal.index + 1: signal
        for signal in signals
        if signal.target is not None and signal.next_session is not None
    }
    ledger = PaperLedger(STARTING_CASH)
    engine = OrderEngine()
    manager = RiskManager(
        RiskLimits(
            max_position_percent=ALLOCATION,
            max_total_exposure_percent=ALLOCATION,
            minimum_cash_reserve_percent=Decimal("0.05"),
            allow_fractional_shares=False,
            estimated_commission=costs.commission,
        )
    )
    fills: list[RotationFill] = []
    target_records: list[MonthlyTarget] = []
    action_resolution: dict[date, TargetResolution] = {}
    held_symbol: str | None = None
    sequence = 0

    for signal in signals:
        if signal.target is None:
            target_records.append(
                MonthlyTarget(
                    signal.signal_date,
                    (),
                    None,
                    None,
                    TargetResolution.MISSING_INPUT,
                    signal.missing_symbols,
                )
            )
        elif signal.next_session is None:
            target_records.append(
                MonthlyTarget(
                    signal.signal_date,
                    signal.ranked_scores,
                    signal.target,
                    None,
                    TargetResolution.END_OF_EXPLORATION,
                )
            )

    daily_marks: list[DailyEquityMark] = []
    month_end_indices = set(_month_end_indices(dates))
    month_end_holdings: dict[str, int] = {symbol: 0 for symbol in UNIVERSE}
    invested_sessions = 0

    with localcontext(DECIMAL_CONTEXT):
        for index, session in enumerate(dates):
            if not EXPLORATION_START <= session < EXPLORATION_END:
                continue
            signal = by_action_index.get(index)
            if signal is not None:
                assert signal.target is not None and signal.next_session == session
                if signal.target == (held_symbol or CASH):
                    action_resolution[signal.signal_date] = (
                        TargetResolution.UNCHANGED_TARGET
                    )
                else:
                    required_symbols = tuple(
                        symbol
                        for symbol in (held_symbol, signal.target)
                        if symbol is not None and symbol != CASH
                    )
                    required_bars: dict[str, Bar] = {}
                    for symbol in required_symbols:
                        symbol_index = UNIVERSE.index(symbol)
                        if index >= len(series[symbol_index]):
                            raise ValueError(
                                "a required next-session OPEN is unavailable"
                            )
                        bar = series[symbol_index][index]
                        if _session_date(bar) != session:
                            raise ValueError(
                                "a required next-session OPEN is unavailable"
                            )
                        if (
                            type(bar.open) is not Decimal
                            or not bar.open.is_finite()
                            or bar.open <= 0
                        ):
                            raise ValueError(
                                "a required next-session OPEN is unavailable"
                            )
                        required_bars[symbol] = bar

                    if held_symbol is not None:
                        sell_bar = required_bars[held_symbol]
                        sell_price = sell_bar.open * (
                            Decimal(1) - costs.slippage_bps / Decimal(10000)
                        )
                        quantity = ledger.get_position(Symbol(held_symbol)).quantity
                        fills.append(
                            _paper_fill(
                                ledger,
                                engine,
                                manager,
                                timestamp=sell_bar.timestamp,
                                symbol=held_symbol,
                                side=OrderSide.SELL,
                                quantity=quantity,
                                execution_open=sell_bar.open,
                                price=sell_price,
                                costs=costs,
                                signal_date=signal.signal_date,
                                sequence=sequence,
                            )
                        )
                        sequence += 1
                        held_symbol = None

                    if signal.target != CASH:
                        buy_bar = required_bars[signal.target]
                        buy_price = buy_bar.open * (
                            Decimal(1) + costs.slippage_bps / Decimal(10000)
                        )
                        quantity = (
                            (ledger.cash * ALLOCATION - costs.commission) / buy_price
                        ).to_integral_value(rounding=ROUND_FLOOR)
                        if quantity <= 0:
                            action_resolution[signal.signal_date] = (
                                TargetResolution.INSUFFICIENT_WHOLE_SHARES
                            )
                        else:
                            fills.append(
                                _paper_fill(
                                    ledger,
                                    engine,
                                    manager,
                                    timestamp=buy_bar.timestamp,
                                    symbol=signal.target,
                                    side=OrderSide.BUY,
                                    quantity=quantity,
                                    execution_open=buy_bar.open,
                                    price=buy_price,
                                    costs=costs,
                                    signal_date=signal.signal_date,
                                    sequence=sequence,
                                )
                            )
                            sequence += 1
                            held_symbol = signal.target
                            action_resolution[signal.signal_date] = (
                                TargetResolution.REBALANCED
                            )
                    else:
                        action_resolution[signal.signal_date] = (
                            TargetResolution.REBALANCED
                        )

                resolution = action_resolution.get(signal.signal_date)
                if resolution is not None:
                    target_records.append(
                        MonthlyTarget(
                            signal.signal_date,
                            signal.ranked_scores,
                            signal.target,
                            signal.next_session,
                            resolution,
                        )
                    )

            bar = series[UNIVERSE.index(held_symbol)][index] if held_symbol else None
            held_quantity = (
                ledger.get_position(Symbol(held_symbol)).quantity
                if held_symbol is not None
                else Decimal(0)
            )
            held_close = bar.close if bar is not None else None
            market_value = (
                held_quantity * held_close if held_close is not None else Decimal(0)
            )
            equity = ledger.cash + market_value
            daily_marks.append(
                DailyEquityMark(
                    series[0][index].timestamp,
                    session,
                    ledger.cash,
                    held_symbol,
                    held_quantity,
                    held_close,
                    equity,
                )
            )
            invested_sessions += held_symbol is not None
            if index in month_end_indices and held_symbol is not None:
                month_end_holdings[held_symbol] += 1

        target_records.sort(key=lambda item: item.signal_date)
        frozen_targets = tuple(target_records)
        frozen_fills = tuple(fills)
        frozen_marks = tuple(daily_marks)
        fill_turnovers = tuple(fill.turnover_notional for fill in frozen_fills)
        average_equity = sum((mark.equity for mark in frozen_marks), Decimal(0)) / len(
            frozen_marks
        )
        total_turnover = sum(fill_turnovers, Decimal(0)) / average_equity
        time_invested = Decimal(invested_sessions) / len(frozen_marks)
        entries = {symbol: 0 for symbol in UNIVERSE}
        for fill in frozen_fills:
            if fill.side == OrderSide.BUY.value:
                entries[fill.symbol] += 1
        months_held = tuple((symbol, month_end_holdings[symbol]) for symbol in UNIVERSE)
        entry_counts = tuple((symbol, entries[symbol]) for symbol in UNIVERSE)
        target_identity = monthly_rotation_identity(
            "target-sequence", tuple(target.identity for target in frozen_targets)
        )
        trade_identity = monthly_rotation_identity(
            "trade-audit", tuple(fill.identity for fill in frozen_fills)
        )
        equity_identity = monthly_rotation_identity(
            "daily-equity-series",
            (
                STARTING_CASH,
                tuple(mark.identity_material for mark in frozen_marks),
            ),
        )
        replay_material = (
            STRATEGY_ID,
            dataset.identity,
            (costs.commission, costs.slippage_bps),
            STARTING_CASH,
            target_identity,
            trade_identity,
            equity_identity,
            total_turnover,
            time_invested,
            months_held,
            entry_counts,
        )
        replay_identity = monthly_rotation_identity("portfolio-replay", replay_material)
        return RotationReplay(
            STRATEGY_ID,
            dataset.identity,
            costs,
            STARTING_CASH,
            frozen_targets,
            frozen_fills,
            fill_turnovers,
            frozen_marks,
            total_turnover,
            time_invested,
            months_held,
            entry_counts,
            target_identity,
            trade_identity,
            equity_identity,
            replay_identity,
        )
