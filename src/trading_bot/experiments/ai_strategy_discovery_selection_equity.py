"""Reconstruct accepted G1 stress equity traces without replaying signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext
from uuid import UUID

from trading_bot.domain import Bar, OrderFill, OrderSide
from trading_bot.experiments.ai_strategy_discovery_generation1 import (
    DISCOVERY_END_EXCLUSIVE,
    DISCOVERY_START,
    VIEW_START,
)
from trading_bot.experiments.filtered_trend_campaign import (
    CONTEXT,
    NY,
    STARTING_CASH,
    STRESS_COSTS,
    CellEvidence,
    FillEvidence,
    Metrics,
    semantic_identity,
)
from trading_bot.experiments.filtered_trend_data import UNIVERSE
from trading_bot.ledger import PaperLedger
from trading_bot.ledger.exceptions import LedgerError


def _uuid5(value: str, field: str) -> UUID:
    if type(value) is not str:
        raise ValueError(f"{field} must be a canonical UUID5")
    try:
        parsed = UUID(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a canonical UUID5") from None
    if str(parsed) != value or parsed.version != 5:
        raise ValueError(f"{field} must be a canonical UUID5")
    return parsed


@dataclass(frozen=True, slots=True)
class ReconstructedSleeve:
    """One symbol's initial cash and daily close equity for the G1 score window."""

    symbol: str
    candidate_id: str
    sessions: tuple[date, ...]
    equity_values: tuple[Decimal, ...]
    trace_identity: str

    def __post_init__(self) -> None:
        if type(self.symbol) is not str or self.symbol not in UNIVERSE:
            raise ValueError("sleeve symbol is outside the accepted G1 universe")
        _uuid5(self.candidate_id, "candidate identity")
        if type(self.sessions) is not tuple or not self.sessions:
            raise ValueError("sleeve sessions must be a nonempty immutable tuple")
        if any(type(session) is not date for session in self.sessions):
            raise ValueError("sleeve sessions must contain dates")
        if any(
            left >= right
            for left, right in zip(self.sessions, self.sessions[1:], strict=False)
        ):
            raise ValueError("sleeve sessions must be strictly ordered")
        if any(
            not DISCOVERY_START <= session < DISCOVERY_END_EXCLUSIVE
            or session.weekday() >= 5
            for session in self.sessions
        ):
            raise ValueError("sleeve sessions escaped the frozen G1 score window")
        if (
            type(self.equity_values) is not tuple
            or len(self.equity_values) != len(self.sessions) + 1
        ):
            raise ValueError("sleeve equity must include initial cash and each session")
        if any(
            type(value) is not Decimal or not value.is_finite() or value <= 0
            for value in self.equity_values
        ):
            raise ValueError("sleeve equity values must be positive finite Decimals")
        if self.equity_values[0] != STARTING_CASH:
            raise ValueError("sleeve must begin with the accepted $100,000 cash")
        _uuid5(self.trace_identity, "equity-trace identity")
        if semantic_identity("equity-trace", self.equity_values) != self.trace_identity:
            raise ValueError("sleeve equity does not match its trace identity")


@dataclass(frozen=True, slots=True)
class BasketReturns:
    """Fixed equal-weight research returns and ordered sleeve trace evidence."""

    daily_returns: tuple[Decimal, ...]
    identity: str
    trace_identities: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if type(self.daily_returns) is not tuple or not self.daily_returns:
            raise ValueError("basket daily returns must be a nonempty immutable tuple")
        if any(
            type(value) is not Decimal or not value.is_finite()
            for value in self.daily_returns
        ):
            raise ValueError("basket returns must be finite Decimals")
        if (
            type(self.trace_identities) is not tuple
            or tuple(symbol for symbol, _ in self.trace_identities) != UNIVERSE
        ):
            raise ValueError("basket trace evidence must cover the ordered G1 universe")
        for symbol, trace_identity in self.trace_identities:
            if type(symbol) is not str:
                raise ValueError("basket trace symbols must be strings")
            _uuid5(trace_identity, "equity-trace identity")
        _uuid5(self.identity, "basket identity")


def _parse_timestamp(value: str, field: str) -> datetime:
    if type(value) is not str:
        raise ValueError(f"{field} must be a timestamp string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field} must be an ISO timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _validate_bars(cell: CellEvidence, bars: tuple[Bar, ...]) -> tuple[date, ...]:
    if type(cell) is not CellEvidence:
        raise ValueError("an exact G1 CellEvidence is required")
    if cell.regime != "continuous":
        raise ValueError("equity reconstruction requires the continuous G1 cell")
    if type(cell.symbol) is not str or cell.symbol not in UNIVERSE:
        raise ValueError("cell symbol is outside the accepted G1 universe")
    if type(bars) is not tuple or not bars:
        raise ValueError("accepted scoring bars must be a nonempty immutable tuple")

    sessions: list[date] = []
    previous_timestamp: datetime | None = None
    for bar in bars:
        if type(bar) is not Bar or bar.symbol.value != cell.symbol:
            raise ValueError("bars must match the exact cell symbol")
        if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
            raise ValueError("scoring bars must be strictly ordered")
        previous_timestamp = bar.timestamp
        session = bar.timestamp.astimezone(NY).date()
        if not DISCOVERY_START <= session < DISCOVERY_END_EXCLUSIVE:
            raise ValueError("scoring bars escaped the frozen 2019-2021 window")
        if session.weekday() >= 5:
            raise ValueError("scoring bar is off the daily trading-session grid")
        sessions.append(session)
    if any(left >= right for left, right in zip(sessions, sessions[1:], strict=False)):
        raise ValueError("scoring sessions must be unique and strictly ordered")
    if cell.session_count != len(bars):
        raise ValueError("cell and scoring-bar session counts do not match")
    if cell.first_session != bars[0].timestamp.isoformat():
        raise ValueError("cell first session does not match the scoring bars")
    if cell.last_session != bars[-1].timestamp.isoformat():
        raise ValueError("cell last session does not match the scoring bars")
    return tuple(sessions)


def _validate_fill(
    evidence: FillEvidence,
    bar: Bar,
    bar_index: int,
    bars: tuple[Bar, ...],
) -> OrderFill:
    if type(evidence) is not FillEvidence:
        raise ValueError("stress fills must use immutable accepted FillEvidence")
    fill_id = _uuid5(evidence.identity, "fill identity")
    if evidence.session != bar.timestamp.isoformat():
        raise ValueError("fill timestamp is off the accepted scoring-bar grid")
    filled_at = _parse_timestamp(evidence.session, "fill timestamp")
    if filled_at != bar.timestamp:
        raise ValueError("fill timestamp does not match its accepted scoring bar")
    if evidence.information_through is None:
        raise ValueError("stress fill lacks its information-through timestamp")
    information_through = _parse_timestamp(
        evidence.information_through, "information-through timestamp"
    )
    if bar_index == 0:
        warmup_session = information_through.astimezone(NY).date()
        if not VIEW_START <= warmup_session < DISCOVERY_START:
            raise ValueError("first scored fill lacks accepted pre-2019 warmup timing")
    elif information_through != bars[bar_index - 1].timestamp:
        raise ValueError("fill timing does not use the immediately prior session")
    if information_through >= filled_at:
        raise ValueError("fill information must precede execution")

    try:
        side = OrderSide(evidence.side)
    except (TypeError, ValueError):
        raise ValueError("fill side is not BUY or SELL") from None
    if evidence.risk_outcome not in {"APPROVED", "RESIZED"}:
        raise ValueError("stress fill has no accepted risk approval")
    if (
        type(evidence.quantity) is not Decimal
        or not evidence.quantity.is_finite()
        or evidence.quantity <= 0
        or evidence.quantity != evidence.quantity.to_integral_value()
    ):
        raise ValueError("stress fill quantity must be a positive whole share")
    if evidence.execution_open != bar.open:
        raise ValueError("stress fill execution open does not match the bar")
    if evidence.commission != STRESS_COSTS.commission:
        raise ValueError("stress fill commission does not match frozen economics")
    if type(evidence.price) is not Decimal or not evidence.price.is_finite():
        raise ValueError("stress fill price must be a finite Decimal")
    with localcontext(CONTEXT):
        slippage = STRESS_COSTS.slippage_bps / Decimal("10000")
        expected_price = bar.open * (
            Decimal("1") + slippage
            if side is OrderSide.BUY
            else Decimal("1") - slippage
        )
    if evidence.price != expected_price:
        raise ValueError("stress fill price does not match frozen slippage")
    if type(evidence.cash_after) is not Decimal or not evidence.cash_after.is_finite():
        raise ValueError("fill cash-after must be a finite Decimal")
    return OrderFill(
        fill_id=fill_id,
        # FillEvidence intentionally omits order IDs. The ledger's accepted
        # accounting projection uses only the immutable fill fields below.
        order_id=fill_id,
        symbol=bar.symbol,
        side=side,
        quantity=evidence.quantity,
        price=evidence.price,
        commission=evidence.commission,
        filled_at=filled_at,
    )


def reconstruct_stress_equity(
    cell: CellEvidence, bars: tuple[Bar, ...]
) -> ReconstructedSleeve:
    """Rebuild one continuous G1 stress trace from fills and adjusted closes.

    ``bars`` must be derived from the accepted, bounded ``DiscoveryView`` at
    the campaign boundary and contain only 2019-2021 scoring sessions. This
    function never compiles or evaluates a signal.
    """
    sessions = _validate_bars(cell, bars)
    metrics = cell.stress
    if type(metrics) is not Metrics:
        raise ValueError("cell stress evidence must use immutable accepted Metrics")
    if type(metrics.fills) is not tuple or metrics.fill_count != len(metrics.fills):
        raise ValueError("stress fill evidence count is inconsistent")

    bar_indexes = {bar.timestamp: index for index, bar in enumerate(bars)}
    projected_fills: list[tuple[int, FillEvidence, OrderFill]] = []
    previous_fill_index = -1
    seen_fill_ids: set[UUID] = set()
    for evidence in metrics.fills:
        if type(evidence) is not FillEvidence:
            raise ValueError("stress fills must use immutable accepted FillEvidence")
        timestamp = _parse_timestamp(evidence.session, "fill timestamp")
        try:
            bar_index = bar_indexes[timestamp]
        except KeyError:
            raise ValueError(
                "stress fill is off the accepted scoring-bar grid"
            ) from None
        if bar_index <= previous_fill_index:
            raise ValueError("stress fills are duplicated or out of order")
        previous_fill_index = bar_index
        fill = _validate_fill(evidence, bars[bar_index], bar_index, bars)
        if fill.fill_id in seen_fill_ids:
            raise ValueError("stress fill identity is duplicated")
        seen_fill_ids.add(fill.fill_id)
        projected_fills.append((bar_index, evidence, fill))

    ledger = PaperLedger(STARTING_CASH)
    equities: list[Decimal] = [STARTING_CASH]
    with localcontext(CONTEXT):
        fill_cursor = 0
        for index, bar in enumerate(bars):
            if fill_cursor < len(projected_fills):
                fill_index, evidence, fill = projected_fills[fill_cursor]
                if fill_index == index:
                    try:
                        ledger.apply_fill(fill)
                    except LedgerError as error:
                        raise ValueError(
                            "stress fill has an invalid ledger transition"
                        ) from error
                    if ledger.cash != evidence.cash_after:
                        raise ValueError(
                            "accepted cash-after evidence does not match the ledger"
                        )
                    fill_cursor += 1
            equity = ledger.create_account_snapshot(
                {bar.symbol: bar.close}, bar.timestamp
            ).equity
            equities.append(equity)
        if fill_cursor != len(projected_fills):
            raise ValueError("not all stress fills map to the scoring sessions")

    equity_values = tuple(equities)
    trace_identity = semantic_identity("equity-trace", equity_values)
    if trace_identity != metrics.equity_trace_identity:
        raise ValueError("reconstructed equity trace does not match accepted evidence")
    if equity_values[-1] != metrics.final_equity:
        raise ValueError("reconstructed final equity does not match accepted evidence")
    with localcontext(CONTEXT):
        total_return = equity_values[-1] / STARTING_CASH - Decimal("1")
    if total_return != metrics.total_return:
        raise ValueError("reconstructed total return does not match accepted evidence")
    return ReconstructedSleeve(
        cell.symbol,
        cell.candidate_id,
        sessions,
        equity_values,
        trace_identity,
    )


def aggregate_g1_basket(
    sleeves: tuple[ReconstructedSleeve, ...],
) -> BasketReturns:
    """Sum the exact eight sleeves and derive fixed, non-rebalanced returns."""
    if type(sleeves) is not tuple or len(sleeves) != len(UNIVERSE):
        raise ValueError("basket requires the complete ordered G1 universe")
    if any(type(sleeve) is not ReconstructedSleeve for sleeve in sleeves):
        raise ValueError("basket sleeves must be exact reconstructed evidence")
    if tuple(sleeve.symbol for sleeve in sleeves) != UNIVERSE:
        raise ValueError("basket requires the complete ordered G1 universe")
    if len({sleeve.candidate_id for sleeve in sleeves}) != 1:
        raise ValueError("basket sleeves must bind the same G1 candidate")
    sessions = sleeves[0].sessions
    if any(sleeve.sessions != sessions for sleeve in sleeves[1:]):
        raise ValueError("basket sleeves must use the same complete session sequence")

    with localcontext(CONTEXT):
        initial_equity = STARTING_CASH * len(UNIVERSE)
        aggregate_equities = tuple(
            sum(
                (sleeve.equity_values[index] for sleeve in sleeves),
                Decimal("0"),
            )
            for index in range(1, len(sleeves[0].equity_values))
        )
        previous = initial_equity
        returns: list[Decimal] = []
        for equity in aggregate_equities:
            if equity <= 0 or previous <= 0:
                raise ValueError("basket equity must remain positive")
            returns.append(equity / previous - Decimal("1"))
            previous = equity

    trace_identities = tuple(
        (sleeve.symbol, sleeve.trace_identity) for sleeve in sleeves
    )
    identity = semantic_identity(
        "g1-equity-return-basket",
        (
            sleeves[0].candidate_id,
            trace_identities,
            tuple(session.isoformat() for session in sessions),
            (initial_equity, *aggregate_equities),
            tuple(returns),
        ),
    )
    return BasketReturns(tuple(returns), identity, trace_identities)
