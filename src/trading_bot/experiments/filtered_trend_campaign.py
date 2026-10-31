"""Frozen, effect-free multi-asset regime research using existing paper primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_FLOOR, Context, Decimal, localcontext
from statistics import median
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import (
    Bar,
    OrderFill,
    OrderSide,
    OrderType,
    TimeInForce,
    TradeProposal,
)
from trading_bot.execution import ExecutionInstruction, OrderEngine
from trading_bot.experiments.filtered_trend_data import UNIVERSE, MultiAssetDataset
from trading_bot.experiments.filtered_trend_strategies import (
    StrategyConfig,
    signal_series,
    strategy_grid,
    wilder_atr,
)
from trading_bot.ledger import PaperLedger
from trading_bot.risk import RiskContext, RiskLimits, RiskManager, RiskOutcome

CONTEXT = Context(prec=50)
STARTING_CASH = Decimal("100000")
ALLOCATION = Decimal("0.95")
NY = ZoneInfo("America/New_York")


def decimal_text(value: Decimal) -> str:
    """Canonical exact decimal text, independent of ambient arithmetic context."""
    if not value.is_finite():
        raise ValueError("nonfinite research value")
    text = format(value, "f")
    return (text.rstrip("0").rstrip(".") if "." in text else text) if value else "0"


def semantic_identity(kind: str, value: object) -> str:
    """Versioned typed length framing; never artifact bytes or object identity."""

    def frame(item: object) -> str:
        if item is None:
            return "n"
        if type(item) is bool:
            return "b1" if item else "b0"
        if type(item) is int:
            return "i" + str(item) + ";"
        if isinstance(item, Decimal):
            return frame(("decimal", decimal_text(item)))
        if isinstance(item, str):
            return "s" + str(len(item)) + ":" + item
        if isinstance(item, (list, tuple)):
            return "a" + str(len(item)) + ":" + "".join(frame(v) for v in item)
        if isinstance(item, dict) and all(type(k) is str for k in item):
            return frame(tuple((k, item[k]) for k in sorted(item)))
        raise TypeError("unsupported semantic material")

    return str(uuid5(NAMESPACE_URL, frame(("filtered-trend/v1", kind, value))))


def config_material(config: StrategyConfig) -> dict:
    return asdict(config)


@dataclass(frozen=True, slots=True)
class Regime:
    label: str
    start: date
    end: date


def regime_plan() -> tuple[Regime, ...]:
    return tuple(
        Regime(str(y), date(y, 1, 1), date(y + 1, 1, 1)) for y in range(2019, 2024)
    ) + (Regime("continuous", date(2019, 1, 1), date(2024, 1, 1)),)


@dataclass(frozen=True, slots=True)
class Costs:
    commission: Decimal
    slippage_bps: Decimal

    def __post_init__(self) -> None:
        if (self.commission, self.slippage_bps) not in (
            (Decimal("1"), Decimal("5")),
            (Decimal("2"), Decimal("10")),
        ):
            raise ValueError("only frozen base and stress economics are supported")


BASE_COSTS = Costs(Decimal("1"), Decimal("5"))
STRESS_COSTS = Costs(Decimal("2"), Decimal("10"))


@dataclass(frozen=True, slots=True)
class FillEvidence:
    identity: str
    session: str
    information_through: str | None
    side: str
    quantity: Decimal
    execution_open: Decimal
    price: Decimal
    commission: Decimal
    cash_after: Decimal
    risk_outcome: str


@dataclass(frozen=True, slots=True)
class Metrics:
    total_return: Decimal
    maximum_drawdown: Decimal
    final_equity: Decimal
    realized_profit_loss: Decimal
    fill_count: int
    closed_trades: int
    turnover: Decimal
    time_invested: Decimal
    equity_trace_identity: str
    fills: tuple[FillEvidence, ...]


@dataclass(frozen=True, slots=True)
class AtrDescription:
    count: int
    minimum: Decimal
    median: Decimal
    maximum: Decimal
    median_close_fraction: Decimal


@dataclass(frozen=True, slots=True)
class CellEvidence:
    candidate_id: str
    symbol: str
    regime: str
    result_id: str
    base: Metrics
    stress: Metrics
    buy_and_hold: Metrics
    buy_and_hold_stress: Metrics
    atr: AtrDescription
    session_count: int
    first_session: str
    last_session: str


@dataclass(frozen=True, slots=True)
class AggregateSummary:
    positive_regime_cells: int
    negative_regime_cells: int
    minimum_regime_return: Decimal
    median_regime_return: Decimal
    worst_regime_drawdown: Decimal
    median_regime_drawdown: Decimal
    median_turnover: Decimal
    positive_continuous_symbols: int
    minimum_continuous_return: Decimal
    median_continuous_return: Decimal
    worst_continuous_drawdown: Decimal


@dataclass(frozen=True, slots=True)
class CandidateSummary:
    candidate_id: str
    config: StrategyConfig
    base: AggregateSummary
    stress: AggregateSummary


def campaign_context(
    dataset: MultiAssetDataset, source_head: str, source_tree: str
) -> dict:
    provenance = [
        {
            "symbol": item.symbol,
            "provider": item.provider_provenance.to_dict(),
            "bar_count": len(item.bars),
            "first_bar": item.bars[0].timestamp.isoformat(),
            "last_bar": item.bars[-1].timestamp.isoformat(),
        }
        for item in dataset.datasets
    ]
    return frozen_context(
        source_head, source_tree, str(dataset.identity), dataset.price_basis, provenance
    )


def frozen_context(
    source_head: str,
    source_tree: str,
    dataset_id: str,
    price_basis: str,
    dataset_provenance: list[dict],
) -> dict:
    for value in (source_head, source_tree):
        if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("source identity must be exact lowercase SHA1")
    return {
        "schema": "filtered-trend-campaign/v1",
        "source_head": source_head,
        "source_tree": source_tree,
        "dataset_id": dataset_id,
        "price_basis": price_basis,
        "dataset_provenance": dataset_provenance,
        "universe": list(UNIVERSE),
        "grid": [config_material(c) for c in strategy_grid()],
        "regimes": [
            (r.label, r.start.isoformat(), r.end.isoformat()) for r in regime_plan()
        ],
        "economics": {
            "starting_cash": "100000",
            "allocation": "0.95",
            "reserve": "0.05",
            "long_only": True,
            "whole_shares": True,
            "leverage": False,
            "commission": "1",
            "slippage_bps": "5",
            "stress_commission": "2",
            "stress_slippage_bps": "10",
        },
        "timing": "completed-through-N-1/signals;N-open/adverse-fill;N-close/equity/v1",
        "valuation": (
            "initial-cash-and-session-close/drawdown;no-forced-terminal-liquidation/v1"
        ),
        "shortlist_policy": (
            "lexicographic-positive-symbols-positive-cells-"
            "min-continuous-dd-median-continuous-median-regime-"
            "turnover-canonical/v1"
        ),
        "neighbor_policy": (
            "adjacent-declared-MA-pairs-and-numeric-filter-levels/"
            "no-momentum-variant-neighbor/v1"
        ),
        "qualification_policy": None,
        "paper_binding": None,
        "live_eligible": False,
    }


def candidate_identity(campaign_id: str, config: StrategyConfig) -> str:
    return semantic_identity("candidate", (campaign_id, config_material(config)))


def _drawdown(equities: tuple[Decimal, ...]) -> Decimal:
    peak = equities[0]
    worst = Decimal(0)
    for value in equities:
        peak = max(peak, value)
        worst = max(worst, (peak - value) / peak)
    return worst


def _replay(
    bars: tuple[Bar, ...],
    indices: tuple[int, ...],
    states: tuple[str, ...],
    costs: Costs,
    run_id: str,
    *,
    buy_hold: bool = False,
) -> Metrics:
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
    equities: list[Decimal] = [STARTING_CASH]
    fills: list[FillEvidence] = []
    invested_sessions = 0
    for offset, index in enumerate(indices):
        bar = bars[index]
        position = ledger.get_position(bar.symbol)
        action = ("BUY" if offset == 0 else "HOLD") if buy_hold else states[index - 1]
        if (action == "BUY" and position is None) or (
            action == "SELL" and position is not None
        ):
            side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
            slipped = bar.open * (
                1 + costs.slippage_bps / 10000
                if side is OrderSide.BUY
                else 1 - costs.slippage_bps / 10000
            )
            snapshot = ledger.create_account_snapshot(
                {bar.symbol: bar.open}, bar.timestamp
            )
            quantity = (
                (
                    (ledger.cash * ALLOCATION - costs.commission) / slipped
                ).to_integral_value(rounding=ROUND_FLOOR)
                if side is OrderSide.BUY
                else position.quantity
            )
            if quantity > 0:
                event_material = (run_id, index, side.value)
                proposal = TradeProposal(
                    UUID(semantic_identity("proposal", event_material)),
                    bar.symbol,
                    side,
                    quantity,
                    bar.timestamp,
                    "frozen adjusted-price research",
                )
                risk = manager.evaluate(
                    proposal,
                    RiskContext(
                        ledger.cash,
                        snapshot.equity,
                        ledger.positions,
                        slipped,
                        snapshot.positions_market_value,
                        True,
                        bar.timestamp,
                    ),
                )
                if (
                    risk.outcome is RiskOutcome.REJECTED
                    or risk.approved_quantity != quantity
                ):
                    raise ValueError("research sizing and risk constraints disagree")
                order = engine.create_order(
                    risk,
                    ExecutionInstruction(
                        OrderType.MARKET, TimeInForce.DAY, bar.timestamp
                    ),
                    order_id=UUID(semantic_identity("order", event_material)),
                    event_id=UUID(semantic_identity("created", event_material)),
                )
                engine.submit_order(
                    order.request.order_id,
                    bar.timestamp,
                    event_id=UUID(semantic_identity("submitted", event_material)),
                )
                fill = OrderFill(
                    UUID(semantic_identity("fill", event_material)),
                    order.request.order_id,
                    bar.symbol,
                    side,
                    quantity,
                    slipped,
                    costs.commission,
                    bar.timestamp,
                )
                engine.apply_fill(
                    fill, event_id=UUID(semantic_identity("filled", event_material))
                )
                ledger.apply_fill(fill)
                fills.append(
                    FillEvidence(
                        str(fill.fill_id),
                        bar.timestamp.isoformat(),
                        None if buy_hold else bars[index - 1].timestamp.isoformat(),
                        side.value,
                        quantity,
                        bar.open,
                        slipped,
                        costs.commission,
                        ledger.cash,
                        risk.outcome.value,
                    )
                )
        invested_sessions += ledger.get_position(bar.symbol) is not None
        equities.append(
            ledger.create_account_snapshot(
                {bar.symbol: bar.close}, bar.timestamp
            ).equity
        )
    equity_values = tuple(equities)
    turnover = sum((f.quantity * f.price for f in fills), Decimal(0)) / (
        sum(equities[1:]) / len(indices)
    )
    return Metrics(
        equities[-1] / STARTING_CASH - 1,
        _drawdown(equity_values),
        equities[-1],
        ledger.realized_profit_loss,
        len(fills),
        sum(f.side == "SELL" for f in fills),
        turnover,
        Decimal(invested_sessions) / len(indices),
        semantic_identity("equity-trace", equity_values),
        tuple(fills),
    )


def _evaluate_cell(
    bars: tuple[Bar, ...],
    config: StrategyConfig,
    regime: Regime,
    candidate_id: str,
    *,
    prepared_states: tuple[str, ...] | None = None,
) -> CellEvidence:
    """Fresh base/stress accounts; prior history contributes indicators only."""
    with localcontext(CONTEXT):
        if regime not in regime_plan() or config not in strategy_grid():
            raise ValueError("outside frozen research plan")
        if not bars or any(b.symbol != bars[0].symbol for b in bars):
            raise ValueError("one symbol per independent account")
        if any(
            a.timestamp >= b.timestamp for a, b in zip(bars, bars[1:], strict=False)
        ):
            raise ValueError("unordered bars")
        if any(
            not date(2016, 1, 1) <= b.timestamp.astimezone(NY).date() < date(2024, 1, 1)
            for b in bars
        ):
            raise ValueError("outside research history")
        indices = tuple(
            i
            for i, b in enumerate(bars)
            if regime.start <= b.timestamp.astimezone(NY).date() < regime.end
        )
        if not indices or indices[0] < 253:
            raise ValueError("insufficient regime/warmup history")
        states = (
            prepared_states
            if prepared_states is not None
            else signal_series(config, bars)
        )
        if len(states) != len(bars):
            raise ValueError("signal series length mismatch")
        # Wilder ATR helper returns one value per prefix (warmup values are None).
        atr_series = wilder_atr(bars)
        values = tuple(
            atr_series[i - 1] for i in indices if atr_series[i - 1] is not None
        )
        fractions = tuple(
            atr_series[i - 1] / bars[i - 1].close
            for i in indices
            if atr_series[i - 1] is not None
        )
        atr = AtrDescription(
            len(values), min(values), median(values), max(values), median(fractions)
        )
        run = semantic_identity(
            "cell", (candidate_id, str(bars[0].symbol), regime.label)
        )
        base = _replay(
            bars,
            indices,
            states,
            BASE_COSTS,
            semantic_identity("replay", (run, "base")),
        )
        stress = _replay(
            bars,
            indices,
            states,
            STRESS_COSTS,
            semantic_identity("replay", (run, "stress")),
        )
        bh = _replay(
            bars,
            indices,
            states,
            BASE_COSTS,
            semantic_identity("replay", (run, "buy-hold")),
            buy_hold=True,
        )
        bhs = _replay(
            bars,
            indices,
            states,
            STRESS_COSTS,
            semantic_identity("replay", (run, "buy-hold-stress")),
            buy_hold=True,
        )
        material = (
            run,
            asdict(base),
            asdict(stress),
            asdict(bh),
            asdict(bhs),
            asdict(atr),
            len(indices),
            bars[indices[0]].timestamp.isoformat(),
            bars[indices[-1]].timestamp.isoformat(),
        )
        return CellEvidence(
            candidate_id,
            str(bars[0].symbol),
            regime.label,
            semantic_identity("cell-result", material),
            base,
            stress,
            bh,
            bhs,
            atr,
            len(indices),
            bars[indices[0]].timestamp.isoformat(),
            bars[indices[-1]].timestamp.isoformat(),
        )


def evaluate_cell(
    bars: tuple[Bar, ...], config: StrategyConfig, regime: Regime, candidate_id: str
) -> CellEvidence:
    return _evaluate_cell(bars, config, regime, candidate_id)


def summarize(
    cells: tuple[CellEvidence, ...], *, stress: bool = False
) -> AggregateSummary:
    """Require every one of the 40 regime cells and eight continuous runs."""
    expected = tuple((s, r.label) for s in UNIVERSE for r in regime_plan())
    if (
        tuple((c.symbol, c.regime) for c in cells) != expected
        or len({c.candidate_id for c in cells}) != 1
    ):
        raise ValueError("incomplete or misordered candidate evidence")
    with localcontext(CONTEXT):
        regular = [
            c.stress if stress else c.base for c in cells if c.regime != "continuous"
        ]
        continuous = [
            c.stress if stress else c.base for c in cells if c.regime == "continuous"
        ]
        return AggregateSummary(
            sum(c.total_return > 0 for c in regular),
            sum(c.total_return < 0 for c in regular),
            min(c.total_return for c in regular),
            median(c.total_return for c in regular),
            max(c.maximum_drawdown for c in regular),
            median(c.maximum_drawdown for c in regular),
            median(c.turnover for c in regular),
            sum(c.total_return > 0 for c in continuous),
            min(c.total_return for c in continuous),
            median(c.total_return for c in continuous),
            max(c.maximum_drawdown for c in continuous),
        )


def shortlist(summaries: tuple[CandidateSummary, ...]) -> tuple[CandidateSummary, ...]:
    if tuple(s.config for s in summaries) != strategy_grid():
        raise ValueError("shortlist requires complete frozen ordered grid")
    order = {c: i for i, c in enumerate(strategy_grid())}
    with localcontext(CONTEXT):
        return tuple(
            sorted(
                summaries,
                key=lambda s: (
                    -s.base.positive_continuous_symbols,
                    -s.base.positive_regime_cells,
                    -s.base.minimum_continuous_return,
                    s.base.worst_continuous_drawdown,
                    -s.base.median_continuous_return,
                    -s.base.median_regime_return,
                    s.base.median_turnover,
                    order[s.config],
                ),
            )[:10]
        )


def neighbor_configs(config: StrategyConfig) -> tuple[StrategyConfig, ...]:
    """Adjacent predeclared parameter levels and adjacent declared MA pairs only."""
    grid = strategy_grid()
    if config not in grid:
        raise ValueError("not a frozen candidate")
    pair_order = ((35, 50), (55, 100), (50, 200))
    same = [
        c
        for c in grid
        if c.family == config.family and c.fast == config.fast and c.slow == config.slow
    ]
    j = same.index(config)
    params = [same[k] for k in (j - 1, j + 1) if 0 <= k < len(same)]
    i = pair_order.index((config.fast, config.slow))
    pairs = [
        c
        for c in grid
        if c.family == config.family
        and c.parameter == config.parameter
        and abs(pair_order.index((c.fast, c.slow)) - i) == 1
    ]
    # Momentum variants are different hypotheses, not numeric parameter neighbors.
    if config.family == "MA_LONG_MOMENTUM":
        params = []
    return tuple(c for c in grid if c in params + pairs)


def run_campaign(
    dataset: MultiAssetDataset, source_head: str, source_tree: str
) -> tuple[dict, tuple[CellEvidence, ...], tuple[CandidateSummary, ...]]:
    """In-memory offline research only; no production roots or external adapters."""
    if type(dataset) is not MultiAssetDataset:
        raise TypeError("exact validated MultiAssetDataset required")
    context = campaign_context(dataset, source_head, source_tree)
    campaign_id = semantic_identity("campaign", context)
    cells = []
    summaries = []
    for config in strategy_grid():
        candidate_id = candidate_identity(campaign_id, config)
        candidate_cells = []
        for item in dataset.datasets:
            states = signal_series(config, item.bars)
            for regime in regime_plan():
                candidate_cells.append(
                    _evaluate_cell(
                        item.bars, config, regime, candidate_id, prepared_states=states
                    )
                )
        owned = tuple(candidate_cells)
        cells.extend(owned)
        summaries.append(
            CandidateSummary(
                candidate_id, config, summarize(owned), summarize(owned, stress=True)
            )
        )
    return context, tuple(cells), tuple(summaries)
