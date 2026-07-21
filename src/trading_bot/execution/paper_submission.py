"""Atomic local submission of portfolio-created paper orders."""

from copy import Error as CopyError
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import Order, OrderStatus
from trading_bot.domain._validation import normalize_utc
from trading_bot.execution.engine import OrderEngine
from trading_bot.execution.exceptions import (
    InconsistentPaperSubmissionBatchResultError,
    InconsistentPaperSubmissionSourceError,
    InvalidPaperSubmissionBatchRequestError,
    OrderEngineError,
    PaperOrderSubmissionError,
    PaperSubmissionEngineCopyError,
    PaperSubmissionEventCollisionError,
)
from trading_bot.execution.models import OrderEvent, OrderEventType
from trading_bot.execution.portfolio_orders import (
    PortfolioOrderBatchResult,
    PortfolioOrderBatchStatus,
)
from trading_bot.portfolio import MetadataEntry

_VERSION = "paper-submission-v1"
_NAMESPACE = UUID("fa5e3c83-80be-5bb2-a41c-c6f659534bbb")


@dataclass(frozen=True, slots=True)
class PaperSubmissionBatchRequest:
    request_id: UUID
    order_batch: PortfolioOrderBatchResult
    submitted_at: datetime
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidPaperSubmissionBatchRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if not isinstance(self.order_batch, PortfolioOrderBatchResult):
            raise error("order_batch must be a PortfolioOrderBatchResult")
        try:
            submitted_at = normalize_utc(self.submitted_at, "submitted_at")
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        try:
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("metadata must be iterable") from caught
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        object.__setattr__(self, "submitted_at", submitted_at)
        object.__setattr__(self, "metadata", metadata)


class PaperSubmissionBatchStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    NO_ACTION = "NO_ACTION"


class PaperSubmissionDiagnosticCode(StrEnum):
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class PaperSubmissionDiagnostic:
    code: PaperSubmissionDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        error = InconsistentPaperSubmissionBatchResultError
        if not isinstance(self.code, PaperSubmissionDiagnosticCode):
            raise error("diagnostic code must be PaperSubmissionDiagnosticCode")
        if not isinstance(self.message, str) or not self.message.strip():
            raise error("diagnostic message must be nonblank")


@dataclass(frozen=True, slots=True)
class PaperSubmissionBatchResult:
    result_id: UUID
    request: PaperSubmissionBatchRequest
    status: PaperSubmissionBatchStatus
    orders: tuple[Order, ...]
    submitted_events: tuple[OrderEvent, ...]
    diagnostics: tuple[PaperSubmissionDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentPaperSubmissionBatchResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, PaperSubmissionBatchRequest):
            raise error("request must be PaperSubmissionBatchRequest")
        if not isinstance(self.status, PaperSubmissionBatchStatus):
            raise error("status must be PaperSubmissionBatchStatus")
        try:
            orders = tuple(self.orders)
            events = tuple(self.submitted_events)
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("result collections must be iterable") from caught
        if not all(isinstance(item, Order) for item in orders):
            raise error("orders must contain Order values")
        if not all(isinstance(item, OrderEvent) for item in events):
            raise error("submitted_events must contain OrderEvent values")
        if not all(isinstance(item, PaperSubmissionDiagnostic) for item in diagnostics):
            raise error("diagnostics contain invalid values")
        if len(orders) != len(events):
            raise error("order and submitted-event counts must match")
        if self.status is PaperSubmissionBatchStatus.SUBMITTED:
            if not orders or diagnostics:
                raise error("SUBMITTED requires output and prohibits diagnostics")
        elif (
            orders
            or events
            or tuple(item.code for item in diagnostics)
            != (PaperSubmissionDiagnosticCode.NO_ACTION,)
        ):
            raise error("NO_ACTION requires exactly one diagnostic and no output")
        source_orders = self.request.order_batch.orders
        if len(orders) != len(source_orders):
            raise error("submitted output must match source order count")
        for ordinal, (source, order, event) in enumerate(
            zip(source_orders, orders, events, strict=True)
        ):
            _validate_submitted_output(self.request, ordinal, source, order, event)
        object.__setattr__(self, "orders", orders)
        object.__setattr__(self, "submitted_events", events)
        object.__setattr__(self, "diagnostics", diagnostics)


class PaperOrderSubmitter:
    """Own and atomically replace an authoritative submitted-order engine."""

    def __init__(self, engine: OrderEngine | None = None) -> None:
        if engine is not None and not isinstance(engine, OrderEngine):
            raise TypeError("engine must be an OrderEngine or None")
        self._engine = engine or OrderEngine()

    @property
    def engine(self) -> OrderEngine:
        return self._engine

    def submit(
        self, request: PaperSubmissionBatchRequest
    ) -> PaperSubmissionBatchResult:
        if not isinstance(request, PaperSubmissionBatchRequest):
            raise TypeError("request must be PaperSubmissionBatchRequest")
        source_orders = _validate_source_shape(request)
        existing_orders = tuple(self._engine.orders.items())
        existing_events = self._engine.get_events()
        existing_fills = tuple(
            (order_id, self._engine.get_fills(order_id))
            for order_id, _ in existing_orders
        )
        pre_state_id = _engine_state_id(
            existing_orders, existing_events, existing_fills
        )
        if not source_orders:
            diagnostic = PaperSubmissionDiagnostic(
                PaperSubmissionDiagnosticCode.NO_ACTION,
                "source portfolio order batch contained no orders",
            )
            return _build_result(
                request,
                pre_state_id,
                PaperSubmissionBatchStatus.NO_ACTION,
                (),
                (),
                (diagnostic,),
            )
        _validate_active_source(
            request, source_orders, existing_orders, existing_events, existing_fills
        )
        event_ids = tuple(
            _submitted_event_id(request, ordinal, order)
            for ordinal, order in enumerate(source_orders)
        )
        if len(set(event_ids)) != len(event_ids):
            raise PaperSubmissionEventCollisionError(
                "batch-derived submitted-event IDs must be unique"
            )
        current_event_ids = {item.event_id for item in existing_events}
        source_event_ids = {
            item.event_id for item in request.order_batch.created_events
        }
        if current_event_ids.intersection(event_ids) or source_event_ids.intersection(
            event_ids
        ):
            raise PaperSubmissionEventCollisionError(
                "derived submitted-event ID collides with existing event identity"
            )
        try:
            shadow = deepcopy(self._engine)
        except (CopyError, TypeError, ValueError, RuntimeError) as caught:
            raise PaperSubmissionEngineCopyError("order engine copy failed") from caught
        updated = []
        try:
            for source, event_id in zip(source_orders, event_ids, strict=True):
                updated.append(
                    shadow.submit_order(
                        source.request.order_id,
                        request.submitted_at,
                        event_id=event_id,
                    )
                )
        except (OrderEngineError, TypeError, ValueError) as caught:
            raise PaperOrderSubmissionError(
                "shadow-engine paper submission failed"
            ) from caught
        all_orders = tuple(shadow.orders.items())
        all_events = shadow.get_events()
        all_fills = tuple(
            (order_id, shadow.get_fills(order_id)) for order_id, _ in all_orders
        )
        _reconcile_shadow(
            request,
            source_orders,
            tuple(updated),
            event_ids,
            existing_orders,
            existing_events,
            existing_fills,
            all_orders,
            all_events,
            all_fills,
        )
        new_events = all_events[len(existing_events) :]
        result = _build_result(
            request,
            pre_state_id,
            PaperSubmissionBatchStatus.SUBMITTED,
            tuple(updated),
            new_events,
            (),
        )
        self._engine = shadow
        return result


def _validate_source_shape(
    request: PaperSubmissionBatchRequest,
) -> tuple[Order, ...]:
    batch = request.order_batch
    orders = batch.orders
    events = batch.created_events
    if batch.status is PortfolioOrderBatchStatus.NO_ACTION:
        if orders or events or batch.source_evaluation_ordinals:
            raise InconsistentPaperSubmissionSourceError(
                "NO_ACTION source must not contain created output"
            )
        return ()
    if batch.status is not PortfolioOrderBatchStatus.CREATED or not orders:
        raise InconsistentPaperSubmissionSourceError(
            "CREATED source must contain at least one order"
        )
    if not (len(orders) == len(events) == len(batch.source_evaluation_ordinals)):
        raise InconsistentPaperSubmissionSourceError(
            "source orders, events, and ordinals must align"
        )
    order_ids = tuple(item.request.order_id for item in orders)
    event_ids = tuple(item.event_id for item in events)
    if len(set(order_ids)) != len(order_ids):
        raise InconsistentPaperSubmissionSourceError("source order IDs must be unique")
    if len(set(event_ids)) != len(event_ids):
        raise InconsistentPaperSubmissionSourceError("source event IDs must be unique")
    for order, event in zip(orders, events, strict=True):
        if order.status is not OrderStatus.PENDING:
            raise InconsistentPaperSubmissionSourceError(
                "source orders must be PENDING snapshots"
            )
        if (
            event.event_type is not OrderEventType.CREATED
            or event.order_id != order.request.order_id
        ):
            raise InconsistentPaperSubmissionSourceError(
                "source CREATED events must align with source orders"
            )
        if order.filled_quantity != 0 or order.average_fill_price is not None:
            raise InconsistentPaperSubmissionSourceError(
                "source pending orders must not contain fill state"
            )
        if request.submitted_at < order.request.submitted_at:
            raise InconsistentPaperSubmissionSourceError(
                "submission timestamp precedes order request creation"
            )
        if request.submitted_at < event.occurred_at:
            raise InconsistentPaperSubmissionSourceError(
                "submission timestamp precedes source CREATED event"
            )
    return orders


def _validate_active_source(
    request: PaperSubmissionBatchRequest,
    source_orders: tuple[Order, ...],
    existing_orders: tuple[tuple[UUID, Order], ...],
    existing_events: tuple[OrderEvent, ...],
    existing_fills: tuple[tuple[UUID, tuple], ...],
) -> None:
    order_map = dict(existing_orders)
    fill_map = dict(existing_fills)
    for source, created_event in zip(
        source_orders, request.order_batch.created_events, strict=True
    ):
        order_id = source.request.order_id
        active = order_map.get(order_id)
        if active is None:
            raise InconsistentPaperSubmissionSourceError(
                f"source order {order_id} is not managed by the active engine"
            )
        if active != source or active.status is not OrderStatus.PENDING:
            raise InconsistentPaperSubmissionSourceError(
                "active order does not equal its source PENDING snapshot"
            )
        if created_event not in existing_events:
            raise InconsistentPaperSubmissionSourceError(
                "exact source CREATED event is absent from active engine"
            )
        order_events = tuple(
            event for event in existing_events if event.order_id == order_id
        )
        if any(event.event_type is OrderEventType.SUBMITTED for event in order_events):
            raise InconsistentPaperSubmissionSourceError(
                "source order already has a SUBMITTED event"
            )
        if not order_events or request.submitted_at < order_events[-1].occurred_at:
            raise InconsistentPaperSubmissionSourceError(
                "submission timestamp precedes latest active order event"
            )
        if fill_map[order_id]:
            raise InconsistentPaperSubmissionSourceError(
                "source pending order must have empty fill history"
            )


def _submitted_event_id(
    request: PaperSubmissionBatchRequest, ordinal: int, order: Order
) -> UUID:
    created_event = request.order_batch.created_events[ordinal]
    material = "|".join(
        (
            _VERSION,
            str(request.request_id),
            str(request.order_batch.result_id),
            str(ordinal),
            str(order.request.order_id),
            str(created_event.event_id),
            request.submitted_at.isoformat(),
            OrderEventType.SUBMITTED.value,
        )
    )
    return uuid5(_NAMESPACE, f"submitted-event|{material}")


def _engine_state_id(existing_orders, existing_events, existing_fills) -> UUID:  # type: ignore[no-untyped-def]
    material = "|".join(
        (
            "paper-submission-engine-state-v1",
            ",".join(
                f"{order_id}:{order.status.value}"
                for order_id, order in existing_orders
            ),
            ",".join(str(event.event_id) for event in existing_events),
            ";".join(
                f"{order_id}:{','.join(str(fill.fill_id) for fill in fills)}"
                for order_id, fills in existing_fills
            ),
        )
    )
    return uuid5(_NAMESPACE, material)


def _request_fingerprint(request: PaperSubmissionBatchRequest) -> str:
    return "|".join(
        (
            _VERSION,
            str(request.request_id),
            str(request.order_batch.result_id),
            request.submitted_at.isoformat(),
            *(f"{item.key}={item.value}" for item in request.metadata),
        )
    )


def _result_id(
    request: PaperSubmissionBatchRequest,
    pre_state_id: UUID,
    status: PaperSubmissionBatchStatus,
    orders: tuple[Order, ...],
    events: tuple[OrderEvent, ...],
    diagnostics: tuple[PaperSubmissionDiagnostic, ...],
) -> UUID:
    material = "|".join(
        (
            _request_fingerprint(request),
            str(pre_state_id),
            status.value,
            ",".join(str(item.request.order_id) for item in orders),
            ",".join(str(item.event_id) for item in events),
            ",".join(item.code.value for item in diagnostics),
        )
    )
    return uuid5(_NAMESPACE, material)


def _validate_submitted_output(
    request: PaperSubmissionBatchRequest,
    ordinal: int,
    source: Order,
    order: Order,
    event: OrderEvent,
) -> None:
    error = InconsistentPaperSubmissionBatchResultError
    if (
        order.request != source.request
        or order.status is not OrderStatus.SUBMITTED
        or order.filled_quantity != source.filled_quantity
        or order.average_fill_price != source.average_fill_price
        or order.rejection_reason is not None
    ):
        raise error("submitted order differs from its valid lifecycle transition")
    if (
        event.event_id != _submitted_event_id(request, ordinal, source)
        or event.order_id != source.request.order_id
        or event.event_type is not OrderEventType.SUBMITTED
        or event.occurred_at != request.submitted_at
        or event.fill_id is not None
        or event.reason is not None
    ):
        raise error("submitted event does not match its source order")


def _reconcile_shadow(
    request,
    source_orders,
    updated,
    event_ids,
    existing_orders,
    existing_events,
    existing_fills,
    all_orders,
    all_events,
    all_fills,
) -> None:  # type: ignore[no-untyped-def]
    error = InconsistentPaperSubmissionBatchResultError
    if tuple(item[0] for item in all_orders) != tuple(
        item[0] for item in existing_orders
    ):
        raise error("submission added, removed, or reordered managed orders")
    source_ids = {item.request.order_id for item in source_orders}
    updated_map = {item.request.order_id: item for item in updated}
    for (order_id, before), (_, after) in zip(existing_orders, all_orders, strict=True):
        if order_id in source_ids:
            if after != updated_map[order_id]:
                raise error("source order does not match submitted shadow snapshot")
        elif after != before:
            raise error("unrelated order changed during paper submission")
    if all_events[: len(existing_events)] != existing_events:
        raise error("existing global events were not preserved as an exact prefix")
    new_events = all_events[len(existing_events) :]
    if len(new_events) != len(source_orders):
        raise error("submission did not append exactly one event per source order")
    if tuple(item.event_id for item in new_events) != event_ids:
        raise error("submitted-event suffix does not match deterministic order")
    if all_fills != existing_fills:
        raise error("fill histories changed during paper submission")
    for ordinal, (source, order, event) in enumerate(
        zip(source_orders, updated, new_events, strict=True)
    ):
        _validate_submitted_output(request, ordinal, source, order, event)


def _build_result(
    request: PaperSubmissionBatchRequest,
    pre_state_id: UUID,
    status: PaperSubmissionBatchStatus,
    orders: tuple[Order, ...],
    events: tuple[OrderEvent, ...],
    diagnostics: tuple[PaperSubmissionDiagnostic, ...],
) -> PaperSubmissionBatchResult:
    return PaperSubmissionBatchResult(
        _result_id(request, pre_state_id, status, orders, events, diagnostics),
        request,
        status,
        orders,
        events,
        diagnostics,
    )
