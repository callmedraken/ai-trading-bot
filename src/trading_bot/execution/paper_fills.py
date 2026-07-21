"""Pure deterministic generation of unapplied paper-fill candidates."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import (
    Order,
    OrderFill,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)
from trading_bot.domain._validation import normalize_utc
from trading_bot.execution.exceptions import (
    InconsistentPaperFillBatchResultError,
    InconsistentPaperFillSourceError,
    InvalidPaperFillBatchRequestError,
    PaperFillCreationError,
    PaperFillIdentityError,
)
from trading_bot.execution.models import OrderEvent, OrderEventType
from trading_bot.execution.paper_submission import (
    PaperSubmissionBatchResult,
    PaperSubmissionBatchStatus,
)
from trading_bot.portfolio import MetadataEntry

_ZERO = Decimal("0")
_BASIS_POINT_DENOMINATOR = Decimal("10000")
_VERSION = "paper-fill-v1"
_NAMESPACE = UUID("848f97da-162d-542f-8322-e50fc9b752b8")


def _request_decimal(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise InvalidPaperFillBatchRequestError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise InvalidPaperFillBatchRequestError(f"{name} must be finite")
    return _ZERO if value == _ZERO else value


def _canonical_decimal(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("identity Decimal values must be finite")
    normalized = _ZERO if value == _ZERO else value.normalize()
    return format(normalized, "f")


@dataclass(frozen=True, slots=True)
class PaperFillPrice:
    order_id: UUID
    reference_price: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, UUID):
            raise InvalidPaperFillBatchRequestError("price order_id must be a UUID")
        price = _request_decimal(self.reference_price, "reference_price")
        if price <= _ZERO:
            raise InvalidPaperFillBatchRequestError(
                "reference_price must be greater than zero"
            )
        object.__setattr__(self, "reference_price", price)


@dataclass(frozen=True, slots=True)
class PaperFillPolicy:
    slippage_basis_points: Decimal = _ZERO
    fixed_commission: Decimal = _ZERO

    def __post_init__(self) -> None:
        slippage = _request_decimal(self.slippage_basis_points, "slippage_basis_points")
        commission = _request_decimal(self.fixed_commission, "fixed_commission")
        if not _ZERO <= slippage < _BASIS_POINT_DENOMINATOR:
            raise InvalidPaperFillBatchRequestError(
                "slippage_basis_points must be between 0 and 10000"
            )
        if commission < _ZERO:
            raise InvalidPaperFillBatchRequestError(
                "fixed_commission must be zero or greater"
            )
        object.__setattr__(self, "slippage_basis_points", slippage)
        object.__setattr__(self, "fixed_commission", commission)


@dataclass(frozen=True, slots=True)
class PaperFillBatchRequest:
    request_id: UUID
    submission_batch: PaperSubmissionBatchResult
    filled_at: datetime
    prices: tuple[PaperFillPrice, ...]
    policy: PaperFillPolicy
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidPaperFillBatchRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if not isinstance(self.submission_batch, PaperSubmissionBatchResult):
            raise error("submission_batch must be a PaperSubmissionBatchResult")
        try:
            filled_at = normalize_utc(self.filled_at, "filled_at")
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        try:
            prices = tuple(self.prices)
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("prices and metadata must be iterable") from caught
        if not all(isinstance(item, PaperFillPrice) for item in prices):
            raise error("prices must contain PaperFillPrice values")
        if len({item.order_id for item in prices}) != len(prices):
            raise error("price order IDs must be unique")
        if not isinstance(self.policy, PaperFillPolicy):
            raise error("policy must be a PaperFillPolicy")
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        object.__setattr__(self, "filled_at", filled_at)
        object.__setattr__(self, "prices", prices)
        object.__setattr__(self, "metadata", metadata)


class PaperFillBatchStatus(StrEnum):
    GENERATED = "GENERATED"
    NO_ACTION = "NO_ACTION"


class PaperFillDiagnosticCode(StrEnum):
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class PaperFillDiagnostic:
    code: PaperFillDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        error = InconsistentPaperFillBatchResultError
        if not isinstance(self.code, PaperFillDiagnosticCode):
            raise error("diagnostic code must be PaperFillDiagnosticCode")
        if not isinstance(self.message, str) or not self.message.strip():
            raise error("diagnostic message must be nonblank")


@dataclass(frozen=True, slots=True)
class PaperFillEvaluation:
    source_order_ordinal: int
    reference_price: Decimal
    slippage_amount: Decimal
    fill: OrderFill

    def __post_init__(self) -> None:
        error = InconsistentPaperFillBatchResultError
        if (
            not isinstance(self.source_order_ordinal, int)
            or isinstance(self.source_order_ordinal, bool)
            or self.source_order_ordinal < 0
        ):
            raise error("source_order_ordinal must be a nonnegative integer")
        for name in ("reference_price", "slippage_amount"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise error(f"{name} must be a finite Decimal")
        if self.reference_price <= _ZERO:
            raise error("reference_price must be positive")
        if self.slippage_amount < _ZERO:
            raise error("slippage_amount must be nonnegative")
        if not isinstance(self.fill, OrderFill):
            raise error("fill must be an OrderFill")


@dataclass(frozen=True, slots=True)
class PaperFillBatchResult:
    result_id: UUID
    request: PaperFillBatchRequest
    status: PaperFillBatchStatus
    evaluations: tuple[PaperFillEvaluation, ...]
    diagnostics: tuple[PaperFillDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentPaperFillBatchResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, PaperFillBatchRequest):
            raise error("request must be PaperFillBatchRequest")
        if not isinstance(self.status, PaperFillBatchStatus):
            raise error("status must be PaperFillBatchStatus")
        try:
            evaluations = tuple(self.evaluations)
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("result collections must be iterable") from caught
        if not all(isinstance(item, PaperFillEvaluation) for item in evaluations):
            raise error("evaluations contain invalid values")
        if not all(isinstance(item, PaperFillDiagnostic) for item in diagnostics):
            raise error("diagnostics contain invalid values")
        if tuple(item.source_order_ordinal for item in evaluations) != tuple(
            range(len(evaluations))
        ):
            raise error("evaluation ordinals must be sequential")
        if self.status is PaperFillBatchStatus.GENERATED:
            if not evaluations or diagnostics:
                raise error("GENERATED requires evaluations and no diagnostics")
        elif evaluations or tuple(item.code for item in diagnostics) != (
            PaperFillDiagnosticCode.NO_ACTION,
        ):
            raise error("NO_ACTION requires one diagnostic and no evaluations")
        source_orders = self.request.submission_batch.orders
        source_events = self.request.submission_batch.submitted_events
        if len(evaluations) != len(source_orders):
            raise error("evaluation count must equal source order count")
        if len({item.fill.fill_id for item in evaluations}) != len(evaluations):
            raise error("fill IDs must be unique")
        for evaluation, source, event, price in zip(
            evaluations,
            source_orders,
            source_events,
            self.request.prices,
            strict=True,
        ):
            _validate_evaluation(self.request, evaluation, source, event, price)
        expected_id = _result_id(self.request, self.status, evaluations, diagnostics)
        if self.result_id != expected_id:
            raise error("result_id does not match deterministic identity")
        object.__setattr__(self, "evaluations", evaluations)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def fills(self) -> tuple[OrderFill, ...]:
        return tuple(evaluation.fill for evaluation in self.evaluations)


class PaperFillGenerator:
    """Generate immutable fill candidates without applying them."""

    def generate(self, request: PaperFillBatchRequest) -> PaperFillBatchResult:
        if not isinstance(request, PaperFillBatchRequest):
            raise TypeError("request must be PaperFillBatchRequest")
        source_orders, source_events = _validate_source(request)
        if not source_orders:
            diagnostics = (
                PaperFillDiagnostic(
                    PaperFillDiagnosticCode.NO_ACTION,
                    "source paper-submission batch contained no orders",
                ),
            )
            return _build_result(
                request, PaperFillBatchStatus.NO_ACTION, (), diagnostics
            )
        candidates = tuple(
            _candidate_values(request, ordinal, order, event, price)
            for ordinal, (order, event, price) in enumerate(
                zip(source_orders, source_events, request.prices, strict=True)
            )
        )
        fill_ids = tuple(item[0] for item in candidates)
        if len(set(fill_ids)) != len(fill_ids):
            raise PaperFillIdentityError("derived fill IDs must be unique")
        evaluations = []
        for ordinal, (source, price, candidate) in enumerate(
            zip(source_orders, request.prices, candidates, strict=True)
        ):
            fill_id, slippage_amount, final_price = candidate
            try:
                fill = OrderFill(
                    fill_id=fill_id,
                    order_id=source.request.order_id,
                    symbol=source.request.symbol,
                    side=source.request.side,
                    quantity=source.request.quantity,
                    price=final_price,
                    commission=request.policy.fixed_commission,
                    filled_at=request.filled_at,
                )
            except (TypeError, ValueError) as caught:
                raise PaperFillCreationError(
                    "fill candidate construction failed"
                ) from caught
            evaluations.append(
                PaperFillEvaluation(
                    ordinal, price.reference_price, slippage_amount, fill
                )
            )
        return _build_result(
            request,
            PaperFillBatchStatus.GENERATED,
            tuple(evaluations),
            (),
        )


def _validate_source(
    request: PaperFillBatchRequest,
) -> tuple[tuple[Order, ...], tuple[OrderEvent, ...]]:
    batch = request.submission_batch
    orders = batch.orders
    events = batch.submitted_events
    if batch.status is PaperSubmissionBatchStatus.NO_ACTION:
        if orders or events:
            raise InconsistentPaperFillSourceError(
                "NO_ACTION submission must not contain output"
            )
        if request.prices:
            raise InvalidPaperFillBatchRequestError(
                "NO_ACTION fill request must not contain prices"
            )
        return (), ()
    if batch.status is not PaperSubmissionBatchStatus.SUBMITTED or not orders:
        raise InconsistentPaperFillSourceError(
            "SUBMITTED source must contain at least one order"
        )
    if len(orders) != len(events):
        raise InconsistentPaperFillSourceError(
            "source orders and submitted events must align"
        )
    if len({item.request.order_id for item in orders}) != len(orders):
        raise InconsistentPaperFillSourceError("source order IDs must be unique")
    if len({item.event_id for item in events}) != len(events):
        raise InconsistentPaperFillSourceError(
            "source submitted-event IDs must be unique"
        )
    expected_price_ids = tuple(item.request.order_id for item in orders)
    actual_price_ids = tuple(item.order_id for item in request.prices)
    if actual_price_ids != expected_price_ids:
        raise InvalidPaperFillBatchRequestError(
            "prices must exactly match source order IDs and order"
        )
    for order, event in zip(orders, events, strict=True):
        order_request = order.request
        quantity = order.remaining_quantity
        if order.status is not OrderStatus.SUBMITTED:
            raise InconsistentPaperFillSourceError("source order must be SUBMITTED")
        if (
            order_request.order_type is not OrderType.MARKET
            or order_request.time_in_force is not TimeInForce.DAY
            or order_request.limit_price is not None
        ):
            raise InconsistentPaperFillSourceError(
                "source orders must be MARKET DAY without limit_price"
            )
        if (
            order.filled_quantity != _ZERO
            or order.average_fill_price is not None
            or quantity != order_request.quantity
            or not isinstance(quantity, Decimal)
            or not quantity.is_finite()
            or quantity <= _ZERO
        ):
            raise InconsistentPaperFillSourceError(
                "source order must be unfilled with positive full remaining quantity"
            )
        if (
            event.event_type is not OrderEventType.SUBMITTED
            or event.order_id != order_request.order_id
        ):
            raise InconsistentPaperFillSourceError(
                "submitted event must align with source order"
            )
        if event.occurred_at < order_request.submitted_at:
            raise InconsistentPaperFillSourceError(
                "source submission event precedes order request creation"
            )
        if (
            request.filled_at < event.occurred_at
            or request.filled_at < order_request.submitted_at
        ):
            raise InconsistentPaperFillSourceError(
                "fill timestamp precedes source submission chronology"
            )
    return orders, events


def _slippage_values(
    reference_price: Decimal, side: OrderSide, basis_points: Decimal
) -> tuple[Decimal, Decimal]:
    slippage_amount = reference_price * (basis_points / _BASIS_POINT_DENOMINATOR)
    final_price = (
        reference_price + slippage_amount
        if side is OrderSide.BUY
        else reference_price - slippage_amount
    )
    if (
        not slippage_amount.is_finite()
        or slippage_amount < _ZERO
        or not final_price.is_finite()
        or final_price <= _ZERO
    ):
        raise InvalidPaperFillBatchRequestError(
            "slippage must produce finite nonnegative impact and positive price"
        )
    return slippage_amount, final_price


def _candidate_values(
    request: PaperFillBatchRequest,
    ordinal: int,
    order: Order,
    event: OrderEvent,
    price: PaperFillPrice,
) -> tuple[UUID, Decimal, Decimal]:
    slippage_amount, final_price = _slippage_values(
        price.reference_price,
        order.request.side,
        request.policy.slippage_basis_points,
    )
    material = "|".join(
        (
            _VERSION,
            str(request.request_id),
            str(request.submission_batch.result_id),
            str(ordinal),
            str(order.request.order_id),
            str(event.event_id),
            order.request.side.value,
            _canonical_decimal(order.request.quantity),
            _canonical_decimal(price.reference_price),
            _canonical_decimal(request.policy.slippage_basis_points),
            _canonical_decimal(final_price),
            _canonical_decimal(request.policy.fixed_commission),
            request.filled_at.isoformat(),
        )
    )
    return uuid5(_NAMESPACE, f"fill|{material}"), slippage_amount, final_price


def _validate_evaluation(
    request: PaperFillBatchRequest,
    evaluation: PaperFillEvaluation,
    source: Order,
    event: OrderEvent,
    price: PaperFillPrice,
) -> None:
    error = InconsistentPaperFillBatchResultError
    ordinal = evaluation.source_order_ordinal
    expected_id, expected_slippage, expected_price = _candidate_values(
        request, ordinal, source, event, price
    )
    fill = evaluation.fill
    if (
        price.order_id != source.request.order_id
        or evaluation.reference_price != price.reference_price
        or evaluation.slippage_amount != expected_slippage
        or fill.fill_id != expected_id
        or fill.order_id != source.request.order_id
        or fill.symbol != source.request.symbol
        or fill.side is not source.request.side
        or fill.quantity != source.request.quantity
        or fill.price != expected_price
        or fill.commission != request.policy.fixed_commission
        or fill.filled_at != request.filled_at
    ):
        raise error("fill evaluation does not match its source and request")


def _request_fingerprint(request: PaperFillBatchRequest) -> str:
    return "|".join(
        (
            _VERSION,
            str(request.request_id),
            str(request.submission_batch.result_id),
            request.filled_at.isoformat(),
            _canonical_decimal(request.policy.slippage_basis_points),
            _canonical_decimal(request.policy.fixed_commission),
            *(
                f"{item.order_id}={_canonical_decimal(item.reference_price)}"
                for item in request.prices
            ),
            *(f"{item.key}={item.value}" for item in request.metadata),
        )
    )


def _result_id(
    request: PaperFillBatchRequest,
    status: PaperFillBatchStatus,
    evaluations: tuple[PaperFillEvaluation, ...],
    diagnostics: tuple[PaperFillDiagnostic, ...],
) -> UUID:
    material = [
        _request_fingerprint(request),
        status.value,
    ]
    for evaluation in evaluations:
        ordinal = evaluation.source_order_ordinal
        material.extend(
            (
                str(ordinal),
                str(evaluation.fill.order_id),
                str(request.submission_batch.submitted_events[ordinal].event_id),
                _canonical_decimal(evaluation.reference_price),
                _canonical_decimal(evaluation.slippage_amount),
                str(evaluation.fill.fill_id),
            )
        )
    material.extend(item.code.value for item in diagnostics)
    return uuid5(_NAMESPACE, "result|" + "|".join(material))


def _build_result(
    request: PaperFillBatchRequest,
    status: PaperFillBatchStatus,
    evaluations: tuple[PaperFillEvaluation, ...],
    diagnostics: tuple[PaperFillDiagnostic, ...],
) -> PaperFillBatchResult:
    return PaperFillBatchResult(
        _result_id(request, status, evaluations, diagnostics),
        request,
        status,
        evaluations,
        diagnostics,
    )
