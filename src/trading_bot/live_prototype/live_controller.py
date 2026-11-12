"""Serialized, effect-disabled L42 ownership controller.

The controller owns ordering around the durable store. It never calls a
provider; callers must invoke a provider only after ``prepare_invocation``
returns, and must record uncertainty when the outcome is not known.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from threading import RLock

from trading_bot.live_prototype.durable_state import (
    DurableState,
    DurableStateStore,
    IntentKind,
    ManualCloseRequired,
    OrderState,
    ReconciliationSnapshot,
)
from trading_bot.live_prototype.tiny_live_policy import ManualCloseTrigger


@dataclass(frozen=True, slots=True)
class PreparedInvocation:
    """A durable, one-use permit returned immediately before a provider call."""

    intent_id: str
    kind: IntentKind
    requested_dollars: Decimal | None
    requested_quantity: Decimal | None
    authority_sha256: str | None = None


class LiveController:
    """Serialize durable intent transitions and expose no provider boundary."""

    def __init__(self, store: DurableStateStore) -> None:
        if type(store) is not DurableStateStore:
            raise TypeError("exact durable state store required")
        self._store = store
        self._lock = RLock()

    @property
    def state(self) -> DurableState:
        with self._lock:
            return self._store.state

    def reserve_entry(self, requested_dollars: Decimal) -> str:
        with self._lock:
            return self._store.reserve_entry(requested_dollars)

    def reserve_exit(
        self,
        requested_quantity: Decimal,
        *,
        authority_sha256: str | None = None,
    ) -> str:
        with self._lock:
            return self._store.reserve_exit(
                requested_quantity,
                authority_sha256=authority_sha256,
            )

    def begin_sell_review(
        self,
        *,
        proposal_sha256: str,
        arguments_sha256: str,
        session_token: object,
    ) -> None:
        with self._lock:
            self._store.begin_sell_review(
                proposal_sha256=proposal_sha256,
                arguments_sha256=arguments_sha256,
                session_token=session_token,
            )

    def accept_sell_review(
        self,
        *,
        proposal_sha256: str,
        arguments_sha256: str,
        review_evidence_sha256: str,
        session_token: object,
    ) -> None:
        with self._lock:
            self._store.accept_sell_review(
                proposal_sha256=proposal_sha256,
                arguments_sha256=arguments_sha256,
                review_evidence_sha256=review_evidence_sha256,
                session_token=session_token,
            )

    def require_manual_close(
        self,
        *,
        trigger: ManualCloseTrigger,
        effect_evidence_sha256: str,
    ) -> ManualCloseRequired:
        with self._lock:
            return self._store.require_manual_close(
                trigger=trigger,
                effect_evidence_sha256=effect_evidence_sha256,
            )

    def prepare_invocation(self, intent_id: str) -> PreparedInvocation:
        """Persist MAY_HAVE_OCCURRED before a caller performs any effect."""

        with self._lock:
            intent = _find_intent(self._store.state, intent_id)
            if intent is None:
                raise ValueError("intent is not present")
            self._store.mark_may_have_occurred(intent_id)
            return PreparedInvocation(
                intent_id=intent.intent_id,
                kind=intent.kind,
                requested_dollars=intent.requested_dollars,
                requested_quantity=intent.requested_quantity,
                authority_sha256=intent.authority_sha256,
            )

    def bind_provider_order(self, intent_id: str, provider_order_id: str) -> None:
        with self._lock:
            self._store.bind_provider_order(intent_id, provider_order_id)

    def mark_unknown(self, intent_id: str) -> None:
        with self._lock:
            self._store.mark_unknown(intent_id)

    def reconcile(self, snapshot: ReconciliationSnapshot) -> DurableState:
        with self._lock:
            return self._store.reconcile(snapshot)


def _find_intent(state: DurableState, intent_id: str) -> OrderState | None:
    for intent in (state.entry, state.exit):
        if intent is not None and intent.intent_id == intent_id:
            return intent
    return None


__all__ = ["LiveController", "PreparedInvocation"]
