from __future__ import annotations

import ast
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments import arch148_churn_research as research
from trading_bot.experiments import arch148_intraday as intraday
from trading_bot.experiments.arch148_churn_policy import CHURN_POLICIES, CONTROL
from trading_bot.experiments.arch148_sparse_backtest import run_sparse_backtest
from trading_bot.live_runtime.models import MarketQuality, MarketRegime, SignalAnalysis


def _dataset(day: date = date(2023, 11, 24)) -> intraday.SparseIntradayDataset:
    datasets = []
    slots = intraday.session_slots(day)
    for symbol in intraday.INTRADAY_SYMBOLS:
        bars = tuple(
            Bar(
                Symbol(symbol),
                timestamp,
                Decimal("100"),
                Decimal("101"),
                Decimal("99"),
                Decimal("100"),
                100,
            )
            for timestamp in slots
        )
        datasets.append(intraday.IntradaySymbolDataset(symbol, bars))
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return intraday.SparseIntradayDataset(
        start, start + timedelta(days=1), tuple(datasets)
    )


def _fixture_signal(market, *, authority):
    if market.as_of == intraday.session_slots(date(2023, 11, 24))[3]:
        return SignalAnalysis(
            MarketQuality.READY,
            MarketRegime.BULLISH,
            MarketRegime.BULLISH,
            None,
            None,
            "SYNTHETIC_ENTRY",
        )
    return SignalAnalysis(
        MarketQuality.READY,
        MarketRegime.NEUTRAL,
        None,
        None,
        None,
        "SYNTHETIC_NEUTRAL",
    )


def test_default_sparse_control_matches_explicit_control() -> None:
    dataset = _dataset()
    default = run_sparse_backtest(dataset, analyzer=_fixture_signal)
    explicit = run_sparse_backtest(
        dataset, analyzer=_fixture_signal, churn_policy=CONTROL
    )

    assert default == explicit
    assert default.trade_count == 1
    assert default.forced_flat_count == 1


def _metric_fixture() -> tuple[
    dict[str, object],
    tuple[research._TradeClose, ...],
    tuple[research._EquityMark, ...],
    tuple[Bar, ...],
]:
    day = date(2023, 11, 27)
    slots = intraday.session_slots(day)
    partition = {
        "name": "FIXTURE_DAY",
        "start": datetime(day.year, day.month, day.day, tzinfo=UTC),
        "end_exclusive": datetime(day.year, day.month, day.day, tzinfo=UTC)
        + timedelta(days=1),
    }
    specs = (
        (4, 5, "STOP", "10", "9", None),
        (6, 8, "REGIME_EXIT", "-2", "-3", MarketRegime.BEARISH),
        (10, 12, "SAFETY", "5", "4", None),
        (15, 18, "REGIME_EXIT", "-1", "-2", None),
        (24, 29, "FORCED_FLAT", "3", "2", None),
        (41, 43, "STOP", "-4", "-5", None),
    )
    closes = []
    for index, (entry_index, exit_index, reason, gross, net, reversal) in enumerate(
        specs
    ):
        holding = slots[exit_index] - slots[entry_index]
        trade = intraday.BacktestTrade(
            "TQQQ",
            slots[entry_index],
            Decimal("100"),
            slots[exit_index],
            Decimal("101"),
            Decimal("1"),
            Decimal(gross),
            Decimal(net),
            Decimal(net) / Decimal("100"),
            reason,
            holding,
        )
        closes.append(research._TradeClose(trade, Decimal(index + 1), reversal))
    last_mark = Decimal("105.00000000000000000000000000000000000000000000001")
    marks = (
        research._EquityMark(slots[0], Decimal("100")),
        research._EquityMark(slots[20], Decimal("120")),
        research._EquityMark(slots[40], Decimal("90")),
        research._EquityMark(slots[-1], last_mark),
    )
    qqq_bars = (
        Bar(
            Symbol("QQQ"),
            slots[0],
            Decimal("100"),
            Decimal("101"),
            Decimal("99"),
            Decimal("100"),
            100,
        ),
        Bar(
            Symbol("QQQ"),
            slots[-1],
            Decimal("109"),
            Decimal("111"),
            Decimal("108"),
            Decimal("110"),
            100,
        ),
    )
    return partition, tuple(closes), marks, qqq_bars


def test_partition_metrics_preserve_exact_lags_and_are_context_independent() -> None:
    partition, trades, marks, qqq_bars = _metric_fixture()
    kwargs = {
        "opening_equity": Decimal("100"),
        "trade_events": trades,
        "equity_marks": marks,
        "qqq_bars": qqq_bars,
        "session_dates": (date(2023, 11, 27),),
    }
    normal = research._partition_metrics(partition, **kwargs)
    with localcontext() as context:
        context.prec = 3
        constrained = research._partition_metrics(partition, **kwargs)

    assert constrained == normal
    assert normal["trade_count"] == 6
    assert normal["session_count"] == 1
    assert normal["gross_strategy_return"] == "0.11"
    assert normal["cost_adjusted_return"] == "0.05"
    assert normal["equity_derived_return"] != normal["cost_adjusted_return"]
    assert normal["qqq_buy_and_hold_return"] == "0.1"
    assert normal["maximum_drawdown"] == "0.25"
    assert normal["stop_hit_count"] == 2
    assert normal["forced_flat_count"] == 1
    assert normal["regime_exit_count"] == 2
    assert normal["safety_exit_count"] == 1
    assert normal["reversal_exit_count"] == 1
    assert normal["exit_reason_counts"] == {
        "FORCED_FLAT": 1,
        "REGIME_EXIT": 2,
        "SAFETY": 1,
        "STOP": 2,
    }
    assert normal["turnover"] == "21"
    assert normal["average_holding_duration_microseconds"] == "750000000"
    assert normal["median_holding_duration_microseconds"] == "600000000"
    assert normal["entries_per_session_distribution"] == {
        "zero": 0,
        "one": 0,
        "two": 0,
        "three_or_more": 1,
    }
    assert normal["entry_count_histogram"] == {"6": 1}
    assert normal["same_direction_reentry_lag_microseconds"] == [
        300_000_000,
        600_000_000,
        900_000_000,
        1_800_000_000,
        3_600_000_000,
    ]
    assert normal["same_direction_reentry_lag_buckets"] == {
        "5_to_10_minutes": 1,
        "10_to_15_minutes": 1,
        "15_to_30_minutes": 1,
        "30_to_60_minutes": 1,
        "60_minutes_or_more": 1,
    }
    assert normal["trade_audit"]["count"] == 6
    assert len(normal["trade_audit"]["sha256"]) == 64
    assert normal["equity_curve"]["count"] == 4
    assert len(normal["equity_curve"]["sha256"]) == 64


def test_reentry_requires_the_immediately_preceding_same_session_trade() -> None:
    day = date(2023, 11, 27)
    slots = intraday.session_slots(day)

    def trade(symbol: str, entry_index: int, exit_index: int) -> intraday.BacktestTrade:
        return intraday.BacktestTrade(
            symbol,
            slots[entry_index],
            Decimal("100"),
            slots[exit_index],
            Decimal("101"),
            Decimal("1"),
            Decimal("1"),
            Decimal("1"),
            Decimal("0.01"),
            "REGIME_EXIT",
            slots[exit_index] - slots[entry_index],
        )

    trades = (
        trade("TQQQ", 4, 5),
        trade("SQQQ", 6, 8),
        trade("TQQQ", 10, 12),
        trade("TQQQ", 13, 16),
    )

    assert research._same_direction_reentry_lags(trades) == (300_000_000,)


def test_requalification_fixture_binds_v3_artifact_shapes_and_sources(
    monkeypatch,
) -> None:
    dataset_identity = "fixture-dataset"
    custody_id = "fixture-custody"
    monkeypatch.setattr(research, "ACCEPTED_DATASET_IDENTITY", dataset_identity)
    monkeypatch.setattr(research, "ACCEPTED_DATASET_BYTE_LENGTH", 123)
    monkeypatch.setattr(research, "ACCEPTED_CUSTODY_BYTE_LENGTH", 456)
    dataset = SimpleNamespace(
        identity=dataset_identity,
        schedule_identity="fixture-schedule",
        schedule_digest="schedule-digest",
        price_basis="RAW",
    )
    custody = SimpleNamespace(
        dataset_identity=dataset_identity,
        evidence_id=custody_id,
    )
    document = {
        "schema": "arch148-b2-offline-requalification-evidence/v1",
        "classification": "OFFLINE_REQUALIFICATION_READY_FOR_INDEPENDENT_REVIEW",
        "open_start": research.ACCEPTED_REQUALIFICATION_OPEN_START_TEXT,
        "open_end_exclusive": research.ACCEPTED_REQUALIFICATION_OPEN_END_TEXT,
        "dataset": {
            "schema": "arch148-intraday-dataset/v3",
            "identity": dataset_identity,
            "sha256": research.ACCEPTED_DATASET_SHA256,
            "byte_length": 123,
        },
        "custody": {
            "schema": "arch148-intraday-custody-evidence/v3",
            "evidence_id": custody_id,
            "sha256": research.ACCEPTED_CUSTODY_SHA256,
            "byte_length": 456,
        },
        "requalification_source": {
            "candidate_head": research.ACCEPTED_REQUALIFICATION_SOURCE_HEAD,
            "candidate_tree": research.ACCEPTED_REQUALIFICATION_SOURCE_TREE,
        },
        "ordered_symbols": ["QQQ", "TQQQ", "SQQQ"],
        "expected_total_provider_pages": 430,
        "automatic_retry": "FORBIDDEN",
        "original_attempt": {
            "attempt_id": "bb1a784b-98d1-41fd-8d95-aa9fa463d5c9",
            "classification": (
                "CONSUMED / BLOCKED / QUALIFICATION_BAR_COUNT_MISMATCH / NO RETRY"
            ),
            "failure_code": "QUALIFICATION_BAR_COUNT_MISMATCH",
            "source_branch": research.ORIGINAL_ATTEMPT_SOURCE_BRANCH,
            "source_head": research.ORIGINAL_ATTEMPT_SOURCE_HEAD,
            "source_tree": research.ORIGINAL_ATTEMPT_SOURCE_TREE,
            "credential_read_attempt_count": 1,
            "provider_request_attempt_count": 430,
            "successful_page_count": 430,
            "unresolved_intent_status": "NONE",
            "automatic_retry": "FORBIDDEN",
        },
        "schedule": {"identity": "fixture-schedule", "sha256": "schedule-digest"},
        "price_basis": "RAW",
        "requalifier_effects": dict(research._ZERO_EFFECTS),
    }

    research._validate_requalification_document(
        document,
        dataset=dataset,
        dataset_byte_length=123,
        custody=custody,
        custody_byte_length=456,
    )
    assert document["open_start"] == "2016-01-01T00:00:00.000000Z"
    assert document["open_end_exclusive"] == "2024-01-01T00:00:00.000000Z"
    for field, accepted_seconds_only in (
        ("open_start", research.ACCEPTED_OPEN_START_TEXT),
        ("open_end_exclusive", research.ACCEPTED_OPEN_END_TEXT),
    ):
        accepted_microseconds = document[field]
        document[field] = accepted_seconds_only
        with pytest.raises(
            research.Arch148ChurnResearchError,
            match="REQUALIFICATION_EVIDENCE_MISMATCH",
        ):
            research._validate_requalification_document(
                document,
                dataset=dataset,
                dataset_byte_length=123,
                custody=custody,
                custody_byte_length=456,
            )
        document[field] = accepted_microseconds

    document["dataset"].pop("schema")
    with pytest.raises(
        research.Arch148ChurnResearchError,
        match="REQUALIFICATION_EVIDENCE_MISMATCH",
    ):
        research._validate_requalification_document(
            document,
            dataset=dataset,
            dataset_byte_length=123,
            custody=custody,
            custody_byte_length=456,
        )


def _baseline_run(cost_model: str) -> dict[str, object]:
    zero_cost = cost_model == "ZERO_COST"
    return {
        "cost_model": cost_model,
        "dataset_identity": research.ACCEPTED_DATASET_IDENTITY,
        "gross_strategy_return": (
            "2.5418471849143892008540066556142407165147299474555" if zero_cost else "0"
        ),
        "cost_adjusted_strategy_return": (
            "2.5418471849143892008540066556142407165147299474555"
            if zero_cost
            else "-0.99998648222118451927638026426240984471001182723079"
        ),
        "qqq_buy_and_hold_return": (
            "2.9917911185837207002274750271981010780338245475225"
        ),
        "cash_control_return": "0",
        "maximum_drawdown": (
            "0.44678527834928943167173740980613865853228572750815"
            if zero_cost
            else "0.9999866431350793575685413520580653038557076790965"
        ),
        "trade_count": 6233 if zero_cost else 6235,
        "stop_hit_count": 72 if zero_cost else 74,
        "forced_flat_count": 713,
        "reversal_exits": 0,
        "exit_reason_counts": {"STOP": 72 if zero_cost else 74},
        "turnover": "1000",
        "win_rate": "0.5",
        "average_win": "0.1",
        "average_loss": "-0.1",
        "average_holding_duration_us": 300_000_000,
        "equity_curve_points": 10,
        "equity_curve_sha256": "1" * 64,
        "trades_sha256": "2" * 64,
    }


def _baseline_document() -> dict[str, object]:
    return {
        "schema": research.ACCEPTED_BASELINE_SCHEMA,
        "classification": "COMPLETED_FOR_INDEPENDENT_REVIEW",
        "bounds": {
            "start": research.ACCEPTED_OPEN_START_TEXT,
            "end_exclusive": research.ACCEPTED_OPEN_END_TEXT,
            "final_holdout_accesses": 0,
        },
        "effects": dict(research._ZERO_EFFECTS),
        "input": {
            "custody_sha256": research.ACCEPTED_CUSTODY_SHA256,
            "dataset_identity": research.ACCEPTED_DATASET_IDENTITY,
            "dataset_sha256": research.ACCEPTED_DATASET_SHA256,
            "requalification_evidence_sha256": research.ACCEPTED_REQUALIFICATION_SHA256,
        },
        "runs": {
            "zero_cost": _baseline_run("ZERO_COST"),
            "conservative_10_bps": _baseline_run("CONSERVATIVE_10_BPS"),
        },
        "source": {
            "current_head": research.ACCEPTED_BASELINE_CURRENT_HEAD,
            "current_tree": research.ACCEPTED_BASELINE_CURRENT_TREE,
            "accepted_executable_head": research.ACCEPTED_EXECUTABLE_HEAD,
            "accepted_executable_tree": research.ACCEPTED_EXECUTABLE_TREE,
            "module_path": "src/trading_bot/experiments/arch148_sparse_backtest.py",
        },
    }


def test_baseline_fixture_binds_source_and_rejects_holdout_access() -> None:
    document = _baseline_document()
    assert document["bounds"]["start"] == "2016-01-01T00:00:00Z"
    assert document["bounds"]["end_exclusive"] == "2024-01-01T00:00:00Z"
    research._validate_baseline_document(document)

    document["bounds"]["final_holdout_accesses"] = True
    with pytest.raises(
        research.Arch148ChurnResearchError, match="BASELINE_BOUNDS_MISMATCH"
    ):
        research._validate_baseline_document(document)


def _report_payload() -> dict[str, object]:
    _, definitions = research._fixed_variant_material()
    partitions = [
        {
            "name": item["name"],
            "start": research._timestamp_text(item["start"]),
            "end_exclusive": research._timestamp_text(item["end_exclusive"]),
            "semantics": (
                "FULL_CHRONOLOGICAL_REPLAY"
                if item["name"] == "OPEN_FULL"
                else research.YEAR_PARTITION_SEMANTICS
            ),
        }
        for item in research._partition_plan()
    ]
    costs = [
        {
            "name": model.name,
            "slippage_bps": research._decimal_text(model.slippage_bps),
            "commission_per_side": research._decimal_text(model.commission_per_side),
        }
        for model in (intraday.ZERO_COST, intraday.CONSERVATIVE_COSTS)
    ]
    runs = [
        {
            "variant": policy.name,
            "cost_model": costs[cost_index],
            "partitions": [
                {"partition": partition["name"]} for partition in partitions
            ],
        }
        for policy in CHURN_POLICIES
        for cost_index in range(2)
    ]
    return {
        "schema": research.RESEARCH_SCHEMA,
        "source": {
            "candidate_head": "a" * 40,
            "candidate_tree": "b" * 40,
            "baseline_current_head": research.ACCEPTED_BASELINE_CURRENT_HEAD,
            "baseline_current_tree": research.ACCEPTED_BASELINE_CURRENT_TREE,
            "baseline_accepted_executable_head": research.ACCEPTED_EXECUTABLE_HEAD,
            "baseline_accepted_executable_tree": research.ACCEPTED_EXECUTABLE_TREE,
        },
        "input": {
            "dataset_identity": research.ACCEPTED_DATASET_IDENTITY,
            "dataset_sha256": research.ACCEPTED_DATASET_SHA256,
            "custody_evidence_id": "dbcced6a-b4cc-5d36-a33b-5e6df3d82baa",
            "custody_sha256": research.ACCEPTED_CUSTODY_SHA256,
            "requalification_evidence_sha256": research.ACCEPTED_REQUALIFICATION_SHA256,
            "baseline_report_sha256": research.ACCEPTED_BASELINE_SHA256,
            "baseline_dataset_identity": research.ACCEPTED_DATASET_IDENTITY,
        },
        "scope": {
            "name": "OPEN",
            "start": research._timestamp_text(intraday.OPEN_START),
            "end_exclusive": research._timestamp_text(intraday.OPEN_END_EXCLUSIVE),
            "partition_method": research.PARTITION_METHOD,
            "slice_interpretation": research.SLICE_INTERPRETATION,
            "final_holdout_accesses": 0,
        },
        "accepted_baseline": {
            "schema": research.ACCEPTED_BASELINE_SCHEMA,
            "classification": "COMPLETED_FOR_INDEPENDENT_REVIEW",
            "report_sha256": research.ACCEPTED_BASELINE_SHA256,
            "source": {
                "current_head": research.ACCEPTED_BASELINE_CURRENT_HEAD,
                "current_tree": research.ACCEPTED_BASELINE_CURRENT_TREE,
                "accepted_executable_head": research.ACCEPTED_EXECUTABLE_HEAD,
                "accepted_executable_tree": research.ACCEPTED_EXECUTABLE_TREE,
            },
            "runs": {"zero_cost": {}, "conservative_10_bps": {}},
        },
        "variant_definitions": list(definitions),
        "cost_models": costs,
        "partitions": partitions,
        "equity_mark_timestamp_semantics": research.EQUITY_MARK_TIMESTAMP_SEMANTICS,
        "runs": runs,
        "descriptive_ranking": [
            {
                "descriptive_rank": index,
                "variant": policy.name,
                "full_open_conservative_return": "0",
            }
            for index, policy in enumerate(CHURN_POLICIES, 1)
        ],
        "selection": {
            "automatic_selection": False,
            "selected_variant": None,
            "interpretation": "DESCRIPTIVE_RESEARCH_ONLY",
        },
        "effects": dict(research._ZERO_EFFECTS),
    }


def test_report_schema_and_identity_are_stable_and_path_free() -> None:
    first = research._make_report(_report_payload())
    second = research._make_report(_report_payload())
    round_trip = research.ChurnResearchReport.from_json(first.to_json())

    assert first == second == round_trip
    assert first.identity == research._research_identity(_report_payload())
    document = first.to_dict()
    assert document["schema"] == research.RESEARCH_SCHEMA
    assert document["scope"]["final_holdout_accesses"] == 0
    assert document["selection"]["automatic_selection"] is False
    assert "output_directory" not in first.to_json()
    assert "2026-11-19" not in first.to_json()


def test_non_open_and_holdout_bounds_are_rejected() -> None:
    with pytest.raises(
        research.Arch148ChurnResearchError, match="OPEN_DATASET_BOUNDS_MISMATCH"
    ):
        research._validate_open_bounds(
            intraday.OPEN_START,
            intraday.OPEN_END_EXCLUSIVE + timedelta(days=1),
        )
    with pytest.raises(
        research.Arch148ChurnResearchError, match="OPEN_DATASET_BOUNDS_MISMATCH"
    ):
        research._validate_open_bounds(
            intraday.OPEN_START + timedelta(days=1), intraday.OPEN_END_EXCLUSIVE
        )


def test_control_reproduction_mismatch_stops_before_candidate_evidence() -> None:
    zero = SimpleNamespace(
        gross_strategy_return=Decimal(
            "2.5418471849143892008540066556142407165147299474555"
        ),
        qqq_buy_and_hold_return=Decimal(
            "2.9917911185837207002274750271981010780338245475225"
        ),
        maximum_drawdown=Decimal(
            "0.44678527834928943167173740980613865853228572750815"
        ),
        trade_count=6233,
        stop_hit_count=72,
        forced_flat_count=713,
    )
    conservative = SimpleNamespace(
        cost_adjusted_strategy_return=Decimal(
            "-0.99998648222118451927638026426240984471001182723079"
        ),
        maximum_drawdown=Decimal("0.9999866431350793575685413520580653038557076790965"),
        trade_count=6235,
    )
    research._assert_control_reproduces_baseline(
        research._RunCapture(zero, (), ()),
        research._RunCapture(conservative, (), ()),
    )
    conservative.trade_count = 6234
    with pytest.raises(
        research.Arch148ChurnResearchError, match="CONTROL_BASELINE_MISMATCH"
    ):
        research._assert_control_reproduces_baseline(
            research._RunCapture(zero, (), ()),
            research._RunCapture(conservative, (), ()),
        )


def test_import_and_help_paths_do_not_open_inputs_or_create_output(
    monkeypatch, capsys
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("operator work must not start without explicit flag")

    monkeypatch.setattr(research, "_candidate_source_identity", forbidden)
    monkeypatch.setattr(research, "_load_accepted_inputs", forbidden)
    monkeypatch.setattr(research, "_fresh_output_directory", forbidden)

    assert research.main([]) == 0
    assert "--run-accepted-open" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        research.main(["--help"])
    assert exc.value.code == 0
    with pytest.raises(SystemExit) as exc:
        research.main(["--invalid-option"])
    assert exc.value.code == 2


def test_research_module_has_no_provider_or_holdout_import_path() -> None:
    module_path = Path(research.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden = {
        "alpaca",
        "robinhood",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "websocket",
    }
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not (imported & forbidden)
