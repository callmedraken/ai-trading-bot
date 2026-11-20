"""Deterministic OPEN-only Architecture 148 churn diagnostics.

The fixed policies are research comparisons, not runtime defaults or promotion
rules. Freqtrade's pinned GPL-3.0 CooldownPeriod is used only as a behavior
reference for an explicit post-close entry lock; no source is copied and no
dependency is added. This study narrows that concept to fixed elapsed-time
cooldown after a normal regime exit. Existing sparse execution, hard-stop,
safety, session and forced-flat rules remain owned by the accepted simulator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

from trading_bot.experiments.arch148_churn_policy import ChurnPolicy
from trading_bot.experiments.arch148_intraday import (
    _DECIMAL_CONTEXT,
    CONSERVATIVE_COSTS,
    OPEN_END_EXCLUSIVE,
    OPEN_START,
    ZERO_COST,
    Arch148IntradayError,
    BacktestCostModel,
    BacktestResult,
    BacktestTrade,
    HistoricalIntradaySessionAuthority,
    SparseIntradayCustodyEvidence,
    SparseIntradayDataset,
    expected_open_slots,
    verify_sparse_intraday_custody_evidence,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes
from trading_bot.live_runtime.models import MarketRegime

RESEARCH_SCHEMA: Final = "arch148-churn-research-evidence/v1"
RESEARCH_IDENTITY_VERSION: Final = "arch148-churn-research-identity/v1"
RESEARCH_NAMESPACE: Final = UUID("a143c6c7-0b62-5f50-8d41-e3bf52a3b4e0")
RESEARCH_READY: Final = "RESEARCH_REPORT_READY_FOR_INDEPENDENT_REVIEW"
FEATURE_BRANCH: Final = "feature/research-arch148-churn"
CANONICAL_ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"
CANONICAL_WORKTREE: Final = Path(
    r"F:\AI\worktrees\ai-trading-bot-arch148-churn-research-current"
)
EXPECTED_PARENT_HEAD: Final = "0e82457d71e584dc526b5e377d7f90867e515879"
EXPECTED_PARENT_TREE: Final = "7981d889617f1a4bcb41b1e314ea04d14c659e0a"
ACCEPTED_EXECUTABLE_HEAD: Final = "6fb78af8c2e07d906629fd95277343eb6d54fde3"
ACCEPTED_EXECUTABLE_TREE: Final = "01091cea96aa3aba6e5de8b88b64d8f722f116ba"
ACCEPTED_DATASET_IDENTITY: Final = "0308b694-c718-5b1a-a51c-9fcc4516bb81"
ACCEPTED_DATASET_SHA256: Final = (
    "0ba8b2437ef27a98fc48855aa8bb8d27ca3cdc0f2888e214305dde760686dbe0"
)
ACCEPTED_DATASET_BYTE_LENGTH: Final = 65_183_146
ACCEPTED_CUSTODY_SHA256: Final = (
    "93db9a9163cf445fdfd61abe68559196d240b09c1c9b70cdc0f7f452e3e8708b"
)
ACCEPTED_CUSTODY_BYTE_LENGTH: Final = 33_447
ACCEPTED_REQUALIFICATION_SHA256: Final = (
    "bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d"
)
ACCEPTED_REQUALIFICATION_SOURCE_HEAD: Final = ACCEPTED_EXECUTABLE_HEAD
ACCEPTED_REQUALIFICATION_SOURCE_TREE: Final = ACCEPTED_EXECUTABLE_TREE
ORIGINAL_ATTEMPT_SOURCE_HEAD: Final = "e11840c2ec7054c79183b3e33aee032f427d1a69"
ORIGINAL_ATTEMPT_SOURCE_TREE: Final = "c5d36dfcac5858f5f7a520cf076e2ed1cd3502c6"
ORIGINAL_ATTEMPT_SOURCE_BRANCH: Final = "feature/robinhood-live-prototype-current"
ACCEPTED_BASELINE_SHA256: Final = (
    "38cbba9beae664c675670af1ad96e86a56df2a9060c6cb924c1ad51ea4f9b85f"
)
ACCEPTED_BASELINE_SCHEMA: Final = "arch148-open-sparse-baseline-observation/v1"
ACCEPTED_OPEN_START_TEXT: Final = "2016-01-01T00:00:00Z"
ACCEPTED_OPEN_END_TEXT: Final = "2024-01-01T00:00:00Z"
ACCEPTED_REQUALIFICATION_OPEN_START_TEXT: Final = "2016-01-01T00:00:00.000000Z"
ACCEPTED_REQUALIFICATION_OPEN_END_TEXT: Final = "2024-01-01T00:00:00.000000Z"
ACCEPTED_BASELINE_CURRENT_HEAD: Final = EXPECTED_PARENT_HEAD
ACCEPTED_BASELINE_CURRENT_TREE: Final = EXPECTED_PARENT_TREE
BASELINE_REQUALIFICATION_DIRECTORY: Final = Path(
    r"F:\AI\temp\arch148-b2-offline-requalification-b9a8babd-4869-466d-a81f-fae08fe2aae5"
)
BASELINE_REPORT_PATH: Final = Path(
    r"F:\AI\temp\arch148-open-sparse-baseline-e3e27c29-8a9d-41c5-9ac0-d89a1d4cb5d1\baseline.json"
)
OUTPUT_ROOT: Final = Path(r"F:\AI\temp")
INITIAL_CAPITAL: Final = Decimal("10000")
REPORTING_YEARS: Final = tuple(range(2016, 2024))
PARTITION_METHOD: Final = (
    "ONE_CHRONOLOGICAL_REPLAY_WITH_PRIOR_YEAR_SETTLED_EQUITY_DENOMINATOR"
)
SLICE_INTERPRETATION: Final = "OBSERVED_OPEN_PARTITIONS_NOT_HOLDOUT_OR_QUALIFICATION"
YEAR_PARTITION_SEMANTICS: Final = (
    "OBSERVED_OPEN_REPORTING_SLICE_WITH_PREVIOUS_SLICE_ENDING_FLAT_EQUITY"
)
EQUITY_MARK_TIMESTAMP_SEMANTICS: Final = (
    "SCHEDULED_SLOT_START_WITH_POST_BAR_VALUATION; OMIT_WHEN_HELD_ETF_BAR_MISSING"
)
_GIT_ID = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_NEW_YORK = ZoneInfo("America/New_York")
_ZERO_EFFECTS: Final = {
    "credential_reads": 0,
    "network_calls": 0,
    "provider_calls": 0,
    "robinhood_calls": 0,
    "broker_calls": 0,
    "order_mutations": 0,
    "production_state_mutations": 0,
    "final_holdout_accesses": 0,
    "baseline_backtests": 0,
}


class Arch148ChurnResearchError(RuntimeError):
    """Sanitized fail-closed research error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ChurnResearchReport:
    """Canonical deterministic report bytes and their derived identity."""

    identity: str
    report_json: str

    def to_json(self) -> str:
        return self.report_json

    def to_dict(self) -> dict[str, object]:
        return json.loads(self.report_json)

    @classmethod
    def from_json(cls, value: str | bytes) -> ChurnResearchReport:
        body = value.encode("utf-8") if type(value) is str else value
        if type(body) is not bytes:
            raise Arch148ChurnResearchError("REPORT_JSON_INVALID")
        document = _parse_json_object(body, "REPORT_JSON_INVALID")
        if canonical_json_bytes(document) != body:
            raise Arch148ChurnResearchError("REPORT_JSON_NOT_CANONICAL")
        identity = document.get("identity")
        if type(identity) is not str or _UUID.fullmatch(identity) is None:
            raise Arch148ChurnResearchError("REPORT_IDENTITY_INVALID")
        if document.get("schema") != RESEARCH_SCHEMA:
            raise Arch148ChurnResearchError("REPORT_SCHEMA_INVALID")
        payload = dict(document)
        del payload["identity"]
        expected = _research_identity(payload)
        if identity != expected:
            raise Arch148ChurnResearchError("REPORT_IDENTITY_MISMATCH")
        _validate_report_payload(payload)
        return cls(identity, body.decode("utf-8"))


@dataclass(frozen=True, slots=True)
class ChurnResearchOutput:
    """Result of writing the one create-once external research artifact."""

    classification: str
    output_directory: Path
    report_sha256: str
    report_byte_length: int
    dataset_identity: str
    sparse_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class _EquityMark:
    at: datetime
    equity: Decimal


@dataclass(frozen=True, slots=True)
class _TradeClose:
    trade: BacktestTrade
    turnover: Decimal
    opposite_candidate: MarketRegime | None


@dataclass(frozen=True, slots=True)
class _RunCapture:
    result: BacktestResult
    trades: tuple[_TradeClose, ...]
    marks: tuple[_EquityMark, ...]


def _research_identity(payload: dict[str, object]) -> str:
    material = canonical_json_bytes([RESEARCH_IDENTITY_VERSION, payload]).decode(
        "utf-8"
    )
    return str(uuid5(RESEARCH_NAMESPACE, material))


def _parse_json_object(body: bytes, error_code: str) -> dict[str, object]:
    try:
        value = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except Arch148ChurnResearchError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise Arch148ChurnResearchError(error_code) from None
    if type(value) is not dict:
        raise Arch148ChurnResearchError(error_code)
    return value


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise Arch148ChurnResearchError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> None:
    raise Arch148ChurnResearchError("NONFINITE_JSON_NUMBER")


def _timestamp_text(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _decimal_text(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise Arch148ChurnResearchError("NONFINITE_DECIMAL_METRIC")
    return format(value, "f")


def _timedelta_microseconds(value: timedelta) -> int:
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


def _duration_decimal_microseconds(value: timedelta) -> Decimal:
    return Decimal(_timedelta_microseconds(value))


def _fixed_variant_material() -> tuple[
    tuple[ChurnPolicy, ...], tuple[dict[str, object], ...]
]:
    from trading_bot.experiments.arch148_churn_policy import (
        CHURN_POLICIES,
        CONTROL,
        OPPOSITE_CONFIRMATION_EXIT,
        OPPOSITE_EXIT_COOLDOWN_15M,
        OPPOSITE_EXIT_COOLDOWN_30M,
    )

    expected = (
        "CONTROL",
        "OPPOSITE_CONFIRMATION_EXIT",
        "OPPOSITE_EXIT_COOLDOWN_15M",
        "OPPOSITE_EXIT_COOLDOWN_30M",
    )
    policies = (
        CONTROL,
        OPPOSITE_CONFIRMATION_EXIT,
        OPPOSITE_EXIT_COOLDOWN_15M,
        OPPOSITE_EXIT_COOLDOWN_30M,
    )
    if tuple(item.name for item in CHURN_POLICIES) != expected:
        raise Arch148ChurnResearchError("VARIANT_SET_DRIFT")
    if tuple(item.name for item in policies) != expected:
        raise Arch148ChurnResearchError("VARIANT_SET_DRIFT")
    definitions = (
        {
            "name": "CONTROL",
            "entry_behavior": "EXISTING_ARCH148_UNCHANGED",
            "normal_exit": "EXISTING_CONFIRMED_REGIME_EXIT_UNCHANGED",
            "cooldown_minutes": 0,
        },
        {
            "name": "OPPOSITE_CONFIRMATION_EXIT",
            "entry_behavior": "UNCHANGED",
            "normal_exit": "TWO_CONSECUTIVE_OPPOSITE_CANDIDATES;NEUTRAL_DOES_NOT_EXIT",
            "cooldown_minutes": 0,
        },
        {
            "name": "OPPOSITE_EXIT_COOLDOWN_15M",
            "entry_behavior": "UNCHANGED",
            "normal_exit": "TWO_CONSECUTIVE_OPPOSITE_CANDIDATES;NEUTRAL_DOES_NOT_EXIT",
            "cooldown_minutes": 15,
        },
        {
            "name": "OPPOSITE_EXIT_COOLDOWN_30M",
            "entry_behavior": "UNCHANGED",
            "normal_exit": "TWO_CONSECUTIVE_OPPOSITE_CANDIDATES;NEUTRAL_DOES_NOT_EXIT",
            "cooldown_minutes": 30,
        },
    )
    return policies, definitions


def _partition_plan() -> tuple[dict[str, object], ...]:
    partitions: list[dict[str, object]] = [
        {
            "name": "OPEN_FULL",
            "start": OPEN_START,
            "end_exclusive": OPEN_END_EXCLUSIVE,
        }
    ]
    partitions.extend(
        {
            "name": f"OPEN_{year}",
            "start": datetime(year, 1, 1, tzinfo=UTC),
            "end_exclusive": datetime(year + 1, 1, 1, tzinfo=UTC),
        }
        for year in REPORTING_YEARS
    )
    if len(partitions) != 9 or partitions[-1]["end_exclusive"] != OPEN_END_EXCLUSIVE:
        raise Arch148ChurnResearchError("PARTITION_PLAN_INVALID")
    yearly = partitions[1:]
    if yearly[0]["start"] != partitions[0]["start"]:
        raise Arch148ChurnResearchError("PARTITION_PLAN_NOT_CONTIGUOUS")
    for previous, following in zip(yearly, yearly[1:], strict=False):
        if previous["end_exclusive"] != following["start"]:
            raise Arch148ChurnResearchError("PARTITION_PLAN_NOT_CONTIGUOUS")
    if yearly[-1]["end_exclusive"] != partitions[0]["end_exclusive"]:
        raise Arch148ChurnResearchError("PARTITION_PLAN_NOT_CONTIGUOUS")
    return tuple(partitions)


def _run_sparse_capture(
    dataset: SparseIntradayDataset,
    cost_model: BacktestCostModel,
    policy: ChurnPolicy,
) -> _RunCapture:
    from trading_bot.experiments.arch148_sparse_backtest import run_sparse_backtest

    close_events: list[_TradeClose] = []
    marks: list[_EquityMark] = []

    def on_trade_close(
        trade: BacktestTrade,
        turnover: Decimal,
        opposite_candidate: MarketRegime | None,
    ) -> None:
        close_events.append(_TradeClose(trade, turnover, opposite_candidate))

    def on_equity_mark(at: datetime, equity: Decimal) -> None:
        marks.append(_EquityMark(at, equity))

    try:
        result = run_sparse_backtest(
            dataset,
            cost_model=cost_model,
            initial_capital=INITIAL_CAPITAL,
            churn_policy=policy,
            on_equity_mark=on_equity_mark,
            on_trade_close=on_trade_close,
        )
    except Arch148IntradayError:
        raise Arch148ChurnResearchError("SPARSE_REPLAY_REJECTED") from None
    if tuple(item.trade for item in close_events) != result.trades:
        raise Arch148ChurnResearchError("TRADE_CALLBACK_MISMATCH")
    if tuple(item.equity for item in marks) != result.equity_curve:
        raise Arch148ChurnResearchError("EQUITY_CALLBACK_MISMATCH")
    with localcontext(_DECIMAL_CONTEXT):
        captured_turnover = sum((item.turnover for item in close_events), Decimal("0"))
    if captured_turnover != result.turnover:
        raise Arch148ChurnResearchError("TURNOVER_CALLBACK_MISMATCH")
    if not _strictly_ordered([item.at for item in marks]):
        raise Arch148ChurnResearchError("EQUITY_MARK_ORDER_INVALID")
    schedule_authority = HistoricalIntradaySessionAuthority()
    for mark in marks:
        session = schedule_authority.schedule_for(mark.at.astimezone(_NEW_YORK).date())
        if (
            mark.at.tzinfo is None
            or not mark.equity.is_finite()
            or session is None
            or not session.opens_at <= mark.at < session.closes_at
            or (mark.at - session.opens_at) % timedelta(minutes=5) != timedelta()
        ):
            raise Arch148ChurnResearchError("EQUITY_MARK_SLOT_INVALID")
    if not _strictly_ordered([item.trade.entry_at for item in close_events]):
        raise Arch148ChurnResearchError("TRADE_ORDER_INVALID")
    for item in close_events:
        if item.trade.exit_at < item.trade.entry_at:
            raise Arch148ChurnResearchError("TRADE_TIME_INVALID")
        if item.trade.holding_duration != item.trade.exit_at - item.trade.entry_at:
            raise Arch148ChurnResearchError("TRADE_DURATION_MISMATCH")
        if (
            item.trade.exit_reason != "REGIME_EXIT"
            and item.opposite_candidate is not None
        ):
            raise Arch148ChurnResearchError("REVERSAL_SOURCE_MISMATCH")
    return _RunCapture(result, tuple(close_events), tuple(marks))


def _strictly_ordered(values: list[datetime]) -> bool:
    return all(left < right for left, right in zip(values, values[1:], strict=False))


def _session_dates(dataset: SparseIntradayDataset) -> tuple[date, ...]:
    authority = HistoricalIntradaySessionAuthority()
    dates = tuple(
        dict.fromkeys(
            slot.astimezone(UTC).date()
            for slot in expected_open_slots(
                dataset.start, dataset.end_exclusive, authority
            )
        )
    )
    if not dates or tuple(sorted(set(dates))) != dates:
        raise Arch148ChurnResearchError("SESSION_SCHEDULE_INVALID")
    return dates


def _trade_record(event: _TradeClose) -> dict[str, object]:
    trade = event.trade
    return {
        "symbol": trade.symbol,
        "entry_at": _timestamp_text(trade.entry_at),
        "entry_price": _decimal_text(trade.entry_price),
        "exit_at": _timestamp_text(trade.exit_at),
        "exit_price": _decimal_text(trade.exit_price),
        "quantity": _decimal_text(trade.quantity),
        "gross_pnl": _decimal_text(trade.gross_pnl),
        "cost_adjusted_pnl": _decimal_text(trade.cost_adjusted_pnl),
        "return_pct": _decimal_text(trade.return_pct),
        "exit_reason": trade.exit_reason,
        "holding_duration_microseconds": _timedelta_microseconds(
            trade.holding_duration
        ),
        "turnover": _decimal_text(event.turnover),
        "opposite_candidate": (
            event.opposite_candidate.value
            if event.opposite_candidate is not None
            else None
        ),
    }


def _partition_metrics(
    partition: dict[str, object],
    *,
    opening_equity: Decimal,
    trade_events: tuple[_TradeClose, ...],
    equity_marks: tuple[_EquityMark, ...],
    qqq_bars: tuple[object, ...],
    session_dates: tuple[date, ...],
) -> dict[str, object]:
    start = partition["start"]
    end = partition["end_exclusive"]
    if type(start) is not datetime or type(end) is not datetime:
        raise Arch148ChurnResearchError("PARTITION_BOUNDARY_INVALID")
    period_trades = tuple(
        event for event in trade_events if start <= event.trade.entry_at < end
    )
    period_marks = tuple(mark for mark in equity_marks if start <= mark.at < end)
    period_qqq = tuple(bar for bar in qqq_bars if start <= bar.timestamp < end)
    period_sessions = tuple(
        session for session in session_dates if start.date() <= session < end.date()
    )
    if opening_equity <= 0 or not opening_equity.is_finite():
        raise Arch148ChurnResearchError("PARTITION_OPENING_EQUITY_INVALID")
    ending_equity = period_marks[-1].equity if period_marks else opening_equity
    if ending_equity <= 0 or not ending_equity.is_finite():
        raise Arch148ChurnResearchError("PARTITION_ENDING_EQUITY_INVALID")

    trades = tuple(event.trade for event in period_trades)
    with localcontext(_DECIMAL_CONTEXT):
        gross_pnl = sum((trade.gross_pnl for trade in trades), Decimal("0"))
        net_pnl = sum((trade.cost_adjusted_pnl for trade in trades), Decimal("0"))
        gross_return = gross_pnl / opening_equity
        net_return = net_pnl / opening_equity
        equity_return = ending_equity / opening_equity - Decimal("1")
        qqq_return = (
            (period_qqq[-1].close - period_qqq[0].open) / period_qqq[0].open
            if period_qqq
            else Decimal("0")
        )
        total_wins = sum(1 for trade in trades if trade.cost_adjusted_pnl > 0)
        wins = [trade.return_pct for trade in trades if trade.cost_adjusted_pnl > 0]
        losses = [trade.return_pct for trade in trades if trade.cost_adjusted_pnl < 0]
        win_rate = (
            Decimal(total_wins) / Decimal(len(trades)) if trades else Decimal("0")
        )
        average_win = (
            sum(wins, Decimal("0")) / Decimal(len(wins)) if wins else Decimal("0")
        )
        average_loss = (
            sum(losses, Decimal("0")) / Decimal(len(losses)) if losses else Decimal("0")
        )
        trades_per_session = (
            Decimal(len(trades)) / Decimal(len(period_sessions))
            if period_sessions
            else Decimal("0")
        )

    durations = sorted(
        _timedelta_microseconds(trade.holding_duration) for trade in trades
    )
    with localcontext(_DECIMAL_CONTEXT):
        if durations:
            midpoint = len(durations) // 2
            if len(durations) % 2:
                median_duration_us = Decimal(durations[midpoint])
            else:
                median_duration_us = Decimal(
                    durations[midpoint - 1] + durations[midpoint]
                ) / Decimal("2")
            average_duration_us = Decimal(sum(durations)) / Decimal(len(durations))
        else:
            median_duration_us = Decimal("0")
            average_duration_us = Decimal("0")

    peak = opening_equity
    max_drawdown = Decimal("0")
    with localcontext(_DECIMAL_CONTEXT):
        for mark in period_marks:
            peak = max(peak, mark.equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - mark.equity) / peak)

    entries_by_session: Counter[date] = Counter(
        event.trade.entry_at.astimezone(UTC).date() for event in period_trades
    )
    entry_count_histogram: Counter[int] = Counter(
        entries_by_session[session] for session in period_sessions
    )
    entry_distribution = {
        "zero": entry_count_histogram[0],
        "one": entry_count_histogram[1],
        "two": entry_count_histogram[2],
        "three_or_more": sum(
            count
            for entry_count, count in entry_count_histogram.items()
            if entry_count >= 3
        ),
    }
    exit_reasons = Counter(trade.exit_reason for trade in trades)
    if any(
        reason not in {"STOP", "FORCED_FLAT", "REGIME_EXIT", "SAFETY"}
        for reason in exit_reasons
    ):
        raise Arch148ChurnResearchError("UNKNOWN_EXIT_REASON")

    reentry_lags = _same_direction_reentry_lags(trades)
    lag_buckets = {
        "5_to_10_minutes": 0,
        "10_to_15_minutes": 0,
        "15_to_30_minutes": 0,
        "30_to_60_minutes": 0,
        "60_minutes_or_more": 0,
    }
    for lag in reentry_lags:
        if lag < 5 * 60_000_000:
            raise Arch148ChurnResearchError("REENTRY_LAG_BELOW_FIVE_MINUTES")
        if lag < 10 * 60_000_000:
            lag_buckets["5_to_10_minutes"] += 1
        elif lag < 15 * 60_000_000:
            lag_buckets["10_to_15_minutes"] += 1
        elif lag < 30 * 60_000_000:
            lag_buckets["15_to_30_minutes"] += 1
        elif lag < 60 * 60_000_000:
            lag_buckets["30_to_60_minutes"] += 1
        else:
            lag_buckets["60_minutes_or_more"] += 1

    trade_audit = [_trade_record(event) for event in period_trades]
    equity_audit = [
        [_timestamp_text(mark.at), _decimal_text(mark.equity)] for mark in period_marks
    ]
    stop_count = exit_reasons["STOP"]
    reversal_count = sum(
        1
        for event in period_trades
        if event.trade.exit_reason == "REGIME_EXIT"
        and event.opposite_candidate is not None
    )
    return {
        "partition": partition["name"],
        "start": _timestamp_text(start),
        "end_exclusive": _timestamp_text(end),
        "session_count": len(period_sessions),
        "opening_equity": _decimal_text(opening_equity),
        "ending_equity": _decimal_text(ending_equity),
        "equity_derived_return": _decimal_text(equity_return),
        "gross_strategy_return": _decimal_text(gross_return),
        "cost_adjusted_return": _decimal_text(net_return),
        "qqq_buy_and_hold_return": _decimal_text(qqq_return),
        "maximum_drawdown": _decimal_text(max_drawdown),
        "trade_count": len(trades),
        "trades_per_session": _decimal_text(trades_per_session),
        "stop_hit_count": stop_count,
        "forced_flat_count": exit_reasons["FORCED_FLAT"],
        "regime_exit_count": exit_reasons["REGIME_EXIT"],
        "safety_exit_count": exit_reasons["SAFETY"],
        "reversal_exit_count": reversal_count,
        "exit_reason_counts": dict(sorted(exit_reasons.items())),
        "turnover": _decimal_text(_sum_turnover(period_trades)),
        "win_rate": _decimal_text(win_rate),
        "average_win": _decimal_text(average_win),
        "average_loss": _decimal_text(average_loss),
        "average_holding_duration_microseconds": _decimal_text(average_duration_us),
        "median_holding_duration_microseconds": _decimal_text(median_duration_us),
        "entries_per_session_distribution": entry_distribution,
        "entry_count_histogram": {
            str(entry_count): count
            for entry_count, count in sorted(entry_count_histogram.items())
        },
        "same_direction_reentry_count": len(reentry_lags),
        "same_direction_reentry_lag_microseconds": list(reentry_lags),
        "same_direction_reentry_lag_buckets": lag_buckets,
        "trade_audit": {
            "count": len(trade_audit),
            "sha256": hashlib.sha256(canonical_json_bytes(trade_audit)).hexdigest(),
        },
        "equity_curve": {
            "count": len(equity_audit),
            "sha256": hashlib.sha256(canonical_json_bytes(equity_audit)).hexdigest(),
        },
    }


def _same_direction_reentry_lags(trades: tuple[BacktestTrade, ...]) -> tuple[int, ...]:
    by_session: dict[date, list[BacktestTrade]] = defaultdict(list)
    for trade in trades:
        by_session[trade.entry_at.astimezone(UTC).date()].append(trade)
    lags: list[int] = []
    for grouped in by_session.values():
        ordered = sorted(grouped, key=lambda item: (item.entry_at, item.exit_at))
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if previous.exit_at > current.entry_at:
                raise Arch148ChurnResearchError("OVERLAPPING_SESSION_TRADES")
            if previous.symbol == current.symbol:
                lags.append(
                    _timedelta_microseconds(current.entry_at - previous.exit_at)
                )
    return tuple(sorted(lags))


def _sum_turnover(events: tuple[_TradeClose, ...]) -> Decimal:
    with localcontext(_DECIMAL_CONTEXT):
        return sum((event.turnover for event in events), Decimal("0"))


def _build_run_partitions(
    capture: _RunCapture,
    dataset: SparseIntradayDataset,
) -> tuple[dict[str, object], ...]:
    plan = _partition_plan()
    session_dates = _session_dates(dataset)
    qqq_bars = dataset.bars_by_symbol["QQQ"]
    opening_equity = INITIAL_CAPITAL
    output: list[dict[str, object]] = []
    for partition in plan:
        metrics = _partition_metrics(
            partition,
            opening_equity=opening_equity,
            trade_events=capture.trades,
            equity_marks=capture.marks,
            qqq_bars=qqq_bars,
            session_dates=session_dates,
        )
        output.append(metrics)
        if partition["name"] != "OPEN_FULL":
            opening_equity = Decimal(metrics["ending_equity"])
    full = output[0]
    if (
        int(full["trade_count"]) != capture.result.trade_count
        or int(full["stop_hit_count"]) != capture.result.stop_hit_count
        or int(full["forced_flat_count"]) != capture.result.forced_flat_count
        or int(full["reversal_exit_count"]) != capture.result.reversal_exits
        or Decimal(full["turnover"]) != capture.result.turnover
    ):
        raise Arch148ChurnResearchError("FULL_RUN_METRICS_MISMATCH")
    if Decimal(full["gross_strategy_return"]) != capture.result.gross_strategy_return:
        raise Arch148ChurnResearchError("FULL_GROSS_RETURN_MISMATCH")
    if (
        Decimal(full["cost_adjusted_return"])
        != capture.result.cost_adjusted_strategy_return
    ):
        raise Arch148ChurnResearchError("FULL_NET_RETURN_MISMATCH")
    if (
        Decimal(full["qqq_buy_and_hold_return"])
        != capture.result.qqq_buy_and_hold_return
    ):
        raise Arch148ChurnResearchError("FULL_QQQ_RETURN_MISMATCH")
    if Decimal(full["maximum_drawdown"]) != capture.result.maximum_drawdown:
        raise Arch148ChurnResearchError("FULL_DRAWDOWN_MISMATCH")
    return tuple(output)


def _assert_control_reproduces_baseline(
    zero_cost: _RunCapture,
    conservative: _RunCapture,
) -> None:
    expected_zero = {
        "gross_strategy_return": Decimal(
            "2.5418471849143892008540066556142407165147299474555"
        ),
        "qqq_buy_and_hold_return": Decimal(
            "2.9917911185837207002274750271981010780338245475225"
        ),
        "maximum_drawdown": Decimal(
            "0.44678527834928943167173740980613865853228572750815"
        ),
        "trade_count": 6233,
        "stop_hit_count": 72,
        "forced_flat_count": 713,
    }
    expected_conservative = {
        "cost_adjusted_strategy_return": Decimal(
            "-0.99998648222118451927638026426240984471001182723079"
        ),
        "maximum_drawdown": Decimal(
            "0.9999866431350793575685413520580653038557076790965"
        ),
        "trade_count": 6235,
    }
    for field, expected in expected_zero.items():
        if getattr(zero_cost.result, field) != expected:
            raise Arch148ChurnResearchError("CONTROL_BASELINE_MISMATCH")
    for field, expected in expected_conservative.items():
        if getattr(conservative.result, field) != expected:
            raise Arch148ChurnResearchError("CONTROL_BASELINE_MISMATCH")


def _validate_report_payload(payload: dict[str, object]) -> None:
    required = {
        "schema",
        "source",
        "input",
        "scope",
        "accepted_baseline",
        "variant_definitions",
        "cost_models",
        "partitions",
        "equity_mark_timestamp_semantics",
        "runs",
        "descriptive_ranking",
        "selection",
        "effects",
    }
    if set(payload) != required or payload.get("schema") != RESEARCH_SCHEMA:
        raise Arch148ChurnResearchError("REPORT_FIELDS_INVALID")
    selection = payload.get("selection")
    if (
        type(selection) is not dict
        or set(selection)
        != {"automatic_selection", "selected_variant", "interpretation"}
        or type(selection.get("automatic_selection")) is not bool
        or selection.get("automatic_selection") is not False
        or selection.get("selected_variant") is not None
        or selection.get("interpretation") != "DESCRIPTIVE_RESEARCH_ONLY"
    ):
        raise Arch148ChurnResearchError("REPORT_SELECTION_INVALID")
    effects = payload.get("effects")
    if (
        type(effects) is not dict
        or set(effects) != set(_ZERO_EFFECTS)
        or any(type(value) is not int or value != 0 for value in effects.values())
    ):
        raise Arch148ChurnResearchError("REPORT_EFFECTS_INVALID")
    scope = payload.get("scope")
    if (
        type(scope) is not dict
        or set(scope)
        != {
            "name",
            "start",
            "end_exclusive",
            "partition_method",
            "slice_interpretation",
            "final_holdout_accesses",
        }
        or scope.get("name") != "OPEN"
        or scope.get("start") != _timestamp_text(OPEN_START)
        or scope.get("end_exclusive") != _timestamp_text(OPEN_END_EXCLUSIVE)
        or scope.get("partition_method") != PARTITION_METHOD
        or scope.get("slice_interpretation") != SLICE_INTERPRETATION
        or type(scope.get("final_holdout_accesses")) is not int
        or scope.get("final_holdout_accesses") != 0
    ):
        raise Arch148ChurnResearchError("REPORT_SCOPE_INVALID")
    source = payload.get("source")
    if (
        type(source) is not dict
        or set(source)
        != {
            "candidate_head",
            "candidate_tree",
            "baseline_current_head",
            "baseline_current_tree",
            "baseline_accepted_executable_head",
            "baseline_accepted_executable_tree",
        }
        or any(
            type(source.get(name)) is not str or _GIT_ID.fullmatch(source[name]) is None
            for name in source
        )
        or source.get("baseline_current_head") != ACCEPTED_BASELINE_CURRENT_HEAD
        or source.get("baseline_current_tree") != EXPECTED_PARENT_TREE
        or source.get("baseline_accepted_executable_head") != ACCEPTED_EXECUTABLE_HEAD
        or source.get("baseline_accepted_executable_tree") != ACCEPTED_EXECUTABLE_TREE
    ):
        raise Arch148ChurnResearchError("REPORT_SOURCE_INVALID")
    input_facts = payload.get("input")
    if (
        type(input_facts) is not dict
        or set(input_facts)
        != {
            "dataset_identity",
            "dataset_sha256",
            "custody_evidence_id",
            "custody_sha256",
            "requalification_evidence_sha256",
            "baseline_report_sha256",
            "baseline_dataset_identity",
        }
        or input_facts.get("dataset_identity") != ACCEPTED_DATASET_IDENTITY
        or input_facts.get("dataset_sha256") != ACCEPTED_DATASET_SHA256
        or input_facts.get("custody_evidence_id")
        != "dbcced6a-b4cc-5d36-a33b-5e6df3d82baa"
        or input_facts.get("custody_sha256") != ACCEPTED_CUSTODY_SHA256
        or input_facts.get("requalification_evidence_sha256")
        != ACCEPTED_REQUALIFICATION_SHA256
        or input_facts.get("baseline_report_sha256") != ACCEPTED_BASELINE_SHA256
        or input_facts.get("baseline_dataset_identity") != ACCEPTED_DATASET_IDENTITY
    ):
        raise Arch148ChurnResearchError("REPORT_INPUT_INVALID")
    baseline = payload.get("accepted_baseline")
    if (
        type(baseline) is not dict
        or baseline.get("schema") != ACCEPTED_BASELINE_SCHEMA
        or baseline.get("report_sha256") != ACCEPTED_BASELINE_SHA256
        or baseline.get("classification") != "COMPLETED_FOR_INDEPENDENT_REVIEW"
        or baseline.get("source")
        != {
            "current_head": ACCEPTED_BASELINE_CURRENT_HEAD,
            "current_tree": ACCEPTED_BASELINE_CURRENT_TREE,
            "accepted_executable_head": ACCEPTED_EXECUTABLE_HEAD,
            "accepted_executable_tree": ACCEPTED_EXECUTABLE_TREE,
        }
        or type(baseline.get("runs")) is not dict
        or set(baseline["runs"]) != {"zero_cost", "conservative_10_bps"}
    ):
        raise Arch148ChurnResearchError("REPORT_BASELINE_INVALID")
    runs = payload.get("runs")
    definitions = payload.get("variant_definitions")
    costs = payload.get("cost_models")
    partitions = payload.get("partitions")
    policies, fixed_definitions = _fixed_variant_material()
    expected_partitions = [
        {
            "name": item["name"],
            "start": _timestamp_text(item["start"]),
            "end_exclusive": _timestamp_text(item["end_exclusive"]),
            "semantics": (
                "FULL_CHRONOLOGICAL_REPLAY"
                if item["name"] == "OPEN_FULL"
                else YEAR_PARTITION_SEMANTICS
            ),
        }
        for item in _partition_plan()
    ]
    expected_costs = [
        {
            "name": model.name,
            "slippage_bps": _decimal_text(model.slippage_bps),
            "commission_per_side": _decimal_text(model.commission_per_side),
        }
        for model in (ZERO_COST, CONSERVATIVE_COSTS)
    ]
    expected_run_keys = [
        (policy.name, cost["name"]) for policy in policies for cost in expected_costs
    ]
    if (
        type(runs) is not list
        or len(runs) != 8
        or type(definitions) is not list
        or definitions != list(fixed_definitions)
        or type(costs) is not list
        or costs != expected_costs
        or type(partitions) is not list
        or partitions != expected_partitions
        or payload.get("equity_mark_timestamp_semantics")
        != EQUITY_MARK_TIMESTAMP_SEMANTICS
    ):
        raise Arch148ChurnResearchError("REPORT_FIXED_GRID_INVALID")
    if [
        (item.get("variant"), item.get("cost_model", {}).get("name"))
        if type(item) is dict and type(item.get("cost_model")) is dict
        else None
        for item in runs
    ] != expected_run_keys:
        raise Arch148ChurnResearchError("REPORT_RUN_ORDER_INVALID")
    for run_index, item in enumerate(runs):
        expected_cost = expected_costs[run_index % len(expected_costs)]
        if (
            type(item) is not dict
            or set(item) != {"variant", "cost_model", "partitions"}
            or item.get("cost_model") != expected_cost
            or type(item.get("partitions")) is not list
            or [
                part.get("partition")
                for part in item["partitions"]
                if type(part) is dict
            ]
            != [partition["name"] for partition in _partition_plan()]
            or len(item["partitions"]) != 9
        ):
            raise Arch148ChurnResearchError("REPORT_RUN_PARTITIONS_INVALID")
    ranking = payload.get("descriptive_ranking")
    variant_names = [policy.name for policy in policies]
    if (
        type(ranking) is not list
        or len(ranking) != len(variant_names)
        or any(type(item) is not dict for item in ranking)
        or [item.get("descriptive_rank") for item in ranking]
        != list(range(1, len(variant_names) + 1))
        or {item.get("variant") for item in ranking if type(item) is dict}
        != set(variant_names)
        or any(
            type(item) is not dict
            or set(item)
            != {"descriptive_rank", "variant", "full_open_conservative_return"}
            or type(item.get("full_open_conservative_return")) is not str
            for item in ranking
        )
    ):
        raise Arch148ChurnResearchError("REPORT_RANKING_INVALID")


def _make_report(payload_without_identity: dict[str, object]) -> ChurnResearchReport:
    _validate_report_payload(payload_without_identity)
    identity = _research_identity(payload_without_identity)
    document = {"identity": identity, **payload_without_identity}
    body = canonical_json_bytes(document)
    return ChurnResearchReport(identity, body.decode("utf-8"))


def _build_report(
    dataset: SparseIntradayDataset,
    *,
    source_head: str,
    source_tree: str,
    dataset_sha256: str,
    custody: SparseIntradayCustodyEvidence,
    custody_sha256: str,
    requalification_sha256: str,
    baseline_document: dict[str, object],
    captures: tuple[tuple[ChurnPolicy, BacktestCostModel, _RunCapture], ...],
) -> ChurnResearchReport:
    policies, definitions = _fixed_variant_material()
    partition_plan = _partition_plan()
    runs: list[dict[str, object]] = []
    lookup: dict[tuple[str, str], tuple[dict[str, object], ...]] = {}
    for policy, definition in zip(policies, definitions, strict=True):
        for model in (ZERO_COST, CONSERVATIVE_COSTS):
            capture = next(
                item_capture
                for item_policy, item_model, item_capture in captures
                if item_policy is policy and item_model == model
            )
            parts = _build_run_partitions(capture, dataset)
            lookup[(str(definition["name"]), model.name)] = parts
            runs.append(
                {
                    "variant": definition["name"],
                    "cost_model": {
                        "name": model.name,
                        "slippage_bps": _decimal_text(model.slippage_bps),
                        "commission_per_side": _decimal_text(model.commission_per_side),
                    },
                    "partitions": list(parts),
                }
            )

    ranking = sorted(
        (
            {
                "variant": definition["name"],
                "full_open_conservative_return": lookup[
                    (str(definition["name"]), CONSERVATIVE_COSTS.name)
                ][0]["cost_adjusted_return"],
            }
            for definition in definitions
        ),
        key=lambda item: (
            Decimal(str(item["full_open_conservative_return"])).copy_negate(),
            str(item["variant"]),
        ),
    )
    ranking = [
        {"descriptive_rank": index, **item} for index, item in enumerate(ranking, 1)
    ]
    baseline_source = baseline_document["source"]
    baseline_input = baseline_document["input"]
    baseline_runs = baseline_document["runs"]
    payload: dict[str, object] = {
        "schema": RESEARCH_SCHEMA,
        "source": {
            "candidate_head": source_head,
            "candidate_tree": source_tree,
            "baseline_current_head": baseline_source["current_head"],
            "baseline_current_tree": baseline_source["current_tree"],
            "baseline_accepted_executable_head": baseline_source[
                "accepted_executable_head"
            ],
            "baseline_accepted_executable_tree": baseline_source[
                "accepted_executable_tree"
            ],
        },
        "input": {
            "dataset_identity": dataset.identity,
            "dataset_sha256": dataset_sha256,
            "custody_evidence_id": custody.evidence_id,
            "custody_sha256": custody_sha256,
            "requalification_evidence_sha256": requalification_sha256,
            "baseline_report_sha256": ACCEPTED_BASELINE_SHA256,
            "baseline_dataset_identity": baseline_input["dataset_identity"],
        },
        "scope": {
            "name": "OPEN",
            "start": _timestamp_text(OPEN_START),
            "end_exclusive": _timestamp_text(OPEN_END_EXCLUSIVE),
            "partition_method": PARTITION_METHOD,
            "slice_interpretation": SLICE_INTERPRETATION,
            "final_holdout_accesses": 0,
        },
        "accepted_baseline": {
            "schema": ACCEPTED_BASELINE_SCHEMA,
            "classification": baseline_document["classification"],
            "report_sha256": ACCEPTED_BASELINE_SHA256,
            "source": {
                "current_head": baseline_source["current_head"],
                "current_tree": baseline_source["current_tree"],
                "accepted_executable_head": baseline_source["accepted_executable_head"],
                "accepted_executable_tree": baseline_source["accepted_executable_tree"],
            },
            "runs": baseline_runs,
        },
        "variant_definitions": list(definitions),
        "cost_models": [
            {
                "name": model.name,
                "slippage_bps": _decimal_text(model.slippage_bps),
                "commission_per_side": _decimal_text(model.commission_per_side),
            }
            for model in (ZERO_COST, CONSERVATIVE_COSTS)
        ],
        "partitions": [
            {
                "name": item["name"],
                "start": _timestamp_text(item["start"]),
                "end_exclusive": _timestamp_text(item["end_exclusive"]),
                "semantics": (
                    "FULL_CHRONOLOGICAL_REPLAY"
                    if item["name"] == "OPEN_FULL"
                    else YEAR_PARTITION_SEMANTICS
                ),
            }
            for item in partition_plan
        ],
        "equity_mark_timestamp_semantics": (EQUITY_MARK_TIMESTAMP_SEMANTICS),
        "runs": runs,
        "descriptive_ranking": ranking,
        "selection": {
            "automatic_selection": False,
            "selected_variant": None,
            "interpretation": "DESCRIPTIVE_RESEARCH_ONLY",
        },
        "effects": dict(_ZERO_EFFECTS),
    }
    return _make_report(payload)


def _validate_open_bounds(start: datetime, end_exclusive: datetime) -> None:
    if start != OPEN_START or end_exclusive != OPEN_END_EXCLUSIVE:
        raise Arch148ChurnResearchError("OPEN_DATASET_BOUNDS_MISMATCH")


def _assert_hash(body: bytes, expected: str, code: str) -> None:
    if hashlib.sha256(body).hexdigest() != expected:
        raise Arch148ChurnResearchError(code)


def _read_fixed(path: Path, code: str) -> bytes:
    try:
        if not path.is_absolute() or _is_reparse_point(path):
            raise Arch148ChurnResearchError(code)
        resolved = path.resolve(strict=True)
        if resolved != path or not path.is_file():
            raise Arch148ChurnResearchError(code)
        return path.read_bytes()
    except Arch148ChurnResearchError:
        raise
    except OSError:
        raise Arch148ChurnResearchError(code) from None


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return path.is_symlink()
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _validate_requalification_document(
    document: dict[str, object],
    *,
    dataset: SparseIntradayDataset,
    dataset_byte_length: int,
    custody: SparseIntradayCustodyEvidence,
    custody_byte_length: int,
) -> None:
    if (
        document.get("schema") != "arch148-b2-offline-requalification-evidence/v1"
        or document.get("classification")
        != "OFFLINE_REQUALIFICATION_READY_FOR_INDEPENDENT_REVIEW"
        or document.get("open_start") != ACCEPTED_REQUALIFICATION_OPEN_START_TEXT
        or document.get("open_end_exclusive") != ACCEPTED_REQUALIFICATION_OPEN_END_TEXT
        or document.get("dataset")
        != {
            "schema": "arch148-intraday-dataset/v3",
            "identity": ACCEPTED_DATASET_IDENTITY,
            "sha256": ACCEPTED_DATASET_SHA256,
            "byte_length": dataset_byte_length,
        }
        or document.get("custody")
        != {
            "schema": "arch148-intraday-custody-evidence/v3",
            "evidence_id": custody.evidence_id,
            "sha256": ACCEPTED_CUSTODY_SHA256,
            "byte_length": custody_byte_length,
        }
        or dataset_byte_length != ACCEPTED_DATASET_BYTE_LENGTH
        or custody_byte_length != ACCEPTED_CUSTODY_BYTE_LENGTH
        or document.get("requalification_source")
        != {
            "candidate_head": ACCEPTED_REQUALIFICATION_SOURCE_HEAD,
            "candidate_tree": ACCEPTED_REQUALIFICATION_SOURCE_TREE,
        }
        or dataset.identity != ACCEPTED_DATASET_IDENTITY
        or custody.dataset_identity != ACCEPTED_DATASET_IDENTITY
        or document.get("ordered_symbols") != ["QQQ", "TQQQ", "SQQQ"]
        or type(document.get("expected_total_provider_pages")) is not int
        or document.get("expected_total_provider_pages") != 430
        or document.get("automatic_retry") != "FORBIDDEN"
    ):
        raise Arch148ChurnResearchError("REQUALIFICATION_EVIDENCE_MISMATCH")
    original = document.get("original_attempt")
    if (
        type(original) is not dict
        or original.get("attempt_id") != "bb1a784b-98d1-41fd-8d95-aa9fa463d5c9"
        or original.get("classification")
        != "CONSUMED / BLOCKED / QUALIFICATION_BAR_COUNT_MISMATCH / NO RETRY"
        or original.get("failure_code") != "QUALIFICATION_BAR_COUNT_MISMATCH"
        or original.get("source_branch") != ORIGINAL_ATTEMPT_SOURCE_BRANCH
        or original.get("source_head") != ORIGINAL_ATTEMPT_SOURCE_HEAD
        or original.get("source_tree") != ORIGINAL_ATTEMPT_SOURCE_TREE
        or type(original.get("credential_read_attempt_count")) is not int
        or original.get("credential_read_attempt_count") != 1
        or type(original.get("provider_request_attempt_count")) is not int
        or original.get("provider_request_attempt_count") != 430
        or type(original.get("successful_page_count")) is not int
        or original.get("successful_page_count") != 430
        or original.get("unresolved_intent_status") != "NONE"
        or original.get("automatic_retry") != "FORBIDDEN"
    ):
        raise Arch148ChurnResearchError("ORIGINAL_ATTEMPT_EVIDENCE_MISMATCH")
    schedule = document.get("schedule")
    if (
        type(schedule) is not dict
        or schedule.get("identity") != dataset.schedule_identity
        or schedule.get("sha256") != dataset.schedule_digest
        or document.get("price_basis") != dataset.price_basis
    ):
        raise Arch148ChurnResearchError("REQUALIFICATION_SCHEDULE_MISMATCH")
    effects = document.get("requalifier_effects")
    if (
        type(effects) is not dict
        or set(effects) != set(_ZERO_EFFECTS)
        or any(type(value) is not int or value != 0 for value in effects.values())
    ):
        raise Arch148ChurnResearchError("REQUALIFICATION_EFFECTS_INVALID")


def _validate_baseline_document(document: dict[str, object]) -> None:
    if set(document) != {
        "bounds",
        "classification",
        "effects",
        "input",
        "runs",
        "schema",
        "source",
    }:
        raise Arch148ChurnResearchError("BASELINE_FIELDS_INVALID")
    if document.get("schema") != ACCEPTED_BASELINE_SCHEMA:
        raise Arch148ChurnResearchError("BASELINE_SCHEMA_MISMATCH")
    if document.get("classification") != "COMPLETED_FOR_INDEPENDENT_REVIEW":
        raise Arch148ChurnResearchError("BASELINE_CLASSIFICATION_MISMATCH")
    source = document.get("source")
    if (
        type(source) is not dict
        or set(source)
        != {
            "current_head",
            "current_tree",
            "accepted_executable_head",
            "accepted_executable_tree",
            "module_path",
        }
        or source.get("current_head") != ACCEPTED_BASELINE_CURRENT_HEAD
        or source.get("current_tree") != ACCEPTED_BASELINE_CURRENT_TREE
        or source.get("accepted_executable_head") != ACCEPTED_EXECUTABLE_HEAD
        or source.get("accepted_executable_tree") != ACCEPTED_EXECUTABLE_TREE
        or type(source.get("module_path")) is not str
    ):
        raise Arch148ChurnResearchError("BASELINE_SOURCE_MISMATCH")
    bounds = document.get("bounds")
    if (
        type(bounds) is not dict
        or set(bounds) != {"start", "end_exclusive", "final_holdout_accesses"}
        or bounds.get("start") != ACCEPTED_OPEN_START_TEXT
        or bounds.get("end_exclusive") != ACCEPTED_OPEN_END_TEXT
        or type(bounds.get("final_holdout_accesses")) is not int
        or bounds.get("final_holdout_accesses") != 0
    ):
        raise Arch148ChurnResearchError("BASELINE_BOUNDS_MISMATCH")
    expected_input = {
        "custody_sha256": ACCEPTED_CUSTODY_SHA256,
        "dataset_identity": ACCEPTED_DATASET_IDENTITY,
        "dataset_sha256": ACCEPTED_DATASET_SHA256,
        "requalification_evidence_sha256": ACCEPTED_REQUALIFICATION_SHA256,
    }
    if (
        type(document.get("input")) is not dict
        or set(document["input"]) != set(expected_input)
        or document.get("input") != expected_input
    ):
        raise Arch148ChurnResearchError("BASELINE_INPUT_MISMATCH")
    effects = document.get("effects")
    if (
        type(effects) is not dict
        or not effects
        or any(type(value) is not int or value != 0 for value in effects.values())
    ):
        raise Arch148ChurnResearchError("BASELINE_EFFECTS_INVALID")
    runs = document.get("runs")
    if type(runs) is not dict or set(runs) != {"zero_cost", "conservative_10_bps"}:
        raise Arch148ChurnResearchError("BASELINE_RUNS_INVALID")
    for key, model_name in (
        ("zero_cost", "ZERO_COST"),
        ("conservative_10_bps", "CONSERVATIVE_10_BPS"),
    ):
        run = runs[key]
        if (
            type(run) is not dict
            or set(run)
            != {
                "cost_model",
                "dataset_identity",
                "gross_strategy_return",
                "cost_adjusted_strategy_return",
                "qqq_buy_and_hold_return",
                "cash_control_return",
                "maximum_drawdown",
                "trade_count",
                "stop_hit_count",
                "forced_flat_count",
                "reversal_exits",
                "exit_reason_counts",
                "turnover",
                "win_rate",
                "average_win",
                "average_loss",
                "average_holding_duration_us",
                "equity_curve_points",
                "equity_curve_sha256",
                "trades_sha256",
            }
            or run.get("cost_model") != model_name
            or run.get("dataset_identity") != ACCEPTED_DATASET_IDENTITY
            or type(run.get("equity_curve_sha256")) is not str
            or _SHA256.fullmatch(run["equity_curve_sha256"]) is None
            or type(run.get("trades_sha256")) is not str
            or _SHA256.fullmatch(run["trades_sha256"]) is None
        ):
            raise Arch148ChurnResearchError("BASELINE_RUN_BINDING_MISMATCH")
    zero = runs["zero_cost"]
    conservative = runs["conservative_10_bps"]
    exact_zero = {
        "gross_strategy_return": "2.5418471849143892008540066556142407165147299474555",
        "qqq_buy_and_hold_return": (
            "2.9917911185837207002274750271981010780338245475225"
        ),
        "maximum_drawdown": "0.44678527834928943167173740980613865853228572750815",
        "trade_count": 6233,
        "stop_hit_count": 72,
        "forced_flat_count": 713,
    }
    exact_conservative = {
        "cost_adjusted_strategy_return": (
            "-0.99998648222118451927638026426240984471001182723079"
        ),
        "maximum_drawdown": "0.9999866431350793575685413520580653038557076790965",
        "trade_count": 6235,
    }
    for key, expected in exact_zero.items():
        if key.endswith("_count"):
            if type(zero.get(key)) is not int or zero.get(key) != expected:
                raise Arch148ChurnResearchError("BASELINE_ACCEPTED_METRICS_MISMATCH")
        else:
            if type(zero.get(key)) is not str or Decimal(zero[key]) != Decimal(
                expected
            ):
                raise Arch148ChurnResearchError("BASELINE_ACCEPTED_METRICS_MISMATCH")
    for key, expected in exact_conservative.items():
        if key.endswith("_count"):
            if (
                type(conservative.get(key)) is not int
                or conservative.get(key) != expected
            ):
                raise Arch148ChurnResearchError("BASELINE_ACCEPTED_METRICS_MISMATCH")
        else:
            if type(conservative.get(key)) is not str or Decimal(
                conservative[key]
            ) != Decimal(expected):
                raise Arch148ChurnResearchError("BASELINE_ACCEPTED_METRICS_MISMATCH")


def _candidate_source_identity() -> tuple[str, str]:
    try:
        resolved = CANONICAL_WORKTREE.resolve(strict=True)
        source_root = Path(__file__).resolve().parents[3]
        if resolved != CANONICAL_WORKTREE or source_root != CANONICAL_WORKTREE:
            raise Arch148ChurnResearchError("CANDIDATE_WORKTREE_MISMATCH")
        branch = _git_output("branch", "--show-current")
        origin = _git_output("remote", "get-url", "origin")
        head = _git_output("rev-parse", "HEAD")
        tree = _git_output("rev-parse", "HEAD^{tree}")
        parents = _git_output("show", "-s", "--format=%P", "HEAD")
        parent_tree = _git_output("rev-parse", f"{EXPECTED_PARENT_HEAD}^{{tree}}")
        status = _git_output("status", "--porcelain=v1", "--untracked-files=all")
    except Arch148ChurnResearchError:
        raise
    except (OSError, subprocess.SubprocessError):
        raise Arch148ChurnResearchError("CANDIDATE_GIT_FACTS_UNAVAILABLE") from None
    if (
        branch != FEATURE_BRANCH
        or origin != CANONICAL_ORIGIN
        or parents.split() != [EXPECTED_PARENT_HEAD]
        or parent_tree != EXPECTED_PARENT_TREE
        or status
        or _GIT_ID.fullmatch(head) is None
        or _GIT_ID.fullmatch(tree) is None
    ):
        raise Arch148ChurnResearchError("CANDIDATE_SOURCE_NOT_EXACT_CLEAN")
    return head, tree


def _git_output(*args: str) -> str:
    command = [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(CANONICAL_WORKTREE),
        *args,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def _load_accepted_inputs() -> tuple[
    SparseIntradayDataset,
    SparseIntradayCustodyEvidence,
    dict[str, object],
    dict[str, object],
]:
    dataset_path = BASELINE_REQUALIFICATION_DIRECTORY / "dataset.json"
    custody_path = BASELINE_REQUALIFICATION_DIRECTORY / "custody-evidence.json"
    evidence_path = BASELINE_REQUALIFICATION_DIRECTORY / "evidence.json"
    dataset_bytes = _read_fixed(dataset_path, "DATASET_READ_FAILED")
    custody_bytes = _read_fixed(custody_path, "CUSTODY_READ_FAILED")
    evidence_bytes = _read_fixed(evidence_path, "REQUALIFICATION_READ_FAILED")
    baseline_bytes = _read_fixed(BASELINE_REPORT_PATH, "BASELINE_READ_FAILED")
    _assert_hash(dataset_bytes, ACCEPTED_DATASET_SHA256, "DATASET_HASH_MISMATCH")
    _assert_hash(custody_bytes, ACCEPTED_CUSTODY_SHA256, "CUSTODY_HASH_MISMATCH")
    _assert_hash(
        evidence_bytes,
        ACCEPTED_REQUALIFICATION_SHA256,
        "REQUALIFICATION_HASH_MISMATCH",
    )
    _assert_hash(baseline_bytes, ACCEPTED_BASELINE_SHA256, "BASELINE_HASH_MISMATCH")
    try:
        dataset = SparseIntradayDataset.from_json(dataset_bytes)
        custody = SparseIntradayCustodyEvidence.from_json(custody_bytes)
        verify_sparse_intraday_custody_evidence(dataset, custody)
    except Arch148IntradayError:
        raise Arch148ChurnResearchError("ACCEPTED_INPUT_SCHEMA_INVALID") from None
    _validate_open_bounds(dataset.start, dataset.end_exclusive)
    if dataset.identity != ACCEPTED_DATASET_IDENTITY:
        raise Arch148ChurnResearchError("DATASET_IDENTITY_MISMATCH")
    evidence = _parse_json_object(evidence_bytes, "REQUALIFICATION_EVIDENCE_INVALID")
    baseline = _parse_json_object(baseline_bytes, "BASELINE_JSON_INVALID")
    _validate_requalification_document(
        evidence,
        dataset=dataset,
        dataset_byte_length=len(dataset_bytes),
        custody=custody,
        custody_byte_length=len(custody_bytes),
    )
    _validate_baseline_document(baseline)
    return dataset, custody, evidence, baseline


def _write_once(path: Path, body: bytes) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except FileExistsError:
        raise Arch148ChurnResearchError("OUTPUT_ARTIFACT_COLLISION") from None
    except OSError:
        raise Arch148ChurnResearchError("OUTPUT_ARTIFACT_CREATE_FAILED") from None
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            if stream.write(body) != len(body):
                raise Arch148ChurnResearchError("OUTPUT_ARTIFACT_WRITE_FAILED")
            stream.flush()
            os.fsync(stream.fileno())
    except Arch148ChurnResearchError:
        raise
    except OSError:
        raise Arch148ChurnResearchError("OUTPUT_ARTIFACT_WRITE_FAILED") from None


def _fresh_output_directory() -> Path:
    try:
        root_resolved = OUTPUT_ROOT.resolve(strict=True)
        if root_resolved != OUTPUT_ROOT or not OUTPUT_ROOT.is_dir():
            raise Arch148ChurnResearchError("OUTPUT_ROOT_INVALID")
        output = OUTPUT_ROOT / f"arch148-churn-research-{uuid4()}"
        output.mkdir()
        if _is_reparse_point(output) or output.resolve(strict=True) != output:
            raise Arch148ChurnResearchError("OUTPUT_PATH_ALIAS")
        return output
    except Arch148ChurnResearchError:
        raise
    except FileExistsError:
        raise Arch148ChurnResearchError("OUTPUT_ALREADY_EXISTS") from None
    except OSError:
        raise Arch148ChurnResearchError("OUTPUT_CREATE_FAILED") from None


def run_accepted_open_churn_research() -> ChurnResearchOutput:
    """Run the guarded one-shot comparison on fixed accepted OPEN evidence.

    This function reads only the fixed local OPEN requalification and baseline
    artifacts, performs pure deterministic replays, and writes one fresh
    create-once report under ``F:\\AI\\temp``. It has no provider or broker
    dependency and rejects any candidate source or input drift before output.
    """

    try:
        return _execute_accepted_open_churn_research()
    except Arch148ChurnResearchError:
        raise
    except Exception:
        raise Arch148ChurnResearchError("RESEARCH_RUN_FAILED") from None


def _execute_accepted_open_churn_research() -> ChurnResearchOutput:

    source_head, source_tree = _candidate_source_identity()
    dataset, custody, requalification, baseline = _load_accepted_inputs()
    policies, _ = _fixed_variant_material()
    captures: list[tuple[ChurnPolicy, BacktestCostModel, _RunCapture]] = []
    control_policy = policies[0]
    control_runs = {
        model.name: _run_sparse_capture(dataset, model, control_policy)
        for model in (ZERO_COST, CONSERVATIVE_COSTS)
    }
    captures.extend(
        (control_policy, model, control_runs[model.name])
        for model in (ZERO_COST, CONSERVATIVE_COSTS)
    )
    _assert_control_reproduces_baseline(
        control_runs[ZERO_COST.name], control_runs[CONSERVATIVE_COSTS.name]
    )
    _validate_baseline_control_runs(baseline, control_runs)
    for policy in policies[1:]:
        for model in (ZERO_COST, CONSERVATIVE_COSTS):
            captures.append(
                (policy, model, _run_sparse_capture(dataset, model, policy))
            )
    report = _build_report(
        dataset,
        source_head=source_head,
        source_tree=source_tree,
        dataset_sha256=ACCEPTED_DATASET_SHA256,
        custody=custody,
        custody_sha256=ACCEPTED_CUSTODY_SHA256,
        requalification_sha256=ACCEPTED_REQUALIFICATION_SHA256,
        baseline_document=baseline,
        captures=tuple(captures),
    )
    body = report.to_json().encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    output = _fresh_output_directory()
    _write_once(output / "research.json", body)
    _write_once(output / "research.sha256", (digest + "\n").encode("ascii"))
    try:
        persisted = (output / "research.json").read_bytes()
    except OSError:
        raise Arch148ChurnResearchError("OUTPUT_READBACK_FAILED") from None
    if persisted != body:
        raise Arch148ChurnResearchError("OUTPUT_READBACK_MISMATCH")
    return ChurnResearchOutput(
        RESEARCH_READY,
        output,
        digest,
        len(body),
        dataset.identity,
        tuple(
            (item.symbol, item.observed_regular_session_count)
            for item in dataset.sparse_evidence
        ),
    )


def _validate_baseline_control_runs(
    baseline: dict[str, object], captures: dict[str, _RunCapture]
) -> None:
    runs = baseline["runs"]
    for name, key in (
        (ZERO_COST.name, "zero_cost"),
        (CONSERVATIVE_COSTS.name, "conservative_10_bps"),
    ):
        expected = runs[key]
        actual = captures[name].result
        fields = (
            "gross_strategy_return",
            "cost_adjusted_strategy_return",
            "qqq_buy_and_hold_return",
            "cash_control_return",
            "maximum_drawdown",
            "trade_count",
            "stop_hit_count",
            "forced_flat_count",
            "reversal_exits",
            "turnover",
            "win_rate",
            "average_win",
            "average_loss",
        )
        for field in fields:
            expected_value = expected[field]
            actual_value = getattr(actual, field)
            if type(actual_value) is Decimal:
                matches = (
                    type(expected_value) is str
                    and Decimal(expected_value) == actual_value
                )
            elif type(actual_value) is int:
                matches = type(expected_value) is int and expected_value == actual_value
            else:
                matches = expected_value == actual_value
            if not matches:
                raise Arch148ChurnResearchError("CONTROL_BASELINE_REPORT_MISMATCH")
        if (
            type(expected["average_holding_duration_us"]) is not int
            or _timedelta_microseconds(actual.average_holding_duration)
            != expected["average_holding_duration_us"]
            or type(expected["equity_curve_points"]) is not int
            or len(actual.equity_curve) != expected["equity_curve_points"]
        ):
            raise Arch148ChurnResearchError("CONTROL_BASELINE_REPORT_MISMATCH")
        expected_reasons = expected["exit_reason_counts"]
        if type(expected_reasons) is not dict or any(
            reason not in {"STOP", "FORCED_FLAT", "REGIME_EXIT", "SAFETY"}
            or type(count) is not int
            or count < 0
            for reason, count in expected_reasons.items()
        ):
            raise Arch148ChurnResearchError("CONTROL_BASELINE_REPORT_MISMATCH")
        actual_reasons = Counter(
            item.trade.exit_reason for item in captures[name].trades
        )
        if any(
            expected_reasons.get(reason, 0) != actual_reasons.get(reason, 0)
            for reason in {"STOP", "FORCED_FLAT", "REGIME_EXIT", "SAFETY"}
        ):
            raise Arch148ChurnResearchError("CONTROL_BASELINE_REPORT_MISMATCH")


def main(argv: list[str] | None = None) -> int:
    """Execute the guarded operator path and print only safe result metadata."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-accepted-open",
        action="store_true",
        help="run the fixed, guarded OPEN-only comparison once",
    )
    arguments = parser.parse_args(argv)
    if not arguments.run_accepted_open:
        parser.print_help()
        return 0
    try:
        output = run_accepted_open_churn_research()
    except Arch148ChurnResearchError as error:
        print(error.code, file=sys.stderr)
        return 1
    print(output.classification)
    print(output.output_directory)
    print(output.report_sha256)
    print(output.report_byte_length)
    print(output.dataset_identity)
    for symbol, count in output.sparse_counts:
        print(f"{symbol} observed={count}")
    return 0


_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)

__all__ = [
    "Arch148ChurnResearchError",
    "ChurnResearchOutput",
    "ChurnResearchReport",
    "RESEARCH_READY",
    "RESEARCH_SCHEMA",
    "run_accepted_open_churn_research",
]


if __name__ == "__main__":
    raise SystemExit(main())
