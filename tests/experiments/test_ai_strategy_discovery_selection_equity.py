"""Synthetic parity checks for source-only G1 equity reconstruction."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal, localcontext
from uuid import UUID

import pytest

from trading_bot.domain import Bar, OrderFill, OrderSide, Symbol
from trading_bot.experiments import ai_strategy_discovery_generation1 as generation1
from trading_bot.experiments import filtered_trend_campaign as campaign
from trading_bot.experiments.ai_strategy_discovery_selection_equity import (
    BasketReturns,
    ReconstructedSleeve,
    aggregate_g1_basket,
    reconstruct_stress_equity,
)
from trading_bot.experiments.filtered_trend_data import UNIVERSE
from trading_bot.ledger import PaperLedger

_UTC = UTC
_D = Decimal


def _bar(symbol: str, session: date, open_price: str, close: str) -> Bar:
    open_value = _D(open_price)
    close_value = _D(close)
    return Bar(
        Symbol(symbol),
        datetime.combine(session, time(21), tzinfo=_UTC),
        open_value,
        max(open_value, close_value) + _D("1"),
        min(open_value, close_value) - _D("1"),
        close_value,
        1000,
    )


def _bars(symbol: str = "SPY") -> tuple[Bar, ...]:
    return (
        _bar(symbol, date(2019, 1, 2), "100", "101"),
        _bar(symbol, date(2019, 1, 3), "102", "105"),
        _bar(symbol, date(2019, 1, 4), "106", "103"),
        _bar(symbol, date(2019, 1, 7), "104", "105"),
    )


def _synthetic_cell(
    bars: tuple[Bar, ...] | None = None,
) -> tuple[campaign.CellEvidence, tuple[Decimal, ...]]:
    bars = bars or _bars()
    symbol = bars[0].symbol.value
    starting_cash = campaign.STARTING_CASH
    ledger = PaperLedger(starting_cash)
    manual_cash = starting_cash
    manual_quantity = Decimal("0")
    fills: list[campaign.FillEvidence] = []
    expected_session_equity: list[Decimal] = []
    planned = {
        0: (OrderSide.BUY, Decimal("4")),
        2: (OrderSide.SELL, Decimal("1")),
    }

    for index, bar in enumerate(bars):
        planned_fill = planned.get(index)
        if planned_fill is not None:
            side, quantity = planned_fill
            slippage = campaign.STRESS_COSTS.slippage_bps / Decimal("10000")
            price = bar.open * (
                Decimal("1") + slippage
                if side is OrderSide.BUY
                else Decimal("1") - slippage
            )
            identity_material = (symbol, index, side.value)
            fill_id = UUID(
                campaign.semantic_identity("synthetic-fill", identity_material)
            )
            order_id = UUID(
                campaign.semantic_identity("synthetic-order", identity_material)
            )
            accepted_fill = OrderFill(
                fill_id,
                order_id,
                bar.symbol,
                side,
                quantity,
                price,
                campaign.STRESS_COSTS.commission,
                bar.timestamp,
            )
            ledger.apply_fill(accepted_fill)

            if side is OrderSide.BUY:
                manual_cash -= quantity * price + campaign.STRESS_COSTS.commission
                manual_quantity += quantity
            else:
                manual_cash += quantity * price - campaign.STRESS_COSTS.commission
                manual_quantity -= quantity
            assert ledger.cash == manual_cash
            assert manual_cash >= 0
            assert manual_quantity >= 0

            information_through = (
                datetime(2018, 12, 31, 21, tzinfo=_UTC).isoformat()
                if index == 0
                else bars[index - 1].timestamp.isoformat()
            )
            fills.append(
                campaign.FillEvidence(
                    str(fill_id),
                    bar.timestamp.isoformat(),
                    information_through,
                    side.value,
                    quantity,
                    bar.open,
                    price,
                    campaign.STRESS_COSTS.commission,
                    ledger.cash,
                    "APPROVED",
                )
            )

        expected_session_equity.append(manual_cash + manual_quantity * bar.close)

    equity_values = (starting_cash, *expected_session_equity)
    with localcontext(campaign.CONTEXT):
        total_return = equity_values[-1] / starting_cash - Decimal("1")
    trace_identity = campaign.semantic_identity("equity-trace", equity_values)
    metrics = campaign.Metrics(
        total_return=total_return,
        maximum_drawdown=Decimal("0"),
        final_equity=equity_values[-1],
        realized_profit_loss=Decimal("0"),
        fill_count=len(fills),
        closed_trades=1,
        turnover=Decimal("0"),
        time_invested=Decimal("0.75"),
        equity_trace_identity=trace_identity,
        fills=tuple(fills),
    )
    cell = campaign.CellEvidence(
        candidate_id=campaign.semantic_identity("synthetic-proposal", symbol),
        symbol=symbol,
        regime="continuous",
        result_id=campaign.semantic_identity("synthetic-cell", symbol),
        base=metrics,
        stress=metrics,
        buy_and_hold=metrics,
        buy_and_hold_stress=metrics,
        atr=campaign.AtrDescription(
            count=1,
            minimum=Decimal("1"),
            median=Decimal("1"),
            maximum=Decimal("1"),
            median_close_fraction=Decimal("0.01"),
        ),
        session_count=len(bars),
        first_session=bars[0].timestamp.isoformat(),
        last_session=bars[-1].timestamp.isoformat(),
    )
    return cell, equity_values


def _replace_stress(
    cell: campaign.CellEvidence, **changes: object
) -> campaign.CellEvidence:
    return replace(cell, stress=replace(cell.stress, **changes))


def test_reconstruction_matches_accepted_style_fill_cash_and_close_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = _bars()
    cell, expected_equity = _synthetic_cell(bars)

    def fail_signal_or_evaluator(*args: object, **kwargs: object) -> None:
        raise AssertionError("equity reconstruction must not evaluate signals")

    monkeypatch.setattr(campaign, "signal_series", fail_signal_or_evaluator)
    monkeypatch.setattr(campaign, "_evaluate_cell", fail_signal_or_evaluator)
    monkeypatch.setattr(campaign, "_evaluate_prepared_cell", fail_signal_or_evaluator)
    monkeypatch.setattr(
        generation1, "generation1_signal_series", fail_signal_or_evaluator
    )
    monkeypatch.setattr(
        generation1, "evaluate_generation1_program", fail_signal_or_evaluator
    )

    sleeve = reconstruct_stress_equity(cell, bars)

    assert sleeve.symbol == "SPY"
    assert sleeve.sessions == tuple(
        bar.timestamp.astimezone(campaign.NY).date() for bar in bars
    )
    assert sleeve.equity_values == expected_equity
    assert sleeve.trace_identity == cell.stress.equity_trace_identity
    assert sleeve.trace_identity == campaign.semantic_identity(
        "equity-trace", expected_equity
    )


def test_reconstruction_rejects_trace_and_cash_evidence_mismatch() -> None:
    bars = _bars()
    cell, expected_equity = _synthetic_cell(bars)
    wrong_trace = campaign.semantic_identity(
        "equity-trace", (*expected_equity[:-1], expected_equity[-1] + Decimal("1"))
    )
    with pytest.raises(ValueError, match="does not match accepted evidence"):
        reconstruct_stress_equity(
            _replace_stress(cell, equity_trace_identity=wrong_trace), bars
        )

    fills = list(cell.stress.fills)
    fills[0] = replace(fills[0], cash_after=fills[0].cash_after + Decimal("1"))
    with pytest.raises(ValueError, match="cash-after"):
        reconstruct_stress_equity(_replace_stress(cell, fills=tuple(fills)), bars)


def test_reconstruction_rejects_off_grid_timing_sessions_and_invalid_transitions() -> (
    None
):
    bars = _bars()
    cell, _ = _synthetic_cell(bars)
    fills = list(cell.stress.fills)
    fills[0] = replace(
        fills[0], session=datetime(2019, 1, 8, 21, tzinfo=_UTC).isoformat()
    )
    with pytest.raises(ValueError, match="off the accepted scoring-bar grid"):
        reconstruct_stress_equity(_replace_stress(cell, fills=tuple(fills)), bars)

    fills = list(cell.stress.fills)
    fills[0] = replace(
        fills[0], information_through=datetime(2019, 1, 2, 20, tzinfo=_UTC).isoformat()
    )
    with pytest.raises(ValueError, match="pre-2019 warmup timing"):
        reconstruct_stress_equity(_replace_stress(cell, fills=tuple(fills)), bars)

    sell_only = replace(cell.stress.fills[1], cash_after=Decimal("1"))
    with pytest.raises(ValueError, match="invalid ledger transition"):
        reconstruct_stress_equity(
            _replace_stress(cell, fills=(sell_only,), fill_count=1), bars
        )

    outside = (_bar("SPY", date(2022, 1, 3), "100", "101"),)
    with pytest.raises(ValueError, match="escaped the frozen 2019-2021 window"):
        reconstruct_stress_equity(cell, outside)

    with pytest.raises(ValueError, match="session counts do not match"):
        reconstruct_stress_equity(cell, bars[:-1])

    duplicate_session_bars = (
        bars[0],
        replace(
            bars[1],
            timestamp=datetime(2019, 1, 2, 22, tzinfo=_UTC),
        ),
        *bars[2:],
    )
    with pytest.raises(ValueError, match="sessions must be unique"):
        reconstruct_stress_equity(cell, duplicate_session_bars)


def _sleeve(
    symbol: str,
    candidate_id: str | None = None,
    equity_values: tuple[Decimal, ...] = (
        Decimal("100000"),
        Decimal("101000"),
        Decimal("102000"),
    ),
    sessions: tuple[date, ...] = (date(2019, 1, 2), date(2019, 1, 3)),
) -> ReconstructedSleeve:
    return ReconstructedSleeve(
        symbol,
        candidate_id
        or campaign.semantic_identity("synthetic-proposal", "shared-basket"),
        sessions,
        equity_values,
        campaign.semantic_identity("equity-trace", equity_values),
    )


def test_basket_uses_all_eight_sleeves_and_first_return_from_800k() -> None:
    sleeves = tuple(_sleeve(symbol) for symbol in UNIVERSE)

    basket = aggregate_g1_basket(sleeves)

    assert isinstance(basket, BasketReturns)
    with localcontext(campaign.CONTEXT):
        assert basket.daily_returns[0] == Decimal("808000") / Decimal("800000") - 1
        assert basket.daily_returns[1] == Decimal("816000") / Decimal("808000") - 1
    assert basket.trace_identities == tuple(
        (sleeve.symbol, sleeve.trace_identity) for sleeve in sleeves
    )
    assert basket.identity == aggregate_g1_basket(sleeves).identity


def test_basket_rejects_missing_duplicate_and_misaligned_sleeves() -> None:
    sleeves = tuple(_sleeve(symbol) for symbol in UNIVERSE)
    with pytest.raises(ValueError, match="complete ordered G1 universe"):
        aggregate_g1_basket(sleeves[:-1])
    with pytest.raises(ValueError, match="complete ordered G1 universe"):
        aggregate_g1_basket((sleeves[0], *sleeves[1:-1], sleeves[0]))
    mixed_proposal = _sleeve(
        UNIVERSE[-1],
        candidate_id=campaign.semantic_identity("synthetic-proposal", "other"),
    )
    with pytest.raises(ValueError, match="same G1 candidate"):
        aggregate_g1_basket((*sleeves[:-1], mixed_proposal))

    misaligned = _sleeve(UNIVERSE[-1], sessions=(date(2019, 1, 2), date(2019, 1, 4)))
    with pytest.raises(ValueError, match="same complete session sequence"):
        aggregate_g1_basket((*sleeves[:-1], misaligned))


def test_basket_rejects_scoring_dates_outside_the_frozen_window() -> None:
    equity_values = (Decimal("100000"), Decimal("101000"))
    with pytest.raises(ValueError, match="escaped the frozen G1 score window"):
        _sleeve(
            "SPY",
            equity_values=equity_values,
            sessions=(date(2022, 1, 3),),
        )
