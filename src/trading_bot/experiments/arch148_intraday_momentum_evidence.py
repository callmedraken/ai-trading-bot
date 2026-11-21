"""Pure, deterministic OPEN evidence for the frozen Arch148 candidate.

This module consumes the accepted sparse input in memory. It has no artifact,
filesystem, provider, credential, broker, production-state, or holdout reader.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from typing import Final
from uuid import UUID, uuid5

from trading_bot.domain import Bar
from trading_bot.experiments.arch148_intraday import (
    ARCH148_INTRADAY_SCHEDULE_DIGEST,
    ARCH148_INTRADAY_SCHEDULE_IDENTITY,
    CONSERVATIVE_COSTS,
    EARLY_CLOSE_DATES,
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
    session_slots,
    verify_sparse_intraday_custody_evidence,
)
from trading_bot.experiments.arch148_intraday_momentum_research import (
    OPENING_DRIVE_POLICY_ID,
    OPENING_DRIVE_REPLAY_SCHEMA,
    OPENING_DRIVE_SIMULATOR_VERSION,
    OpeningDriveEquityMark,
    OpeningDriveReplayCapture,
    OpeningDriveSessionCapture,
    run_opening_drive_replay,
)
from trading_bot.experiments.arch148_sparse_backtest import (
    sparse_backtest_decimal_context,
)
from trading_bot.experiments.historical_research_custody import (
    HistoricalSessionAuthority,
    canonical_json_bytes,
)
from trading_bot.experiments.historical_research_sessions import (
    AUTHORITY_DIGEST,
    AUTHORITY_IDENTITY,
    SOURCE_BUNDLE_SHA256,
)
from trading_bot.live_runtime.models import MarketQuality

RESEARCH_SCHEMA: Final = "arch148-intraday-momentum-evidence/v1"
RESEARCH_IDENTITY_VERSION: Final = "arch148-intraday-momentum-evidence-identity/v1"
RESEARCH_NAMESPACE: Final = UUID("7d7dfb14-9bc8-59d4-a3f4-0c6dab8d28b4")
_INITIAL_CAPITAL: Final = Decimal("10000")
_REPORTING_YEARS: Final = tuple(range(2016, 2024))
PARTITION_METHOD: Final = (
    "ONE_CHRONOLOGICAL_REPLAY_WITH_PRIOR_YEAR_SETTLED_EQUITY_DENOMINATOR"
)
_ACCEPTED_DATASET_IDENTITY: Final = "0308b694-c718-5b1a-a51c-9fcc4516bb81"
_ACCEPTED_DATASET_SHA256: Final = (
    "0ba8b2437ef27a98fc48855aa8bb8d27ca3cdc0f2888e214305dde760686dbe0"
)
_ACCEPTED_DATASET_BYTE_LENGTH: Final = 65_183_146
_ACCEPTED_CUSTODY_IDENTITY: Final = "dbcced6a-b4cc-5d36-a33b-5e6df3d82baa"
_ACCEPTED_CUSTODY_SHA256: Final = (
    "93db9a9163cf445fdfd61abe68559196d240b09c1c9b70cdc0f7f452e3e8708b"
)
_ACCEPTED_CUSTODY_BYTE_LENGTH: Final = 33_447
_ACCEPTED_REQUALIFICATION_SHA256: Final = (
    "bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d"
)
_ACCEPTED_BASELINE_SHA256: Final = (
    "38cbba9beae664c675670af1ad96e86a56df2a9060c6cb924c1ad51ea4f9b85f"
)
_ACCEPTED_CHURN_SHA256: Final = (
    "5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8"
)
_OPEN_START: Final = OPEN_START
_OPEN_END_EXCLUSIVE: Final = OPEN_END_EXCLUSIVE
_NO_TRADE_REASONS: Final = (
    "MISSING_PREVIOUS_QQQ_CLOSE",
    "INCOMPLETE_FIRST_HALF_HOUR_QQQ",
    "ZERO_OPENING_DRIVE",
    "MISSING_SCHEDULED_ENTRY_BAR",
    "QQQ_DATA_SAFETY_AT_ENTRY",
)
_POLICY_NO_TRADE_REASONS: Final = _NO_TRADE_REASONS[:4]
_EXIT_REASONS: Final = ("FORCED_FLAT", "SAFETY", "STOP")
_ZERO_EFFECT_COUNTERS: Final = (
    "credential_reads",
    "network_calls",
    "provider_calls",
    "robinhood_calls",
    "broker_calls",
    "order_mutations",
    "production_state_mutations",
    "final_holdout_accesses",
    "baseline_backtests",
)
_GIT_ID = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
_BAR_WIDTH = timedelta(minutes=5)


class Arch148IntradayMomentumEvidenceError(RuntimeError):
    """Sanitized fail-closed report error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OpeningDriveResearchReport:
    """Immutable canonical report bytes with deterministic identity and hash."""

    report_json: str
    identity: str = field(init=False)
    classification: str = field(init=False)

    def __post_init__(self) -> None:
        document = _parse_report_json(self.report_json)
        if canonical_json_bytes(document) != self.report_json.encode("utf-8"):
            raise Arch148IntradayMomentumEvidenceError("REPORT_JSON_NOT_CANONICAL")
        _validate_report_document(document)
        object.__setattr__(self, "identity", document["identity"])
        object.__setattr__(self, "classification", document["classification"])

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.report_json.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        return self.report_json

    def to_dict(self) -> dict[str, object]:
        return json.loads(self.report_json)

    @classmethod
    def from_json(cls, value: str | bytes) -> OpeningDriveResearchReport:
        if type(value) is str:
            body = value.encode("utf-8")
        elif type(value) is bytes:
            body = value
        else:
            raise Arch148IntradayMomentumEvidenceError("REPORT_JSON_INVALID")
        try:
            document = _parse_report_json(body)
            if canonical_json_bytes(document) != body:
                raise Arch148IntradayMomentumEvidenceError("REPORT_JSON_NOT_CANONICAL")
            return cls(body.decode("utf-8"))
        except Arch148IntradayMomentumEvidenceError:
            raise
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise Arch148IntradayMomentumEvidenceError("REPORT_JSON_INVALID") from None


def evaluate_opening_drive_research(
    dataset: SparseIntradayDataset,
    custody: SparseIntradayCustodyEvidence,
    *,
    authority: HistoricalIntradaySessionAuthority,
    source_head: str,
    source_tree: str,
) -> OpeningDriveResearchReport:
    """Replay the two frozen cost cases and return an in-memory OPEN report."""

    input_bindings = _validate_accepted_input(dataset, custody)
    _validate_authority(authority)
    _validate_source_identity(source_head, source_tree)
    try:
        captures = tuple(
            run_opening_drive_replay(dataset, authority=authority, cost_model=model)
            for model in (ZERO_COST, CONSERVATIVE_COSTS)
        )
    except Arch148IntradayError:
        raise Arch148IntradayMomentumEvidenceError("SPARSE_REPLAY_REJECTED") from None
    except (ArithmeticError, TypeError, ValueError):
        raise Arch148IntradayMomentumEvidenceError("SPARSE_REPLAY_REJECTED") from None

    if captures[0].session_captures != captures[1].session_captures:
        raise Arch148IntradayMomentumEvidenceError("COST_CASE_SESSION_MISMATCH")
    session_dates = _dataset_session_dates(dataset, authority)
    expected_partitions = _partition_plan()
    runs = tuple(
        _build_cost_run(dataset, capture, model, session_dates, authority)
        for model, capture in zip(
            (ZERO_COST, CONSERVATIVE_COSTS), captures, strict=True
        )
    )
    classification = _classify_result(runs[1]["partitions"])
    payload: dict[str, object] = {
        "schema": RESEARCH_SCHEMA,
        "strategy": {
            "id": OPENING_DRIVE_POLICY_ID,
            "replay_schema": OPENING_DRIVE_REPLAY_SCHEMA,
            "simulator_version": OPENING_DRIVE_SIMULATOR_VERSION,
            "partition_method": PARTITION_METHOD,
        },
        "source": {"head": source_head, "tree": source_tree},
        "inputs": input_bindings,
        "cost_models": [
            _cost_model_record(model) for model in (ZERO_COST, CONSERVATIVE_COSTS)
        ],
        "partitions": [_partition_record(item) for item in expected_partitions],
        "runs": list(runs),
        "classification": classification,
        "final_holdout_sealed": True,
        "effects": {name: 0 for name in _ZERO_EFFECT_COUNTERS},
    }
    return _report_from_payload(payload)


def _validate_accepted_input(
    dataset: SparseIntradayDataset,
    custody: SparseIntradayCustodyEvidence,
) -> dict[str, object]:
    if (
        type(dataset) is not SparseIntradayDataset
        or type(custody) is not SparseIntradayCustodyEvidence
        or dataset.start != _OPEN_START
        or dataset.end_exclusive != _OPEN_END_EXCLUSIVE
        or dataset.identity != _ACCEPTED_DATASET_IDENTITY
        or custody.dataset_identity != _ACCEPTED_DATASET_IDENTITY
        or custody.evidence_id != _ACCEPTED_CUSTODY_IDENTITY
        or dataset.schedule_identity != ARCH148_INTRADAY_SCHEDULE_IDENTITY
        or dataset.schedule_digest != ARCH148_INTRADAY_SCHEDULE_DIGEST
    ):
        raise Arch148IntradayMomentumEvidenceError("ACCEPTED_INPUT_BINDING_MISMATCH")
    try:
        verify_sparse_intraday_custody_evidence(dataset, custody)
        dataset_bytes = dataset.to_json().encode("utf-8")
        custody_bytes = custody.to_json().encode("utf-8")
    except Arch148IntradayError:
        raise Arch148IntradayMomentumEvidenceError("CUSTODY_BINDING_INVALID") from None
    dataset_digest = hashlib.sha256(dataset_bytes).hexdigest()
    custody_digest = hashlib.sha256(custody_bytes).hexdigest()
    if (
        dataset_digest != _ACCEPTED_DATASET_SHA256
        or len(dataset_bytes) != _ACCEPTED_DATASET_BYTE_LENGTH
        or custody_digest != _ACCEPTED_CUSTODY_SHA256
        or len(custody_bytes) != _ACCEPTED_CUSTODY_BYTE_LENGTH
    ):
        raise Arch148IntradayMomentumEvidenceError("ACCEPTED_INPUT_DIGEST_MISMATCH")
    return {
        "open_start": _timestamp_text(_OPEN_START),
        "open_end_exclusive": _timestamp_text(_OPEN_END_EXCLUSIVE),
        "dataset": {
            "schema": "arch148-intraday-dataset/v3",
            "identity": dataset.identity,
            "sha256": dataset_digest,
            "byte_length": len(dataset_bytes),
        },
        "custody": {
            "schema": "arch148-intraday-custody-evidence/v3",
            "evidence_id": custody.evidence_id,
            "sha256": custody_digest,
            "byte_length": len(custody_bytes),
        },
        "requalification_sha256": _ACCEPTED_REQUALIFICATION_SHA256,
        "baseline_sha256": _ACCEPTED_BASELINE_SHA256,
        "churn_sha256": _ACCEPTED_CHURN_SHA256,
        "schedule": {
            "identity": ARCH148_INTRADAY_SCHEDULE_IDENTITY,
            "sha256": ARCH148_INTRADAY_SCHEDULE_DIGEST,
        },
    }


def _validate_source_identity(source_head: str, source_tree: str) -> None:
    if (
        type(source_head) is not str
        or _GIT_ID.fullmatch(source_head) is None
        or type(source_tree) is not str
        or _GIT_ID.fullmatch(source_tree) is None
    ):
        raise Arch148IntradayMomentumEvidenceError("SOURCE_IDENTITY_INVALID")


def _validate_authority(authority: HistoricalIntradaySessionAuthority) -> None:
    if (
        type(authority) is not HistoricalIntradaySessionAuthority
        or type(authority.published) is not HistoricalSessionAuthority
        or authority.published.identity != AUTHORITY_IDENTITY
        or authority.published.digest != AUTHORITY_DIGEST
        or authority.published.source_sha256 != SOURCE_BUNDLE_SHA256
        or len(authority.published.sessions) != 2718
    ):
        raise Arch148IntradayMomentumEvidenceError(
            "ACCEPTED_SCHEDULE_AUTHORITY_INVALID"
        )


def _dataset_session_dates(
    dataset: SparseIntradayDataset,
    authority: HistoricalIntradaySessionAuthority,
) -> tuple[date, ...]:
    slots = expected_open_slots(dataset.start, dataset.end_exclusive, authority)
    sessions = tuple(dict.fromkeys(slot.astimezone(UTC).date() for slot in slots))
    if not sessions or tuple(sorted(set(sessions))) != sessions:
        raise Arch148IntradayMomentumEvidenceError("SESSION_SCHEDULE_INVALID")
    return sessions


def _partition_plan() -> tuple[dict[str, object], ...]:
    partitions: list[dict[str, object]] = [
        {
            "name": "OPEN_FULL",
            "start": _OPEN_START,
            "end_exclusive": _OPEN_END_EXCLUSIVE,
        }
    ]
    for year in _REPORTING_YEARS:
        start = max(_OPEN_START, datetime(year, 1, 1, tzinfo=UTC))
        end = min(_OPEN_END_EXCLUSIVE, datetime(year + 1, 1, 1, tzinfo=UTC))
        if start < end:
            partitions.append(
                {"name": f"OPEN_{year}", "start": start, "end_exclusive": end}
            )
    if len(partitions) != len(_REPORTING_YEARS) + 1:
        raise Arch148IntradayMomentumEvidenceError("PARTITION_PLAN_INCOMPLETE")
    yearly = partitions[1:]
    if not yearly or yearly[0]["start"] != _OPEN_START:
        raise Arch148IntradayMomentumEvidenceError("PARTITION_PLAN_NOT_CONTIGUOUS")
    for previous, following in zip(yearly, yearly[1:], strict=False):
        if previous["end_exclusive"] != following["start"]:
            raise Arch148IntradayMomentumEvidenceError("PARTITION_PLAN_NOT_CONTIGUOUS")
    if yearly[-1]["end_exclusive"] != _OPEN_END_EXCLUSIVE:
        raise Arch148IntradayMomentumEvidenceError("PARTITION_PLAN_NOT_CONTIGUOUS")
    return tuple(partitions)


def _build_cost_run(
    dataset: SparseIntradayDataset,
    capture: OpeningDriveReplayCapture,
    cost_model: BacktestCostModel,
    session_dates: tuple[date, ...],
    authority: HistoricalIntradaySessionAuthority,
) -> dict[str, object]:
    trade_turnovers = _validate_capture(
        dataset, capture, cost_model, session_dates, authority
    )
    partitions = _partition_plan()
    qqq_bars = dataset.bars_by_symbol["QQQ"]
    opening_equity = _INITIAL_CAPITAL
    result: list[dict[str, object]] = []
    for partition in partitions:
        metrics = _partition_metrics(
            partition,
            opening_equity=opening_equity,
            session_captures=capture.session_captures,
            trades=capture.backtest_result.trades,
            trade_turnovers=trade_turnovers,
            equity_marks=capture.equity_marks,
            qqq_bars=qqq_bars,
            missing_held_session_dates=capture.missing_held_session_dates,
        )
        result.append(metrics)
        if partition["name"] != "OPEN_FULL":
            opening_equity = _parse_decimal(metrics["ending_equity"])
    return {
        "cost_model": _cost_model_record(cost_model),
        "partitions": result,
    }


def _validate_capture(
    dataset: SparseIntradayDataset,
    capture: OpeningDriveReplayCapture,
    cost_model: BacktestCostModel,
    session_dates: tuple[date, ...],
    authority: HistoricalIntradaySessionAuthority,
) -> tuple[Decimal, ...]:
    if (
        type(capture) is not OpeningDriveReplayCapture
        or type(capture.backtest_result) is not BacktestResult
        or capture.backtest_result.dataset_identity != dataset.identity
        or capture.backtest_result.cost_model != cost_model.name
        or type(capture.session_captures) is not tuple
        or len(capture.session_captures) != len(session_dates)
        or tuple(item.session_date for item in capture.session_captures)
        != session_dates
        or any(
            type(item) is not OpeningDriveSessionCapture
            for item in capture.session_captures
        )
        or type(capture.equity_marks) is not tuple
        or type(capture.missing_held_session_dates) is not tuple
    ):
        raise Arch148IntradayMomentumEvidenceError("REPLAY_CAPTURE_BINDING_INVALID")
    result = capture.backtest_result
    trades = result.trades
    turnovers = capture.trade_turnovers
    if (
        type(trades) is not tuple
        or type(turnovers) is not tuple
        or len(turnovers) != len(trades)
        or type(result.trade_count) is not int
        or result.trade_count != len(trades)
        or type(result.equity_curve) is not tuple
        or len(result.equity_curve) != len(capture.equity_marks)
        or any(
            type(turnover) is not Decimal or not turnover.is_finite() or turnover < 0
            for turnover in turnovers
        )
        or any(
            type(mark) is not OpeningDriveEquityMark for mark in capture.equity_marks
        )
        or tuple(mark.equity for mark in capture.equity_marks) != result.equity_curve
        or any(
            left.at >= right.at
            for left, right in zip(
                capture.equity_marks, capture.equity_marks[1:], strict=False
            )
        )
    ):
        raise Arch148IntradayMomentumEvidenceError("REPLAY_CAPTURE_SHAPE_INVALID")
    with localcontext(sparse_backtest_decimal_context()):
        if sum(turnovers, Decimal("0")) != result.turnover:
            raise Arch148IntradayMomentumEvidenceError("TURNOVER_CAPTURE_MISMATCH")
    qqq_by_timestamp: dict[datetime, Bar] = {
        bar.timestamp: bar for bar in dataset.bars_by_symbol["QQQ"]
    }
    bars_by_symbol = dataset.bars_by_symbol
    target_timestamps = {
        "TQQQ": {bar.timestamp for bar in bars_by_symbol["TQQQ"]},
        "SQQQ": {bar.timestamp for bar in bars_by_symbol["SQQQ"]},
    }
    calendar_dates = tuple(sorted(authority.published.sessions))
    calendar_indexes = {day: index for index, day in enumerate(calendar_dates)}
    trades_by_date: dict[date, list[BacktestTrade]] = {day: [] for day in session_dates}
    for trade in trades:
        if (
            type(trade) is not BacktestTrade
            or trade.symbol not in {"TQQQ", "SQQQ"}
            or trade.exit_reason not in _EXIT_REASONS
            or trade.exit_at < trade.entry_at
            or trade.holding_duration != trade.exit_at - trade.entry_at
            or trade.exit_at.tzinfo is None
            or trade.entry_at.tzinfo is None
        ):
            raise Arch148IntradayMomentumEvidenceError("TRADE_AUDIT_INVALID")
        trade_day = trade.entry_at.astimezone(UTC).date()
        if trade_day not in trades_by_date:
            raise Arch148IntradayMomentumEvidenceError("TRADE_SESSION_OUTSIDE_DATASET")
        trades_by_date[trade_day].append(trade)
    if any(len(day_trades) > 1 for day_trades in trades_by_date.values()):
        raise Arch148IntradayMomentumEvidenceError("MULTIPLE_ENTRIES_PER_SESSION")
    if result.reversal_exits != 0:
        raise Arch148IntradayMomentumEvidenceError("REGIME_EXIT_NOT_ALLOWED")
    if result.stop_hit_count != sum(trade.exit_reason == "STOP" for trade in trades):
        raise Arch148IntradayMomentumEvidenceError("STOP_COUNT_MISMATCH")
    if result.forced_flat_count != sum(
        trade.exit_reason == "FORCED_FLAT" for trade in trades
    ):
        raise Arch148IntradayMomentumEvidenceError("FORCED_FLAT_COUNT_MISMATCH")
    qqq_bars = dataset.bars_by_symbol["QQQ"]
    if not qqq_bars:
        raise Arch148IntradayMomentumEvidenceError("QQQ_OBSERVATIONS_REQUIRED")
    with localcontext(sparse_backtest_decimal_context()):
        gross_return = (
            sum((trade.gross_pnl for trade in trades), Decimal("0")) / _INITIAL_CAPITAL
        )
        net_return = (
            sum((trade.cost_adjusted_pnl for trade in trades), Decimal("0"))
            / _INITIAL_CAPITAL
        )
        qqq_return = (qqq_bars[-1].close - qqq_bars[0].open) / qqq_bars[0].open
        peak = _INITIAL_CAPITAL
        full_drawdown = Decimal("0")
        for mark in capture.equity_marks:
            peak = max(peak, mark.equity)
            full_drawdown = max(full_drawdown, (peak - mark.equity) / peak)
    if (
        result.gross_strategy_return != gross_return
        or result.cost_adjusted_strategy_return != net_return
        or result.qqq_buy_and_hold_return != qqq_return
        or result.maximum_drawdown != full_drawdown
    ):
        raise Arch148IntradayMomentumEvidenceError("BACKTEST_AGGREGATE_MISMATCH")
    if not _ordered_unique_dates(capture.missing_held_session_dates):
        raise Arch148IntradayMomentumEvidenceError("MISSING_HELD_DATES_INVALID")
    traded_dates = {day for day, day_trades in trades_by_date.items() if day_trades}
    if not set(capture.missing_held_session_dates).issubset(traded_dates):
        raise Arch148IntradayMomentumEvidenceError("MISSING_HELD_DATE_NOT_TRADED")

    for item in capture.session_captures:
        session = authority.schedule_for(item.session_date)
        if session is None:
            raise Arch148IntradayMomentumEvidenceError("SESSION_SCHEDULE_INVALID")
        entry_at = session.closes_at - timedelta(minutes=35)
        force_flat_at = session.closes_at - timedelta(minutes=5)
        expected_early_close = item.session_date in EARLY_CLOSE_DATES
        if (
            item.entry_at != entry_at
            or item.force_flat_at != force_flat_at
            or item.early_close is not expected_early_close
        ):
            raise Arch148IntradayMomentumEvidenceError("SESSION_BOUNDARY_MISMATCH")
        position = calendar_indexes.get(item.session_date)
        if position is None:
            raise Arch148IntradayMomentumEvidenceError(
                "SESSION_SCHEDULE_INVALID"
            ) from None
        expected_previous = calendar_dates[position - 1] if position else None
        if item.previous_session_date != expected_previous:
            raise Arch148IntradayMomentumEvidenceError("PREVIOUS_SESSION_MISMATCH")
        previous_close_at = None
        if expected_previous is not None:
            previous_schedule = authority.schedule_for(expected_previous)
            if previous_schedule is None:
                raise Arch148IntradayMomentumEvidenceError("PREVIOUS_SESSION_INVALID")
            previous_close_at = previous_schedule.closes_at - _BAR_WIDTH
        previous_bar = qqq_by_timestamp.get(previous_close_at)
        if previous_bar is None:
            expected_drive = None
            expected_target = None
            expected_reason = "MISSING_PREVIOUS_QQQ_CLOSE"
        else:
            first_half_slots = session_slots(item.session_date, authority)[:6]
            first_half_bars = tuple(
                qqq_by_timestamp.get(slot) for slot in first_half_slots
            )
            if len(first_half_slots) != 6 or any(
                bar is None for bar in first_half_bars
            ):
                expected_drive = None
                expected_target = None
                expected_reason = "INCOMPLETE_FIRST_HALF_HOUR_QQQ"
            else:
                sixth_bar = first_half_bars[-1]
                with localcontext(sparse_backtest_decimal_context()):
                    expected_drive = sixth_bar.close / previous_bar.close - Decimal("1")
                if expected_drive == 0:
                    expected_target = None
                    expected_reason = "ZERO_OPENING_DRIVE"
                else:
                    expected_target = "TQQQ" if expected_drive > 0 else "SQQQ"
                    if entry_at not in target_timestamps[expected_target]:
                        expected_reason = "MISSING_SCHEDULED_ENTRY_BAR"
                    else:
                        expected_reason = None
        actual_drive = item.opening_drive_return
        if actual_drive is not None and (
            type(actual_drive) is not Decimal or not actual_drive.is_finite()
        ):
            raise Arch148IntradayMomentumEvidenceError("OPENING_DRIVE_INVALID")
        if actual_drive != expected_drive or item.target_symbol != expected_target:
            raise Arch148IntradayMomentumEvidenceError("OPENING_DRIVE_FACT_MISMATCH")
        reason = _reason_text(item.no_trade_reason)
        eligible = expected_reason is None
        if item.policy_entry_eligible is not eligible:
            raise Arch148IntradayMomentumEvidenceError("ELIGIBILITY_FACT_MISMATCH")
        if reason == "QQQ_DATA_SAFETY_AT_ENTRY":
            if (
                not eligible
                or item.entry_data_quality is None
                or item.entry_data_quality is MarketQuality.READY
            ):
                raise Arch148IntradayMomentumEvidenceError(
                    "SAFETY_REASON_PRECEDENCE_INVALID"
                )
        elif reason != expected_reason:
            raise Arch148IntradayMomentumEvidenceError("NO_TRADE_REASON_MISMATCH")
        elif eligible and item.entry_data_quality is not MarketQuality.READY:
            raise Arch148IntradayMomentumEvidenceError("ENTRY_QUALITY_FACT_MISMATCH")
        elif not eligible and item.entry_data_quality is not None:
            raise Arch148IntradayMomentumEvidenceError("ENTRY_QUALITY_FACT_MISMATCH")
        if reason is not None and reason not in _NO_TRADE_REASONS:
            raise Arch148IntradayMomentumEvidenceError("UNKNOWN_NO_TRADE_REASON")
        if reason is None and not eligible:
            raise Arch148IntradayMomentumEvidenceError("TRADE_WITHOUT_ELIGIBILITY")
        day_trades = trades_by_date[item.session_date]
        if reason is None:
            if (
                len(day_trades) != 1
                or day_trades[0].entry_at != entry_at
                or day_trades[0].symbol != expected_target
                or day_trades[0].exit_at > force_flat_at
            ):
                raise Arch148IntradayMomentumEvidenceError("TRADE_SESSION_MISMATCH")
        elif day_trades:
            raise Arch148IntradayMomentumEvidenceError("TRADE_FOR_SKIPPED_SESSION")
        expected_late_return = _late_window_return(
            qqq_by_timestamp, entry_at, force_flat_at
        )
        if item.qqq_late_window_return != expected_late_return:
            raise Arch148IntradayMomentumEvidenceError("LATE_WINDOW_FACT_MISMATCH")

    return turnovers


def _late_window_return(
    qqq_by_timestamp: dict[datetime, Bar], entry_at: datetime, late_at: datetime
) -> Decimal | None:
    start_bar = qqq_by_timestamp.get(entry_at)
    end_bar = qqq_by_timestamp.get(late_at)
    if start_bar is None or end_bar is None:
        return None
    with localcontext(sparse_backtest_decimal_context()):
        return end_bar.open / start_bar.open - Decimal("1")


def _partition_metrics(
    partition: dict[str, object],
    *,
    opening_equity: Decimal,
    session_captures: tuple[OpeningDriveSessionCapture, ...],
    trades: tuple[BacktestTrade, ...],
    trade_turnovers: tuple[Decimal, ...],
    equity_marks: tuple[OpeningDriveEquityMark, ...],
    qqq_bars: tuple[Bar, ...],
    missing_held_session_dates: tuple[date, ...],
) -> dict[str, object]:
    start = partition["start"]
    end = partition["end_exclusive"]
    if type(start) is not datetime or type(end) is not datetime:
        raise Arch148IntradayMomentumEvidenceError("PARTITION_BOUNDARY_INVALID")
    period_sessions = tuple(
        item
        for item in session_captures
        if start.date() <= item.session_date < end.date()
    )
    period_trades = tuple(
        (trade, turnover)
        for trade, turnover in zip(trades, trade_turnovers, strict=True)
        if start <= trade.entry_at < end
    )
    period_marks = tuple(mark for mark in equity_marks if start <= mark.at < end)
    period_qqq = tuple(bar for bar in qqq_bars if start <= bar.timestamp < end)
    period_missing_dates = tuple(
        day for day in missing_held_session_dates if start.date() <= day < end.date()
    )
    if opening_equity <= 0 or not opening_equity.is_finite():
        raise Arch148IntradayMomentumEvidenceError("PARTITION_OPENING_EQUITY_INVALID")
    ending_equity = period_marks[-1].equity if period_marks else opening_equity
    if ending_equity <= 0 or not ending_equity.is_finite():
        raise Arch148IntradayMomentumEvidenceError("PARTITION_ENDING_EQUITY_INVALID")
    period_trade_facts = tuple(trade for trade, _ in period_trades)
    with localcontext(sparse_backtest_decimal_context()):
        gross_pnl = sum((trade.gross_pnl for trade in period_trade_facts), Decimal("0"))
        net_pnl = sum(
            (trade.cost_adjusted_pnl for trade in period_trade_facts), Decimal("0")
        )
        gross_return = gross_pnl / opening_equity
        net_return = net_pnl / opening_equity
        equity_return = ending_equity / opening_equity - Decimal("1")
        qqq_return = (
            (period_qqq[-1].close - period_qqq[0].open) / period_qqq[0].open
            if period_qqq
            else None
        )
        turnover = sum((value for _, value in period_trades), Decimal("0"))
    peak = opening_equity
    maximum_drawdown = Decimal("0")
    with localcontext(sparse_backtest_decimal_context()):
        for mark in period_marks:
            peak = max(peak, mark.equity)
            if peak > 0:
                maximum_drawdown = max(maximum_drawdown, (peak - mark.equity) / peak)

    traded_dates = {
        trade.entry_at.astimezone(UTC).date() for trade in period_trade_facts
    }
    no_trade_counts = Counter(
        reason
        for item in period_sessions
        if (reason := _reason_text(item.no_trade_reason)) is not None
    )
    no_trade_distribution = {
        reason: no_trade_counts[reason] for reason in _NO_TRADE_REASONS
    }
    exit_counts = Counter(trade.exit_reason for trade in period_trade_facts)
    if set(exit_counts).difference(_EXIT_REASONS):
        raise Arch148IntradayMomentumEvidenceError("UNKNOWN_EXIT_REASON")
    exit_distribution = {reason: exit_counts[reason] for reason in _EXIT_REASONS}
    wins = tuple(
        trade.return_pct for trade in period_trade_facts if trade.cost_adjusted_pnl > 0
    )
    losses = tuple(
        trade.return_pct for trade in period_trade_facts if trade.cost_adjusted_pnl < 0
    )
    with localcontext(sparse_backtest_decimal_context()):
        win_rate = (
            Decimal(len(wins)) / Decimal(len(period_trade_facts))
            if period_trade_facts
            else Decimal("0")
        )
        average_win = (
            sum(wins, Decimal("0")) / Decimal(len(wins)) if wins else Decimal("0")
        )
        average_loss = (
            sum(losses, Decimal("0")) / Decimal(len(losses)) if losses else Decimal("0")
        )
    durations = tuple(
        _duration_microseconds(trade.holding_duration) for trade in period_trade_facts
    )
    with localcontext(sparse_backtest_decimal_context()):
        average_duration = (
            Decimal(sum(durations)) / Decimal(len(durations))
            if durations
            else Decimal("0")
        )
        median_duration = (
            _median(tuple(Decimal(value) for value in durations))
            if durations
            else Decimal("0")
        )
    eligible_count = sum(item.policy_entry_eligible for item in period_sessions)
    traded_count = len(period_trade_facts)
    no_trade_count = len(period_sessions) - traded_count
    if (
        sum(no_trade_distribution.values()) != no_trade_count
        or traded_count > eligible_count
        or eligible_count > len(period_sessions)
        or eligible_count - traded_count
        != no_trade_distribution["QQQ_DATA_SAFETY_AT_ENTRY"]
    ):
        raise Arch148IntradayMomentumEvidenceError("SESSION_COUNT_MISMATCH")

    drive_and_late = tuple(
        (item.opening_drive_return, item.qqq_late_window_return)
        for item in period_sessions
        if item.opening_drive_return not in (None, Decimal("0"))
        and item.qqq_late_window_return is not None
    )
    hit_count = sum(
        (drive > 0 and late > 0) or (drive < 0 and late < 0)
        for drive, late in drive_and_late
    )
    hit_rate = (
        None
        if not drive_and_late
        else _ratio(Decimal(hit_count), Decimal(len(drive_and_late)))
    )
    positive_late = tuple(
        late for drive, late in drive_and_late if drive is not None and drive > 0
    )
    negative_late = tuple(
        late for drive, late in drive_and_late if drive is not None and drive < 0
    )
    conditional_late = {
        "positive_opening_drive": _conditional_summary(positive_late),
        "negative_opening_drive": _conditional_summary(negative_late),
    }
    realized_by_symbol = {
        symbol: _conditional_summary(
            tuple(
                trade.return_pct
                for trade in period_trade_facts
                if trade.symbol == symbol
            )
        )
        for symbol in ("TQQQ", "SQQQ")
    }
    early_close_count = sum(item.early_close for item in period_sessions)
    traded_early_close_count = sum(
        item.early_close and item.session_date in traded_dates
        for item in period_sessions
    )
    trade_audit = [_trade_record(trade, turnover) for trade, turnover in period_trades]
    equity_audit = [
        [_timestamp_text(mark.at), _decimal_text(mark.equity)] for mark in period_marks
    ]
    return {
        "partition": partition["name"],
        "start": _timestamp_text(start),
        "end_exclusive": _timestamp_text(end),
        "opening_equity": _decimal_text(opening_equity),
        "ending_equity": _decimal_text(ending_equity),
        "equity_derived_return": _decimal_text(equity_return),
        "gross_strategy_return": _decimal_text(gross_return),
        "net_strategy_return": _decimal_text(net_return),
        "qqq_buy_and_hold_return": _optional_decimal_text(qqq_return),
        "qqq_observed_bar_count": len(period_qqq),
        "maximum_drawdown": _decimal_text(maximum_drawdown),
        "session_count": len(period_sessions),
        "eligible_session_count": eligible_count,
        "traded_session_count": traded_count,
        "no_trade_session_count": no_trade_count,
        "no_trade_reason_distribution": no_trade_distribution,
        "tqqq_entry_count": sum(trade.symbol == "TQQQ" for trade in period_trade_facts),
        "sqqq_entry_count": sum(trade.symbol == "SQQQ" for trade in period_trade_facts),
        "completed_trade_count": len(period_trade_facts),
        "turnover": _decimal_text(turnover),
        "exit_reason_distribution": exit_distribution,
        "stop_exit_count": exit_distribution["STOP"],
        "safety_exit_count": exit_distribution["SAFETY"],
        "forced_flat_exit_count": exit_distribution["FORCED_FLAT"],
        "win_rate": _decimal_text(win_rate),
        "average_win": _decimal_text(average_win),
        "average_loss": _decimal_text(average_loss),
        "average_holding_duration_microseconds": _decimal_text(average_duration),
        "median_holding_duration_microseconds": _decimal_text(median_duration),
        "opening_drive_hit_rate": _optional_decimal_text(hit_rate),
        "opening_drive_hit_count": hit_count,
        "opening_drive_hit_denominator": len(drive_and_late),
        "conditional_qqq_late_window_return": conditional_late,
        "realized_trade_return_by_symbol": realized_by_symbol,
        "missing_previous_close_session_count": no_trade_distribution[
            "MISSING_PREVIOUS_QQQ_CLOSE"
        ],
        "incomplete_first_half_hour_session_count": no_trade_distribution[
            "INCOMPLETE_FIRST_HALF_HOUR_QQQ"
        ],
        "missing_scheduled_entry_session_count": no_trade_distribution[
            "MISSING_SCHEDULED_ENTRY_BAR"
        ],
        "qqq_data_safety_at_entry_session_count": no_trade_distribution[
            "QQQ_DATA_SAFETY_AT_ENTRY"
        ],
        "missing_held_session_count": len(period_missing_dates),
        "missing_held_session_dates": [day.isoformat() for day in period_missing_dates],
        "early_close_session_count": early_close_count,
        "traded_early_close_session_count": traded_early_close_count,
        "trade_audit": {
            "count": len(trade_audit),
            "sha256": hashlib.sha256(canonical_json_bytes(trade_audit)).hexdigest(),
        },
        "equity_series": {
            "count": len(equity_audit),
            "sha256": hashlib.sha256(canonical_json_bytes(equity_audit)).hexdigest(),
        },
    }


def _conditional_summary(values: tuple[Decimal, ...]) -> dict[str, object]:
    if not values:
        return {"count": 0, "mean": None, "median": None}
    with localcontext(sparse_backtest_decimal_context()):
        mean = sum(values, Decimal("0")) / Decimal(len(values))
        median = _median(values)
    return {
        "count": len(values),
        "mean": _decimal_text(mean),
        "median": _decimal_text(median),
    }


def _classify_result(year_partitions: list[dict[str, object]]) -> str:
    if len(year_partitions) != len(_REPORTING_YEARS) + 1:
        raise Arch148IntradayMomentumEvidenceError("CLASSIFICATION_PARTITIONS_INVALID")
    full_partition = year_partitions[0]
    yearly = year_partitions[1:]
    if full_partition["partition"] != "OPEN_FULL" or len(yearly) != len(
        _REPORTING_YEARS
    ):
        raise Arch148IntradayMomentumEvidenceError("CLASSIFICATION_PARTITIONS_INVALID")
    stress_full_return = _parse_decimal(full_partition["net_strategy_return"])
    yearly_returns = tuple(
        _parse_decimal(partition["net_strategy_return"]) for partition in yearly
    )
    if stress_full_return <= 0 or _median(yearly_returns) <= 0:
        return "ECONOMICALLY_REJECTED"
    return "OPEN_CANDIDATE_ONLY"


def _partition_record(partition: dict[str, object]) -> dict[str, str]:
    return {
        "name": str(partition["name"]),
        "start": _timestamp_text(partition["start"]),
        "end_exclusive": _timestamp_text(partition["end_exclusive"]),
    }


def _cost_model_record(model: BacktestCostModel) -> dict[str, str]:
    return {
        "name": model.name,
        "slippage_bps": _decimal_text(model.slippage_bps),
        "commission_per_side": _decimal_text(model.commission_per_side),
    }


def _trade_record(trade: BacktestTrade, turnover: Decimal) -> dict[str, object]:
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
        "holding_duration_microseconds": _duration_microseconds(trade.holding_duration),
        "turnover": _decimal_text(turnover),
    }


def _median(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        raise Arch148IntradayMomentumEvidenceError("MEDIAN_REQUIRES_VALUES")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    with localcontext(sparse_backtest_decimal_context()):
        return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    with localcontext(sparse_backtest_decimal_context()):
        return numerator / denominator


def _duration_microseconds(value: timedelta) -> int:
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


def _timestamp_text(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None:
        raise Arch148IntradayMomentumEvidenceError("TIMESTAMP_INVALID")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _decimal_text(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise Arch148IntradayMomentumEvidenceError("NONFINITE_DECIMAL_METRIC")
    return format(value, "f")


def _optional_decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else _decimal_text(value)


def _parse_decimal(value: object) -> Decimal:
    if type(value) is not str:
        raise Arch148IntradayMomentumEvidenceError("DECIMAL_TEXT_INVALID")
    try:
        parsed = Decimal(value)
    except (ArithmeticError, ValueError):
        raise Arch148IntradayMomentumEvidenceError("DECIMAL_TEXT_INVALID") from None
    if not parsed.is_finite():
        raise Arch148IntradayMomentumEvidenceError("DECIMAL_TEXT_INVALID")
    return parsed


def _reason_text(value: object) -> str | None:
    if value is None:
        return None
    text = getattr(value, "value", value)
    if type(text) is not str:
        raise Arch148IntradayMomentumEvidenceError("NO_TRADE_REASON_INVALID")
    return text


def _ordered_unique_dates(values: tuple[date, ...]) -> bool:
    return (
        type(values) is tuple
        and all(type(value) is date for value in values)
        and tuple(sorted(set(values))) == values
    )


def _report_from_payload(payload: dict[str, object]) -> OpeningDriveResearchReport:
    _validate_report_payload(payload)
    identity = _research_identity(payload)
    document = {**payload, "identity": identity}
    return OpeningDriveResearchReport(canonical_json_bytes(document).decode("utf-8"))


def _research_identity(payload: dict[str, object]) -> str:
    material = canonical_json_bytes([RESEARCH_IDENTITY_VERSION, payload]).decode(
        "utf-8"
    )
    return str(uuid5(RESEARCH_NAMESPACE, material))


def _parse_report_json(value: str | bytes) -> dict[str, object]:
    body = value.encode("utf-8") if type(value) is str else value
    if type(body) is not bytes:
        raise Arch148IntradayMomentumEvidenceError("REPORT_JSON_INVALID")
    try:
        document = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except Arch148IntradayMomentumEvidenceError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise Arch148IntradayMomentumEvidenceError("REPORT_JSON_INVALID") from None
    if type(document) is not dict:
        raise Arch148IntradayMomentumEvidenceError("REPORT_JSON_INVALID")
    return document


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise Arch148IntradayMomentumEvidenceError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> None:
    raise Arch148IntradayMomentumEvidenceError("NONFINITE_JSON_NUMBER")


def _validate_report_document(document: dict[str, object]) -> None:
    if set(document) != {
        "schema",
        "strategy",
        "source",
        "inputs",
        "cost_models",
        "partitions",
        "runs",
        "classification",
        "final_holdout_sealed",
        "effects",
        "identity",
    }:
        raise Arch148IntradayMomentumEvidenceError("REPORT_FIELDS_INVALID")
    identity = document.get("identity")
    if type(identity) is not str or _UUID_PATTERN.fullmatch(identity) is None:
        raise Arch148IntradayMomentumEvidenceError("REPORT_IDENTITY_INVALID")
    payload = dict(document)
    del payload["identity"]
    if identity != _research_identity(payload):
        raise Arch148IntradayMomentumEvidenceError("REPORT_IDENTITY_MISMATCH")
    _validate_report_payload(payload)


def _validate_report_payload(payload: dict[str, object]) -> None:
    if payload.get("schema") != RESEARCH_SCHEMA:
        raise Arch148IntradayMomentumEvidenceError("REPORT_SCHEMA_INVALID")
    if payload.get("final_holdout_sealed") is not True:
        raise Arch148IntradayMomentumEvidenceError("HOLDOUT_SEAL_INVALID")
    strategy = payload.get("strategy")
    if strategy != {
        "id": OPENING_DRIVE_POLICY_ID,
        "replay_schema": OPENING_DRIVE_REPLAY_SCHEMA,
        "simulator_version": OPENING_DRIVE_SIMULATOR_VERSION,
        "partition_method": PARTITION_METHOD,
    }:
        raise Arch148IntradayMomentumEvidenceError("REPORT_STRATEGY_INVALID")
    source = payload.get("source")
    if (
        type(source) is not dict
        or set(source) != {"head", "tree"}
        or type(source.get("head")) is not str
        or _GIT_ID.fullmatch(source["head"]) is None
        or type(source.get("tree")) is not str
        or _GIT_ID.fullmatch(source["tree"]) is None
    ):
        raise Arch148IntradayMomentumEvidenceError("REPORT_SOURCE_INVALID")
    inputs = payload.get("inputs")
    if (
        type(inputs) is not dict
        or inputs.get("open_start") != _timestamp_text(_OPEN_START)
        or inputs.get("open_end_exclusive") != _timestamp_text(_OPEN_END_EXCLUSIVE)
        or inputs.get("requalification_sha256") != _ACCEPTED_REQUALIFICATION_SHA256
        or inputs.get("baseline_sha256") != _ACCEPTED_BASELINE_SHA256
        or inputs.get("churn_sha256") != _ACCEPTED_CHURN_SHA256
        or type(inputs.get("dataset")) is not dict
        or inputs["dataset"].get("identity") != _ACCEPTED_DATASET_IDENTITY
        or inputs["dataset"].get("sha256") != _ACCEPTED_DATASET_SHA256
        or inputs["dataset"].get("byte_length") != _ACCEPTED_DATASET_BYTE_LENGTH
        or type(inputs.get("custody")) is not dict
        or inputs["custody"].get("evidence_id") != _ACCEPTED_CUSTODY_IDENTITY
        or inputs["custody"].get("sha256") != _ACCEPTED_CUSTODY_SHA256
        or inputs["custody"].get("byte_length") != _ACCEPTED_CUSTODY_BYTE_LENGTH
        or inputs.get("schedule")
        != {
            "identity": ARCH148_INTRADAY_SCHEDULE_IDENTITY,
            "sha256": ARCH148_INTRADAY_SCHEDULE_DIGEST,
        }
    ):
        raise Arch148IntradayMomentumEvidenceError("REPORT_INPUTS_INVALID")
    expected_costs = [
        _cost_model_record(model) for model in (ZERO_COST, CONSERVATIVE_COSTS)
    ]
    if payload.get("cost_models") != expected_costs:
        raise Arch148IntradayMomentumEvidenceError("REPORT_COST_GRID_INVALID")
    expected_partitions = [_partition_record(item) for item in _partition_plan()]
    if payload.get("partitions") != expected_partitions:
        raise Arch148IntradayMomentumEvidenceError("REPORT_PARTITION_GRID_INVALID")
    runs = payload.get("runs")
    if type(runs) is not list or len(runs) != 2:
        raise Arch148IntradayMomentumEvidenceError("REPORT_RUNS_INVALID")
    for run, cost in zip(runs, expected_costs, strict=True):
        if (
            type(run) is not dict
            or set(run) != {"cost_model", "partitions"}
            or run.get("cost_model") != cost
            or type(run.get("partitions")) is not list
            or len(run["partitions"]) != len(expected_partitions)
            or [
                part.get("partition")
                for part in run["partitions"]
                if type(part) is dict
            ]
            != [item["name"] for item in expected_partitions]
        ):
            raise Arch148IntradayMomentumEvidenceError("REPORT_RUN_PARTITIONS_INVALID")
        for part in run["partitions"]:
            _validate_partition_payload(part)
    expected_classification = _classify_result(runs[1]["partitions"])
    if payload.get("classification") != expected_classification:
        raise Arch148IntradayMomentumEvidenceError("REPORT_CLASSIFICATION_INVALID")
    effects = payload.get("effects")
    if (
        type(effects) is not dict
        or set(effects) != set(_ZERO_EFFECT_COUNTERS)
        or any(type(value) is not int or value != 0 for value in effects.values())
    ):
        raise Arch148IntradayMomentumEvidenceError("REPORT_EFFECTS_INVALID")


def _validate_partition_payload(partition: object) -> None:
    fields = {
        "partition",
        "start",
        "end_exclusive",
        "opening_equity",
        "ending_equity",
        "equity_derived_return",
        "gross_strategy_return",
        "net_strategy_return",
        "qqq_observed_bar_count",
        "qqq_buy_and_hold_return",
        "maximum_drawdown",
        "session_count",
        "eligible_session_count",
        "traded_session_count",
        "no_trade_session_count",
        "no_trade_reason_distribution",
        "tqqq_entry_count",
        "sqqq_entry_count",
        "completed_trade_count",
        "turnover",
        "exit_reason_distribution",
        "stop_exit_count",
        "safety_exit_count",
        "forced_flat_exit_count",
        "win_rate",
        "average_win",
        "average_loss",
        "average_holding_duration_microseconds",
        "median_holding_duration_microseconds",
        "opening_drive_hit_rate",
        "opening_drive_hit_count",
        "opening_drive_hit_denominator",
        "conditional_qqq_late_window_return",
        "realized_trade_return_by_symbol",
        "missing_previous_close_session_count",
        "incomplete_first_half_hour_session_count",
        "missing_scheduled_entry_session_count",
        "qqq_data_safety_at_entry_session_count",
        "missing_held_session_count",
        "missing_held_session_dates",
        "early_close_session_count",
        "traded_early_close_session_count",
        "trade_audit",
        "equity_series",
    }
    if type(partition) is not dict or set(partition) != fields:
        raise Arch148IntradayMomentumEvidenceError("PARTITION_FIELDS_INVALID")
    integer_fields = fields.intersection(
        {
            "session_count",
            "qqq_observed_bar_count",
            "eligible_session_count",
            "traded_session_count",
            "no_trade_session_count",
            "tqqq_entry_count",
            "sqqq_entry_count",
            "completed_trade_count",
            "stop_exit_count",
            "safety_exit_count",
            "forced_flat_exit_count",
            "opening_drive_hit_count",
            "opening_drive_hit_denominator",
            "missing_previous_close_session_count",
            "incomplete_first_half_hour_session_count",
            "missing_scheduled_entry_session_count",
            "qqq_data_safety_at_entry_session_count",
            "missing_held_session_count",
            "early_close_session_count",
            "traded_early_close_session_count",
        }
    )
    if any(
        type(partition[name]) is not int or partition[name] < 0
        for name in integer_fields
    ):
        raise Arch148IntradayMomentumEvidenceError("PARTITION_COUNT_INVALID")
    decimal_fields = {
        "opening_equity",
        "ending_equity",
        "equity_derived_return",
        "gross_strategy_return",
        "net_strategy_return",
        "maximum_drawdown",
        "turnover",
        "win_rate",
        "average_win",
        "average_loss",
        "average_holding_duration_microseconds",
        "median_holding_duration_microseconds",
    }
    for name in decimal_fields:
        _parse_decimal(partition[name])
    if partition["qqq_buy_and_hold_return"] is not None:
        _parse_decimal(partition["qqq_buy_and_hold_return"])
    if partition["opening_drive_hit_rate"] is not None:
        _parse_decimal(partition["opening_drive_hit_rate"])
    for summary_name, keys in (
        (
            "conditional_qqq_late_window_return",
            ("positive_opening_drive", "negative_opening_drive"),
        ),
        ("realized_trade_return_by_symbol", ("TQQQ", "SQQQ")),
    ):
        summary = partition[summary_name]
        if type(summary) is not dict or set(summary) != set(keys):
            raise Arch148IntradayMomentumEvidenceError("CONDITIONAL_SUMMARY_INVALID")
        for item in summary.values():
            if (
                type(item) is not dict
                or set(item) != {"count", "mean", "median"}
                or type(item["count"]) is not int
                or item["count"] < 0
                or ((item["mean"] is None) != (item["count"] == 0))
                or ((item["median"] is None) != (item["count"] == 0))
            ):
                raise Arch148IntradayMomentumEvidenceError(
                    "CONDITIONAL_SUMMARY_INVALID"
                )
            if item["mean"] is not None:
                _parse_decimal(item["mean"])
                _parse_decimal(item["median"])
    no_trade = partition["no_trade_reason_distribution"]
    exits = partition["exit_reason_distribution"]
    if (
        type(no_trade) is not dict
        or set(no_trade) != set(_NO_TRADE_REASONS)
        or any(type(value) is not int or value < 0 for value in no_trade.values())
        or sum(no_trade.values()) != partition["no_trade_session_count"]
        or type(exits) is not dict
        or set(exits) != set(_EXIT_REASONS)
        or any(type(value) is not int or value < 0 for value in exits.values())
        or sum(exits.values()) != partition["completed_trade_count"]
        or partition["traded_session_count"] != partition["completed_trade_count"]
        or partition["tqqq_entry_count"] + partition["sqqq_entry_count"]
        != partition["completed_trade_count"]
        or partition["session_count"]
        != partition["traded_session_count"] + partition["no_trade_session_count"]
        or partition["traded_session_count"] > partition["eligible_session_count"]
        or partition["eligible_session_count"] > partition["session_count"]
        or partition["opening_drive_hit_count"]
        > partition["opening_drive_hit_denominator"]
    ):
        raise Arch148IntradayMomentumEvidenceError("PARTITION_DISTRIBUTION_INVALID")
    for audit_name in ("trade_audit", "equity_series"):
        audit = partition[audit_name]
        if (
            type(audit) is not dict
            or set(audit) != {"count", "sha256"}
            or type(audit["count"]) is not int
            or audit["count"] < 0
            or type(audit["sha256"]) is not str
            or _SHA256.fullmatch(audit["sha256"]) is None
        ):
            raise Arch148IntradayMomentumEvidenceError("PARTITION_AUDIT_INVALID")
