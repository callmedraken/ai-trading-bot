"""Injected Architecture 148 runtime composition and single-effect cycle path."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID

from trading_bot.live_prototype.contracts import (
    Command,
    PrototypeCommandResult,
    PrototypeSnapshot,
    Reason,
    RestrictedLiveStatus,
)
from trading_bot.live_prototype.l43_runtime import L43SerializedLifecycleInterlock
from trading_bot.live_runtime.application import (
    CycleApplicationService,
    CycleRequest,
    ReconciliationOutcome,
    ReconciliationRequest,
    validate_protective_stop_cancel_candidate,
)
from trading_bot.live_runtime.gui_adapter import (
    Arch148GuiAdapter,
    Arch148RuntimeDisplayCache,
    Arch148RuntimeDisplayFacts,
    create_arch148_window,
)
from trading_bot.live_runtime.models import (
    SQQQ,
    TQQQ,
    AdmissionBlocker,
    BrokerReviewFacts,
    BrokerSnapshot,
    CycleResult,
    ExecutionProfile,
    IntentKind,
    IntentLifecycle,
    LogicalOrderIntent,
    MarketSnapshot,
    MarketSnapshotProvider,
    ProtectiveStopCancelCandidate,
    RuntimeState,
    RuntimeStateStore,
    SourceIdentity,
    TargetPosition,
)
from trading_bot.live_runtime.order_tracker import (
    InProcessWritePermit,
    OrderTracker,
    OrderWriteReservation,
    ReservationResult,
)
from trading_bot.live_runtime.strategy import (
    HardStopPolicy,
    confirmed_regime_exit,
    session_decision,
)
from trading_bot.live_runtime.worker import (
    Arch148RuntimeWorker,
    Clock,
    KillControl,
    OwnerLeaseFactory,
    RuntimeWorkerSession,
)

_SETTLEMENT_LIMIT = 4
_FACT_MAX_AGE = timedelta(seconds=30)
_BAR_MAX_AGE = timedelta(minutes=5)
_PRICE_MAX_AGE = timedelta(seconds=15)


class BrokerAdapter(Protocol):
    """Injected factual/review/write adapter; never constructed by default."""

    def read_snapshot(self, as_of: datetime, state: RuntimeState) -> BrokerSnapshot: ...

    def review_order(
        self,
        intent: LogicalOrderIntent,
        broker: BrokerSnapshot,
        *,
        observed_at: datetime,
    ) -> BrokerReviewFacts: ...

    def place_order(
        self,
        *,
        state: RuntimeState,
        reservation: OrderWriteReservation,
        permit: InProcessWritePermit,
        broker: BrokerSnapshot,
        observed_at: datetime,
    ) -> object: ...

    def cancel_order(
        self,
        *,
        state: RuntimeState,
        reservation: OrderWriteReservation,
        permit: InProcessWritePermit,
        broker: BrokerSnapshot,
        observed_at: datetime,
    ) -> object: ...


class LifecycleOwnerJournal(Protocol):
    """Existing opt-in local lifecycle lock used to exclude another worker."""

    def acquire(self) -> None: ...

    def release(self) -> None: ...


def lifecycle_journal_owner_lease(journal: LifecycleOwnerJournal) -> OwnerLeaseFactory:
    """Adapt the existing journal lock to worker ownership without repair.

    A failed acquire propagates unchanged. In particular, a stale lock left by a
    prior crash is not removed or reinterpreted by this adapter.
    """

    if not callable(getattr(journal, "acquire", None)) or not callable(
        getattr(journal, "release", None)
    ):
        raise TypeError("journal must implement acquire and release")

    @contextmanager
    def own() -> Iterator[bool]:
        journal.acquire()
        try:
            yield True
        finally:
            journal.release()

    return own


class OrderEffectAuthority(Protocol):
    """Explicit injected gate; no default service grants order-write authority."""

    def allows_place(
        self,
        intent: LogicalOrderIntent,
        *,
        state: RuntimeState,
        result: CycleResult,
        broker: BrokerSnapshot,
    ) -> bool: ...


class CancelEffectAuthority(Protocol):
    """Separate explicit gate for a policy-produced exact stop cancellation."""

    def allows_cancel(
        self,
        candidate: ProtectiveStopCancelCandidate,
        *,
        state: RuntimeState,
        result: CycleResult,
        broker: BrokerSnapshot,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class Arch148RuntimeBindings:
    """Context-owned per-run dependencies supplied by desktop composition."""

    owner_id: UUID
    source_identity: SourceIdentity
    session_fingerprint: str
    application: CycleApplicationService
    state_store: RuntimeStateStore
    order_tracker: OrderTracker
    market_provider: MarketSnapshotProvider
    broker_adapter: BrokerAdapter
    clock: Clock
    execution_profile: ExecutionProfile = ExecutionProfile.FRACTIONAL_RESEARCH_PAPER

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, UUID):
            raise TypeError("owner_id must be UUID")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("source_identity must be SourceIdentity")
        if (
            not isinstance(self.session_fingerprint, str)
            or not self.session_fingerprint
        ):
            raise ValueError("session_fingerprint must be nonblank")
        if not callable(getattr(self.application, "run_cycle", None)) or not callable(
            getattr(self.application, "reconcile_only", None)
        ):
            raise TypeError("application must plan and reconcile supplied facts")
        if not callable(getattr(self.state_store, "load", None)) or not callable(
            getattr(self.state_store, "compare_and_swap", None)
        ):
            raise TypeError("state_store must support load and compare_and_swap")
        if not isinstance(self.order_tracker, OrderTracker):
            raise TypeError("order_tracker must be OrderTracker")
        if self.application.state_store is not self.state_store:
            raise ValueError("application and bindings must share one state store")
        if self.order_tracker.state_store is not self.state_store:
            raise ValueError("tracker and bindings must share one state store")
        if not callable(getattr(self.market_provider, "read_snapshot", None)):
            raise TypeError("market_provider must implement read_snapshot")
        if not all(
            callable(getattr(self.broker_adapter, name, None))
            for name in (
                "read_snapshot",
                "review_order",
                "place_order",
                "cancel_order",
            )
        ):
            raise TypeError("broker_adapter lacks the required injected methods")
        if not callable(self.clock):
            raise TypeError("clock must be callable")
        if not isinstance(self.execution_profile, ExecutionProfile):
            raise TypeError("execution_profile must be an ExecutionProfile")


BindingsFactory = Callable[[], AbstractContextManager[Arch148RuntimeBindings]]


class Arch148RuntimeBlocked(RuntimeError):
    """Safe startup/cycle blocker that carries only a sanitized reason code."""

    def __init__(self, code: str) -> None:
        if (
            not isinstance(code, str)
            or not code
            or len(code) > 96
            or any(
                character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
                for character in code
            )
        ):
            raise ValueError("blocked reason must be a sanitized code")
        self.code = code
        super().__init__(code)


class RuntimeCycleBlocker(StrEnum):
    NO_ACTION = "NO_ACTION"
    PLANNER_BLOCKED = "PLANNER_BLOCKED"
    AUTHORITY_MISSING = "AUTHORITY_MISSING"
    REVIEW_BLOCKED = "REVIEW_BLOCKED"
    PLAN_CHANGED = "PLAN_CHANGED"
    PROPOSAL_BINDING_FAILED = "PROPOSAL_BINDING_FAILED"
    BROKER_FACTS_STALE = "BROKER_FACTS_STALE"
    RESERVATION_UNAVAILABLE = "RESERVATION_UNAVAILABLE"
    LIFECYCLE_STOPPED = "LIFECYCLE_STOPPED"
    RECONCILIATION_ADVANCED = "RECONCILIATION_ADVANCED"
    EFFECT_OUTCOME_UNKNOWN = "EFFECT_OUTCOME_UNKNOWN"
    CANCEL_AUTHORITY_MISSING = "CANCEL_AUTHORITY_MISSING"
    EXECUTION_PROFILE_BLOCKED = "EXECUTION_PROFILE_BLOCKED"


@dataclass(frozen=True, slots=True)
class Arch148CycleOutcome:
    result: CycleResult | None
    blocker: RuntimeCycleBlocker | None
    effect_status: str | None = None


class Arch148RuntimeService:
    """Desktop service with injected session, owner lease, and default-deny writes."""

    def __init__(
        self,
        bindings_factory: BindingsFactory,
        *,
        owner_lease_factory: OwnerLeaseFactory,
        cadence: timedelta,
        effect_authority: OrderEffectAuthority | None = None,
        cancel_effect_authority: CancelEffectAuthority | None = None,
        kill_control: KillControl | None = None,
        display_cache: Arch148RuntimeDisplayCache | None = None,
        worker_clock: Clock | None = None,
    ) -> None:
        if not callable(bindings_factory):
            raise TypeError("bindings_factory must be callable")
        if effect_authority is not None and not callable(
            getattr(effect_authority, "allows_place", None)
        ):
            raise TypeError("effect_authority must implement allows_place")
        if cancel_effect_authority is not None and not callable(
            getattr(cancel_effect_authority, "allows_cancel", None)
        ):
            raise TypeError("cancel_effect_authority must implement allows_cancel")
        self._bindings_factory = bindings_factory
        self._effect_authority = effect_authority
        self._cancel_effect_authority = cancel_effect_authority
        self._display_cache = display_cache or Arch148RuntimeDisplayCache()
        self._worker = Arch148RuntimeWorker(
            self._make_session,
            owner_lease_factory=owner_lease_factory,
            cadence=cadence,
            kill_control=kill_control,
            clock=worker_clock,
        )
        self._gui_adapter = Arch148GuiAdapter(self._worker, self._display_cache.read)

    def snapshot(self) -> PrototypeSnapshot:
        return self._gui_adapter.snapshot()

    def submit(self, command: Command) -> PrototypeCommandResult:
        return self._gui_adapter.submit(command)

    def display_details(self) -> tuple[str, ...]:
        return self._gui_adapter.display_details()

    def request_report(self, path: Path) -> bool:
        return self._gui_adapter.request_report(path)

    def shutdown_complete(self) -> bool:
        return self._gui_adapter.shutdown_complete()

    def create_window(self) -> object:
        """Explicitly construct the existing desktop window for this service."""

        return create_arch148_window(self)

    def wait(self, timeout: float | None = None) -> bool:
        return self._worker.wait(timeout)

    def _make_session(self) -> AbstractContextManager[RuntimeWorkerSession]:
        return _service_session_context(
            self._bindings_factory,
            self._display_cache,
            self._effect_authority,
            self._cancel_effect_authority,
        )


@contextmanager
def _service_session_context(
    bindings_factory: BindingsFactory,
    display_cache: Arch148RuntimeDisplayCache,
    effect_authority: OrderEffectAuthority | None,
    cancel_effect_authority: CancelEffectAuthority | None,
) -> Iterator[RuntimeWorkerSession]:
    with bindings_factory() as bindings:
        if not isinstance(bindings, Arch148RuntimeBindings):
            raise TypeError("bindings_factory must yield Arch148RuntimeBindings")
        yield _Arch148WorkerSession(
            bindings, display_cache, effect_authority, cancel_effect_authority
        )


class _Arch148WorkerSession(RuntimeWorkerSession):
    def __init__(
        self,
        bindings: Arch148RuntimeBindings,
        display_cache: Arch148RuntimeDisplayCache,
        effect_authority: OrderEffectAuthority | None,
        cancel_effect_authority: CancelEffectAuthority | None,
    ) -> None:
        self._bindings = bindings
        self._display_cache = display_cache
        self._effect_authority = effect_authority
        self._cancel_effect_authority = cancel_effect_authority
        self._last_state: RuntimeState | None = None
        self._last_broker: BrokerSnapshot | None = None
        self._last_market: MarketSnapshot | None = None
        self._last_result: CycleResult | None = None
        self._last_effect: str | None = None
        self._skip_next_cycle = False

    def startup_reconcile(
        self,
        stop_event: threading.Event,
        lifecycle_interlock: L43SerializedLifecycleInterlock,
    ) -> None:
        del lifecycle_interlock
        if stop_event.is_set():
            return
        state, broker, settled_exit, _ = self._reconcile_until_stable()
        self._last_state = state
        self._last_broker = broker
        self._skip_next_cycle = settled_exit
        self._publish("STARTUP_RECONCILED", ())

    def run_cycle(
        self,
        stop_event: threading.Event,
        lifecycle_interlock: L43SerializedLifecycleInterlock,
    ) -> Arch148CycleOutcome:
        if stop_event.is_set():
            return Arch148CycleOutcome(None, RuntimeCycleBlocker.LIFECYCLE_STOPPED)
        if self._skip_next_cycle:
            self._skip_next_cycle = False
            self._publish("EXIT_SETTLED_WAIT", ())
            return Arch148CycleOutcome(
                None, RuntimeCycleBlocker.RECONCILIATION_ADVANCED
            )
        state, broker, settled_exit, as_of = self._reconcile_until_stable()
        self._last_state = state
        self._last_broker = broker
        if stop_event.is_set():
            self._publish("STOP_REQUESTED", ())
            return Arch148CycleOutcome(None, RuntimeCycleBlocker.LIFECYCLE_STOPPED)
        if settled_exit:
            self._publish("EXIT_SETTLED_WAIT", ())
            return Arch148CycleOutcome(
                None, RuntimeCycleBlocker.RECONCILIATION_ADVANCED
            )
        market = self._bindings.market_provider.read_snapshot(as_of)
        if not isinstance(market, MarketSnapshot):
            raise Arch148RuntimeBlocked("MARKET_SNAPSHOT_UNAVAILABLE")
        if market.as_of != as_of:
            raise Arch148RuntimeBlocked("MARKET_AS_OF_MISMATCH")
        request = CycleRequest(
            as_of,
            self._bindings.owner_id,
            self._bindings.source_identity,
            self._bindings.session_fingerprint,
            state.revision,
            market,
            broker,
            execution_profile=self._bindings.execution_profile,
        )
        candidate_result = self._bindings.application.run_cycle(request)
        if not isinstance(candidate_result, CycleResult):
            raise Arch148RuntimeBlocked("PLANNER_RESULT_UNAVAILABLE")
        self._last_state = self._load_state()
        self._last_market = market
        self._last_broker = broker
        self._last_result = candidate_result
        self._last_effect = None
        if stop_event.is_set():
            self._publish("STOP_REQUESTED", candidate_result.status.blockers)
            return Arch148CycleOutcome(
                candidate_result, RuntimeCycleBlocker.LIFECYCLE_STOPPED
            )
        if candidate_result.cancel_candidate is not None:
            return self._cancel_protective_stop(
                candidate_result.cancel_candidate,
                candidate_result,
                market=market,
                planned_as_of=as_of,
                stop_event=stop_event,
                lifecycle_interlock=lifecycle_interlock,
            )
        candidate = candidate_result.intent
        if candidate is None or not _reviewable(candidate_result, candidate):
            self._publish("RUNNING", candidate_result.status.blockers)
            blocker = (
                RuntimeCycleBlocker.NO_ACTION
                if candidate is None and not candidate_result.status.blockers
                else RuntimeCycleBlocker.PLANNER_BLOCKED
            )
            return Arch148CycleOutcome(candidate_result, blocker)
        if (
            self._bindings.execution_profile
            is not ExecutionProfile.PROTECTED_WHOLE_SHARE
        ):
            self._publish("EXECUTION_PROFILE_BLOCKED", candidate_result.status.blockers)
            return Arch148CycleOutcome(
                candidate_result, RuntimeCycleBlocker.EXECUTION_PROFILE_BLOCKED
            )
        if self._effect_authority is None:
            self._publish("AUTHORIZATION_MISSING", candidate_result.status.blockers)
            return Arch148CycleOutcome(
                candidate_result, RuntimeCycleBlocker.AUTHORITY_MISSING
            )

        if candidate_result.effect_proposal is not None:
            # The first plan already consumed a fresh, exact broker review.
            # Keep that plan/review pair instead of reviewing a second time.
            review = broker.review
            reviewed_result = candidate_result
        else:
            review = self._bindings.broker_adapter.review_order(
                candidate, broker, observed_at=as_of
            )
            if not isinstance(review, BrokerReviewFacts):
                raise Arch148RuntimeBlocked("BROKER_REVIEW_UNAVAILABLE")
            reviewed_broker = replace(broker, review=review)
            reviewed_result = self._bindings.application.run_cycle(
                replace(request, broker=reviewed_broker)
            )
            if not isinstance(reviewed_result, CycleResult):
                raise Arch148RuntimeBlocked("PLANNER_RESULT_UNAVAILABLE")
            self._last_broker = reviewed_broker
            self._last_result = reviewed_result
            self._last_state = self._load_state()
        if not isinstance(review, BrokerReviewFacts):
            raise Arch148RuntimeBlocked("BROKER_REVIEW_UNAVAILABLE")
        if reviewed_result.intent != candidate:
            self._publish("PLAN_CHANGED_BLOCKED", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.PLAN_CHANGED
            )
        if reviewed_result.effect_proposal is None:
            self._publish("REVIEW_BLOCKED", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.REVIEW_BLOCKED
            )
        if stop_event.is_set():
            self._publish("STOP_REQUESTED", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.LIFECYCLE_STOPPED
            )

        proposed_state = self._load_state()
        persisted_intent = next(
            (
                item
                for item in proposed_state.intents
                if item.intent_id == candidate.intent_id
            ),
            None,
        )
        if (
            persisted_intent != candidate
            or persisted_intent.lifecycle is not IntentLifecycle.PROPOSED
            or review not in proposed_state.proposal_reviews
        ):
            self._publish("PROPOSAL_BINDING_FAILED", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.PROPOSAL_BINDING_FAILED
            )
        fresh_broker = self._bindings.broker_adapter.read_snapshot(
            as_of, proposed_state
        )
        if not isinstance(fresh_broker, BrokerSnapshot):
            raise Arch148RuntimeBlocked("BROKER_SNAPSHOT_UNAVAILABLE")
        self._last_state = proposed_state
        self._last_broker = fresh_broker
        if fresh_broker.review is not None and fresh_broker.review != review:
            self._publish("BROKER_REVIEW_CHANGED", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.REVIEW_BLOCKED
            )
        effect_at = _now(self._bindings.clock)
        if not _facts_fresh_for_effect(
            market=market,
            broker=fresh_broker,
            review=review,
            intent=candidate,
            result=reviewed_result,
            planned_as_of=as_of,
            effect_at=effect_at,
            expected_state_revision=proposed_state.revision,
        ):
            self._publish("BROKER_FACTS_STALE", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.BROKER_FACTS_STALE
            )
        allowed = self._effect_authority.allows_place(
            candidate,
            state=proposed_state,
            result=reviewed_result,
            broker=fresh_broker,
        )
        if type(allowed) is not bool or not allowed:
            self._publish("AUTHORIZATION_MISSING", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.AUTHORITY_MISSING
            )

        stale_before_reservation = False
        with lifecycle_interlock.effect_boundary() as admitted:
            if not admitted or stop_event.is_set():
                self._publish("STOP_REQUESTED", reviewed_result.status.blockers)
                return Arch148CycleOutcome(
                    reviewed_result, RuntimeCycleBlocker.LIFECYCLE_STOPPED
                )
            reserve_at = _now(self._bindings.clock)
            if not _facts_fresh_for_effect(
                market=market,
                broker=fresh_broker,
                review=review,
                intent=candidate,
                result=reviewed_result,
                planned_as_of=as_of,
                effect_at=reserve_at,
                expected_state_revision=proposed_state.revision,
            ):
                stale_before_reservation = True
                reservation_result = None
            else:
                reservation_result = self._bindings.order_tracker.begin_place(
                    owner_id=self._bindings.owner_id,
                    source_identity=self._bindings.source_identity,
                    session_fingerprint=self._bindings.session_fingerprint,
                    expected_revision=proposed_state.revision,
                    intent_id=candidate.intent_id,
                    broker=fresh_broker,
                    as_of=reserve_at,
                )
        if stale_before_reservation:
            self._publish("BROKER_FACTS_STALE", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.BROKER_FACTS_STALE
            )
        if not isinstance(reservation_result, ReservationResult):
            self._publish("RESERVATION_BLOCKED", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.RESERVATION_UNAVAILABLE
            )

        invoke_at = _now(self._bindings.clock)
        if not _facts_fresh_for_effect(
            market=market,
            broker=fresh_broker,
            review=reservation_result.reservation.review,
            intent=candidate,
            result=reviewed_result,
            planned_as_of=as_of,
            effect_at=invoke_at,
            expected_state_revision=reservation_result.reservation.expected_revision,
        ):
            self._last_state = reservation_result.state
            self._last_effect = "MAY_HAVE_OCCURRED_NO_INVOCATION_STALE_FACTS"
            self._publish("BROKER_FACTS_STALE", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result, RuntimeCycleBlocker.BROKER_FACTS_STALE
            )

        # Reservation admission is the serialized lifecycle boundary.  Once it
        # wins, this cycle makes one exact invocation even if Stop follows;
        # Stop then waits for the call and reconciles without retrying it.
        try:
            effect = self._bindings.broker_adapter.place_order(
                state=reservation_result.state,
                reservation=reservation_result.reservation,
                permit=reservation_result.permit,
                broker=fresh_broker,
                observed_at=invoke_at,
            )
        except Exception:
            # The adapter may already have consumed its one-shot permission.
            # Leave MAY persisted and reconcile facts later; never retry here.
            self._last_state = reservation_result.state
            self._last_broker = fresh_broker
            self._last_effect = "UNKNOWN"
            self._publish("EFFECT_OUTCOME_UNKNOWN", reviewed_result.status.blockers)
            return Arch148CycleOutcome(
                reviewed_result,
                RuntimeCycleBlocker.EFFECT_OUTCOME_UNKNOWN,
                effect_status="UNKNOWN",
            )
        self._last_state = reservation_result.state
        self._last_broker = fresh_broker
        self._last_effect = _effect_status(effect)
        self._publish("EFFECT_IN_FLIGHT_RECONCILE", reviewed_result.status.blockers)
        return Arch148CycleOutcome(
            reviewed_result, None, effect_status=self._last_effect
        )

    def _cancel_protective_stop(
        self,
        candidate: ProtectiveStopCancelCandidate,
        result: CycleResult,
        *,
        market: MarketSnapshot,
        planned_as_of: datetime,
        stop_event: threading.Event,
        lifecycle_interlock: L43SerializedLifecycleInterlock,
    ) -> Arch148CycleOutcome:
        """Consume one policy-produced exact cancel candidate, then end cadence."""

        if stop_event.is_set():
            self._publish("STOP_REQUESTED", result.status.blockers)
            return Arch148CycleOutcome(result, RuntimeCycleBlocker.LIFECYCLE_STOPPED)
        if (
            self._bindings.execution_profile
            is not ExecutionProfile.PROTECTED_WHOLE_SHARE
        ):
            self._publish("EXECUTION_PROFILE_BLOCKED", result.status.blockers)
            return Arch148CycleOutcome(
                result, RuntimeCycleBlocker.EXECUTION_PROFILE_BLOCKED
            )
        if self._cancel_effect_authority is None:
            self._publish("CANCEL_AUTHORIZATION_MISSING", result.status.blockers)
            return Arch148CycleOutcome(
                result, RuntimeCycleBlocker.CANCEL_AUTHORITY_MISSING
            )

        state = self._load_state()
        as_of = _now(self._bindings.clock)
        broker = self._bindings.broker_adapter.read_snapshot(as_of, state)
        if not isinstance(broker, BrokerSnapshot):
            raise Arch148RuntimeBlocked("BROKER_SNAPSHOT_UNAVAILABLE")
        self._last_state = state
        self._last_broker = broker
        if not validate_protective_stop_cancel_candidate(
            candidate, state, broker, as_of=as_of
        ) or not _cancel_decision_fresh(
            candidate,
            result,
            state,
            market=market,
            planned_as_of=planned_as_of,
            effect_at=as_of,
        ):
            self._publish("CANCEL_CANDIDATE_STALE", result.status.blockers)
            return Arch148CycleOutcome(result, RuntimeCycleBlocker.BROKER_FACTS_STALE)
        allowed = self._cancel_effect_authority.allows_cancel(
            candidate,
            state=state,
            result=result,
            broker=broker,
        )
        if type(allowed) is not bool or not allowed:
            self._publish("CANCEL_AUTHORIZATION_MISSING", result.status.blockers)
            return Arch148CycleOutcome(
                result, RuntimeCycleBlocker.CANCEL_AUTHORITY_MISSING
            )
        if stop_event.is_set():
            self._publish("STOP_REQUESTED", result.status.blockers)
            return Arch148CycleOutcome(result, RuntimeCycleBlocker.LIFECYCLE_STOPPED)

        stale_before_reservation = False
        with lifecycle_interlock.effect_boundary() as admitted:
            if not admitted or stop_event.is_set():
                self._publish("STOP_REQUESTED", result.status.blockers)
                return Arch148CycleOutcome(
                    result, RuntimeCycleBlocker.LIFECYCLE_STOPPED
                )
            reserve_at = _now(self._bindings.clock)
            current_state = self._load_state()
            if (
                current_state.revision != state.revision
                or not validate_protective_stop_cancel_candidate(
                    candidate, current_state, broker, as_of=reserve_at
                )
                or not _cancel_decision_fresh(
                    candidate,
                    result,
                    current_state,
                    market=market,
                    planned_as_of=planned_as_of,
                    effect_at=reserve_at,
                )
            ):
                stale_before_reservation = True
                reservation_result = None
            else:
                reservation_result = self._bindings.order_tracker.begin_cancel(
                    owner_id=self._bindings.owner_id,
                    source_identity=self._bindings.source_identity,
                    session_fingerprint=self._bindings.session_fingerprint,
                    expected_revision=current_state.revision,
                    candidate=candidate,
                    broker=broker,
                    as_of=reserve_at,
                )
        if stale_before_reservation:
            self._publish("CANCEL_CANDIDATE_STALE", result.status.blockers)
            return Arch148CycleOutcome(result, RuntimeCycleBlocker.BROKER_FACTS_STALE)
        if not isinstance(reservation_result, ReservationResult):
            self._publish("CANCEL_RESERVATION_BLOCKED", result.status.blockers)
            return Arch148CycleOutcome(
                result, RuntimeCycleBlocker.RESERVATION_UNAVAILABLE
            )

        invoke_at = _now(self._bindings.clock)
        if not validate_protective_stop_cancel_candidate(
            candidate, state, broker, as_of=invoke_at
        ) or not _cancel_decision_fresh(
            candidate,
            result,
            state,
            market=market,
            planned_as_of=planned_as_of,
            effect_at=invoke_at,
        ):
            self._last_state = reservation_result.state
            self._last_effect = "MAY_HAVE_OCCURRED_NO_INVOCATION_STALE_FACTS"
            self._publish("CANCEL_CANDIDATE_STALE", result.status.blockers)
            return Arch148CycleOutcome(result, RuntimeCycleBlocker.BROKER_FACTS_STALE)
        try:
            effect = self._bindings.broker_adapter.cancel_order(
                state=reservation_result.state,
                reservation=reservation_result.reservation,
                permit=reservation_result.permit,
                broker=broker,
                observed_at=invoke_at,
            )
        except Exception:
            self._last_state = reservation_result.state
            self._last_effect = "UNKNOWN"
            self._publish("CANCEL_OUTCOME_UNKNOWN", result.status.blockers)
            return Arch148CycleOutcome(
                result,
                RuntimeCycleBlocker.EFFECT_OUTCOME_UNKNOWN,
                effect_status="UNKNOWN",
            )
        self._last_state = reservation_result.state
        self._last_effect = _effect_status(effect)
        self._publish("CANCEL_IN_FLIGHT_RECONCILE", result.status.blockers)
        return Arch148CycleOutcome(result, None, effect_status=self._last_effect)

    def stop_reconcile(self) -> None:
        state, broker, _, _ = self._reconcile_until_stable()
        self._last_state = state
        self._last_broker = broker
        self._publish("STOP_RECONCILED", ())

    def _reconcile_until_stable(
        self,
    ) -> tuple[RuntimeState, BrokerSnapshot, bool, datetime]:
        settled_exit = False
        for _ in range(_SETTLEMENT_LIMIT):
            state = self._load_state()
            as_of = _now(self._bindings.clock)
            broker = self._bindings.broker_adapter.read_snapshot(as_of, state)
            if not isinstance(broker, BrokerSnapshot):
                raise Arch148RuntimeBlocked("BROKER_SNAPSHOT_UNAVAILABLE")
            outcome = self._bindings.application.reconcile_only(
                ReconciliationRequest(
                    as_of,
                    self._bindings.owner_id,
                    self._bindings.source_identity,
                    self._bindings.session_fingerprint,
                    state.revision,
                    broker,
                )
            )
            if not isinstance(outcome, ReconciliationOutcome):
                raise Arch148RuntimeBlocked("RECONCILIATION_RESULT_UNAVAILABLE")
            if outcome.blockers:
                self._last_state = outcome.state or state
                self._last_broker = broker
                self._publish("RECONCILIATION_BLOCKED", outcome.blockers)
                raise Arch148RuntimeBlocked("RECONCILIATION_BLOCKED")
            if outcome.state is None:
                raise Arch148RuntimeBlocked("RECONCILIATION_STATE_UNAVAILABLE")
            self._last_state = outcome.state
            self._last_broker = broker
            settled_exit = settled_exit or outcome.settled_exit
            if outcome.state_advanced:
                continue
            latest = self._load_state()
            if latest.revision != outcome.state.revision:
                raise Arch148RuntimeBlocked("STATE_CHANGED_DURING_RECONCILE")
            return latest, broker, settled_exit, as_of
        raise Arch148RuntimeBlocked("RECONCILIATION_DID_NOT_SETTLE")

    def _load_state(self) -> RuntimeState:
        try:
            state = self._bindings.state_store.load(
                self._bindings.owner_id, self._bindings.source_identity
            )
        except Exception:
            state = None
        if (
            not isinstance(state, RuntimeState)
            or state.owner_id != self._bindings.owner_id
            or state.source_identity != self._bindings.source_identity
            or state.session_fingerprint != self._bindings.session_fingerprint
        ):
            raise Arch148RuntimeBlocked("RUNTIME_STATE_UNAVAILABLE")
        return state

    def _publish(
        self,
        health: str,
        blockers: tuple[AdmissionBlocker, ...],
    ) -> None:
        facts = _display_facts(
            self._bindings,
            state=self._last_state,
            broker=self._last_broker,
            market=self._last_market,
            result=self._last_result,
            effect_status=self._last_effect,
            health=health,
            blockers=blockers,
        )
        self._display_cache.publish(facts)


def _reviewable(result: CycleResult, intent: LogicalOrderIntent) -> bool:
    """Trust only the planner's action-specific candidate boundary.

    The planner may retain ambient safety facts such as STOP_UNPROTECTED or
    FORCED_FLAT in its descriptive status while producing a valid EXIT or
    PROTECTIVE_STOP proposal.  A candidate is reviewable only when its action
    agrees with the planner status; the reviewed replan and durable reservation
    enforce the action-specific gates again.
    """

    return result.intent == intent and result.status.action is intent.kind


def _facts_fresh_for_effect(
    *,
    market: MarketSnapshot,
    broker: BrokerSnapshot,
    review: BrokerReviewFacts | None,
    intent: LogicalOrderIntent,
    result: CycleResult,
    planned_as_of: datetime,
    effect_at: datetime,
    expected_state_revision: int,
) -> bool:
    """Recheck the planner's exact input freshness at the reservation/write time."""

    if (
        result.intent != intent
        or result.status.as_of != planned_as_of
        or market.as_of != planned_as_of
        or broker.state_revision != expected_state_revision
        or broker.source_identity != intent.source_identity
        or broker.session_fingerprint == ""
        or review is None
        or review.source_identity != broker.source_identity
        or review.account_fingerprint != broker.account.fingerprint
        or review.session_fingerprint != broker.session_fingerprint
        or review.ref_id != intent.ref_id
        or review.terms_digest != intent.terms_digest
        or review.status.value != "ACCEPTED"
        or review.warnings
        or review.approval_required
        or review.state_revision
        not in (expected_state_revision, expected_state_revision - 1)
    ):
        return False
    if not _age_within(effect_at, planned_as_of, _BAR_MAX_AGE):
        return False
    signal_point = result.signal.latest
    if signal_point is None or not _age_within(
        effect_at, signal_point.bar_end, _BAR_MAX_AGE
    ):
        return False
    execution_price = market.execution_prices.get(intent.symbol)
    if execution_price is None or not _age_within(
        effect_at, execution_price.observed_at, _PRICE_MAX_AGE
    ):
        return False

    observations = (
        broker.observed_at,
        broker.account.observed_at,
        broker.position_scope.observed_at,
        broker.order_scope.observed_at,
        broker.approvals.observed_at,
        *(item.observed_at for item in broker.tradability.values()),
        *(item.observed_at for item in broker.orders),
        *(item.observed_at for item in broker.approvals.requests),
        review.observed_at,
    )
    return all(
        _age_within(effect_at, observed_at, _FACT_MAX_AGE)
        for observed_at in observations
    )


def _age_within(now: datetime, observed_at: datetime, max_age: timedelta) -> bool:
    age = now - observed_at
    return timedelta(0) <= age <= max_age


def _cancel_decision_fresh(
    candidate: ProtectiveStopCancelCandidate,
    result: CycleResult,
    state: RuntimeState,
    *,
    market: MarketSnapshot,
    planned_as_of: datetime,
    effect_at: datetime,
) -> bool:
    """Keep the original EXIT reason bound to a fresh planner decision."""

    if (
        result.status.as_of != planned_as_of
        or market.as_of != planned_as_of
        or not _age_within(effect_at, planned_as_of, _BAR_MAX_AGE)
    ):
        return False
    reasons = set(candidate.exit_reasons)
    position = state.positions.get(candidate.fact.symbol)
    price = market.execution_prices.get(candidate.fact.symbol)
    if (
        position is None
        or price is None
        or candidate.held_price.symbol != candidate.fact.symbol
        or price != candidate.held_price
        or not _age_within(effect_at, price.observed_at, _PRICE_MAX_AGE)
    ):
        return False
    if AdmissionBlocker.STOP_BREACH in reasons:
        if not HardStopPolicy().is_breached(
            price.price,
            HardStopPolicy().threshold(
                position.average_entry_fill, position.hard_stop_price
            ),
        ):
            return False
    if AdmissionBlocker.REGIME_EXIT in reasons:
        latest = result.signal.latest
        if (
            latest is None
            or not _age_within(effect_at, latest.bar_end, _BAR_MAX_AGE)
            or not confirmed_regime_exit(result.signal, result.status.actual_position)
        ):
            return False
    return True


def _display_facts(
    bindings: Arch148RuntimeBindings,
    *,
    state: RuntimeState | None,
    broker: BrokerSnapshot | None,
    market: MarketSnapshot | None,
    result: CycleResult | None,
    effect_status: str | None,
    health: str,
    blockers: tuple[AdmissionBlocker, ...],
) -> Arch148RuntimeDisplayFacts:
    as_of = result.status.as_of if result is not None else _now(bindings.clock)
    candidate = result.status.current_candidate if result is not None else None
    confirmation = result.status.entry_confirmation if result is not None else None
    desired = result.status.desired_position if result is not None else None
    actual = _actual_position(state, broker, result)
    position = (
        state.positions.get(actual.symbol)
        if state is not None and actual is not None and actual.symbol is not None
        else None
    )
    working_orders = (
        sum(not order.state.terminal for order in broker.orders)
        if broker is not None
        else None
    )
    fills = (
        sum(order.filled_quantity > Decimal("0") for order in broker.orders)
        if broker is not None
        else None
    )
    signal_fresh = result is not None and result.signal.quality.value == "READY"
    price_observations = (
        tuple(market.execution_prices.values()) if market is not None else ()
    )
    quote_as_of = max((price.observed_at for price in price_observations), default=None)
    quote_fresh = bool(price_observations) and all(
        timedelta(0) <= as_of - item.observed_at <= _PRICE_MAX_AGE
        for item in price_observations
    )
    pending = None
    if state is not None:
        pending = next(
            (
                item
                for item in reversed(state.intents)
                if item.lifecycle
                in (
                    IntentLifecycle.PROPOSED,
                    IntentLifecycle.APPROVAL_REQUIRED,
                    IntentLifecycle.MAY_HAVE_OCCURRED,
                    IntentLifecycle.UNKNOWN,
                )
            ),
            None,
        )
    effect = effect_status
    if effect is None and state is not None and state.write_reservations:
        effect = state.write_reservations[-1].status.value
    if pending is not None:
        intent_text = f"{pending.kind.value}:{pending.lifecycle.value}:{pending.ref_id}"
    else:
        intent_text = None
    protection = "UNAVAILABLE"
    if result is not None:
        if result.status.actual_position is TargetPosition.FLAT:
            protection = "NOT_HELD"
        else:
            protection = "READY" if result.status.protective_stop_ready else "BLOCKED"
    if blockers:
        restricted_status = RestrictedLiveStatus.BLOCKED
        reasons = (Reason.RECONCILIATION_REQUIRED,)
    elif pending is not None and pending.lifecycle is IntentLifecycle.UNKNOWN:
        restricted_status = RestrictedLiveStatus.EFFECT_UNKNOWN
        reasons = (Reason.EFFECT_UNKNOWN,)
    elif pending is not None:
        restricted_status = (
            RestrictedLiveStatus.ENTRY_PENDING
            if pending.kind is IntentKind.ENTRY
            else RestrictedLiveStatus.SELL_PENDING
        )
        reasons = (
            Reason.ENTRY_PENDING
            if pending.kind is IntentKind.ENTRY
            else Reason.SELL_PENDING,
        )
    elif result is not None and result.effect_proposal is not None:
        restricted_status = RestrictedLiveStatus.REVIEW_ACCEPTED
        reasons = (Reason.AUTHORIZATION_MISSING,)
    else:
        restricted_status = RestrictedLiveStatus.RUNNING_READ_ONLY
        reasons = (Reason.NO_ACTION,)
    blocker_text = tuple(item.value for item in blockers)
    session = session_decision(as_of).reason.value
    return Arch148RuntimeDisplayFacts(
        session=session,
        strategy="ARCH148_QQQ_5M_TQQQ_SQQQ",
        source_head=bindings.source_identity.head,
        source_tree=bindings.source_identity.tree,
        signal_as_of=as_of if result is not None else None,
        quote_as_of=quote_as_of,
        signal_fresh=signal_fresh,
        quote_fresh=quote_fresh,
        connected=broker is not None,
        current_regime=candidate.value if candidate is not None else None,
        entry_confirmation=confirmation.value if confirmation is not None else None,
        desired_position=desired.value if desired is not None else None,
        actual_position=actual.value if actual is not None else None,
        owned_quantity=position.quantity if position is not None else None,
        working_orders=working_orders,
        fills=fills,
        entries_used=(
            sum(
                item.kind is IntentKind.ENTRY
                for item in state.intents
                if item.lifecycle is not IntentLifecycle.PROPOSED
            )
            if state is not None
            else 0
        ),
        exits_used=(
            sum(
                item.kind in (IntentKind.EXIT, IntentKind.PROTECTIVE_STOP)
                for item in state.intents
                if item.lifecycle is not IntentLifecycle.PROPOSED
            )
            if state is not None
            else 0
        ),
        latest_reconciled_fill=(
            f"entry average {position.average_entry_fill}"
            if position is not None
            else None
        ),
        hard_stop_price=position.hard_stop_price if position is not None else None,
        protection_status=protection,
        pending_intent=intent_text,
        effect_status=effect,
        latest_result=(result.status.state if result is not None else health),
        blockers=blocker_text,
        health=health,
        reasons=reasons,
        restricted_live_status=restricted_status,
        runtime_enabled=health
        not in (
            "STOPPED",
            "STOP_REQUESTED",
            "STOP_RECONCILED",
            "BLOCKED",
            "RECONCILIATION_BLOCKED",
        ),
    )


def _effect_status(effect: object) -> str:
    status = getattr(effect, "status", None)
    value = getattr(status, "value", status)
    if not isinstance(value, str) or not value:
        return "UNKNOWN"
    return value


def _actual_position(
    state: RuntimeState | None,
    broker: BrokerSnapshot | None,
    result: CycleResult | None,
) -> TargetPosition | None:
    if broker is not None:
        broker_symbols = tuple(
            symbol for symbol in (TQQQ, SQQQ) if symbol in broker.positions
        )
        if not broker_symbols:
            if state is not None and not state.positions:
                return TargetPosition.FLAT
            return None
        if len(broker_symbols) == 1 and state is not None:
            symbol = broker_symbols[0]
            owned = state.positions.get(symbol)
            provider_position = broker.positions[symbol]
            if (
                owned is not None
                and broker.position_owners.get(symbol) == owned.entry_intent_id
                and provider_position.quantity == owned.quantity
            ):
                return TargetPosition(symbol.value)
        return None
    if state is not None and len(state.positions) == 1:
        return TargetPosition(next(iter(state.positions)).value)
    return result.status.actual_position if result is not None else None


def _now(clock: Clock) -> datetime:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise Arch148RuntimeBlocked("CLOCK_UNAVAILABLE")
    return value.astimezone(UTC)
