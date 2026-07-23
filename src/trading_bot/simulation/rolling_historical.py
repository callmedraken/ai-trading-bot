"""Deterministic rolling historical optimized-simulation orchestration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain._validation import normalize_utc
from trading_bot.execution import PaperFillPolicy
from trading_bot.execution.state_fingerprints import (
    engine_snapshot,
    engine_state_id,
    ledger_snapshot,
    ledger_state_id,
)
from trading_bot.market_data import (
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
    Timeframe,
)
from trading_bot.market_data.exceptions import HistoricalDataValidationError
from trading_bot.portfolio import (
    ForecastHorizon,
    HistoricalReturnScenarioFactory,
    HistoricalScenarioGenerationError,
    HistoricalScenarioGenerationPolicy,
    HistoricalScenarioGenerationRequest,
    HistoricalScenarioGenerationResult,
    MeanCvarOptimizationParameters,
    MetadataEntry,
    PortfolioConstraints,
)
from trading_bot.portfolio_analytics import (
    InconsistentOptimizedSimulationPerformanceResultError,
    InvalidOptimizedSimulationPerformanceRequestError,
    OptimizedSimulationPerformanceAnalyzer,
    OptimizedSimulationPerformanceReconciliationError,
    OptimizedSimulationPerformanceRequest,
    OptimizedSimulationPerformanceResult,
    OptimizedSimulationValuationBasis,
    OptimizedSimulationValuationError,
    OptimizedSimulationValuationPolicy,
)
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import PaperPortfolioCyclePrice
from trading_bot.simulation.exceptions import (
    InconsistentRollingHistoricalSimulationResultError,
    InvalidOptimizedPaperSimulationFrameError,
    InvalidOptimizedPaperSimulationRequestError,
    InvalidRollingHistoricalSimulationRequestError,
    OptimizedPaperSimulationError,
    RollingHistoricalFrameConstructionError,
    RollingHistoricalPerformanceError,
    RollingHistoricalScenarioGenerationError,
    RollingHistoricalScheduleError,
    RollingHistoricalSimulationExecutionError,
    RollingHistoricalSimulationReconciliationError,
    RollingHistoricalWindowError,
)
from trading_bot.simulation.optimized_paper_portfolio import (
    OptimizedPaperPortfolioSimulator,
    OptimizedPaperSimulationFrame,
    OptimizedPaperSimulationRequest,
    OptimizedPaperSimulationResult,
)

_ZERO = Decimal("0")
_VERSION = "rolling-historical-optimized-simulation-v1"
_NAMESPACE = UUID("9be7f6e5-bfde-58c9-92a4-8e66f5959472")
_RESERVED_PREFIX = "rolling_historical_simulation_"


class RollingHistoricalExecutionPriceField(StrEnum):
    """Supported historical fields for cycle prices."""

    CLOSE = "CLOSE"


@dataclass(frozen=True, slots=True)
class RollingHistoricalWindowPolicy:
    """Fixed trailing observation-window policy."""

    observation_count: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.observation_count, int)
            or isinstance(self.observation_count, bool)
            or self.observation_count < 2
        ):
            raise InvalidRollingHistoricalSimulationRequestError(
                "observation_count must be an integer of at least two"
            )


@dataclass(frozen=True, slots=True)
class RollingHistoricalExecutionPricePolicy:
    """Explicit historical fields used for risk and paper fills."""

    risk_price_field: RollingHistoricalExecutionPriceField = (
        RollingHistoricalExecutionPriceField.CLOSE
    )
    fill_reference_price_field: RollingHistoricalExecutionPriceField = (
        RollingHistoricalExecutionPriceField.CLOSE
    )

    def __post_init__(self) -> None:
        if self.risk_price_field is not RollingHistoricalExecutionPriceField.CLOSE:
            raise InvalidRollingHistoricalSimulationRequestError(
                "only CLOSE risk prices are supported"
            )
        if (
            self.fill_reference_price_field
            is not RollingHistoricalExecutionPriceField.CLOSE
        ):
            raise InvalidRollingHistoricalSimulationRequestError(
                "only CLOSE fill-reference prices are supported"
            )


@dataclass(frozen=True, slots=True)
class RollingHistoricalCycleTimingPolicy:
    """Deterministic offsets from each rebalance timestamp."""

    submission_offset: timedelta = timedelta(0)
    fill_offset: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        if (
            type(self.submission_offset) is not timedelta
            or type(self.fill_offset) is not timedelta
        ):
            raise InvalidRollingHistoricalSimulationRequestError(
                "timing offsets must be timedelta values"
            )
        if not timedelta(0) <= self.submission_offset <= self.fill_offset:
            raise InvalidRollingHistoricalSimulationRequestError(
                "timing offsets must satisfy 0 <= submission <= fill"
            )


@dataclass(frozen=True, slots=True)
class RollingHistoricalSimulationRequest:
    """Complete immutable input for one rolling historical run."""

    request_id: UUID
    historical_data: MultiSymbolHistoricalDataResult
    rebalance_timestamps: tuple[datetime, ...]
    window_policy: RollingHistoricalWindowPolicy
    scenario_policy: HistoricalScenarioGenerationPolicy
    execution_price_policy: RollingHistoricalExecutionPricePolicy
    timing_policy: RollingHistoricalCycleTimingPolicy
    scenario_cash_return: Decimal
    scenario_source_name: str
    optimization_parameters: MeanCvarOptimizationParameters
    risk_aversion: Decimal
    portfolio_constraints: PortfolioConstraints
    rebalance_assumptions: RebalanceAssumptions
    proposal_policy: RebalanceProposalPolicy
    proposal_confidence: Decimal | None
    risk_limits: RiskLimits
    risk_policy: PortfolioRiskPolicy
    fill_policy: PaperFillPolicy
    trading_enabled: bool
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidRollingHistoricalSimulationRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if type(self.historical_data) is not MultiSymbolHistoricalDataResult:
            raise error(
                "historical_data must be exactly MultiSymbolHistoricalDataResult"
            )
        for name, expected in (
            ("window_policy", RollingHistoricalWindowPolicy),
            ("scenario_policy", HistoricalScenarioGenerationPolicy),
            ("execution_price_policy", RollingHistoricalExecutionPricePolicy),
            ("timing_policy", RollingHistoricalCycleTimingPolicy),
            ("optimization_parameters", MeanCvarOptimizationParameters),
            ("portfolio_constraints", PortfolioConstraints),
            ("rebalance_assumptions", RebalanceAssumptions),
            ("proposal_policy", RebalanceProposalPolicy),
            ("risk_limits", RiskLimits),
            ("risk_policy", PortfolioRiskPolicy),
            ("fill_policy", PaperFillPolicy),
        ):
            if not isinstance(getattr(self, name), expected):
                raise error(f"{name} must be {expected.__name__}")
        self.window_policy.__post_init__()
        self.scenario_policy.__post_init__()
        self.execution_price_policy.__post_init__()
        self.timing_policy.__post_init__()
        try:
            timestamps = tuple(
                normalize_utc(item, f"rebalance_timestamps[{index}]")
                for index, item in enumerate(self.rebalance_timestamps)
            )
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        cash_return = self.scenario_cash_return
        if (
            not isinstance(cash_return, Decimal)
            or not cash_return.is_finite()
            or cash_return < Decimal("-1")
        ):
            raise error("scenario_cash_return must be a finite Decimal >= -1")
        if (
            not isinstance(self.scenario_source_name, str)
            or not self.scenario_source_name.strip()
        ):
            raise error("scenario_source_name must be nonblank")
        risk_aversion = self.risk_aversion
        if (
            not isinstance(risk_aversion, Decimal)
            or not risk_aversion.is_finite()
            or risk_aversion < _ZERO
        ):
            raise error("risk_aversion must be a finite nonnegative Decimal")
        confidence = self.proposal_confidence
        if confidence is not None and (
            not isinstance(confidence, Decimal)
            or not confidence.is_finite()
            or not _ZERO <= confidence <= Decimal("1")
        ):
            raise error("proposal_confidence must be a finite Decimal from 0 to 1")
        if not isinstance(self.trading_enabled, bool):
            raise error("trading_enabled must be bool")
        if not (
            self.rebalance_assumptions.fixed_commission
            == self.risk_limits.estimated_commission
            == self.fill_policy.fixed_commission
        ):
            raise error("planner, risk, and fill fixed commissions must match")
        try:
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("metadata must be iterable") from caught
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
            raise error(f"{_RESERVED_PREFIX} metadata keys are reserved")
        object.__setattr__(self, "rebalance_timestamps", timestamps)
        object.__setattr__(
            self,
            "scenario_cash_return",
            _ZERO if cash_return == _ZERO else cash_return,
        )
        object.__setattr__(
            self, "risk_aversion", _ZERO if risk_aversion == _ZERO else risk_aversion
        )
        object.__setattr__(
            self, "proposal_confidence", _ZERO if confidence == _ZERO else confidence
        )
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class RollingHistoricalFrameGeneration:
    """One prepared historical window, scenario result, and optimized frame."""

    frame_ordinal: int
    rebalance_timestamp: datetime
    historical_frame_index: int
    window_start_index: int
    window_end_index_inclusive: int
    window_start_timestamp: datetime
    window_end_timestamp: datetime
    source_frame_id: UUID
    scenario_request_id: UUID
    scenario_result: HistoricalScenarioGenerationResult
    optimized_frame_fingerprint: UUID
    optimized_frame: OptimizedPaperSimulationFrame

    def __post_init__(self) -> None:
        error = InconsistentRollingHistoricalSimulationResultError
        for name in (
            "frame_ordinal",
            "historical_frame_index",
            "window_start_index",
            "window_end_index_inclusive",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise error(f"{name} must be a nonnegative integer")
        for name in (
            "rebalance_timestamp",
            "window_start_timestamp",
            "window_end_timestamp",
        ):
            try:
                object.__setattr__(self, name, normalize_utc(getattr(self, name), name))
            except (TypeError, ValueError) as caught:
                raise error(str(caught)) from caught
        for name in (
            "source_frame_id",
            "scenario_request_id",
            "optimized_frame_fingerprint",
        ):
            if not isinstance(getattr(self, name), UUID):
                raise error(f"{name} must be a UUID")
        if not isinstance(
            self.scenario_result, HistoricalScenarioGenerationResult
        ) or not isinstance(self.optimized_frame, OptimizedPaperSimulationFrame):
            raise error("frame generation contains invalid result or frame types")
        if (
            self.window_start_index > self.window_end_index_inclusive
            or self.window_end_index_inclusive != self.historical_frame_index
            or self.window_end_timestamp != self.rebalance_timestamp
            or self.scenario_result.request.request_id != self.scenario_request_id
            or self.scenario_result.request.as_of != self.rebalance_timestamp
            or self.optimized_frame.as_of != self.rebalance_timestamp
            or self.optimized_frame.scenarios is not self.scenario_result.scenario_set
            or self.optimized_frame.expected_returns
            is not self.scenario_result.expected_returns
        ):
            raise error("frame generation relationships are inconsistent")
        if self.optimized_frame_fingerprint != _optimized_frame_fingerprint(
            self.optimized_frame
        ):
            raise error("optimized frame fingerprint is inconsistent")


@dataclass(frozen=True, slots=True)
class RollingHistoricalSimulationResult:
    """Complete immutable rolling preparation, simulation, and analytics audit."""

    result_id: UUID
    request: RollingHistoricalSimulationRequest
    frame_generations: tuple[RollingHistoricalFrameGeneration, ...]
    optimized_request: OptimizedPaperSimulationRequest
    optimized_result: OptimizedPaperSimulationResult
    performance_request: OptimizedSimulationPerformanceRequest
    performance_result: OptimizedSimulationPerformanceResult
    initial_engine_state_id: UUID
    initial_ledger_state_id: UUID
    final_engine_state_id: UUID
    final_ledger_state_id: UUID

    def __post_init__(self) -> None:
        error = InconsistentRollingHistoricalSimulationResultError
        if not isinstance(self.result_id, UUID) or not isinstance(
            self.request, RollingHistoricalSimulationRequest
        ):
            raise error("result identity or request has an invalid type")
        try:
            generations = tuple(self.frame_generations)
        except TypeError as caught:
            raise error("frame_generations must be iterable") from caught
        if not generations or not all(
            isinstance(item, RollingHistoricalFrameGeneration) for item in generations
        ):
            raise error("frame_generations must contain frame audit values")
        if tuple(item.frame_ordinal for item in generations) != tuple(
            range(len(generations))
        ):
            raise error("frame generation ordinals must be sequential")
        if tuple(item.rebalance_timestamp for item in generations) != (
            self.request.rebalance_timestamps
        ):
            raise error("frame generation timestamps must match the schedule")
        for generation in generations:
            child = generation.scenario_result.request.historical_data
            if (
                len(child.frames) != self.request.window_policy.observation_count
                or child.frames[0].timestamp != generation.window_start_timestamp
                or child.frames[-1].timestamp != generation.window_end_timestamp
                or tuple(
                    item.symbol for item in generation.scenario_result.expected_returns
                )
                != self.request.historical_data.symbols
                or generation.scenario_result.scenario_set.symbols
                != self.request.historical_data.symbols
            ):
                raise error("retained window or scenario universe is inconsistent")
        if not isinstance(self.optimized_request, OptimizedPaperSimulationRequest):
            raise error("optimized_request has an invalid type")
        if not isinstance(self.optimized_result, OptimizedPaperSimulationResult):
            raise error("optimized_result has an invalid type")
        if not isinstance(
            self.performance_request, OptimizedSimulationPerformanceRequest
        ) or not isinstance(
            self.performance_result, OptimizedSimulationPerformanceResult
        ):
            raise error("performance request or result has an invalid type")
        if self.optimized_request.frames != tuple(
            item.optimized_frame for item in generations
        ):
            raise error("optimized request frames differ from generated frames")
        if (
            self.optimized_result.request is not self.optimized_request
            or self.performance_request.simulation_result is not self.optimized_result
            or self.performance_result.request is not self.performance_request
        ):
            raise error("nested request and result sources are inconsistent")
        ids = (
            self.initial_engine_state_id,
            self.initial_ledger_state_id,
            self.final_engine_state_id,
            self.final_ledger_state_id,
        )
        if not all(isinstance(item, UUID) for item in ids):
            raise error("component state IDs must be UUID values")
        if ids != (
            self.optimized_result.initial_engine_state_id,
            self.optimized_result.initial_ledger_state_id,
            self.optimized_result.final_engine_state_id,
            self.optimized_result.final_ledger_state_id,
        ):
            raise error("component state IDs differ from optimized simulation")
        historical_id = _historical_fingerprint(self.request.historical_data)
        expected_id = _rolling_result_id(
            self.request,
            historical_id,
            generations,
            self.optimized_request,
            self.optimized_result,
            self.performance_request,
            self.performance_result,
            *ids,
        )
        if self.result_id != expected_id:
            raise error("result_id does not match deterministic identity")
        object.__setattr__(self, "frame_generations", generations)


class RollingHistoricalOptimizedSimulationRunner:
    """Prepare rolling historical frames and run one simulator and analyzer."""

    _scenario_factory_type = HistoricalReturnScenarioFactory
    _performance_analyzer_type = OptimizedSimulationPerformanceAnalyzer

    def __init__(self, simulator: OptimizedPaperPortfolioSimulator) -> None:
        if not isinstance(simulator, OptimizedPaperPortfolioSimulator):
            raise TypeError("simulator must be OptimizedPaperPortfolioSimulator")
        self._simulator = simulator

    @property
    def simulator(self) -> OptimizedPaperPortfolioSimulator:
        return self._simulator

    def run(
        self, request: RollingHistoricalSimulationRequest
    ) -> RollingHistoricalSimulationResult:
        if not isinstance(request, RollingHistoricalSimulationRequest):
            raise InvalidRollingHistoricalSimulationRequestError(
                "request must be RollingHistoricalSimulationRequest"
            )
        timestamps, index_by_timestamp = _validate_historical_and_schedule(request)
        historical_id = _historical_fingerprint(request.historical_data)
        initial_engine_id, initial_ledger_id = _live_state_ids(self._simulator)
        generations = []
        for ordinal, rebalance_at in enumerate(request.rebalance_timestamps):
            source_index = index_by_timestamp[rebalance_at]
            start_index = source_index - request.window_policy.observation_count + 1
            child = _historical_window(
                request.historical_data, start_index, source_index
            )
            scenario_request_id = _scenario_request_id(
                request,
                ordinal,
                rebalance_at,
                start_index,
                source_index,
                timestamps[start_index],
                timestamps[source_index],
                historical_id,
            )
            try:
                scenario_request = HistoricalScenarioGenerationRequest(
                    scenario_request_id,
                    child,
                    request.scenario_policy,
                    rebalance_at,
                    ForecastHorizon(1, Timeframe.DAY_1),
                    request.scenario_cash_return,
                    request.scenario_source_name,
                    _scenario_metadata(
                        request,
                        ordinal,
                        timestamps[start_index],
                        timestamps[source_index],
                    ),
                )
                scenario_result = self._scenario_factory_type().generate(
                    scenario_request
                )
            except HistoricalScenarioGenerationError as caught:
                raise RollingHistoricalScenarioGenerationError(
                    ordinal, rebalance_at, str(caught)
                ) from caught
            source_frame = request.historical_data.frames[source_index]
            try:
                optimized_frame = _optimized_frame(
                    request,
                    ordinal,
                    source_frame,
                    timestamps[start_index],
                    timestamps[source_index],
                    scenario_result,
                )
            except InvalidOptimizedPaperSimulationFrameError as caught:
                raise RollingHistoricalFrameConstructionError(str(caught)) from caught
            generations.append(
                RollingHistoricalFrameGeneration(
                    ordinal,
                    rebalance_at,
                    source_index,
                    start_index,
                    source_index,
                    timestamps[start_index],
                    timestamps[source_index],
                    _source_frame_id(source_frame),
                    scenario_request_id,
                    scenario_result,
                    _optimized_frame_fingerprint(optimized_frame),
                    optimized_frame,
                )
            )
        optimized_request_id = _optimized_request_id(request, tuple(generations))
        try:
            optimized_request = OptimizedPaperSimulationRequest(
                optimized_request_id,
                tuple(item.optimized_frame for item in generations),
                _optimized_request_metadata(request),
            )
        except InvalidOptimizedPaperSimulationRequestError as caught:
            raise RollingHistoricalFrameConstructionError(str(caught)) from caught
        prepared_engine_id, prepared_ledger_id = _live_state_ids(self._simulator)
        if (prepared_engine_id, prepared_ledger_id) != (
            initial_engine_id,
            initial_ledger_id,
        ):
            raise RollingHistoricalSimulationReconciliationError(
                "pure preparation changed simulator component state"
            )
        try:
            optimized_result = self._simulator.run(optimized_request)
        except OptimizedPaperSimulationError as caught:
            frame_ordinal = getattr(caught, "frame_ordinal", None)
            rebalance = (
                None
                if frame_ordinal is None
                else request.rebalance_timestamps[frame_ordinal]
            )
            raise RollingHistoricalSimulationExecutionError(
                str(caught),
                frame_ordinal=frame_ordinal,
                rebalance_timestamp=rebalance,
            ) from caught
        post_simulation_ids = _live_state_ids(self._simulator)
        try:
            performance_request = OptimizedSimulationPerformanceRequest(
                _performance_request_id(request, optimized_result),
                optimized_result,
                OptimizedSimulationValuationPolicy(
                    OptimizedSimulationValuationBasis.FRAME_RISK_PRICES
                ),
                _performance_metadata(request),
            )
            performance_result = self._performance_analyzer_type().analyze(
                performance_request
            )
        except (
            InvalidOptimizedSimulationPerformanceRequestError,
            OptimizedSimulationValuationError,
            OptimizedSimulationPerformanceReconciliationError,
            InconsistentOptimizedSimulationPerformanceResultError,
        ) as caught:
            raise RollingHistoricalPerformanceError(
                optimized_result.result_id, str(caught)
            ) from caught
        final_engine_id, final_ledger_id = _live_state_ids(self._simulator)
        if (final_engine_id, final_ledger_id) != post_simulation_ids:
            raise RollingHistoricalSimulationReconciliationError(
                "performance analytics changed simulator component state"
            )
        _reconcile_live(
            request,
            tuple(generations),
            optimized_request,
            optimized_result,
            performance_request,
            performance_result,
            initial_engine_id,
            initial_ledger_id,
            final_engine_id,
            final_ledger_id,
        )
        result_id = _rolling_result_id(
            request,
            historical_id,
            tuple(generations),
            optimized_request,
            optimized_result,
            performance_request,
            performance_result,
            initial_engine_id,
            initial_ledger_id,
            final_engine_id,
            final_ledger_id,
        )
        return RollingHistoricalSimulationResult(
            result_id,
            request,
            tuple(generations),
            optimized_request,
            optimized_result,
            performance_request,
            performance_result,
            initial_engine_id,
            initial_ledger_id,
            final_engine_id,
            final_ledger_id,
        )


def _validate_historical_and_schedule(
    request: RollingHistoricalSimulationRequest,
) -> tuple[tuple[datetime, ...], dict[datetime, int]]:
    data = request.historical_data
    if not request.rebalance_timestamps:
        raise RollingHistoricalScheduleError("rebalance_timestamps must not be empty")
    if data.request.timeframe is not Timeframe.DAY_1 or not data.frames:
        raise RollingHistoricalSimulationReconciliationError(
            "historical data must contain DAY_1 frames"
        )
    if not data.is_complete:
        raise RollingHistoricalSimulationReconciliationError(
            "historical data must contain complete frames"
        )
    symbols = data.symbols
    if not symbols or len(set(symbols)) != len(symbols):
        raise RollingHistoricalSimulationReconciliationError(
            "historical universe must be nonempty and unique"
        )
    timestamps = []
    previous = None
    for ordinal, frame in enumerate(data.frames):
        if previous is not None and frame.timestamp <= previous:
            raise RollingHistoricalSimulationReconciliationError(
                "historical timestamps must be strictly increasing"
            )
        if (
            frame.symbols != symbols
            or frame.missing_symbols
            or tuple(frame.bars_by_symbol) != symbols
        ):
            raise RollingHistoricalSimulationReconciliationError(
                f"historical frame {ordinal} has an inconsistent universe"
            )
        for symbol in symbols:
            bar = frame.bars_by_symbol.get(symbol)
            if (
                bar is None
                or bar.symbol != symbol
                or bar.timestamp != frame.timestamp
                or not isinstance(bar.close, Decimal)
                or not bar.close.is_finite()
                or bar.close <= _ZERO
            ):
                raise RollingHistoricalSimulationReconciliationError(
                    f"historical frame {ordinal} contains an inconsistent bar"
                )
        timestamps.append(frame.timestamp)
        previous = frame.timestamp
    index_by_timestamp = {
        timestamp: index for index, timestamp in enumerate(timestamps)
    }
    schedule_previous = None
    prior_filled = None
    for ordinal, timestamp in enumerate(request.rebalance_timestamps):
        if schedule_previous is not None and timestamp <= schedule_previous:
            raise RollingHistoricalScheduleError(
                "rebalance timestamps must be strictly increasing"
            )
        if timestamp not in index_by_timestamp:
            raise RollingHistoricalScheduleError(
                f"rebalance timestamp {timestamp.isoformat()} is absent from history"
            )
        source_index = index_by_timestamp[timestamp]
        if source_index + 1 < request.window_policy.observation_count:
            raise RollingHistoricalWindowError(
                f"rebalance ordinal {ordinal} has insufficient history"
            )
        if prior_filled is not None and timestamp < prior_filled:
            raise RollingHistoricalScheduleError(
                "next rebalance timestamp precedes the prior fill timestamp"
            )
        try:
            prior_filled = timestamp + request.timing_policy.fill_offset
        except OverflowError as caught:
            raise RollingHistoricalScheduleError(
                "fill offset exceeds supported datetime range"
            ) from caught
        schedule_previous = timestamp
    return tuple(timestamps), index_by_timestamp


def _historical_window(
    source: MultiSymbolHistoricalDataResult,
    start_index: int,
    end_index_inclusive: int,
) -> MultiSymbolHistoricalDataResult:
    frames = source.frames[start_index : end_index_inclusive + 1]
    if not frames:
        raise RollingHistoricalWindowError("historical window must not be empty")
    end = (
        source.frames[end_index_inclusive + 1].timestamp
        if end_index_inclusive + 1 < len(source.frames)
        else source.request.end
    )
    try:
        child_request = MultiSymbolHistoricalDataRequest(
            source.symbols,
            frames[0].timestamp,
            end,
            source.request.timeframe,
            source.request.adjustment,
            source.request.missing_bar_policy,
        )
        return MultiSymbolHistoricalDataResult(
            child_request, frames, source.provider_name
        )
    except HistoricalDataValidationError as caught:
        raise RollingHistoricalWindowError(str(caught)) from caught


def _optimized_frame(
    request: RollingHistoricalSimulationRequest,
    ordinal: int,
    source_frame,  # type: ignore[no-untyped-def]
    window_start: datetime,
    window_end: datetime,
    scenario_result: HistoricalScenarioGenerationResult,
) -> OptimizedPaperSimulationFrame:
    prices = tuple(
        PaperPortfolioCyclePrice(
            symbol,
            source_frame.bars_by_symbol[symbol].close,
            source_frame.bars_by_symbol[symbol].close,
        )
        for symbol in source_frame.symbols
    )
    as_of = source_frame.timestamp
    return OptimizedPaperSimulationFrame(
        as_of,
        prices,
        scenario_result.expected_returns,
        scenario_result.scenario_set,
        request.optimization_parameters,
        request.risk_aversion,
        request.portfolio_constraints,
        request.rebalance_assumptions,
        request.proposal_policy,
        request.proposal_confidence,
        request.risk_limits,
        request.risk_policy,
        request.fill_policy,
        request.trading_enabled,
        as_of + request.timing_policy.submission_offset,
        as_of + request.timing_policy.fill_offset,
        _optimized_frame_metadata(
            ordinal,
            window_start,
            window_end,
            request.window_policy.observation_count,
        ),
    )


def _scenario_metadata(
    request: RollingHistoricalSimulationRequest,
    ordinal: int,
    start: datetime,
    end: datetime,
) -> tuple[MetadataEntry, ...]:
    return (
        MetadataEntry("rolling_historical_simulation_id", str(request.request_id)),
        MetadataEntry("rolling_historical_frame_ordinal", str(ordinal)),
        MetadataEntry("rolling_historical_window_start", start.isoformat()),
        MetadataEntry("rolling_historical_window_end", end.isoformat()),
        MetadataEntry(
            "rolling_historical_observation_count",
            str(request.window_policy.observation_count),
        ),
    )


def _optimized_request_metadata(
    request: RollingHistoricalSimulationRequest,
) -> tuple[MetadataEntry, ...]:
    return (
        MetadataEntry("rolling_historical_simulation_id", str(request.request_id)),
        MetadataEntry(
            "rolling_historical_simulation_source",
            "rolling-historical-runner",
        ),
    )


def _optimized_frame_metadata(
    ordinal: int,
    start: datetime,
    end: datetime,
    count: int,
) -> tuple[MetadataEntry, ...]:
    return (
        MetadataEntry("rolling_historical_frame_ordinal", str(ordinal)),
        MetadataEntry("rolling_historical_window_start", start.isoformat()),
        MetadataEntry("rolling_historical_window_end", end.isoformat()),
        MetadataEntry("rolling_historical_observation_count", str(count)),
    )


def _performance_metadata(
    request: RollingHistoricalSimulationRequest,
) -> tuple[MetadataEntry, ...]:
    return _optimized_request_metadata(request)


def _scenario_request_id(
    request: RollingHistoricalSimulationRequest,
    ordinal: int,
    rebalance: datetime,
    start_index: int,
    end_index: int,
    start: datetime,
    end: datetime,
    historical_id: UUID,
) -> UUID:
    return _id(
        "historical-scenarios",
        str(request.request_id),
        str(ordinal),
        rebalance.isoformat(),
        str(start_index),
        str(end_index),
        start.isoformat(),
        end.isoformat(),
        str(historical_id),
    )


def _optimized_request_id(
    request: RollingHistoricalSimulationRequest,
    generations: tuple[RollingHistoricalFrameGeneration, ...],
) -> UUID:
    return _id(
        "optimized-simulation",
        str(request.request_id),
        *(str(item.scenario_result.result_id) for item in generations),
        *(str(item.optimized_frame_fingerprint) for item in generations),
    )


def _performance_request_id(
    request: RollingHistoricalSimulationRequest,
    result: OptimizedPaperSimulationResult,
) -> UUID:
    return _id(
        "performance",
        str(request.request_id),
        str(result.result_id),
        OptimizedSimulationValuationBasis.FRAME_RISK_PRICES.value,
    )


def _source_frame_id(frame) -> UUID:  # type: ignore[no-untyped-def]
    material = [frame.timestamp.isoformat()]
    for symbol in frame.symbols:
        bar = frame.bars_by_symbol[symbol]
        material.extend(_bar_material(bar))
    return _id("source-frame", *material)


def _historical_fingerprint(data: MultiSymbolHistoricalDataResult) -> UUID:
    request = data.request
    material = [
        request.start.isoformat(),
        request.end.isoformat(),
        request.timeframe.value,
        request.adjustment.value,
        request.missing_bar_policy.value,
        data.provider_name,
        *(str(symbol) for symbol in request.symbols),
    ]
    for frame in data.frames:
        material.extend(
            (
                frame.timestamp.isoformat(),
                *(str(symbol) for symbol in frame.missing_symbols),
            )
        )
        for symbol in frame.symbols:
            bar = frame.bars_by_symbol.get(symbol)
            material.extend(
                ("missing", str(symbol)) if bar is None else _bar_material(bar)
            )
    return _id("historical-data", *material)


def _bar_material(bar) -> tuple[str, ...]:  # type: ignore[no-untyped-def]
    return (
        str(bar.symbol),
        bar.timestamp.isoformat(),
        _canonical(bar.open),
        _canonical(bar.high),
        _canonical(bar.low),
        _canonical(bar.close),
        str(bar.volume),
    )


def _optimized_frame_fingerprint(frame: OptimizedPaperSimulationFrame) -> UUID:
    material = [
        frame.as_of.isoformat(),
        frame.submitted_at.isoformat(),
        frame.filled_at.isoformat(),
        *(
            f"{item.symbol}:{_canonical(item.risk_price)}:"
            f"{_canonical(item.fill_reference_price)}"
            for item in frame.prices
        ),
        *(f"{item.symbol}:{_canonical(item.value)}" for item in frame.expected_returns),
        str(frame.scenarios.scenario_set_id),
        _canonical(frame.risk_aversion),
        _canonical(frame.optimization_parameters.confidence_level),
        str(frame.optimization_parameters.maximum_iterations),
        _canonical(frame.optimization_parameters.solver_tolerance),
        _canonical(frame.optimization_parameters.output_quantum),
        _optional(frame.optimization_parameters.minimum_expected_return),
        _canonical(frame.portfolio_constraints.minimum_cash_weight),
        _canonical(frame.portfolio_constraints.maximum_cash_weight),
        _canonical(frame.portfolio_constraints.maximum_position_weight),
        _optional(frame.portfolio_constraints.maximum_one_way_rebalance_turnover),
        _optional(frame.portfolio_constraints.minimum_position_weight),
        str(frame.portfolio_constraints.long_only),
        str(frame.portfolio_constraints.allow_leverage),
        _rebalance_material(frame.rebalance_assumptions),
        str(frame.proposal_policy.allow_partial_plans),
        _optional(frame.proposal_confidence),
        _risk_limits_material(frame.risk_limits),
        str(frame.risk_policy.allow_sell_proceeds_for_later_buys),
        _canonical(frame.fill_policy.slippage_basis_points),
        _canonical(frame.fill_policy.fixed_commission),
        str(frame.trading_enabled),
        *(f"{item.key}={item.value}" for item in frame.metadata),
    ]
    return _id("optimized-frame", *material)


def _rebalance_material(value: RebalanceAssumptions) -> str:
    return ":".join(
        (
            _canonical(value.fixed_commission),
            str(value.allow_fractional_quantities),
            _canonical(value.quantity_increment),
            _canonical(value.minimum_trade_notional),
            _canonical(value.minimum_trade_quantity),
            _canonical(value.target_weight_tolerance),
            _canonical(value.additional_execution_cash_buffer),
            str(value.use_planned_sell_proceeds),
        )
    )


def _risk_limits_material(value: RiskLimits) -> str:
    return ":".join(
        (
            _canonical(value.max_position_percent),
            _canonical(value.max_total_exposure_percent),
            _optional(value.max_order_notional),
            _optional(value.max_new_position_percent),
            _canonical(value.minimum_cash_reserve_percent),
            str(value.allow_fractional_shares),
            _canonical(value.fractional_increment),
            str(value.allow_buying),
            str(value.allow_selling),
            _canonical(value.estimated_commission),
        )
    )


def _request_fingerprint(request: RollingHistoricalSimulationRequest) -> str:
    material = [
        str(request.request_id),
        str(_historical_fingerprint(request.historical_data)),
        *(item.isoformat() for item in request.rebalance_timestamps),
        str(request.window_policy.observation_count),
        request.scenario_policy.price_field.value,
        request.scenario_policy.return_method.value,
        request.scenario_policy.window_policy.value,
        request.execution_price_policy.risk_price_field.value,
        request.execution_price_policy.fill_reference_price_field.value,
        str(_timedelta_microseconds(request.timing_policy.submission_offset)),
        str(_timedelta_microseconds(request.timing_policy.fill_offset)),
        _canonical(request.scenario_cash_return),
        request.scenario_source_name,
        _canonical(request.risk_aversion),
        _optional(request.proposal_confidence),
        str(request.trading_enabled),
        *(f"{item.key}={item.value}" for item in request.metadata),
    ]
    material.extend(
        (
            _canonical(request.optimization_parameters.confidence_level),
            _canonical(request.optimization_parameters.solver_tolerance),
            str(request.optimization_parameters.maximum_iterations),
            _canonical(request.optimization_parameters.output_quantum),
            _optional(request.optimization_parameters.minimum_expected_return),
            _canonical(request.portfolio_constraints.minimum_cash_weight),
            _canonical(request.portfolio_constraints.maximum_cash_weight),
            _canonical(request.portfolio_constraints.maximum_position_weight),
            _optional(request.portfolio_constraints.maximum_one_way_rebalance_turnover),
            _optional(request.portfolio_constraints.minimum_position_weight),
            str(request.portfolio_constraints.long_only),
            str(request.portfolio_constraints.allow_leverage),
            _rebalance_material(request.rebalance_assumptions),
            str(request.proposal_policy.allow_partial_plans),
            _risk_limits_material(request.risk_limits),
            str(request.risk_policy.allow_sell_proceeds_for_later_buys),
            _canonical(request.fill_policy.slippage_basis_points),
            _canonical(request.fill_policy.fixed_commission),
        )
    )
    return "|".join(material)


def _rolling_result_id(
    request: RollingHistoricalSimulationRequest,
    historical_id: UUID,
    generations: tuple[RollingHistoricalFrameGeneration, ...],
    optimized_request: OptimizedPaperSimulationRequest,
    optimized_result: OptimizedPaperSimulationResult,
    performance_request: OptimizedSimulationPerformanceRequest,
    performance_result: OptimizedSimulationPerformanceResult,
    initial_engine_id: UUID,
    initial_ledger_id: UUID,
    final_engine_id: UUID,
    final_ledger_id: UUID,
) -> UUID:
    return _id(
        "result",
        _request_fingerprint(request),
        str(historical_id),
        str(initial_engine_id),
        str(initial_ledger_id),
        *(str(item.source_frame_id) for item in generations),
        *(str(item.scenario_result.result_id) for item in generations),
        *(str(item.optimized_frame_fingerprint) for item in generations),
        str(optimized_request.request_id),
        str(optimized_result.result_id),
        str(performance_request.request_id),
        str(performance_result.result_id),
        str(final_engine_id),
        str(final_ledger_id),
    )


def _reconcile_live(
    request: RollingHistoricalSimulationRequest,
    generations: tuple[RollingHistoricalFrameGeneration, ...],
    optimized_request: OptimizedPaperSimulationRequest,
    optimized_result: OptimizedPaperSimulationResult,
    performance_request: OptimizedSimulationPerformanceRequest,
    performance_result: OptimizedSimulationPerformanceResult,
    initial_engine_id: UUID,
    initial_ledger_id: UUID,
    final_engine_id: UUID,
    final_ledger_id: UUID,
) -> None:
    error = RollingHistoricalSimulationReconciliationError
    historical_id = _historical_fingerprint(request.historical_data)
    for generation in generations:
        if generation.scenario_request_id != _scenario_request_id(
            request,
            generation.frame_ordinal,
            generation.rebalance_timestamp,
            generation.window_start_index,
            generation.window_end_index_inclusive,
            generation.window_start_timestamp,
            generation.window_end_timestamp,
            historical_id,
        ):
            raise error("scenario request identity does not reconcile")
    if optimized_request.request_id != _optimized_request_id(request, generations):
        raise error("optimized request identity does not reconcile")
    if performance_request.request_id != _performance_request_id(
        request, optimized_result
    ):
        raise error("performance request identity does not reconcile")
    if (
        optimized_result.request is not optimized_request
        or optimized_result.initial_engine_state_id != initial_engine_id
        or optimized_result.initial_ledger_state_id != initial_ledger_id
        or optimized_result.final_engine_state_id != final_engine_id
        or optimized_result.final_ledger_state_id != final_ledger_id
    ):
        raise error("optimized simulation state and request do not reconcile")
    if (
        performance_request.simulation_result is not optimized_result
        or performance_result.request is not performance_request
    ):
        raise error("performance source relationships do not reconcile")
    if len(generations) != len(optimized_result.evaluations) or len(generations) != len(
        performance_result.frames
    ):
        raise error("frame counts do not reconcile across stages")
    for ordinal, (generation, evaluation, performance) in enumerate(
        zip(
            generations,
            optimized_result.evaluations,
            performance_result.frames,
            strict=True,
        )
    ):
        if (
            generation.frame_ordinal != ordinal
            or generation.rebalance_timestamp != request.rebalance_timestamps[ordinal]
            or evaluation.frame_ordinal != ordinal
            or evaluation.frame is not generation.optimized_frame
            or performance.frame_ordinal != ordinal
            or performance.source_cycle_result_id != evaluation.cycle_result.result_id
        ):
            raise error("frame ordering or source identity does not reconcile")


def _live_state_ids(
    simulator: OptimizedPaperPortfolioSimulator,
) -> tuple[UUID, UUID]:
    return (
        engine_state_id(engine_snapshot(simulator.engine)),
        ledger_state_id(ledger_snapshot(simulator.ledger)),
    )


def _timedelta_microseconds(value: timedelta) -> int:
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


def _optional(value: Decimal | None) -> str:
    return "none" if value is None else _canonical(value)


def _canonical(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("identity Decimal values must be finite")
    if value == _ZERO:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _id(stage: str, *material: str) -> UUID:
    return uuid5(_NAMESPACE, "|".join((_VERSION, stage, *material)))
