from __future__ import annotations

import builtins
import copy
import hashlib
import json
import socket
import subprocess
import urllib.request
from datetime import UTC, date, datetime, time
from decimal import ROUND_UP, Decimal, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments import (
    arch149_monthly_defensive_rotation_evidence as evidence,
)
from trading_bot.experiments.arch149_monthly_defensive_rotation import (
    CASH,
    TargetResolution,
    monthly_rotation_identity,
)
from trading_bot.experiments.filtered_trend_campaign import (
    BASE_COSTS,
    STARTING_CASH,
    STRESS_COSTS,
)
from trading_bot.experiments.filtered_trend_data import (
    UNIVERSE,
    MultiAssetDataset,
    SymbolDataset,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)

NEW_YORK = ZoneInfo("America/New_York")
SOURCE_HEAD = "a" * 40
SOURCE_TREE = "b" * 40


@pytest.fixture(scope="module")
def synthetic_dataset() -> MultiAssetDataset:
    sessions = tuple(
        session
        for session in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= session < date(2024, 1, 1)
    )
    datasets: list[SymbolDataset] = []
    for symbol in UNIVERSE:
        bars: list[Bar] = []
        for index, session in enumerate(sessions):
            if index >= len(sessions) - 300:
                close = Decimal("120") - Decimal(
                    index - (len(sessions) - 300)
                ) / Decimal(10)
            else:
                close = Decimal("100") + Decimal((index % 800) - 400) / Decimal(20)
            timestamp = datetime.combine(session, time.min, tzinfo=NEW_YORK).astimezone(
                UTC
            )
            bars.append(
                Bar(
                    Symbol(symbol),
                    timestamp,
                    close,
                    close + Decimal(1),
                    close - Decimal(1),
                    close,
                    1_000,
                )
            )
        datasets.append(SymbolDataset(symbol, tuple(bars)))
    return MultiAssetDataset(tuple(datasets))


def _pin_synthetic_dataset(
    monkeypatch: pytest.MonkeyPatch, dataset: MultiAssetDataset
) -> tuple[str, int]:
    body = dataset.to_json().encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    monkeypatch.setattr(evidence, "_ACCEPTED_DATASET_IDENTITY", dataset.identity)
    monkeypatch.setattr(evidence, "_ACCEPTED_DATASET_SHA256", digest)
    return digest, len(body)


def _build_report(
    monkeypatch: pytest.MonkeyPatch, dataset: MultiAssetDataset
) -> evidence.RotationEvidenceReport:
    _pin_synthetic_dataset(monkeypatch, dataset)
    return evidence.evaluate_monthly_defensive_rotation(
        dataset, source_head=SOURCE_HEAD, source_tree=SOURCE_TREE
    )


def test_report_preserves_frozen_costs_partitions_and_full_continuous_capture(
    monkeypatch: pytest.MonkeyPatch, synthetic_dataset: MultiAssetDataset
) -> None:
    report = _build_report(monkeypatch, synthetic_dataset)

    assert report.strategy_id == "MONTHLY_CROSS_ASSET_DEFENSIVE_ROTATION_V1"
    assert report.source_head == SOURCE_HEAD
    assert report.source_tree == SOURCE_TREE
    assert report.dataset_identity == synthetic_dataset.identity
    assert report.dataset_evidence_binding.sha256 == report.dataset_sha256
    assert report.dataset_evidence_binding.byte_length == report.dataset_byte_length
    assert report.base.costs == BASE_COSTS
    assert report.stress.costs == STRESS_COSTS
    assert tuple(item.label for item in report.base.partitions) == (
        "EXPLORATORY_FULL",
        *(str(year) for year in range(2017, 2024)),
    )
    assert tuple(item.label for item in report.stress.partitions) == tuple(
        item.label for item in report.base.partitions
    )

    for case in (report.base, report.stress):
        replay = case.replay
        full = case.partitions[0]
        assert replay.initial_equity == STARTING_CASH
        assert full.opening_equity == STARTING_CASH
        assert full.final_equity == replay.final_equity
        assert full.month_end_signal_count == 84
        assert full.missing_input_no_rebalance_count == 0
        assert full.target_sequence_identity == replay.target_sequence_identity
        assert full.trade_audit_identity == replay.trade_audit_identity
        assert full.daily_equity_identity == replay.daily_equity_identity
        assert full.annual_returns == tuple(
            (str(year), case.partitions[index].net_return)
            for index, year in enumerate(range(2017, 2024), start=1)
        )
        carried_equity = STARTING_CASH
        for year, partition in zip(range(2017, 2024), case.partitions[1:], strict=True):
            assert partition.opening_equity == carried_equity
            assert partition.annual_returns == ((str(year), partition.net_return),)
            carried_equity = partition.final_equity
        assert carried_equity == full.final_equity
        assert all(mark.session_date.year >= 2017 for mark in replay.daily_marks)
        assert all(mark.session_date < date(2024, 1, 1) for mark in replay.daily_marks)
        assert all(target.signal_date.year >= 2017 for target in replay.targets)
        assert all(target.signal_date < date(2024, 1, 1) for target in replay.targets)
        assert all(
            fill.timestamp.astimezone(NEW_YORK).date().year >= 2017
            for fill in replay.fills
        )
        assert all(
            fill.timestamp.astimezone(NEW_YORK).date() < date(2024, 1, 1)
            for fill in replay.fills
        )
        assert replay.targets[-1].signal_date.year == 2023
        assert replay.targets[-1].signal_date.month == 12
        assert replay.targets[-1].resolution is TargetResolution.END_OF_EXPLORATION
        assert replay.targets[-1].next_session is None
        assert replay.targets[-1].target == CASH

        year = case.partitions[-1]
        expected_cash = sum(
            target.target == CASH
            for target in replay.targets
            if target.signal_date.year == 2023
        )
        assert year.cash_target_count == expected_cash
        assert year.executable_rebalance_count == sum(
            target.resolution is TargetResolution.REBALANCED
            and target.next_session is not None
            and target.next_session.year == 2023
            for target in replay.targets
        )
        assert year.unchanged_target_count == sum(
            target.resolution is TargetResolution.UNCHANGED_TARGET
            and target.next_session is not None
            and target.next_session.year == 2023
            for target in replay.targets
        )
        assert year.fill_count == sum(
            fill.timestamp.astimezone(NEW_YORK).date().year == 2023
            for fill in replay.fills
        )

    assert any(target.target != CASH for target in report.base.replay.targets)
    assert any(target.target == CASH for target in report.base.replay.targets)
    assert report.passive_comparisons[0].symbol == "SPY"
    assert report.passive_comparisons[1].symbol == "QQQ"
    first_scoring_session = min(
        mark.session_date for mark in report.base.replay.daily_marks
    )
    last_scoring_session = max(
        mark.session_date for mark in report.base.replay.daily_marks
    )
    assert all(
        item.basis == evidence.PASSIVE_COMPARISON_BASIS
        and item.start_session == first_scoring_session
        and item.end_session == last_scoring_session
        for item in report.passive_comparisons
    )
    assert report.zero_effects == tuple(
        (name, 0) for name in evidence.ZERO_EFFECT_COUNTER_NAMES
    )
    assert report.final_holdout_sealed is True
    assert report.reporting_conventions == evidence.REPORTING_CONVENTIONS
    assert any(
        "SAMPLE_DAILY_RETURN_DEVIATION_TIMES_SQRT_252" in item
        for item in report.reporting_conventions
    )

    serialized = json.loads(report.to_json())
    assert serialized["identity"] == report.identity
    assert (
        serialized["base"]["replay"]["daily_marks"][0]["session_date"] >= "2017-01-01"
    )
    assert (
        serialized["stress"]["replay"]["daily_marks"][-1]["session_date"] < "2024-01-01"
    )


def test_report_bytes_and_identity_ignore_ambient_decimal_context(
    monkeypatch: pytest.MonkeyPatch, synthetic_dataset: MultiAssetDataset
) -> None:
    _pin_synthetic_dataset(monkeypatch, synthetic_dataset)
    normal = evidence.evaluate_monthly_defensive_rotation(
        synthetic_dataset, source_head=SOURCE_HEAD, source_tree=SOURCE_TREE
    )
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_UP
        altered = evidence.evaluate_monthly_defensive_rotation(
            synthetic_dataset, source_head=SOURCE_HEAD, source_tree=SOURCE_TREE
        )
    assert altered.identity == normal.identity
    assert altered.to_json() == normal.to_json()


def test_fixed_stress_classification_boundaries() -> None:
    def full(
        *,
        net_return: Decimal = Decimal("0.05"),
        annual: tuple[Decimal, ...] = (Decimal("0.02"),) * 7,
        drawdown: Decimal = Decimal("0.35"),
    ) -> evidence.PartitionDiagnostics:
        component = monthly_rotation_identity("classification-fixture", ())
        return evidence.PartitionDiagnostics(
            label="EXPLORATORY_FULL",
            start=date(2017, 1, 1),
            end_exclusive=date(2024, 1, 1),
            opening_equity=Decimal("100"),
            final_equity=Decimal("105"),
            net_return=net_return,
            cagr=Decimal("0.01"),
            maximum_drawdown=drawdown,
            annualized_volatility=Decimal("0.1"),
            sharpe_ratio=Decimal("0.2"),
            annual_returns=tuple(
                (str(year), value)
                for year, value in zip(range(2017, 2024), annual, strict=True)
            ),
            month_end_signal_count=84,
            missing_input_no_rebalance_count=0,
            executable_rebalance_count=0,
            unchanged_target_count=0,
            cash_target_count=0,
            etf_switch_count=0,
            insufficient_whole_shares_count=0,
            fill_count=0,
            turnover_notional=Decimal(0),
            turnover=Decimal(0),
            time_invested=Decimal(0),
            months_held=tuple((symbol, 0) for symbol in UNIVERSE),
            entry_count_by_symbol=tuple((symbol, 0) for symbol in UNIVERSE),
            target_sequence_identity=component,
            trade_audit_identity=component,
            daily_equity_identity=component,
        )

    classify = evidence._classify_stress
    assert (
        classify(full())
        is evidence.ExploratoryClassification.EXPLORATORY_CANDIDATE_ONLY
    )
    assert (
        classify(full(net_return=Decimal(0)))
        is evidence.ExploratoryClassification.ECONOMICALLY_REJECTED
    )
    assert (
        classify(
            full(
                annual=(
                    Decimal("-0.1"),
                    Decimal("-0.1"),
                    Decimal(0),
                    Decimal("0.1"),
                    Decimal("0.1"),
                    Decimal("0.1"),
                    Decimal("0.1"),
                )
            )
        )
        is evidence.ExploratoryClassification.ECONOMICALLY_REJECTED
    )
    assert (
        classify(
            full(
                annual=(
                    Decimal("-0.1"),
                    Decimal("-0.1"),
                    Decimal("0.1"),
                    Decimal("0.1"),
                    Decimal("0.1"),
                    Decimal("0.1"),
                    Decimal("0.1"),
                )
            )
        )
        is evidence.ExploratoryClassification.EXPLORATORY_CANDIDATE_ONLY
    )
    assert (
        classify(
            full(
                annual=(
                    Decimal("-0.1"),
                    Decimal("-0.1"),
                    Decimal("-0.1"),
                    Decimal("0.1"),
                    Decimal("0.1"),
                    Decimal("0.1"),
                    Decimal("0.1"),
                )
            )
        )
        is evidence.ExploratoryClassification.ECONOMICALLY_REJECTED
    )
    assert (
        classify(full(drawdown=Decimal("0.3500000001")))
        is evidence.ExploratoryClassification.ECONOMICALLY_REJECTED
    )


def test_daily_risk_statistics_use_sample_deviation_and_zero_risk_free_sharpe() -> None:
    returns = (Decimal("0"), Decimal("0.02"))
    volatility, sharpe = evidence._daily_risk_statistics(returns)
    with localcontext(evidence.DECIMAL_CONTEXT):
        standard_deviation = (Decimal("0.0002")).sqrt()
        annual_factor = Decimal(252).sqrt()
        assert volatility == standard_deviation * annual_factor
        assert sharpe == Decimal("0.01") / standard_deviation * annual_factor
    assert evidence._daily_risk_statistics((Decimal("0.01"), Decimal("0.01"))) == (
        Decimal(0),
        None,
    )
    assert evidence._daily_risk_statistics((Decimal("0.01"),)) == (None, None)


def test_wrong_dataset_identity_and_hash_fail_before_any_replay(
    monkeypatch: pytest.MonkeyPatch, synthetic_dataset: MultiAssetDataset
) -> None:
    replay_was_called = False

    def no_replay(*args: object, **kwargs: object) -> object:
        nonlocal replay_was_called
        replay_was_called = True
        raise AssertionError("dataset rejection must precede replay")

    monkeypatch.setattr(evidence, "replay_monthly_defensive_rotation", no_replay)
    monkeypatch.setattr(evidence, "_ACCEPTED_DATASET_IDENTITY", "0" * 36 + "0001")
    with pytest.raises(
        evidence.MonthlyDefensiveRotationEvidenceError, match="identity"
    ):
        evidence.evaluate_monthly_defensive_rotation(
            synthetic_dataset, source_head=SOURCE_HEAD, source_tree=SOURCE_TREE
        )
    assert not replay_was_called

    monkeypatch.setattr(
        evidence, "_ACCEPTED_DATASET_IDENTITY", synthetic_dataset.identity
    )
    monkeypatch.setattr(evidence, "_ACCEPTED_DATASET_SHA256", "f" * 64)
    with pytest.raises(evidence.MonthlyDefensiveRotationEvidenceError, match="SHA-256"):
        evidence.evaluate_monthly_defensive_rotation(
            synthetic_dataset, source_head=SOURCE_HEAD, source_tree=SOURCE_TREE
        )
    assert not replay_was_called


def test_out_of_bound_bar_is_rejected_before_serialization(
    monkeypatch: pytest.MonkeyPatch, synthetic_dataset: MultiAssetDataset
) -> None:
    _pin_synthetic_dataset(monkeypatch, synthetic_dataset)
    forged = copy.copy(synthetic_dataset)
    first = copy.copy(synthetic_dataset.datasets[0])
    last_close = first.bars[-1].close
    future_bar = Bar(
        first.bars[-1].symbol,
        datetime.combine(date(2024, 1, 2), time.min, tzinfo=NEW_YORK),
        last_close,
        last_close + Decimal(1),
        last_close - Decimal(1),
        last_close,
        1_000,
    )
    object.__setattr__(first, "bars", (*first.bars, future_bar))
    object.__setattr__(forged, "datasets", (first, *synthetic_dataset.datasets[1:]))

    def serialization_forbidden(self: MultiAssetDataset) -> str:
        raise AssertionError("out-of-bounds date must be rejected before serialization")

    monkeypatch.setattr(MultiAssetDataset, "to_json", serialization_forbidden)
    with pytest.raises(evidence.MonthlyDefensiveRotationEvidenceError, match="outside"):
        evidence.evaluate_monthly_defensive_rotation(
            forged, source_head=SOURCE_HEAD, source_tree=SOURCE_TREE
        )


def test_imported_report_builder_has_no_io_network_or_process_effects(
    monkeypatch: pytest.MonkeyPatch, synthetic_dataset: MultiAssetDataset
) -> None:
    _pin_synthetic_dataset(monkeypatch, synthetic_dataset)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("effect-free report builder attempted an external effect")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    assert not hasattr(evidence, "main")
    report = evidence.evaluate_monthly_defensive_rotation(
        synthetic_dataset, source_head=SOURCE_HEAD, source_tree=SOURCE_TREE
    )
    assert report.base.replay.daily_marks
