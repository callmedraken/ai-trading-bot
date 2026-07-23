"""Deterministic sequential comparison of explicit historical variants."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.execution import OrderEngine, PaperFillPolicy
from trading_bot.execution.state_fingerprints import (
    canonical_decimal,
    engine_snapshot,
)
from trading_bot.experiments.exceptions import (
    HistoricalExperimentExecutionError,
    HistoricalExperimentInitializationError,
    HistoricalExperimentIsolationError,
    HistoricalExperimentReconciliationError,
    HistoricalExperimentVariantError,
    InconsistentHistoricalExperimentResultError,
    InvalidHistoricalExperimentRequestError,
)
from trading_bot.ledger import LedgerError, PaperLedger
from trading_bot.market_data import (
    MultiSymbolHistoricalDataResult,
    canonical_multi_symbol_historical_material,
)
from trading_bot.portfolio import (
    HistoricalScenarioGenerationPolicy,
    MeanCvarOptimizationParameters,
    MetadataEntry,
    PortfolioConstraints,
)
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import PaperPortfolioRuntime
from trading_bot.simulation import (
    OptimizedPaperPortfolioSimulator,
    RollingHistoricalCycleTimingPolicy,
    RollingHistoricalExecutionPricePolicy,
    RollingHistoricalOptimizedSimulationRunner,
    RollingHistoricalSimulationError,
    RollingHistoricalSimulationRequest,
    RollingHistoricalSimulationResult,
    RollingHistoricalWindowPolicy,
)

_ZERO = Decimal("0")
_VERSION = "historical-experiment-runner-v1"
_NAMESPACE = UUID("8db639bc-7116-5fc8-902f-fc94ec770743")
_RESERVED_PREFIX = "historical_experiment_"


class HistoricalExperimentInitializationMode(StrEnum):
    CASH_ONLY = "CASH_ONLY"
    BOOTSTRAP_FILLS = "BOOTSTRAP_FILLS"


@dataclass(frozen=True, slots=True)
class HistoricalExperimentBootstrapPosition:
    symbol: Symbol
    quantity: Decimal
    unit_cost: Decimal

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentRequestError
        if not isinstance(self.symbol, Symbol):
            raise error("bootstrap symbol must be a Symbol")
        for name in ("quantity", "unit_cost"):
            value = getattr(self, name)
            if (
                not isinstance(value, Decimal)
                or isinstance(value, bool)
                or not value.is_finite()
                or value <= _ZERO
            ):
                raise error(f"bootstrap {name} must be a finite positive Decimal")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentInitialState:
    mode: HistoricalExperimentInitializationMode
    as_of: datetime
    available_cash: Decimal
    bootstrap_positions: tuple[HistoricalExperimentBootstrapPosition, ...] = ()
    bootstrap_commission: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentRequestError
        if not isinstance(self.mode, HistoricalExperimentInitializationMode):
            raise error("initialization mode has an invalid type")
        try:
            as_of = normalize_utc(self.as_of, "initial_state.as_of")
            positions = tuple(self.bootstrap_positions)
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        cash = self.available_cash
        commission = self.bootstrap_commission
        if (
            not isinstance(cash, Decimal)
            or isinstance(cash, bool)
            or not cash.is_finite()
            or cash < _ZERO
        ):
            raise error("available_cash must be a finite nonnegative Decimal")
        if (
            not isinstance(commission, Decimal)
            or isinstance(commission, bool)
            or not commission.is_finite()
            or commission != _ZERO
        ):
            raise error("bootstrap_commission must be exactly zero")
        if not all(
            isinstance(item, HistoricalExperimentBootstrapPosition)
            for item in positions
        ):
            raise error("bootstrap_positions contain an invalid value")
        if len({item.symbol for item in positions}) != len(positions):
            raise error("bootstrap position symbols must be unique")
        if self.mode is HistoricalExperimentInitializationMode.CASH_ONLY and positions:
            raise error("CASH_ONLY cannot contain bootstrap positions")
        if (
            self.mode is HistoricalExperimentInitializationMode.BOOTSTRAP_FILLS
            and not positions
        ):
            raise error("BOOTSTRAP_FILLS requires at least one position")
        if cash == _ZERO and not positions:
            raise error("initial state must contain cash or positions")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "available_cash", _normalize_zero(cash))
        object.__setattr__(self, "bootstrap_commission", _ZERO)
        object.__setattr__(self, "bootstrap_positions", positions)


class HistoricalExperimentSimulatorFactory(Protocol):
    """Construct one fresh, already initialized simulator per variant."""

    def __call__(
        self,
        initial_state: HistoricalExperimentInitialState,
        *,
        experiment_request_id: UUID,
        variant_id: UUID,
        variant_ordinal: int,
    ) -> OptimizedPaperPortfolioSimulator: ...


@dataclass(frozen=True, slots=True)
class HistoricalExperimentVariant:
    variant_id: UUID
    name: str
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
        error = HistoricalExperimentVariantError
        if not isinstance(self.variant_id, UUID):
            raise error("variant_id must be a UUID")
        if not isinstance(self.name, str) or not self.name.strip():
            raise error("variant name must be nonblank")
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
        try:
            for policy in (
                self.window_policy,
                self.scenario_policy,
                self.execution_price_policy,
                self.timing_policy,
                self.optimization_parameters,
                self.portfolio_constraints,
                self.rebalance_assumptions,
                self.proposal_policy,
                self.risk_limits,
                self.risk_policy,
                self.fill_policy,
            ):
                validator = getattr(policy, "__post_init__", None)
                if validator is not None:
                    validator()
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        cash_return = _finite_decimal(
            self.scenario_cash_return, "scenario_cash_return", error
        )
        if cash_return < Decimal("-1"):
            raise error("scenario_cash_return must be at least negative one")
        risk_aversion = _finite_decimal(self.risk_aversion, "risk_aversion", error)
        if risk_aversion < _ZERO:
            raise error("risk_aversion must be nonnegative")
        confidence = self.proposal_confidence
        if confidence is not None:
            confidence = _finite_decimal(confidence, "proposal_confidence", error)
            if not _ZERO <= confidence <= Decimal("1"):
                raise error("proposal_confidence must be between zero and one")
        if (
            not isinstance(self.scenario_source_name, str)
            or not self.scenario_source_name.strip()
        ):
            raise error("scenario_source_name must be nonblank")
        if type(self.trading_enabled) is not bool:
            raise error("trading_enabled must be bool")
        if not (
            self.rebalance_assumptions.fixed_commission
            == self.risk_limits.estimated_commission
            == self.fill_policy.fixed_commission
        ):
            raise error("planner, risk, and fill fixed commissions must match")
        metadata = _validated_metadata(self.metadata, error)
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "scenario_cash_return", _normalize_zero(cash_return))
        object.__setattr__(self, "risk_aversion", _normalize_zero(risk_aversion))
        object.__setattr__(
            self,
            "proposal_confidence",
            None if confidence is None else _normalize_zero(confidence),
        )
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentRequest:
    request_id: UUID
    historical_data: MultiSymbolHistoricalDataResult
    rebalance_timestamps: tuple[datetime, ...]
    initial_state: HistoricalExperimentInitialState
    variants: tuple[HistoricalExperimentVariant, ...]
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if type(self.historical_data) is not MultiSymbolHistoricalDataResult:
            raise error(
                "historical_data must be exactly MultiSymbolHistoricalDataResult"
            )
        if not isinstance(self.initial_state, HistoricalExperimentInitialState):
            raise error("initial_state has an invalid type")
        self.initial_state.__post_init__()
        try:
            timestamps = tuple(
                normalize_utc(item, f"rebalance_timestamps[{index}]")
                for index, item in enumerate(self.rebalance_timestamps)
            )
            variants = tuple(self.variants)
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        if not timestamps:
            raise error("rebalance_timestamps must not be empty")
        if not variants or not all(
            isinstance(item, HistoricalExperimentVariant) for item in variants
        ):
            raise error("variants must contain at least one experiment variant")
        if len({item.variant_id for item in variants}) != len(variants):
            raise error("variant IDs must be unique")
        for variant in variants:
            variant.__post_init__()
        normalized_names = tuple(item.name.strip().casefold() for item in variants)
        if len(set(normalized_names)) != len(variants):
            raise error("variant names must be unique after normalization")
        metadata = _validated_metadata(self.metadata, error)
        object.__setattr__(self, "rebalance_timestamps", timestamps)
        object.__setattr__(self, "variants", variants)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentMetrics:
    initial_equity: Decimal
    final_equity: Decimal
    absolute_simulation_profit_loss: Decimal
    simulation_return: Decimal
    maximum_drawdown_amount: Decimal
    maximum_drawdown_percentage: Decimal
    simulation_realized_profit_loss: Decimal
    total_commissions: Decimal
    adverse_slippage_cost: Decimal
    total_execution_cost: Decimal
    aggregate_one_way_turnover: Decimal
    aggregate_two_way_turnover: Decimal
    maximum_allocation_drift: Decimal
    total_orders: int
    total_fills: int
    approved_decisions: int
    resized_decisions: int
    rejected_decisions: int
    rejected_notional: Decimal
    reduced_notional: Decimal
    mean_expected_portfolio_return: Decimal
    worst_cvar: Decimal
    minimum_target_cash_weight: Decimal
    maximum_target_cash_weight: Decimal
    applied_cycle_count: int
    no_action_cycle_count: int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentResultError
        decimal_names = (
            "initial_equity",
            "final_equity",
            "absolute_simulation_profit_loss",
            "simulation_return",
            "maximum_drawdown_amount",
            "maximum_drawdown_percentage",
            "simulation_realized_profit_loss",
            "total_commissions",
            "adverse_slippage_cost",
            "total_execution_cost",
            "aggregate_one_way_turnover",
            "aggregate_two_way_turnover",
            "maximum_allocation_drift",
            "rejected_notional",
            "reduced_notional",
            "mean_expected_portfolio_return",
            "worst_cvar",
            "minimum_target_cash_weight",
            "maximum_target_cash_weight",
        )
        if any(
            not isinstance(getattr(self, name), Decimal)
            or not getattr(self, name).is_finite()
            for name in decimal_names
        ):
            raise error("metric financial values must be finite Decimals")
        count_names = (
            "total_orders",
            "total_fills",
            "approved_decisions",
            "resized_decisions",
            "rejected_decisions",
            "applied_cycle_count",
            "no_action_cycle_count",
        )
        if any(
            not isinstance(getattr(self, name), int)
            or isinstance(getattr(self, name), bool)
            or getattr(self, name) < 0
            for name in count_names
        ):
            raise error("metric counts must be nonnegative integers")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentRun:
    run_id: UUID
    ordinal: int
    variant: HistoricalExperimentVariant
    rolling_request_id: UUID
    rolling_result: RollingHistoricalSimulationResult
    initial_state_content_fingerprint: UUID
    metrics: HistoricalExperimentMetrics

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentResultError
        if (
            not isinstance(self.run_id, UUID)
            or not isinstance(self.ordinal, int)
            or isinstance(self.ordinal, bool)
            or self.ordinal < 0
            or not isinstance(self.variant, HistoricalExperimentVariant)
            or not isinstance(self.rolling_request_id, UUID)
            or not isinstance(self.rolling_result, RollingHistoricalSimulationResult)
            or not isinstance(self.initial_state_content_fingerprint, UUID)
            or not isinstance(self.metrics, HistoricalExperimentMetrics)
        ):
            raise error("experiment run contains an invalid field type")
        if self.rolling_result.request.request_id != self.rolling_request_id:
            raise error("rolling request identity is inconsistent")
        if self.metrics != _project_metrics(self.rolling_result):
            raise error("metrics do not exactly project the performance result")
        experiment_id = _metadata_uuid(
            self.rolling_result.request.metadata, "historical_experiment_id", error
        )
        if self.run_id != _run_id(
            experiment_id,
            self.variant,
            self.rolling_request_id,
            self.rolling_result.result_id,
            self.initial_state_content_fingerprint,
            self.metrics,
        ):
            raise error("run_id is inconsistent")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentResult:
    result_id: UUID
    request: HistoricalExperimentRequest
    runs: tuple[HistoricalExperimentRun, ...]
    historical_fingerprint: UUID
    schedule_fingerprint: UUID
    initial_state_fingerprint: UUID

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentResultError
        if not isinstance(self.result_id, UUID) or not isinstance(
            self.request, HistoricalExperimentRequest
        ):
            raise error("experiment result identity or request is invalid")
        try:
            runs = tuple(self.runs)
        except TypeError as caught:
            raise error("runs must be iterable") from caught
        if len(runs) != len(self.request.variants) or not all(
            isinstance(item, HistoricalExperimentRun) for item in runs
        ):
            raise error("runs must exactly cover variants")
        if tuple(item.ordinal for item in runs) != tuple(range(len(runs))):
            raise error("run ordinals must be sequential")
        if any(
            run.variant is not variant
            for run, variant in zip(runs, self.request.variants, strict=True)
        ):
            raise error("run variants must preserve exact caller order")
        expected_fingerprints = (
            _historical_fingerprint(self.request.historical_data),
            _schedule_fingerprint(self.request.rebalance_timestamps),
            _initial_state_fingerprint(self.request.initial_state),
        )
        if (
            self.historical_fingerprint,
            self.schedule_fingerprint,
            self.initial_state_fingerprint,
        ) != expected_fingerprints:
            raise error("shared fingerprints are inconsistent")
        for run in runs:
            rolling_request = run.rolling_result.request
            if (
                rolling_request.historical_data is not self.request.historical_data
                or rolling_request.rebalance_timestamps
                != self.request.rebalance_timestamps
                or run.initial_state_content_fingerprint
                != self.initial_state_fingerprint
                or rolling_request.request_id
                != _rolling_request_id(
                    self.request,
                    run.variant,
                    run.ordinal,
                    *expected_fingerprints,
                )
                or rolling_request.metadata
                != _rolling_metadata(self.request, run.variant, run.ordinal)
            ):
                raise error("retained rolling source relationships are inconsistent")
        if self.result_id != _result_id(self.request, runs, *expected_fingerprints):
            raise error("result_id is inconsistent")
        object.__setattr__(self, "runs", runs)


class HistoricalExperimentRunner:
    """Execute explicit variants sequentially through isolated simulators."""

    def __init__(self, simulator_factory: HistoricalExperimentSimulatorFactory) -> None:
        if not callable(simulator_factory):
            raise TypeError("simulator_factory must be callable")
        self._simulator_factory = simulator_factory

    def run(self, request: HistoricalExperimentRequest) -> HistoricalExperimentResult:
        if not isinstance(request, HistoricalExperimentRequest):
            raise InvalidHistoricalExperimentRequestError(
                "request must be HistoricalExperimentRequest"
            )
        request.__post_init__()
        _validate_static_request(request)
        historical_id = _historical_fingerprint(request.historical_data)
        schedule_id = _schedule_fingerprint(request.rebalance_timestamps)
        initial_id = _initial_state_fingerprint(request.initial_state)
        request_before = _request_fingerprint(request)
        seen: dict[str, list[object]] = {
            "simulator": [],
            "runtime": [],
            "engine": [],
            "ledger": [],
        }
        runs = []
        for ordinal, variant in enumerate(request.variants):
            context = (ordinal, variant.variant_id, variant.name)
            try:
                simulator = self._simulator_factory(
                    request.initial_state,
                    experiment_request_id=request.request_id,
                    variant_id=variant.variant_id,
                    variant_ordinal=ordinal,
                )
            except (TypeError, ValueError, LedgerError) as caught:
                raise HistoricalExperimentInitializationError(
                    *context, "factory", str(caught)
                ) from caught
            _validate_simulator(simulator, request.initial_state, context, seen)
            live_fingerprint = _live_initial_state_fingerprint(
                simulator, request.initial_state
            )
            if live_fingerprint != initial_id:
                raise HistoricalExperimentInitializationError(
                    *context,
                    "initial-state-reconciliation",
                    "initialized public state differs from specification",
                )
            rolling_id = _rolling_request_id(
                request,
                variant,
                ordinal,
                historical_id,
                schedule_id,
                initial_id,
            )
            rolling_request = _rolling_request(request, variant, ordinal, rolling_id)
            try:
                rolling_result = RollingHistoricalOptimizedSimulationRunner(
                    simulator
                ).run(rolling_request)
            except RollingHistoricalSimulationError as caught:
                raise HistoricalExperimentExecutionError(
                    *context, "rolling-simulation", str(caught)
                ) from caught
            _retain_component_identities(simulator, seen)
            metrics = _project_metrics(rolling_result)
            runs.append(
                HistoricalExperimentRun(
                    _run_id(
                        request.request_id,
                        variant,
                        rolling_id,
                        rolling_result.result_id,
                        initial_id,
                        metrics,
                    ),
                    ordinal,
                    variant,
                    rolling_id,
                    rolling_result,
                    initial_id,
                    metrics,
                )
            )
        if request_before != _request_fingerprint(request):
            raise HistoricalExperimentReconciliationError(
                "experiment inputs changed during execution"
            )
        completed = tuple(runs)
        return HistoricalExperimentResult(
            _result_id(request, completed, historical_id, schedule_id, initial_id),
            request,
            completed,
            historical_id,
            schedule_id,
            initial_id,
        )


def _validate_static_request(request: HistoricalExperimentRequest) -> None:
    error = InvalidHistoricalExperimentRequestError
    data = request.historical_data
    if not data.is_complete:
        raise error("historical data must be complete")
    symbols = data.symbols
    timestamps = data.timestamps
    if not symbols or not timestamps:
        raise error("historical data must be nonempty")
    index_by_timestamp = {
        timestamp: index for index, timestamp in enumerate(timestamps)
    }
    if len(index_by_timestamp) != len(timestamps):
        raise error("historical timestamps must be unique")
    previous = None
    for timestamp in request.rebalance_timestamps:
        if previous is not None and timestamp <= previous:
            raise error("rebalance timestamps must be strictly increasing")
        if timestamp not in index_by_timestamp:
            raise error("rebalance timestamp is absent from historical data")
        previous = timestamp
    if request.initial_state.as_of > request.rebalance_timestamps[0]:
        raise error("initial state timestamp cannot follow the first rebalance")
    if any(
        item.symbol not in symbols for item in request.initial_state.bootstrap_positions
    ):
        raise error("bootstrap symbols must belong to the historical universe")
    for variant in request.variants:
        prior_fill = None
        for timestamp in request.rebalance_timestamps:
            index = index_by_timestamp[timestamp]
            if index + 1 < variant.window_policy.observation_count:
                raise error(f"variant {variant.name} has insufficient trailing history")
            if prior_fill is not None and timestamp < prior_fill:
                raise error(f"variant {variant.name} has a fill timing conflict")
            try:
                prior_fill = timestamp + variant.timing_policy.fill_offset
            except OverflowError as caught:
                raise error(
                    f"variant {variant.name} fill timestamp overflows"
                ) from caught


def _validate_simulator(
    simulator: object,
    initial: HistoricalExperimentInitialState,
    context: tuple[int, UUID, str],
    seen: dict[str, list[object]],
) -> None:
    if type(simulator) is not OptimizedPaperPortfolioSimulator:
        raise HistoricalExperimentInitializationError(
            *context,
            "factory-return",
            "factory must return exactly OptimizedPaperPortfolioSimulator",
        )
    components = {
        "simulator": simulator,
        "runtime": simulator.runtime,
        "engine": simulator.engine,
        "ledger": simulator.ledger,
    }
    if type(simulator.runtime) is not PaperPortfolioRuntime:
        raise HistoricalExperimentInitializationError(
            *context, "runtime-type", "simulator runtime has an invalid type"
        )
    if (
        type(simulator.engine) is not OrderEngine
        or type(simulator.ledger) is not PaperLedger
    ):
        raise HistoricalExperimentInitializationError(
            *context, "component-type", "engine or ledger has an invalid type"
        )
    for name, component in components.items():
        if any(component is prior for prior in seen[name]):
            raise HistoricalExperimentIsolationError(
                *context, f"{name}-isolation", f"{name} was reused across variants"
            )
        seen[name].append(component)
    if engine_snapshot(simulator.engine) != ((), (), ()):
        raise HistoricalExperimentInitializationError(
            *context, "engine-state", "initial engine must be empty"
        )
    _validate_ledger_content(simulator.ledger, initial, context)


def _retain_component_identities(
    simulator: OptimizedPaperPortfolioSimulator,
    seen: dict[str, list[object]],
) -> None:
    """Keep strong references to post-run components that atomic commits replaced."""
    components = {
        "simulator": simulator,
        "runtime": simulator.runtime,
        "engine": simulator.engine,
        "ledger": simulator.ledger,
    }
    for name, component in components.items():
        if not any(component is prior for prior in seen[name]):
            seen[name].append(component)


def _validate_ledger_content(
    ledger: PaperLedger,
    initial: HistoricalExperimentInitialState,
    context: tuple[int, UUID, str],
) -> None:
    if ledger.cash != initial.available_cash or ledger.realized_profit_loss != _ZERO:
        raise HistoricalExperimentInitializationError(
            *context, "ledger-state", "initial ledger cash or realized P&L differs"
        )
    positions = ledger.positions
    expected = initial.bootstrap_positions
    if tuple(positions) != tuple(item.symbol for item in expected):
        raise HistoricalExperimentInitializationError(
            *context, "ledger-positions", "initial ledger position order differs"
        )
    for item in expected:
        position = positions[item.symbol]
        if (
            position.quantity != item.quantity
            or position.average_cost != item.unit_cost
        ):
            raise HistoricalExperimentInitializationError(
                *context, "ledger-positions", "initial ledger position content differs"
            )
    fills = ledger.fills
    if len(fills) != len(expected):
        raise HistoricalExperimentInitializationError(
            *context, "ledger-fills", "initial ledger fill count differs"
        )
    for fill, item in zip(fills, expected, strict=True):
        if (
            fill.symbol != item.symbol
            or fill.side is not OrderSide.BUY
            or fill.quantity != item.quantity
            or fill.price != item.unit_cost
            or fill.commission != _ZERO
            or fill.filled_at != initial.as_of
        ):
            raise HistoricalExperimentInitializationError(
                *context, "ledger-fills", "initial bootstrap fill content differs"
            )
    if len({item.fill_id for item in fills}) != len(fills) or len(
        {item.order_id for item in fills}
    ) != len(fills):
        raise HistoricalExperimentInitializationError(
            *context, "ledger-fills", "bootstrap fill or order IDs must be unique"
        )


def _rolling_request(
    request: HistoricalExperimentRequest,
    variant: HistoricalExperimentVariant,
    ordinal: int,
    rolling_id: UUID,
) -> RollingHistoricalSimulationRequest:
    return RollingHistoricalSimulationRequest(
        rolling_id,
        request.historical_data,
        request.rebalance_timestamps,
        variant.window_policy,
        variant.scenario_policy,
        variant.execution_price_policy,
        variant.timing_policy,
        variant.scenario_cash_return,
        variant.scenario_source_name,
        variant.optimization_parameters,
        variant.risk_aversion,
        variant.portfolio_constraints,
        variant.rebalance_assumptions,
        variant.proposal_policy,
        variant.proposal_confidence,
        variant.risk_limits,
        variant.risk_policy,
        variant.fill_policy,
        variant.trading_enabled,
        _rolling_metadata(request, variant, ordinal),
    )


def _rolling_metadata(
    request: HistoricalExperimentRequest,
    variant: HistoricalExperimentVariant,
    ordinal: int,
) -> tuple[MetadataEntry, ...]:
    return (
        MetadataEntry("historical_experiment_id", str(request.request_id)),
        MetadataEntry("historical_experiment_variant_id", str(variant.variant_id)),
        MetadataEntry("historical_experiment_variant_ordinal", str(ordinal)),
        MetadataEntry("historical_experiment_variant_name", variant.name),
    )


def _project_metrics(
    rolling_result: RollingHistoricalSimulationResult,
) -> HistoricalExperimentMetrics:
    performance = rolling_result.performance_result
    optimization = performance.optimization_summary
    return HistoricalExperimentMetrics(
        performance.initial_equity,
        performance.final_equity,
        performance.absolute_simulation_profit_loss,
        performance.simulation_return,
        performance.drawdowns.maximum_amount.amount,
        performance.drawdowns.maximum_percentage.percentage,
        performance.cumulative_simulation_realized_profit_loss,
        performance.total_commissions,
        performance.total_adverse_slippage_cost,
        performance.total_execution_cost,
        performance.aggregate_one_way_turnover,
        performance.aggregate_two_way_turnover,
        performance.maximum_absolute_allocation_drift,
        performance.total_order_count,
        performance.total_fill_count,
        performance.total_approved_risk_count,
        performance.total_resized_risk_count,
        performance.total_rejected_risk_count,
        performance.total_rejected_notional,
        performance.total_reduced_notional,
        optimization.mean_expected_portfolio_return,
        optimization.worst_cvar,
        optimization.minimum_target_cash_weight,
        optimization.maximum_target_cash_weight,
        performance.applied_cycle_count,
        performance.no_action_cycle_count,
    )


def _historical_fingerprint(data: MultiSymbolHistoricalDataResult) -> UUID:
    return _id("historical-data", *canonical_multi_symbol_historical_material(data))


def _schedule_fingerprint(timestamps: tuple[datetime, ...]) -> UUID:
    return _id("schedule", *(item.isoformat() for item in timestamps))


def _initial_state_fingerprint(state: HistoricalExperimentInitialState) -> UUID:
    return _id("initial-state", *_initial_material(state))


def _live_initial_state_fingerprint(
    simulator: OptimizedPaperPortfolioSimulator,
    specification: HistoricalExperimentInitialState,
) -> UUID:
    ledger = simulator.ledger
    material = [
        (
            HistoricalExperimentInitializationMode.CASH_ONLY.value
            if not ledger.fills
            else HistoricalExperimentInitializationMode.BOOTSTRAP_FILLS.value
        ),
        (
            ledger.fills[0].filled_at.isoformat()
            if ledger.fills
            else specification.as_of.isoformat()
        ),
        canonical_decimal(ledger.cash),
    ]
    for fill in ledger.fills:
        material.extend(
            (
                str(fill.symbol),
                canonical_decimal(fill.quantity),
                canonical_decimal(fill.price),
            )
        )
    material.append("0")
    return _id("initial-state", *material)


def _initial_material(state: HistoricalExperimentInitialState) -> tuple[str, ...]:
    material = [
        state.mode.value,
        state.as_of.isoformat(),
        canonical_decimal(state.available_cash),
    ]
    for item in state.bootstrap_positions:
        material.extend(
            (
                str(item.symbol),
                canonical_decimal(item.quantity),
                canonical_decimal(item.unit_cost),
            )
        )
    material.append(canonical_decimal(state.bootstrap_commission))
    return tuple(material)


def _variant_fingerprint(variant: HistoricalExperimentVariant) -> UUID:
    return _id("variant", *_variant_material(variant))


def _variant_material(variant: HistoricalExperimentVariant) -> tuple[str, ...]:
    parameters = variant.optimization_parameters
    constraints = variant.portfolio_constraints
    assumptions = variant.rebalance_assumptions
    limits = variant.risk_limits
    return (
        str(variant.variant_id),
        variant.name,
        str(variant.window_policy.observation_count),
        variant.scenario_policy.price_field.value,
        variant.scenario_policy.return_method.value,
        variant.scenario_policy.window_policy.value,
        variant.execution_price_policy.risk_price_field.value,
        variant.execution_price_policy.fill_reference_price_field.value,
        str(_microseconds(variant.timing_policy.submission_offset)),
        str(_microseconds(variant.timing_policy.fill_offset)),
        canonical_decimal(variant.scenario_cash_return),
        variant.scenario_source_name,
        canonical_decimal(parameters.confidence_level),
        _optional(parameters.minimum_expected_return),
        canonical_decimal(parameters.solver_tolerance),
        str(parameters.maximum_iterations),
        canonical_decimal(parameters.output_quantum),
        canonical_decimal(variant.risk_aversion),
        canonical_decimal(constraints.minimum_cash_weight),
        canonical_decimal(constraints.maximum_cash_weight),
        canonical_decimal(constraints.maximum_position_weight),
        _optional(constraints.maximum_one_way_rebalance_turnover),
        _optional(constraints.minimum_position_weight),
        str(constraints.long_only),
        str(constraints.allow_leverage),
        canonical_decimal(assumptions.fixed_commission),
        str(assumptions.allow_fractional_quantities),
        canonical_decimal(assumptions.quantity_increment),
        canonical_decimal(assumptions.minimum_trade_notional),
        canonical_decimal(assumptions.minimum_trade_quantity),
        canonical_decimal(assumptions.target_weight_tolerance),
        canonical_decimal(assumptions.additional_execution_cash_buffer),
        str(assumptions.use_planned_sell_proceeds),
        str(variant.proposal_policy.allow_partial_plans),
        _optional(variant.proposal_confidence),
        canonical_decimal(limits.max_position_percent),
        canonical_decimal(limits.max_total_exposure_percent),
        _optional(limits.max_order_notional),
        _optional(limits.max_new_position_percent),
        canonical_decimal(limits.minimum_cash_reserve_percent),
        str(limits.allow_fractional_shares),
        canonical_decimal(limits.fractional_increment),
        str(limits.allow_buying),
        str(limits.allow_selling),
        canonical_decimal(limits.estimated_commission),
        str(variant.risk_policy.allow_sell_proceeds_for_later_buys),
        canonical_decimal(variant.fill_policy.slippage_basis_points),
        canonical_decimal(variant.fill_policy.fixed_commission),
        str(variant.trading_enabled),
        *(f"{item.key}={item.value}" for item in variant.metadata),
    )


def _rolling_request_id(
    request: HistoricalExperimentRequest,
    variant: HistoricalExperimentVariant,
    ordinal: int,
    historical_id: UUID,
    schedule_id: UUID,
    initial_id: UUID,
) -> UUID:
    return _id(
        "rolling-simulation",
        str(request.request_id),
        str(variant.variant_id),
        str(ordinal),
        str(historical_id),
        str(schedule_id),
        str(initial_id),
    )


def _run_id(
    experiment_id: UUID,
    variant: HistoricalExperimentVariant,
    rolling_request_id: UUID,
    rolling_result_id: UUID,
    initial_id: UUID,
    metrics: HistoricalExperimentMetrics,
) -> UUID:
    return _id(
        "variant-run",
        str(experiment_id),
        str(_variant_fingerprint(variant)),
        str(rolling_request_id),
        str(rolling_result_id),
        str(initial_id),
        *_metrics_material(metrics),
    )


def _result_id(
    request: HistoricalExperimentRequest,
    runs: tuple[HistoricalExperimentRun, ...],
    historical_id: UUID,
    schedule_id: UUID,
    initial_id: UUID,
) -> UUID:
    return _id(
        "result",
        str(_request_fingerprint(request)),
        str(historical_id),
        str(schedule_id),
        str(initial_id),
        *(str(item.run_id) for item in runs),
    )


def _request_fingerprint(request: HistoricalExperimentRequest) -> UUID:
    return _id(
        "request",
        str(request.request_id),
        str(_historical_fingerprint(request.historical_data)),
        str(_schedule_fingerprint(request.rebalance_timestamps)),
        str(_initial_state_fingerprint(request.initial_state)),
        *(str(_variant_fingerprint(item)) for item in request.variants),
        *(f"{item.key}={item.value}" for item in request.metadata),
    )


def _metrics_material(metrics: HistoricalExperimentMetrics) -> tuple[str, ...]:
    return tuple(
        canonical_decimal(value) if isinstance(value, Decimal) else str(value)
        for value in (
            metrics.initial_equity,
            metrics.final_equity,
            metrics.absolute_simulation_profit_loss,
            metrics.simulation_return,
            metrics.maximum_drawdown_amount,
            metrics.maximum_drawdown_percentage,
            metrics.simulation_realized_profit_loss,
            metrics.total_commissions,
            metrics.adverse_slippage_cost,
            metrics.total_execution_cost,
            metrics.aggregate_one_way_turnover,
            metrics.aggregate_two_way_turnover,
            metrics.maximum_allocation_drift,
            metrics.total_orders,
            metrics.total_fills,
            metrics.approved_decisions,
            metrics.resized_decisions,
            metrics.rejected_decisions,
            metrics.rejected_notional,
            metrics.reduced_notional,
            metrics.mean_expected_portfolio_return,
            metrics.worst_cvar,
            metrics.minimum_target_cash_weight,
            metrics.maximum_target_cash_weight,
            metrics.applied_cycle_count,
            metrics.no_action_cycle_count,
        )
    )


def _validated_metadata(values, error_type):  # type: ignore[no-untyped-def]
    try:
        metadata = tuple(values)
    except TypeError as caught:
        raise error_type("metadata must be iterable") from caught
    if not all(isinstance(item, MetadataEntry) for item in metadata):
        raise error_type("metadata must contain MetadataEntry values")
    if len({item.key for item in metadata}) != len(metadata):
        raise error_type("metadata keys must be unique")
    if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
        raise error_type(f"{_RESERVED_PREFIX} metadata keys are reserved")
    return metadata


def _metadata_uuid(metadata: tuple[MetadataEntry, ...], key: str, error_type) -> UUID:  # type: ignore[no-untyped-def]
    matches = tuple(item.value for item in metadata if item.key == key)
    if len(matches) != 1:
        raise error_type(f"{key} metadata is missing or duplicated")
    try:
        return UUID(matches[0])
    except ValueError as caught:
        raise error_type(f"{key} metadata is not a UUID") from caught


def _finite_decimal(value, name: str, error_type):  # type: ignore[no-untyped-def]
    if (
        not isinstance(value, Decimal)
        or isinstance(value, bool)
        or not value.is_finite()
    ):
        raise error_type(f"{name} must be a finite Decimal")
    return value


def _optional(value: Decimal | None) -> str:
    return "none" if value is None else canonical_decimal(value)


def _normalize_zero(value: Decimal) -> Decimal:
    return _ZERO if value == _ZERO else value


def _microseconds(value) -> int:  # type: ignore[no-untyped-def]
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


def _id(stage: str, *material: str) -> UUID:
    return uuid5(_NAMESPACE, "|".join((_VERSION, stage, *material)))
