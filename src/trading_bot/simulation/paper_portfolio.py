"""Deterministic coordination of ordered paper portfolio runtime cycles."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
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
from trading_bot.portfolio import (
    InvalidPortfolioStateError,
    MetadataEntry,
    PortfolioConstraints,
    PortfolioPositionState,
    PortfolioState,
    TargetPortfolio,
)
from trading_bot.rebalancing import (
    RebalanceAssumptions,
    RebalanceProposalPolicy,
)
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
from trading_bot.simulation.exceptions import (
    InconsistentPaperPortfolioSimulationResultError,
    InvalidPaperPortfolioSimulationFrameError,
    InvalidPaperPortfolioSimulationRequestError,
    PaperPortfolioSimulationCycleError,
    PaperPortfolioSimulationStateDerivationError,
    PaperPortfolioSimulationStateMismatchError,
)

_ZERO = Decimal("0")
_VERSION = "paper-portfolio-simulation-v1"
_NAMESPACE = UUID("69965f23-c849-5686-91b8-3fb8043bb046")
_RESERVED_METADATA_PREFIX = "simulation_"


def _metadata(
    values: tuple[MetadataEntry, ...],
    error_type: type[ValueError],
) -> tuple[MetadataEntry, ...]:
    try:
        items = tuple(values)
    except TypeError as caught:
        raise error_type("metadata must be iterable") from caught
    if not all(isinstance(item, MetadataEntry) for item in items):
        raise error_type("metadata must contain MetadataEntry values")
    if len({item.key for item in items}) != len(items):
        raise error_type("metadata keys must be unique")
    if any(item.key.startswith(_RESERVED_METADATA_PREFIX) for item in items):
        raise error_type("simulation_ metadata keys are reserved")
    return items


@dataclass(frozen=True, slots=True)
class PaperPortfolioSimulationFrame:
    as_of: datetime
    target: TargetPortfolio
    prices: tuple[PaperPortfolioCyclePrice, ...]
    rebalance_assumptions: RebalanceAssumptions
    portfolio_constraints: PortfolioConstraints | None
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
        error = InvalidPaperPortfolioSimulationFrameError
        for name, expected in (
            ("target", TargetPortfolio),
            ("rebalance_assumptions", RebalanceAssumptions),
            ("proposal_policy", RebalanceProposalPolicy),
            ("risk_limits", RiskLimits),
            ("risk_policy", PortfolioRiskPolicy),
            ("fill_policy", PaperFillPolicy),
        ):
            if not isinstance(getattr(self, name), expected):
                raise error(f"{name} must be {expected.__name__}")
        if self.portfolio_constraints is not None and not isinstance(
            self.portfolio_constraints, PortfolioConstraints
        ):
            raise error("portfolio_constraints must be PortfolioConstraints or None")
        if not isinstance(self.trading_enabled, bool):
            raise error("trading_enabled must be a bool")
        confidence = self.proposal_confidence
        if confidence is not None and (
            not isinstance(confidence, Decimal)
            or not confidence.is_finite()
            or not _ZERO <= confidence <= Decimal("1")
        ):
            raise error("proposal_confidence must be a finite Decimal from 0 to 1")
        try:
            prices = tuple(self.prices)
        except TypeError as caught:
            raise error("prices must be iterable") from caught
        if not prices or not all(
            isinstance(item, PaperPortfolioCyclePrice) for item in prices
        ):
            raise error("prices must contain PaperPortfolioCyclePrice values")
        symbols = tuple(item.symbol for item in prices)
        if len(set(symbols)) != len(symbols):
            raise error("price symbols must be unique")
        if symbols != self.target.symbols:
            raise error("price symbols must exactly match target symbol order")
        try:
            as_of = normalize_utc(self.as_of, "as_of")
            submitted_at = normalize_utc(self.submitted_at, "submitted_at")
            filled_at = normalize_utc(self.filled_at, "filled_at")
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        if self.target.as_of != as_of:
            raise error("target as_of must equal frame as_of")
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
        object.__setattr__(self, "metadata", _metadata(self.metadata, error))
        if confidence == _ZERO:
            object.__setattr__(self, "proposal_confidence", _ZERO)


@dataclass(frozen=True, slots=True)
class PaperPortfolioSimulationRequest:
    request_id: UUID
    frames: tuple[PaperPortfolioSimulationFrame, ...]
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidPaperPortfolioSimulationRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        try:
            frames = tuple(self.frames)
        except TypeError as caught:
            raise error("frames must be iterable") from caught
        if not frames or not all(
            isinstance(item, PaperPortfolioSimulationFrame) for item in frames
        ):
            raise error("frames must contain at least one simulation frame")
        metadata = _metadata(self.metadata, error)
        for ordinal, frame in enumerate(frames):
            if ordinal and (
                frame.as_of <= frames[ordinal - 1].as_of
                or frame.as_of < frames[ordinal - 1].filled_at
            ):
                raise error(
                    "frame as_of values must increase and follow the prior fill"
                )
            keys = [item.key for item in (*metadata, *frame.metadata)]
            if len(set(keys)) != len(keys):
                raise error("request and frame metadata keys must not overlap")
        object.__setattr__(self, "frames", frames)
        object.__setattr__(self, "metadata", metadata)


class PaperPortfolioSimulationStatus(StrEnum):
    COMPLETED = "COMPLETED"
    NO_ACTION = "NO_ACTION"


class PaperPortfolioSimulationDiagnosticCode(StrEnum):
    ALL_CYCLES_NO_ACTION = "ALL_CYCLES_NO_ACTION"


@dataclass(frozen=True, slots=True)
class PaperPortfolioSimulationDiagnostic:
    code: PaperPortfolioSimulationDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        error = InconsistentPaperPortfolioSimulationResultError
        if not isinstance(self.code, PaperPortfolioSimulationDiagnosticCode):
            raise error("diagnostic code has an invalid type")
        if not isinstance(self.message, str) or not self.message.strip():
            raise error("diagnostic message must be nonblank")


@dataclass(frozen=True, slots=True)
class PaperPortfolioSimulationEvaluation:
    frame_ordinal: int
    frame: PaperPortfolioSimulationFrame
    derived_state: PortfolioState
    cycle_request_id: UUID
    cycle_result: PaperPortfolioCycleResult
    pre_engine_state_id: UUID
    pre_ledger_state_id: UUID
    post_engine_state_id: UUID
    post_ledger_state_id: UUID

    def __post_init__(self) -> None:
        error = InconsistentPaperPortfolioSimulationResultError
        if (
            not isinstance(self.frame_ordinal, int)
            or isinstance(self.frame_ordinal, bool)
            or self.frame_ordinal < 0
        ):
            raise error("frame_ordinal must be a nonnegative integer")
        if not isinstance(self.frame, PaperPortfolioSimulationFrame):
            raise error("frame has an invalid type")
        if not isinstance(self.derived_state, PortfolioState):
            raise error("derived_state has an invalid type")
        if not isinstance(self.cycle_request_id, UUID):
            raise error("cycle_request_id must be a UUID")
        if not isinstance(self.cycle_result, PaperPortfolioCycleResult):
            raise error("cycle_result has an invalid type")
        if self.cycle_result.request.request_id != self.cycle_request_id:
            raise error("cycle request identity does not match evaluation")
        if self.cycle_result.request.inputs.state != self.derived_state:
            raise error("cycle state does not match the derived state")
        for name in (
            "pre_engine_state_id",
            "pre_ledger_state_id",
            "post_engine_state_id",
            "post_ledger_state_id",
        ):
            if not isinstance(getattr(self, name), UUID):
                raise error(f"{name} must be a UUID")
            if getattr(self, name) != getattr(self.cycle_result, name):
                raise error(f"{name} does not match the cycle result")


@dataclass(frozen=True, slots=True)
class PaperPortfolioSimulationResult:
    result_id: UUID
    request: PaperPortfolioSimulationRequest
    evaluations: tuple[PaperPortfolioSimulationEvaluation, ...]
    initial_engine_state_id: UUID
    initial_ledger_state_id: UUID
    final_engine_state_id: UUID
    final_ledger_state_id: UUID
    applied_cycle_count: int
    no_action_cycle_count: int
    status: PaperPortfolioSimulationStatus
    diagnostics: tuple[PaperPortfolioSimulationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentPaperPortfolioSimulationResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, PaperPortfolioSimulationRequest):
            raise error("request has an invalid type")
        try:
            evaluations = tuple(self.evaluations)
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("result tuple fields must be iterable") from caught
        if len(evaluations) != len(self.request.frames) or not all(
            isinstance(item, PaperPortfolioSimulationEvaluation) for item in evaluations
        ):
            raise error("evaluations must exactly cover request frames")
        if not all(
            isinstance(item, PaperPortfolioSimulationDiagnostic) for item in diagnostics
        ):
            raise error("diagnostics contain invalid values")
        _validate_result_chain(self, evaluations, diagnostics)
        expected_id = _result_id(
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
        )
        if self.result_id != expected_id:
            raise error("result_id does not match deterministic identity")
        object.__setattr__(self, "evaluations", evaluations)
        object.__setattr__(self, "diagnostics", diagnostics)


class PaperPortfolioSimulator:
    """Run ordered frames through one authoritative paper portfolio runtime."""

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
        self, request: PaperPortfolioSimulationRequest
    ) -> PaperPortfolioSimulationResult:
        if not isinstance(request, PaperPortfolioSimulationRequest):
            raise TypeError("request must be a PaperPortfolioSimulationRequest")
        initial_engine_id = engine_state_id(engine_snapshot(self.engine))
        initial_ledger_id = ledger_state_id(ledger_snapshot(self.ledger))
        evaluations: list[PaperPortfolioSimulationEvaluation] = []
        prior_result_id: UUID | None = None
        for ordinal, frame in enumerate(request.frames):
            pre_engine_id = engine_state_id(engine_snapshot(self.engine))
            pre_ledger_id = ledger_state_id(ledger_snapshot(self.ledger))
            state = _derive_state(self.ledger, frame)
            cycle_id = _cycle_id(
                request,
                frame,
                ordinal,
                pre_engine_id,
                pre_ledger_id,
                prior_result_id,
            )
            try:
                cycle_request = PaperPortfolioCycleRequest(
                    cycle_id,
                    PaperPortfolioCycleInputs(
                        state,
                        frame.target,
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
                    _cycle_metadata(request, frame, ordinal),
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
                PaperPortfolioSimulationEvaluation(
                    ordinal,
                    frame,
                    state,
                    cycle_id,
                    cycle_result,
                    pre_engine_id,
                    pre_ledger_id,
                    post_engine_id,
                    post_ledger_id,
                )
            )
            prior_result_id = cycle_result.result_id
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
                    "every simulation cycle completed without an action",
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


def _derive_state(
    ledger: PaperLedger, frame: PaperPortfolioSimulationFrame
) -> PortfolioState:
    holdings = ledger.positions
    symbols = tuple(item.symbol for item in frame.prices)
    missing = set(holdings) - set(symbols)
    if missing:
        names = ", ".join(sorted(str(item) for item in missing))
        raise PaperPortfolioSimulationStateDerivationError(
            f"frame prices and target omit held symbols: {names}"
        )
    try:
        positions = tuple(
            PortfolioPositionState(
                price.symbol,
                holdings[price.symbol].quantity if price.symbol in holdings else _ZERO,
                holdings[price.symbol].average_cost
                if price.symbol in holdings
                else _ZERO,
                price.risk_price,
            )
            for price in frame.prices
        )
        exposure = sum((item.market_value for item in positions), start=_ZERO)
        return PortfolioState(
            frame.as_of,
            positions,
            ledger.cash,
            ledger.cash + exposure,
        )
    except InvalidPortfolioStateError as caught:
        raise PaperPortfolioSimulationStateDerivationError(
            "ledger and frame prices could not produce a valid portfolio state"
        ) from caught


def _cycle_metadata(
    request: PaperPortfolioSimulationRequest,
    frame: PaperPortfolioSimulationFrame,
    ordinal: int,
) -> tuple[MetadataEntry, ...]:
    return (
        *request.metadata,
        *frame.metadata,
        MetadataEntry("simulation_id", str(request.request_id)),
        MetadataEntry("simulation_frame_ordinal", str(ordinal)),
    )


def _optional_decimal(value: Decimal | None) -> str:
    return "none" if value is None else canonical_decimal(value)


def _frame_fingerprint(frame: PaperPortfolioSimulationFrame, ordinal: int) -> str:
    target = frame.target
    assumptions = frame.rebalance_assumptions
    constraints = frame.portfolio_constraints
    limits = frame.risk_limits
    constraint_material = (
        "none"
        if constraints is None
        else ":".join(
            (
                canonical_decimal(constraints.minimum_cash_weight),
                canonical_decimal(constraints.maximum_cash_weight),
                canonical_decimal(constraints.maximum_position_weight),
                _optional_decimal(constraints.minimum_position_weight),
                _optional_decimal(constraints.maximum_one_way_rebalance_turnover),
                str(constraints.long_only),
                str(constraints.allow_leverage),
            )
        )
    )
    return "|".join(
        (
            _VERSION,
            str(ordinal),
            frame.as_of.isoformat(),
            frame.submitted_at.isoformat(),
            frame.filled_at.isoformat(),
            str(target.target_id),
            canonical_decimal(target.cash_weight),
            *(
                f"target={item.symbol}:{canonical_decimal(item.weight)}"
                for item in target.allocations
            ),
            target.source.value,
            "none" if target.source_name is None else target.source_name,
            *(f"target-meta={item.key}={item.value}" for item in target.metadata),
            *(
                f"price={item.symbol}:{canonical_decimal(item.risk_price)}:{canonical_decimal(item.fill_reference_price)}"
                for item in frame.prices
            ),
            canonical_decimal(assumptions.fixed_commission),
            str(assumptions.allow_fractional_quantities),
            canonical_decimal(assumptions.quantity_increment),
            canonical_decimal(assumptions.minimum_trade_notional),
            canonical_decimal(assumptions.minimum_trade_quantity),
            canonical_decimal(assumptions.target_weight_tolerance),
            canonical_decimal(assumptions.additional_execution_cash_buffer),
            str(assumptions.use_planned_sell_proceeds),
            constraint_material,
            str(frame.proposal_policy.allow_partial_plans),
            _optional_decimal(frame.proposal_confidence),
            canonical_decimal(limits.max_position_percent),
            canonical_decimal(limits.max_total_exposure_percent),
            _optional_decimal(limits.max_order_notional),
            _optional_decimal(limits.max_new_position_percent),
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


def _request_fingerprint(request: PaperPortfolioSimulationRequest) -> str:
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


def _cycle_id(
    request: PaperPortfolioSimulationRequest,
    frame: PaperPortfolioSimulationFrame,
    ordinal: int,
    pre_engine_id: UUID,
    pre_ledger_id: UUID,
    prior_result_id: UUID | None,
) -> UUID:
    predecessor = (
        f"initial:{pre_engine_id}:{pre_ledger_id}"
        if prior_result_id is None
        else f"prior:{prior_result_id}"
    )
    return uuid5(
        _NAMESPACE,
        "|".join(
            (
                _VERSION,
                str(request.request_id),
                str(ordinal),
                frame.as_of.isoformat(),
                _frame_fingerprint(frame, ordinal),
                predecessor,
            )
        ),
    )


def _validate_result_chain(
    result: PaperPortfolioSimulationResult,
    evaluations: tuple[PaperPortfolioSimulationEvaluation, ...],
    diagnostics: tuple[PaperPortfolioSimulationDiagnostic, ...],
) -> None:
    error = InconsistentPaperPortfolioSimulationResultError
    uuids = (
        result.initial_engine_state_id,
        result.initial_ledger_state_id,
        result.final_engine_state_id,
        result.final_ledger_state_id,
    )
    if not all(isinstance(item, UUID) for item in uuids):
        raise error("state identifiers must be UUID values")
    prior_result_id: UUID | None = None
    for ordinal, (frame, evaluation) in enumerate(
        zip(result.request.frames, evaluations, strict=True)
    ):
        if evaluation.frame_ordinal != ordinal or evaluation.frame != frame:
            raise error("evaluation order does not match request frame order")
        expected_cycle_id = _cycle_id(
            result.request,
            frame,
            ordinal,
            evaluation.pre_engine_state_id,
            evaluation.pre_ledger_state_id,
            prior_result_id,
        )
        if evaluation.cycle_request_id != expected_cycle_id:
            raise error("cycle request ID does not match deterministic derivation")
        if ordinal == 0:
            if (
                evaluation.pre_engine_state_id != result.initial_engine_state_id
                or evaluation.pre_ledger_state_id != result.initial_ledger_state_id
            ):
                raise error("first evaluation does not match initial state IDs")
        else:
            previous = evaluations[ordinal - 1]
            if (
                previous.post_engine_state_id != evaluation.pre_engine_state_id
                or previous.post_ledger_state_id != evaluation.pre_ledger_state_id
            ):
                raise error("adjacent evaluation states do not chain")
        prior_result_id = evaluation.cycle_result.result_id
    if (
        evaluations[-1].post_engine_state_id != result.final_engine_state_id
        or evaluations[-1].post_ledger_state_id != result.final_ledger_state_id
    ):
        raise error("final state IDs do not match the final evaluation")
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
        raise error("simulation status does not reconcile")
    expected_codes = (
        ()
        if applied
        else (PaperPortfolioSimulationDiagnosticCode.ALL_CYCLES_NO_ACTION,)
    )
    if tuple(item.code for item in diagnostics) != expected_codes:
        raise error("simulation diagnostics do not reconcile")


def _result_id(
    request: PaperPortfolioSimulationRequest,
    evaluations: tuple[PaperPortfolioSimulationEvaluation, ...],
    initial_engine_id: UUID,
    initial_ledger_id: UUID,
    final_engine_id: UUID,
    final_ledger_id: UUID,
    applied: int,
    no_action: int,
    status: PaperPortfolioSimulationStatus,
    codes: tuple[PaperPortfolioSimulationDiagnosticCode, ...],
) -> UUID:
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
    request: PaperPortfolioSimulationRequest,
    evaluations: tuple[PaperPortfolioSimulationEvaluation, ...],
    initial_engine_id: UUID,
    initial_ledger_id: UUID,
    final_engine_id: UUID,
    final_ledger_id: UUID,
    applied: int,
    no_action: int,
    status: PaperPortfolioSimulationStatus,
    diagnostics: tuple[PaperPortfolioSimulationDiagnostic, ...],
) -> PaperPortfolioSimulationResult:
    codes = tuple(item.code for item in diagnostics)
    return PaperPortfolioSimulationResult(
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
