"""Atomic construction of portfolio orders from collective risk results."""

from copy import Error as CopyError
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import Order, OrderStatus, OrderType, TimeInForce
from trading_bot.execution.engine import OrderEngine
from trading_bot.execution.exceptions import (
    InconsistentPortfolioOrderBatchResultError,
    InconsistentPortfolioOrderSourceError,
    InvalidPortfolioOrderBatchRequestError,
    OrderEngineError,
    PortfolioOrderCreationError,
    PortfolioOrderEngineCopyError,
)
from trading_bot.execution.models import (
    ExecutionInstruction,
    OrderEvent,
    OrderEventType,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.risk import (
    PortfolioRiskBatchResult,
    PortfolioRiskBatchStatus,
    RiskOutcome,
)

_VERSION = "portfolio-order-v1"
_NAMESPACE = UUID("70bdba5c-2f0b-51fd-8c39-e7ceef4af4aa")


@dataclass(frozen=True, slots=True)
class PortfolioOrderBatchRequest:
    request_id: UUID
    risk_batch: PortfolioRiskBatchResult
    instruction: ExecutionInstruction
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidPortfolioOrderBatchRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if not isinstance(self.risk_batch, PortfolioRiskBatchResult):
            raise error("risk_batch must be a PortfolioRiskBatchResult")
        if not isinstance(self.instruction, ExecutionInstruction):
            raise error("instruction must be an ExecutionInstruction")
        if (
            self.instruction.order_type is not OrderType.MARKET
            or self.instruction.time_in_force is not TimeInForce.DAY
            or self.instruction.limit_price is not None
        ):
            raise error(
                "only MARKET DAY instructions without limit_price are supported"
            )
        if self.instruction.created_at != self.risk_batch.request.base_context.as_of:
            raise error("instruction timestamp must equal the risk batch timestamp")
        try:
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("metadata must be iterable") from caught
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        object.__setattr__(self, "metadata", metadata)


class PortfolioOrderBatchStatus(StrEnum):
    CREATED = "CREATED"
    NO_ACTION = "NO_ACTION"


class PortfolioOrderDiagnosticCode(StrEnum):
    REJECTED_EVALUATIONS_SKIPPED = "REJECTED_EVALUATIONS_SKIPPED"
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class PortfolioOrderDiagnostic:
    code: PortfolioOrderDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, PortfolioOrderDiagnosticCode):
            raise InconsistentPortfolioOrderBatchResultError(
                "diagnostic code must be PortfolioOrderDiagnosticCode"
            )
        if not isinstance(self.message, str) or not self.message.strip():
            raise InconsistentPortfolioOrderBatchResultError(
                "diagnostic message must be nonblank"
            )


@dataclass(frozen=True, slots=True)
class PortfolioOrderBatchResult:
    result_id: UUID
    request: PortfolioOrderBatchRequest
    status: PortfolioOrderBatchStatus
    source_evaluation_ordinals: tuple[int, ...]
    orders: tuple[Order, ...]
    created_events: tuple[OrderEvent, ...]
    diagnostics: tuple[PortfolioOrderDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentPortfolioOrderBatchResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, PortfolioOrderBatchRequest):
            raise error("request must be PortfolioOrderBatchRequest")
        if not isinstance(self.status, PortfolioOrderBatchStatus):
            raise error("status must be PortfolioOrderBatchStatus")
        try:
            ordinals = tuple(self.source_evaluation_ordinals)
            orders = tuple(self.orders)
            events = tuple(self.created_events)
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("result collections must be iterable") from caught
        if not all(
            isinstance(item, int) and not isinstance(item, bool) for item in ordinals
        ):
            raise error("source ordinals must be integers")
        if ordinals != tuple(sorted(set(ordinals))):
            raise error("source ordinals must be unique and increasing")
        if not all(isinstance(item, Order) for item in orders):
            raise error("orders must contain Order values")
        if not all(isinstance(item, OrderEvent) for item in events):
            raise error("created_events must contain OrderEvent values")
        if not all(isinstance(item, PortfolioOrderDiagnostic) for item in diagnostics):
            raise error("diagnostics contain invalid values")
        if not (len(ordinals) == len(orders) == len(events)):
            raise error("source, order, and event counts must match")
        if self.status is PortfolioOrderBatchStatus.CREATED and not orders:
            raise error("CREATED results require at least one order")
        if self.status is PortfolioOrderBatchStatus.NO_ACTION and (
            ordinals or orders or events
        ):
            raise error("NO_ACTION results prohibit created output")
        for source_ordinal, order, event in zip(ordinals, orders, events, strict=True):
            if not 0 <= source_ordinal < len(self.request.risk_batch.evaluations):
                raise error("source ordinal is outside the risk batch")
            evaluation = self.request.risk_batch.evaluations[source_ordinal]
            _validate_created_output(
                self.request, evaluation, source_ordinal, order, event
            )
        expected_codes = _diagnostic_codes(self.request.risk_batch)
        if tuple(item.code for item in diagnostics) != expected_codes:
            raise error("diagnostic codes do not match source batch")
        object.__setattr__(self, "source_evaluation_ordinals", ordinals)
        object.__setattr__(self, "orders", orders)
        object.__setattr__(self, "created_events", events)
        object.__setattr__(self, "diagnostics", diagnostics)


class PortfolioOrderOrchestrator:
    """Own and atomically replace an authoritative order engine."""

    def __init__(self, engine: OrderEngine | None = None) -> None:
        if engine is not None and not isinstance(engine, OrderEngine):
            raise TypeError("engine must be an OrderEngine or None")
        self._engine = engine or OrderEngine()

    @property
    def engine(self) -> OrderEngine:
        return self._engine

    def create(self, request: PortfolioOrderBatchRequest) -> PortfolioOrderBatchResult:
        if not isinstance(request, PortfolioOrderBatchRequest):
            raise TypeError("request must be PortfolioOrderBatchRequest")
        accepted = _validate_source(request)
        existing_orders = tuple(self._engine.orders.values())
        existing_events = self._engine.get_events()
        pre_state_id = _engine_state_id(existing_orders, existing_events)
        status = (
            PortfolioOrderBatchStatus.CREATED
            if accepted
            else PortfolioOrderBatchStatus.NO_ACTION
        )
        diagnostics = _diagnostics(request.risk_batch)
        if not accepted:
            return _build_result(request, pre_state_id, status, (), (), (), diagnostics)
        identities = tuple(
            (
                source_ordinal,
                _derived_id("order", request, source_ordinal),
                _derived_id("created-event", request, source_ordinal),
            )
            for source_ordinal in accepted
        )
        order_ids = tuple(item[1] for item in identities)
        event_ids = tuple(item[2] for item in identities)
        if len(set(order_ids)) != len(order_ids) or len(set(event_ids)) != len(
            event_ids
        ):
            raise InconsistentPortfolioOrderSourceError(
                "batch-derived order and event IDs must be unique"
            )
        existing_order_ids = {item.request.order_id for item in existing_orders}
        existing_event_ids = {item.event_id for item in existing_events}
        if existing_order_ids.intersection(order_ids):
            raise InconsistentPortfolioOrderSourceError(
                "derived order ID collides with the active engine"
            )
        if existing_event_ids.intersection(event_ids):
            raise InconsistentPortfolioOrderSourceError(
                "derived event ID collides with the active engine"
            )
        try:
            shadow = deepcopy(self._engine)
        except (CopyError, TypeError, ValueError, RuntimeError) as caught:
            raise PortfolioOrderEngineCopyError("order engine copy failed") from caught
        created = []
        try:
            for source_ordinal, order_id, event_id in identities:
                decision = request.risk_batch.evaluations[source_ordinal].decision
                created.append(
                    shadow.create_order(
                        decision,
                        request.instruction,
                        order_id=order_id,
                        event_id=event_id,
                    )
                )
        except (OrderEngineError, TypeError, ValueError) as caught:
            raise PortfolioOrderCreationError(
                "shadow-engine order construction failed"
            ) from caught
        all_orders = tuple(shadow.orders.values())
        all_events = shadow.get_events()
        if all_orders[: len(existing_orders)] != existing_orders:
            raise InconsistentPortfolioOrderBatchResultError(
                "preexisting orders were not preserved as an exact prefix"
            )
        if all_events[: len(existing_events)] != existing_events:
            raise InconsistentPortfolioOrderBatchResultError(
                "preexisting events were not preserved as an exact prefix"
            )
        new_orders = all_orders[len(existing_orders) :]
        new_events = all_events[len(existing_events) :]
        if new_orders != tuple(created):
            raise InconsistentPortfolioOrderBatchResultError(
                "created orders do not match shadow-engine order suffix"
            )
        result = _build_result(
            request,
            pre_state_id,
            status,
            accepted,
            new_orders,
            new_events,
            diagnostics,
        )
        self._engine = shadow
        return result


def _validate_source(request: PortfolioOrderBatchRequest) -> tuple[int, ...]:
    batch = request.risk_batch
    evaluations = batch.evaluations
    if len(evaluations) != len(batch.request.proposals):
        raise InconsistentPortfolioOrderSourceError(
            "one risk evaluation is required per source proposal"
        )
    if tuple(item.ordinal for item in evaluations) != tuple(range(len(evaluations))):
        raise InconsistentPortfolioOrderSourceError(
            "risk evaluation ordinals must be sequential"
        )
    proposals = tuple(item.decision.proposal for item in evaluations)
    if proposals != batch.request.proposals:
        raise InconsistentPortfolioOrderSourceError(
            "risk evaluations must preserve source proposal order"
        )
    if len({item.proposal_id for item in proposals}) != len(proposals):
        raise InconsistentPortfolioOrderSourceError(
            "source proposal IDs must be unique"
        )
    accepted = []
    for ordinal, evaluation in enumerate(evaluations):
        decision = evaluation.decision
        proposal = decision.proposal
        if (
            decision.evaluated_at != request.instruction.created_at
            or proposal.created_at != request.instruction.created_at
        ):
            raise InconsistentPortfolioOrderSourceError(
                "proposal, decision, and instruction timestamps must match"
            )
        quantity = decision.approved_quantity
        valid = (
            decision.outcome is RiskOutcome.APPROVED
            and quantity == proposal.desired_quantity
            or decision.outcome is RiskOutcome.RESIZED
            and quantity > 0
            and quantity < proposal.desired_quantity
            or decision.outcome is RiskOutcome.REJECTED
            and quantity == 0
        )
        if not valid:
            raise InconsistentPortfolioOrderSourceError(
                "risk outcome and approved quantity are inconsistent"
            )
        if decision.outcome in {RiskOutcome.APPROVED, RiskOutcome.RESIZED}:
            accepted.append(ordinal)
    expected_status = _expected_risk_status(evaluations)
    if batch.status is not expected_status:
        raise InconsistentPortfolioOrderSourceError(
            "risk batch status does not match evaluation outcomes"
        )
    if batch.status is PortfolioRiskBatchStatus.PARTIALLY_APPROVED and not accepted:
        raise InconsistentPortfolioOrderSourceError(
            "partially approved risk batch requires an accepted evaluation"
        )
    return tuple(accepted)


def _expected_risk_status(evaluations):  # type: ignore[no-untyped-def]
    if not evaluations:
        return PortfolioRiskBatchStatus.NO_ACTION
    outcomes = tuple(item.decision.outcome for item in evaluations)
    if all(item is RiskOutcome.APPROVED for item in outcomes):
        return PortfolioRiskBatchStatus.ALL_APPROVED
    if all(item is RiskOutcome.REJECTED for item in outcomes):
        return PortfolioRiskBatchStatus.ALL_REJECTED
    return PortfolioRiskBatchStatus.PARTIALLY_APPROVED


def _diagnostic_codes(
    batch: PortfolioRiskBatchResult,
) -> tuple[PortfolioOrderDiagnosticCode, ...]:
    if batch.status is PortfolioRiskBatchStatus.NO_ACTION:
        return (PortfolioOrderDiagnosticCode.NO_ACTION,)
    if any(item.decision.outcome is RiskOutcome.REJECTED for item in batch.evaluations):
        return (PortfolioOrderDiagnosticCode.REJECTED_EVALUATIONS_SKIPPED,)
    return ()


def _diagnostics(
    batch: PortfolioRiskBatchResult,
) -> tuple[PortfolioOrderDiagnostic, ...]:
    return tuple(
        PortfolioOrderDiagnostic(
            code,
            "risk batch contained no proposals"
            if code is PortfolioOrderDiagnosticCode.NO_ACTION
            else "rejected risk evaluations were skipped",
        )
        for code in _diagnostic_codes(batch)
    )


def _canonical_decimal(value):  # type: ignore[no-untyped-def]
    normalized = 0 if value == 0 else value.normalize()
    return format(normalized, "f")


def _identity_material(request: PortfolioOrderBatchRequest, source_ordinal: int) -> str:
    evaluation = request.risk_batch.evaluations[source_ordinal]
    decision = evaluation.decision
    proposal = decision.proposal
    instruction = request.instruction
    return "|".join(
        (
            _VERSION,
            str(request.request_id),
            str(request.risk_batch.result_id),
            str(source_ordinal),
            str(proposal.proposal_id),
            decision.outcome.value,
            _canonical_decimal(decision.approved_quantity),
            str(proposal.symbol),
            proposal.side.value,
            instruction.order_type.value,
            instruction.time_in_force.value,
            instruction.created_at.isoformat(),
            "none",
        )
    )


def _derived_id(
    kind: str, request: PortfolioOrderBatchRequest, source_ordinal: int
) -> UUID:
    return uuid5(_NAMESPACE, f"{kind}|{_identity_material(request, source_ordinal)}")


def _engine_state_id(orders: tuple[Order, ...], events: tuple[OrderEvent, ...]) -> UUID:
    identity = "|".join(
        (
            "engine-state",
            ",".join(str(item.request.order_id) for item in orders),
            ",".join(str(item.event_id) for item in events),
        )
    )
    return uuid5(_NAMESPACE, identity)


def _request_fingerprint(request: PortfolioOrderBatchRequest) -> str:
    return "|".join(
        (
            _VERSION,
            str(request.request_id),
            str(request.risk_batch.result_id),
            request.instruction.order_type.value,
            request.instruction.time_in_force.value,
            request.instruction.created_at.isoformat(),
            "none",
            *(f"{item.key}={item.value}" for item in request.metadata),
        )
    )


def _result_id(
    request: PortfolioOrderBatchRequest,
    pre_state_id: UUID,
    status: PortfolioOrderBatchStatus,
    ordinals: tuple[int, ...],
    orders: tuple[Order, ...],
    events: tuple[OrderEvent, ...],
    codes: tuple[PortfolioOrderDiagnosticCode, ...],
) -> UUID:
    identity = "|".join(
        (
            _request_fingerprint(request),
            str(pre_state_id),
            status.value,
            ",".join(str(item) for item in ordinals),
            ",".join(str(item.request.order_id) for item in orders),
            ",".join(str(item.event_id) for item in events),
            ",".join(item.value for item in codes),
        )
    )
    return uuid5(_NAMESPACE, identity)


def _validate_created_output(
    request: PortfolioOrderBatchRequest,
    evaluation,
    source_ordinal: int,
    order: Order,
    event: OrderEvent,
) -> None:  # type: ignore[no-untyped-def]
    decision = evaluation.decision
    proposal = decision.proposal
    order_request = order.request
    if (
        order_request.order_id != _derived_id("order", request, source_ordinal)
        or order.status is not OrderStatus.PENDING
        or order_request.symbol != proposal.symbol
        or order_request.side is not proposal.side
        or order_request.quantity != decision.approved_quantity
        or order_request.order_type is not request.instruction.order_type
        or order_request.time_in_force is not request.instruction.time_in_force
        or order_request.submitted_at != request.instruction.created_at
        or order_request.limit_price is not None
    ):
        raise InconsistentPortfolioOrderBatchResultError(
            "created order does not match its accepted risk evaluation"
        )
    if (
        event.event_id != _derived_id("created-event", request, source_ordinal)
        or event.order_id != order_request.order_id
        or event.event_type is not OrderEventType.CREATED
        or event.occurred_at != request.instruction.created_at
    ):
        raise InconsistentPortfolioOrderBatchResultError(
            "created event does not match its order"
        )


def _build_result(
    request: PortfolioOrderBatchRequest,
    pre_state_id: UUID,
    status: PortfolioOrderBatchStatus,
    ordinals: tuple[int, ...],
    orders: tuple[Order, ...],
    events: tuple[OrderEvent, ...],
    diagnostics: tuple[PortfolioOrderDiagnostic, ...],
) -> PortfolioOrderBatchResult:
    codes = tuple(item.code for item in diagnostics)
    return PortfolioOrderBatchResult(
        _result_id(request, pre_state_id, status, ordinals, orders, events, codes),
        request,
        status,
        ordinals,
        orders,
        events,
        diagnostics,
    )
