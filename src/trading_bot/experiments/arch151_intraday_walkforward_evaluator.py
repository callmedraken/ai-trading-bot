"""Deterministic synthetic-testable execution evaluator for Architecture 151.

Import performs no reads. The evaluator accepts only an already source-owned
Arch150 D1R history object; it has no custody loader, acquisition, provider, or
protected-effect surface.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, localcontext
from enum import Enum, StrEnum
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID, uuid5

from trading_bot.experiments import arch150_intraday_data as arch150_data
from trading_bot.experiments import arch151_intraday_walkforward as arch151

type SourceHistory = arch151.Arch150D1RSourceHistory | arch151._SyntheticSourceHistory
type Signal = (
    arch151.NoiseBreakoutSignal
    | arch151.OpeningRangeRetestSignal
    | arch151.VwapMeanReversionSignal
    | arch151.TrendPullbackSignal
)

_NAMESPACE = uuid5(arch151.CANONICAL_MANIFEST.manifest_id, "arch151-evaluator/v1")
_FILL_NAMESPACE = uuid5(_NAMESPACE, "fill/v1")
_TRADE_NAMESPACE = uuid5(_NAMESPACE, "trade/v1")
_SIGNAL_NAMESPACE = uuid5(_NAMESPACE, "signal/v1")
_SIGNAL_OUTCOME_NAMESPACE = uuid5(_NAMESPACE, "signal-outcome/v1")
_SESSION_NAMESPACE = uuid5(_NAMESPACE, "session/v2")
_RESULT_NAMESPACE = uuid5(_NAMESPACE, "slot-year/v1")
_BENCHMARK_NAMESPACE = uuid5(_NAMESPACE, "passive-spy-benchmark/v1")
_DIAGNOSTICS_NAMESPACE = uuid5(_NAMESPACE, "research-diagnostics/v1")
_SOURCE_BINDING_NAMESPACE = uuid5(_NAMESPACE, "development-source-binding/v1")
_BATCH_NAMESPACE = uuid5(_NAMESPACE, "canonical-year-batch/v3")
_DEVELOPMENT_RUN_SCHEMA = "arch151-development-evaluation-run/v4"
_DEVELOPMENT_REPORT_SCHEMA = "arch151-development-evaluation-report/v3"
_DEVELOPMENT_RUN_NAMESPACE = uuid5(_NAMESPACE, "development-evaluation-run/v4")
_DEVELOPMENT_REPORT_NAMESPACE = uuid5(_DEVELOPMENT_RUN_NAMESPACE, "canonical-report/v3")
_SOURCE_BINDING_SEAL = object()
_CANONICAL_YEAR_BATCH_SEAL = object()
_DEVELOPMENT_RUN_SEAL = object()
_DEVELOPMENT_REPORT_SEAL = object()
_BPS = Decimal(10000)


class FillSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class ExitReason(StrEnum):
    STOP_GAP = "STOP_GAP"
    STOP_TOUCH = "STOP_TOUCH"
    TARGET_OPEN = "TARGET_OPEN"
    TARGET_TOUCH = "TARGET_TOUCH"
    VWAP_REVERSION = "VWAP_REVERSION"
    MAXIMUM_HOLD = "MAXIMUM_HOLD"
    SESSION_LIQUIDATION = "SESSION_LIQUIDATION"


class ReplayFailureKind(StrEnum):
    MANDATORY_LIQUIDATION_UNOBSERVED = "MANDATORY_LIQUIDATION_UNOBSERVED"
    CALIBRATION_UNAVAILABLE = "CALIBRATION_UNAVAILABLE"


class AnnualReplayOperationStage(StrEnum):
    FAMILY_A_CALIBRATION = "FAMILY_A_CALIBRATION"
    PROGRAM_FEATURE_PREPARATION = "PROGRAM_FEATURE_PREPARATION"
    SESSION_TAPE_PREPARATION = "SESSION_TAPE_PREPARATION"
    SESSION_EXECUTION = "SESSION_EXECUTION"
    SLOT_YEAR_AGGREGATION = "SLOT_YEAR_AGGREGATION"


@dataclass(frozen=True, slots=True)
class AnnualReplayFailureContext:
    scored_year: int
    program_id: UUID
    slot_id: UUID
    symbol: str
    cost_case: arch151.FillCostCase | None
    session_date: date | None
    operation_stage: AnnualReplayOperationStage


class AnnualReplayFailure(RuntimeError):
    """Unexpected annual-simulation failure with sanitized frozen context."""

    def __init__(self, context: AnnualReplayFailureContext) -> None:
        self.context = context
        super().__init__("annual replay failed")


class RejectionReason(StrEnum):
    NONPOSITIVE_INITIAL_R = "NONPOSITIVE_INITIAL_R"
    POSITION_ALREADY_OPEN = "POSITION_ALREADY_OPEN"
    SESSION_ENTRY_LIMIT = "SESSION_ENTRY_LIMIT"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    ENTRY_WINDOW_CLOSED = "ENTRY_WINDOW_CLOSED"
    LIQUIDATION_WINDOW = "LIQUIDATION_WINDOW"


class SignalDisposition(StrEnum):
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"


class BenchmarkStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class BenchmarkUnavailableReason(StrEnum):
    FIRST_SESSION_OPEN_UNOBSERVED = "FIRST_SESSION_OPEN_UNOBSERVED"
    LAST_SESSION_CLOSE_UNOBSERVED = "LAST_SESSION_CLOSE_UNOBSERVED"


class DiagnosticScope(StrEnum):
    SCORED_YEAR = "SCORED_YEAR"
    FIVE_YEAR_CAMPAIGN = "FIVE_YEAR_CAMPAIGN"


class CostPathRelationship(StrEnum):
    IDENTICAL_ENTRY_EXIT_PATH = "IDENTICAL_ENTRY_EXIT_PATH"
    ENTRY_EXIT_PATH_CHANGED = "ENTRY_EXIT_PATH_CHANGED"
    INCOMPLETE = "INCOMPLETE"


class DevelopmentSourceKind(StrEnum):
    """Distinguish accepted Arch150 provenance from private synthetic fixtures."""

    ARCH150_D1R_ACCEPTED = "ARCH150_D1R_ACCEPTED"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


@dataclass(frozen=True, slots=True, init=False)
class DevelopmentSourceBinding:
    """Source-issued identity material carried into batches and result reports."""

    kind: DevelopmentSourceKind
    source_digest: str
    source_id: UUID | None
    dataset_id: UUID | None
    dataset_sha256: str | None
    custody_id: UUID | None
    custody_sha256: str | None
    evidence_id: UUID | None
    evidence_sha256: str | None
    artifact_commitments: tuple[tuple[str, int, str], ...]
    binding_id: UUID
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        kind: DevelopmentSourceKind,
        source_digest: str,
        source_id: UUID | None = None,
        dataset_id: UUID | None = None,
        dataset_sha256: str | None = None,
        custody_id: UUID | None = None,
        custody_sha256: str | None = None,
        evidence_id: UUID | None = None,
        evidence_sha256: str | None = None,
        artifact_commitments: tuple[tuple[str, int, str], ...] = (),
    ) -> None:
        if _seal is not _SOURCE_BINDING_SEAL:
            raise arch151.AuthorizationUnavailableError(
                "development source binding must be issued by a source adapter"
            )
        if type(kind) is not DevelopmentSourceKind:
            raise TypeError("development source kind is invalid")
        if not arch151._is_sha256(source_digest):
            raise ValueError("development source digest is invalid")
        accepted_values = (
            source_id,
            dataset_id,
            dataset_sha256,
            custody_id,
            custody_sha256,
            evidence_id,
            evidence_sha256,
        )
        if kind is DevelopmentSourceKind.ARCH150_D1R_ACCEPTED:
            if (
                type(source_id) is not UUID
                or type(dataset_id) is not UUID
                or dataset_id != arch151.ARCH150_D1R_DATASET_ID
                or dataset_sha256 != arch151.ARCH150_D1R_DATASET_SHA256
                or custody_id != arch151.ARCH150_D1R_CUSTODY_ID
                or custody_sha256 != arch151.ARCH150_D1R_CUSTODY_SHA256
                or evidence_id != arch151.ARCH150_D1R_EVIDENCE_ID
                or evidence_sha256 != arch151.ARCH150_D1R_EVIDENCE_SHA256
                or any(value is None for value in accepted_values)
            ):
                raise arch151.AuthorizationUnavailableError(
                    "accepted source provenance differs from the pinned D1R identity"
                )
            if type(artifact_commitments) is not tuple or not artifact_commitments:
                raise ValueError("accepted source artifact commitments are required")
            for name, size, digest in artifact_commitments:
                if (
                    type(name) is not str
                    or not name
                    or type(size) is not int
                    or size < 0
                    or not arch151._is_sha256(digest)
                ):
                    raise ValueError("accepted source artifact commitment is invalid")
        elif (
            any(value is not None for value in accepted_values) or artifact_commitments
        ):
            raise arch151.AuthorizationUnavailableError(
                "synthetic source cannot carry accepted-custody provenance"
            )
        material = {
            "schema": "arch151-development-source-binding/v1",
            "kind": kind.value,
            "source_digest": source_digest,
            "source_id": str(source_id) if source_id is not None else None,
            "dataset_id": str(dataset_id) if dataset_id is not None else None,
            "dataset_sha256": dataset_sha256,
            "custody_id": str(custody_id) if custody_id is not None else None,
            "custody_sha256": custody_sha256,
            "evidence_id": str(evidence_id) if evidence_id is not None else None,
            "evidence_sha256": evidence_sha256,
            "artifact_commitments": [
                [name, size, digest] for name, size, digest in artifact_commitments
            ],
        }
        binding_id = _canonical_id(
            _SOURCE_BINDING_NAMESPACE, "arch151-development-source-binding/v1", material
        )
        for name, value in (
            ("kind", kind),
            ("source_digest", source_digest),
            ("source_id", source_id),
            ("dataset_id", dataset_id),
            ("dataset_sha256", dataset_sha256),
            ("custody_id", custody_id),
            ("custody_sha256", custody_sha256),
            ("evidence_id", evidence_id),
            ("evidence_sha256", evidence_sha256),
            ("artifact_commitments", artifact_commitments),
            ("binding_id", binding_id),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)

    def canonical_material(self) -> dict[str, object]:
        if self._seal is not _SOURCE_BINDING_SEAL:
            raise arch151.AuthorizationUnavailableError(
                "development source binding seal is invalid"
            )
        return {
            "kind": self.kind.value,
            "source_digest": self.source_digest,
            "source_id": str(self.source_id) if self.source_id is not None else None,
            "dataset_id": str(self.dataset_id) if self.dataset_id is not None else None,
            "dataset_sha256": self.dataset_sha256,
            "custody_id": str(self.custody_id) if self.custody_id is not None else None,
            "custody_sha256": self.custody_sha256,
            "evidence_id": str(self.evidence_id)
            if self.evidence_id is not None
            else None,
            "evidence_sha256": self.evidence_sha256,
            "artifact_commitments": [
                [name, size, digest] for name, size, digest in self.artifact_commitments
            ],
            "binding_id": str(self.binding_id),
        }


@dataclass(frozen=True, slots=True)
class FillRecord:
    fill_id: UUID
    side: FillSide
    timestamp: datetime
    reference_price: Decimal
    execution_price: Decimal
    quantity: Decimal
    adverse_cost: Decimal
    cash_before: Decimal
    cash_after: Decimal


@dataclass(frozen=True, slots=True)
class TradeRecord:
    trade_id: UUID
    slot_id: UUID
    program_id: UUID
    symbol: str
    session_date: date
    signal_timestamp: datetime
    entry: FillRecord
    exit: FillRecord
    exit_reason: ExitReason
    initial_stop_reference: Decimal
    final_stop_reference: Decimal
    target_reference: Decimal | None
    initial_risk: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    total_adverse_cost: Decimal
    equity_before: Decimal
    equity_after: Decimal
    gross_exposure_fraction: Decimal
    mfe_return: Decimal | None = None
    mae_return: Decimal | None = None
    excursion_minute_count: int = 0


@dataclass(frozen=True, slots=True)
class SignalRejection:
    signal_timestamp: datetime
    reason: RejectionReason


@dataclass(frozen=True, slots=True)
class SignalLifecycleOutcome:
    signal_id: UUID
    outcome_id: UUID
    signal_timestamp: datetime
    decision_timestamp: datetime
    scheduled_next_open: datetime
    entry_window_eligible: bool
    disposition: SignalDisposition
    blocked_reason: RejectionReason | None
    entry_fill_id: UUID | None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, SignalDisposition):
            raise TypeError("signal disposition must use the closed enum")
        if self.scheduled_next_open < self.decision_timestamp:
            raise ValueError("signal next open cannot precede its completed decision")
        if type(self.entry_window_eligible) is not bool:
            raise TypeError("signal eligibility must be boolean")
        if self.disposition is SignalDisposition.BLOCKED:
            if not isinstance(self.blocked_reason, RejectionReason):
                raise ValueError("blocked signal requires one typed rejection reason")
            if self.entry_fill_id is not None:
                raise ValueError("blocked signal cannot have an entry fill")
        elif self.blocked_reason is not None:
            raise ValueError("nonblocked signal cannot have a rejection reason")
        elif self.disposition is SignalDisposition.EXECUTED:
            if not isinstance(self.entry_fill_id, UUID):
                raise ValueError("executed signal requires its entry fill identity")
        elif self.entry_fill_id is not None:
            raise ValueError("expired signal cannot have an entry fill")


@dataclass(frozen=True, slots=True)
class ReplayFailureEvidence:
    failure_id: UUID
    kind: ReplayFailureKind
    session_date: date
    liquidation_boundary: datetime
    entry_signal_timestamp: datetime | None
    entry_fill: FillRecord | None
    quantity: Decimal | None
    initial_stop_reference: Decimal | None
    active_stop_reference: Decimal | None
    target_reference: Decimal | None
    pending_exit_reason: ExitReason | None
    last_observed_timestamp: datetime | None
    evidence_digest: str


@dataclass(frozen=True, slots=True)
class SessionReplayRecord:
    session_id: UUID
    session_date: date
    starting_equity: Decimal
    closing_equity: Decimal | None
    session_return: Decimal | None
    trades: tuple[TradeRecord, ...]
    fills: tuple[FillRecord, ...]
    expired_entry_timestamps: tuple[datetime, ...]
    signal_rejections: tuple[SignalRejection, ...]
    fill_notional: Decimal
    failure: ReplayFailureEvidence | None
    signal_outcomes: tuple[SignalLifecycleOutcome, ...] = ()

    def __post_init__(self) -> None:
        if type(self.signal_outcomes) is not tuple or any(
            not isinstance(item, SignalLifecycleOutcome)
            for item in self.signal_outcomes
        ):
            raise TypeError("session signal outcomes must be immutable typed records")
        if len({item.signal_id for item in self.signal_outcomes}) != len(
            self.signal_outcomes
        ):
            raise ValueError("session signal identities must be unique")
        expected_expired = tuple(
            item.scheduled_next_open
            for item in self.signal_outcomes
            if item.disposition is SignalDisposition.EXPIRED
        )
        if self.expired_entry_timestamps != expected_expired:
            raise ValueError("expired entry timestamps must match lifecycle outcomes")
        expected_rejections = tuple(
            SignalRejection(item.scheduled_next_open, item.blocked_reason)
            for item in self.signal_outcomes
            if item.disposition is SignalDisposition.BLOCKED
        )
        if self.signal_rejections != expected_rejections:
            raise ValueError("signal rejections must match blocked lifecycle outcomes")
        if not self.signal_lifecycle_reconciled:
            raise ValueError("signal terminal dispositions must reconcile to generated")

    @property
    def generated_signal_count(self) -> int:
        return len(self.signal_outcomes)

    @property
    def eligible_signal_count(self) -> int:
        return sum(item.entry_window_eligible for item in self.signal_outcomes)

    @property
    def executed_signal_count(self) -> int:
        return sum(
            item.disposition is SignalDisposition.EXECUTED
            for item in self.signal_outcomes
        )

    @property
    def expired_signal_count(self) -> int:
        return sum(
            item.disposition is SignalDisposition.EXPIRED
            for item in self.signal_outcomes
        )

    @property
    def blocked_signal_count(self) -> int:
        return sum(
            item.disposition is SignalDisposition.BLOCKED
            for item in self.signal_outcomes
        )

    @property
    def signal_lifecycle_reconciled(self) -> bool:
        return self.generated_signal_count == (
            self.executed_signal_count
            + self.expired_signal_count
            + self.blocked_signal_count
        )

    @property
    def completed_round_trips(self) -> int:
        return len(self.trades)

    @property
    def active(self) -> bool:
        return bool(self.trades)


@dataclass(frozen=True, slots=True)
class SlotYearReplay:
    replay_id: UUID
    slot: arch151.TrialSlot
    scored_year: int
    cost_case: arch151.FillCostCase
    source_digest: str
    sessions: tuple[SessionReplayRecord, ...]
    trades: tuple[TradeRecord, ...]
    complete: bool
    initial_equity: Decimal
    final_equity: Decimal | None
    net_return: Decimal | None
    positive_net_pnl: Decimal | None
    negative_net_pnl: Decimal | None
    gross_trade_pnl: Decimal | None
    total_adverse_cost: Decimal | None
    fill_notional: Decimal | None
    turnover: Decimal | None
    maximum_drawdown: Decimal | None
    failure: ReplayFailureEvidence | None

    @property
    def session_returns(self) -> tuple[tuple[date, Decimal | None], ...]:
        return tuple((item.session_date, item.session_return) for item in self.sessions)

    @property
    def completed_round_trips(self) -> int:
        return len(self.trades)

    @property
    def replay_digest(self) -> str:
        return sha256(
            arch151._canonical_json(_canonical_output_material(self))
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class NumericDistribution:
    count: int
    mean: Decimal | None
    median: Decimal | None
    minimum: Decimal | None
    first_quartile: Decimal | None
    third_quartile: Decimal | None
    maximum: Decimal | None


@dataclass(frozen=True, slots=True)
class MonthlyReturnDiagnostic:
    year: int
    month: int
    session_count: int
    complete: bool
    net_return: Decimal | None


@dataclass(frozen=True, slots=True)
class ExitReasonDiagnostic:
    reason: ExitReason
    trade_count: int
    gross_pnl: Decimal
    net_pnl: Decimal


@dataclass(frozen=True, slots=True)
class TradeDiagnostic:
    trade_id: UUID
    signal_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime
    exit_reason: ExitReason
    gross_pnl: Decimal
    net_pnl: Decimal
    adverse_cost: Decimal
    holding_minutes: Decimal
    mfe_return: Decimal | None
    mae_return: Decimal | None
    excursion_minute_count: int


@dataclass(frozen=True, slots=True)
class RejectionReasonDiagnostic:
    reason: RejectionReason
    count: int


@dataclass(frozen=True, slots=True)
class EconomicDiagnostic:
    diagnostic_id: UUID
    scope: DiagnosticScope
    slot_id: UUID
    program_id: UUID
    symbol: str
    scored_year: int | None
    cost_case: arch151.FillCostCase
    replay_ids: tuple[UUID, ...]
    complete: bool
    trade_count: int
    trades: tuple[TradeDiagnostic, ...]
    gross_trade_pnl: Decimal
    net_trade_pnl: Decimal
    total_adverse_cost: Decimal
    gross_trade_expectancy: Decimal | None
    net_trade_expectancy: Decimal | None
    net_win_rate: Decimal | None
    average_net_win: Decimal | None
    average_net_loss: Decimal | None
    net_payoff_ratio: Decimal | None
    compounded_net_return: Decimal | None
    monthly_returns: tuple[MonthlyReturnDiagnostic, ...]
    positive_month_count: int
    available_month_count: int
    positive_month_fraction: Decimal | None
    holding_minutes: NumericDistribution
    time_in_market_minutes: Decimal
    published_session_minutes: int
    time_in_market_fraction: Decimal | None
    exits_by_reason: tuple[ExitReasonDiagnostic, ...]
    generated_signals: int
    eligible_signals: int
    executed_signals: int
    expired_signals: int
    blocked_signals: int
    rejections_by_reason: tuple[RejectionReasonDiagnostic, ...]
    mfe_returns: NumericDistribution
    mae_returns: NumericDistribution


@dataclass(frozen=True, slots=True)
class CostDragDiagnostic:
    slot_id: UUID
    scored_year: int | None
    cost_case: arch151.FillCostCase
    reference_case: arch151.FillCostCase
    path_relationship: CostPathRelationship
    net_return_delta: Decimal | None
    adverse_cost_delta: Decimal | None


@dataclass(frozen=True, slots=True)
class PassiveBenchmarkYear:
    benchmark_id: UUID
    source_digest: str
    scored_year: int
    adjustment: str
    adjustment_semantics: str
    price_basis: str
    status: BenchmarkStatus
    unavailable_reason: BenchmarkUnavailableReason | None
    scheduled_session_count: int
    start_timestamp: datetime | None
    start_price: Decimal | None
    end_timestamp: datetime | None
    end_price: Decimal | None
    adjusted_price_return: Decimal | None

    def __post_init__(self) -> None:
        if (
            self.adjustment != arch150_data.ADJUSTMENT
            or self.adjustment_semantics != arch150_data.ADJUSTMENT_SEMANTICS
            or self.price_basis != arch150_data.PRICE_BASIS
        ):
            raise EvaluationIntegrityError(
                "SPY benchmark price basis is not source-owned"
            )
        if self.status is BenchmarkStatus.AVAILABLE:
            if (
                self.unavailable_reason is not None
                or self.start_timestamp is None
                or self.start_price is None
                or self.end_timestamp is None
                or self.end_price is None
                or self.adjusted_price_return is None
            ):
                raise EvaluationIntegrityError("available SPY benchmark is incomplete")
            with localcontext(arch151._DECIMAL_CONTEXT):
                expected_return = self.end_price / self.start_price - Decimal(1)
            if self.adjusted_price_return != expected_return:
                raise EvaluationIntegrityError(
                    "SPY benchmark return does not reconcile"
                )
        elif (
            self.status is not BenchmarkStatus.UNAVAILABLE
            or self.unavailable_reason is None
            or self.adjusted_price_return is not None
        ):
            raise EvaluationIntegrityError(
                "unavailable SPY benchmark must not be zero-filled"
            )


@dataclass(frozen=True, slots=True)
class PassiveBenchmarkCampaign:
    benchmark_id: UUID
    source_digest: str
    annual_benchmark_ids: tuple[UUID, ...]
    adjustment: str
    adjustment_semantics: str
    price_basis: str
    status: BenchmarkStatus
    unavailable_reason: BenchmarkUnavailableReason | None
    start_timestamp: datetime | None
    start_price: Decimal | None
    end_timestamp: datetime | None
    end_price: Decimal | None
    adjusted_price_return: Decimal | None

    def __post_init__(self) -> None:
        if (
            len(self.annual_benchmark_ids) != len(arch151.SCORED_YEARS)
            or self.adjustment != arch150_data.ADJUSTMENT
            or self.adjustment_semantics != arch150_data.ADJUSTMENT_SEMANTICS
            or self.price_basis != arch150_data.PRICE_BASIS
        ):
            raise EvaluationIntegrityError("campaign benchmark provenance is invalid")
        if self.status is BenchmarkStatus.AVAILABLE:
            if (
                self.unavailable_reason is not None
                or self.start_timestamp is None
                or self.start_price is None
                or self.end_timestamp is None
                or self.end_price is None
                or self.adjusted_price_return is None
            ):
                raise EvaluationIntegrityError("campaign benchmark is incomplete")
            with localcontext(arch151._DECIMAL_CONTEXT):
                expected_return = self.end_price / self.start_price - Decimal(1)
            if self.adjusted_price_return != expected_return:
                raise EvaluationIntegrityError(
                    "campaign benchmark return does not reconcile"
                )
        elif (
            self.status is not BenchmarkStatus.UNAVAILABLE
            or self.unavailable_reason is None
            or self.adjusted_price_return is not None
        ):
            raise EvaluationIntegrityError("campaign benchmark cannot be zero-filled")


@dataclass(frozen=True, slots=True)
class CanonicalYearBatch:
    batch_id: UUID
    scored_year: int
    manifest_id: UUID
    manifest_fingerprint: str
    source_digest: str
    evaluations: tuple[SlotYearReplay, ...]
    passive_spy_benchmark: PassiveBenchmarkYear
    source_binding: DevelopmentSourceBinding
    _seal: object

    def __post_init__(self) -> None:
        if self._seal is not _CANONICAL_YEAR_BATCH_SEAL:
            raise arch151.AuthorizationUnavailableError(
                "canonical year batches must be issued by the evaluator"
            )
        if (
            type(self.source_binding) is not DevelopmentSourceBinding
            or getattr(self.source_binding, "_seal", None) is not _SOURCE_BINDING_SEAL
            or self.source_binding.source_digest != self.source_digest
        ):
            raise EvaluationIntegrityError(
                "canonical year batch source binding is invalid"
            )
        if (
            type(self.passive_spy_benchmark) is not PassiveBenchmarkYear
            or self.passive_spy_benchmark.source_digest != self.source_digest
            or self.passive_spy_benchmark.scored_year != self.scored_year
            or self.passive_spy_benchmark.benchmark_id
            != _passive_benchmark_year_id(self.passive_spy_benchmark)
        ):
            raise EvaluationIntegrityError("canonical year batch benchmark is unbound")

    @property
    def complete(self) -> bool:
        return len(self.evaluations) == len(arch151.CANONICAL_SLOTS) * len(
            arch151.EVALUATION_ECONOMICS_ORDER
        ) and all(item.complete for item in self.evaluations)


class EvaluationIntegrityError(arch151.Arch151Error):
    """Evaluator output failed completeness or consistency checks."""


@dataclass(frozen=True, slots=True)
class DevelopmentEvaluationRun:
    """Composed 480-record five-fold population plus DSR/rank/freeze outputs."""

    run_id: UUID
    source_digest: str
    year_batches: tuple[CanonicalYearBatch, ...]
    slot_batches: tuple[arch151.DevelopmentEvaluationBatch, ...]
    qualifications: tuple[arch151.DevelopmentQualification, ...]
    selection_bias: arch151.SelectionBiasCalculation
    passive_spy_benchmark: PassiveBenchmarkCampaign
    ranking_order: tuple[UUID, ...]
    final_freeze: arch151.FinalCandidateFreeze
    source_binding: DevelopmentSourceBinding
    _seal: object

    def __post_init__(self) -> None:
        if self._seal is not _DEVELOPMENT_RUN_SEAL:
            raise arch151.AuthorizationUnavailableError(
                "development evaluation runs must be composed by the evaluator"
            )
        if (
            type(self.source_binding) is not DevelopmentSourceBinding
            or getattr(self.source_binding, "_seal", None) is not _SOURCE_BINDING_SEAL
            or self.source_digest != self.source_binding.source_digest
            or any(
                batch.source_binding != self.source_binding
                for batch in self.year_batches
            )
        ):
            raise EvaluationIntegrityError("development run source binding is invalid")
        if (
            tuple(item.scored_year for item in self.year_batches)
            != arch151.SCORED_YEARS
        ):
            raise EvaluationIntegrityError(
                "development run must contain all five folds"
            )
        expected_benchmark = _passive_benchmark_campaign(
            tuple(item.passive_spy_benchmark for item in self.year_batches)
        )
        if (
            type(self.passive_spy_benchmark) is not PassiveBenchmarkCampaign
            or self.passive_spy_benchmark.source_digest != self.source_digest
            or self.passive_spy_benchmark != expected_benchmark
        ):
            raise EvaluationIntegrityError("development run benchmark is not canonical")
        if len(self.slot_batches) != len(arch151.CANONICAL_SLOTS):
            raise EvaluationIntegrityError("development run must contain all 32 slots")
        if sum(len(item.records) for item in self.slot_batches) != 480:
            raise EvaluationIntegrityError(
                "development run must retain all 480 records"
            )
        if tuple(item.slot_id for item in self.slot_batches) != tuple(
            item.slot_id for item in arch151.CANONICAL_SLOTS
        ):
            raise EvaluationIntegrityError("development run slot order is noncanonical")
        if tuple(item.slot_id for item in self.qualifications) != tuple(
            item.slot_id for item in arch151.CANONICAL_SLOTS
        ):
            raise EvaluationIntegrityError(
                "development run qualification order is invalid"
            )
        expected_id = _development_run_id(
            self.source_binding,
            self.year_batches,
            self.slot_batches,
            self.selection_bias,
            self.qualifications,
            self.passive_spy_benchmark,
            self.ranking_order,
            self.final_freeze,
        )
        if self.run_id != expected_id:
            raise EvaluationIntegrityError(
                "development run identity differs from canonical outputs"
            )

    @property
    def fold_evaluation_count(self) -> int:
        return sum(len(item.records) for item in self.slot_batches)


@dataclass(frozen=True, slots=True, init=False)
class DevelopmentEvaluationReport:
    """Canonical in-memory report; it has no file-writing or holdout reader."""

    report_id: UUID
    run_id: UUID
    source_binding_id: UUID
    manifest_id: UUID
    manifest_fingerprint: str
    record_count: int
    canonical_json_bytes: bytes
    sha256: str
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        report_id: UUID,
        run_id: UUID,
        source_binding_id: UUID,
        manifest_id: UUID,
        manifest_fingerprint: str,
        record_count: int,
        canonical_json_bytes: bytes,
        sha256_digest: str,
    ) -> None:
        if _seal is not _DEVELOPMENT_REPORT_SEAL:
            raise arch151.AuthorizationUnavailableError(
                "development reports must be serialized from a composed evaluator run"
            )
        if (
            type(report_id) is not UUID
            or type(run_id) is not UUID
            or type(source_binding_id) is not UUID
            or manifest_id != arch151.CANONICAL_MANIFEST.manifest_id
            or manifest_fingerprint != arch151.CANONICAL_MANIFEST.fingerprint
            or record_count != 480
            or type(canonical_json_bytes) is not bytes
            or sha256(canonical_json_bytes).hexdigest() != sha256_digest
        ):
            raise EvaluationIntegrityError("development report identity is invalid")
        expected_id = _canonical_id(
            _DEVELOPMENT_REPORT_NAMESPACE,
            _DEVELOPMENT_REPORT_SCHEMA,
            {"run_id": str(run_id), "sha256": sha256_digest},
        )
        if report_id != expected_id:
            raise EvaluationIntegrityError("development report ID is not canonical")
        for name, value in (
            ("report_id", report_id),
            ("run_id", run_id),
            ("source_binding_id", source_binding_id),
            ("manifest_id", manifest_id),
            ("manifest_fingerprint", manifest_fingerprint),
            ("record_count", record_count),
            ("canonical_json_bytes", canonical_json_bytes),
            ("sha256", sha256_digest),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class _EntryIntent:
    signal: Signal
    signal_timestamp: datetime
    completed_at: datetime
    family_a_calibration: arch151.FamilyACalibration | None = None
    family_a_current_measure: arch151.FamilyASessionMeasure | None = None


@dataclass(frozen=True, slots=True)
class _PendingExit:
    reason: ExitReason
    decision_timestamp: datetime


@dataclass(slots=True)
class _Position:
    intent: _EntryIntent
    entry_fill: FillRecord
    entry_reference: Decimal
    quantity: Decimal
    initial_stop: Decimal
    active_stop: Decimal
    initial_risk: Decimal
    target: Decimal | None
    frozen_atr: Decimal | None
    entry_sigma: Decimal | None
    favorable_high: Decimal
    max_hold_at: datetime
    cash_after_entry: Decimal


@dataclass(frozen=True, slots=True)
class _SessionTape:
    features: arch151.PreparedSessionFeatures
    confirming_features: arch151.PreparedSessionFeatures | None
    evidence: object
    confirming_evidence: object | None
    entry_intents: Mapping[datetime, _EntryIntent]
    observation_by_completed_at: Mapping[datetime, arch151.VwapObservation]
    aggregate_by_completed_at: Mapping[datetime, arch151.AggregateBar]


class _PreparationCache:
    def __init__(self, history: SourceHistory) -> None:
        self.history = history
        self._features: dict[
            tuple[UUID, str, date], arch151.PreparedSessionFeatures | None
        ] = {}

    def features(
        self, program: arch151.Arch151Program, symbol: str, session: date
    ) -> arch151.PreparedSessionFeatures | None:
        key = (arch151.program_id(program), symbol, session)
        if key in self._features:
            return self._features[key]
        if not arch151._source_history_digest(self.history):
            raise arch151.AuthorizationUnavailableError("source history is unbound")
        if (
            self.history._projection_index.get((symbol, session, program.resolution))
            is None
        ):
            self._features[key] = None
            return None
        schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
        if schedule is None:
            raise arch151.Arch151Error("replay date is not a published XNYS session")
        features = arch151.prepare_session_features(
            self.history,
            program,
            symbol,
            session,
            schedule.closes_at.astimezone(UTC),
        )
        self._features[key] = features
        return features

    def evidence(
        self,
        symbol: str,
        session: date,
        resolution: arch151.BarResolution,
    ) -> object | None:
        projection = self.history._projection_index.get((symbol, session, resolution))
        if projection is None:
            return None
        return next(
            item
            for item in projection.verified_sessions
            if item.resolution is resolution
        )


class _FamilyACalibrationCache:
    """Reuse symbol/year source measures across A parameter variants."""

    def __init__(self, history: SourceHistory) -> None:
        self.history = history
        self.source_digest = _history_digest(history)
        self._measures: dict[
            tuple[str, str, int], tuple[arch151.FamilyASessionMeasure, ...]
        ] = {}
        self._calibrations: dict[
            tuple[str, UUID, str, int], arch151.FamilyACalibration
        ] = {}

    def calibration(
        self,
        program: arch151.Arch151Program,
        symbol: str,
        scored_year: int,
    ) -> arch151.FamilyACalibration:
        measure_key = (self.source_digest, symbol, scored_year)
        if measure_key not in self._measures:
            self._measures[measure_key] = (
                arch151._family_a_historical_measures_from_source_history(
                    self.history, symbol, scored_year
                )
            )
        calibration_key = (
            self.source_digest,
            arch151.program_id(program),
            symbol,
            scored_year,
        )
        if calibration_key not in self._calibrations:
            self._calibrations[calibration_key] = arch151.calibrate_family_a(
                program, self._measures[measure_key], scored_year
            )
        return self._calibrations[calibration_key]


def _canonical_id(namespace: UUID, schema: str, material: object) -> UUID:
    canonical = arch151._canonical_json({"schema": schema, "material": material})
    return uuid5(namespace, canonical.decode("utf-8"))


def _canonical_output_material(value: object) -> object:
    """Normalize immutable evaluator records without paths or ambient context."""

    if type(value) is Decimal:
        return arch151._decimal_text(value)
    if type(value) is UUID:
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise EvaluationIntegrityError("evaluator output has a naive timestamp")
        return value.astimezone(UTC).isoformat()
    if type(value) is date:
        return value.isoformat()
    if type(value) is time:
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _canonical_output_material(getattr(value, item.name))
            for item in fields(value)
            if not item.name.startswith("_")
        }
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_output_material(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if type(value) in (tuple, list):
        return [_canonical_output_material(item) for item in value]
    if value is None or type(value) in (bool, int, str):
        return value
    raise TypeError(f"unsupported canonical evaluator output: {type(value).__name__}")


def _passive_benchmark_year_material(record: PassiveBenchmarkYear) -> dict[str, object]:
    return {
        "schema": "arch151-passive-spy-year-benchmark/v1",
        "source_digest": record.source_digest,
        "scored_year": record.scored_year,
        "adjustment": record.adjustment,
        "adjustment_semantics": record.adjustment_semantics,
        "price_basis": record.price_basis,
        "status": record.status.value,
        "unavailable_reason": (
            record.unavailable_reason.value
            if record.unavailable_reason is not None
            else None
        ),
        "scheduled_session_count": record.scheduled_session_count,
        "start_timestamp": (
            record.start_timestamp.astimezone(UTC).isoformat()
            if record.start_timestamp is not None
            else None
        ),
        "start_price": (
            arch151._decimal_text(record.start_price)
            if record.start_price is not None
            else None
        ),
        "end_timestamp": (
            record.end_timestamp.astimezone(UTC).isoformat()
            if record.end_timestamp is not None
            else None
        ),
        "end_price": (
            arch151._decimal_text(record.end_price)
            if record.end_price is not None
            else None
        ),
        "adjusted_price_return": (
            arch151._decimal_text(record.adjusted_price_return)
            if record.adjusted_price_return is not None
            else None
        ),
    }


def _passive_benchmark_year_id(record: PassiveBenchmarkYear) -> UUID:
    return _canonical_id(
        _BENCHMARK_NAMESPACE,
        "arch151-passive-spy-year-benchmark/v1",
        _passive_benchmark_year_material(record),
    )


def _passive_benchmark_campaign_material(
    record: PassiveBenchmarkCampaign,
) -> dict[str, object]:
    return {
        "schema": "arch151-passive-spy-campaign-benchmark/v1",
        "source_digest": record.source_digest,
        "annual_benchmark_ids": [str(item) for item in record.annual_benchmark_ids],
        "adjustment": record.adjustment,
        "adjustment_semantics": record.adjustment_semantics,
        "price_basis": record.price_basis,
        "status": record.status.value,
        "unavailable_reason": (
            record.unavailable_reason.value
            if record.unavailable_reason is not None
            else None
        ),
        "start_timestamp": (
            record.start_timestamp.astimezone(UTC).isoformat()
            if record.start_timestamp is not None
            else None
        ),
        "start_price": (
            arch151._decimal_text(record.start_price)
            if record.start_price is not None
            else None
        ),
        "end_timestamp": (
            record.end_timestamp.astimezone(UTC).isoformat()
            if record.end_timestamp is not None
            else None
        ),
        "end_price": (
            arch151._decimal_text(record.end_price)
            if record.end_price is not None
            else None
        ),
        "adjusted_price_return": (
            arch151._decimal_text(record.adjusted_price_return)
            if record.adjusted_price_return is not None
            else None
        ),
    }


def _passive_benchmark_campaign_id(record: PassiveBenchmarkCampaign) -> UUID:
    return _canonical_id(
        _BENCHMARK_NAMESPACE,
        "arch151-passive-spy-campaign-benchmark/v1",
        _passive_benchmark_campaign_material(record),
    )


def _passive_benchmark_year(
    history: SourceHistory, scored_year: int
) -> PassiveBenchmarkYear:
    sessions = arch151._published_sessions_for_year(scored_year)
    if not sessions:
        raise EvaluationIntegrityError("SPY benchmark year has no published sessions")
    first_date, last_date = sessions[0], sessions[-1]
    first_schedule = arch151._SESSION_AUTHORITY.schedule_for(first_date)
    last_schedule = arch151._SESSION_AUTHORITY.schedule_for(last_date)
    if first_schedule is None or last_schedule is None:
        raise EvaluationIntegrityError("SPY benchmark schedule is unavailable")
    first_open = first_schedule.opens_at.astimezone(UTC)
    final_minute = last_schedule.closes_at.astimezone(UTC) - timedelta(minutes=1)
    first_projection = next(
        (
            projection
            for projection in history._session_projections
            if projection.symbol == "SPY" and projection.session_date == first_date
        ),
        None,
    )
    last_projection = next(
        (
            projection
            for projection in history._session_projections
            if projection.symbol == "SPY" and projection.session_date == last_date
        ),
        None,
    )
    start_bar = next(
        (
            item
            for item in (first_projection.minutes if first_projection else ())
            if item.timestamp == first_open
        ),
        None,
    )
    end_bar = next(
        (
            item
            for item in (last_projection.minutes if last_projection else ())
            if item.timestamp == final_minute
        ),
        None,
    )
    reason = (
        BenchmarkUnavailableReason.FIRST_SESSION_OPEN_UNOBSERVED
        if start_bar is None
        else (
            BenchmarkUnavailableReason.LAST_SESSION_CLOSE_UNOBSERVED
            if end_bar is None
            else None
        )
    )
    if reason is None:
        status = BenchmarkStatus.AVAILABLE
        start_timestamp = start_bar.timestamp
        start_price = start_bar.open
        end_timestamp = end_bar.completed_at
        end_price = end_bar.close
        with localcontext(arch151._DECIMAL_CONTEXT):
            adjusted_return = end_price / start_price - Decimal(1)
    else:
        status = BenchmarkStatus.UNAVAILABLE
        start_timestamp = start_bar.timestamp if start_bar is not None else None
        start_price = start_bar.open if start_bar is not None else None
        end_timestamp = end_bar.completed_at if end_bar is not None else None
        end_price = end_bar.close if end_bar is not None else None
        adjusted_return = None
    provisional = PassiveBenchmarkYear(
        UUID(int=0),
        _history_digest(history),
        scored_year,
        arch150_data.ADJUSTMENT,
        arch150_data.ADJUSTMENT_SEMANTICS,
        arch150_data.PRICE_BASIS,
        status,
        reason,
        len(sessions),
        start_timestamp,
        start_price,
        end_timestamp,
        end_price,
        adjusted_return,
    )
    return replace(provisional, benchmark_id=_passive_benchmark_year_id(provisional))


def _passive_benchmark_campaign(
    benchmarks: tuple[PassiveBenchmarkYear, ...],
) -> PassiveBenchmarkCampaign:
    if (
        type(benchmarks) is not tuple
        or tuple(item.scored_year for item in benchmarks) != arch151.SCORED_YEARS
        or len({item.source_digest for item in benchmarks}) != 1
        or any(
            item.benchmark_id != _passive_benchmark_year_id(item) for item in benchmarks
        )
    ):
        raise EvaluationIntegrityError("campaign SPY benchmarks are not canonical")
    first, last = benchmarks[0], benchmarks[-1]
    if first.start_price is None:
        status = BenchmarkStatus.UNAVAILABLE
        reason = BenchmarkUnavailableReason.FIRST_SESSION_OPEN_UNOBSERVED
        start_timestamp = start_price = None
    elif last.end_price is None:
        status = BenchmarkStatus.UNAVAILABLE
        reason = BenchmarkUnavailableReason.LAST_SESSION_CLOSE_UNOBSERVED
        start_timestamp = first.start_timestamp
        start_price = first.start_price
    else:
        status = BenchmarkStatus.AVAILABLE
        reason = None
        start_timestamp = first.start_timestamp
        start_price = first.start_price
    if status is BenchmarkStatus.AVAILABLE:
        end_timestamp = last.end_timestamp
        end_price = last.end_price
        assert start_price is not None and end_price is not None
        with localcontext(arch151._DECIMAL_CONTEXT):
            adjusted_return = end_price / start_price - Decimal(1)
    else:
        end_timestamp = last.end_timestamp
        end_price = last.end_price
        adjusted_return = None
    provisional = PassiveBenchmarkCampaign(
        UUID(int=0),
        benchmarks[0].source_digest,
        tuple(item.benchmark_id for item in benchmarks),
        arch150_data.ADJUSTMENT,
        arch150_data.ADJUSTMENT_SEMANTICS,
        arch150_data.PRICE_BASIS,
        status,
        reason,
        start_timestamp,
        start_price,
        end_timestamp,
        end_price,
        adjusted_return,
    )
    return replace(
        provisional,
        benchmark_id=_passive_benchmark_campaign_id(provisional),
    )


def _synthetic_passive_benchmark_for_test(
    source_digest: str,
    scored_year: int,
    *,
    start_price: Decimal | None = Decimal("100"),
    end_price: Decimal | None = Decimal("110"),
    unavailable_reason: BenchmarkUnavailableReason | None = None,
) -> PassiveBenchmarkYear:
    """Private seam for report-composition tests; never grants source authority."""

    sessions = arch151._published_sessions_for_year(scored_year)
    first_schedule = arch151._SESSION_AUTHORITY.schedule_for(sessions[0])
    last_schedule = arch151._SESSION_AUTHORITY.schedule_for(sessions[-1])
    assert first_schedule is not None and last_schedule is not None
    if unavailable_reason is None:
        if start_price is None or end_price is None:
            raise ValueError("available synthetic benchmark requires both endpoints")
        status = BenchmarkStatus.AVAILABLE
        start_timestamp = first_schedule.opens_at.astimezone(UTC)
        end_timestamp = last_schedule.closes_at.astimezone(UTC)
        with localcontext(arch151._DECIMAL_CONTEXT):
            adjusted_return = end_price / start_price - Decimal(1)
    else:
        status = BenchmarkStatus.UNAVAILABLE
        adjusted_return = None
        start_timestamp = (
            first_schedule.opens_at.astimezone(UTC) if start_price is not None else None
        )
        end_timestamp = (
            last_schedule.closes_at.astimezone(UTC) if end_price is not None else None
        )
    provisional = PassiveBenchmarkYear(
        UUID(int=0),
        source_digest,
        scored_year,
        arch150_data.ADJUSTMENT,
        arch150_data.ADJUSTMENT_SEMANTICS,
        arch150_data.PRICE_BASIS,
        status,
        unavailable_reason,
        len(sessions),
        start_timestamp,
        start_price,
        end_timestamp,
        end_price,
        adjusted_return,
    )
    return replace(provisional, benchmark_id=_passive_benchmark_year_id(provisional))


def _history_digest(history: SourceHistory) -> str:
    if type(history) not in (
        arch151.Arch150D1RSourceHistory,
        arch151._SyntheticSourceHistory,
    ):
        raise arch151.AuthorizationUnavailableError(
            "replay requires source-owned Arch150 or synthetic history"
        )
    return arch151._source_history_digest(history)


def _development_source_binding(
    history: SourceHistory,
) -> DevelopmentSourceBinding:
    """Bind a year batch to accepted Arch150 identity or test-only provenance."""

    source_digest = _history_digest(history)
    if type(history) is arch151.Arch150D1RSourceHistory:
        return DevelopmentSourceBinding(
            _seal=_SOURCE_BINDING_SEAL,
            kind=DevelopmentSourceKind.ARCH150_D1R_ACCEPTED,
            source_digest=source_digest,
            source_id=history.source_id,
            dataset_id=history.dataset_id,
            dataset_sha256=history.dataset_sha256,
            custody_id=history.custody_id,
            custody_sha256=history.custody_sha256,
            evidence_id=history.evidence_id,
            evidence_sha256=history.evidence_sha256,
            artifact_commitments=history.artifact_commitments,
        )
    return DevelopmentSourceBinding(
        _seal=_SOURCE_BINDING_SEAL,
        kind=DevelopmentSourceKind.SYNTHETIC_TEST_ONLY,
        source_digest=source_digest,
    )


def _synthetic_source_binding_for_test(source_digest: str) -> DevelopmentSourceBinding:
    """Private fixture seam; synthetic provenance never impersonates custody."""

    if not arch151._is_sha256(source_digest):
        raise ValueError("synthetic source digest must be lowercase SHA-256")
    return DevelopmentSourceBinding(
        _seal=_SOURCE_BINDING_SEAL,
        kind=DevelopmentSourceKind.SYNTHETIC_TEST_ONLY,
        source_digest=source_digest,
    )


def _canonical_year_batch_id(
    source_binding: DevelopmentSourceBinding,
    scored_year: int,
    evaluations: tuple[SlotYearReplay, ...],
    passive_spy_benchmark: PassiveBenchmarkYear,
) -> UUID:
    material = {
        "schema": "arch151-canonical-year-batch/v3",
        "source_binding_id": str(source_binding.binding_id),
        "source_digest": source_binding.source_digest,
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "scored_year": scored_year,
        "replay_outputs": [
            {"replay_id": str(item.replay_id), "replay_digest": item.replay_digest}
            for item in evaluations
        ],
        "passive_spy_benchmark_id": str(passive_spy_benchmark.benchmark_id),
    }
    return _canonical_id(_BATCH_NAMESPACE, "arch151-canonical-year-batch/v3", material)


def _slot_program(slot: arch151.TrialSlot) -> arch151.Arch151Program:
    if not arch151.validate_slot(slot):
        raise arch151.Arch151Error("replay slot is not in the canonical manifest")
    program = arch151._program_by_key(slot.program_key)
    if (
        program is None
        or arch151.program_id(program) != slot.program_id
        or arch151.program_fingerprint(program) != slot.program_fingerprint
        or program.resolution is not slot.resolution
    ):
        raise arch151.Arch151Error("replay slot identity differs from its program")
    return program


def _cost_policy(case: arch151.FillCostCase) -> arch151.FillCostPolicy:
    if type(case) is not arch151.FillCostCase:
        raise TypeError("cost case must be a canonical FillCostCase")
    return next(item for item in arch151.FILL_COST_POLICIES if item.case is case)


def _window_allows(program: arch151.Arch151Program, timestamp: datetime) -> bool:
    return program.entry_window.contains(timestamp)


def _source_evidence(
    cache: _PreparationCache,
    symbol: str,
    session: date,
    resolution: arch151.BarResolution,
) -> object:
    evidence = cache.evidence(symbol, session, resolution)
    if evidence is None:
        raise arch151.AuthorizationUnavailableError(
            "source projection lacks verified sparse-session evidence"
        )
    return evidence


def _signal_completion_time(
    signal: Signal, bars_by_timestamp: Mapping[datetime, arch151.AggregateBar]
) -> datetime:
    if type(signal) is arch151.NoiseBreakoutSignal:
        signal_bar = bars_by_timestamp[signal.confirmation_timestamps[-1]]
        return signal_bar.completed_at
    if type(signal) is arch151.OpeningRangeRetestSignal:
        return signal.signal_timestamp.astimezone(UTC)
    signal_bar = bars_by_timestamp[signal.signal_timestamp]
    return signal_bar.completed_at


def _signal_timestamp(signal: Signal) -> datetime:
    if type(signal) is arch151.NoiseBreakoutSignal:
        return signal.confirmation_timestamps[-1].astimezone(UTC)
    return signal.signal_timestamp.astimezone(UTC)


def _session_tape(
    history: SourceHistory,
    cache: _PreparationCache,
    program: arch151.Arch151Program,
    symbol: str,
    session: date,
    calibration: arch151.FamilyACalibration | None,
) -> _SessionTape | None:
    features = cache.features(program, symbol, session)
    if features is None:
        return None
    bars = features.bars
    observations = features.vwap_observations
    if tuple(item.bar for item in observations) != bars:
        raise arch151.Arch151Error("session replay features are not bar aligned")
    evidence = _source_evidence(cache, symbol, session, program.resolution)
    confirming_features = None
    confirming_evidence = None
    confirming_symbol = None
    if program.family is arch151.StrategyFamily.CROSS_ETF_TREND_PULLBACK:
        confirming_symbol = next(
            item for item in arch151.INITIAL_UNIVERSE if item != symbol
        )
        confirming_features = cache.features(program, confirming_symbol, session)
        if confirming_features is not None:
            confirming_evidence = _source_evidence(
                cache, confirming_symbol, session, program.resolution
            )

    intents: dict[datetime, _EntryIntent] = {}
    bars_by_timestamp = {bar.timestamp: bar for bar in bars}
    schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
    if schedule is None:
        raise arch151.Arch151Error("replay session is not published by XNYS")
    current_measure: arch151.FamilyASessionMeasure | None = None
    if program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT:
        try:
            current_measure = arch151.family_a_current_measure_from_source_history(
                history, symbol, session
            )
        except arch151.UnavailableIndicatorError:
            current_measure = None

    for index, bar in enumerate(bars):
        decision_at = bar.completed_at
        if not _window_allows(program, decision_at):
            continue
        signal: Signal | None = None
        try:
            if program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT:
                parameters = program.parameters
                assert type(parameters) is arch151.NoiseBreakoutParameters
                if calibration is None or current_measure is None:
                    continue
                if decision_at < schedule.opens_at.astimezone(UTC) + timedelta(
                    minutes=30
                ):
                    continue
                count = parameters.confirmation_bars
                if index + 1 < count:
                    continue
                signal = arch151.family_a_entry_signal(
                    program,
                    calibration,
                    current_measure,
                    observations[index + 1 - count : index + 1],
                )
            elif program.family is arch151.StrategyFamily.OPENING_RANGE_RETEST:
                if not bars or bars[0].timestamp != schedule.opens_at.astimezone(UTC):
                    break
                signal = arch151.family_b_entry_signal(program, bars[: index + 1])
            elif program.family is arch151.StrategyFamily.VWAP_MEAN_REVERSION:
                parameters = program.parameters
                assert type(parameters) is arch151.VwapMeanReversionParameters
                needed = max(
                    parameters.deviation_lookback_bars,
                    parameters.efficiency_ratio_lookback,
                )
                if index < needed:
                    continue
                signal = arch151.family_c_entry_signal(
                    program,
                    observations[index - needed : index],
                    observations[index],
                    verified_session=evidence,
                )
            else:
                if confirming_features is None or confirming_evidence is None:
                    continue
                confirming_index = next(
                    (
                        offset
                        for offset, other_bar in enumerate(confirming_features.bars)
                        if other_bar.timestamp == bar.timestamp
                    ),
                    None,
                )
                if confirming_index is None:
                    continue
                signal = arch151.family_d_entry_signal(
                    program,
                    bars[: index + 1],
                    confirming_features.bars[: confirming_index + 1],
                    confirming_features.vwap_observations[: confirming_index + 1],
                    target_session=evidence,
                    confirming_session=confirming_evidence,
                )
        except arch151.UnavailableIndicatorError:
            continue
        if signal is None:
            continue
        completed_at = _signal_completion_time(signal, bars_by_timestamp)
        if completed_at != decision_at:
            raise arch151.Arch151Error(
                "family predicate emitted a stale or noncurrent decision signal"
            )
        if completed_at >= schedule.closes_at.astimezone(UTC) - timedelta(minutes=5):
            continue
        intents[completed_at] = _EntryIntent(
            signal,
            _signal_timestamp(signal),
            completed_at,
            calibration if type(signal) is arch151.NoiseBreakoutSignal else None,
            current_measure if type(signal) is arch151.NoiseBreakoutSignal else None,
        )

    aggregate_by_completed = {bar.completed_at: bar for bar in bars}
    observation_by_completed = {
        observation.bar.completed_at: observation for observation in observations
    }
    return _SessionTape(
        features,
        confirming_features,
        evidence,
        confirming_evidence,
        MappingProxyType(intents),
        MappingProxyType(observation_by_completed),
        MappingProxyType(aggregate_by_completed),
    )


def _execution_price(
    reference_price: Decimal, side: FillSide, policy: arch151.FillCostPolicy
) -> tuple[Decimal, Decimal]:
    with localcontext(arch151._DECIMAL_CONTEXT):
        fraction = policy.adverse_slippage_bps_per_fill / _BPS
        execution = reference_price * (
            Decimal(1) + fraction if side is FillSide.BUY else Decimal(1) - fraction
        )
        cost = abs(execution - reference_price)
    if execution <= 0 or not execution.is_finite() or not cost.is_finite():
        raise arch151.UnavailableIndicatorError("adverse fill price is invalid")
    return execution, cost


def _make_fill(
    *,
    source_digest: str,
    slot: arch151.TrialSlot,
    session: date,
    case: arch151.FillCostCase,
    ordinal: int,
    side: FillSide,
    timestamp: datetime,
    reference_price: Decimal,
    quantity: Decimal,
    cash_before: Decimal,
    policy: arch151.FillCostPolicy,
) -> FillRecord:
    execution_price, cost_per_share = _execution_price(reference_price, side, policy)
    with localcontext(arch151._DECIMAL_CONTEXT):
        adverse_cost = quantity * cost_per_share
        notional = quantity * execution_price
        cash_after = (
            cash_before - notional if side is FillSide.BUY else cash_before + notional
        )
    material = {
        "source_digest": source_digest,
        "slot_id": str(slot.slot_id),
        "session": session.isoformat(),
        "cost_case": case.value,
        "ordinal": ordinal,
        "side": side.value,
        "timestamp": timestamp.astimezone(UTC).isoformat(timespec="minutes"),
        "reference_price": arch151._decimal_text(reference_price),
        "execution_price": arch151._decimal_text(execution_price),
        "quantity": arch151._decimal_text(quantity),
    }
    return FillRecord(
        _canonical_id(_FILL_NAMESPACE, "arch151-fill/v1", material),
        side,
        timestamp.astimezone(UTC),
        reference_price,
        execution_price,
        quantity,
        adverse_cost,
        cash_before,
        cash_after,
    )


def _initial_risk(
    program: arch151.Arch151Program,
    intent: _EntryIntent,
    entry_reference: Decimal,
) -> tuple[Decimal, Decimal, Decimal | None, Decimal | None, Decimal | None]:
    signal = intent.signal
    target: Decimal | None = None
    frozen_atr: Decimal | None = None
    entry_sigma: Decimal | None = None
    if type(signal) is arch151.NoiseBreakoutSignal:
        if (
            intent.family_a_calibration is None
            or intent.family_a_current_measure is None
        ):
            raise arch151.AuthorizationUnavailableError(
                "Family A entry lacks source-owned calibration inputs"
            )
        risk = arch151.family_a_initial_risk(
            program,
            intent.family_a_calibration,
            intent.family_a_current_measure,
            entry_reference,
        )
        stop = risk.stop_reference_price
        initial_risk = risk.risk_distance
    elif type(signal) is arch151.OpeningRangeRetestSignal:
        stop = signal.stop_reference_price
        with localcontext(arch151._DECIMAL_CONTEXT):
            initial_risk = entry_reference - stop
            if initial_risk > 0:
                target = entry_reference + signal.target_r * initial_risk
    elif type(signal) is arch151.VwapMeanReversionSignal:
        parameters = program.parameters
        assert type(parameters) is arch151.VwapMeanReversionParameters
        entry_sigma = signal.frozen_entry_sigma
        initial_risk = arch151.vwap_sigma_stop_distance(
            entry_reference,
            entry_sigma,
            parameters.stop_sigma_multiplier,
        )
        with localcontext(arch151._DECIMAL_CONTEXT):
            stop = entry_reference - initial_risk
    else:
        stop = signal.stop_reference_price
        with localcontext(arch151._DECIMAL_CONTEXT):
            initial_risk = entry_reference - stop
        frozen_atr = signal.frozen_atr
    if (
        not entry_reference.is_finite()
        or not stop.is_finite()
        or not initial_risk.is_finite()
        or entry_reference <= 0
        or stop <= 0
        or initial_risk <= 0
        or (target is not None and target <= entry_reference)
    ):
        raise arch151.UnavailableIndicatorError("entry has nonpositive initial R")
    return stop, initial_risk, target, frozen_atr, entry_sigma


def _entry_position(
    *,
    history_digest: str,
    slot: arch151.TrialSlot,
    program: arch151.Arch151Program,
    intent: _EntryIntent,
    minute: arch151.OneMinuteBar,
    cash: Decimal,
    case: arch151.FillCostCase,
    policy: arch151.FillCostPolicy,
    fill_ordinal: int,
) -> tuple[_Position, Decimal, FillRecord, Decimal]:
    entry_reference = minute.open
    stop, risk, target, frozen_atr, entry_sigma = _initial_risk(
        program, intent, entry_reference
    )
    execution_price, _ = _execution_price(entry_reference, FillSide.BUY, policy)
    with localcontext(arch151._DECIMAL_CONTEXT):
        quantity = cash / execution_price
        if quantity * execution_price > cash:
            quantity = quantity.next_minus(arch151._DECIMAL_CONTEXT)
    if quantity <= 0:
        raise arch151.UnavailableIndicatorError("cash cannot fund a positive quantity")
    entry = _make_fill(
        source_digest=history_digest,
        slot=slot,
        session=minute.session_date,
        case=case,
        ordinal=fill_ordinal,
        side=FillSide.BUY,
        timestamp=minute.timestamp,
        reference_price=entry_reference,
        quantity=quantity,
        cash_before=cash,
        policy=policy,
    )
    if entry.cash_after < 0:
        raise arch151.Arch151Error("fractional entry exceeded available cash")
    parameters = program.parameters
    hold_minutes = parameters.max_hold_minutes
    position = _Position(
        intent,
        entry,
        entry_reference,
        quantity,
        stop,
        stop,
        risk,
        target,
        frozen_atr,
        entry_sigma,
        entry_reference,
        minute.timestamp + timedelta(minutes=hold_minutes),
        entry.cash_after,
    )
    with localcontext(arch151._DECIMAL_CONTEXT):
        exposure = quantity * execution_price / cash
    if exposure > 1:
        raise arch151.Arch151Error("unleveraged entry exceeded available cash")
    return position, entry.cash_after, entry, exposure


def _tighten_trailing_stop(
    position: _Position,
    program: arch151.Arch151Program,
    tape: _SessionTape,
    completed_at: datetime,
) -> None:
    bar = tape.aggregate_by_completed_at.get(completed_at)
    if bar is None or completed_at <= position.entry_fill.timestamp:
        return
    position.favorable_high = max(position.favorable_high, bar.high)
    parameters = program.parameters
    with localcontext(arch151._DECIMAL_CONTEXT):
        if type(parameters) is arch151.NoiseBreakoutParameters:
            activated = position.favorable_high >= (
                position.entry_reference
                + parameters.trail_activation_r * position.initial_risk
            )
            if not activated:
                return
            candidate = (
                position.favorable_high
                - parameters.trail_distance_r * position.initial_risk
            )
        elif type(parameters) is arch151.OpeningRangeRetestParameters:
            if parameters.trail_activation_r is None:
                return
            activated = position.favorable_high >= (
                position.entry_reference
                + parameters.trail_activation_r * position.initial_risk
            )
            if not activated:
                return
            bars = tape.features.bars
            current_index = next(
                index for index, item in enumerate(bars) if item == bar
            )
            if current_index == 0:
                return
            previous = bars[current_index - 1]
            if bar.timestamp != previous.timestamp + timedelta(
                minutes=int(program.resolution)
            ):
                return
            candidate = previous.low * (Decimal(1) - parameters.stop_buffer_bps / _BPS)
        elif type(parameters) is arch151.CrossEtfPullbackParameters:
            activated = position.favorable_high >= (
                position.entry_reference
                + parameters.trail_activation_r * position.initial_risk
            )
            if not activated or position.frozen_atr is None:
                return
            candidate = (
                position.favorable_high
                - parameters.trail_distance_atr * position.frozen_atr
            )
        else:
            return
    if candidate.is_finite() and candidate > position.active_stop:
        position.active_stop = candidate


def _exit_fill(
    *,
    history_digest: str,
    slot: arch151.TrialSlot,
    session: date,
    case: arch151.FillCostCase,
    policy: arch151.FillCostPolicy,
    position: _Position,
    timestamp: datetime,
    reference_price: Decimal,
    reason: ExitReason,
    cash: Decimal,
    fill_ordinal: int,
) -> tuple[FillRecord, Decimal, TradeRecord]:
    exit_fill = _make_fill(
        source_digest=history_digest,
        slot=slot,
        session=session,
        case=case,
        ordinal=fill_ordinal,
        side=FillSide.SELL,
        timestamp=timestamp,
        reference_price=reference_price,
        quantity=position.quantity,
        cash_before=cash,
        policy=policy,
    )
    entry_reference = position.entry_reference
    with localcontext(arch151._DECIMAL_CONTEXT):
        gross = position.quantity * (reference_price - entry_reference)
        net = exit_fill.cash_after - position.entry_fill.cash_before
        costs = position.entry_fill.adverse_cost + exit_fill.adverse_cost
        gross_exposure = (
            position.quantity
            * position.entry_fill.execution_price
            / position.entry_fill.cash_before
        )
    signal = position.intent.signal
    if type(signal) is arch151.NoiseBreakoutSignal:
        signal_timestamp = signal.confirmation_timestamps[-1]
    elif type(signal) is arch151.OpeningRangeRetestSignal:
        signal_timestamp = signal.signal_timestamp
    else:
        signal_timestamp = signal.signal_timestamp
    trade_id = _canonical_id(
        _TRADE_NAMESPACE,
        "arch151-trade/v1",
        {
            "entry_fill_id": str(position.entry_fill.fill_id),
            "exit_fill_id": str(exit_fill.fill_id),
            "exit_reason": reason.value,
            "signal_timestamp": signal_timestamp.astimezone(UTC).isoformat(),
        },
    )
    trade = TradeRecord(
        trade_id,
        slot.slot_id,
        slot.program_id,
        slot.symbol,
        session,
        signal_timestamp.astimezone(UTC),
        position.entry_fill,
        exit_fill,
        reason,
        position.initial_stop,
        position.active_stop,
        position.target,
        position.initial_risk,
        gross,
        net,
        costs,
        position.entry_fill.cash_before,
        exit_fill.cash_after,
        gross_exposure,
    )
    return exit_fill, exit_fill.cash_after, trade


def _mark_to_market(
    cash: Decimal, position: _Position | None, close: Decimal
) -> Decimal:
    if position is None:
        return cash
    return cash + position.quantity * close


def _idle_session(
    *,
    history_digest: str,
    slot: arch151.TrialSlot,
    case: arch151.FillCostCase,
    session: date,
    starting_equity: Decimal,
) -> SessionReplayRecord:
    session_id = _session_replay_id(
        history_digest, slot, case, session, (), None, (), idle=True
    )
    return SessionReplayRecord(
        session_id,
        session,
        starting_equity,
        starting_equity,
        Decimal(0),
        (),
        (),
        (),
        (),
        Decimal(0),
        None,
    )


def _failure_evidence(
    *,
    source_digest: str,
    slot: arch151.TrialSlot,
    session: date,
    kind: ReplayFailureKind,
    liquidation_boundary: datetime,
    position: _Position | None,
    pending: _PendingExit | None,
    last_observed_timestamp: datetime | None,
) -> ReplayFailureEvidence:
    signal_timestamp = None
    entry_fill = None
    quantity = None
    initial_stop = None
    active_stop = None
    target = None
    if position is not None:
        signal_timestamp = position.intent.signal_timestamp
        entry_fill = position.entry_fill
        quantity = position.quantity
        initial_stop = position.initial_stop
        active_stop = position.active_stop
        target = position.target
    pending_reason = pending.reason if pending is not None else None
    material = {
        "schema": "arch151-replay-failure/v1",
        "source_digest": source_digest,
        "slot_id": str(slot.slot_id),
        "session": session.isoformat(),
        "kind": kind.value,
        "liquidation_boundary": liquidation_boundary.astimezone(UTC).isoformat(),
        "entry_fill_id": str(entry_fill.fill_id) if entry_fill is not None else None,
        "quantity": arch151._decimal_text(quantity) if quantity is not None else None,
        "initial_stop": arch151._decimal_text(initial_stop)
        if initial_stop is not None
        else None,
        "active_stop": arch151._decimal_text(active_stop)
        if active_stop is not None
        else None,
        "target": arch151._decimal_text(target) if target is not None else None,
        "pending_exit": pending_reason.value if pending_reason is not None else None,
        "last_observed_timestamp": (
            last_observed_timestamp.astimezone(UTC).isoformat()
            if last_observed_timestamp is not None
            else None
        ),
    }
    digest = sha256(arch151._canonical_json(material)).hexdigest()
    failure_id = _canonical_id(_RESULT_NAMESPACE, "arch151-replay-failure/v1", material)
    return ReplayFailureEvidence(
        failure_id,
        kind,
        session,
        liquidation_boundary.astimezone(UTC),
        signal_timestamp,
        entry_fill,
        quantity,
        initial_stop,
        active_stop,
        target,
        pending_reason,
        last_observed_timestamp,
        digest,
    )


def _session_replay_id(
    source_digest: str,
    slot: arch151.TrialSlot,
    case: arch151.FillCostCase,
    session: date,
    fills: tuple[FillRecord, ...],
    failure: ReplayFailureEvidence | None,
    signal_outcomes: tuple[SignalLifecycleOutcome, ...],
    *,
    idle: bool = False,
) -> UUID:
    return _canonical_id(
        _SESSION_NAMESPACE,
        "arch151-session-replay/v2",
        {
            "source_digest": source_digest,
            "slot_id": str(slot.slot_id),
            "cost_case": case.value,
            "session": session.isoformat(),
            "fill_ids": [str(item.fill_id) for item in fills],
            "failure_id": str(failure.failure_id) if failure is not None else None,
            "signal_outcome_ids": [str(item.outcome_id) for item in signal_outcomes],
            "idle": idle,
        },
    )


def _signal_lifecycle_outcome(
    *,
    source_digest: str,
    slot: arch151.TrialSlot,
    case: arch151.FillCostCase,
    session: date,
    intent: _EntryIntent,
    scheduled_next_open: datetime,
    entry_window_eligible: bool,
    disposition: SignalDisposition,
    blocked_reason: RejectionReason | None = None,
    entry_fill_id: UUID | None = None,
) -> SignalLifecycleOutcome:
    signal_timestamp = intent.signal_timestamp.astimezone(UTC)
    decision_timestamp = intent.completed_at.astimezone(UTC)
    next_open = scheduled_next_open.astimezone(UTC)
    signal_material = {
        "source_digest": source_digest,
        "slot_id": str(slot.slot_id),
        "session": session.isoformat(),
        "signal_type": type(intent.signal).__name__,
        "signal_timestamp": signal_timestamp.isoformat(),
        "decision_timestamp": decision_timestamp.isoformat(),
    }
    signal_id = _canonical_id(
        _SIGNAL_NAMESPACE, "arch151-generated-signal/v1", signal_material
    )
    outcome_material = {
        "signal_id": str(signal_id),
        "cost_case": case.value,
        "scheduled_next_open": next_open.isoformat(),
        "entry_window_eligible": entry_window_eligible,
        "disposition": disposition.value,
        "blocked_reason": blocked_reason.value if blocked_reason is not None else None,
        "entry_fill_id": str(entry_fill_id) if entry_fill_id is not None else None,
    }
    outcome_id = _canonical_id(
        _SIGNAL_OUTCOME_NAMESPACE,
        "arch151-signal-lifecycle-outcome/v1",
        outcome_material,
    )
    return SignalLifecycleOutcome(
        signal_id,
        outcome_id,
        signal_timestamp,
        decision_timestamp,
        next_open,
        entry_window_eligible,
        disposition,
        blocked_reason,
        entry_fill_id,
    )


def _exit_position(
    *,
    history_digest: str,
    slot: arch151.TrialSlot,
    case: arch151.FillCostCase,
    policy: arch151.FillCostPolicy,
    position: _Position,
    reason: ExitReason,
    timestamp: datetime,
    reference_price: Decimal,
    cash: Decimal,
    fill_ordinal: int,
) -> tuple[Decimal, FillRecord, TradeRecord]:
    fill, next_cash, trade = _exit_fill(
        history_digest=history_digest,
        slot=slot,
        session=timestamp.astimezone(arch151.NEW_YORK).date(),
        case=case,
        policy=policy,
        position=position,
        timestamp=timestamp,
        reference_price=reference_price,
        reason=reason,
        cash=cash,
        fill_ordinal=fill_ordinal,
    )
    return next_cash, fill, trade


def _trade_with_observed_excursions(
    trade: TradeRecord, minutes: tuple[arch151.OneMinuteBar, ...]
) -> TradeRecord:
    """Bind MFE/MAE from fully held observed minutes only.

    The minute containing an intrabar exit is excluded because its OHLC order is
    unknown. A minute is included only when its completion is no later than the
    exit fill timestamp. This intentionally leaves an immediate same-minute
    trade without an excursion estimate.
    """

    held_minutes = tuple(
        item
        for item in minutes
        if item.symbol == trade.symbol
        and item.session_date == trade.session_date
        and item.timestamp >= trade.entry.timestamp
        and item.completed_at <= trade.exit.timestamp
    )
    if not held_minutes:
        return replace(
            trade, mfe_return=None, mae_return=None, excursion_minute_count=0
        )
    with localcontext(arch151._DECIMAL_CONTEXT):
        entry_price = trade.entry.execution_price
        mfe = max(item.high / entry_price - Decimal(1) for item in held_minutes)
        mae = min(item.low / entry_price - Decimal(1) for item in held_minutes)
    return replace(
        trade,
        mfe_return=mfe,
        mae_return=mae,
        excursion_minute_count=len(held_minutes),
    )


def _simulate_session_from_tape(
    *,
    history_digest: str,
    slot: arch151.TrialSlot,
    program: arch151.Arch151Program,
    session: date,
    tape: _SessionTape | None,
    minutes: tuple[arch151.OneMinuteBar, ...],
    starting_equity: Decimal,
    case: arch151.FillCostCase,
) -> SessionReplayRecord:
    if (
        type(starting_equity) is not Decimal
        or not starting_equity.is_finite()
        or starting_equity <= 0
    ):
        raise ValueError("session starting equity must be finite and positive")
    policy = _cost_policy(case)
    schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
    if schedule is None:
        raise arch151.Arch151Error("replay date is not a published XNYS session")
    if tape is None:
        return _idle_session(
            history_digest=history_digest,
            slot=slot,
            case=case,
            session=session,
            starting_equity=starting_equity,
        )
    minute_by_timestamp = {item.timestamp: item for item in minutes}
    if len(minute_by_timestamp) != len(minutes):
        raise arch151.Arch151Error("source minute projection contains duplicates")
    open_utc = schedule.opens_at.astimezone(UTC)
    close_utc = schedule.closes_at.astimezone(UTC)
    liquidation_boundary = close_utc - timedelta(minutes=5)
    position: _Position | None = None
    pending_exit: _PendingExit | None = None
    cash = starting_equity
    fills: list[FillRecord] = []
    trades: list[TradeRecord] = []
    expired_entries: list[datetime] = []
    rejections: list[SignalRejection] = []
    signal_outcomes: list[SignalLifecycleOutcome] = []
    fill_notional = Decimal(0)
    last_exit_timestamp: datetime | None = None
    last_observed_timestamp: datetime | None = None

    timestamp = open_utc
    while timestamp < close_utc:
        minute = minute_by_timestamp.get(timestamp)
        intent = tape.entry_intents.get(timestamp)

        if position is not None:
            completed_observation = tape.observation_by_completed_at.get(timestamp)
            if (
                completed_observation is not None
                and type(position.intent.signal) is arch151.VwapMeanReversionSignal
            ):
                should_exit = arch151.family_c_reversion_exit(
                    program,
                    position.intent.signal,
                    completed_observation,
                    verified_session=tape.evidence,
                )
                if should_exit and pending_exit is None:
                    pending_exit = _PendingExit(ExitReason.VWAP_REVERSION, timestamp)
            if timestamp >= position.max_hold_at:
                # The elapsed holding limit is mandatory and wins a same-open
                # tie with a completed-bar reversion decision.
                pending_exit = _PendingExit(ExitReason.MAXIMUM_HOLD, timestamp)
            if timestamp >= liquidation_boundary:
                pending_exit = _PendingExit(
                    ExitReason.SESSION_LIQUIDATION, liquidation_boundary
                )
            if timestamp in tape.aggregate_by_completed_at:
                _tighten_trailing_stop(position, program, tape, timestamp)

        had_position_at_open = position is not None
        if minute is not None:
            last_observed_timestamp = timestamp

        if position is not None and minute is not None:
            exit_reason: ExitReason | None = None
            exit_reference: Decimal | None = None
            if timestamp >= liquidation_boundary:
                exit_reason = ExitReason.SESSION_LIQUIDATION
                exit_reference = minute.open
            elif minute.open <= position.active_stop:
                exit_reason = ExitReason.STOP_GAP
                exit_reference = minute.open
            elif position.target is not None and minute.open >= position.target:
                exit_reason = ExitReason.TARGET_OPEN
                exit_reference = position.target
            elif pending_exit is not None:
                exit_reason = pending_exit.reason
                exit_reference = minute.open
            elif minute.low <= position.active_stop:
                exit_reason = ExitReason.STOP_TOUCH
                exit_reference = position.active_stop
            elif position.target is not None and minute.high >= position.target:
                exit_reason = ExitReason.TARGET_TOUCH
                exit_reference = position.target
            if exit_reason is not None and exit_reference is not None:
                cash, exit_fill, trade = _exit_position(
                    history_digest=history_digest,
                    slot=slot,
                    case=case,
                    policy=policy,
                    position=position,
                    reason=exit_reason,
                    timestamp=timestamp,
                    reference_price=exit_reference,
                    cash=cash,
                    fill_ordinal=len(fills),
                )
                trade = _trade_with_observed_excursions(trade, minutes)
                fills.append(exit_fill)
                trades.append(trade)
                with localcontext(arch151._DECIMAL_CONTEXT):
                    fill_notional += exit_fill.quantity * exit_fill.execution_price
                position = None
                pending_exit = None
                last_exit_timestamp = timestamp

        if intent is not None:
            parameters = program.parameters
            entry_window_eligible = (
                timestamp < close_utc
                and timestamp < liquidation_boundary
                and program.entry_window.contains(timestamp)
            )
            blocked_reason: RejectionReason | None = None
            if had_position_at_open:
                blocked_reason = RejectionReason.POSITION_ALREADY_OPEN
            elif timestamp >= liquidation_boundary or timestamp >= close_utc:
                blocked_reason = RejectionReason.LIQUIDATION_WINDOW
            elif len(trades) >= 2 or len(trades) >= parameters.entry_limit_per_session:
                blocked_reason = RejectionReason.SESSION_ENTRY_LIMIT
            elif (
                type(parameters) is arch151.VwapMeanReversionParameters
                and last_exit_timestamp is not None
                and timestamp
                < last_exit_timestamp + timedelta(minutes=parameters.cooldown_minutes)
            ):
                blocked_reason = RejectionReason.COOLDOWN_ACTIVE
            elif not program.entry_window.contains(timestamp):
                blocked_reason = RejectionReason.ENTRY_WINDOW_CLOSED

            if blocked_reason is not None:
                rejections.append(SignalRejection(timestamp, blocked_reason))
                signal_outcomes.append(
                    _signal_lifecycle_outcome(
                        source_digest=history_digest,
                        slot=slot,
                        case=case,
                        session=session,
                        intent=intent,
                        scheduled_next_open=timestamp,
                        entry_window_eligible=entry_window_eligible,
                        disposition=SignalDisposition.BLOCKED,
                        blocked_reason=blocked_reason,
                    )
                )
            elif minute is None:
                expired_entries.append(timestamp)
                signal_outcomes.append(
                    _signal_lifecycle_outcome(
                        source_digest=history_digest,
                        slot=slot,
                        case=case,
                        session=session,
                        intent=intent,
                        scheduled_next_open=timestamp,
                        entry_window_eligible=entry_window_eligible,
                        disposition=SignalDisposition.EXPIRED,
                    )
                )
            else:
                try:
                    position, cash, entry_fill, _exposure = _entry_position(
                        history_digest=history_digest,
                        slot=slot,
                        program=program,
                        intent=intent,
                        minute=minute,
                        cash=cash,
                        case=case,
                        policy=policy,
                        fill_ordinal=len(fills),
                    )
                    fills.append(entry_fill)
                    with localcontext(arch151._DECIMAL_CONTEXT):
                        fill_notional += (
                            entry_fill.quantity * entry_fill.execution_price
                        )
                except arch151.UnavailableIndicatorError:
                    blocked_reason = RejectionReason.NONPOSITIVE_INITIAL_R
                    rejections.append(SignalRejection(timestamp, blocked_reason))
                    signal_outcomes.append(
                        _signal_lifecycle_outcome(
                            source_digest=history_digest,
                            slot=slot,
                            case=case,
                            session=session,
                            intent=intent,
                            scheduled_next_open=timestamp,
                            entry_window_eligible=entry_window_eligible,
                            disposition=SignalDisposition.BLOCKED,
                            blocked_reason=blocked_reason,
                        )
                    )

                if position is not None:
                    signal_outcomes.append(
                        _signal_lifecycle_outcome(
                            source_digest=history_digest,
                            slot=slot,
                            case=case,
                            session=session,
                            intent=intent,
                            scheduled_next_open=timestamp,
                            entry_window_eligible=entry_window_eligible,
                            disposition=SignalDisposition.EXECUTED,
                            entry_fill_id=entry_fill.fill_id,
                        )
                    )
                    # The entry open is the fill reference. The remaining
                    # observed range in that same minute is checked afterward.
                    entry_exit_reason: ExitReason | None = None
                    entry_exit_reference: Decimal | None = None
                    if minute.low <= position.active_stop:
                        entry_exit_reason = ExitReason.STOP_TOUCH
                        entry_exit_reference = position.active_stop
                    elif position.target is not None and minute.high >= position.target:
                        entry_exit_reason = ExitReason.TARGET_TOUCH
                        entry_exit_reference = position.target
                    if (
                        entry_exit_reason is not None
                        and entry_exit_reference is not None
                    ):
                        cash, exit_fill, trade = _exit_position(
                            history_digest=history_digest,
                            slot=slot,
                            case=case,
                            policy=policy,
                            position=position,
                            reason=entry_exit_reason,
                            timestamp=timestamp,
                            reference_price=entry_exit_reference,
                            cash=cash,
                            fill_ordinal=len(fills),
                        )
                        trade = _trade_with_observed_excursions(trade, minutes)
                        fills.append(exit_fill)
                        trades.append(trade)
                        with localcontext(arch151._DECIMAL_CONTEXT):
                            fill_notional += (
                                exit_fill.quantity * exit_fill.execution_price
                            )
                        position = None
                        last_exit_timestamp = timestamp

        timestamp += timedelta(minutes=1)

    failure = None
    if position is not None:
        failure = _failure_evidence(
            source_digest=history_digest,
            slot=slot,
            session=session,
            kind=ReplayFailureKind.MANDATORY_LIQUIDATION_UNOBSERVED,
            liquidation_boundary=liquidation_boundary,
            position=position,
            pending=pending_exit,
            last_observed_timestamp=last_observed_timestamp,
        )
        closing_equity = None
        session_return = None
    else:
        closing_equity = cash
        with localcontext(arch151._DECIMAL_CONTEXT):
            session_return = closing_equity / starting_equity - Decimal(1)
    fill_tuple = tuple(fills)
    trade_tuple = tuple(trades)
    outcome_tuple = tuple(signal_outcomes)
    return SessionReplayRecord(
        _session_replay_id(
            history_digest,
            slot,
            case,
            session,
            fill_tuple,
            failure,
            outcome_tuple,
        ),
        session,
        starting_equity,
        closing_equity,
        session_return,
        trade_tuple,
        fill_tuple,
        tuple(expired_entries),
        tuple(rejections),
        fill_notional,
        failure,
        outcome_tuple,
    )


def _simulate_session(
    history: SourceHistory,
    slot: arch151.TrialSlot,
    session: date,
    case: arch151.FillCostCase,
    *,
    starting_equity: Decimal = Decimal(1),
) -> SessionReplayRecord:
    """Testable one-session entry point; it accepts no fabricated features."""

    history_digest = _history_digest(history)
    program = _slot_program(slot)
    if type(session) is not date:
        raise TypeError("replay session must be a date")
    if session.year not in arch151.SCORED_YEARS:
        raise ValueError("replay session is outside the scored development years")
    cache = _PreparationCache(history)
    calibration = None
    if program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT:
        try:
            calibration = arch151.calibrate_family_a_from_source_history(
                history, program, slot.symbol, session.year
            )
        except arch151.UnavailableIndicatorError:
            schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
            if schedule is None:
                raise arch151.Arch151Error(
                    "replay date is not a published XNYS session"
                ) from None
            boundary = schedule.closes_at.astimezone(UTC) - timedelta(minutes=5)
            failure = _failure_evidence(
                source_digest=history_digest,
                slot=slot,
                session=session,
                kind=ReplayFailureKind.CALIBRATION_UNAVAILABLE,
                liquidation_boundary=boundary,
                position=None,
                pending=None,
                last_observed_timestamp=None,
            )
            return SessionReplayRecord(
                _session_replay_id(
                    history_digest, slot, case, session, (), failure, ()
                ),
                session,
                starting_equity,
                None,
                None,
                (),
                (),
                (),
                (),
                Decimal(0),
                failure,
            )
    tape = _session_tape(history, cache, program, slot.symbol, session, calibration)
    projection = history._projection_index.get(
        (slot.symbol, session, program.resolution)
    )
    minutes = projection.minutes if projection is not None else ()
    return _simulate_session_from_tape(
        history_digest=history_digest,
        slot=slot,
        program=program,
        session=session,
        tape=tape,
        minutes=minutes,
        starting_equity=starting_equity,
        case=case,
    )


def _slot_year_failure(
    history_digest: str,
    slot: arch151.TrialSlot,
    year: int,
    case: arch151.FillCostCase,
    failure: ReplayFailureEvidence,
) -> SlotYearReplay:
    replay_id = _canonical_id(
        _RESULT_NAMESPACE,
        "arch151-slot-year-replay/v1",
        {
            "source_digest": history_digest,
            "slot_id": str(slot.slot_id),
            "scored_year": year,
            "cost_case": case.value,
            "failure_id": str(failure.failure_id),
        },
    )
    return SlotYearReplay(
        replay_id=replay_id,
        slot=slot,
        scored_year=year,
        cost_case=case,
        source_digest=history_digest,
        sessions=(),
        trades=(),
        complete=False,
        initial_equity=Decimal(1),
        final_equity=None,
        net_return=None,
        positive_net_pnl=None,
        negative_net_pnl=None,
        gross_trade_pnl=None,
        total_adverse_cost=None,
        fill_notional=None,
        turnover=None,
        maximum_drawdown=None,
        failure=failure,
    )


def _finish_slot_year(
    *,
    history_digest: str,
    slot: arch151.TrialSlot,
    year: int,
    case: arch151.FillCostCase,
    sessions: tuple[SessionReplayRecord, ...],
) -> SlotYearReplay:
    trades = tuple(trade for item in sessions for trade in item.trades)
    failure = next(
        (item.failure for item in sessions if item.failure is not None), None
    )
    if failure is not None or any(item.session_return is None for item in sessions):
        replay_id = _canonical_id(
            _RESULT_NAMESPACE,
            "arch151-slot-year-replay/v1",
            {
                "source_digest": history_digest,
                "slot_id": str(slot.slot_id),
                "scored_year": year,
                "cost_case": case.value,
                "session_ids": [str(item.session_id) for item in sessions],
                "failure_id": str(failure.failure_id) if failure is not None else None,
            },
        )
        return SlotYearReplay(
            replay_id=replay_id,
            slot=slot,
            scored_year=year,
            cost_case=case,
            source_digest=history_digest,
            sessions=sessions,
            trades=trades,
            complete=False,
            initial_equity=Decimal(1),
            final_equity=None,
            net_return=None,
            positive_net_pnl=None,
            negative_net_pnl=None,
            gross_trade_pnl=None,
            total_adverse_cost=None,
            fill_notional=None,
            turnover=None,
            maximum_drawdown=None,
            failure=failure,
        )
    if len(sessions) != len(arch151._published_sessions_for_year(year)):
        raise arch151.Arch151Error("slot-year replay omitted published XNYS sessions")
    with localcontext(arch151._DECIMAL_CONTEXT):
        final_equity = sessions[-1].closing_equity
        assert final_equity is not None
        net_return = final_equity - Decimal(1)
        positive_net = sum(
            (max(trade.net_pnl, Decimal(0)) for trade in trades), Decimal(0)
        )
        negative_net = sum(
            (max(-trade.net_pnl, Decimal(0)) for trade in trades), Decimal(0)
        )
        gross_trade = sum((trade.gross_pnl for trade in trades), Decimal(0))
        adverse_cost = sum((trade.total_adverse_cost for trade in trades), Decimal(0))
        fill_notional = sum((item.fill_notional for item in sessions), Decimal(0))
        avg_equity = sum(
            (
                item.closing_equity
                for item in sessions
                if item.closing_equity is not None
            ),
            Decimal(0),
        ) / Decimal(len(sessions))
        turnover = fill_notional / avg_equity if avg_equity > 0 else Decimal(0)
        peak = Decimal(1)
        max_drawdown = Decimal(0)
        for item in sessions:
            assert item.closing_equity is not None
            peak = max(peak, item.closing_equity)
            drawdown = (peak - item.closing_equity) / peak
            max_drawdown = max(max_drawdown, drawdown)
    replay_material = {
        "source_digest": history_digest,
        "slot_id": str(slot.slot_id),
        "scored_year": year,
        "cost_case": case.value,
        "session_ids": [str(item.session_id) for item in sessions],
        "trade_ids": [str(item.trade_id) for item in trades],
    }
    return SlotYearReplay(
        _canonical_id(
            _RESULT_NAMESPACE, "arch151-slot-year-replay/v1", replay_material
        ),
        slot,
        year,
        case,
        history_digest,
        sessions,
        trades,
        True,
        Decimal(1),
        final_equity,
        net_return,
        positive_net,
        negative_net,
        gross_trade,
        adverse_cost,
        fill_notional,
        turnover,
        max_drawdown,
        None,
    )


def _simulate_slot_year_cases(
    history: SourceHistory,
    slot: arch151.TrialSlot,
    year: int,
    *,
    preparation_cache: _PreparationCache | None = None,
    calibration_cache: _FamilyACalibrationCache | None = None,
) -> tuple[SlotYearReplay, ...]:
    history_digest = _history_digest(history)
    program = _slot_program(slot)
    if type(year) is not int or year not in arch151.SCORED_YEARS:
        raise ValueError("scored year is outside the frozen walk-forward period")
    cases = arch151.EVALUATION_ECONOMICS_ORDER
    calibration = None
    if program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT:
        try:
            if calibration_cache is None:
                calibration = arch151.calibrate_family_a_from_source_history(
                    history, program, slot.symbol, year
                )
            else:
                if calibration_cache.source_digest != history_digest:
                    raise EvaluationIntegrityError(
                        "Family A calibration cache belongs to another source"
                    )
                calibration = calibration_cache.calibration(program, slot.symbol, year)
        except arch151.UnavailableIndicatorError:
            first_session = arch151._published_sessions_for_year(year)[0]
            schedule = arch151._SESSION_AUTHORITY.schedule_for(first_session)
            assert schedule is not None
            failure = _failure_evidence(
                source_digest=history_digest,
                slot=slot,
                session=first_session,
                kind=ReplayFailureKind.CALIBRATION_UNAVAILABLE,
                liquidation_boundary=schedule.closes_at.astimezone(UTC)
                - timedelta(minutes=5),
                position=None,
                pending=None,
                last_observed_timestamp=None,
            )
            return tuple(
                _slot_year_failure(history_digest, slot, year, case, failure)
                for case in cases
            )
        except Exception as error:
            raise AnnualReplayFailure(
                AnnualReplayFailureContext(
                    year,
                    slot.program_id,
                    slot.slot_id,
                    slot.symbol,
                    None,
                    None,
                    AnnualReplayOperationStage.FAMILY_A_CALIBRATION,
                )
            ) from error
    try:
        cache = preparation_cache or _PreparationCache(history)
    except Exception as error:
        raise AnnualReplayFailure(
            AnnualReplayFailureContext(
                year,
                slot.program_id,
                slot.slot_id,
                slot.symbol,
                None,
                None,
                AnnualReplayOperationStage.PROGRAM_FEATURE_PREPARATION,
            )
        ) from error
    sessions_by_case: dict[arch151.FillCostCase, list[SessionReplayRecord]] = {
        case: [] for case in cases
    }
    equity_by_case = {case: Decimal(1) for case in cases}
    stopped_cases: set[arch151.FillCostCase] = set()
    for session in arch151._published_sessions_for_year(year):
        try:
            tape = _session_tape(
                history, cache, program, slot.symbol, session, calibration
            )
        except Exception as error:
            raise AnnualReplayFailure(
                AnnualReplayFailureContext(
                    year,
                    slot.program_id,
                    slot.slot_id,
                    slot.symbol,
                    None,
                    session,
                    AnnualReplayOperationStage.SESSION_TAPE_PREPARATION,
                )
            ) from error
        projection = history._projection_index.get(
            (slot.symbol, session, program.resolution)
        )
        for case in cases:
            if case in stopped_cases:
                continue
            try:
                record = _simulate_session_from_tape(
                    history_digest=history_digest,
                    slot=slot,
                    program=program,
                    session=session,
                    tape=tape,
                    minutes=projection.minutes if projection is not None else (),
                    starting_equity=equity_by_case[case],
                    case=case,
                )
            except Exception as error:
                raise AnnualReplayFailure(
                    AnnualReplayFailureContext(
                        year,
                        slot.program_id,
                        slot.slot_id,
                        slot.symbol,
                        case,
                        session,
                        AnnualReplayOperationStage.SESSION_EXECUTION,
                    )
                ) from error
            sessions_by_case[case].append(record)
            if record.closing_equity is None:
                stopped_cases.add(case)
            else:
                equity_by_case[case] = record.closing_equity
    results = []
    for case in cases:
        try:
            results.append(
                _finish_slot_year(
                    history_digest=history_digest,
                    slot=slot,
                    year=year,
                    case=case,
                    sessions=tuple(sessions_by_case[case]),
                )
            )
        except Exception as error:
            raise AnnualReplayFailure(
                AnnualReplayFailureContext(
                    year,
                    slot.program_id,
                    slot.slot_id,
                    slot.symbol,
                    case,
                    None,
                    AnnualReplayOperationStage.SLOT_YEAR_AGGREGATION,
                )
            ) from error
    return tuple(results)


def _simulate_slot_year(
    history: SourceHistory,
    slot: arch151.TrialSlot,
    year: int,
    case: arch151.FillCostCase,
) -> SlotYearReplay:
    """Evaluate one internal cost projection; public batches remain complete."""

    _cost_policy(case)
    return next(
        result
        for result in _simulate_slot_year_cases(history, slot, year)
        if result.cost_case is case
    )


def simulate_canonical_year(
    history: SourceHistory, scored_year: int
) -> CanonicalYearBatch:
    """Replay the immutable complete 32-slot × 3-economics population.

    This source API exposes no caller-selected subset and performs no reads or
    effects. Production history must already have been issued by Assignment A;
    focused tests use the separate private synthetic history constructor.
    """

    history_digest = _history_digest(history)
    if type(scored_year) is not int or scored_year not in arch151.SCORED_YEARS:
        raise ValueError("scored year is outside the frozen walk-forward period")
    evaluations_list: list[SlotYearReplay] = []
    active_program_id: UUID | None = None
    program_cache: _PreparationCache | None = None
    calibration_cache = _FamilyACalibrationCache(history)
    for slot in arch151.CANONICAL_SLOTS:
        if slot.program_id != active_program_id:
            active_program_id = slot.program_id
            program = _slot_program(slot)
            try:
                program_cache = (
                    _PreparationCache(history)
                    if program.family is arch151.StrategyFamily.CROSS_ETF_TREND_PULLBACK
                    else None
                )
            except Exception as error:
                raise AnnualReplayFailure(
                    AnnualReplayFailureContext(
                        scored_year,
                        slot.program_id,
                        slot.slot_id,
                        slot.symbol,
                        None,
                        None,
                        AnnualReplayOperationStage.PROGRAM_FEATURE_PREPARATION,
                    )
                ) from error
        # Family D prepares both ETFs for either execution slot. The manifest
        # orders its two symbols adjacently, so one program-scoped cache reuses
        # those immutable prefixes without retaining features across programs.
        evaluations_list.extend(
            _simulate_slot_year_cases(
                history,
                slot,
                scored_year,
                preparation_cache=program_cache,
                calibration_cache=calibration_cache,
            )
        )
    evaluations = tuple(evaluations_list)
    source_binding = _development_source_binding(history)
    passive_spy_benchmark = _passive_benchmark_year(history, scored_year)
    material = {
        "schema": "arch151-canonical-year-batch/v3",
        "source_binding_id": str(source_binding.binding_id),
        "source_digest": history_digest,
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "scored_year": scored_year,
        "replay_outputs": [
            {"replay_id": str(item.replay_id), "replay_digest": item.replay_digest}
            for item in evaluations
        ],
        "passive_spy_benchmark_id": str(passive_spy_benchmark.benchmark_id),
    }
    return CanonicalYearBatch(
        _canonical_id(_BATCH_NAMESPACE, "arch151-canonical-year-batch/v3", material),
        scored_year,
        arch151.CANONICAL_MANIFEST.manifest_id,
        arch151.CANONICAL_MANIFEST.fingerprint,
        history_digest,
        evaluations,
        passive_spy_benchmark,
        source_binding,
        _CANONICAL_YEAR_BATCH_SEAL,
    )


def _validate_session_trade_cash(session: SessionReplayRecord) -> None:
    # Cash balances telescope across fills and across sessions. Profit-factor
    # gain and loss sums round separately and need not subtract to that result.
    cash = session.starting_equity
    if session.trades or session.fills:
        if session.fills != tuple(
            fill for trade in session.trades for fill in (trade.entry, trade.exit)
        ):
            raise EvaluationIntegrityError(
                "session fills differ from its completed trades"
            )
        with localcontext(arch151._DECIMAL_CONTEXT):
            for trade in session.trades:
                if (
                    trade.entry.cash_before != cash
                    or trade.exit.cash_before != trade.entry.cash_after
                    or trade.equity_before != cash
                    or trade.equity_after != trade.exit.cash_after
                ):
                    raise EvaluationIntegrityError(
                        "trade cash balances do not reconcile"
                    )
                if trade.net_pnl != trade.exit.cash_after - cash:
                    raise EvaluationIntegrityError(
                        "trade net P&L does not reconcile to fill cash"
                    )
                cash = trade.exit.cash_after
    if cash != session.closing_equity:
        raise EvaluationIntegrityError(
            "session closing equity does not reconcile to fill cash"
        )


def _fold_metrics_from_slot_year(replay: SlotYearReplay) -> arch151.FoldMetrics:
    if type(replay) is not SlotYearReplay or not replay.complete or replay.failure:
        raise EvaluationIntegrityError(
            "incomplete slot-year replay cannot be qualified"
        )
    expected_sessions = arch151._published_sessions_for_year(replay.scored_year)
    if tuple(item.session_date for item in replay.sessions) != expected_sessions:
        raise EvaluationIntegrityError("slot-year replay omits published XNYS sessions")
    if replay.initial_equity != Decimal(1):
        raise EvaluationIntegrityError(
            "each scored year must start at normalized equity one"
        )
    expected_equity = Decimal(1)
    returns: list[Decimal] = []
    round_trips: list[int] = []
    for session in replay.sessions:
        if (
            session.failure is not None
            or session.closing_equity is None
            or session.session_return is None
            or session.starting_equity != expected_equity
        ):
            raise EvaluationIntegrityError(
                "session sequence contains a failed or inconsistent equity record"
            )
        if not session.signal_lifecycle_reconciled:
            raise EvaluationIntegrityError("session signal outcomes do not reconcile")
        with localcontext(arch151._DECIMAL_CONTEXT):
            expected_return = (
                session.closing_equity / session.starting_equity - Decimal(1)
            )
        if session.session_return != expected_return:
            raise EvaluationIntegrityError(
                "session return does not reconcile to equity"
            )
        _validate_session_trade_cash(session)
        returns.append(session.session_return)
        round_trips.append(session.completed_round_trips)
        expected_equity = session.closing_equity
    flattened_trades = tuple(trade for item in replay.sessions for trade in item.trades)
    if replay.trades != flattened_trades:
        raise EvaluationIntegrityError(
            "slot-year trades differ from its session records"
        )
    if replay.final_equity != expected_equity or replay.net_return is None:
        raise EvaluationIntegrityError(
            "slot-year final equity is missing or inconsistent"
        )
    with localcontext(arch151._DECIMAL_CONTEXT):
        if replay.net_return != expected_equity - Decimal(1):
            raise EvaluationIntegrityError("slot-year net return does not reconcile")
        gross_positive = sum(
            (max(trade.gross_pnl, Decimal(0)) for trade in replay.trades), Decimal(0)
        )
        gross_negative = sum(
            (max(-trade.gross_pnl, Decimal(0)) for trade in replay.trades), Decimal(0)
        )
        net_positive = sum(
            (max(trade.net_pnl, Decimal(0)) for trade in replay.trades), Decimal(0)
        )
        net_negative = sum(
            (max(-trade.net_pnl, Decimal(0)) for trade in replay.trades), Decimal(0)
        )
        total_gross = sum((trade.gross_pnl for trade in replay.trades), Decimal(0))
        total_adverse_cost = sum(
            (trade.total_adverse_cost for trade in replay.trades), Decimal(0)
        )
    if (
        replay.positive_net_pnl != net_positive
        or replay.negative_net_pnl != net_negative
        or replay.gross_trade_pnl != total_gross
        or replay.total_adverse_cost != total_adverse_cost
    ):
        raise EvaluationIntegrityError(
            "slot-year realized P&L totals do not reconcile to trade outcomes"
        )
    if (
        type(replay.turnover) is not Decimal
        or not replay.turnover.is_finite()
        or replay.turnover < 0
    ):
        raise EvaluationIntegrityError("slot-year evaluator turnover is unavailable")
    return arch151.FoldMetrics(
        expected_sessions,
        tuple(returns),
        tuple(round_trips),
        gross_positive,
        gross_negative,
        net_positive,
        net_negative,
        replay.turnover,
    )


def compose_development_evaluation(
    year_batches: tuple[CanonicalYearBatch, ...],
) -> DevelopmentEvaluationRun:
    """Validate five canonical year outputs and compose all 480 fold records."""

    if (
        type(year_batches) is not tuple
        or tuple(item.scored_year for item in year_batches) != arch151.SCORED_YEARS
    ):
        raise EvaluationIntegrityError(
            "development composition requires exact WF1–WF5 order"
        )
    first = year_batches[0]
    if any(
        type(batch) is not CanonicalYearBatch
        or getattr(batch, "_seal", None) is not _CANONICAL_YEAR_BATCH_SEAL
        or not batch.complete
        or batch.source_digest != first.source_digest
        or batch.source_binding != first.source_binding
        or batch.manifest_id != arch151.CANONICAL_MANIFEST.manifest_id
        or batch.manifest_fingerprint != arch151.CANONICAL_MANIFEST.fingerprint
        or batch.batch_id
        != _canonical_year_batch_id(
            batch.source_binding,
            batch.scored_year,
            batch.evaluations,
            batch.passive_spy_benchmark,
        )
        for batch in year_batches
    ):
        raise EvaluationIntegrityError(
            "all five complete year outputs must share "
            "exact source and manifest identity, with evaluator-issued batch IDs"
        )
    expected_year_rows = tuple(
        (slot.slot_id, cost_case)
        for slot in arch151.CANONICAL_SLOTS
        for cost_case in arch151.EVALUATION_ECONOMICS_ORDER
    )
    for batch in year_batches:
        if (
            len(batch.evaluations) != len(expected_year_rows)
            or tuple((item.slot.slot_id, item.cost_case) for item in batch.evaluations)
            != expected_year_rows
        ):
            raise EvaluationIntegrityError(
                "each year output must contain all 32 slots × three cost cases in order"
            )
        if any(
            item.scored_year != batch.scored_year
            or item.source_digest != batch.source_digest
            or item.slot not in arch151.CANONICAL_SLOTS
            for item in batch.evaluations
        ):
            raise EvaluationIntegrityError(
                "year output contains mixed replay identities"
            )
    runs_by_year = {
        batch.scored_year: {
            (item.slot.slot_id, item.cost_case): item for item in batch.evaluations
        }
        for batch in year_batches
    }
    slot_batches: list[arch151.DevelopmentEvaluationBatch] = []
    for slot in arch151.CANONICAL_SLOTS:
        fold_records: list[arch151.FoldEvaluation] = []
        for fold in arch151.WALK_FORWARD_FOLDS:
            for cost_case in arch151.EVALUATION_ECONOMICS_ORDER:
                replay = runs_by_year[fold.scored_year][(slot.slot_id, cost_case)]
                fold_records.append(
                    arch151.FoldEvaluation(
                        slot.slot_id,
                        slot.program_id,
                        slot.symbol,
                        fold,
                        cost_case,
                        _fold_metrics_from_slot_year(replay),
                    )
                )
        slot_batches.append(
            arch151.DevelopmentEvaluationBatch(slot.slot_id, tuple(fold_records))
        )
    batches = tuple(slot_batches)
    if sum(len(item.records) for item in batches) != 480:
        raise EvaluationIntegrityError(
            "composed development population is not 480 records"
        )
    selection = arch151.compute_selection_bias_evidence(batches)
    evidence_by_slot = {item.candidate_slot_id: item for item in selection.evidence}
    qualifications = tuple(
        arch151.qualify_development(batch, evidence_by_slot.get(batch.slot_id))
        for batch in batches
    )
    ranking_order = (
        arch151.rank_verified_candidate_population(batches, selection)
        if selection.status is arch151.SelectionBiasStatus.DSR_VERIFIED
        else ()
    )
    freeze = arch151.freeze_final_candidate_set(
        batches, _selection_bias_calculation=selection
    )
    passive_spy_benchmark = _passive_benchmark_campaign(
        tuple(batch.passive_spy_benchmark for batch in year_batches)
    )
    run_id = _development_run_id(
        first.source_binding,
        year_batches,
        batches,
        selection,
        qualifications,
        passive_spy_benchmark,
        ranking_order,
        freeze,
    )
    return DevelopmentEvaluationRun(
        run_id,
        first.source_digest,
        year_batches,
        batches,
        qualifications,
        selection,
        passive_spy_benchmark,
        ranking_order,
        freeze,
        first.source_binding,
        _DEVELOPMENT_RUN_SEAL,
    )


def _development_run_id(
    source_binding: DevelopmentSourceBinding,
    year_batches: tuple[CanonicalYearBatch, ...],
    slot_batches: tuple[arch151.DevelopmentEvaluationBatch, ...],
    selection_bias: arch151.SelectionBiasCalculation,
    qualifications: tuple[arch151.DevelopmentQualification, ...],
    passive_spy_benchmark: PassiveBenchmarkCampaign,
    ranking_order: tuple[UUID, ...],
    final_freeze: arch151.FinalCandidateFreeze,
) -> UUID:
    material = {
        "schema": _DEVELOPMENT_RUN_SCHEMA,
        "source_binding_id": str(source_binding.binding_id),
        "source_digest": source_binding.source_digest,
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "year_batch_ids": [str(item.batch_id) for item in year_batches],
        "slot_batch_digests": [item.batch_digest for item in slot_batches],
        "selection_bias_calculation_id": str(selection_bias.calculation_id),
        "qualification_ids": [str(item.qualification_id) for item in qualifications],
        "passive_spy_benchmark_id": str(passive_spy_benchmark.benchmark_id),
        "ranking_order": [str(item) for item in ranking_order],
        "freeze_id": str(final_freeze.freeze_id),
    }
    return _canonical_id(
        _DEVELOPMENT_RUN_NAMESPACE,
        _DEVELOPMENT_RUN_SCHEMA,
        material,
    )


def _aggregate_report_material(
    aggregate: arch151.DevelopmentAggregate,
) -> dict[str, object]:
    return {
        "slot_id": str(aggregate.slot_id),
        "economics_case": aggregate.economics_case.value,
        "net_return": arch151._decimal_text(aggregate.net_return),
        "profit_factor": aggregate.profit_factor.canonical_material(),
        "pre_cost_profit_factor": (
            aggregate.pre_cost_profit_factor.canonical_material()
        ),
        "positive_scored_years": aggregate.positive_scored_years,
        "profitable_scored_years": aggregate.profitable_scored_years,
        "worst_scored_year_return": arch151._decimal_text(
            aggregate.worst_scored_year_return
        ),
        "max_drawdown": arch151._decimal_text(aggregate.max_drawdown),
        "average_round_trips_per_year": arch151._decimal_text(
            aggregate.average_round_trips_per_year
        ),
        "active_session_fraction": arch151._decimal_text(
            aggregate.active_session_fraction
        ),
        "median_round_trips_per_active_session": arch151._decimal_text(
            aggregate.median_round_trips_per_active_session
        ),
        "sharpe": (
            arch151._decimal_text(aggregate.sharpe)
            if aggregate.sharpe is not None
            else None
        ),
        "turnover": arch151._decimal_text(aggregate.turnover),
    }


def _slot_year_report_material(replay: SlotYearReplay) -> dict[str, object]:
    sessions = replay.sessions
    return {
        "replay_id": str(replay.replay_id),
        "replay_digest": replay.replay_digest,
        "slot_id": str(replay.slot.slot_id),
        "program_id": str(replay.slot.program_id),
        "symbol": replay.slot.symbol,
        "scored_year": replay.scored_year,
        "economics_case": replay.cost_case.value,
        "complete": replay.complete,
        "session_count": len(sessions),
        "trade_count": len(replay.trades),
        "signal_counts": {
            "generated": sum(item.generated_signal_count for item in sessions),
            "eligible": sum(item.eligible_signal_count for item in sessions),
            "executed": sum(item.executed_signal_count for item in sessions),
            "expired": sum(item.expired_signal_count for item in sessions),
            "blocked": sum(item.blocked_signal_count for item in sessions),
        },
        "initial_equity": arch151._decimal_text(replay.initial_equity),
        "final_equity": (
            arch151._decimal_text(replay.final_equity)
            if replay.final_equity is not None
            else None
        ),
        "net_return": (
            arch151._decimal_text(replay.net_return)
            if replay.net_return is not None
            else None
        ),
        "gross_trade_pnl": (
            arch151._decimal_text(replay.gross_trade_pnl)
            if replay.gross_trade_pnl is not None
            else None
        ),
        "total_adverse_cost": (
            arch151._decimal_text(replay.total_adverse_cost)
            if replay.total_adverse_cost is not None
            else None
        ),
        "fill_notional": (
            arch151._decimal_text(replay.fill_notional)
            if replay.fill_notional is not None
            else None
        ),
        "turnover": (
            arch151._decimal_text(replay.turnover)
            if replay.turnover is not None
            else None
        ),
        "maximum_drawdown": (
            arch151._decimal_text(replay.maximum_drawdown)
            if replay.maximum_drawdown is not None
            else None
        ),
        "failure": (
            {
                "failure_id": str(replay.failure.failure_id),
                "kind": replay.failure.kind.value,
                "evidence_digest": replay.failure.evidence_digest,
            }
            if replay.failure is not None
            else None
        ),
    }


def _distribution_summary(values: tuple[Decimal, ...]) -> NumericDistribution:
    ordered = tuple(sorted(values))
    if not ordered:
        return NumericDistribution(0, None, None, None, None, None, None)
    count = len(ordered)
    with localcontext(arch151._DECIMAL_CONTEXT):
        if count % 2:
            median = ordered[count // 2]
        else:
            median = (ordered[count // 2 - 1] + ordered[count // 2]) / Decimal(2)
        mean = sum(ordered, Decimal(0)) / Decimal(count)
    first_rank = max(1, (count + 3) // 4)
    third_rank = max(1, (3 * count + 3) // 4)
    return NumericDistribution(
        count,
        mean,
        median,
        ordered[0],
        ordered[first_rank - 1],
        ordered[third_rank - 1],
        ordered[-1],
    )


def _holding_minutes(trade: TradeRecord) -> Decimal:
    elapsed = trade.exit.timestamp - trade.entry.timestamp
    whole_seconds = elapsed.days * 86_400 + elapsed.seconds
    with localcontext(arch151._DECIMAL_CONTEXT):
        return Decimal(whole_seconds) / Decimal(60)


def _economic_diagnostic_material(record: EconomicDiagnostic) -> dict[str, object]:
    return {
        item.name: _canonical_output_material(getattr(record, item.name))
        for item in fields(record)
        if item.name != "diagnostic_id"
    }


def _economic_diagnostic_id(record: EconomicDiagnostic) -> UUID:
    return _canonical_id(
        _DIAGNOSTICS_NAMESPACE,
        "arch151-economic-diagnostic/v1",
        _economic_diagnostic_material(record),
    )


def _monthly_return_diagnostics(
    replays: tuple[SlotYearReplay, ...], years: tuple[int, ...]
) -> tuple[MonthlyReturnDiagnostic, ...]:
    scheduled = tuple(
        session
        for year in years
        for session in arch151._published_sessions_for_year(year)
    )
    sessions_by_date = {
        item.session_date: item for replay in replays for item in replay.sessions
    }
    if len(sessions_by_date) != sum(len(item.sessions) for item in replays):
        raise EvaluationIntegrityError("diagnostic session dates are duplicated")
    result: list[MonthlyReturnDiagnostic] = []
    for year in years:
        for month in range(1, 13):
            month_sessions = tuple(
                item for item in scheduled if item.year == year and item.month == month
            )
            if not month_sessions:
                continue
            session_records = tuple(
                sessions_by_date.get(item) for item in month_sessions
            )
            complete = all(
                item is not None and item.session_return is not None
                for item in session_records
            )
            if complete:
                with localcontext(arch151._DECIMAL_CONTEXT):
                    compounded = Decimal(1)
                    for item in session_records:
                        assert item is not None and item.session_return is not None
                        compounded *= Decimal(1) + item.session_return
                    monthly_return = compounded - Decimal(1)
            else:
                monthly_return = None
            result.append(
                MonthlyReturnDiagnostic(
                    year, month, len(month_sessions), complete, monthly_return
                )
            )
    return tuple(result)


def _sum_trade_values(
    trades: tuple[TradeRecord, ...], reason: ExitReason, *, gross: bool
) -> Decimal:
    with localcontext(arch151._DECIMAL_CONTEXT):
        return sum(
            (
                (item.gross_pnl if gross else item.net_pnl)
                for item in trades
                if item.exit_reason is reason
            ),
            Decimal(0),
        )


def _economic_diagnostic(
    replays: tuple[SlotYearReplay, ...], scope: DiagnosticScope
) -> EconomicDiagnostic:
    if not replays or type(replays) is not tuple:
        raise EvaluationIntegrityError("economic diagnostics need replay records")
    first = replays[0]
    if any(
        item.slot.slot_id != first.slot.slot_id
        or item.cost_case is not first.cost_case
        or item.source_digest != first.source_digest
        for item in replays
    ):
        raise EvaluationIntegrityError("economic diagnostic mixes replay identities")
    if scope is DiagnosticScope.SCORED_YEAR:
        if len(replays) != 1:
            raise EvaluationIntegrityError("annual diagnostic requires one replay")
        years = (first.scored_year,)
    elif scope is DiagnosticScope.FIVE_YEAR_CAMPAIGN:
        if tuple(item.scored_year for item in replays) != arch151.SCORED_YEARS:
            raise EvaluationIntegrityError(
                "campaign diagnostic requires five ordered years"
            )
        years = arch151.SCORED_YEARS
    else:
        raise TypeError("diagnostic scope must use the closed enum")
    sessions = tuple(session for item in replays for session in item.sessions)
    trades = tuple(trade for item in replays for trade in item.trades)
    complete = all(item.complete and item.failure is None for item in replays)
    expected_sessions = tuple(
        session
        for year in years
        for session in arch151._published_sessions_for_year(year)
    )
    complete = (
        complete and tuple(item.session_date for item in sessions) == expected_sessions
    )
    with localcontext(arch151._DECIMAL_CONTEXT):
        gross_trade_pnl = sum((item.gross_pnl for item in trades), Decimal(0))
        net_trade_pnl = sum((item.net_pnl for item in trades), Decimal(0))
        adverse_cost = sum((item.total_adverse_cost for item in trades), Decimal(0))
    net_wins = tuple(item.net_pnl for item in trades if item.net_pnl > 0)
    net_losses = tuple(
        item.net_pnl.copy_negate() for item in trades if item.net_pnl < 0
    )
    with localcontext(arch151._DECIMAL_CONTEXT):
        gross_expectancy = (
            sum((item.gross_pnl for item in trades), Decimal(0)) / Decimal(len(trades))
            if trades
            else None
        )
        net_expectancy = (
            sum((item.net_pnl for item in trades), Decimal(0)) / Decimal(len(trades))
            if trades
            else None
        )
        win_rate = Decimal(len(net_wins)) / Decimal(len(trades)) if trades else None
        average_win = (
            sum(net_wins, Decimal(0)) / Decimal(len(net_wins)) if net_wins else None
        )
        average_loss = (
            sum(net_losses, Decimal(0)) / Decimal(len(net_losses))
            if net_losses
            else None
        )
        payoff = (
            average_win / average_loss
            if average_win is not None and average_loss is not None and average_loss > 0
            else None
        )
        compounded_return = None
        if complete:
            compounded = Decimal(1)
            for session in sessions:
                assert session.session_return is not None
                compounded *= Decimal(1) + session.session_return
            compounded_return = compounded - Decimal(1)
        held_minutes = sum((_holding_minutes(item) for item in trades), Decimal(0))
    months = _monthly_return_diagnostics(replays, years)
    available_months = tuple(item for item in months if item.net_return is not None)
    positive_month_count = sum(item.net_return > 0 for item in available_months)
    with localcontext(arch151._DECIMAL_CONTEXT):
        positive_month_fraction = (
            Decimal(positive_month_count) / Decimal(len(available_months))
            if available_months
            else None
        )
    scheduled_minutes = 0
    for year in years:
        for session_date in arch151._published_sessions_for_year(year):
            schedule = arch151._SESSION_AUTHORITY.schedule_for(session_date)
            assert schedule is not None
            scheduled_minutes += int(
                (schedule.closes_at - schedule.opens_at).total_seconds() // 60
            )
    with localcontext(arch151._DECIMAL_CONTEXT):
        time_fraction = held_minutes / Decimal(scheduled_minutes) if complete else None
    exit_records = tuple(
        ExitReasonDiagnostic(
            reason,
            sum(item.exit_reason is reason for item in trades),
            _sum_trade_values(trades, reason, gross=True),
            _sum_trade_values(trades, reason, gross=False),
        )
        for reason in ExitReason
    )
    rejection_counts = tuple(
        RejectionReasonDiagnostic(
            reason,
            sum(
                rejection.reason is reason
                for session in sessions
                for rejection in session.signal_rejections
            ),
        )
        for reason in RejectionReason
    )
    diagnostic = EconomicDiagnostic(
        UUID(int=0),
        scope,
        first.slot.slot_id,
        first.slot.program_id,
        first.slot.symbol,
        first.scored_year if scope is DiagnosticScope.SCORED_YEAR else None,
        first.cost_case,
        tuple(item.replay_id for item in replays),
        complete,
        len(trades),
        tuple(
            TradeDiagnostic(
                item.trade_id,
                item.signal_timestamp,
                item.entry.timestamp,
                item.exit.timestamp,
                item.exit_reason,
                item.gross_pnl,
                item.net_pnl,
                item.total_adverse_cost,
                _holding_minutes(item),
                item.mfe_return,
                item.mae_return,
                item.excursion_minute_count,
            )
            for item in trades
        ),
        gross_trade_pnl,
        net_trade_pnl,
        adverse_cost,
        gross_expectancy,
        net_expectancy,
        win_rate,
        average_win,
        average_loss,
        payoff,
        compounded_return,
        months,
        positive_month_count,
        len(available_months),
        positive_month_fraction,
        _distribution_summary(tuple(_holding_minutes(item) for item in trades)),
        held_minutes,
        scheduled_minutes,
        time_fraction,
        exit_records,
        sum(item.generated_signal_count for item in sessions),
        sum(item.eligible_signal_count for item in sessions),
        sum(item.executed_signal_count for item in sessions),
        sum(item.expired_signal_count for item in sessions),
        sum(item.blocked_signal_count for item in sessions),
        rejection_counts,
        _distribution_summary(
            tuple(item.mfe_return for item in trades if item.mfe_return is not None)
        ),
        _distribution_summary(
            tuple(item.mae_return for item in trades if item.mae_return is not None)
        ),
    )
    return replace(diagnostic, diagnostic_id=_economic_diagnostic_id(diagnostic))


def _trade_path_signature(replay: SlotYearReplay) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.signal_timestamp,
            item.entry.timestamp,
            item.exit.timestamp,
            item.exit_reason,
        )
        for item in replay.trades
    )


def _cost_drag_diagnostic(
    replay: SlotYearReplay,
    zero_replay: SlotYearReplay,
    scope: DiagnosticScope,
    replay_group: tuple[SlotYearReplay, ...],
    zero_group: tuple[SlotYearReplay, ...],
) -> CostDragDiagnostic:
    if replay.cost_case is arch151.FillCostCase.ZERO:
        raise EvaluationIntegrityError("ZERO cannot be a compared cost case")
    if scope is DiagnosticScope.SCORED_YEAR:
        if len(replay_group) != 1 or len(zero_group) != 1:
            raise EvaluationIntegrityError("annual cost comparison has mixed years")
    if scope is DiagnosticScope.FIVE_YEAR_CAMPAIGN and (
        tuple(item.scored_year for item in replay_group) != arch151.SCORED_YEARS
        or tuple(item.scored_year for item in zero_group) != arch151.SCORED_YEARS
    ):
        raise EvaluationIntegrityError("campaign cost comparison lacks exact years")
    if any(
        item.slot.slot_id != replay.slot.slot_id
        or item.cost_case is not replay.cost_case
        for item in replay_group
    ) or any(
        item.slot.slot_id != zero_replay.slot.slot_id
        or item.cost_case is not arch151.FillCostCase.ZERO
        for item in zero_group
    ):
        raise EvaluationIntegrityError("cost comparison mixes slots or economics")
    if not all(item.complete for item in (*replay_group, *zero_group)):
        relationship = CostPathRelationship.INCOMPLETE
    elif tuple(_trade_path_signature(item) for item in replay_group) == tuple(
        _trade_path_signature(item) for item in zero_group
    ):
        relationship = CostPathRelationship.IDENTICAL_ENTRY_EXIT_PATH
    else:
        relationship = CostPathRelationship.ENTRY_EXIT_PATH_CHANGED
    compared = _economic_diagnostic(replay_group, scope)
    zero = _economic_diagnostic(zero_group, scope)
    with localcontext(arch151._DECIMAL_CONTEXT):
        delta = (
            compared.compounded_net_return - zero.compounded_net_return
            if compared.compounded_net_return is not None
            and zero.compounded_net_return is not None
            else None
        )
        cost_delta = compared.total_adverse_cost - zero.total_adverse_cost
    return CostDragDiagnostic(
        replay.slot.slot_id,
        replay.scored_year if scope is DiagnosticScope.SCORED_YEAR else None,
        replay.cost_case,
        arch151.FillCostCase.ZERO,
        relationship,
        delta,
        cost_delta,
    )


def _research_diagnostics_material(
    run: DevelopmentEvaluationRun,
) -> dict[str, object]:
    replays_by_key = {
        (item.slot.slot_id, item.scored_year, item.cost_case): item
        for batch in run.year_batches
        for item in batch.evaluations
    }
    annual = tuple(
        _economic_diagnostic(
            (replays_by_key[(slot.slot_id, year, case)],),
            DiagnosticScope.SCORED_YEAR,
        )
        for slot in arch151.CANONICAL_SLOTS
        for year in arch151.SCORED_YEARS
        for case in arch151.EVALUATION_ECONOMICS_ORDER
    )
    campaigns: list[EconomicDiagnostic] = []
    cost_drag: list[CostDragDiagnostic] = []
    for slot in arch151.CANONICAL_SLOTS:
        for case in arch151.EVALUATION_ECONOMICS_ORDER:
            case_replays = tuple(
                replays_by_key[(slot.slot_id, year, case)]
                for year in arch151.SCORED_YEARS
            )
            campaigns.append(
                _economic_diagnostic(case_replays, DiagnosticScope.FIVE_YEAR_CAMPAIGN)
            )
            if case is not arch151.FillCostCase.ZERO:
                zero_replays = tuple(
                    replays_by_key[(slot.slot_id, year, arch151.FillCostCase.ZERO)]
                    for year in arch151.SCORED_YEARS
                )
                cost_drag.append(
                    _cost_drag_diagnostic(
                        case_replays[0],
                        zero_replays[0],
                        DiagnosticScope.FIVE_YEAR_CAMPAIGN,
                        case_replays,
                        zero_replays,
                    )
                )
    for slot in arch151.CANONICAL_SLOTS:
        for year in arch151.SCORED_YEARS:
            zero = replays_by_key[(slot.slot_id, year, arch151.FillCostCase.ZERO)]
            for case in (arch151.FillCostCase.BASE, arch151.FillCostCase.STRESS):
                cost_drag.append(
                    _cost_drag_diagnostic(
                        replays_by_key[(slot.slot_id, year, case)],
                        zero,
                        DiagnosticScope.SCORED_YEAR,
                        (replays_by_key[(slot.slot_id, year, case)],),
                        (zero,),
                    )
                )
    benchmarks = tuple(item.passive_spy_benchmark for item in run.year_batches)
    return {
        "schema": "arch151-research-diagnostics/v1",
        "qualification_or_ranking_input": False,
        "annual_slot_economics": [
            _economic_diagnostic_material(item) for item in annual
        ],
        "five_year_slot_economics": [
            _economic_diagnostic_material(item) for item in campaigns
        ],
        "cost_drag_vs_zero": [_canonical_output_material(item) for item in cost_drag],
        "passive_spy_benchmark": {
            "metric": "ADJUSTED_PRICE_RETURN",
            "dividend_cashflow_total_return_reconstructed": False,
            "adjustment": arch150_data.ADJUSTMENT,
            "adjustment_semantics": arch150_data.ADJUSTMENT_SEMANTICS,
            "price_basis": arch150_data.PRICE_BASIS,
            "annual": [_canonical_output_material(item) for item in benchmarks],
            "five_year": _canonical_output_material(run.passive_spy_benchmark),
        },
        "mfe_mae_convention": (
            "entry-execution-price-relative extrema from observed one-minute bars "
            "fully held through bar completion; exclude the exit minute when its "
            "intrabar order is unknown"
        ),
    }


def _development_report_material(run: DevelopmentEvaluationRun) -> dict[str, object]:
    records = [
        {
            "evaluation_id": str(record.evaluation_id),
            "slot_id": str(record.slot_id),
            "program_id": str(record.program_id),
            "symbol": record.symbol,
            "fold": {
                "fold_id": str(record.fold.fold_id),
                "name": record.fold.name,
                "calibration_start": record.fold.calibration_start.isoformat(),
                "calibration_end_exclusive": (
                    record.fold.calibration_end_exclusive.isoformat()
                ),
                "scored_start": record.fold.scored_start.isoformat(),
                "scored_end_exclusive": record.fold.scored_end_exclusive.isoformat(),
                "scored_year": record.fold.scored_year,
            },
            "economics_case": record.economics_case.value,
            "metrics": arch151._fold_metrics_material(record.metrics),
        }
        for batch in run.slot_batches
        for record in batch.records
    ]
    if len(records) != 480:
        raise EvaluationIntegrityError(
            "development report requires all 480 canonical fold records"
        )
    selection = run.selection_bias
    selection_material = {
        "calculation_id": str(selection.calculation_id),
        "status": selection.status.value,
        "population_digest": selection.population_digest,
        "effective_trial_count": selection.effective_trial_count,
        "unavailable_reason": (
            selection.unavailable_reason.value
            if selection.unavailable_reason is not None
            else None
        ),
        "trial_diagnostics": [
            item.canonical_material() for item in selection.trial_diagnostics
        ],
        "affected_trial_slot_ids": [
            str(item) for item in selection.affected_trial_slot_ids
        ],
        "descriptive_economic_order": [
            str(item) for item in selection.descriptive_economic_order
        ],
        "evidence": [
            {
                "evidence_id": str(item.evidence_id),
                "evidence_digest": item.evidence_digest,
                "candidate_slot_id": str(item.candidate_slot_id),
                "development_batch_digest": item.development_batch_digest,
                "population_digest": item.population_digest,
                "ledger_id": str(item.ledger_id),
                "effective_trial_count": item.effective_trial_count,
                "observation_count": item.observation_count,
                "daily_sharpe": arch151._decimal_text(item.daily_sharpe),
                "expected_max_daily_sharpe": arch151._decimal_text(
                    item.expected_max_daily_sharpe
                ),
                "skew": arch151._decimal_text(item.skew),
                "non_excess_kurtosis": arch151._decimal_text(item.non_excess_kurtosis),
                "probability": arch151._decimal_text(item.probability),
            }
            for item in selection.evidence
        ],
    }
    qualifications = [
        {
            "qualification_id": str(item.qualification_id),
            "slot_id": str(item.slot_id),
            "batch_digest": item.batch_digest,
            "aggregate": _aggregate_report_material(item.aggregate),
            "economic_rejection_reasons": [
                reason.value for reason in item.economic_rejection_reasons
            ],
            "rejection_reasons": [reason.value for reason in item.rejection_reasons],
            "selection_bias_status": item.selection_bias_status.value,
            "economically_qualified": item.economically_qualified,
            "qualified": item.qualified,
        }
        for item in run.qualifications
    ]
    freeze = run.final_freeze
    return {
        "schema": _DEVELOPMENT_REPORT_SCHEMA,
        "run": {
            "run_id": str(run.run_id),
            "source_digest": run.source_digest,
            "source_binding": run.source_binding.canonical_material(),
        },
        "manifest": {
            "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
            "fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
            "program_ids": [
                str(arch151.program_id(item)) for item in arch151.CANONICAL_PROGRAMS
            ],
            "ordered_slot_ids": [str(item.slot_id) for item in arch151.CANONICAL_SLOTS],
        },
        "year_batches": [
            {
                "batch_id": str(item.batch_id),
                "scored_year": item.scored_year,
                "source_digest": item.source_digest,
                "source_binding_id": str(item.source_binding.binding_id),
                "manifest_id": str(item.manifest_id),
                "manifest_fingerprint": item.manifest_fingerprint,
                "passive_spy_benchmark_id": str(
                    item.passive_spy_benchmark.benchmark_id
                ),
                "replay_outputs": [
                    {
                        "replay_id": str(replay.replay_id),
                        "replay_digest": replay.replay_digest,
                    }
                    for replay in item.evaluations
                ],
            }
            for item in run.year_batches
        ],
        "slot_year_replays": [
            _slot_year_report_material(replay)
            for batch in run.year_batches
            for replay in batch.evaluations
        ],
        "slot_batches": [
            {
                "slot_id": str(item.slot_id),
                "batch_digest": item.batch_digest,
                "record_count": len(item.records),
            }
            for item in run.slot_batches
        ],
        "record_count": len(records),
        "fold_records": records,
        "qualifications": qualifications,
        "selection_bias": selection_material,
        "research_diagnostics": _research_diagnostics_material(run),
        "ranking_order": [str(item) for item in run.ranking_order],
        "final_freeze": {
            "freeze_id": str(freeze.freeze_id),
            "fingerprint": freeze.fingerprint,
            "source_manifest_id": str(freeze.source_manifest_id),
            "batch_digests": list(freeze.batch_digests),
            "economically_qualified_slot_ids": [
                str(item) for item in freeze.economically_qualified_slot_ids
            ],
            "ranking_order": [str(item) for item in freeze.ranking_order],
            "selection_bias_calculation_id": (
                str(freeze.selection_bias_calculation_id)
                if freeze.selection_bias_calculation_id is not None
                else None
            ),
            "selection_bias_evidence_digests": list(
                freeze.selection_bias_evidence_digests
            ),
            "candidate_slot_id": (
                str(freeze.candidate_slot_id)
                if freeze.candidate_slot_id is not None
                else None
            ),
            "candidate_program_id": (
                str(freeze.candidate_program_id)
                if freeze.candidate_program_id is not None
                else None
            ),
            "selection_bias_status": freeze.selection_bias_status.value,
            "status": freeze.status.value,
        },
    }


def serialize_development_evaluation(
    run: DevelopmentEvaluationRun,
) -> DevelopmentEvaluationReport:
    """Create a canonical report bound to a recomposed source-owned 480-record run.

    The operation returns immutable bytes in memory. It has no report-file,
    custody, holdout, or extension reader/writer surface.
    """

    if (
        type(run) is not DevelopmentEvaluationRun
        or getattr(run, "_seal", None) is not _DEVELOPMENT_RUN_SEAL
    ):
        raise arch151.AuthorizationUnavailableError(
            "development report requires a source-owned composed run"
        )
    recomposed = compose_development_evaluation(run.year_batches)
    if run != recomposed:
        raise EvaluationIntegrityError(
            "development report input differs from canonical recomposition"
        )
    canonical = arch151._canonical_json(_development_report_material(run))
    digest = sha256(canonical).hexdigest()
    report_id = _canonical_id(
        _DEVELOPMENT_REPORT_NAMESPACE,
        _DEVELOPMENT_REPORT_SCHEMA,
        {"run_id": str(run.run_id), "sha256": digest},
    )
    return DevelopmentEvaluationReport(
        _seal=_DEVELOPMENT_REPORT_SEAL,
        report_id=report_id,
        run_id=run.run_id,
        source_binding_id=run.source_binding.binding_id,
        manifest_id=arch151.CANONICAL_MANIFEST.manifest_id,
        manifest_fingerprint=arch151.CANONICAL_MANIFEST.fingerprint,
        record_count=run.fold_evaluation_count,
        canonical_json_bytes=canonical,
        sha256_digest=digest,
    )


def authenticate_development_evidence(
    run: DevelopmentEvaluationRun,
    report: DevelopmentEvaluationReport,
    source_attestation: object,
) -> arch151.AuthenticatedDevelopmentEvidence:
    """Bind accepted-source run/report/freeze/DSR to the operator's receipt.

    Synthetic histories and caller-built reports are rejected. This issuer has
    no custody, holdout, extension, or later-period reader surface.
    """

    if (
        type(run) is not DevelopmentEvaluationRun
        or getattr(run, "_seal", None) is not _DEVELOPMENT_RUN_SEAL
        or type(report) is not DevelopmentEvaluationReport
        or getattr(report, "_seal", None) is not _DEVELOPMENT_REPORT_SEAL
    ):
        raise arch151.AuthorizationUnavailableError(
            "authenticated evidence requires a sealed source-owned run and report"
        )
    if run.source_binding.kind is not DevelopmentSourceKind.ARCH150_D1R_ACCEPTED:
        raise arch151.AuthorizationUnavailableError(
            "synthetic development runs cannot issue authenticated development evidence"
        )
    selection = run.selection_bias
    freeze = run.final_freeze
    if (
        run.fold_evaluation_count != 480
        or len(run.year_batches) != len(arch151.SCORED_YEARS)
        or any(not batch.complete for batch in run.year_batches)
        or tuple(batch.scored_year for batch in run.year_batches)
        != arch151.SCORED_YEARS
        or report.record_count != 480
        or report.run_id != run.run_id
        or report.source_binding_id != run.source_binding.binding_id
        or report.manifest_id != arch151.CANONICAL_MANIFEST.manifest_id
        or report.manifest_fingerprint != arch151.CANONICAL_MANIFEST.fingerprint
        or sha256(report.canonical_json_bytes).hexdigest() != report.sha256
        or serialize_development_evaluation(run) != report
        or freeze.status is not arch151.FinalFreezeStatus.ONE_CANDIDATE_FROZEN
        or freeze.candidate_slot_id is None
        or freeze.selection_bias_status is not arch151.SelectionBiasStatus.DSR_VERIFIED
        or selection.status is not arch151.SelectionBiasStatus.DSR_VERIFIED
        or freeze.selection_bias_calculation_id != selection.calculation_id
        or freeze.batch_digests != tuple(item.batch_digest for item in run.slot_batches)
        or freeze.selection_bias_evidence_digests
        != tuple(item.evidence_digest for item in selection.evidence)
        or len(selection.evidence) != len(arch151.CANONICAL_SLOTS)
        or len(selection.trial_diagnostics) != len(arch151.CANONICAL_SLOTS)
    ):
        raise arch151.AuthorizationUnavailableError(
            "development run, report, freeze, or full DSR population is "
            "incomplete or inconsistent"
        )
    for slot, batch, evidence in zip(
        arch151.CANONICAL_SLOTS, run.slot_batches, selection.evidence, strict=True
    ):
        if (
            batch.slot_id != slot.slot_id
            or evidence.candidate_slot_id != slot.slot_id
            or evidence.development_batch_digest != batch.batch_digest
            or evidence.population_digest != selection.population_digest
            or evidence.ledger_id != arch151.SELECTION_BIAS_INPUT.ledger_id
            or evidence.effective_trial_count
            != arch151.SELECTION_BIAS_INPUT.effective_trial_count
        ):
            raise arch151.AuthorizationUnavailableError(
                "development DSR evidence does not bind the full canonical population"
            )
    candidate_index = next(
        index
        for index, slot in enumerate(arch151.CANONICAL_SLOTS)
        if slot.slot_id == freeze.candidate_slot_id
    )
    candidate_evidence = selection.evidence[candidate_index]
    candidate_qualification = run.qualifications[candidate_index]
    if (
        candidate_qualification.slot_id != freeze.candidate_slot_id
        or not candidate_qualification.qualified
        or candidate_evidence.probability
        < arch151.SELECTION_BIAS_INPUT.minimum_probability
    ):
        raise arch151.AuthorizationUnavailableError(
            "the frozen candidate is not qualified by the complete development evidence"
        )
    from trading_bot.experiments import (
        arch151_intraday_walkforward_operator as operator,
    )

    source_attestation = operator._validate_development_source_attestation(
        run, report, source_attestation
    )
    source_revision = source_attestation.source_revision
    current_revision = operator._read_source_revision()
    if current_revision != source_revision:
        raise arch151.AuthorizationUnavailableError(
            "operator source attestation revision differs from current source"
        )
    invocation_id = source_attestation.invocation_id
    source_revision_digest = source_attestation.source_revision_digest
    return arch151.AuthenticatedDevelopmentEvidence(
        _seal=arch151._AUTHENTICATED_DEVELOPMENT_EVIDENCE_SEAL,
        freeze_id=freeze.freeze_id,
        freeze_fingerprint=freeze.fingerprint,
        candidate_slot_id=freeze.candidate_slot_id,
        source_manifest_id=freeze.source_manifest_id,
        manifest_fingerprint=arch151.CANONICAL_MANIFEST.fingerprint,
        batch_digests=tuple(item.batch_digest for item in run.slot_batches),
        year_batch_ids=tuple(item.batch_id for item in run.year_batches),
        run_id=run.run_id,
        report_id=report.report_id,
        report_sha256=report.sha256,
        record_count=report.record_count,
        source_kind=run.source_binding.kind.value,
        source_binding_id=run.source_binding.binding_id,
        source_digest=run.source_digest,
        source_branch=source_revision.branch,
        source_origin=source_revision.origin,
        source_head=source_revision.head,
        source_tree=source_revision.tree,
        invocation_id=invocation_id,
        source_revision_digest=source_revision_digest,
        selection_bias_calculation_id=selection.calculation_id,
        selection_bias_population_digest=selection.population_digest,
        selection_bias_ledger_id=arch151.SELECTION_BIAS_INPUT.ledger_id,
        selection_bias_effective_trial_count=selection.effective_trial_count,
        selection_bias_evidence_ids=tuple(
            item.evidence_id for item in selection.evidence
        ),
        selection_bias_evidence_digests=tuple(
            item.evidence_digest for item in selection.evidence
        ),
    )


def evaluate_full_development_history(
    history: arch151.Arch150D1RSourceHistory,
) -> DevelopmentEvaluationRun:
    """Run all five sealed development years from accepted D1R history only.

    This function is an explicit future evaluator operation. Import and the
    synthetic tests never invoke the fixed-root custody loader or this replay.
    """

    if type(history) is not arch151.Arch150D1RSourceHistory:
        raise arch151.AuthorizationUnavailableError(
            "full development evaluation requires accepted Arch150 D1R source history"
        )
    year_batches = tuple(
        simulate_canonical_year(history, year) for year in arch151.SCORED_YEARS
    )
    return compose_development_evaluation(year_batches)


__all__ = (
    "BenchmarkStatus",
    "BenchmarkUnavailableReason",
    "CanonicalYearBatch",
    "CostDragDiagnostic",
    "CostPathRelationship",
    "DiagnosticScope",
    "DevelopmentEvaluationReport",
    "DevelopmentEvaluationRun",
    "DevelopmentSourceBinding",
    "DevelopmentSourceKind",
    "EvaluationIntegrityError",
    "ExitReason",
    "FillRecord",
    "FillSide",
    "EconomicDiagnostic",
    "ExitReasonDiagnostic",
    "MonthlyReturnDiagnostic",
    "NumericDistribution",
    "PassiveBenchmarkCampaign",
    "PassiveBenchmarkYear",
    "ReplayFailureEvidence",
    "ReplayFailureKind",
    "SignalDisposition",
    "SignalLifecycleOutcome",
    "SessionReplayRecord",
    "SignalRejection",
    "SlotYearReplay",
    "TradeDiagnostic",
    "TradeRecord",
    "compose_development_evaluation",
    "authenticate_development_evidence",
    "evaluate_full_development_history",
    "serialize_development_evaluation",
    "simulate_canonical_year",
)
