"""Canonical synthetic-safe evidence and fixed classification for Arch149.

The public builder consumes an already constructed A147 dataset in memory. It
does not read data, discover files, call providers, or expose an operator path.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext
from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar
from trading_bot.experiments.arch149_monthly_defensive_rotation import (
    CASH,
    DECIMAL_CONTEXT,
    STRATEGY_ID,
    DailyEquityMark,
    MonthlyTarget,
    RotationFill,
    RotationReplay,
    TargetResolution,
    monthly_rotation_identity,
    replay_monthly_defensive_rotation,
    verify_rotation_replay_identity,
)
from trading_bot.experiments.filtered_trend_campaign import (
    BASE_COSTS,
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
)

EVIDENCE_SCHEMA: Final = "arch149-monthly-defensive-rotation-evidence/v1"
REPORTING_START: Final = date(2017, 1, 1)
REPORTING_END: Final = date(2024, 1, 1)
PARTITION_LABELS: Final = (
    "EXPLORATORY_FULL",
    *(str(year) for year in range(2017, 2024)),
)
ZERO_EFFECT_COUNTER_NAMES: Final = (
    "ai_service_calls",
    "credential_reads",
    "provider_network_calls",
    "robinhood_calls",
    "broker_calls",
    "order_effects",
    "production_state_reads",
    "production_state_writes",
    "final_holdout_accesses",
    "strategy_promotions",
)
PASSIVE_COMPARISON_BASIS: Final = (
    "ADJUSTED_PRICE_FIRST_SCORING_OPEN_TO_LAST_SCORING_CLOSE"
)
_NEW_YORK: Final = ZoneInfo("America/New_York")
REPORTING_CONVENTIONS: Final = (
    "WARMUP_2016_EXCLUDED_FROM_REPORTABLE_RECORDS",
    "DECEMBER_2023_TARGET_IS_TERMINAL_WITHOUT_NEXT_SESSION_LOOKUP",
    "VALID_SIGNALS_AND_CASH_TARGETS_COUNT_BY_SIGNAL_DATE",
    "REBALANCES_UNCHANGED_TARGETS_SWITCHES_AND_FILLS_COUNT_BY_ACTION_DATE",
    "MISSING_INPUT_IS_A_SEPARATE_NON_SIGNAL_NO_REBALANCE_DIAGNOSTIC",
    "ANNUAL_PARTITIONS_SLICE_ONE_CONTINUOUS_PORTFOLIO_PATH",
    "NET_DAILY_RETURN_FIRST_MARK_USES_SLICE_OPENING_EQUITY",
    "CAGR_USES_SEVEN_CALENDAR_YEARS_FULL_AND_ONE_YEAR_ANNUAL",
    "MAXIMUM_DRAWDOWN_IS_PEAK_TO_TROUGH_FRACTION_FROM_SLICE_OPENING_EQUITY",
    "VOLATILITY_USES_SAMPLE_DAILY_RETURN_DEVIATION_TIMES_SQRT_252",
    "SHARPE_USES_ZERO_RISK_FREE_DAILY_MEAN_OVER_SAMPLE_DEVIATION_TIMES_SQRT_252",
    "TURNOVER_IS_FILL_NOTIONAL_OVER_MEAN_DAILY_EQUITY",
    "TIME_INVESTED_IS_THE_SCORING_SESSION_FRACTION_HELD_AT_CLOSE",
    "MONTHS_HELD_COUNTS_QUALIFIED_MONTH_END_CLOSING_HOLDINGS",
    "PASSIVE_COMPARISON_USES_FIRST_SCORING_OPEN_TO_LAST_SCORING_CLOSE",
    "DEGENERATE_SHARPE_IS_UNDEFINED_AND_SINGLETON_VOLATILITY_IS_UNDEFINED",
)

# The test suite may replace these private pins only for synthetic fixtures.
_ACCEPTED_DATASET_IDENTITY: Final = "d5aa8ed7-b5cd-53a3-8671-5370f976e8e3"
_ACCEPTED_DATASET_SHA256: Final = (
    "ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214"
)
_SOURCE_ID_PATTERN: Final = re.compile(r"^[0-9a-f]{40}$")
_PARTITIONS: Final = (
    ("EXPLORATORY_FULL", date(2017, 1, 1), date(2024, 1, 1), 7),
    *(
        (str(year), date(year, 1, 1), date(year + 1, 1, 1), 1)
        for year in range(2017, 2024)
    ),
)
_STRESS_MAX_DRAWDOWN_LIMIT: Final = Decimal("0.35")


class MonthlyDefensiveRotationEvidenceError(ValueError):
    """Misbound or incomplete Arch149 evidence input."""


class ExploratoryClassification(StrEnum):
    ECONOMICALLY_REJECTED = "ECONOMICALLY_REJECTED"
    EXPLORATORY_CANDIDATE_ONLY = "EXPLORATORY_CANDIDATE_ONLY"


@dataclass(frozen=True, slots=True)
class DatasetEvidenceBinding:
    """In-memory integrity facts for the accepted serialized A147 dataset."""

    dataset_identity: str
    sha256: str
    byte_length: int
    price_basis: str
    start: datetime
    end_exclusive: datetime

    def __post_init__(self) -> None:
        if self.dataset_identity != _ACCEPTED_DATASET_IDENTITY:
            raise MonthlyDefensiveRotationEvidenceError(
                "dataset evidence identity differs from the accepted A147 dataset"
            )
        if self.sha256 != _ACCEPTED_DATASET_SHA256 or not re.fullmatch(
            r"[0-9a-f]{64}", self.sha256
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "dataset evidence SHA differs from the accepted A147 dataset"
            )
        if type(self.byte_length) is not int or self.byte_length <= 0:
            raise MonthlyDefensiveRotationEvidenceError(
                "dataset evidence byte length must be positive"
            )
        if (
            self.price_basis != PRICE_BASIS
            or self.start != DATA_START
            or self.end_exclusive != DATA_END_EXCLUSIVE
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "dataset evidence bounds or price basis differ from A147"
            )


@dataclass(frozen=True, slots=True)
class PassiveComparison:
    """Price-only descriptive support over the frozen scoring interval."""

    symbol: str
    basis: str
    start_session: date
    end_session: date
    starting_open: Decimal
    ending_close: Decimal
    price_return: Decimal

    def __post_init__(self) -> None:
        if self.symbol not in ("SPY", "QQQ"):
            raise MonthlyDefensiveRotationEvidenceError(
                "passive comparison is outside the frozen support pair"
            )
        if self.basis != PASSIVE_COMPARISON_BASIS:
            raise MonthlyDefensiveRotationEvidenceError(
                "passive comparison basis is not frozen"
            )
        if not REPORTING_START <= self.start_session < self.end_session < REPORTING_END:
            raise MonthlyDefensiveRotationEvidenceError(
                "passive comparison dates are outside the scoring interval"
            )
        for value in (self.starting_open, self.ending_close):
            if type(value) is not Decimal or not value.is_finite() or value <= 0:
                raise MonthlyDefensiveRotationEvidenceError(
                    "passive comparison prices must be positive finite Decimals"
                )
        with localcontext(DECIMAL_CONTEXT):
            expected = self.ending_close / self.starting_open - Decimal(1)
        if self.price_return != expected:
            raise MonthlyDefensiveRotationEvidenceError(
                "passive comparison return does not match its price endpoints"
            )


@dataclass(frozen=True, slots=True)
class PartitionDiagnostics:
    """Descriptive continuous-path diagnostics for one fixed calendar slice."""

    label: str
    start: date
    end_exclusive: date
    opening_equity: Decimal
    final_equity: Decimal
    net_return: Decimal
    cagr: Decimal
    maximum_drawdown: Decimal
    annualized_volatility: Decimal | None
    sharpe_ratio: Decimal | None
    annual_returns: tuple[tuple[str, Decimal], ...]
    month_end_signal_count: int
    missing_input_no_rebalance_count: int
    executable_rebalance_count: int
    unchanged_target_count: int
    cash_target_count: int
    etf_switch_count: int
    insufficient_whole_shares_count: int
    fill_count: int
    turnover_notional: Decimal
    turnover: Decimal
    time_invested: Decimal
    months_held: tuple[tuple[str, int], ...]
    entry_count_by_symbol: tuple[tuple[str, int], ...]
    target_sequence_identity: str
    trade_audit_identity: str
    daily_equity_identity: str
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        expected_window = next(
            (
                (start, end)
                for label, start, end, _ in _PARTITIONS
                if label == self.label
            ),
            None,
        )
        if expected_window != (self.start, self.end_exclusive):
            raise MonthlyDefensiveRotationEvidenceError(
                "partition label and window must match the frozen reporting map"
            )
        decimal_values = (
            self.opening_equity,
            self.final_equity,
            self.net_return,
            self.cagr,
            self.maximum_drawdown,
            self.turnover_notional,
            self.turnover,
            self.time_invested,
        )
        if any(
            type(value) is not Decimal or not value.is_finite()
            for value in decimal_values
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "partition metrics must be finite Decimals"
            )
        if self.annualized_volatility is not None and (
            type(self.annualized_volatility) is not Decimal
            or not self.annualized_volatility.is_finite()
            or self.annualized_volatility < 0
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "annualized volatility must be nonnegative or undefined"
            )
        if self.sharpe_ratio is not None and (
            type(self.sharpe_ratio) is not Decimal or not self.sharpe_ratio.is_finite()
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "Sharpe ratio must be finite or undefined"
            )
        if self.opening_equity <= 0 or self.final_equity <= 0:
            raise MonthlyDefensiveRotationEvidenceError(
                "portfolio equity must remain positive"
            )
        if not Decimal(0) <= self.maximum_drawdown <= Decimal(1):
            raise MonthlyDefensiveRotationEvidenceError(
                "maximum drawdown must be a nonnegative fraction"
            )
        if not Decimal(0) <= self.time_invested <= Decimal(1):
            raise MonthlyDefensiveRotationEvidenceError(
                "time invested must be a session fraction"
            )
        counts = (
            self.month_end_signal_count,
            self.missing_input_no_rebalance_count,
            self.executable_rebalance_count,
            self.unchanged_target_count,
            self.cash_target_count,
            self.etf_switch_count,
            self.insufficient_whole_shares_count,
            self.fill_count,
        )
        if any(type(count) is not int or count < 0 for count in counts):
            raise MonthlyDefensiveRotationEvidenceError(
                "partition event counts must be nonnegative integers"
            )
        for vector in (self.months_held, self.entry_count_by_symbol):
            if (
                type(vector) is not tuple
                or tuple(symbol for symbol, _ in vector) != UNIVERSE
                or any(type(count) is not int or count < 0 for _, count in vector)
            ):
                raise MonthlyDefensiveRotationEvidenceError(
                    "per-symbol metrics must preserve universe order"
                )
        if type(self.annual_returns) is not tuple or any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not Decimal
            or not item[1].is_finite()
            for item in self.annual_returns
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "annual returns must be an ordered immutable Decimal vector"
            )
        if any(
            not _is_sha_identity(value)
            for value in (
                self.target_sequence_identity,
                self.trade_audit_identity,
                self.daily_equity_identity,
            )
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "partition component identities must be UUID5 values"
            )
        object.__setattr__(
            self,
            "identity",
            monthly_rotation_identity("evidence-partition", self.identity_material),
        )

    @property
    def identity_material(self) -> tuple[object, ...]:
        return (
            self.label,
            self.start,
            self.end_exclusive,
            self.opening_equity,
            self.final_equity,
            self.net_return,
            self.cagr,
            self.maximum_drawdown,
            self.annualized_volatility,
            self.sharpe_ratio,
            self.annual_returns,
            self.month_end_signal_count,
            self.missing_input_no_rebalance_count,
            self.executable_rebalance_count,
            self.unchanged_target_count,
            self.cash_target_count,
            self.etf_switch_count,
            self.insufficient_whole_shares_count,
            self.fill_count,
            self.turnover_notional,
            self.turnover,
            self.time_invested,
            self.months_held,
            self.entry_count_by_symbol,
            self.target_sequence_identity,
            self.trade_audit_identity,
            self.daily_equity_identity,
        )


@dataclass(frozen=True, slots=True)
class CostCaseEvidence:
    """One complete replay and its fixed report partitions."""

    costs: Costs
    replay: RotationReplay
    partitions: tuple[PartitionDiagnostics, ...]
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.costs) is not Costs or self.costs not in (
            BASE_COSTS,
            STRESS_COSTS,
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "cost-case evidence must use frozen BASE or STRESS economics"
            )
        if type(self.replay) is not RotationReplay or self.replay.costs != self.costs:
            raise MonthlyDefensiveRotationEvidenceError(
                "cost-case replay is inconsistent"
            )
        if (
            type(self.partitions) is not tuple
            or tuple(item.label for item in self.partitions) != PARTITION_LABELS
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "cost case must preserve all eight ordered report partitions"
            )
        full = self.partitions[0]
        expected_annual_returns = tuple(
            (str(year), self.partitions[index].net_return)
            for index, year in enumerate(range(2017, 2024), start=1)
        )
        if (
            full.opening_equity != self.replay.initial_equity
            or full.final_equity != self.replay.final_equity
            or full.annual_returns != expected_annual_returns
            or full.target_sequence_identity != self.replay.target_sequence_identity
            or full.trade_audit_identity != self.replay.trade_audit_identity
            or full.daily_equity_identity != self.replay.daily_equity_identity
            or full.turnover != self.replay.turnover
            or full.time_invested != self.replay.time_invested
            or full.months_held != self.replay.months_held
            or full.entry_count_by_symbol != self.replay.entry_counts
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "full partition does not preserve the replay totals"
            )
        expected_identity = monthly_rotation_identity(
            "cost-case-evidence",
            (
                (self.costs.commission, self.costs.slippage_bps),
                self.replay.identity,
                tuple(item.identity for item in self.partitions),
            ),
        )
        object.__setattr__(self, "identity", expected_identity)


@dataclass(frozen=True, slots=True)
class RotationEvidenceReport:
    """Complete BASE/STRESS source-only report for the single Arch149 trial."""

    source_head: str
    source_tree: str
    dataset_identity: str
    dataset_sha256: str
    dataset_byte_length: int
    dataset_evidence_binding: DatasetEvidenceBinding
    base: CostCaseEvidence
    stress: CostCaseEvidence
    passive_comparisons: tuple[PassiveComparison, ...]
    classification: ExploratoryClassification
    zero_effects: tuple[tuple[str, int], ...]
    identity: str = field(init=False)
    schema: str = field(default=EVIDENCE_SCHEMA, init=False)
    strategy_id: str = field(default=STRATEGY_ID, init=False)
    final_holdout_sealed: bool = field(default=True, init=False)
    reporting_conventions: tuple[str, ...] = field(
        default=REPORTING_CONVENTIONS, init=False
    )

    def __post_init__(self) -> None:
        if (
            type(self.source_head) is not str
            or type(self.source_tree) is not str
            or not _SOURCE_ID_PATTERN.fullmatch(self.source_head)
            or not _SOURCE_ID_PATTERN.fullmatch(self.source_tree)
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "source HEAD and tree must be lower-case Git object IDs"
            )
        if self.dataset_identity != _ACCEPTED_DATASET_IDENTITY:
            raise MonthlyDefensiveRotationEvidenceError(
                "report dataset is outside the accepted A147 identity"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", self.dataset_sha256):
            raise MonthlyDefensiveRotationEvidenceError(
                "dataset SHA-256 must be lower-case hexadecimal"
            )
        if type(self.dataset_byte_length) is not int or self.dataset_byte_length <= 0:
            raise MonthlyDefensiveRotationEvidenceError(
                "dataset byte length must be positive"
            )
        if (
            type(self.dataset_evidence_binding) is not DatasetEvidenceBinding
            or self.dataset_evidence_binding.dataset_identity != self.dataset_identity
            or self.dataset_evidence_binding.sha256 != self.dataset_sha256
            or self.dataset_evidence_binding.byte_length != self.dataset_byte_length
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "dataset evidence binding must match report integrity facts"
            )
        if (
            type(self.base) is not CostCaseEvidence
            or type(self.stress) is not CostCaseEvidence
            or self.base.costs != BASE_COSTS
            or self.stress.costs != STRESS_COSTS
            or self.base.replay.dataset_identity != self.dataset_identity
            or self.stress.replay.dataset_identity != self.dataset_identity
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "report must bind exactly one BASE and one STRESS replay"
            )
        if not _same_signal_decisions(
            self.base.replay.targets, self.stress.replay.targets
        ):
            raise MonthlyDefensiveRotationEvidenceError(
                "BASE and STRESS replays disagree on the frozen signal sequence"
            )
        if type(self.passive_comparisons) is not tuple or tuple(
            item.symbol for item in self.passive_comparisons
        ) != ("SPY", "QQQ"):
            raise MonthlyDefensiveRotationEvidenceError(
                "report requires ordered SPY and QQQ passive comparisons"
            )
        if type(self.classification) is not ExploratoryClassification:
            raise MonthlyDefensiveRotationEvidenceError(
                "classification must use a declared frozen value"
            )
        if self.classification is not _classify_stress(self.stress.partitions[0]):
            raise MonthlyDefensiveRotationEvidenceError(
                "classification disagrees with the frozen STRESS gates"
            )
        expected_zeros = tuple((name, 0) for name in ZERO_EFFECT_COUNTER_NAMES)
        if self.zero_effects != expected_zeros:
            raise MonthlyDefensiveRotationEvidenceError(
                "all external and lifecycle effect counters must remain zero"
            )
        object.__setattr__(
            self,
            "identity",
            monthly_rotation_identity("evidence-report", self.identity_material),
        )

    @property
    def identity_material(self) -> tuple[object, ...]:
        # The accepted dataset SHA is reported as an integrity check but is not
        # deterministic domain-identity material. Dataset identity is semantic.
        return (
            self.schema,
            self.strategy_id,
            self.source_head,
            self.source_tree,
            self.dataset_identity,
            self.dataset_evidence_binding.dataset_identity,
            self.base.identity,
            self.stress.identity,
            tuple(_identity_passive(item) for item in self.passive_comparisons),
            self.classification.value,
            self.zero_effects,
            self.final_holdout_sealed,
            self.reporting_conventions,
        )

    def to_dict(self) -> dict[str, object]:
        """Return a complete JSON-compatible immutable-evidence projection."""
        return _json_value(self)

    def to_json(self) -> str:
        """Return canonical report JSON with exact Decimal strings."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )


def evaluate_monthly_defensive_rotation(
    dataset: MultiAssetDataset, *, source_head: str, source_tree: str
) -> RotationEvidenceReport:
    """Build the fixed report from one in-memory accepted A147 dataset.

    The function validates the dataset's pinned semantic identity and canonical
    serialized SHA before running one BASE and one STRESS replay. It has no
    filesystem, network, provider, credential, broker, production, or holdout
    reader and cannot acquire another dataset.
    """
    _validate_source_ids(source_head, source_tree)
    binding = _validate_dataset_binding(dataset)
    base_replay = replay_monthly_defensive_rotation(dataset, costs=BASE_COSTS)
    stress_replay = replay_monthly_defensive_rotation(dataset, costs=STRESS_COSTS)
    _validate_replay(dataset, base_replay, BASE_COSTS)
    _validate_replay(dataset, stress_replay, STRESS_COSTS)
    if not _same_signal_decisions(base_replay.targets, stress_replay.targets):
        raise MonthlyDefensiveRotationEvidenceError(
            "BASE and STRESS replays must preserve the exact signal decisions"
        )
    base = _build_cost_case(base_replay)
    stress = _build_cost_case(stress_replay)
    comparisons = _passive_comparisons(dataset)
    classification = _classify_stress(stress.partitions[0])
    return RotationEvidenceReport(
        source_head=source_head,
        source_tree=source_tree,
        dataset_identity=dataset.identity,
        dataset_sha256=binding.sha256,
        dataset_byte_length=binding.byte_length,
        dataset_evidence_binding=binding,
        base=base,
        stress=stress,
        passive_comparisons=comparisons,
        classification=classification,
        zero_effects=tuple((name, 0) for name in ZERO_EFFECT_COUNTER_NAMES),
    )


def _validate_source_ids(source_head: str, source_tree: str) -> None:
    if type(source_head) is not str or not _SOURCE_ID_PATTERN.fullmatch(source_head):
        raise MonthlyDefensiveRotationEvidenceError(
            "source_head must be a lower-case 40-character Git object ID"
        )
    if type(source_tree) is not str or not _SOURCE_ID_PATTERN.fullmatch(source_tree):
        raise MonthlyDefensiveRotationEvidenceError(
            "source_tree must be a lower-case 40-character Git object ID"
        )


def _validate_dataset_binding(dataset: MultiAssetDataset) -> DatasetEvidenceBinding:
    if type(dataset) is not MultiAssetDataset:
        raise MonthlyDefensiveRotationEvidenceError(
            "an already constructed exact A147 MultiAssetDataset is required"
        )
    if (
        dataset.identity != _ACCEPTED_DATASET_IDENTITY
        or dataset.price_basis != PRICE_BASIS
        or dataset.symbols != UNIVERSE
    ):
        raise MonthlyDefensiveRotationEvidenceError(
            "dataset identity, price basis, or universe differs from the accepted"
            " binding"
        )
    for symbol_data in dataset.datasets:
        for bar in symbol_data.bars:
            day = bar.timestamp.astimezone(_NEW_YORK).date()
            if not DATA_START.date() <= day < DATA_END_EXCLUSIVE.date():
                raise MonthlyDefensiveRotationEvidenceError(
                    "dataset contains a bar outside the accepted 2016-2023 interval"
                )
    body = dataset.to_json().encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    if digest != _ACCEPTED_DATASET_SHA256:
        raise MonthlyDefensiveRotationEvidenceError(
            "dataset canonical bytes do not match the accepted A147 SHA-256"
        )
    return DatasetEvidenceBinding(
        dataset_identity=dataset.identity,
        sha256=digest,
        byte_length=len(body),
        price_basis=dataset.price_basis,
        start=DATA_START,
        end_exclusive=DATA_END_EXCLUSIVE,
    )


def _dataset_session_bars(
    dataset: MultiAssetDataset,
) -> tuple[tuple[date, ...], dict[tuple[str, date], Bar]]:
    first = dataset.datasets[0].bars
    dates = tuple(bar.timestamp.astimezone(_NEW_YORK).date() for bar in first)
    bars: dict[tuple[str, date], Bar] = {}
    for item in dataset.datasets:
        for bar in item.bars:
            day = bar.timestamp.astimezone(_NEW_YORK).date()
            bars[(item.symbol, day)] = bar
    return dates, bars


def _date_in_window(value: date, start: date, end_exclusive: date) -> bool:
    return start <= value < end_exclusive


def _expected_month_ends(dates: tuple[date, ...]) -> tuple[date, ...]:
    scoring = tuple(day for day in dates if REPORTING_START <= day < REPORTING_END)
    return tuple(
        day
        for index, day in enumerate(scoring)
        if index + 1 == len(scoring)
        or (day.year, day.month) != (scoring[index + 1].year, scoring[index + 1].month)
    )


def _validate_replay(
    dataset: MultiAssetDataset, replay: RotationReplay, expected_costs: Costs
) -> None:
    if (
        type(replay) is not RotationReplay
        or replay.costs != expected_costs
        or replay.strategy_id != STRATEGY_ID
        or replay.initial_equity != STARTING_CASH
        or replay.dataset_identity != dataset.identity
        or not verify_rotation_replay_identity(replay)
    ):
        raise MonthlyDefensiveRotationEvidenceError(
            "replay does not verify against the supplied dataset and cost case"
        )
    dates, bars = _dataset_session_bars(dataset)
    scoring_dates = tuple(
        day for day in dates if REPORTING_START <= day < REPORTING_END
    )
    if tuple(mark.session_date for mark in replay.daily_marks) != scoring_dates:
        raise MonthlyDefensiveRotationEvidenceError(
            "daily replay marks must exactly cover scoring sessions only"
        )
    if any(
        mark.session_date < REPORTING_START or mark.session_date >= REPORTING_END
        for mark in replay.daily_marks
    ):
        raise MonthlyDefensiveRotationEvidenceError(
            "a daily result mark crossed the warmup or confirmation firewall"
        )
    expected_targets = _expected_month_ends(dates)
    if tuple(target.signal_date for target in replay.targets) != expected_targets:
        raise MonthlyDefensiveRotationEvidenceError(
            "target sequence must cover every scoring month-end exactly once"
        )
    date_index = {day: index for index, day in enumerate(dates)}
    for target in replay.targets:
        position = date_index[target.signal_date]
        expected_next = dates[position + 1] if position + 1 < len(dates) else None
        if target.signal_date == expected_targets[-1]:
            if (
                target.signal_date.year != 2023
                or target.signal_date.month != 12
                or target.resolution is not TargetResolution.END_OF_EXPLORATION
                or target.next_session is not None
            ):
                raise MonthlyDefensiveRotationEvidenceError(
                    "the final 2023 target must remain non-executable"
                )
        elif target.resolution is TargetResolution.END_OF_EXPLORATION:
            raise MonthlyDefensiveRotationEvidenceError(
                "only the terminal 2023 target may use END_OF_EXPLORATION"
            )
        elif target.resolution is TargetResolution.MISSING_INPUT:
            if target.target is not None or target.next_session is not None:
                raise MonthlyDefensiveRotationEvidenceError(
                    "missing-input diagnostics cannot carry an executable target"
                )
        elif target.next_session != expected_next or expected_next is None:
            raise MonthlyDefensiveRotationEvidenceError(
                "target action date must be the following in-range qualified session"
            )
    _validate_fills(replay, bars, expected_costs)
    with localcontext(DECIMAL_CONTEXT):
        expected_turnover = sum(replay.fill_turnovers, Decimal(0)) / (
            sum((mark.equity for mark in replay.daily_marks), Decimal(0))
            / len(replay.daily_marks)
        )
        expected_invested = Decimal(
            sum(mark.held_symbol is not None for mark in replay.daily_marks)
        ) / len(replay.daily_marks)
    expected_months_held, expected_entries = _replay_counts(replay)
    if (
        replay.turnover != expected_turnover
        or replay.time_invested != expected_invested
        or replay.months_held != expected_months_held
        or replay.entry_counts != expected_entries
    ):
        raise MonthlyDefensiveRotationEvidenceError(
            "replay summary counts or turnover do not match its captured facts"
        )


def _validate_fills(
    replay: RotationReplay,
    bars: dict[tuple[str, date], Bar],
    costs: Costs,
) -> None:
    targets = {target.signal_date: target for target in replay.targets}
    fills_by_signal: dict[date, list[RotationFill]] = defaultdict(list)
    sequence_by_timestamp: dict[datetime, list[RotationFill]] = defaultdict(list)
    with localcontext(DECIMAL_CONTEXT):
        slip = costs.slippage_bps / Decimal(10000)
        for fill in replay.fills:
            target = targets.get(fill.signal_date)
            fill_date = fill.timestamp.astimezone(_NEW_YORK).date()
            if (
                target is None
                or target.next_session != fill_date
                or target.resolution
                in (
                    TargetResolution.MISSING_INPUT,
                    TargetResolution.END_OF_EXPLORATION,
                )
            ):
                raise MonthlyDefensiveRotationEvidenceError(
                    "fill is not bound to an executable month-end target"
                )
            bar = bars.get((fill.symbol, fill_date))
            if (
                bar is None
                or fill.timestamp != bar.timestamp
                or fill.execution_open != bar.open
            ):
                raise MonthlyDefensiveRotationEvidenceError(
                    "fill execution price is not the exact supplied qualified OPEN"
                )
            expected_price = fill.execution_open * (
                Decimal(1) + slip if fill.side == "BUY" else Decimal(1) - slip
            )
            if fill.price != expected_price or fill.commission != costs.commission:
                raise MonthlyDefensiveRotationEvidenceError(
                    "fill economics do not match the frozen cost case"
                )
            sequence_by_timestamp[fill.timestamp].append(fill)
            fills_by_signal[fill.signal_date].append(fill)
        for target in replay.targets:
            associated = fills_by_signal.get(target.signal_date, [])
            buys = tuple(fill for fill in associated if fill.side == "BUY")
            sells = tuple(fill for fill in associated if fill.side == "SELL")
            if (
                target.resolution
                in (
                    TargetResolution.MISSING_INPUT,
                    TargetResolution.END_OF_EXPLORATION,
                    TargetResolution.UNCHANGED_TARGET,
                )
                and associated
            ):
                raise MonthlyDefensiveRotationEvidenceError(
                    "non-executable or unchanged targets cannot create fills"
                )
            if target.resolution is TargetResolution.REBALANCED:
                if target.target == CASH and (len(sells) != 1 or buys):
                    raise MonthlyDefensiveRotationEvidenceError(
                        "a cash rebalance must contain its single liquidation fill"
                    )
                if target.target != CASH and (
                    len(buys) != 1
                    or buys[0].symbol != target.target
                    or len(sells) > 1
                    or any(fill.symbol == target.target for fill in sells)
                ):
                    raise MonthlyDefensiveRotationEvidenceError(
                        "an ETF rebalance must buy its target after any prior sale"
                    )
            if target.resolution is TargetResolution.INSUFFICIENT_WHOLE_SHARES and (
                target.target == CASH or buys or len(sells) > 1
            ):
                raise MonthlyDefensiveRotationEvidenceError(
                    "whole-share insufficiency cannot create a target buy"
                )
        for same_timestamp in sequence_by_timestamp.values():
            sides = tuple(fill.side for fill in same_timestamp)
            if "SELL" in sides and "BUY" in sides:
                if max(i for i, side in enumerate(sides) if side == "SELL") > min(
                    i for i, side in enumerate(sides) if side == "BUY"
                ):
                    raise MonthlyDefensiveRotationEvidenceError(
                        "ETF switches must sell before buying at the shared OPEN"
                    )


def _replay_counts(
    replay: RotationReplay,
) -> tuple[tuple[tuple[str, int], ...], tuple[tuple[str, int], ...]]:
    marks = {mark.session_date: mark for mark in replay.daily_marks}
    held = {symbol: 0 for symbol in UNIVERSE}
    for target in replay.targets:
        mark = marks[target.signal_date]
        if mark.held_symbol is not None:
            held[mark.held_symbol] += 1
    entries = {symbol: 0 for symbol in UNIVERSE}
    for fill in replay.fills:
        if fill.side == "BUY":
            entries[fill.symbol] += 1
    return (
        tuple((symbol, held[symbol]) for symbol in UNIVERSE),
        tuple((symbol, entries[symbol]) for symbol in UNIVERSE),
    )


def _build_cost_case(replay: RotationReplay) -> CostCaseEvidence:
    yearly = tuple(
        _build_partition(replay, label, start, end, years)
        for label, start, end, years in _PARTITIONS[1:]
    )
    full = _build_partition(
        replay,
        "EXPLORATORY_FULL",
        REPORTING_START,
        REPORTING_END,
        7,
        annual_returns=tuple((item.label, item.net_return) for item in yearly),
    )
    partitions = (full, *yearly)
    return CostCaseEvidence(replay.costs, replay, partitions)


def _build_partition(
    replay: RotationReplay,
    label: str,
    start: date,
    end_exclusive: date,
    calendar_years: int,
    *,
    annual_returns: tuple[tuple[str, Decimal], ...] | None = None,
) -> PartitionDiagnostics:
    marks = tuple(
        mark
        for mark in replay.daily_marks
        if _date_in_window(mark.session_date, start, end_exclusive)
    )
    if not marks:
        raise MonthlyDefensiveRotationEvidenceError(
            "every frozen report partition must contain scoring marks"
        )
    prior = tuple(mark for mark in replay.daily_marks if mark.session_date < start)
    opening_equity = replay.initial_equity if not prior else prior[-1].equity
    targets = tuple(
        target
        for target in replay.targets
        if _date_in_window(target.signal_date, start, end_exclusive)
    )
    fills = tuple(
        fill
        for fill in replay.fills
        if _date_in_window(
            fill.timestamp.astimezone(_NEW_YORK).date(), start, end_exclusive
        )
    )
    action_targets = tuple(
        target
        for target in replay.targets
        if target.next_session is not None
        and _date_in_window(target.next_session, start, end_exclusive)
    )
    signal_count = sum(
        target.resolution is not TargetResolution.MISSING_INPUT for target in targets
    )
    missing_count = sum(
        target.resolution is TargetResolution.MISSING_INPUT for target in targets
    )
    rebalance_count = sum(
        target.resolution is TargetResolution.REBALANCED for target in action_targets
    )
    unchanged_count = sum(
        target.resolution is TargetResolution.UNCHANGED_TARGET
        for target in action_targets
    )
    insufficient_count = sum(
        target.resolution is TargetResolution.INSUFFICIENT_WHOLE_SHARES
        for target in action_targets
    )
    cash_target_count = sum(target.target == CASH for target in targets)
    switch_count = _switch_count(fills)
    with localcontext(DECIMAL_CONTEXT):
        turnover_notional = sum(
            (
                replay.fill_turnovers[index]
                for index, fill in enumerate(replay.fills)
                if _date_in_window(
                    fill.timestamp.astimezone(_NEW_YORK).date(), start, end_exclusive
                )
            ),
            Decimal(0),
        )
        average_equity = sum((mark.equity for mark in marks), Decimal(0)) / len(marks)
        turnover = turnover_notional / average_equity
        invested = Decimal(sum(mark.held_symbol is not None for mark in marks)) / len(
            marks
        )
        net_return = marks[-1].equity / opening_equity - Decimal(1)
        cagr = (marks[-1].equity / opening_equity) ** (
            Decimal(1) / Decimal(calendar_years)
        ) - Decimal(1)
        daily_returns: list[Decimal] = []
        previous_equity = opening_equity
        for mark in marks:
            daily_returns.append(mark.equity / previous_equity - Decimal(1))
            previous_equity = mark.equity
        volatility, sharpe = _daily_risk_statistics(tuple(daily_returns))
        drawdown = _maximum_drawdown(opening_equity, marks)
    if annual_returns is None:
        annual_returns = ((label, net_return),)
    month_held = {symbol: 0 for symbol in UNIVERSE}
    mark_by_date = {mark.session_date: mark for mark in marks}
    for target in targets:
        held_symbol = mark_by_date[target.signal_date].held_symbol
        if held_symbol is not None:
            month_held[held_symbol] += 1
    entry_counts = {symbol: 0 for symbol in UNIVERSE}
    for fill in fills:
        if fill.side == "BUY":
            entry_counts[fill.symbol] += 1
    target_identity = monthly_rotation_identity(
        "target-sequence", tuple(target.identity for target in targets)
    )
    trade_identity = monthly_rotation_identity(
        "trade-audit", tuple(fill.identity for fill in fills)
    )
    if label == "EXPLORATORY_FULL":
        daily_identity = replay.daily_equity_identity
        target_identity = replay.target_sequence_identity
        trade_identity = replay.trade_audit_identity
    else:
        daily_identity = monthly_rotation_identity(
            "partition-daily-equity-series",
            (
                label,
                start,
                end_exclusive,
                opening_equity,
                tuple(mark.identity_material for mark in marks),
            ),
        )
    return PartitionDiagnostics(
        label=label,
        start=start,
        end_exclusive=end_exclusive,
        opening_equity=opening_equity,
        final_equity=marks[-1].equity,
        net_return=net_return,
        cagr=cagr,
        maximum_drawdown=drawdown,
        annualized_volatility=volatility,
        sharpe_ratio=sharpe,
        annual_returns=annual_returns,
        month_end_signal_count=signal_count,
        missing_input_no_rebalance_count=missing_count,
        executable_rebalance_count=rebalance_count,
        unchanged_target_count=unchanged_count,
        cash_target_count=cash_target_count,
        etf_switch_count=switch_count,
        insufficient_whole_shares_count=insufficient_count,
        fill_count=len(fills),
        turnover_notional=turnover_notional,
        turnover=turnover,
        time_invested=invested,
        months_held=tuple((symbol, month_held[symbol]) for symbol in UNIVERSE),
        entry_count_by_symbol=tuple(
            (symbol, entry_counts[symbol]) for symbol in UNIVERSE
        ),
        target_sequence_identity=target_identity,
        trade_audit_identity=trade_identity,
        daily_equity_identity=daily_identity,
    )


def _switch_count(fills: tuple[RotationFill, ...]) -> int:
    by_timestamp: dict[datetime, list[RotationFill]] = defaultdict(list)
    for fill in fills:
        by_timestamp[fill.timestamp].append(fill)
    return sum(
        1
        for at_timestamp in by_timestamp.values()
        if any(fill.side == "SELL" for fill in at_timestamp)
        and any(fill.side == "BUY" for fill in at_timestamp)
        and len({fill.symbol for fill in at_timestamp}) > 1
    )


def _daily_risk_statistics(
    daily_returns: tuple[Decimal, ...],
) -> tuple[Decimal | None, Decimal | None]:
    if len(daily_returns) < 2:
        return None, None
    with localcontext(DECIMAL_CONTEXT):
        average = sum(daily_returns, Decimal(0)) / len(daily_returns)
        sum_squares = sum(
            ((value - average) ** 2 for value in daily_returns), Decimal(0)
        )
        standard_deviation = (sum_squares / Decimal(len(daily_returns) - 1)).sqrt()
        annual_factor = Decimal(252).sqrt()
        volatility = standard_deviation * annual_factor
        sharpe = (
            None
            if standard_deviation == 0
            else average / standard_deviation * annual_factor
        )
    return volatility, sharpe


def _maximum_drawdown(
    opening_equity: Decimal, marks: tuple[DailyEquityMark, ...]
) -> Decimal:
    with localcontext(DECIMAL_CONTEXT):
        peak = opening_equity
        largest = Decimal(0)
        for mark in marks:
            peak = max(peak, mark.equity)
            largest = max(largest, (peak - mark.equity) / peak)
    return largest


def _classify_stress(stress_full: PartitionDiagnostics) -> ExploratoryClassification:
    annual_returns = tuple(value for _, value in stress_full.annual_returns)
    if len(annual_returns) != 7:
        raise MonthlyDefensiveRotationEvidenceError(
            "STRESS classification requires all seven calendar-year returns"
        )
    ordered = tuple(sorted(annual_returns))
    median_annual_return = ordered[3]
    positive_years = sum(value > 0 for value in annual_returns)
    if (
        stress_full.net_return <= 0
        or median_annual_return <= 0
        or positive_years < 5
        or stress_full.maximum_drawdown > _STRESS_MAX_DRAWDOWN_LIMIT
    ):
        return ExploratoryClassification.ECONOMICALLY_REJECTED
    return ExploratoryClassification.EXPLORATORY_CANDIDATE_ONLY


def _passive_comparisons(dataset: MultiAssetDataset) -> tuple[PassiveComparison, ...]:
    first_session: date | None = None
    last_session: date | None = None
    selected: dict[str, tuple[Decimal, Decimal]] = {}
    for symbol in ("SPY", "QQQ"):
        scoring = tuple(
            bar
            for bar in dataset.bars_by_symbol[symbol]
            if REPORTING_START
            <= bar.timestamp.astimezone(_NEW_YORK).date()
            < REPORTING_END
        )
        if not scoring:
            raise MonthlyDefensiveRotationEvidenceError(
                "passive comparator requires the full scoring interval"
            )
        symbol_first = scoring[0].timestamp.astimezone(_NEW_YORK).date()
        symbol_last = scoring[-1].timestamp.astimezone(_NEW_YORK).date()
        if first_session is None:
            first_session, last_session = symbol_first, symbol_last
        elif (symbol_first, symbol_last) != (first_session, last_session):
            raise MonthlyDefensiveRotationEvidenceError(
                "passive comparators must share the scoring endpoints"
            )
        selected[symbol] = (scoring[0].open, scoring[-1].close)
    assert first_session is not None and last_session is not None
    with localcontext(DECIMAL_CONTEXT):
        return tuple(
            PassiveComparison(
                symbol=symbol,
                basis=PASSIVE_COMPARISON_BASIS,
                start_session=first_session,
                end_session=last_session,
                starting_open=selected[symbol][0],
                ending_close=selected[symbol][1],
                price_return=selected[symbol][1] / selected[symbol][0] - Decimal(1),
            )
            for symbol in ("SPY", "QQQ")
        )


def _same_signal_decisions(
    left: tuple[MonthlyTarget, ...], right: tuple[MonthlyTarget, ...]
) -> bool:
    return len(left) == len(right) and all(
        (
            a.signal_date,
            a.ranked_scores,
            a.target,
            a.next_session,
            a.missing_symbols,
        )
        == (
            b.signal_date,
            b.ranked_scores,
            b.target,
            b.next_session,
            b.missing_symbols,
        )
        for a, b in zip(left, right, strict=True)
    )


def _identity_passive(item: PassiveComparison) -> tuple[object, ...]:
    return (
        item.symbol,
        item.basis,
        item.start_session,
        item.end_session,
        item.starting_open,
        item.ending_close,
        item.price_return,
    )


def _is_sha_identity(value: str) -> bool:
    if type(value) is not str:
        return False
    try:
        from uuid import UUID

        parsed = UUID(value)
    except ValueError:
        return False
    return str(parsed) == value and parsed.version == 5


def _json_value(value: object) -> object:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is Decimal:
        if not value.is_finite():
            raise TypeError("nonfinite Decimal cannot be serialized")
        return format(value, "f")
    if isinstance(value, StrEnum):
        return value.value
    if type(value) is date:
        return value.isoformat()
    if type(value) is datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise TypeError("report timestamps must be timezone-aware")
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _json_value(getattr(value, item.name)) for item in fields(value)
        }
    if type(value) is tuple:
        return [_json_value(item) for item in value]
    raise TypeError(f"unsupported report value: {type(value).__name__}")
