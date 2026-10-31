from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Context, Decimal, localcontext
from uuid import UUID

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.filtered_trend_campaign import (
    UNIVERSE,
    AggregateSummary,
    CandidateSummary,
    Costs,
    evaluate_cell,
    neighbor_configs,
    regime_plan,
    semantic_identity,
    shortlist,
    strategy_grid,
    summarize,
)


def bars_for(symbol="SPY"):
    warmup = tuple(
        datetime(2017, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(400)
    )
    trading = tuple(
        datetime(2019, 1, 2, tzinfo=UTC) + timedelta(days=i) for i in range(130)
    )
    values = []
    for i, stamp in enumerate(warmup + trading):
        price = (
            Decimal(100) + Decimal(i) / 10
            if i < 460
            else Decimal(146) - Decimal(i - 460)
        )
        values.append(
            Bar(Symbol(symbol), stamp, price, price + 1, price - 1, price, 1000)
        )
    return tuple(values)


@pytest.mark.parametrize("config", strategy_grid())
def test_every_configuration_excludes_execution_session_hlc(config):
    bars = bars_for()
    # Compare every execution fill, including current session; only equity may change.
    original = evaluate_cell(
        bars,
        config,
        regime_plan()[0],
        semantic_identity("test-candidate", asdict(config)),
    )
    chosen = 470
    changed = (
        bars[:chosen]
        + (
            replace(
                bars[chosen],
                high=Decimal(10000),
                low=Decimal("0.01"),
                close=Decimal(5000),
            ),
        )
        + bars[chosen + 1 :]
    )
    modified = evaluate_cell(changed, config, regime_plan()[0], original.candidate_id)
    cutoff = bars[chosen].timestamp.isoformat()
    for field in ("base", "stress"):
        before = tuple(f for f in getattr(original, field).fills if f.session <= cutoff)
        after = tuple(f for f in getattr(modified, field).fills if f.session <= cutoff)
        assert before == after
        assert all(f.information_through < f.session for f in before)


def test_sizing_commissions_risk_and_independent_stress():
    config = strategy_grid()[0]
    result = evaluate_cell(
        bars_for(), config, regime_plan()[0], semantic_identity("candidate", "base")
    )
    buy = result.base.fills[0]
    assert buy.side == "BUY"
    assert (
        buy.quantity
        == ((Decimal(95000) - 1) / (buy.execution_open * Decimal("1.0005"))) // 1
    )
    assert buy.cash_after >= Decimal(5000)
    assert buy.quantity != 100
    assert all(f.risk_outcome == "APPROVED" for f in result.base.fills)
    assert result.base.closed_trades > 0
    assert result.stress.total_return < result.base.total_return
    assert result.buy_and_hold.fill_count == 1
    assert result.buy_and_hold.closed_trades == 0
    assert result.buy_and_hold.realized_profit_loss == 0
    assert result.atr.count == result.session_count
    assert UUID(result.result_id).version == 5
    fixed_bars = bars_for()
    with localcontext(Context(prec=3)):
        again = evaluate_cell(fixed_bars, config, regime_plan()[0], result.candidate_id)
    assert again == result


def test_regimes_fresh_account_warmup_only():
    data = bars_for()
    later = tuple(
        replace(b, timestamp=b.timestamp.replace(year=2020)) for b in data[400:]
    )
    combined = data + later
    first = evaluate_cell(
        combined, strategy_grid()[0], regime_plan()[0], semantic_identity("c", 1)
    )
    second = evaluate_cell(
        combined, strategy_grid()[0], regime_plan()[1], semantic_identity("c", 1)
    )
    fill = second.buy_and_hold.fills[0]
    assert fill.cash_after == 100000 - fill.quantity * fill.price - fill.commission
    assert first.buy_and_hold.fills[0].session != fill.session
    assert all(f.session.startswith("2020-") for f in second.base.fills)
    assert len(regime_plan()) == 6
    assert regime_plan()[-1].end == date(2024, 1, 1)


def test_insufficient_history_future_bars_and_grid_changes_fail_closed():
    with pytest.raises(ValueError):
        Costs(Decimal(0), Decimal(5))
    for bars in (
        bars_for()[400:],
        bars_for()
        + (replace(bars_for()[-1], timestamp=datetime(2024, 1, 2, tzinfo=UTC)),),
    ):
        with pytest.raises(ValueError):
            evaluate_cell(
                bars, strategy_grid()[0], regime_plan()[0], semantic_identity("c", 1)
            )
    with pytest.raises(ValueError):
        shortlist(())
    with pytest.raises(ValueError):
        summarize(())


def test_all_lexicographic_shortlist_fields_and_ties():
    summary = AggregateSummary(
        20,
        20,
        Decimal("-.1"),
        Decimal(".1"),
        Decimal(".2"),
        Decimal(".1"),
        Decimal(1),
        4,
        Decimal("-.1"),
        Decimal(".1"),
        Decimal(".2"),
    )
    rows = tuple(
        CandidateSummary(semantic_identity("c", i), config, summary, summary)
        for i, config in enumerate(strategy_grid())
    )
    assert shortlist(rows) == rows[:10]
    priorities = (
        ("positive_continuous_symbols", 5),
        ("positive_regime_cells", 21),
        ("minimum_continuous_return", Decimal(0)),
        ("worst_continuous_drawdown", Decimal(".1")),
        ("median_continuous_return", Decimal(".2")),
        ("median_regime_return", Decimal(".2")),
        ("median_turnover", Decimal(".5")),
    )
    for field, value in priorities:
        better = replace(rows[-1], base=replace(summary, **{field: value}))
        assert shortlist(rows[:-1] + (better,))[0] == better
    # Each earlier field dominates all the lower fields.
    better = replace(
        rows[-1],
        base=replace(
            summary,
            positive_continuous_symbols=5,
            positive_regime_cells=0,
            minimum_continuous_return=Decimal("-.99"),
        ),
    )
    assert shortlist(rows[:-1] + (better,))[0] == better
    assert len(shortlist(rows)) == 10


def test_aggregation_complete_40_cells_and_eight_continuous():
    sample = evaluate_cell(
        bars_for(), strategy_grid()[0], regime_plan()[0], semantic_identity("c", 1)
    )
    cells = tuple(
        replace(sample, symbol=s, regime=r.label)
        for s in UNIVERSE
        for r in regime_plan()
    )
    aggregate = summarize(cells)
    assert aggregate.positive_regime_cells + aggregate.negative_regime_cells <= 40
    assert aggregate.minimum_continuous_return == sample.base.total_return
    assert (
        summarize(cells, stress=True).median_regime_return == sample.stress.total_return
    )
    with pytest.raises(ValueError):
        summarize(cells[:-1])
    with pytest.raises(ValueError):
        summarize(tuple(reversed(cells)))


def test_neighbors_only_predeclared_and_momentum_hypotheses_not_neighbors():
    for config in strategy_grid():
        neighbors = neighbor_configs(config)
        assert all(
            c in strategy_grid() and c != config and c.family == config.family
            for c in neighbors
        )
        if config.family == "MA_LONG_MOMENTUM":
            assert all(c.parameter == config.parameter for c in neighbors)


@pytest.mark.parametrize(
    "changes",
    [
        {
            (
                "branch",
                "--show-current",
            ): "feature/research-filtered-trend-multi-asset-current"
        },
        {("rev-parse", "HEAD"): "b" * 40},
        {("rev-parse", "HEAD^{tree}"): "b" * 40},
        {("rev-parse", "origin/develop"): "b" * 40},
        {("remote", "get-url", "origin"): "https://example.invalid/repository"},
        {("status", "--porcelain=v1", "--untracked-files=no"): " M source.py"},
    ],
)
def test_offline_cli_rejects_unaccepted_source_before_read_or_write(
    monkeypatch, tmp_path, changes
):
    from types import SimpleNamespace

    from scripts import run_filtered_trend_research as cli

    responses = {
        ("branch", "--show-current"): "develop",
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "HEAD^{tree}"): "c" * 40,
        ("rev-parse", "origin/develop"): "a" * 40,
        (
            "remote",
            "get-url",
            "origin",
        ): "https://github.com/callmedraken/ai-trading-bot.git",
        ("status", "--porcelain=v1", "--untracked-files=no"): "",
    }
    responses.update(changes)

    def fake_run(args, **kwargs):
        assert args[0] == "git"
        assert "fetch" not in args
        return SimpleNamespace(stdout=responses[tuple(args[3:])])

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    def forbidden(*args, **kwargs):
        pytest.fail("source failure must precede dataset read/campaign/output")

    monkeypatch.setattr(cli, "read_dataset", forbidden)
    output = tmp_path / "report"
    assert (
        cli.main(
            [
                "--run",
                "--dataset",
                str(tmp_path / "dataset.json"),
                "--output",
                str(output),
                "--expected-head",
                "a" * 40,
                "--expected-tree",
                "c" * 40,
            ]
        )
        == 1
    )
    assert not output.exists()
