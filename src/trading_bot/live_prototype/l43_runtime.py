"""Production composition and one serialized Architecture 147 L43 cycle.

Construction is inert with respect to credentials and providers.  The runtime
uses the accepted observer, operator, transport and reconciler; RHC4's
production authorizer is closed by default.
"""

from __future__ import annotations

import asyncio
import re
import threading
from collections.abc import Callable, Coroutine, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Any

from trading_bot.live_prototype.contracts import RestrictedLiveStatus
from trading_bot.live_prototype.durable_state import (
    BlockReason,
    IntentStatus,
)
from trading_bot.live_prototype.l43_effect_operator import (
    L43AcceptedReviewReceipt,
    L43AuthorizationRequest,
    L43EffectOperator,
    L43EffectOutcome,
    L43EffectResult,
    L43EffectStage,
    L43ExactPlanAuthorizer,
    L43StageAuthorization,
)
from trading_bot.live_prototype.l43_pre_effect_observation import (
    L43PreEffectDependencies,
    L43PreEffectOutcome,
    L43PreEffectResult,
    observe_l43_pre_effect,
)
from trading_bot.live_prototype.l43_production_owner import (
    L43SourceIdentity,
    read_source_identity,
)
from trading_bot.live_prototype.l43_provider_contracts import L43AccountIdentity
from trading_bot.live_prototype.l43_state import (
    L43StateSession,
    L43StateSnapshot,
)
from trading_bot.live_prototype.tiny_live_policy import ManualCloseTrigger
from trading_bot.robinhood_mcp.l43_production_composition import (
    DEFAULT_ROBINHOOD_REDIRECT_URI,
    L43ProductionPreEffectComposition,
)
from trading_bot.robinhood_mcp.l43_transport import L43RobinhoodTransport

_SAFE_REASON = re.compile(r"[A-Z0-9_]{1,96}\Z")
_ZERO = Decimal("0")
_MAYBE_EFFECT = {IntentStatus.MAY_HAVE_OCCURRED, IntentStatus.UNKNOWN}
_PENDING_ORDER = {IntentStatus.WORKING, IntentStatus.PARTIAL}


@dataclass(frozen=True, slots=True)
class L43RuntimeObservation:
    """Sanitized cycle status; no account handle, provider ID or plan escapes."""

    status: RestrictedLiveStatus
    reason_code: str

    def __post_init__(self) -> None:
        if type(self.status) is not RestrictedLiveStatus:
            raise TypeError("runtime observation status must be closed")
        if (
            type(self.reason_code) is not str
            or _SAFE_REASON.fullmatch(self.reason_code) is None
        ):
            raise ValueError("runtime observation reason must be sanitized")


class _DefaultDenyAuthorizer(L43ExactPlanAuthorizer):
    """RHC4 has no admitted grant source; every exact stage remains closed."""

    __slots__ = ()

    def authorize(
        self, request: L43AuthorizationRequest
    ) -> L43StageAuthorization | None:
        del request
        return None


class L43SerializedLifecycleInterlock:
    """Linearize Stop against a new durable effect/review transition."""

    __slots__ = ("_lock", "_active_stop")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_stop: threading.Event | None = None

    def bind_cycle(self, stop: threading.Event) -> None:
        if not callable(getattr(stop, "is_set", None)):
            raise TypeError("lifecycle interlock requires a threading.Event")
        with self._lock:
            if self._active_stop is not None:
                raise RuntimeError("lifecycle interlock already has an active cycle")
            self._active_stop = stop

    def unbind_cycle(self, stop: threading.Event) -> None:
        with self._lock:
            if self._active_stop is not stop:
                raise RuntimeError("lifecycle interlock cycle identity changed")
            self._active_stop = None

    def request_stop(self) -> None:
        """Request Stop in the same order as a new effect/review boundary."""

        with self._lock:
            if self._active_stop is not None:
                self._active_stop.set()

    @contextmanager
    def effect_boundary(self) -> Iterator[bool]:
        """Admit reservation/MAY or durable review-start as one decision."""

        with self._lock:
            stop = self._active_stop
            yield stop is not None and not stop.is_set()


@dataclass(frozen=True, slots=True)
class _RuntimeComponents:
    session_factory: Callable[[], L43StateSession]
    observer: Callable[
        [Callable[[L43AccountIdentity], None] | None], L43PreEffectResult
    ]
    operator: object


class L43Runtime:
    """Serialized synchronous facade around the accepted async effect operator."""

    __slots__ = (
        "_expected_source",
        "_source_reader",
        "_components_factory",
        "_components",
        "_components_failed",
        "_cycle_lock",
        "_active_stop",
        "_lifecycle_interlock",
        "_accepted_review",
    )

    def __init__(
        self,
        *,
        expected_source: L43SourceIdentity,
        source_reader: Callable[[], L43SourceIdentity],
        components_factory: Callable[
            [Callable[[], AbstractContextManager[bool]]], _RuntimeComponents
        ],
    ) -> None:
        if type(expected_source) is not L43SourceIdentity:
            raise TypeError("runtime requires a pinned source identity")
        if not callable(source_reader) or not callable(components_factory):
            raise TypeError("runtime source and component builders must be callable")
        self._expected_source = expected_source
        self._source_reader = source_reader
        self._components_factory = components_factory
        self._components: _RuntimeComponents | None = None
        self._components_failed = False
        self._cycle_lock = threading.Lock()
        self._active_stop: threading.Event | None = None
        self._lifecycle_interlock = L43SerializedLifecycleInterlock()
        self._accepted_review: L43AcceptedReviewReceipt | None = None

    @property
    def source_head(self) -> str:
        return self._expected_source.source_head

    @property
    def source_tree(self) -> str:
        return self._expected_source.source_tree

    def request_stop(self) -> None:
        """Serialize an application Stop request with the current effect path."""

        self._lifecycle_interlock.request_stop()

    def run_cycle(self, stop: threading.Event) -> L43RuntimeObservation:
        """Run one cycle to completion; Stop never cancels an effect boundary."""

        if not callable(getattr(stop, "is_set", None)):
            raise TypeError("runtime cycle requires a threading.Event")
        if stop.is_set():
            return _observation(RestrictedLiveStatus.STOPPED, "STOP_REQUESTED")
        with self._cycle_lock:
            self._active_stop = stop
            self._lifecycle_interlock.bind_cycle(stop)
            try:
                return self._run_cycle_locked(stop)
            finally:
                self._lifecycle_interlock.unbind_cycle(stop)
                self._active_stop = None

    def _run_cycle_locked(self, stop: threading.Event) -> L43RuntimeObservation:
        if stop.is_set():
            return _observation(RestrictedLiveStatus.STOPPED, "STOP_REQUESTED")
        if not self._source_is_pinned():
            return _observation(
                RestrictedLiveStatus.BLOCKED, "EXECUTABLE_SOURCE_CHANGED"
            )
        components = self._ensure_components()
        if components is None:
            return _observation(
                RestrictedLiveStatus.BLOCKED,
                "PRODUCTION_COMPOSITION_UNAVAILABLE",
            )
        if not self._source_is_pinned():
            return _observation(
                RestrictedLiveStatus.BLOCKED, "EXECUTABLE_SOURCE_CHANGED"
            )
        try:
            with components.session_factory() as session:
                snapshot = session.snapshot()
        except Exception:
            return _observation(RestrictedLiveStatus.BLOCKED, "L43_STATE_UNAVAILABLE")
        if type(snapshot) is not L43StateSnapshot:
            return _observation(RestrictedLiveStatus.BLOCKED, "L43_STATE_INVALID")

        prior = _snapshot_outcome(snapshot)
        if prior is not None:
            return prior

        pending = _pending_order(snapshot)
        if pending is not None:
            if isinstance(pending, L43RuntimeObservation):
                return pending
            stage, intent_id, provider_order_id = pending
            if stop.is_set():
                return _observation(
                    RestrictedLiveStatus.STOPPED, "STOP_BEFORE_SETTLEMENT"
                )
            try:
                settled = self._run_async(
                    components.operator.settle_pending_order(
                        stage=stage,
                        intent_id=intent_id,
                        provider_order_id=provider_order_id,
                    )
                )
            except Exception:
                return _observation(
                    RestrictedLiveStatus.BLOCKED, "PENDING_SETTLEMENT_FAILED"
                )
            return _effect_observation(settled)

        remainder = _snapshot_remainder_outcome(snapshot)
        if remainder is not None:
            if remainder.status is not RestrictedLiveStatus.REVIEW_ACCEPTED:
                return remainder
            if self._accepted_review is None:
                return _observation(
                    RestrictedLiveStatus.BLOCKED,
                    "ACCEPTED_REVIEW_REQUIRES_RECOVERY",
                )
            return self._place_after_accepted_review(stop, components)

        if stop.is_set():
            return _observation(RestrictedLiveStatus.STOPPED, "STOP_BEFORE_OBSERVATION")
        return self._observe_cycle(stop, components)

    def _ensure_components(self) -> _RuntimeComponents | None:
        if self._components is not None:
            return self._components
        if self._components_failed:
            return None
        try:
            components = self._components_factory(
                self._lifecycle_interlock.effect_boundary
            )
            if (
                type(components) is not _RuntimeComponents
                or not callable(components.session_factory)
                or not callable(components.observer)
                or not all(
                    callable(getattr(components.operator, name, None))
                    for name in (
                        "settle_pending_order",
                        "place_entry",
                        "review_sell",
                        "place_sell",
                        "persist_observed_manual_close",
                    )
                )
            ):
                raise TypeError
        except Exception:
            self._components_failed = True
            return None
        self._components = components
        return components

    def _source_is_pinned(self) -> bool:
        try:
            return self._source_reader() == self._expected_source
        except Exception:
            return False

    def _observe_cycle(
        self, stop: threading.Event, components: _RuntimeComponents
    ) -> L43RuntimeObservation:
        selected: list[L43AccountIdentity] = []
        try:
            pre_effect = components.observer(selected.append)
        except Exception:
            return _observation(
                RestrictedLiveStatus.BLOCKED, "PRE_EFFECT_OBSERVATION_FAILED"
            )
        if type(pre_effect) is not L43PreEffectResult:
            return _observation(
                RestrictedLiveStatus.BLOCKED, "PRE_EFFECT_RESULT_INVALID"
            )

        if pre_effect.outcome is L43PreEffectOutcome.NO_ACTION_SIGNAL:
            return _observation(RestrictedLiveStatus.NO_ACTION, "NO_ACTION_SIGNAL")
        if pre_effect.outcome is L43PreEffectOutcome.BLOCKED:
            return _pre_effect_block(pre_effect)
        if pre_effect.outcome is L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED:
            try:
                return _effect_observation(
                    components.operator.persist_observed_manual_close(pre_effect)
                )
            except Exception:
                return _observation(
                    RestrictedLiveStatus.BLOCKED, "MANUAL_CLOSE_PERSISTENCE_FAILED"
                )

        account = _selected_account(selected, pre_effect)
        if account is None:
            return _observation(
                RestrictedLiveStatus.BLOCKED, "ACCOUNT_SELECTION_UNAVAILABLE"
            )
        if stop.is_set():
            return _observation(
                RestrictedLiveStatus.STOPPED, "STOP_BEFORE_EFFECT_STAGE"
            )

        if pre_effect.outcome is L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW:
            try:
                result = self._run_async(
                    components.operator.place_entry(pre_effect, account_number=account)
                )
            except Exception:
                return self._stage_failure(
                    components, "ENTRY_STAGE_FAILED", may_have_written=True
                )
            return _effect_observation(result)

        if (
            pre_effect.outcome
            is not L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW
        ):
            return _observation(
                RestrictedLiveStatus.BLOCKED, "PRE_EFFECT_OUTCOME_UNSUPPORTED"
            )

        try:
            reviewed = self._run_async(
                components.operator.review_sell(pre_effect, account_number=account)
            )
        except Exception:
            return self._stage_failure(
                components, "SELL_REVIEW_STAGE_FAILED", may_have_written=True
            )
        reviewed_observation = _effect_observation(reviewed)
        if reviewed.outcome is not L43EffectOutcome.REVIEW_ACCEPTED:
            return reviewed_observation
        receipt = reviewed.accepted_review
        if type(receipt) is not L43AcceptedReviewReceipt:
            return _observation(
                RestrictedLiveStatus.BLOCKED, "ACCEPTED_REVIEW_RECEIPT_MISSING"
            )
        self._accepted_review = receipt
        if stop.is_set():
            return _observation(
                RestrictedLiveStatus.REVIEW_ACCEPTED, "SELL_REVIEW_ACCEPTED"
            )
        return self._place_after_accepted_review(stop, components)

    def _place_after_accepted_review(
        self, stop: threading.Event, components: _RuntimeComponents
    ) -> L43RuntimeObservation:
        receipt = self._accepted_review
        if receipt is None:
            return _observation(
                RestrictedLiveStatus.BLOCKED, "ACCEPTED_REVIEW_REQUIRES_RECOVERY"
            )
        if stop.is_set():
            return _observation(
                RestrictedLiveStatus.REVIEW_ACCEPTED, "SELL_REVIEW_ACCEPTED"
            )
        selected: list[L43AccountIdentity] = []
        try:
            fresh = components.observer(selected.append)
        except Exception:
            return _observation(
                RestrictedLiveStatus.BLOCKED, "SELL_PLACEMENT_OBSERVATION_FAILED"
            )
        if type(fresh) is not L43PreEffectResult:
            return _observation(
                RestrictedLiveStatus.BLOCKED, "PRE_EFFECT_RESULT_INVALID"
            )
        if fresh.outcome is L43PreEffectOutcome.BLOCKED:
            return _pre_effect_block(fresh)
        if fresh.outcome is L43PreEffectOutcome.NO_ACTION_SIGNAL:
            return _observation(RestrictedLiveStatus.NO_ACTION, "NO_ACTION_SIGNAL")
        if fresh.outcome is L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED:
            try:
                return _effect_observation(
                    components.operator.persist_observed_manual_close(fresh)
                )
            except Exception:
                return _observation(
                    RestrictedLiveStatus.BLOCKED, "MANUAL_CLOSE_PERSISTENCE_FAILED"
                )
        if fresh.outcome is not L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW:
            return _observation(
                RestrictedLiveStatus.BLOCKED, "PRE_EFFECT_OUTCOME_UNSUPPORTED"
            )
        current_account = _selected_account(selected, fresh)
        if current_account is None:
            return _observation(
                RestrictedLiveStatus.BLOCKED, "ACCOUNT_SELECTION_UNAVAILABLE"
            )
        if stop.is_set():
            return _observation(
                RestrictedLiveStatus.REVIEW_ACCEPTED, "SELL_REVIEW_ACCEPTED"
            )
        try:
            result = self._run_async(
                components.operator.place_sell(
                    fresh,
                    receipt,
                    account_number=current_account,
                )
            )
        except Exception:
            return self._stage_failure(
                components, "SELL_PLACEMENT_STAGE_FAILED", may_have_written=True
            )
        mapped = _effect_observation(result)
        if mapped.status not in {
            RestrictedLiveStatus.AUTHORIZATION_MISSING,
            RestrictedLiveStatus.REVIEW_ACCEPTED,
        }:
            self._accepted_review = None
        return mapped

    def _stage_failure(
        self,
        components: _RuntimeComponents,
        reason_code: str,
        *,
        may_have_written: bool,
    ) -> L43RuntimeObservation:
        """Prefer durable facts over generic failure after an escaped stage."""

        try:
            with components.session_factory() as session:
                snapshot = session.snapshot()
        except Exception:
            return _observation(
                RestrictedLiveStatus.EFFECT_UNKNOWN
                if may_have_written
                else RestrictedLiveStatus.BLOCKED,
                "STAGE_FAILURE_STATE_UNAVAILABLE",
            )
        prior = _snapshot_outcome(snapshot)
        if prior is not None:
            return prior
        pending = _pending_order(snapshot)
        if isinstance(pending, L43RuntimeObservation):
            return pending
        if pending is not None:
            stage, _, _ = pending
            return _observation(
                RestrictedLiveStatus.ENTRY_PENDING
                if stage is L43EffectStage.ENTRY_PLACEMENT
                else RestrictedLiveStatus.SELL_PENDING,
                "DURABLE_ORDER_PENDING",
            )
        remainder = _snapshot_remainder_outcome(snapshot)
        if remainder is not None:
            return remainder
        if may_have_written:
            return _observation(
                RestrictedLiveStatus.EFFECT_UNKNOWN,
                "STAGE_FAILURE_EFFECT_UNRESOLVED",
            )
        return _observation(RestrictedLiveStatus.BLOCKED, reason_code)

    @staticmethod
    def _run_async(
        coroutine: Coroutine[Any, Any, L43EffectResult],
    ) -> L43EffectResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            close = getattr(coroutine, "close", None)
            if callable(close):
                close()
            raise RuntimeError("runtime cycle cannot run inside an event loop")
        result = asyncio.run(coroutine)
        if type(result) is not L43EffectResult:
            raise TypeError("L43 operator returned an unsupported result")
        return result


def build_production_l43_runtime(repo_root: Path) -> L43Runtime:
    """Pin local executable source without loading Q62, state or providers."""

    if not isinstance(repo_root, Path):
        raise TypeError("production L43 runtime requires a concrete repo Path")
    root = repo_root.resolve()
    expected = _read_source_identity(root)
    return L43Runtime(
        expected_source=expected,
        source_reader=lambda: _read_source_identity(root),
        components_factory=lambda effect_boundary: _production_components(
            root,
            expected,
            effect_boundary=effect_boundary,
        ),
    )


def _production_components(
    repo_root: Path,
    expected_source: L43SourceIdentity,
    *,
    effect_boundary: Callable[[], AbstractContextManager[bool]],
) -> _RuntimeComponents:
    """Load canonical prerequisites only after Start enters the first cycle."""

    composition = L43ProductionPreEffectComposition.for_production(repo_root=repo_root)
    dependencies = composition.dependencies
    if dependencies.source_reader() != expected_source:
        raise RuntimeError("production L43 source changed during composition")
    from trading_bot.robinhood_mcp.order_scope_evidence_admission import (
        OrderScopeEvidenceAuthority,
        load_order_scope_evidence_authority,
    )

    retained_scope = load_order_scope_evidence_authority(composition.origin)
    if (
        type(retained_scope) is not OrderScopeEvidenceAuthority
        or retained_scope.account_fingerprint
        != composition.origin.runtime_identity.account_fingerprint
    ):
        raise RuntimeError("retained RHC3 order-scope evidence is unavailable")

    state_factory = L43StateSession.for_production
    transport = L43RobinhoodTransport.for_production(
        redirect_uri=DEFAULT_ROBINHOOD_REDIRECT_URI
    )
    operator = L43EffectOperator(
        session_factory=state_factory,
        transport=transport,
        authorizer=_DefaultDenyAuthorizer(),
        effect_boundary=effect_boundary,
        reobserver=_locked_reobserver(dependencies),
        reconciler=composition.post_effect_reconciler(),
        review_caller=transport.review_sell_order,
    )

    def observer(
        sink: Callable[[L43AccountIdentity], None] | None,
    ) -> L43PreEffectResult:
        return observe_l43_pre_effect(
            dependencies,
            _account_identity_sink=sink,
        )

    return _RuntimeComponents(
        session_factory=state_factory,
        observer=observer,
        operator=operator,
    )


def _locked_reobserver(
    dependencies: L43PreEffectDependencies,
) -> Callable[..., L43PreEffectResult]:
    """Observe immutable state detached under the operator-held file lock."""

    def reobserve(
        session: L43StateSession,
        *,
        requested_entry_risk: Decimal | None = None,
    ) -> L43PreEffectResult:
        snapshot = session.snapshot()
        detached = replace(
            dependencies,
            state_snapshot_reader=lambda: snapshot,
        )

        def read() -> L43PreEffectResult:
            if requested_entry_risk is None:
                return observe_l43_pre_effect(detached)
            return observe_l43_pre_effect(
                detached,
                requested_entry_risk=requested_entry_risk,
            )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return read()
        with ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="arch147-l43-reobserver",
        ) as executor:
            return executor.submit(read).result()

    return reobserve


def _read_source_identity(repo_root: Path) -> L43SourceIdentity:
    return read_source_identity(repo_root)


def _snapshot_outcome(
    snapshot: L43StateSnapshot,
) -> L43RuntimeObservation | None:
    state = snapshot.state
    entry = state.entry
    exit_order = state.exit
    statuses = tuple(order.status for order in (entry, exit_order) if order is not None)

    if state.blocked_reason is BlockReason.UNCERTAIN_EFFECT or any(
        status in _MAYBE_EFFECT for status in statuses
    ):
        return _observation(
            RestrictedLiveStatus.EFFECT_UNKNOWN, "DURABLE_EFFECT_UNKNOWN"
        )
    if state.manual_close is not None:
        if state.manual_close.trigger in {
            ManualCloseTrigger.SELL_UNKNOWN,
            ManualCloseTrigger.SELL_REVIEW_UNKNOWN,
        }:
            return _observation(
                RestrictedLiveStatus.EFFECT_UNKNOWN, "SELL_EFFECT_UNKNOWN"
            )
        return _observation(
            RestrictedLiveStatus.MANUAL_CLOSE_REQUIRED,
            state.manual_close.trigger.value,
        )
    if (
        exit_order is not None
        and exit_order.status is IntentStatus.FILLED
        and state.owned_quantity == _ZERO
        and state.reconciled
    ):
        return _observation(
            RestrictedLiveStatus.SELL_RECONCILED, "SELL_FACTUALLY_RECONCILED"
        )
    return None


def _snapshot_remainder_outcome(
    snapshot: L43StateSnapshot,
) -> L43RuntimeObservation | None:
    """Classify durable states only after bound WORKING/PARTIAL settlement."""

    state = snapshot.state
    if snapshot.manual_close_required or state.manual_close_required:
        return _observation(
            RestrictedLiveStatus.MANUAL_CLOSE_REQUIRED,
            "DURABLE_MANUAL_CLOSE_REQUIRED",
        )
    if state.blocked_reason is not None:
        return _observation(RestrictedLiveStatus.BLOCKED, state.blocked_reason.value)
    if snapshot.sell_review_pending or state.sell_review_pending:
        return _observation(RestrictedLiveStatus.BLOCKED, "SELL_REVIEW_INCOMPLETE")
    if (
        state.sell_review is not None
        and state.sell_review.status.value == "ACCEPTED"
        and state.exit is None
    ):
        return _observation(
            RestrictedLiveStatus.REVIEW_ACCEPTED, "SELL_REVIEW_ACCEPTED"
        )
    if snapshot.manual_follow_up_required or state.manual_follow_up_required:
        return _observation(
            RestrictedLiveStatus.BLOCKED, "DURABLE_MANUAL_FOLLOW_UP_REQUIRED"
        )
    if state.exit is not None:
        return _observation(RestrictedLiveStatus.BLOCKED, "EXIT_STATE_NOT_SETTLED")
    if state.entry is not None and state.entry.status is IntentStatus.RESERVED:
        return _observation(
            RestrictedLiveStatus.BLOCKED, "ENTRY_RESERVATION_UNRESOLVED"
        )
    if (
        state.entry is not None
        and state.entry.status in {IntentStatus.CANCELED, IntentStatus.REJECTED}
        and state.entry.cumulative_quantity == _ZERO
    ):
        return _observation(RestrictedLiveStatus.BLOCKED, "ENTRY_ALREADY_CONSUMED")
    return None


def _pending_order(
    snapshot: L43StateSnapshot,
) -> tuple[L43EffectStage, str, str] | L43RuntimeObservation | None:
    state = snapshot.state
    pending: list[tuple[L43EffectStage, object]] = []
    if state.entry is not None and state.entry.status in _PENDING_ORDER:
        pending.append((L43EffectStage.ENTRY_PLACEMENT, state.entry))
    if state.exit is not None and state.exit.status in _PENDING_ORDER:
        pending.append((L43EffectStage.SELL_PLACEMENT, state.exit))
    if not pending:
        return None
    if len(pending) != 1:
        return _observation(RestrictedLiveStatus.BLOCKED, "MULTIPLE_PENDING_ORDERS")
    stage, order = pending[0]
    intent_id = getattr(order, "intent_id", None)
    provider_order_id = getattr(order, "provider_order_id", None)
    if (
        type(intent_id) is not str
        or type(provider_order_id) is not str
        or not intent_id
        or not provider_order_id
    ):
        return _observation(RestrictedLiveStatus.BLOCKED, "PENDING_ORDER_NOT_BOUND")
    return stage, intent_id, provider_order_id


def _selected_account(
    selected: list[L43AccountIdentity], result: L43PreEffectResult
) -> str | None:
    if (
        len(selected) != 1
        or type(selected[0]) is not L43AccountIdentity
        or result.plan is None
        or selected[0].account_fingerprint != result.plan.account_fingerprint
    ):
        return None
    return selected[0].account_number


def _pre_effect_block(result: L43PreEffectResult) -> L43RuntimeObservation:
    if result.outcome is L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED:
        return _observation(
            RestrictedLiveStatus.MANUAL_CLOSE_REQUIRED,
            "PRE_EFFECT_MANUAL_CLOSE_REQUIRED",
        )
    reason = result.blockers[0].value if result.blockers else "PRE_EFFECT_BLOCKED"
    return _observation(RestrictedLiveStatus.BLOCKED, reason)


def _effect_observation(result: L43EffectResult) -> L43RuntimeObservation:
    status = {
        L43EffectOutcome.NO_ACTION_SIGNAL: RestrictedLiveStatus.NO_ACTION,
        L43EffectOutcome.ENTRY_PENDING: RestrictedLiveStatus.ENTRY_PENDING,
        L43EffectOutcome.SELL_PENDING: RestrictedLiveStatus.SELL_PENDING,
        L43EffectOutcome.ENTRY_RECONCILED: RestrictedLiveStatus.ENTRY_RECONCILED,
        L43EffectOutcome.SELL_RECONCILED: RestrictedLiveStatus.SELL_RECONCILED,
        L43EffectOutcome.MANUAL_CLOSE_REQUIRED: (
            RestrictedLiveStatus.MANUAL_CLOSE_REQUIRED
        ),
        L43EffectOutcome.EFFECT_UNKNOWN: RestrictedLiveStatus.EFFECT_UNKNOWN,
        L43EffectOutcome.REVIEW_ACCEPTED: RestrictedLiveStatus.REVIEW_ACCEPTED,
        L43EffectOutcome.BLOCKED: (
            RestrictedLiveStatus.AUTHORIZATION_MISSING
            if result.reason_code.endswith("AUTHORIZATION_MISSING")
            else RestrictedLiveStatus.BLOCKED
        ),
    }[result.outcome]
    return _observation(status, result.reason_code)


def _observation(
    status: RestrictedLiveStatus, reason_code: str
) -> L43RuntimeObservation:
    return L43RuntimeObservation(status=status, reason_code=reason_code)


__all__ = [
    "L43Runtime",
    "L43RuntimeObservation",
    "RestrictedLiveStatus",
    "build_production_l43_runtime",
]
