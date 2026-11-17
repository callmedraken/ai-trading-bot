"""Exact, read-only L43 post-placement broker reconciliation.

The reconciler shares the exhaustive account/position/order acquisition kernel
with pre-effect observation, then interprets the resulting facts for either the
exact newly bound intent or a later read-only settlement of that same durable
binding. The two paths have separate validation rules: only the initial path
requires a fresh zero-fill working receipt. Neither path contains review,
placement, cancellation, or retry authority. The potentially blocking provider
read runs outside the async event loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from contextlib import nullcontext
from datetime import datetime, timedelta
from decimal import Context, Decimal, localcontext
from typing import cast

from trading_bot.domain import OrderSide
from trading_bot.live_prototype.durable_state import (
    DurableState,
    IntentKind,
    IntentStatus,
    OrderObservation,
    OrderState,
    OrderStatus,
    ReconciliationSnapshot,
)
from trading_bot.live_prototype.l43_effect_operator import (
    L43EffectStage,
    L43PostEffectFacts,
)
from trading_bot.live_prototype.l43_pre_effect_observation import (
    _ACCOUNT_TTL,
    _ORDERS_TTL,
    _POSITION_TTL,
    L43PlanKind,
    L43PreEffectBlocker,
    L43PreEffectDependencies,
    L43PreEffectPlan,
    _BrokerSnapshot,
    _clock,
    _Counters,
    _decimal_text,
    _read_broker_snapshot,
    _require_fresh,
)
from trading_bot.live_prototype.l43_production_owner import (
    L43ContinuityResult,
    L43Provenance,
    L43SourceIdentity,
    Q62JournalOrigin,
)
from trading_bot.live_prototype.l43_provider_contracts import (
    L43DollarAmountFact,
    L43ExecutionFact,
    L43OrderFact,
    L43PlacementReceipt,
    L43TransportError,
)
from trading_bot.live_prototype.l43_state import origin_anchor_from_q62

_ZERO = Decimal("0")
_EXECUTION_ID = re.compile(r"[A-Za-z0-9_-]{1,256}\Z")
_ARITHMETIC = Context(prec=256, Emin=-999999, Emax=999999)
_MAX_EXECUTIONS_PER_ORDER = 10_000
_PROVIDER_STATES: dict[str, OrderStatus] = {
    "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELED,
    "cancelled": OrderStatus.CANCELED,
    "rejected": OrderStatus.REJECTED,
    "partially_filled": OrderStatus.PARTIAL,
    "new": OrderStatus.WORKING,
    "queued": OrderStatus.WORKING,
    "confirmed": OrderStatus.WORKING,
    "unconfirmed": OrderStatus.WORKING,
    "open": OrderStatus.WORKING,
    "pending": OrderStatus.WORKING,
    "submitted": OrderStatus.WORKING,
    "pending_cancelled": OrderStatus.WORKING,
}
_TERMINAL_INTENT_STATUSES = frozenset(
    {IntentStatus.FILLED, IntentStatus.CANCELED, IntentStatus.REJECTED}
)


class L43ExactPostEffectReconciler:
    """Read once and prove exact post-placement order and position facts."""

    __slots__ = ("_dependencies",)

    def __init__(self, dependencies: L43PreEffectDependencies) -> None:
        if type(dependencies) is not L43PreEffectDependencies:
            raise TypeError("post-effect reconciler requires exact L43 dependencies")
        self._dependencies = dependencies

    async def reconcile(
        self,
        *,
        stage: L43EffectStage,
        plan: L43PreEffectPlan,
        intent_id: str,
        provider_order_id: str,
        known_state: object,
    ) -> L43PostEffectFacts:
        """Run a single bounded read in a worker thread; failures are sanitized."""

        try:
            return await asyncio.to_thread(
                self._reconcile_initial_sync,
                stage=stage,
                plan=plan,
                intent_id=intent_id,
                provider_order_id=provider_order_id,
                known_state=known_state,
            )
        except Exception:
            raise L43TransportError("L43_POST_EFFECT_RECONCILIATION_FAILED") from None

    async def settle_bound_order(
        self,
        *,
        stage: L43EffectStage,
        intent_id: str,
        provider_order_id: str,
        known_state: object,
    ) -> L43PostEffectFacts:
        """Settle one already-bound order using reads only.

        This path deliberately accepts no detached effect plan.  It binds to
        the current durable state and the provider ID already stored there,
        then reuses the same source-continuity and exhaustive account/position/
        SPY-order read kernel as the initial post-placement path.
        """

        try:
            return await asyncio.to_thread(
                self._settle_bound_order_sync,
                stage=stage,
                intent_id=intent_id,
                provider_order_id=provider_order_id,
                known_state=known_state,
            )
        except Exception:
            raise L43TransportError("L43_BOUND_ORDER_SETTLEMENT_FAILED") from None

    def _reconcile_initial_sync(
        self,
        *,
        stage: L43EffectStage,
        plan: L43PreEffectPlan,
        intent_id: str,
        provider_order_id: str,
        known_state: object,
    ) -> L43PostEffectFacts:
        dependencies = self._dependencies
        origin = dependencies.origin
        if type(stage) is not L43EffectStage:
            raise ValueError("effect stage is invalid")
        if type(plan) is not L43PreEffectPlan:
            raise ValueError("effect plan is invalid")
        if type(known_state) is not DurableState:
            raise ValueError("durable state is invalid")
        L43PlacementReceipt(provider_order_id)
        state = cast(DurableState, known_state)
        target = _validate_bound_state(
            stage=stage,
            plan=plan,
            intent_id=intent_id,
            provider_order_id=provider_order_id,
            state=state,
            origin=origin,
        )
        initial_source = dependencies.source_reader()
        if type(initial_source) is not L43SourceIdentity or (
            initial_source != plan.current_source
        ):
            raise ValueError("current executable source differs from effect plan")

        reader = dependencies.robinhood_builder()
        scope = (
            dependencies.read_operation_scope_factory(reader)
            if dependencies.read_operation_scope_factory is not None
            else nullcontext()
        )
        with scope:
            broker = _read_broker_snapshot(
                reader,
                dependencies=dependencies,
                origin=origin,
                counters=_Counters(),
            )
        final_as_of = _clock(dependencies.clock)
        _require_current_freshness(broker, final_as_of, plan.observation_as_of)
        if broker.account.fingerprint != plan.account_fingerprint:
            raise ValueError("current account differs from effect plan")
        if broker.account.fingerprint != origin.runtime_identity.account_fingerprint:
            raise ValueError("current account differs from canonical Q62")
        if not _bounded_decimal(broker.spy_position_quantity):
            raise ValueError("SPY position quantity is outside its bounded domain")
        if not _bounded_decimal(broker.spy_sellable_quantity):
            raise ValueError("SPY sellable quantity is outside its bounded domain")

        state_orders = _bound_orders_by_provider_id(state)
        if len(broker.spy_orders) != len(state_orders):
            raise ValueError("account-wide SPY order set differs from durable state")
        observations: list[OrderObservation] = []
        observed_by_intent: dict[str, OrderObservation] = {}
        for order in broker.spy_orders:
            durable_order = state_orders.get(order.order_id)
            if durable_order is None:
                raise ValueError("account-wide SPY result contains an unrelated order")
            observation = _normalize_order(
                order,
                durable_order,
                is_new_target=durable_order is target,
            )
            observations.append(observation)
            observed_by_intent[durable_order.intent_id] = observation

        if set(observed_by_intent) != {
            order.intent_id for order in (state.entry, state.exit) if order is not None
        }:
            raise ValueError("bound durable order coverage is incomplete")
        expected_position = _expected_position(state, observed_by_intent)
        if broker.spy_position_quantity != expected_position:
            raise ValueError("broker SPY position differs from observed owned fills")
        snapshot = ReconciliationSnapshot(
            identity=origin.runtime_identity,
            observed_position=broker.spy_position_quantity,
            orders=tuple(sorted(observations, key=lambda item: item.local_intent_id)),
        )
        final_source = dependencies.source_reader()
        if (
            type(final_source) is not L43SourceIdentity
            or final_source != initial_source
        ):
            raise ValueError("executable source changed during reconciliation")
        evidence_sha256 = _post_effect_evidence_digest(
            stage=stage,
            plan=plan,
            intent_id=intent_id,
            provider_order_id=provider_order_id,
            state=state,
            broker=broker,
            snapshot=snapshot,
            final_as_of=final_as_of,
        )
        return L43PostEffectFacts(
            account_fingerprint=broker.account.fingerprint,
            snapshot=snapshot,
            positions_digest=broker.positions_digest,
            orders_digest=broker.orders_digest,
            order_scope_digest=broker.order_scope_digest,
            evidence_sha256=evidence_sha256,
            all_relevant_orders_proven=True,
        )

    def _settle_bound_order_sync(
        self,
        *,
        stage: L43EffectStage,
        intent_id: str,
        provider_order_id: str,
        known_state: object,
    ) -> L43PostEffectFacts:
        dependencies = self._dependencies
        origin = dependencies.origin
        if type(stage) is not L43EffectStage:
            raise ValueError("effect stage is invalid")
        if type(known_state) is not DurableState:
            raise ValueError("durable state is invalid")
        L43PlacementReceipt(provider_order_id)
        state = cast(DurableState, known_state)
        target = _validate_bound_settlement_state(
            stage=stage,
            intent_id=intent_id,
            provider_order_id=provider_order_id,
            state=state,
            origin=origin,
        )
        current_source, continuity = _current_source_continuity(dependencies, origin)

        reader = dependencies.robinhood_builder()
        scope = (
            dependencies.read_operation_scope_factory(reader)
            if dependencies.read_operation_scope_factory is not None
            else nullcontext()
        )
        with scope:
            broker = _read_broker_snapshot(
                reader,
                dependencies=dependencies,
                origin=origin,
                counters=_Counters(),
            )
        final_as_of = _clock(dependencies.clock)
        _require_current_freshness(broker, final_as_of, None)
        if broker.account.fingerprint != origin.runtime_identity.account_fingerprint:
            raise ValueError("current account differs from canonical Q62")
        if not _bounded_decimal(broker.spy_position_quantity):
            raise ValueError("SPY position quantity is outside its bounded domain")
        if not _bounded_decimal(broker.spy_sellable_quantity):
            raise ValueError("SPY sellable quantity is outside its bounded domain")

        state_orders = _bound_orders_by_provider_id(state)
        if len(broker.spy_orders) != len(state_orders):
            raise ValueError("account-wide SPY order set differs from durable state")
        observations: list[OrderObservation] = []
        observed_by_intent: dict[str, OrderObservation] = {}
        for order in broker.spy_orders:
            durable_order = state_orders.get(order.order_id)
            if durable_order is None:
                raise ValueError("account-wide SPY result contains an unrelated order")
            observation = _normalize_order(
                order,
                durable_order,
                is_new_target=False,
            )
            observations.append(observation)
            observed_by_intent[durable_order.intent_id] = observation

        if set(observed_by_intent) != {
            order.intent_id for order in (state.entry, state.exit) if order is not None
        }:
            raise ValueError("bound durable order coverage is incomplete")
        expected_position = _expected_position(state, observed_by_intent)
        if broker.spy_position_quantity != expected_position:
            raise ValueError("broker SPY position differs from observed owned fills")
        snapshot = ReconciliationSnapshot(
            identity=origin.runtime_identity,
            observed_position=broker.spy_position_quantity,
            orders=tuple(sorted(observations, key=lambda item: item.local_intent_id)),
        )
        final_source = dependencies.source_reader()
        if (
            type(final_source) is not L43SourceIdentity
            or final_source != current_source
            or continuity.current != final_source
        ):
            raise ValueError("executable source changed during settlement")
        evidence_sha256 = _settlement_evidence_digest(
            stage=stage,
            intent_id=intent_id,
            provider_order_id=provider_order_id,
            state=state,
            source=current_source,
            broker=broker,
            snapshot=snapshot,
            final_as_of=final_as_of,
        )
        if target.intent_id != intent_id:
            raise ValueError("settlement target changed during reconciliation")
        return L43PostEffectFacts(
            account_fingerprint=broker.account.fingerprint,
            snapshot=snapshot,
            positions_digest=broker.positions_digest,
            orders_digest=broker.orders_digest,
            order_scope_digest=broker.order_scope_digest,
            evidence_sha256=evidence_sha256,
            all_relevant_orders_proven=True,
        )


def _validate_bound_state(
    *,
    stage: L43EffectStage,
    plan: L43PreEffectPlan,
    intent_id: str,
    provider_order_id: str,
    state: DurableState,
    origin: Q62JournalOrigin,
) -> OrderState:
    identity = origin.runtime_identity
    if (
        state.identity != identity
        or state.l43_origin != origin_anchor_from_q62(origin)
        or plan.continuity.origin != origin
        or plan.continuity.current != plan.current_source
        or plan.continuity.provenance != plan.provenance
        or not plan.provenance.matches(identity)
        or plan.reconciliation_snapshot.identity != identity
        or plan.account_fingerprint != identity.account_fingerprint
        or state.last_sequence != plan.state_last_sequence + 3
        or state.journal_hash == plan.state_journal_sha256
        or state.reconciled
        or state.blocked_reason is not None
        or state.manual_close_required
        or state.sell_review_pending
    ):
        raise ValueError("durable state differs from canonical effect plan")
    if state.expected_position != plan.reconciliation_snapshot.observed_position:
        raise ValueError("durable pre-fill position differs from effect plan")

    if stage is L43EffectStage.ENTRY_PLACEMENT:
        if plan.kind is not L43PlanKind.ENTRY or plan.requested_entry_risk is None:
            raise ValueError("entry effect has no matching entry plan")
        target = state.entry
        if (
            target is None
            or state.exit is not None
            or target.kind is not IntentKind.ENTRY
            or target.requested_dollars != plan.requested_entry_risk
            or target.requested_quantity is not None
            or state.entries_used != 1
            or state.exits_used != 0
            or state.baseline_quantity != plan.reconciliation_snapshot.observed_position
        ):
            raise ValueError("bound entry intent differs from exact effect plan")
    elif stage is L43EffectStage.SELL_PLACEMENT:
        proposal = plan.sell_proposal
        target = state.exit
        if (
            plan.kind is not L43PlanKind.EXACT_OWNED_SELL_REVIEW
            or proposal is None
            or target is None
            or target.kind is not IntentKind.EXIT
            or target.requested_quantity != proposal.placement_arguments.quantity
            or target.requested_dollars is not None
            or state.entry is None
            or state.entry.status not in _TERMINAL_INTENT_STATUSES
            or state.entries_used != 1
            or state.exits_used != 1
        ):
            raise ValueError("bound sell intent differs from exact effect plan")
    else:
        raise ValueError("unsupported post-effect stage")

    if (
        target.intent_id != intent_id
        or target.provider_order_id != provider_order_id
        or target.status is not IntentStatus.WORKING
        or target.cumulative_quantity != _ZERO
        or target.cumulative_notional != _ZERO
    ):
        raise ValueError("placement receipt does not bind a fresh working intent")
    if not _prior_order_observations_match(plan=plan, state=state, target=target):
        raise ValueError("prior terminal order facts differ from effect plan")
    return target


def _validate_bound_settlement_state(
    *,
    stage: L43EffectStage,
    intent_id: str,
    provider_order_id: str,
    state: DurableState,
    origin: Q62JournalOrigin,
) -> OrderState:
    """Validate only current durable identity for a later read-only settle."""

    identity = origin.runtime_identity
    if (
        state.identity != identity
        or state.l43_origin != origin_anchor_from_q62(origin)
        or state.manual_close is not None
        or state.sell_review_pending
    ):
        raise ValueError("durable state differs from canonical settlement origin")

    if stage is L43EffectStage.ENTRY_PLACEMENT:
        target = state.entry
        if (
            target is None
            or state.exit is not None
            or target.kind is not IntentKind.ENTRY
            or target.status not in {IntentStatus.WORKING, IntentStatus.PARTIAL}
            or target.requested_dollars is None
            or target.requested_quantity is not None
            or target.working_remainder != _ZERO
            or state.entries_used != 1
            or state.exits_used != 0
            or state.baseline_quantity != _ZERO
        ):
            raise ValueError("durable entry is not a pending settlement")
    elif stage is L43EffectStage.SELL_PLACEMENT:
        target = state.exit
        if (
            target is None
            or target.kind is not IntentKind.EXIT
            or target.status not in {IntentStatus.WORKING, IntentStatus.PARTIAL}
            or target.requested_quantity is None
            or target.requested_dollars is not None
            or state.entry is None
            or state.entry.status not in _TERMINAL_INTENT_STATUSES
            or state.entries_used != 1
            or state.exits_used != 1
            or state.owned_quantity <= _ZERO
        ):
            raise ValueError("durable sell is not a pending settlement")
        expected_remainder = (
            target.requested_quantity
            if target.status is IntentStatus.WORKING
            else _subtract(target.requested_quantity, target.cumulative_quantity)
        )
        if target.working_remainder != expected_remainder:
            raise ValueError("durable sell remainder differs from its exact binding")
    else:
        raise ValueError("unsupported settlement stage")

    if target.intent_id != intent_id or target.provider_order_id != provider_order_id:
        raise ValueError("settlement receipt differs from the exact durable binding")
    return target


def _current_source_continuity(
    dependencies: L43PreEffectDependencies,
    origin: Q62JournalOrigin,
) -> tuple[L43SourceIdentity, L43ContinuityResult]:
    try:
        source = dependencies.source_reader()
        if type(source) is not L43SourceIdentity:
            raise ValueError
        continuity = dependencies.continuity_owner.prove_continuity(
            origin=origin,
            current=source,
            provenance=L43Provenance(
                config_digest=origin.runtime_identity.config_digest,
                binding_digest=origin.runtime_identity.binding_digest,
                account_fingerprint=origin.runtime_identity.account_fingerprint,
            ),
        )
    except Exception:
        raise ValueError(
            "current executable source continuity is unavailable"
        ) from None
    if (
        type(continuity) is not L43ContinuityResult
        or not continuity.accepted
        or continuity.origin != origin
        or continuity.current != source
        or not continuity.provenance.matches(origin.runtime_identity)
    ):
        raise ValueError("current executable source continuity is not accepted")
    return source, continuity


def _bound_orders_by_provider_id(state: DurableState) -> dict[str, OrderState]:
    result: dict[str, OrderState] = {}
    for order in (state.entry, state.exit):
        if order is None:
            continue
        provider_id = order.provider_order_id
        if type(provider_id) is not str or provider_id in result:
            raise ValueError("durable order ID is missing or duplicated")
        result[provider_id] = order
    return result


def _prior_order_observations_match(
    *,
    plan: L43PreEffectPlan,
    state: DurableState,
    target: OrderState,
) -> bool:
    expected = {
        item.local_intent_id: item for item in plan.reconciliation_snapshot.orders
    }
    previous = {
        order.intent_id: order
        for order in (state.entry, state.exit)
        if order is not None and order is not target
    }
    if set(expected) != set(previous):
        return False
    for intent_id, durable in previous.items():
        observation = expected[intent_id]
        if (
            durable.provider_order_id != observation.provider_order_id
            or durable.status.value != observation.status.value
            or durable.cumulative_quantity != observation.cumulative_quantity
            or durable.cumulative_notional != observation.cumulative_notional
            or durable.working_remainder != observation.working_remainder
            or durable.status not in _TERMINAL_INTENT_STATUSES
        ):
            return False
    return True


def _normalize_order(
    order: L43OrderFact,
    durable: OrderState,
    *,
    is_new_target: bool,
) -> OrderObservation:
    if (
        type(order) is not L43OrderFact
        or order.order_id != durable.provider_order_id
        or order.symbol != "SPY"
        or type(order.agent_initiated) is not bool
        or order.agent_initiated is not True
        or order.order_type != "market"
        or order.market_hours != "regular_hours"
        or order.time_in_force != "gfd"
        or order.trigger != "immediate"
    ):
        raise ValueError("provider order differs from exact L43 order contract")
    if order.side is not (
        OrderSide.BUY if durable.kind is IntentKind.ENTRY else OrderSide.SELL
    ):
        raise ValueError("provider order side differs from durable kind")
    if durable.status not in _TERMINAL_INTENT_STATUSES | {
        IntentStatus.WORKING,
        IntentStatus.PARTIAL,
    }:
        raise ValueError("durable order state is unresolved")
    if is_new_target and durable.status is not IntentStatus.WORKING:
        raise ValueError("new bound provider order is not in WORKING state")

    status = _PROVIDER_STATES.get(order.state.casefold())
    if status is None:
        raise ValueError("provider order state is outside the closed allowlist")
    quantity, notional = _execution_totals(order)
    if (
        quantity != order.cumulative_quantity
        or quantity < durable.cumulative_quantity
        or notional < durable.cumulative_notional
    ):
        raise ValueError("provider order fill facts are inconsistent or regressed")
    if durable.status in _TERMINAL_INTENT_STATUSES and (
        status.value != durable.status.value
        or quantity != durable.cumulative_quantity
        or notional != durable.cumulative_notional
    ):
        raise ValueError("terminal durable order identity or fills changed")

    if durable.kind is IntentKind.ENTRY:
        requested_dollars = durable.requested_dollars
        amount = order.dollar_based_amount
        if (
            requested_dollars is None
            or type(amount) is not L43DollarAmountFact
            or amount.currency_code != "USD"
            or not _bounded_decimal(amount.amount, positive=True)
            or amount.amount != requested_dollars
            or (
                order.requested_quantity is not None
                and not _bounded_decimal(order.requested_quantity)
            )
        ):
            raise ValueError("dollar entry amount differs from durable reservation")
        remainder = _ZERO
        if status is OrderStatus.WORKING and quantity != _ZERO:
            raise ValueError("working entry unexpectedly contains fills")
        if status in {OrderStatus.PARTIAL, OrderStatus.FILLED} and quantity <= _ZERO:
            raise ValueError("entry fill state has no confirmed fill")
    else:
        requested_quantity = durable.requested_quantity
        if (
            requested_quantity is None
            or not _bounded_decimal(requested_quantity, positive=True)
            or type(order.requested_quantity) is not Decimal
            or not _bounded_decimal(order.requested_quantity, positive=True)
            or order.requested_quantity != requested_quantity
            or order.dollar_based_amount is not None
            or quantity > requested_quantity
        ):
            raise ValueError("sell quantity differs from exact durable request")
        if status is OrderStatus.WORKING:
            if quantity != _ZERO:
                raise ValueError("working sell unexpectedly contains fills")
            remainder = requested_quantity
        elif status is OrderStatus.PARTIAL:
            if not _ZERO < quantity < requested_quantity:
                raise ValueError("partial sell is outside the exact residual range")
            remainder = _subtract(requested_quantity, quantity)
        elif status is OrderStatus.FILLED:
            if quantity != requested_quantity:
                raise ValueError("filled sell differs from exact requested shares")
            remainder = _ZERO
        else:
            remainder = _ZERO

    return OrderObservation(
        local_intent_id=durable.intent_id,
        provider_order_id=order.order_id,
        status=status,
        cumulative_quantity=quantity,
        cumulative_notional=notional,
        working_remainder=remainder,
    )


def _execution_totals(order: L43OrderFact) -> tuple[Decimal, Decimal]:
    if type(order.cumulative_quantity) is not Decimal or not _bounded_decimal(
        order.cumulative_quantity
    ):
        raise ValueError("provider cumulative quantity is invalid")
    if type(order.executions) is not tuple:
        raise ValueError("provider executions are not immutable")
    if len(order.executions) > _MAX_EXECUTIONS_PER_ORDER:
        raise ValueError("provider execution collection exceeds its bound")
    seen: set[str] = set()
    total_quantity = _ZERO
    total_notional = _ZERO
    with localcontext(_ARITHMETIC):
        for execution in order.executions:
            if type(execution) is not L43ExecutionFact:
                raise ValueError("provider execution fact is malformed")
            execution_id = execution.execution_id
            if (
                type(execution_id) is not str
                or _EXECUTION_ID.fullmatch(execution_id) is None
                or execution_id in seen
                or not _bounded_decimal(execution.quantity, positive=True)
                or not _bounded_decimal(execution.price, positive=True)
            ):
                raise ValueError("provider execution is invalid or duplicated")
            seen.add(execution_id)
            total_quantity += execution.quantity
            total_notional += _canonical_decimal(execution.quantity * execution.price)
    total_quantity = _canonical_decimal(total_quantity)
    total_notional = _canonical_decimal(total_notional)
    if not _bounded_decimal(total_quantity) or not _bounded_decimal(total_notional):
        raise ValueError("execution totals are outside the bounded Decimal domain")
    if total_quantity > _ZERO and total_notional <= _ZERO:
        raise ValueError("positive execution quantity has no positive notional")
    return total_quantity, total_notional


def _expected_position(
    state: DurableState,
    observations: dict[str, OrderObservation],
) -> Decimal:
    bought = _ZERO
    sold = _ZERO
    if state.entry is not None:
        observation = observations[state.entry.intent_id]
        bought = observation.cumulative_quantity
    if state.exit is not None:
        observation = observations[state.exit.intent_id]
        sold = observation.cumulative_quantity
    if not _bounded_decimal(state.baseline_quantity):
        raise ValueError("durable baseline position is outside its bounded domain")
    expected = _canonical_decimal(_add(state.baseline_quantity, bought))
    expected = _canonical_decimal(_subtract(expected, sold))
    if not _bounded_decimal(expected):
        raise ValueError("expected broker position is outside the bounded domain")
    return expected


def _require_current_freshness(
    broker: _BrokerSnapshot,
    final_as_of: datetime,
    plan_as_of: datetime | None,
) -> None:
    if plan_as_of is not None and final_as_of < plan_as_of:
        raise ValueError("post-effect observation clock is invalid")
    timestamps = (
        (broker.account_observed_at, _ACCOUNT_TTL, L43PreEffectBlocker.ACCOUNT_STALE),
        (
            broker.positions_observed_at,
            _POSITION_TTL,
            L43PreEffectBlocker.POSITION_STALE,
        ),
        (broker.orders_observed_at, _ORDERS_TTL, L43PreEffectBlocker.ORDERS_STALE),
    )
    observed = tuple(timestamp for timestamp, _, _ in timestamps)
    if observed != tuple(sorted(observed)):
        raise ValueError("broker observation timestamps are inconsistent")
    for timestamp, ttl, blocker in timestamps:
        if (
            type(timestamp) is not datetime
            or timestamp.tzinfo is None
            or timestamp.utcoffset() != timedelta(0)
            or (plan_as_of is not None and timestamp < plan_as_of)
        ):
            raise ValueError("broker factual snapshot is stale")
        _require_fresh(
            observed_at=timestamp,
            final_as_of=final_as_of,
            ttl=ttl,
            blocker=blocker,
        )


def _bounded_decimal(value: object, *, positive: bool = False) -> bool:
    if type(value) is not Decimal or not value.is_finite():
        return False
    parts = value.as_tuple()
    if (
        not -12 <= parts.exponent <= 12
        or len(parts.digits) > 64
        or value.adjusted() > 12
    ):
        return False
    return value > _ZERO if positive else value >= _ZERO


def _add(left: Decimal, right: Decimal) -> Decimal:
    with localcontext(_ARITHMETIC):
        return left + right


def _subtract(left: Decimal, right: Decimal) -> Decimal:
    with localcontext(_ARITHMETIC):
        return left - right


def _canonical_decimal(value: Decimal) -> Decimal:
    if value == _ZERO:
        return _ZERO
    parts = value.as_tuple()
    digits = list(parts.digits)
    exponent = parts.exponent
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    return Decimal((parts.sign, tuple(digits), exponent))


def _post_effect_evidence_digest(
    *,
    stage: L43EffectStage,
    plan: L43PreEffectPlan,
    intent_id: str,
    provider_order_id: str,
    state: DurableState,
    broker: _BrokerSnapshot,
    snapshot: ReconciliationSnapshot,
    final_as_of: datetime,
) -> str:
    material = (
        "ARCH147_L43_POST_EFFECT_FACTS_V1",
        stage.value,
        plan.binding_sha256,
        intent_id,
        provider_order_id,
        state.identity.to_record(),
        state.last_sequence,
        state.journal_hash,
        broker.account.fingerprint,
        broker.positions_digest,
        broker.orders_digest,
        broker.order_scope_digest,
        broker.order_scope_evidence_digest,
        broker.positions_observation_digest,
        broker.orders_observation_digest,
        broker.account_observed_at.isoformat(),
        broker.positions_observed_at.isoformat(),
        broker.orders_observed_at.isoformat(),
        final_as_of.isoformat(),
        snapshot.identity.to_record(),
        _decimal_text(snapshot.observed_position),
        tuple(
            (
                order.local_intent_id,
                order.provider_order_id,
                order.status.value,
                _decimal_text(order.cumulative_quantity),
                _decimal_text(order.cumulative_notional),
                _decimal_text(order.working_remainder),
            )
            for order in snapshot.orders
        ),
    )
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _settlement_evidence_digest(
    *,
    stage: L43EffectStage,
    intent_id: str,
    provider_order_id: str,
    state: DurableState,
    source: L43SourceIdentity,
    broker: _BrokerSnapshot,
    snapshot: ReconciliationSnapshot,
    final_as_of: datetime,
) -> str:
    material = (
        "ARCH147_L43_BOUND_ORDER_SETTLEMENT_FACTS_V1",
        stage.value,
        intent_id,
        provider_order_id,
        state.identity.to_record(),
        state.last_sequence,
        state.journal_hash,
        source.source_head,
        source.source_tree,
        broker.account.fingerprint,
        broker.positions_digest,
        broker.orders_digest,
        broker.order_scope_digest,
        broker.order_scope_evidence_digest,
        broker.positions_observation_digest,
        broker.orders_observation_digest,
        broker.account_observed_at.isoformat(),
        broker.positions_observed_at.isoformat(),
        broker.orders_observed_at.isoformat(),
        final_as_of.isoformat(),
        snapshot.identity.to_record(),
        _decimal_text(snapshot.observed_position),
        tuple(
            (
                order.local_intent_id,
                order.provider_order_id,
                order.status.value,
                _decimal_text(order.cumulative_quantity),
                _decimal_text(order.cumulative_notional),
                _decimal_text(order.working_remainder),
            )
            for order in snapshot.orders
        ),
    )
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["L43ExactPostEffectReconciler"]
