from __future__ import annotations

import ast
import builtins
import hashlib
import importlib
import socket
import subprocess
import urllib.request
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments import (
    arch148_intraday as intraday,
)
from trading_bot.experiments import (
    arch148_intraday_momentum_evidence as evidence,
)


def _synthetic_dataset(
    authority: intraday.HistoricalIntradaySessionAuthority,
    days: tuple[date, ...],
) -> intraday.SparseIntradayDataset:
    bars_by_symbol: dict[str, list[Bar]] = {
        symbol: [] for symbol in intraday.INTRADAY_SYMBOLS
    }
    for session_date in days:
        slots = intraday.session_slots(session_date, authority)
        force_flat_at = authority.schedule_for(session_date).closes_at - timedelta(
            minutes=5
        )
        for symbol in intraday.INTRADAY_SYMBOLS:
            for index, timestamp in enumerate(slots):
                open_price = Decimal("100")
                close_price = Decimal("100")
                if symbol == "QQQ" and index == 5 and session_date != days[0]:
                    close_price = Decimal("101")
                if symbol == "QQQ" and timestamp == force_flat_at:
                    open_price = Decimal("101")
                if symbol == "TQQQ" and timestamp == force_flat_at:
                    open_price = Decimal("101")
                    close_price = Decimal("101")
                bars_by_symbol[symbol].append(
                    Bar(
                        Symbol(symbol),
                        timestamp,
                        open_price,
                        max(open_price, close_price) + Decimal("1"),
                        min(open_price, close_price) - Decimal("1"),
                        close_price,
                        100,
                    )
                )
    datasets = tuple(
        intraday.IntradaySymbolDataset(symbol, tuple(bars_by_symbol[symbol]))
        for symbol in intraday.INTRADAY_SYMBOLS
    )
    start = datetime.combine(days[0], datetime.min.time(), UTC)
    end = datetime.combine(days[-1] + timedelta(days=1), datetime.min.time(), UTC)
    return intraday.SparseIntradayDataset(start, end, datasets)


def _synthetic_custody(
    dataset: intraday.SparseIntradayDataset,
) -> intraday.SparseIntradayCustodyEvidence:
    pages = tuple(
        intraday.IntradayPageEvidence(
            symbol,
            (hashlib.sha256(f"synthetic:{symbol}".encode()).hexdigest(),),
            (len(symbol.encode()),),
        )
        for symbol in intraday.INTRADAY_SYMBOLS
    )
    return intraday.build_sparse_intraday_custody_evidence(dataset, pages)


def _bind_synthetic_authority(
    monkeypatch: pytest.MonkeyPatch,
    dataset: intraday.SparseIntradayDataset,
    custody: intraday.SparseIntradayCustodyEvidence,
    years: tuple[int, ...],
) -> None:
    dataset_bytes = dataset.to_json().encode("utf-8")
    custody_bytes = custody.to_json().encode("utf-8")
    monkeypatch.setattr(evidence, "_ACCEPTED_DATASET_IDENTITY", dataset.identity)
    monkeypatch.setattr(
        evidence,
        "_ACCEPTED_DATASET_SHA256",
        hashlib.sha256(dataset_bytes).hexdigest(),
    )
    monkeypatch.setattr(evidence, "_ACCEPTED_DATASET_BYTE_LENGTH", len(dataset_bytes))
    monkeypatch.setattr(evidence, "_ACCEPTED_CUSTODY_IDENTITY", custody.evidence_id)
    monkeypatch.setattr(
        evidence,
        "_ACCEPTED_CUSTODY_SHA256",
        hashlib.sha256(custody_bytes).hexdigest(),
    )
    monkeypatch.setattr(evidence, "_ACCEPTED_CUSTODY_BYTE_LENGTH", len(custody_bytes))
    monkeypatch.setattr(evidence, "_OPEN_START", dataset.start)
    monkeypatch.setattr(evidence, "_OPEN_END_EXCLUSIVE", dataset.end_exclusive)
    monkeypatch.setattr(evidence, "_REPORTING_YEARS", years)


def _evaluate(
    dataset: intraday.SparseIntradayDataset,
    custody: intraday.SparseIntradayCustodyEvidence,
    authority: intraday.HistoricalIntradaySessionAuthority,
) -> evidence.OpeningDriveResearchReport:
    return evidence.evaluate_opening_drive_research(
        dataset,
        custody,
        authority=authority,
        source_head="1" * 40,
        source_tree="2" * 40,
    )


def test_fixed_open_partition_plan_has_full_and_all_eight_years() -> None:
    partitions = evidence._partition_plan()

    assert len(partitions) == 9
    assert [item["name"] for item in partitions] == [
        "OPEN_FULL",
        *(f"OPEN_{year}" for year in range(2016, 2024)),
    ]
    assert partitions[0]["start"] == datetime(2016, 1, 1, tzinfo=UTC)
    assert partitions[-1]["end_exclusive"] == datetime(2024, 1, 1, tzinfo=UTC)
    assert all(
        left["end_exclusive"] == right["start"]
        for left, right in zip(partitions[1:], partitions[2:], strict=False)
    )


def test_classification_keeps_fixed_boundary_and_year_median() -> None:
    def partition(name: str, value: str) -> dict[str, object]:
        return {"partition": name, "net_strategy_return": value}

    years = [partition(f"OPEN_{year}", "0.01") for year in range(2016, 2024)]
    assert evidence._classify_result([partition("OPEN_FULL", "0.02"), *years]) == (
        "OPEN_CANDIDATE_ONLY"
    )
    assert evidence._classify_result([partition("OPEN_FULL", "0"), *years]) == (
        "ECONOMICALLY_REJECTED"
    )
    median_boundary = [
        partition(f"OPEN_{year}", "0" if year <= 2020 else "0.01")
        for year in range(2016, 2024)
    ]
    assert (
        evidence._classify_result([partition("OPEN_FULL", "0.02"), *median_boundary])
        == "ECONOMICALLY_REJECTED"
    )


def test_empty_partition_keeps_cash_and_marks_qqq_buy_hold_unobserved() -> None:
    partition = {
        "name": "OPEN_2016",
        "start": datetime(2016, 1, 1, tzinfo=UTC),
        "end_exclusive": datetime(2017, 1, 1, tzinfo=UTC),
    }
    metrics = evidence._partition_metrics(
        partition,
        opening_equity=Decimal("12000"),
        session_captures=(),
        trades=(),
        trade_turnovers=(),
        equity_marks=(),
        qqq_bars=(),
        missing_held_session_dates=(),
    )

    assert metrics["opening_equity"] == "12000"
    assert metrics["ending_equity"] == "12000"
    assert metrics["qqq_observed_bar_count"] == 0
    assert metrics["qqq_buy_and_hold_return"] is None
    assert metrics["opening_drive_hit_rate"] is None
    assert metrics["completed_trade_count"] == 0


def test_synthetic_report_binds_costs_diagnostics_and_is_context_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = intraday.HistoricalIntradaySessionAuthority()
    days = (date(2023, 11, 22), date(2023, 11, 24))
    dataset = _synthetic_dataset(authority, days)
    custody = _synthetic_custody(dataset)
    _bind_synthetic_authority(monkeypatch, dataset, custody, (2023,))

    with localcontext() as context:
        context.prec = 7
        first = _evaluate(dataset, custody, authority)
    with localcontext() as context:
        context.prec = 43
        second = _evaluate(dataset, custody, authority)

    assert first.to_json() == second.to_json()
    assert first.identity == second.identity
    assert first.sha256 == second.sha256
    restored = evidence.OpeningDriveResearchReport.from_json(first.to_json())
    assert restored == first
    assert first.classification == "OPEN_CANDIDATE_ONLY"
    document = first.to_dict()
    assert document["source"] == {"head": "1" * 40, "tree": "2" * 40}
    assert document["final_holdout_sealed"] is True
    assert set(document["effects"].values()) == {0}
    assert [item["name"] for item in document["partitions"]] == [
        "OPEN_FULL",
        "OPEN_2023",
    ]
    for run in document["runs"]:
        assert [item["partition"] for item in run["partitions"]] == [
            "OPEN_FULL",
            "OPEN_2023",
        ]
        full = run["partitions"][0]
        assert full["session_count"] == 2
        assert full["eligible_session_count"] == 1
        assert full["traded_session_count"] == 1
        assert full["no_trade_reason_distribution"]["MISSING_PREVIOUS_QQQ_CLOSE"] == 1
        assert full["tqqq_entry_count"] == 1
        assert full["early_close_session_count"] == 1
        assert full["traded_early_close_session_count"] == 1
        assert full["opening_drive_hit_rate"] == "1"
        assert full["opening_drive_hit_denominator"] == 1
        assert (
            full["conditional_qqq_late_window_return"]["positive_opening_drive"][
                "count"
            ]
            == 1
        )
        assert full["realized_trade_return_by_symbol"]["TQQQ"]["count"] == 1
        assert full["trade_audit"]["count"] == 1
        assert len(full["trade_audit"]["sha256"]) == 64
        assert len(full["equity_series"]["sha256"]) == 64


def test_annual_partitions_carry_continuous_ending_equity_forward(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = intraday.HistoricalIntradaySessionAuthority()
    days = (date(2022, 12, 29), date(2022, 12, 30), date(2023, 1, 3))
    dataset = _synthetic_dataset(authority, days)
    custody = _synthetic_custody(dataset)
    _bind_synthetic_authority(monkeypatch, dataset, custody, (2022, 2023))

    report = _evaluate(dataset, custody, authority).to_dict()
    for run in report["runs"]:
        full, prior_year, current_year = run["partitions"]
        assert prior_year["partition"] == "OPEN_2022"
        assert current_year["partition"] == "OPEN_2023"
        assert Decimal(prior_year["ending_equity"]) > Decimal("10000")
        assert current_year["opening_equity"] == prior_year["ending_equity"]
        assert full["ending_equity"] == current_year["ending_equity"]


def test_accepted_input_digest_mismatch_fails_before_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = intraday.HistoricalIntradaySessionAuthority()
    dataset = _synthetic_dataset(authority, (date(2023, 11, 22), date(2023, 11, 24)))
    custody = _synthetic_custody(dataset)
    _bind_synthetic_authority(monkeypatch, dataset, custody, (2023,))
    monkeypatch.setattr(evidence, "_ACCEPTED_DATASET_SHA256", "f" * 64)

    def unexpected_replay(*args: object, **kwargs: object) -> object:
        pytest.fail("replay must not run after accepted input mismatch")

    monkeypatch.setattr(evidence, "run_opening_drive_replay", unexpected_replay)
    with pytest.raises(evidence.Arch148IntradayMomentumEvidenceError) as error:
        _evaluate(dataset, custody, authority)
    assert error.value.code == "ACCEPTED_INPUT_DIGEST_MISMATCH"


def test_import_and_fake_build_do_not_call_external_effect_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = intraday.HistoricalIntradaySessionAuthority()
    dataset = _synthetic_dataset(authority, (date(2023, 11, 22), date(2023, 11, 24)))
    custody = _synthetic_custody(dataset)
    module_source = Path(evidence.__file__).read_text(encoding="utf-8")

    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("external effect or artifact access attempted")

    monkeypatch.setattr(builtins, "open", blocked)
    monkeypatch.setattr(Path, "open", blocked)
    monkeypatch.setattr(Path, "read_bytes", blocked)
    monkeypatch.setattr(Path, "read_text", blocked)
    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    importlib.reload(evidence)
    _bind_synthetic_authority(monkeypatch, dataset, custody, (2023,))

    report = _evaluate(dataset, custody, authority)
    restored = evidence.OpeningDriveResearchReport.from_json(report.to_json())
    assert restored.identity == report.identity
    assert restored.sha256 == report.sha256
    module_tree = ast.parse(module_source)
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(module_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(module_tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert not imported_modules.intersection(
        {"argparse", "os", "pathlib", "socket", "subprocess", "urllib"}
    )
    assert all(
        not (isinstance(node, ast.FunctionDef) and node.name == "main")
        for node in ast.walk(module_tree)
    )
