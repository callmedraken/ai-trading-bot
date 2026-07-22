"""Optimizer-driven deterministic multi-cycle paper portfolio simulation."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.domain._validation import normalize_utc
from trading_bot.execution import OrderEngine, PaperFillPolicy
from trading_bot.execution.state_fingerprints import (
    canonical_decimal,
    engine_snapshot,
    engine_state_id,
    ledger_snapshot,
    ledger_state_id,
)
from trading_bot.ledger import PaperLedger
from trading_bot.optimization import CpuMeanCvarOptimizer
from trading_bot.optimization.exceptions import OptimizationAdapterError
from trading_bot.portfolio import (
    ExpectedReturn,
    MeanCvarOptimizationParameters,
    MeanCvarOptimizationRequest,
    MeanCvarOptimizationResult,
    MetadataEntry,
    OptimizationStatus,
    OptimizedTargetAdapterError,
    OptimizedTargetPortfolioFactory,
    OptimizedTargetRequest,
    OptimizedTargetResult,
    PortfolioConstraints,
    PortfolioOptimizationRequest,
    PortfolioState,
    ReturnScenarioSet,
)
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import (
    PaperPortfolioCycleInputs,
    PaperPortfolioCyclePrice,
    PaperPortfolioCycleRequest,
    PaperPortfolioCycleResult,
    PaperPortfolioCycleStatus,
    PaperPortfolioRuntime,
    PaperPortfolioRuntimeError,
)
from trading_bot.simulation._portfolio_state import derive_portfolio_state
from trading_bot.simulation.exceptions import (
    InconsistentOptimizedPaperSimulationResultError,
    InvalidOptimizedPaperSimulationFrameError,
    InvalidOptimizedPaperSimulationRequestError,
    OptimizedPaperSimulationCertificationError,
    OptimizedPaperSimulationOptimizationError,
    PaperPortfolioSimulationCycleError,
    PaperPortfolioSimulationStateMismatchError,
)
from trading_bot.simulation.paper_portfolio import (
    PaperPortfolioSimulationDiagnostic,
    PaperPortfolioSimulationDiagnosticCode,
    PaperPortfolioSimulationStatus,
)

_ZERO = Decimal("0")
_VERSION = "optimized-paper-simulation-v1"
_NAMESPACE = UUID("7e4e39cd-e22f-596a-9dae-95e8f8daa5ab")
_RESERVED_PREFIX = "optimized_simulation_"


def _metadata(values, error_type):  # type: ignore[no-untyped-def]
    try:
        items = tuple(values)
    except TypeError as caught:
        raise error_type("metadata must be iterable") from caught
    if not all(isinstance(item, MetadataEntry) for item in items):
        raise error_type("metadata must contain MetadataEntry values")
    if len({item.key for item in items}) != len(items):
        raise error_type("metadata keys must be unique")
    if any(item.key.startswith(_RESERVED_PREFIX) for item in items):
        raise error_type("optimized_simulation_ metadata keys are reserved")
    return items


@dataclass(frozen=True, slots=True)
class OptimizedPaperSimulationFrame:
    as_of: datetime
    prices: tuple[PaperPortfolioCyclePrice, ...]
    expected_returns: tuple[ExpectedReturn, ...]
    scenarios: ReturnScenarioSet
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
    submitted_at: datetime
    filled_at: datetime
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidOptimizedPaperSimulationFrameError
        for name, expected in (
            ("scenarios", ReturnScenarioSet),
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
        if not isinstance(self.trading_enabled, bool):
            raise error("trading_enabled must be a bool")
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
        try:
            prices = tuple(self.prices)
            expected_returns = tuple(self.expected_returns)
        except TypeError as caught:
            raise error("prices and expected_returns must be iterable") from caught
        if not prices or not all(
            isinstance(item, PaperPortfolioCyclePrice) for item in prices
        ):
            raise error("prices must contain PaperPortfolioCyclePrice values")
        if not expected_returns or not all(
            isinstance(item, ExpectedReturn) for item in expected_returns
        ):
            raise error("expected_returns must contain ExpectedReturn values")
        price_symbols = tuple(item.symbol for item in prices)
        if len(set(price_symbols)) != len(price_symbols):
            raise error("price symbols must be unique")
        if tuple(item.symbol for item in expected_returns) != price_symbols:
            raise error("expected-return symbols must exactly match price order")
        if self.scenarios.symbols != price_symbols:
            raise error("scenario symbols must exactly match price order")
        try:
            as_of = normalize_utc(self.as_of, "as_of")
            submitted_at = normalize_utc(self.submitted_at, "submitted_at")
            filled_at = normalize_utc(self.filled_at, "filled_at")
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        if self.scenarios.as_of != as_of:
            raise error("scenario as_of must equal frame as_of")
        if not as_of <= submitted_at <= filled_at:
            raise error("timestamps must satisfy as_of <= submitted_at <= filled_at")
        if not (
            self.rebalance_assumptions.fixed_commission
            == self.risk_limits.estimated_commission
            == self.fill_policy.fixed_commission
        ):
            raise error("planner, risk, and fill fixed commissions must match")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "submitted_at", submitted_at)
        object.__setattr__(self, "filled_at", filled_at)
        object.__setattr__(self, "prices", prices)
        object.__setattr__(self, "expected_returns", expected_returns)
        object.__setattr__(
            self, "risk_aversion", _ZERO if risk_aversion == _ZERO else risk_aversion
        )
        object.__setattr__(
            self, "proposal_confidence", _ZERO if confidence == _ZERO else confidence
        )
        object.__setattr__(self, "metadata", _metadata(self.metadata, error))


@dataclass(frozen=True, slots=True)
class OptimizedPaperSimulationRequest:
    request_id: UUID
    frames: tuple[OptimizedPaperSimulationFrame, ...]
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidOptimizedPaperSimulationRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        try:
            frames = tuple(self.frames)
        except TypeError as caught:
            raise error("frames must be iterable") from caught
        if not frames or not all(
            isinstance(item, OptimizedPaperSimulationFrame) for item in frames
        ):
            raise error("frames must contain at least one optimized frame")
        metadata = _metadata(self.metadata, error)
        for ordinal, frame in enumerate(frames):
            if ordinal and (
                frame.as_of <= frames[ordinal - 1].as_of
                or frame.as_of < frames[ordinal - 1].filled_at
            ):
                raise error("frame as_of values must increase and follow prior fill")
            keys = [item.key for item in (*metadata, *frame.metadata)]
            if len(set(keys)) != len(keys):
                raise error("request and frame metadata keys must not overlap")
        object.__setattr__(self, "frames", frames)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class OptimizedPaperSimulationEvaluation:
    frame_ordinal: int
    frame: OptimizedPaperSimulationFrame
    derived_state: PortfolioState
    optimization_request_id: UUID
    optimization_result: MeanCvarOptimizationResult
    optimized_target_result: OptimizedTargetResult
    cycle_request_id: UUID
    cycle_result: PaperPortfolioCycleResult
    pre_engine_state_id: UUID
    pre_ledger_state_id: UUID
    post_engine_state_id: UUID
    post_ledger_state_id: UUID

    def __post_init__(self) -> None:
        error = InconsistentOptimizedPaperSimulationResultError
        if (
            not isinstance(self.frame_ordinal, int)
            or isinstance(self.frame_ordinal, bool)
            or self.frame_ordinal < 0
        ):
            raise error("frame_ordinal must be a nonnegative integer")
        if not isinstance(self.frame, OptimizedPaperSimulationFrame):
            raise error("frame has an invalid type")
        if not isinstance(self.derived_state, PortfolioState):
            raise error("derived_state has an invalid type")
        if not isinstance(self.optimization_request_id, UUID):
            raise error("optimization_request_id must be a UUID")
        if not isinstance(self.optimization_result, MeanCvarOptimizationResult):
            raise error("optimization_result has an invalid type")
        if not isinstance(self.optimized_target_result, OptimizedTargetResult):
            raise error("optimized_target_result has an invalid type")
        if not isinstance(self.cycle_request_id, UUID):
            raise error("cycle_request_id must be a UUID")
        if not isinstance(self.cycle_result, PaperPortfolioCycleResult):
            raise error("cycle_result has an invalid type")
        base = self.optimization_result.request.base_request
        if (
            base.request_id != self.optimization_request_id
            or base.state != self.derived_state
            or base.expected_returns != self.frame.expected_returns
            or self.optimization_result.request.scenarios != self.frame.scenarios
            or self.optimization_result.request.parameters
            != self.frame.optimization_parameters
        ):
            raise error("optimization request does not match evaluation state")
        if (
            self.optimized_target_result.request.optimization_result
            != self.optimization_result
            or (self.optimized_target_result.request.state != self.derived_state)
        ):
            raise error("certification does not match optimization and state")
        source_target = self.optimization_result.optimization_result.target
        if (
            source_target is None
            or self.optimized_target_result.target != source_target
        ):
            raise error("certified target does not match optimizer target")
        cycle_inputs = self.cycle_result.request.inputs
        if (
            self.cycle_result.request.request_id != self.cycle_request_id
            or cycle_inputs.state != self.derived_state
            or cycle_inputs.target != self.optimized_target_result.target
        ):
            raise error("runtime cycle does not match certified target and state")
        for name in (
            "pre_engine_state_id",
            "pre_ledger_state_id",
            "post_engine_state_id",
            "post_ledger_state_id",
        ):
            if not isinstance(getattr(self, name), UUID) or getattr(
                self, name
            ) != getattr(self.cycle_result, name):
                raise error(f"{name} does not match cycle result")


@dataclass(frozen=True, slots=True)
class OptimizedPaperSimulationResult:
    result_id: UUID
    request: OptimizedPaperSimulationRequest
    evaluations: tuple[OptimizedPaperSimulationEvaluation, ...]
    initial_engine_state_id: UUID
    initial_ledger_state_id: UUID
    final_engine_state_id: UUID
    final_ledger_state_id: UUID
    applied_cycle_count: int
    no_action_cycle_count: int
    status: PaperPortfolioSimulationStatus
    diagnostics: tuple[PaperPortfolioSimulationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentOptimizedPaperSimulationResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, OptimizedPaperSimulationRequest):
            raise error("request has an invalid type")
        try:
            evaluations = tuple(self.evaluations)
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("result tuple fields must be iterable") from caught
        if len(evaluations) != len(self.request.frames) or not all(
            isinstance(item, OptimizedPaperSimulationEvaluation) for item in evaluations
        ):
            raise error("evaluations must exactly cover request frames")
        if not all(
            isinstance(item, PaperPortfolioSimulationDiagnostic) for item in diagnostics
        ):
            raise error("diagnostics contain invalid values")
        _validate_result(self, evaluations, diagnostics)
        if self.result_id != _result_id(
            self.request,
            evaluations,
            self.initial_engine_state_id,
            self.initial_ledger_state_id,
            self.final_engine_state_id,
            self.final_ledger_state_id,
            self.applied_cycle_count,
            self.no_action_cycle_count,
            self.status,
            tuple(item.code for item in diagnostics),
        ):
            raise error("result_id does not match deterministic identity")
        object.__setattr__(self, "evaluations", evaluations)
        object.__setattr__(self, "diagnostics", diagnostics)


class OptimizedPaperPortfolioSimulator:
    """Optimize, certify, and execute ordered frames through one runtime."""

    _optimizer_type = CpuMeanCvarOptimizer
    _target_factory_type = OptimizedTargetPortfolioFactory

    def __init__(self, runtime: PaperPortfolioRuntime) -> None:
        if not isinstance(runtime, PaperPortfolioRuntime):
            raise TypeError("runtime must be a PaperPortfolioRuntime")
        self._runtime = runtime

    @property
    def runtime(self) -> PaperPortfolioRuntime:
        return self._runtime

    @property
    def engine(self) -> OrderEngine:
        return self._runtime.engine

    @property
    def ledger(self) -> PaperLedger:
        return self._runtime.ledger

    def run(
        self, request: OptimizedPaperSimulationRequest
    ) -> OptimizedPaperSimulationResult:
        if not isinstance(request, OptimizedPaperSimulationRequest):
            raise TypeError("request must be an OptimizedPaperSimulationRequest")
        initial_engine_id = engine_state_id(engine_snapshot(self.engine))
        initial_ledger_id = ledger_state_id(ledger_snapshot(self.ledger))
        evaluations: list[OptimizedPaperSimulationEvaluation] = []
        prior_cycle_result_id: UUID | None = None
        for ordinal, frame in enumerate(request.frames):
            pre_engine_id = engine_state_id(engine_snapshot(self.engine))
            pre_ledger_id = ledger_state_id(ledger_snapshot(self.ledger))
            state = derive_portfolio_state(self.ledger, frame.as_of, frame.prices)
            optimization_id = _optimization_id(
                request,
                frame,
                ordinal,
                state,
                pre_engine_id,
                pre_ledger_id,
                prior_cycle_result_id,
            )
            combined_metadata = _combined_metadata(request, frame, ordinal)
            mean_request = MeanCvarOptimizationRequest(
                PortfolioOptimizationRequest(
                    optimization_id,
                    state,
                    frame.portfolio_constraints,
                    frame.expected_returns,
                    frame.scenarios.forecast_horizon,
                    frame.risk_aversion,
                    combined_metadata,
                ),
                frame.scenarios,
                frame.optimization_parameters,
            )
            try:
                optimization_result = self._optimizer_type().optimize(mean_request)
            except OptimizationAdapterError as caught:
                raise OptimizedPaperSimulationOptimizationError(
                    ordinal,
                    f"optimizer raised for frame {ordinal}",
                ) from caught
            if optimization_result.request is not mean_request:
                raise PaperPortfolioSimulationStateMismatchError(
                    f"optimizer replaced its source request for frame {ordinal}"
                )
            portfolio_result = optimization_result.optimization_result
            if portfolio_result.status is not OptimizationStatus.OPTIMAL:
                raise OptimizedPaperSimulationOptimizationError(
                    ordinal,
                    f"optimizer did not produce OPTIMAL output for frame {ordinal}",
                    status=portfolio_result.status,
                    diagnostic_codes=tuple(
                        item.code for item in portfolio_result.diagnostics
                    ),
                )
            certification_id = _stage_id(
                request,
                frame,
                ordinal,
                "target-certification",
                portfolio_result.result_id,
            )
            target_request = OptimizedTargetRequest(
                certification_id,
                optimization_result,
                state,
                combined_metadata,
            )
            try:
                target_result = self._target_factory_type().create(target_request)
            except OptimizedTargetAdapterError as caught:
                raise OptimizedPaperSimulationCertificationError(
                    ordinal, f"target certification failed for frame {ordinal}"
                ) from caught
            if (
                target_result.request.optimization_result is not optimization_result
                or target_result.request.state is not state
                or target_result.target is not portfolio_result.target
            ):
                raise PaperPortfolioSimulationStateMismatchError(
                    f"certification replaced live frame objects for frame {ordinal}"
                )
            if (
                engine_state_id(engine_snapshot(self.engine)) != pre_engine_id
                or ledger_state_id(ledger_snapshot(self.ledger)) != pre_ledger_id
            ):
                raise PaperPortfolioSimulationStateMismatchError(
                    f"optimization changed runtime state for frame {ordinal}"
                )
            cycle_id = _stage_id(
                request,
                frame,
                ordinal,
                "runtime-cycle",
                target_result.result_id,
            )
            try:
                cycle_request = PaperPortfolioCycleRequest(
                    cycle_id,
                    PaperPortfolioCycleInputs(
                        state,
                        target_result.target,
                        frame.rebalance_assumptions,
                        frame.portfolio_constraints,
                        frame.proposal_policy,
                        frame.proposal_confidence,
                        frame.risk_limits,
                        frame.risk_policy,
                        frame.prices,
                        frame.fill_policy,
                        frame.trading_enabled,
                        frame.submitted_at,
                        frame.filled_at,
                    ),
                    combined_metadata,
                )
                cycle_result = self._runtime.run_cycle(cycle_request)
            except PaperPortfolioRuntimeError as caught:
                raise PaperPortfolioSimulationCycleError(
                    ordinal, f"paper portfolio cycle failed for frame {ordinal}"
                ) from caught
            post_engine_id = engine_state_id(engine_snapshot(self.engine))
            post_ledger_id = ledger_state_id(ledger_snapshot(self.ledger))
            if (
                cycle_result.pre_engine_state_id != pre_engine_id
                or cycle_result.pre_ledger_state_id != pre_ledger_id
                or cycle_result.post_engine_state_id != post_engine_id
                or cycle_result.post_ledger_state_id != post_ledger_id
            ):
                raise PaperPortfolioSimulationStateMismatchError(
                    f"runtime state does not match cycle audit for frame {ordinal}"
                )
            evaluations.append(
                OptimizedPaperSimulationEvaluation(
                    ordinal,
                    frame,
                    state,
                    optimization_id,
                    optimization_result,
                    target_result,
                    cycle_id,
                    cycle_result,
                    pre_engine_id,
                    pre_ledger_id,
                    post_engine_id,
                    post_ledger_id,
                )
            )
            prior_cycle_result_id = cycle_result.result_id
        applied = sum(
            item.cycle_result.status is PaperPortfolioCycleStatus.APPLIED
            for item in evaluations
        )
        no_action = len(evaluations) - applied
        status = (
            PaperPortfolioSimulationStatus.COMPLETED
            if applied
            else PaperPortfolioSimulationStatus.NO_ACTION
        )
        diagnostics = (
            ()
            if applied
            else (
                PaperPortfolioSimulationDiagnostic(
                    PaperPortfolioSimulationDiagnosticCode.ALL_CYCLES_NO_ACTION,
                    "every optimized simulation cycle completed without an action",
                ),
            )
        )
        final_engine_id = engine_state_id(engine_snapshot(self.engine))
        final_ledger_id = ledger_state_id(ledger_snapshot(self.ledger))
        return _build_result(
            request,
            tuple(evaluations),
            initial_engine_id,
            initial_ledger_id,
            final_engine_id,
            final_ledger_id,
            applied,
            no_action,
            status,
            diagnostics,
        )


def _combined_metadata(request, frame, ordinal):  # type: ignore[no-untyped-def]
    return (
        *request.metadata,
        *frame.metadata,
        MetadataEntry("optimized_simulation_id", str(request.request_id)),
        MetadataEntry("optimized_simulation_frame_ordinal", str(ordinal)),
    )


def _optional(value):  # type: ignore[no-untyped-def]
    return "none" if value is None else canonical_decimal(value)


def _scenario_material(item) -> str:  # type: ignore[no-untyped-def]
    returns = ",".join(canonical_decimal(value) for value in item.returns)
    metadata = ",".join(f"{meta.key}={meta.value}" for meta in item.metadata)
    return ":".join(
        (
            str(item.scenario_id),
            returns,
            canonical_decimal(item.probability),
            metadata,
        )
    )


def _frame_fingerprint(frame: OptimizedPaperSimulationFrame, ordinal: int) -> str:
    scenarios = frame.scenarios
    parameters = frame.optimization_parameters
    constraints = frame.portfolio_constraints
    assumptions = frame.rebalance_assumptions
    limits = frame.risk_limits
    return "|".join(
        (
            _VERSION,
            str(ordinal),
            frame.as_of.isoformat(),
            frame.submitted_at.isoformat(),
            frame.filled_at.isoformat(),
            *(
                f"price={item.symbol}:{canonical_decimal(item.risk_price)}:{canonical_decimal(item.fill_reference_price)}"
                for item in frame.prices
            ),
            *(
                f"return={item.symbol}:{canonical_decimal(item.value)}"
                for item in frame.expected_returns
            ),
            str(scenarios.scenario_set_id),
            scenarios.as_of.isoformat(),
            str(scenarios.forecast_horizon.periods),
            scenarios.forecast_horizon.timeframe.value,
            *(f"scenario-symbol={item}" for item in scenarios.symbols),
            *(f"scenario={_scenario_material(item)}" for item in scenarios.scenarios),
            canonical_decimal(scenarios.cash_return),
            scenarios.source.value,
            "none" if scenarios.source_name is None else scenarios.source_name,
            *(f"scenario-meta={item.key}={item.value}" for item in scenarios.metadata),
            canonical_decimal(parameters.confidence_level),
            _optional(parameters.minimum_expected_return),
            canonical_decimal(parameters.solver_tolerance),
            "none"
            if parameters.maximum_iterations is None
            else str(parameters.maximum_iterations),
            canonical_decimal(parameters.output_quantum),
            canonical_decimal(frame.risk_aversion),
            canonical_decimal(constraints.minimum_cash_weight),
            canonical_decimal(constraints.maximum_cash_weight),
            canonical_decimal(constraints.maximum_position_weight),
            _optional(constraints.minimum_position_weight),
            _optional(constraints.maximum_one_way_rebalance_turnover),
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
            str(frame.proposal_policy.allow_partial_plans),
            _optional(frame.proposal_confidence),
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
            str(frame.risk_policy.allow_sell_proceeds_for_later_buys),
            canonical_decimal(frame.fill_policy.slippage_basis_points),
            canonical_decimal(frame.fill_policy.fixed_commission),
            str(frame.trading_enabled),
            *(f"meta={item.key}={item.value}" for item in frame.metadata),
        )
    )


def _state_fingerprint(state: PortfolioState) -> str:
    return "|".join(
        (
            state.as_of.isoformat(),
            canonical_decimal(state.cash),
            canonical_decimal(state.equity),
            *(
                f"{item.symbol}:{canonical_decimal(item.quantity)}:{canonical_decimal(item.average_cost)}:{canonical_decimal(item.current_price)}"
                for item in state.positions
            ),
        )
    )


def _request_fingerprint(request: OptimizedPaperSimulationRequest) -> str:
    return "|".join(
        (
            _VERSION,
            str(request.request_id),
            *(f"meta={item.key}={item.value}" for item in request.metadata),
            *(
                f"frame={_frame_fingerprint(frame, ordinal)}"
                for ordinal, frame in enumerate(request.frames)
            ),
        )
    )


def _optimization_id(
    request,
    frame,
    ordinal,
    state,
    pre_engine_id,
    pre_ledger_id,
    prior_cycle_result_id,
):  # type: ignore[no-untyped-def]
    predecessor = (
        f"initial:{pre_engine_id}:{pre_ledger_id}"
        if prior_cycle_result_id is None
        else f"prior:{prior_cycle_result_id}"
    )
    return uuid5(
        _NAMESPACE,
        "|".join(
            (
                _VERSION,
                str(request.request_id),
                str(ordinal),
                _frame_fingerprint(frame, ordinal),
                _state_fingerprint(state),
                predecessor,
                "optimization-request",
            )
        ),
    )


def _stage_id(request, frame, ordinal, stage, upstream):  # type: ignore[no-untyped-def]
    return uuid5(
        _NAMESPACE,
        "|".join(
            (
                _VERSION,
                str(request.request_id),
                str(ordinal),
                _frame_fingerprint(frame, ordinal),
                str(upstream),
                stage,
            )
        ),
    )


def _validate_result(result, evaluations, diagnostics):  # type: ignore[no-untyped-def]
    error = InconsistentOptimizedPaperSimulationResultError
    state_ids = (
        result.initial_engine_state_id,
        result.initial_ledger_state_id,
        result.final_engine_state_id,
        result.final_ledger_state_id,
    )
    if not all(isinstance(item, UUID) for item in state_ids):
        raise error("state IDs must be UUID values")
    prior_cycle_id = None
    for ordinal, (frame, evaluation) in enumerate(
        zip(result.request.frames, evaluations, strict=True)
    ):
        if evaluation.frame_ordinal != ordinal or evaluation.frame != frame:
            raise error("evaluation order does not match request frame order")
        expected_optimization_id = _optimization_id(
            result.request,
            frame,
            ordinal,
            evaluation.derived_state,
            evaluation.pre_engine_state_id,
            evaluation.pre_ledger_state_id,
            prior_cycle_id,
        )
        if evaluation.optimization_request_id != expected_optimization_id:
            raise error("optimization request ID does not match derivation")
        expected_certification_id = _stage_id(
            result.request,
            frame,
            ordinal,
            "target-certification",
            evaluation.optimization_result.optimization_result.result_id,
        )
        if (
            evaluation.optimized_target_result.request.request_id
            != expected_certification_id
        ):
            raise error("certification request ID does not match derivation")
        expected_cycle_id = _stage_id(
            result.request,
            frame,
            ordinal,
            "runtime-cycle",
            evaluation.optimized_target_result.result_id,
        )
        if evaluation.cycle_request_id != expected_cycle_id:
            raise error("runtime cycle request ID does not match derivation")
        if ordinal == 0:
            if (
                evaluation.pre_engine_state_id != result.initial_engine_state_id
                or evaluation.pre_ledger_state_id != result.initial_ledger_state_id
            ):
                raise error("first evaluation does not match initial state")
        else:
            previous = evaluations[ordinal - 1]
            if (
                previous.post_engine_state_id != evaluation.pre_engine_state_id
                or previous.post_ledger_state_id != evaluation.pre_ledger_state_id
            ):
                raise error("adjacent evaluation states do not chain")
        prior_cycle_id = evaluation.cycle_result.result_id
    if (
        evaluations[-1].post_engine_state_id != result.final_engine_state_id
        or evaluations[-1].post_ledger_state_id != result.final_ledger_state_id
    ):
        raise error("final state IDs do not match final evaluation")
    applied = sum(
        item.cycle_result.status is PaperPortfolioCycleStatus.APPLIED
        for item in evaluations
    )
    if (
        not isinstance(result.applied_cycle_count, int)
        or isinstance(result.applied_cycle_count, bool)
        or not isinstance(result.no_action_cycle_count, int)
        or isinstance(result.no_action_cycle_count, bool)
        or result.applied_cycle_count != applied
        or result.no_action_cycle_count != len(evaluations) - applied
    ):
        raise error("cycle counts do not reconcile")
    expected_status = (
        PaperPortfolioSimulationStatus.COMPLETED
        if applied
        else PaperPortfolioSimulationStatus.NO_ACTION
    )
    if result.status is not expected_status:
        raise error("status does not reconcile")
    expected_codes = (
        ()
        if applied
        else (PaperPortfolioSimulationDiagnosticCode.ALL_CYCLES_NO_ACTION,)
    )
    if tuple(item.code for item in diagnostics) != expected_codes:
        raise error("diagnostics do not reconcile")


def _result_id(
    request,
    evaluations,
    initial_engine_id,
    initial_ledger_id,
    final_engine_id,
    final_ledger_id,
    applied,
    no_action,
    status,
    codes,
):  # type: ignore[no-untyped-def]
    return uuid5(
        _NAMESPACE,
        "|".join(
            (
                _VERSION,
                _request_fingerprint(request),
                str(initial_engine_id),
                str(initial_ledger_id),
                *(
                    f"frame={_frame_fingerprint(item.frame, item.frame_ordinal)}"
                    for item in evaluations
                ),
                *(
                    f"optimization={item.optimization_result.optimization_result.result_id}"
                    for item in evaluations
                ),
                *(
                    f"certification={item.optimized_target_result.result_id}"
                    for item in evaluations
                ),
                *(f"cycle={item.cycle_result.result_id}" for item in evaluations),
                str(final_engine_id),
                str(final_ledger_id),
                str(applied),
                str(no_action),
                status.value,
                *(item.value for item in codes),
            )
        ),
    )


def _build_result(
    request,
    evaluations,
    initial_engine_id,
    initial_ledger_id,
    final_engine_id,
    final_ledger_id,
    applied,
    no_action,
    status,
    diagnostics,
):  # type: ignore[no-untyped-def]
    codes = tuple(item.code for item in diagnostics)
    return OptimizedPaperSimulationResult(
        _result_id(
            request,
            evaluations,
            initial_engine_id,
            initial_ledger_id,
            final_engine_id,
            final_ledger_id,
            applied,
            no_action,
            status,
            codes,
        ),
        request,
        evaluations,
        initial_engine_id,
        initial_ledger_id,
        final_engine_id,
        final_ledger_id,
        applied,
        no_action,
        status,
        diagnostics,
    )
