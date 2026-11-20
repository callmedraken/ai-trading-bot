"""Durable Architecture 148 order-write reservations and factual tracking.

This module is effect-free. A successful reservation records that a write may
have occurred; callers must perform no more than the single invocation guarded
by that reservation. It never retries a possibly invoked write.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import Lock
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide

from .models import (
    SQQQ,
    TQQQ,
    TRADED_SYMBOLS,
    BrokerOrderFact,
    BrokerReviewFacts,
    BrokerSnapshot,
    IntentKind,
    IntentLifecycle,
    LogicalOrderIntent,
    OrderState,
    PendingExit,
    ProtectiveStopCancelCandidate,
    RuntimeState,
    RuntimeStateStore,
    SourceIdentity,
    decimal_sum_equals,
)

_OPERATION_NAMESPACE = UUID("a5a27dd2-bfe8-5678-9c0b-38f3937f193b")
_MAX_FACT_AGE = timedelta(seconds=30)
_MAX_PRICE_AGE = timedelta(seconds=15)
_PERMIT_SEAL = object()
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class OrderWriteAction(StrEnum):
    PLACE = "PLACE"
    CANCEL = "CANCEL"


class OrderWriteStatus(StrEnum):
    MAY_HAVE_OCCURRED = "MAY_HAVE_OCCURRED"
    UNKNOWN = "UNKNOWN"
    OBSERVED = "OBSERVED"
    TERMINAL = "TERMINAL"


class OrderTrackerError(RuntimeError):
    """A reservation or factual update failed closed."""


@dataclass(frozen=True, slots=True)
class TrackedOrder:
    """Independent durable logical/ref/approval/provider identity linkage."""

    intent_id: UUID
    ref_id: str
    approval_id: str | None = None
    provider_order_id: str | None = None
    last_fact: BrokerOrderFact | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, UUID):
            raise TypeError("intent_id must be UUID")
        if not isinstance(self.ref_id, str) or not self.ref_id:
            raise ValueError("ref_id must be nonblank")
        for name in ("approval_id", "provider_order_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{name} must be nonblank or None")
        if self.last_fact is not None:
            if not isinstance(self.last_fact, BrokerOrderFact):
                raise TypeError("last_fact must be BrokerOrderFact or None")
            if (
                self.last_fact.intent_id not in (None, self.intent_id)
                or self.last_fact.ref_id not in (None, self.ref_id)
                or self.last_fact.provider_order_id != self.provider_order_id
            ):
                raise ValueError("last order fact identity differs from tracker")


@dataclass(frozen=True, slots=True)
class OrderWriteReservation:
    """One persisted MAY_HAVE_OCCURRED boundary for an exact order operation."""

    operation_id: UUID
    action: OrderWriteAction
    intent_id: UUID
    ref_id: str
    terms_digest: str
    owner_id: UUID
    source_identity: SourceIdentity
    account_fingerprint: str
    session_fingerprint: str
    expected_revision: int
    reserved_revision: int
    review_revision: int | None = None
    review: BrokerReviewFacts | None = None
    approval_id: str | None = None
    target_provider_order_id: str | None = None
    status: OrderWriteStatus = OrderWriteStatus.MAY_HAVE_OCCURRED

    def __post_init__(self) -> None:
        if (
            not isinstance(self.operation_id, UUID)
            or not isinstance(self.intent_id, UUID)
            or not isinstance(self.owner_id, UUID)
        ):
            raise TypeError("operation, intent and owner identities must be UUID")
        if not isinstance(self.action, OrderWriteAction):
            raise TypeError("action must be OrderWriteAction")
        for name in (
            "ref_id",
            "terms_digest",
            "account_fingerprint",
            "session_fingerprint",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be nonblank")
        if _HEX64.fullmatch(self.terms_digest) is None:
            raise ValueError("terms_digest must be a lowercase SHA-256 digest")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("source_identity must be SourceIdentity")
        for name in ("expected_revision", "reserved_revision"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.reserved_revision != self.expected_revision + 1:
            raise ValueError(
                "reserved_revision must immediately follow expected_revision"
            )
        if self.review is not None and not isinstance(self.review, BrokerReviewFacts):
            raise TypeError("review must be BrokerReviewFacts or None")
        if self.review_revision is not None and (
            not isinstance(self.review_revision, int)
            or isinstance(self.review_revision, bool)
            or self.review_revision < 0
        ):
            raise ValueError("review_revision must be nonnegative or None")
        if self.approval_id is not None and (
            not isinstance(self.approval_id, str) or not self.approval_id
        ):
            raise ValueError("approval_id must be nonblank or None")
        if self.target_provider_order_id is not None and (
            not isinstance(self.target_provider_order_id, str)
            or not self.target_provider_order_id
        ):
            raise ValueError("target_provider_order_id must be nonblank or None")
        if not isinstance(self.status, OrderWriteStatus):
            raise TypeError("status must be OrderWriteStatus")
        if self.action is OrderWriteAction.PLACE:
            if (
                self.review is None
                or self.review_revision is None
                or self.target_provider_order_id is not None
            ):
                raise ValueError("PLACE requires exact review and no target order ID")
            if (
                self.review.ref_id != self.ref_id
                or self.review.terms_digest != self.terms_digest
                or self.review.state_revision != self.review_revision
                or self.review_revision
                not in (self.expected_revision, self.expected_revision - 1)
                or self.review.source_identity != self.source_identity
                or self.review.account_fingerprint != self.account_fingerprint
                or self.review.session_fingerprint != self.session_fingerprint
                or self.review.status.value != "ACCEPTED"
                or self.review.warnings
                or self.review.approval_required
            ):
                raise ValueError("PLACE review is not bound to this reservation")
        else:
            if (
                self.review is not None
                or self.review_revision is not None
                or self.approval_id is not None
            ):
                raise ValueError("CANCEL cannot reuse placement review/approval IDs")
            if self.target_provider_order_id is None:
                raise ValueError("CANCEL requires an exact target provider order ID")
        if self.operation_id != _operation_id(
            action=self.action,
            owner_id=self.owner_id,
            source_identity=self.source_identity,
            intent_id=self.intent_id,
            ref_id=self.ref_id,
            expected_revision=self.expected_revision,
            target_provider_order_id=self.target_provider_order_id,
        ):
            raise ValueError("operation_id differs from canonical reservation identity")


@dataclass(frozen=True, slots=True)
class ReservationResult:
    state: RuntimeState
    reservation: OrderWriteReservation
    permit: InProcessWritePermit

    def __post_init__(self) -> None:
        if not isinstance(self.state, RuntimeState):
            raise TypeError("state must be RuntimeState")
        if not isinstance(self.reservation, OrderWriteReservation):
            raise TypeError("reservation must be OrderWriteReservation")
        if not isinstance(self.permit, InProcessWritePermit):
            raise TypeError("permit must be InProcessWritePermit")
        if self.state.revision != self.reservation.reserved_revision:
            raise ValueError("result state is not the exact reserved revision")
        if self.reservation not in self.state.write_reservations:
            raise ValueError("reservation is not present in result state")
        if not self.permit.matches(self.reservation):
            raise ValueError("permit does not authorize the result reservation")


class InProcessWritePermit:
    """Nonserializable, process-local, lock-protected one-shot write permission."""

    __slots__ = ("_reservation", "_lock", "_consumed")

    def __init__(
        self, reservation: OrderWriteReservation, *, _seal: object | None = None
    ) -> None:
        if _seal is not _PERMIT_SEAL:
            raise TypeError("write permits are issued only by a successful CAS")
        if not isinstance(reservation, OrderWriteReservation):
            raise TypeError("reservation must be OrderWriteReservation")
        self._reservation = reservation
        self._lock = Lock()
        self._consumed = False

    def matches(self, reservation: OrderWriteReservation) -> bool:
        return reservation == self._reservation

    def consume(
        self, reservation: OrderWriteReservation, *, action: OrderWriteAction
    ) -> bool:
        if action is not self._reservation.action or not self.matches(reservation):
            return False
        with self._lock:
            if self._consumed:
                return False
            self._consumed = True
            return True


class OrderTracker:
    """CAS owner for place/cancel boundaries and exact broker observations."""

    def __init__(self, state_store: RuntimeStateStore) -> None:
        if not callable(getattr(state_store, "load", None)) or not callable(
            getattr(state_store, "compare_and_swap", None)
        ):
            raise TypeError("state_store must implement load and compare_and_swap")
        self._state_store = state_store

    @property
    def state_store(self) -> RuntimeStateStore:
        """Return the injected CAS owner so composition can verify identity."""

        return self._state_store

    def begin_place(
        self,
        *,
        owner_id: UUID,
        source_identity: SourceIdentity,
        session_fingerprint: str,
        expected_revision: int,
        intent_id: UUID,
        broker: BrokerSnapshot,
        as_of: datetime,
    ) -> ReservationResult | None:
        """Persist exact MAY state before a single placement invocation."""

        if not isinstance(broker, BrokerSnapshot):
            raise TypeError("broker must be BrokerSnapshot")
        state = self._load_bound_state(
            owner_id=owner_id,
            source_identity=source_identity,
            session_fingerprint=session_fingerprint,
            expected_revision=expected_revision,
            broker=broker,
        )
        if state is None:
            return None
        intent = next(
            (item for item in state.intents if item.intent_id == intent_id), None
        )
        if intent is None or intent.lifecycle is not IntentLifecycle.PROPOSED:
            return None
        if any(item.intent_id == intent_id for item in state.tracked_orders) or any(
            item.intent_id == intent_id and item.action is OrderWriteAction.PLACE
            for item in state.write_reservations
        ):
            return None
        review = broker.review
        if review is not None and (
            not _fresh(review.observed_at, as_of)
            or review.account_fingerprint != state.account_fingerprint
            or review.source_identity != state.source_identity
            or review.session_fingerprint != state.session_fingerprint
            or review.ref_id != intent.ref_id
            or review.terms_digest != intent.terms_digest
        ):
            return None
        stored_reviews = tuple(
            item
            for item in state.proposal_reviews
            if item.ref_id == intent.ref_id and item.terms_digest == intent.terms_digest
        )
        if len(stored_reviews) > 1:
            return None
        if stored_reviews and state.revision == stored_reviews[0].state_revision + 1:
            exact_review = stored_reviews[0]
            if review is not None and review.state_revision == state.revision:
                exact_review = review
        elif review is not None and review.state_revision == state.revision:
            exact_review = review
        else:
            return None
        if (
            exact_review.status.value != "ACCEPTED"
            or exact_review.warnings
            or exact_review.approval_required
            or not _fresh(exact_review.observed_at, as_of)
        ):
            return None
        if not _exhaustive_current_snapshot(broker, state, as_of):
            return None
        if (
            broker.approvals.setting_enabled is not False
            or broker.approvals.unresolved_refs
            or any(
                item.status.value in ("PENDING", "UNKNOWN")
                for item in broker.approvals.requests
            )
            or not _intent_snapshot_safe(state, intent, broker, as_of)
        ):
            return None
        if len({order.provider_order_id for order in broker.orders}) != len(
            broker.orders
        ):
            return None
        echoed_refs = tuple(
            order.ref_id for order in broker.orders if order.ref_id is not None
        )
        echoed_intents = tuple(
            order.intent_id for order in broker.orders if order.intent_id is not None
        )
        if len(set(echoed_refs)) != len(echoed_refs) or len(set(echoed_intents)) != len(
            echoed_intents
        ):
            return None
        known_external_ids = _known_external_ids(state)
        for order in broker.orders:
            if order.ref_id == intent.ref_id or order.intent_id == intent.intent_id:
                return None
            if order.provider_order_id in known_external_ids and not (
                _is_exact_settled_history_fact(state, order, as_of)
            ):
                return None
        reservation = _reservation(
            action=OrderWriteAction.PLACE,
            state=state,
            intent=intent,
            review=exact_review,
            approval_id=None,
            target_provider_order_id=None,
        )
        track = TrackedOrder(intent_id=intent.intent_id, ref_id=intent.ref_id)
        next_state = replace(
            state,
            revision=reservation.reserved_revision,
            intents=tuple(
                replace(item, lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED)
                if item.intent_id == intent.intent_id
                else item
                for item in state.intents
            ),
            tracked_orders=state.tracked_orders + (track,),
            write_reservations=state.write_reservations + (reservation,),
        )
        return self._commit(state, next_state, reservation)

    def begin_cancel(
        self,
        *,
        owner_id: UUID,
        source_identity: SourceIdentity,
        session_fingerprint: str,
        expected_revision: int,
        candidate: ProtectiveStopCancelCandidate,
        broker: BrokerSnapshot,
        as_of: datetime,
    ) -> ReservationResult | None:
        """Persist one planner-approved exact-stop cancel before invocation."""

        if not isinstance(candidate, ProtectiveStopCancelCandidate) or not isinstance(
            broker, BrokerSnapshot
        ):
            return None
        state = self._load_bound_state(
            owner_id=owner_id,
            source_identity=source_identity,
            session_fingerprint=session_fingerprint,
            expected_revision=expected_revision,
            broker=broker,
        )
        if (
            state is None
            or state.pending_exit is not None
            or broker.approvals.setting_enabled is not False
            or candidate.expected_state_revision != expected_revision
            or candidate.held_price.symbol != candidate.fact.symbol
            or not _fresh_with_max_age(
                candidate.held_price.observed_at, as_of, _MAX_PRICE_AGE
            )
        ):
            return None
        intent = next(
            (item for item in state.intents if item.intent_id == candidate.intent_id),
            None,
        )
        tracked = next(
            (
                item
                for item in state.tracked_orders
                if item.intent_id == candidate.intent_id
            ),
            None,
        )
        if (
            intent is None
            or intent.kind is not IntentKind.PROTECTIVE_STOP
            or intent.ref_id != candidate.ref_id
            or intent.terms_digest != candidate.terms_digest
            or intent.lifecycle
            not in (
                IntentLifecycle.MAY_HAVE_OCCURRED,
                IntentLifecycle.UNKNOWN,
                IntentLifecycle.RECONCILED,
            )
            or tracked is None
            or tracked.provider_order_id != candidate.provider_order_id
            or tracked.last_fact is None
            or tracked.last_fact.state
            not in (OrderState.OPEN, OrderState.PARTIALLY_FILLED)
        ):
            return None
        position_record = state.positions.get(intent.symbol)
        if (
            position_record is None
            or position_record.stop_intent_id != intent.intent_id
        ):
            return None
        if not _exhaustive_current_snapshot(broker, state, as_of):
            return None
        if any(
            item.action is OrderWriteAction.CANCEL
            and item.target_provider_order_id == candidate.provider_order_id
            for item in state.write_reservations
        ):
            return None
        facts = tuple(
            item
            for item in broker.orders
            if item.provider_order_id == candidate.provider_order_id
        )
        if len(facts) != 1:
            return None
        fact = facts[0]
        position = broker.positions.get(intent.symbol)
        if (
            not _fact_matches_intent(fact, intent, state)
            or fact.state not in (OrderState.OPEN, OrderState.PARTIALLY_FILLED)
            or fact.remaining_quantity != position_record.quantity
            or not _fresh(fact.observed_at, as_of)
            or not _same_bound_order_evidence(candidate.fact, fact, intent, state)
            or position is None
            or position.quantity != position_record.quantity
            or position.average_cost != position_record.average_entry_fill
            or broker.position_owners.get(intent.symbol)
            != position_record.entry_intent_id
            or any(
                symbol in broker.positions
                for symbol in TRADED_SYMBOLS
                if symbol != intent.symbol
            )
            or any(
                order.symbol in TRADED_SYMBOLS
                and not order.state.terminal
                and order.provider_order_id != candidate.provider_order_id
                for order in broker.orders
            )
        ):
            return None
        if not _same_bound_order_evidence(
            tracked.last_fact, fact, intent, state
        ) and not _fact_progresses(tracked.last_fact, fact):
            return None
        reservation = _reservation(
            action=OrderWriteAction.CANCEL,
            state=state,
            intent=intent,
            review=None,
            approval_id=None,
            target_provider_order_id=candidate.provider_order_id,
        )
        updated_track = (
            tracked
            if _same_order_evidence(tracked.last_fact, fact)
            else replace(
                tracked,
                provider_order_id=fact.provider_order_id,
                last_fact=fact,
            )
        )
        next_state = replace(
            state,
            revision=reservation.reserved_revision,
            tracked_orders=tuple(
                updated_track if item.intent_id == intent.intent_id else item
                for item in state.tracked_orders
            ),
            write_reservations=state.write_reservations + (reservation,),
            pending_exit=PendingExit(
                stop_intent_id=candidate.intent_id,
                stop_provider_order_id=candidate.provider_order_id,
                symbol=intent.symbol,
                exit_reasons=candidate.exit_reasons,
            ),
        )
        return self._commit(state, next_state, reservation)

    def mark_unknown(
        self,
        *,
        owner_id: UUID,
        source_identity: SourceIdentity,
        expected_revision: int,
        operation_id: UUID,
    ) -> RuntimeState | None:
        """Persist ambiguity without clearing or rearming the reservation."""

        state = self._load(owner_id, source_identity)
        if state is None or state.revision != expected_revision:
            return None
        reservation = next(
            (
                item
                for item in state.write_reservations
                if item.operation_id == operation_id
            ),
            None,
        )
        if (
            reservation is None
            or reservation.status is not OrderWriteStatus.MAY_HAVE_OCCURRED
        ):
            return None
        intents = tuple(
            replace(item, lifecycle=IntentLifecycle.UNKNOWN)
            if reservation.action is OrderWriteAction.PLACE
            and item.intent_id == reservation.intent_id
            and item.lifecycle is IntentLifecycle.MAY_HAVE_OCCURRED
            else item
            for item in state.intents
        )
        reservations = tuple(
            replace(item, status=OrderWriteStatus.UNKNOWN)
            if item.operation_id == operation_id
            else item
            for item in state.write_reservations
        )
        next_state = replace(
            state,
            revision=state.revision + 1,
            intents=intents,
            write_reservations=reservations,
        )
        try:
            return (
                next_state
                if self._state_store.compare_and_swap(state.revision, next_state)
                else None
            )
        except Exception:
            return None

    def record_order_fact(
        self,
        *,
        owner_id: UUID,
        source_identity: SourceIdentity,
        expected_revision: int,
        fact: BrokerOrderFact,
        as_of: datetime,
        approval_id: str | None = None,
        reservation: OrderWriteReservation | None = None,
    ) -> RuntimeState | None:
        """Persist one exact late/current fact; it never authorizes a retry."""

        if not isinstance(fact, BrokerOrderFact):
            raise TypeError("fact must be BrokerOrderFact")
        state = self._load(owner_id, source_identity)
        if (
            state is None
            or state.revision != expected_revision
            or not _fresh(fact.observed_at, as_of)
        ):
            return None
        if reservation is not None and (
            reservation.action is not OrderWriteAction.PLACE
            or reservation not in state.write_reservations
            or reservation.status
            not in (OrderWriteStatus.MAY_HAVE_OCCURRED, OrderWriteStatus.UNKNOWN)
            or reservation.owner_id != state.owner_id
            or reservation.source_identity != state.source_identity
            or reservation.account_fingerprint != state.account_fingerprint
            or reservation.session_fingerprint != state.session_fingerprint
        ):
            return None
        intent = (
            next(
                (
                    item
                    for item in state.intents
                    if item.intent_id == reservation.intent_id
                ),
                None,
            )
            if reservation is not None
            else _match_order_fact(state, fact)
        )
        if intent is None or not _fact_matches_intent(fact, intent, state):
            return None
        if reservation is None and (
            fact.source_identity != state.source_identity
            or fact.intent_id != intent.intent_id
            or fact.ref_id != intent.ref_id
        ):
            return None
        if approval_id is not None:
            receipts = tuple(
                receipt
                for receipt in state.approval_receipts
                if receipt.intent_id == intent.intent_id
                and receipt.approval_id == approval_id
                and receipt.ref_id == fact.ref_id
                and receipt.terms_digest == intent.terms_digest
            )
            if len(receipts) != 1:
                return None
        elif any(
            receipt.intent_id == intent.intent_id for receipt in state.approval_receipts
        ):
            return None
        tracked = next(
            (
                item
                for item in state.tracked_orders
                if item.intent_id == intent.intent_id
            ),
            None,
        )
        if tracked is not None and _same_order_evidence(tracked.last_fact, fact):
            return state
        if tracked is not None and not _fact_progresses(tracked.last_fact, fact):
            return None
        if _identifier_collision(state, fact, approval_id, intent.intent_id):
            return None
        updated = TrackedOrder(
            intent_id=intent.intent_id,
            ref_id=intent.ref_id,
            approval_id=approval_id or (tracked.approval_id if tracked else None),
            provider_order_id=fact.provider_order_id,
            last_fact=fact,
        )
        tracks = tuple(
            updated if item.intent_id == intent.intent_id else item
            for item in state.tracked_orders
        )
        if tracked is None:
            tracks += (updated,)
        reservations = tuple(
            _reservation_status_after_fact(item, fact)
            if item.intent_id == intent.intent_id
            else item
            for item in state.write_reservations
        )
        next_state = replace(
            state,
            revision=state.revision + 1,
            tracked_orders=tracks,
            write_reservations=reservations,
        )
        try:
            return (
                next_state
                if self._state_store.compare_and_swap(state.revision, next_state)
                else None
            )
        except Exception:
            return None

    def record_broker_snapshot(
        self,
        *,
        owner_id: UUID,
        source_identity: SourceIdentity,
        expected_revision: int,
        broker: BrokerSnapshot,
        as_of: datetime,
    ) -> RuntimeState | None:
        """Persist unique exact order observations from one fresh exhaustive read."""

        if not isinstance(broker, BrokerSnapshot):
            raise TypeError("broker must be BrokerSnapshot")
        state = self._load(owner_id, source_identity)
        if (
            state is None
            or state.revision != expected_revision
            or broker.state_revision != expected_revision
            or broker.source_identity != state.source_identity
            or broker.session_fingerprint != state.session_fingerprint
            or broker.account.fingerprint != state.account_fingerprint
            or not _exhaustive_current_snapshot(broker, state, as_of)
        ):
            return None
        try:
            updated = apply_broker_order_facts(state, broker.orders, as_of=as_of)
        except OrderTrackerError:
            return None
        if (
            updated.tracked_orders == state.tracked_orders
            and updated.write_reservations == state.write_reservations
        ):
            return state
        updated = replace(updated, revision=state.revision + 1)
        try:
            return (
                updated
                if self._state_store.compare_and_swap(state.revision, updated)
                else None
            )
        except Exception:
            return None

    def _load_bound_state(
        self,
        *,
        owner_id: UUID,
        source_identity: SourceIdentity,
        session_fingerprint: str,
        expected_revision: int,
        broker: BrokerSnapshot,
    ) -> RuntimeState | None:
        state = self._load(owner_id, source_identity)
        if (
            state is None
            or state.revision != expected_revision
            or state.session_fingerprint != session_fingerprint
            or state.account_fingerprint != broker.account.fingerprint
            or broker.source_identity != state.source_identity
            or broker.session_fingerprint != state.session_fingerprint
            or broker.state_revision != state.revision
        ):
            return None
        return state

    def _load(
        self, owner_id: UUID, source_identity: SourceIdentity
    ) -> RuntimeState | None:
        try:
            state = self._state_store.load(owner_id, source_identity)
        except Exception:
            return None
        if (
            not isinstance(state, RuntimeState)
            or state.owner_id != owner_id
            or state.source_identity != source_identity
        ):
            return None
        return state

    def _commit(
        self,
        old_state: RuntimeState,
        next_state: RuntimeState,
        reservation: OrderWriteReservation,
    ) -> ReservationResult | None:
        try:
            if self._state_store.compare_and_swap(old_state.revision, next_state):
                return ReservationResult(
                    next_state,
                    reservation,
                    InProcessWritePermit(reservation, _seal=_PERMIT_SEAL),
                )
        except Exception:
            pass
        return None


def validate_order_write_reservation(
    state: RuntimeState, reservation: OrderWriteReservation
) -> bool:
    """Pure adapter gate for the exact state/token produced by one CAS."""

    if not isinstance(state, RuntimeState) or not isinstance(
        reservation, OrderWriteReservation
    ):
        return False
    if (
        state.revision != reservation.reserved_revision
        or state.owner_id != reservation.owner_id
        or state.source_identity != reservation.source_identity
        or state.account_fingerprint != reservation.account_fingerprint
        or state.session_fingerprint != reservation.session_fingerprint
        or reservation not in state.write_reservations
        or reservation.status is not OrderWriteStatus.MAY_HAVE_OCCURRED
    ):
        return False
    intent = next(
        (item for item in state.intents if item.intent_id == reservation.intent_id),
        None,
    )
    return (
        intent is not None
        and intent.ref_id == reservation.ref_id
        and intent.terms_digest == reservation.terms_digest
        and (
            intent.lifecycle is IntentLifecycle.MAY_HAVE_OCCURRED
            if reservation.action is OrderWriteAction.PLACE
            else intent.lifecycle is IntentLifecycle.RECONCILED
        )
    )


def apply_broker_order_facts(
    state: RuntimeState,
    facts: tuple[BrokerOrderFact, ...],
    *,
    as_of: datetime,
) -> RuntimeState:
    """Return a same-revision state with only unique exact factual updates."""

    if not isinstance(state, RuntimeState):
        raise TypeError("state must be RuntimeState")
    if not isinstance(facts, tuple) or not all(
        isinstance(item, BrokerOrderFact) for item in facts
    ):
        raise TypeError("facts must be a tuple of BrokerOrderFact values")
    matched: list[tuple[LogicalOrderIntent, BrokerOrderFact]] = []
    for fact in facts:
        intent = _match_order_fact(state, fact)
        if intent is None:
            continue
        if not _fact_matches_intent(fact, intent, state) or not _fresh(
            fact.observed_at, as_of
        ):
            continue
        if intent.lifecycle not in (
            IntentLifecycle.APPROVAL_REQUIRED,
            IntentLifecycle.MAY_HAVE_OCCURRED,
            IntentLifecycle.UNKNOWN,
            IntentLifecycle.RECONCILED,
        ):
            continue
        matched.append((intent, fact))
    intent_counts: dict[UUID, int] = {}
    provider_owners: dict[str, UUID] = {}
    for intent, _ in matched:
        intent_counts[intent.intent_id] = intent_counts.get(intent.intent_id, 0) + 1
    for intent, fact in matched:
        prior_owner = provider_owners.get(fact.provider_order_id)
        if prior_owner is not None and prior_owner != intent.intent_id:
            raise OrderTrackerError("one provider order ID maps to multiple intents")
        provider_owners[fact.provider_order_id] = intent.intent_id
    if any(count > 1 for count in intent_counts.values()):
        raise OrderTrackerError("multiple broker rows match one logical intent")
    tracked_by_intent = {item.intent_id: item for item in state.tracked_orders}
    tracks = list(state.tracked_orders)
    reservations = list(state.write_reservations)
    intents = list(state.intents)
    receipts = list(state.approval_receipts)
    for intent, fact in matched:
        prior = tracked_by_intent.get(intent.intent_id)
        if prior is not None and _same_order_evidence(prior.last_fact, fact):
            continue
        if prior is not None and not _fact_progresses(prior.last_fact, fact):
            raise OrderTrackerError("broker order fact regressed")
        approval_receipts = tuple(
            item
            for item in state.approval_receipts
            if item.intent_id == intent.intent_id
        )
        if len(approval_receipts) > 1:
            raise OrderTrackerError("logical intent has conflicting approval IDs")
        approval_id = (
            approval_receipts[0].approval_id
            if approval_receipts
            else (prior.approval_id if prior is not None else None)
        )
        if _identifier_collision(state, fact, approval_id, intent.intent_id):
            raise OrderTrackerError("broker order identifiers collide with durable IDs")
        updated = TrackedOrder(
            intent_id=intent.intent_id,
            ref_id=intent.ref_id,
            approval_id=approval_id,
            provider_order_id=fact.provider_order_id,
            last_fact=fact,
        )
        if prior is None:
            tracks.append(updated)
        else:
            tracks[tracks.index(prior)] = updated
        if intent.lifecycle is IntentLifecycle.APPROVAL_REQUIRED:
            intents[intents.index(intent)] = replace(
                intent, lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED
            )
            receipts = [
                receipt for receipt in receipts if receipt.intent_id != intent.intent_id
            ]
        reservations = [
            _reservation_status_after_fact(item, fact)
            if item.intent_id == intent.intent_id
            else item
            for item in reservations
        ]
    return replace(
        state,
        intents=tuple(intents),
        approval_receipts=tuple(receipts),
        tracked_orders=tuple(tracks),
        write_reservations=tuple(reservations),
    )


def _reservation(
    *,
    action: OrderWriteAction,
    state: RuntimeState,
    intent: LogicalOrderIntent,
    review: BrokerReviewFacts | None,
    approval_id: str | None,
    target_provider_order_id: str | None,
) -> OrderWriteReservation:
    return OrderWriteReservation(
        operation_id=_operation_id(
            action=action,
            owner_id=state.owner_id,
            source_identity=state.source_identity,
            intent_id=intent.intent_id,
            ref_id=intent.ref_id,
            expected_revision=state.revision,
            target_provider_order_id=target_provider_order_id,
        ),
        action=action,
        intent_id=intent.intent_id,
        ref_id=intent.ref_id,
        terms_digest=intent.terms_digest,
        owner_id=state.owner_id,
        source_identity=state.source_identity,
        account_fingerprint=state.account_fingerprint,
        session_fingerprint=state.session_fingerprint,
        expected_revision=state.revision,
        reserved_revision=state.revision + 1,
        review_revision=None if review is None else review.state_revision,
        review=review,
        approval_id=approval_id,
        target_provider_order_id=target_provider_order_id,
    )


def _operation_id(
    *,
    action: OrderWriteAction,
    owner_id: UUID,
    source_identity: SourceIdentity,
    intent_id: UUID,
    ref_id: str,
    expected_revision: int,
    target_provider_order_id: str | None,
) -> UUID:
    material = "\n".join(
        (
            "arch148-order-write-reservation/v1",
            action.value,
            owner_id.hex,
            source_identity.head,
            source_identity.tree,
            intent_id.hex,
            ref_id,
            str(expected_revision),
            target_provider_order_id or "none",
        )
    )
    return uuid5(_OPERATION_NAMESPACE, material)


def _exhaustive_current_snapshot(
    broker: BrokerSnapshot, state: RuntimeState, as_of: datetime
) -> bool:
    return (
        broker.account.active
        and broker.account.agentic_allowed
        and broker.account.fingerprint == state.account_fingerprint
        and _fresh(broker.observed_at, as_of)
        and _fresh(broker.account.observed_at, as_of)
        and broker.position_scope.all_agents
        and broker.position_scope.exhausted
        and broker.order_scope.all_agents
        and broker.order_scope.exhausted
        and broker.position_scope.account_fingerprint == state.account_fingerprint
        and broker.order_scope.account_fingerprint == state.account_fingerprint
        and broker.position_scope.symbols in (None, (TQQQ, SQQQ))
        and broker.order_scope.symbols in (None, (TQQQ, SQQQ))
        and _fresh(broker.position_scope.observed_at, as_of)
        and _fresh(broker.order_scope.observed_at, as_of)
        and broker.approvals.exhaustive
        and broker.approvals.account_fingerprint == state.account_fingerprint
        and broker.approvals.source_identity == state.source_identity
        and broker.approvals.session_fingerprint == state.session_fingerprint
        and broker.approvals.state_revision == state.revision
        and _fresh(broker.approvals.observed_at, as_of)
        and broker.approvals.setting_enabled is not None
        and not broker.approvals.unresolved_refs
        and all(
            request.account_fingerprint == state.account_fingerprint
            and request.source_identity == state.source_identity
            and request.session_fingerprint == state.session_fingerprint
            and request.state_revision == state.revision
            and _fresh(request.observed_at, as_of)
            for request in broker.approvals.requests
        )
    )


def _intent_snapshot_safe(
    state: RuntimeState,
    intent: LogicalOrderIntent,
    broker: BrokerSnapshot,
    as_of: datetime,
) -> bool:
    facts = broker.tradability.get(intent.symbol)
    if (
        facts is None
        or not _fresh(facts.observed_at, as_of)
        or facts.active is not True
        or facts.halted is not False
        or facts.regular_session_eligible is not True
    ):
        return False
    quantity_is_fractional = intent.quantity != intent.quantity.to_integral_value()
    if intent.kind is IntentKind.ENTRY:
        if facts.fractional_entry_supported is not True and quantity_is_fractional:
            return False
        if (
            facts.stop_market_supported is not True
            or facts.exact_stop_price_supported is not True
            or (quantity_is_fractional and facts.fractional_stop_supported is not True)
            or state.positions
            or any(symbol in broker.positions for symbol in TRADED_SYMBOLS)
            or any(symbol in broker.position_owners for symbol in TRADED_SYMBOLS)
            or any(
                order.symbol in TRADED_SYMBOLS and not order.state.terminal
                for order in broker.orders
            )
        ):
            return False
    else:
        position_record = state.positions.get(intent.symbol)
        position = broker.positions.get(intent.symbol)
        if (
            position_record is None
            or len(state.positions) != 1
            or position is None
            or position.quantity != position_record.quantity
            or position.average_cost != position_record.average_entry_fill
            or broker.position_owners.get(intent.symbol)
            != position_record.entry_intent_id
            or any(
                symbol in broker.positions
                for symbol in TRADED_SYMBOLS
                if symbol != intent.symbol
            )
            or any(
                symbol in broker.position_owners
                for symbol in TRADED_SYMBOLS
                if symbol != intent.symbol
            )
            or any(
                order.symbol in TRADED_SYMBOLS and not order.state.terminal
                for order in broker.orders
            )
        ):
            return False
        if intent.kind is IntentKind.PROTECTIVE_STOP and (
            facts.stop_market_supported is not True
            or facts.exact_stop_price_supported is not True
            or (quantity_is_fractional and facts.fractional_stop_supported is not True)
            or position_record.stop_intent_id not in (None, intent.intent_id)
        ):
            return False
    return True


def _is_exact_settled_history_fact(
    state: RuntimeState,
    fact: BrokerOrderFact,
    as_of: datetime,
) -> bool:
    if not fact.state.terminal or not _fresh(fact.observed_at, as_of):
        return False
    matches = tuple(
        (intent, tracked)
        for intent in state.intents
        for tracked in state.tracked_orders
        if tracked.intent_id == intent.intent_id
        and tracked.provider_order_id == fact.provider_order_id
    )
    if len(matches) != 1:
        return False
    intent, tracked = matches[0]
    if (
        intent.lifecycle not in (IntentLifecycle.RECONCILED, IntentLifecycle.REJECTED)
        or tracked.ref_id != intent.ref_id
        or tracked.last_fact is None
        or not _fact_matches_intent(fact, intent, state)
        or not _same_bound_order_evidence(tracked.last_fact, fact, intent, state)
    ):
        return False
    if fact.state is OrderState.FILLED and (
        fact.filled_quantity != intent.quantity
        or fact.remaining_quantity != 0
        or fact.average_fill_price is None
    ):
        return False
    if intent.lifecycle is IntentLifecycle.REJECTED and (
        fact.state is not OrderState.REJECTED
        or fact.filled_quantity != 0
        or fact.remaining_quantity != intent.quantity
    ):
        return False
    relevant_reservations = tuple(
        reservation
        for reservation in state.write_reservations
        if reservation.intent_id == intent.intent_id
        or reservation.target_provider_order_id == fact.provider_order_id
    )
    return all(
        reservation.status is OrderWriteStatus.TERMINAL
        for reservation in relevant_reservations
    )


def _is_exact_pending_canceled_stop(
    state: RuntimeState,
    exit_intent: LogicalOrderIntent,
    fact: BrokerOrderFact,
    as_of: datetime,
) -> bool:
    pending = state.pending_exit
    if (
        pending is None
        or pending.exit_intent_id != exit_intent.intent_id
        or exit_intent.kind is not IntentKind.EXIT
        or exit_intent.side is not OrderSide.SELL
        or exit_intent.symbol != pending.symbol
    ):
        return False
    stop = next(
        (item for item in state.intents if item.intent_id == pending.stop_intent_id),
        None,
    )
    tracked = next(
        (
            item
            for item in state.tracked_orders
            if item.intent_id == pending.stop_intent_id
        ),
        None,
    )
    position = state.positions.get(pending.symbol)
    if (
        stop is None
        or stop.kind is not IntentKind.PROTECTIVE_STOP
        or stop.symbol != pending.symbol
        or stop.side is not OrderSide.SELL
        or tracked is None
        or tracked.provider_order_id != pending.stop_provider_order_id
        or tracked.last_fact is None
        or tracked.last_fact.state not in (OrderState.CANCELED, OrderState.REJECTED)
        or position is None
        or position.stop_intent_id is not None
        or fact.provider_order_id != pending.stop_provider_order_id
        or fact.account_fingerprint != state.account_fingerprint
        or fact.source_identity not in (None, state.source_identity)
        or fact.intent_id not in (None, stop.intent_id)
        or fact.ref_id not in (None, stop.ref_id)
        or fact.kind is not IntentKind.PROTECTIVE_STOP
        or fact.symbol != pending.symbol
        or fact.side is not OrderSide.SELL
        or fact.state not in (OrderState.CANCELED, OrderState.REJECTED)
        or fact.requested_quantity != stop.quantity
        or fact.stop_price != stop.stop_price
        or not decimal_sum_equals(
            fact.filled_quantity, fact.remaining_quantity, fact.requested_quantity
        )
        or fact.remaining_quantity != position.quantity
        or not _fresh(fact.observed_at, as_of)
    ):
        return False
    return _same_bound_order_evidence(tracked.last_fact, fact, stop, state)


def _is_exact_reconciled_entry_predecessor(
    state: RuntimeState,
    new_intent: LogicalOrderIntent,
    fact: BrokerOrderFact,
    broker: BrokerSnapshot,
    as_of: datetime,
) -> bool:
    if (
        new_intent.kind not in (IntentKind.PROTECTIVE_STOP, IntentKind.EXIT)
        or new_intent.side is not OrderSide.SELL
    ):
        return False
    record = state.positions.get(new_intent.symbol)
    if record is None:
        return False
    if new_intent.kind is IntentKind.PROTECTIVE_STOP:
        if state.pending_exit is not None or record.stop_intent_id not in (
            None,
            new_intent.intent_id,
        ):
            return False
    elif (
        state.pending_exit is None
        or state.pending_exit.exit_intent_id != new_intent.intent_id
        or state.pending_exit.symbol != new_intent.symbol
        or record.stop_intent_id is not None
    ):
        return False
    entry = next(
        (item for item in state.intents if item.intent_id == record.entry_intent_id),
        None,
    )
    tracked = next(
        (
            item
            for item in state.tracked_orders
            if item.intent_id == record.entry_intent_id
        ),
        None,
    )
    position = broker.positions.get(record.symbol)
    return (
        entry is not None
        and entry.kind is IntentKind.ENTRY
        and entry.lifecycle is IntentLifecycle.RECONCILED
        and entry.symbol == new_intent.symbol
        and entry.owner_id == state.owner_id
        and entry.source_identity == state.source_identity
        and tracked is not None
        and tracked.ref_id == entry.ref_id
        and tracked.provider_order_id == fact.provider_order_id
        and tracked.last_fact is not None
        and tracked.last_fact.state is OrderState.FILLED
        and position is not None
        and position.quantity == record.quantity
        and position.average_cost == record.average_entry_fill
        and broker.position_owners.get(record.symbol) == record.entry_intent_id
        and fact.state is OrderState.FILLED
        and fact.filled_quantity == entry.quantity
        and fact.remaining_quantity == 0
        and fact.average_fill_price == record.average_entry_fill
        and _fact_matches_intent(fact, entry, state)
        and _same_bound_order_evidence(tracked.last_fact, fact, entry, state)
        and _fresh(fact.observed_at, as_of)
    )


def _fresh(observed_at: datetime, as_of: datetime) -> bool:
    try:
        if (
            not isinstance(observed_at, datetime)
            or observed_at.tzinfo is None
            or observed_at.utcoffset() is None
            or not isinstance(as_of, datetime)
            or as_of.tzinfo is None
            or as_of.utcoffset() is None
        ):
            return False
        current = as_of.astimezone(UTC)
        observed = observed_at.astimezone(UTC)
        return observed <= current and current - observed <= _MAX_FACT_AGE
    except (AttributeError, OverflowError, TypeError, ValueError):
        return False


def _fresh_with_max_age(
    observed_at: datetime, as_of: datetime, maximum_age: timedelta
) -> bool:
    if not _fresh(observed_at, as_of):
        return False
    try:
        return as_of.astimezone(UTC) - observed_at.astimezone(UTC) <= maximum_age
    except (AttributeError, OverflowError, TypeError, ValueError):
        return False


def _fact_matches_intent(
    fact: BrokerOrderFact, intent: LogicalOrderIntent, state: RuntimeState
) -> bool:
    return (
        fact.account_fingerprint == state.account_fingerprint
        and fact.source_identity in (None, state.source_identity)
        and fact.intent_id in (None, intent.intent_id)
        and fact.ref_id in (None, intent.ref_id)
        and fact.kind is intent.kind
        and fact.symbol == intent.symbol
        and fact.side is intent.side
        and fact.requested_quantity == intent.quantity
        and fact.stop_price == intent.stop_price
        and decimal_sum_equals(
            fact.filled_quantity, fact.remaining_quantity, fact.requested_quantity
        )
    )


def _fact_progresses(
    previous: BrokerOrderFact | None, current: BrokerOrderFact
) -> bool:
    if previous is None:
        return True
    if (
        previous.provider_order_id != current.provider_order_id
        or previous.account_fingerprint != current.account_fingerprint
        or (
            previous.source_identity is not None
            and current.source_identity not in (None, previous.source_identity)
        )
        or (
            previous.intent_id is not None
            and current.intent_id not in (None, previous.intent_id)
        )
        or (
            previous.ref_id is not None
            and current.ref_id not in (None, previous.ref_id)
        )
        or previous.kind is not current.kind
        or previous.symbol != current.symbol
        or previous.side is not current.side
        or previous.requested_quantity != current.requested_quantity
        or previous.stop_price != current.stop_price
        or current.filled_quantity < previous.filled_quantity
        or current.remaining_quantity > previous.remaining_quantity
        or current.observed_at < previous.observed_at
    ):
        return False
    if previous.state is OrderState.FILLED and current != previous:
        return False
    if previous.state.terminal and current.state is not previous.state:
        return False
    if previous.state is not OrderState.UNKNOWN and current.state is OrderState.UNKNOWN:
        return False
    if (
        previous.state is OrderState.PARTIALLY_FILLED
        and current.state is OrderState.OPEN
    ):
        return False
    if previous.state is OrderState.PENDING_CANCEL and current.state is OrderState.OPEN:
        return False
    return True


def _same_order_evidence(
    previous: BrokerOrderFact | None, current: BrokerOrderFact
) -> bool:
    if previous is None:
        return False
    return replace(previous, observed_at=current.observed_at) == current


def _same_bound_order_evidence(
    previous: BrokerOrderFact | None,
    current: BrokerOrderFact,
    intent: LogicalOrderIntent,
    state: RuntimeState,
) -> bool:
    if previous is None:
        return False
    for fact in (previous, current):
        if (
            fact.provider_order_id != current.provider_order_id
            or fact.account_fingerprint != state.account_fingerprint
            or fact.source_identity not in (None, state.source_identity)
            or fact.intent_id not in (None, intent.intent_id)
            or fact.ref_id not in (None, intent.ref_id)
        ):
            return False
    return (
        replace(
            previous,
            observed_at=current.observed_at,
            source_identity=current.source_identity,
            intent_id=current.intent_id,
            ref_id=current.ref_id,
        )
        == current
    )


def same_order_evidence(
    previous: BrokerOrderFact | None, current: BrokerOrderFact
) -> bool:
    """Compare all broker order facts while permitting a refreshed timestamp."""

    return _same_order_evidence(previous, current)


def _match_order_fact(
    state: RuntimeState, fact: BrokerOrderFact
) -> LogicalOrderIntent | None:
    if fact.ref_id is None and fact.intent_id is None:
        tracked = tuple(
            item
            for item in state.tracked_orders
            if item.provider_order_id == fact.provider_order_id
        )
        if len(tracked) != 1:
            return None
        return next(
            (item for item in state.intents if item.intent_id == tracked[0].intent_id),
            None,
        )
    matches = tuple(
        item
        for item in state.intents
        if (fact.ref_id is None or item.ref_id == fact.ref_id)
        and (fact.intent_id is None or item.intent_id == fact.intent_id)
    )
    return matches[0] if len(matches) == 1 else None


def _known_provider_ids(state: RuntimeState) -> set[str]:
    return {
        tracked.provider_order_id
        for tracked in state.tracked_orders
        if tracked.provider_order_id is not None
    }


def _known_external_ids(state: RuntimeState) -> set[str]:
    identifiers = _known_provider_ids(state)
    identifiers.update(str(intent.intent_id) for intent in state.intents)
    identifiers.update(intent.ref_id for intent in state.intents)
    identifiers.update(
        tracked.approval_id
        for tracked in state.tracked_orders
        if tracked.approval_id is not None
    )
    identifiers.update(receipt.approval_id for receipt in state.approval_receipts)
    identifiers.update(str(item.operation_id) for item in state.write_reservations)
    return identifiers


def _identifier_collision(
    state: RuntimeState,
    fact: BrokerOrderFact,
    approval_id: str | None,
    local_intent_id: UUID,
) -> bool:
    if fact.provider_order_id in {str(item.intent_id) for item in state.intents} | {
        item.ref_id for item in state.intents
    }:
        return True
    if approval_id is not None and approval_id in {
        str(item.intent_id) for item in state.intents
    } | {item.ref_id for item in state.intents}:
        return True
    for tracked in state.tracked_orders:
        if (
            tracked.provider_order_id == fact.provider_order_id
            and tracked.intent_id != local_intent_id
        ):
            return True
        if (
            approval_id is not None
            and tracked.approval_id == approval_id
            and tracked.intent_id != local_intent_id
        ):
            return True
        if approval_id is not None and tracked.provider_order_id == approval_id:
            return True
        if tracked.approval_id == fact.provider_order_id:
            return True
    return any(
        str(reservation.operation_id) in (fact.provider_order_id, approval_id)
        for reservation in state.write_reservations
    )


def _reservation_status_after_fact(
    reservation: OrderWriteReservation, fact: BrokerOrderFact
) -> OrderWriteReservation:
    if reservation.action is OrderWriteAction.PLACE:
        status = (
            OrderWriteStatus.TERMINAL
            if fact.state.terminal
            else OrderWriteStatus.OBSERVED
        )
    elif reservation.target_provider_order_id == fact.provider_order_id:
        if fact.state.terminal:
            status = OrderWriteStatus.TERMINAL
        elif fact.state is OrderState.PENDING_CANCEL:
            status = OrderWriteStatus.OBSERVED
        else:
            return reservation
    else:
        return reservation
    return replace(reservation, status=status)
