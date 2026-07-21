"""Atomic application of generated paper fills to orders and accounting."""

from copy import Error as CopyError
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import Order, OrderFill, OrderSide, OrderStatus, Position
from trading_bot.execution.engine import OrderEngine
from trading_bot.execution.exceptions import (
    InconsistentPaperFillApplicationResultError,
    InconsistentPaperFillApplicationSourceError,
    InvalidPaperFillApplicationBatchRequestError,
    OrderEngineError,
    PaperFillApplicationEngineCopyError,
    PaperFillApplicationEngineStateError,
    PaperFillApplicationEventCollisionError,
    PaperFillApplicationLedgerCopyError,
    PaperFillApplicationLedgerStateError,
    PaperFillEngineApplyError,
    PaperFillLedgerApplyError,
)
from trading_bot.execution.models import OrderEvent, OrderEventType
from trading_bot.execution.paper_fills import PaperFillBatchResult, PaperFillBatchStatus
from trading_bot.execution.state_fingerprints import (
    canonical_decimal as _canonical_decimal,
)
from trading_bot.execution.state_fingerprints import (
    engine_snapshot as _engine_snapshot,
)
from trading_bot.execution.state_fingerprints import (
    engine_state_id as _engine_state_id,
)
from trading_bot.execution.state_fingerprints import (
    ledger_snapshot as _ledger_snapshot,
)
from trading_bot.execution.state_fingerprints import (
    ledger_state_id as _ledger_state_id,
)
from trading_bot.ledger import LedgerError, PaperLedger
from trading_bot.portfolio import MetadataEntry

_ZERO = Decimal("0")
_VERSION = "paper-fill-application-v1"
_NAMESPACE = UUID("07373b22-6336-568d-b4ba-b684544997a2")


@dataclass(frozen=True, slots=True)
class PaperFillApplicationBatchRequest:
    request_id: UUID
    fill_batch: PaperFillBatchResult
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidPaperFillApplicationBatchRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if not isinstance(self.fill_batch, PaperFillBatchResult):
            raise error("fill_batch must be a PaperFillBatchResult")
        try:
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("metadata must be iterable") from caught
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        object.__setattr__(self, "metadata", metadata)


class PaperFillApplicationBatchStatus(StrEnum):
    APPLIED = "APPLIED"
    NO_ACTION = "NO_ACTION"


class PaperFillApplicationDiagnosticCode(StrEnum):
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class PaperFillApplicationDiagnostic:
    code: PaperFillApplicationDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        error = InconsistentPaperFillApplicationResultError
        if not isinstance(self.code, PaperFillApplicationDiagnosticCode):
            raise error("diagnostic code must be PaperFillApplicationDiagnosticCode")
        if not isinstance(self.message, str) or not self.message.strip():
            raise error("diagnostic message must be nonblank")


@dataclass(frozen=True, slots=True)
class PaperFillApplicationEvaluation:
    source_fill_ordinal: int
    fill: OrderFill
    updated_order: Order
    fill_event: OrderEvent
    ledger_cash_after: Decimal
    ledger_position_after: Position | None
    ledger_realized_profit_loss_after: Decimal

    def __post_init__(self) -> None:
        error = InconsistentPaperFillApplicationResultError
        if (
            not isinstance(self.source_fill_ordinal, int)
            or isinstance(self.source_fill_ordinal, bool)
            or self.source_fill_ordinal < 0
        ):
            raise error("source_fill_ordinal must be a nonnegative integer")
        if not isinstance(self.fill, OrderFill):
            raise error("fill must be an OrderFill")
        if not isinstance(self.updated_order, Order):
            raise error("updated_order must be an Order")
        if not isinstance(self.fill_event, OrderEvent):
            raise error("fill_event must be an OrderEvent")
        for name in ("ledger_cash_after", "ledger_realized_profit_loss_after"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise error(f"{name} must be a finite Decimal")
        if self.ledger_cash_after < _ZERO:
            raise error("ledger_cash_after must be nonnegative")
        if self.ledger_position_after is not None and not isinstance(
            self.ledger_position_after, Position
        ):
            raise error("ledger_position_after must be a Position or None")
        if (
            self.ledger_position_after is not None
            and self.ledger_position_after.symbol != self.fill.symbol
        ):
            raise error("ledger position symbol must match the fill")


@dataclass(frozen=True, slots=True)
class PaperFillApplicationBatchResult:
    result_id: UUID
    request: PaperFillApplicationBatchRequest
    status: PaperFillApplicationBatchStatus
    evaluations: tuple[PaperFillApplicationEvaluation, ...]
    pre_engine_state_id: UUID
    pre_ledger_state_id: UUID
    post_engine_state_id: UUID
    post_ledger_state_id: UUID
    diagnostics: tuple[PaperFillApplicationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentPaperFillApplicationResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, PaperFillApplicationBatchRequest):
            raise error("request must be PaperFillApplicationBatchRequest")
        if not isinstance(self.status, PaperFillApplicationBatchStatus):
            raise error("status must be PaperFillApplicationBatchStatus")
        for name in (
            "pre_engine_state_id",
            "pre_ledger_state_id",
            "post_engine_state_id",
            "post_ledger_state_id",
        ):
            if not isinstance(getattr(self, name), UUID):
                raise error(f"{name} must be a UUID")
        try:
            evaluations = tuple(self.evaluations)
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("result collections must be iterable") from caught
        if not all(
            isinstance(item, PaperFillApplicationEvaluation) for item in evaluations
        ):
            raise error("evaluations contain invalid values")
        if not all(
            isinstance(item, PaperFillApplicationDiagnostic) for item in diagnostics
        ):
            raise error("diagnostics contain invalid values")
        if tuple(item.source_fill_ordinal for item in evaluations) != tuple(
            range(len(evaluations))
        ):
            raise error("application ordinals must be sequential")
        if self.status is PaperFillApplicationBatchStatus.APPLIED:
            if not evaluations or diagnostics:
                raise error("APPLIED requires evaluations and no diagnostics")
        elif (
            evaluations
            or tuple(item.code for item in diagnostics)
            != (PaperFillApplicationDiagnosticCode.NO_ACTION,)
            or self.pre_engine_state_id != self.post_engine_state_id
            or self.pre_ledger_state_id != self.post_ledger_state_id
        ):
            raise error("NO_ACTION requires one diagnostic and unchanged state IDs")
        if len(evaluations) != len(self.request.fill_batch.evaluations):
            raise error("application count must equal source fill count")
        for evaluation, source in zip(
            evaluations, self.request.fill_batch.evaluations, strict=True
        ):
            _validate_result_evaluation(self.request, evaluation, source.fill)
        expected_id = _result_id(
            self.request,
            self.status,
            evaluations,
            self.pre_engine_state_id,
            self.pre_ledger_state_id,
            self.post_engine_state_id,
            self.post_ledger_state_id,
            diagnostics,
        )
        if self.result_id != expected_id:
            raise error("result_id does not match deterministic identity")
        object.__setattr__(self, "evaluations", evaluations)
        object.__setattr__(self, "diagnostics", diagnostics)


class PaperFillApplier:
    """Own and atomically replace authoritative order and ledger state."""

    def __init__(self, engine: OrderEngine, ledger: PaperLedger) -> None:
        if not isinstance(engine, OrderEngine):
            raise TypeError("engine must be an OrderEngine")
        if not isinstance(ledger, PaperLedger):
            raise TypeError("ledger must be a PaperLedger")
        self._engine = engine
        self._ledger = ledger

    @property
    def engine(self) -> OrderEngine:
        return self._engine

    @property
    def ledger(self) -> PaperLedger:
        return self._ledger

    def apply(
        self, request: PaperFillApplicationBatchRequest
    ) -> PaperFillApplicationBatchResult:
        if not isinstance(request, PaperFillApplicationBatchRequest):
            raise TypeError("request must be PaperFillApplicationBatchRequest")
        fills, source_orders, source_events = _validate_source(request)
        engine_before = _engine_snapshot(self._engine)
        ledger_before = _ledger_snapshot(self._ledger)
        if not fills:
            pre_engine_id = _engine_state_id(engine_before)
            pre_ledger_id = _ledger_state_id(ledger_before)
            diagnostic = PaperFillApplicationDiagnostic(
                PaperFillApplicationDiagnosticCode.NO_ACTION,
                "source paper-fill batch contained no candidates",
            )
            return _build_result(
                request,
                PaperFillApplicationBatchStatus.NO_ACTION,
                (),
                pre_engine_id,
                pre_ledger_id,
                pre_engine_id,
                pre_ledger_id,
                (diagnostic,),
            )
        _validate_live_engine(fills, source_orders, source_events, engine_before)
        _validate_live_ledger(fills, ledger_before)
        pre_engine_id = _engine_state_id(engine_before)
        pre_ledger_id = _ledger_state_id(ledger_before)
        event_ids = tuple(
            _fill_event_id(request, ordinal, fill, source_event)
            for ordinal, (fill, source_event) in enumerate(
                zip(fills, source_events, strict=True)
            )
        )
        if len(set(event_ids)) != len(event_ids):
            raise PaperFillApplicationEventCollisionError(
                "derived fill-event IDs must be unique"
            )
        existing_event_ids = {event.event_id for event in engine_before[1]}
        source_lifecycle_ids = {
            event.event_id
            for event in (
                *request.fill_batch.request.submission_batch.request.order_batch.created_events,
                *source_events,
            )
        }
        if existing_event_ids.intersection(
            event_ids
        ) or source_lifecycle_ids.intersection(event_ids):
            raise PaperFillApplicationEventCollisionError(
                "derived fill-event ID collides with lifecycle event identity"
            )
        try:
            shadow_engine = deepcopy(self._engine)
        except (CopyError, TypeError, ValueError, RuntimeError) as caught:
            raise PaperFillApplicationEngineCopyError(
                "order engine copy failed"
            ) from caught
        try:
            shadow_ledger = deepcopy(self._ledger)
        except (CopyError, TypeError, ValueError, RuntimeError) as caught:
            raise PaperFillApplicationLedgerCopyError(
                "paper ledger copy failed"
            ) from caught
        evaluations = []
        for ordinal, (fill, source_order, event_id) in enumerate(
            zip(fills, source_orders, event_ids, strict=True)
        ):
            try:
                updated_order = shadow_engine.apply_fill(fill, event_id=event_id)
            except OrderEngineError as caught:
                raise PaperFillEngineApplyError(
                    "shadow order engine rejected generated fill"
                ) from caught
            try:
                shadow_ledger.apply_fill(fill)
            except (LedgerError, TypeError, ValueError) as caught:
                raise PaperFillLedgerApplyError(
                    "shadow paper ledger rejected generated fill"
                ) from caught
            fill_event = shadow_engine.get_events()[-1]
            _reconcile_one(
                ordinal,
                fill,
                source_order,
                updated_order,
                fill_event,
                event_id,
                shadow_engine,
                shadow_ledger,
            )
            evaluations.append(
                PaperFillApplicationEvaluation(
                    ordinal,
                    fill,
                    updated_order,
                    fill_event,
                    shadow_ledger.cash,
                    shadow_ledger.get_position(fill.symbol),
                    shadow_ledger.realized_profit_loss,
                )
            )
        engine_after = _engine_snapshot(shadow_engine)
        ledger_after = _ledger_snapshot(shadow_ledger)
        _reconcile_batch(
            fills,
            source_orders,
            tuple(evaluations),
            event_ids,
            engine_before,
            ledger_before,
            engine_after,
            ledger_after,
        )
        post_engine_id = _engine_state_id(engine_after)
        post_ledger_id = _ledger_state_id(ledger_after)
        result = _build_result(
            request,
            PaperFillApplicationBatchStatus.APPLIED,
            tuple(evaluations),
            pre_engine_id,
            pre_ledger_id,
            post_engine_id,
            post_ledger_id,
            (),
        )
        self._engine = shadow_engine
        self._ledger = shadow_ledger
        return result


def _validate_source(
    request: PaperFillApplicationBatchRequest,
) -> tuple[tuple[OrderFill, ...], tuple[Order, ...], tuple[OrderEvent, ...]]:
    batch = request.fill_batch
    evaluations = batch.evaluations
    submission = batch.request.submission_batch
    orders = submission.orders
    events = submission.submitted_events
    if batch.status is PaperFillBatchStatus.NO_ACTION:
        if evaluations or batch.fills or orders or events:
            raise InconsistentPaperFillApplicationSourceError(
                "NO_ACTION source must not contain fill or submission output"
            )
        return (), (), ()
    if batch.status is not PaperFillBatchStatus.GENERATED or not evaluations:
        raise InconsistentPaperFillApplicationSourceError(
            "GENERATED source must contain evaluations"
        )
    if not (len(evaluations) == len(orders) == len(events)):
        raise InconsistentPaperFillApplicationSourceError(
            "fills, submitted orders, and events must align"
        )
    if tuple(item.source_order_ordinal for item in evaluations) != tuple(
        range(len(evaluations))
    ):
        raise InconsistentPaperFillApplicationSourceError(
            "source fill ordinals must be sequential"
        )
    fills = batch.fills
    if len({fill.fill_id for fill in fills}) != len(fills):
        raise InconsistentPaperFillApplicationSourceError(
            "source fill IDs must be unique"
        )
    for evaluation, fill, order, event in zip(
        evaluations, fills, orders, events, strict=True
    ):
        if evaluation.fill != fill:
            raise InconsistentPaperFillApplicationSourceError(
                "evaluation fill mapping is inconsistent"
            )
        if (
            order.status is not OrderStatus.SUBMITTED
            or event.event_type is not OrderEventType.SUBMITTED
            or event.order_id != order.request.order_id
            or fill.order_id != order.request.order_id
            or fill.symbol != order.request.symbol
            or fill.side is not order.request.side
            or fill.quantity != order.remaining_quantity
            or fill.quantity != order.request.quantity
        ):
            raise InconsistentPaperFillApplicationSourceError(
                "generated fill does not exactly map to a full submitted order"
            )
    return fills, orders, events


def _validate_live_engine(fills, source_orders, source_events, snapshot) -> None:  # type: ignore[no-untyped-def]
    order_map = dict(snapshot[0])
    all_fills = tuple(fill for _, history in snapshot[2] for fill in history)
    existing_fill_ids = {fill.fill_id for fill in all_fills}
    for fill, source, source_event in zip(
        fills, source_orders, source_events, strict=True
    ):
        active = order_map.get(fill.order_id)
        if active is None:
            raise PaperFillApplicationEngineStateError(
                f"source order {fill.order_id} is absent from active engine"
            )
        if (
            active.request != source.request
            or active.status is not OrderStatus.SUBMITTED
            or active.filled_quantity != source.filled_quantity
            or active.average_fill_price != source.average_fill_price
            or active.remaining_quantity != fill.quantity
            or fill.symbol != active.request.symbol
            or fill.side is not active.request.side
        ):
            raise PaperFillApplicationEngineStateError(
                "active order has advanced or differs from submitted source"
            )
        order_events = tuple(
            event for event in snapshot[1] if event.order_id == fill.order_id
        )
        if not order_events or order_events[-1] != source_event:
            raise PaperFillApplicationEngineStateError(
                "active latest event is not the exact source SUBMITTED event"
            )
        if fill.filled_at < order_events[-1].occurred_at:
            raise PaperFillApplicationEngineStateError(
                "candidate timestamp precedes active latest event"
            )
        if fill.fill_id in existing_fill_ids:
            raise PaperFillApplicationEngineStateError(
                "candidate fill ID already exists in active engine"
            )


def _validate_live_ledger(fills, snapshot) -> None:  # type: ignore[no-untyped-def]
    cash, realized, positions, history = snapshot
    if not cash.is_finite() or cash < _ZERO or not realized.is_finite():
        raise PaperFillApplicationLedgerStateError(
            "active ledger monetary state must be finite and valid"
        )
    for _, position in positions:
        if (
            not position.quantity.is_finite()
            or not position.average_cost.is_finite()
            or position.quantity <= _ZERO
            or position.average_cost <= _ZERO
        ):
            raise PaperFillApplicationLedgerStateError(
                "active ledger positions must be finite and positive"
            )
    existing_ids = tuple(fill.fill_id for fill in history)
    if len(set(existing_ids)) != len(existing_ids):
        raise PaperFillApplicationLedgerStateError(
            "active ledger fill IDs must be unique"
        )
    candidate_ids = {fill.fill_id for fill in fills}
    if candidate_ids.intersection(existing_ids):
        raise PaperFillApplicationLedgerStateError(
            "candidate fill already exists in active ledger"
        )
    symbols = {symbol for symbol, _ in positions}
    for fill in fills:
        if fill.side is OrderSide.SELL and fill.symbol not in symbols:
            raise PaperFillApplicationLedgerStateError(
                f"sell symbol {fill.symbol} is absent from active ledger"
            )


def _fill_event_id(
    request: PaperFillApplicationBatchRequest,
    ordinal: int,
    fill: OrderFill,
    source_event: OrderEvent,
) -> UUID:
    material = "|".join(
        (
            _VERSION,
            str(request.request_id),
            str(request.fill_batch.result_id),
            str(ordinal),
            str(fill.fill_id),
            str(fill.order_id),
            str(source_event.event_id),
            fill.filled_at.isoformat(),
            OrderEventType.FILLED.value,
            OrderStatus.FILLED.value,
        )
    )
    return uuid5(_NAMESPACE, f"fill-event|{material}")


def _reconcile_one(
    ordinal,
    fill,
    source_order,
    updated_order,
    event,
    event_id,
    engine,
    ledger,
) -> None:  # type: ignore[no-untyped-def]
    error = InconsistentPaperFillApplicationResultError
    if (
        updated_order.request != source_order.request
        or updated_order.status is not OrderStatus.FILLED
        or updated_order.filled_quantity != source_order.request.quantity
        or updated_order.remaining_quantity != _ZERO
        or updated_order.average_fill_price != fill.price
    ):
        raise error(f"updated order at ordinal {ordinal} is not a full fill")
    if (
        event.event_id != event_id
        or event.event_type is not OrderEventType.FILLED
        or event.order_id != fill.order_id
        or event.fill_id != fill.fill_id
        or event.occurred_at != fill.filled_at
        or event.reason is not None
    ):
        raise error(f"fill event at ordinal {ordinal} is inconsistent")
    engine_matches = tuple(
        item for item in engine.get_fills(fill.order_id) if item == fill
    )
    ledger_matches = tuple(item for item in ledger.fills if item == fill)
    if len(engine_matches) != 1 or len(ledger_matches) != 1:
        raise error("engine and ledger must each contain the exact fill once")


def _reconcile_batch(
    fills,
    source_orders,
    evaluations,
    event_ids,
    engine_before,
    ledger_before,
    engine_after,
    ledger_after,
) -> None:  # type: ignore[no-untyped-def]
    error = InconsistentPaperFillApplicationResultError
    before_orders, before_events, before_fills = engine_before
    after_orders, after_events, after_fills = engine_after
    if tuple(item[0] for item in after_orders) != tuple(
        item[0] for item in before_orders
    ):
        raise error("application added, removed, or reordered engine orders")
    source_ids = {fill.order_id for fill in fills}
    evaluation_map = {item.fill.order_id: item.updated_order for item in evaluations}
    for (order_id, before), (_, after) in zip(before_orders, after_orders, strict=True):
        if order_id in source_ids:
            if after != evaluation_map[order_id]:
                raise error("source order does not match applied audit snapshot")
        elif after != before:
            raise error("unrelated engine order changed")
    if after_events[: len(before_events)] != before_events:
        raise error("preexisting engine events are not an exact prefix")
    event_suffix = after_events[len(before_events) :]
    if tuple(item.event_id for item in event_suffix) != event_ids:
        raise error("engine fill-event suffix is inconsistent")
    before_fill_map = dict(before_fills)
    after_fill_map = dict(after_fills)
    fill_map = {fill.order_id: fill for fill in fills}
    for order_id in before_fill_map:
        expected = before_fill_map[order_id]
        if order_id in fill_map:
            expected = expected + (fill_map[order_id],)
        if after_fill_map[order_id] != expected:
            raise error("engine fill histories were not preserved and extended exactly")
    before_cash, before_realized, before_positions, before_history = ledger_before
    del before_cash, before_realized
    after_cash, after_realized, after_positions, after_history = ledger_after
    del after_cash, after_realized
    if after_history != before_history + fills:
        raise error("ledger fill history does not have exact candidate suffix")
    touched = {fill.symbol for fill in fills}
    before_position_map = dict(before_positions)
    after_position_map = dict(after_positions)
    for symbol, position in before_position_map.items():
        if symbol not in touched and after_position_map.get(symbol) != position:
            raise error("untouched ledger position changed")
    final_by_symbol = {}
    for evaluation in evaluations:
        final_by_symbol[evaluation.fill.symbol] = evaluation.ledger_position_after
    for symbol, expected in final_by_symbol.items():
        if after_position_map.get(symbol) != expected:
            raise error("final touched ledger position differs from audit snapshot")
    if tuple(item.fill for item in evaluations) != fills or tuple(
        item.updated_order.request.order_id for item in evaluations
    ) != tuple(item.request.order_id for item in source_orders):
        raise error("application audit order does not match source order")


def _validate_result_evaluation(
    request: PaperFillApplicationBatchRequest,
    evaluation: PaperFillApplicationEvaluation,
    source_fill: OrderFill,
) -> None:
    error = InconsistentPaperFillApplicationResultError
    ordinal = evaluation.source_fill_ordinal
    source_event = request.fill_batch.request.submission_batch.submitted_events[ordinal]
    expected_event_id = _fill_event_id(request, ordinal, source_fill, source_event)
    if evaluation.fill != source_fill:
        raise error("application evaluation fill differs from source candidate")
    order = evaluation.updated_order
    event = evaluation.fill_event
    if (
        order.request.order_id != source_fill.order_id
        or order.status is not OrderStatus.FILLED
        or order.filled_quantity != order.request.quantity
        or order.remaining_quantity != _ZERO
        or order.average_fill_price != source_fill.price
        or event.event_id != expected_event_id
        or event.event_type is not OrderEventType.FILLED
        or event.order_id != source_fill.order_id
        or event.fill_id != source_fill.fill_id
        or event.occurred_at != source_fill.filled_at
    ):
        raise error("application evaluation order or event mapping is inconsistent")


def _request_fingerprint(request: PaperFillApplicationBatchRequest) -> str:
    return "|".join(
        (
            _VERSION,
            str(request.request_id),
            str(request.fill_batch.result_id),
            *(f"{item.key}={item.value}" for item in request.metadata),
        )
    )


def _result_id(
    request,
    status,
    evaluations,
    pre_engine_id,
    pre_ledger_id,
    post_engine_id,
    post_ledger_id,
    diagnostics,
) -> UUID:  # type: ignore[no-untyped-def]
    material = [
        _request_fingerprint(request),
        status.value,
        str(pre_engine_id),
        str(pre_ledger_id),
        str(post_engine_id),
        str(post_ledger_id),
    ]
    for evaluation in evaluations:
        material.extend(
            (
                str(evaluation.fill.fill_id),
                str(evaluation.fill_event.event_id),
                str(evaluation.updated_order.request.order_id),
                evaluation.updated_order.status.value,
                _canonical_decimal(evaluation.ledger_cash_after),
                "none"
                if evaluation.ledger_position_after is None
                else f"{evaluation.ledger_position_after.symbol}:"
                f"{_canonical_decimal(evaluation.ledger_position_after.quantity)}:"
                f"{_canonical_decimal(evaluation.ledger_position_after.average_cost)}",
                _canonical_decimal(evaluation.ledger_realized_profit_loss_after),
            )
        )
    material.extend(item.code.value for item in diagnostics)
    return uuid5(_NAMESPACE, "result|" + "|".join(material))


def _build_result(
    request,
    status,
    evaluations,
    pre_engine_id,
    pre_ledger_id,
    post_engine_id,
    post_ledger_id,
    diagnostics,
) -> PaperFillApplicationBatchResult:  # type: ignore[no-untyped-def]
    return PaperFillApplicationBatchResult(
        _result_id(
            request,
            status,
            evaluations,
            pre_engine_id,
            pre_ledger_id,
            post_engine_id,
            post_ledger_id,
            diagnostics,
        ),
        request,
        status,
        evaluations,
        pre_engine_id,
        pre_ledger_id,
        post_engine_id,
        post_ledger_id,
        diagnostics,
    )
