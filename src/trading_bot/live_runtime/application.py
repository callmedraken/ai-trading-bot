"""One fakeable, effect-free Architecture 148 cycle and its admission gates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import (
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, Position, Symbol, TradeProposal
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.risk import RiskContext, RiskDecision, RiskManager, RiskOutcome

from .identity import canonical_decimal, create_order_intent
from .models import (
    SQQQ,
    TQQQ,
    TRADED_SYMBOLS,
    UNIVERSE_SYMBOLS,
    AccountFacts,
    AdmissionBlocker,
    ApprovalRequestStatus,
    ApprovalRequiredReceipt,
    BrokerSnapshot,
    CycleResult,
    CycleStatus,
    EffectProposal,
    IntentKind,
    IntentLifecycle,
    LogicalOrderIntent,
    MarketQuality,
    MarketRegime,
    MarketSnapshot,
    OrderState,
    OwnedPositionRecord,
    PriceObservation,
    ProviderApprovalFact,
    RuntimeState,
    RuntimeStateStore,
    SourceIdentity,
    TargetPosition,
    decimal_sum_equals,
)
from .strategy import (
    HardStopPolicy,
    SessionDecision,
    SessionReason,
    analyze_market,
    confirmed_regime_exit,
    session_decision,
)

_MAX_FACT_AGE = timedelta(seconds=30)
_MAX_PRICE_AGE = timedelta(seconds=15)
_RISK_NAMESPACE = UUID("88698e5d-1e48-5a86-9870-c4c1088b0f13")


@dataclass(frozen=True, slots=True)
class CycleRequest:
    as_of: datetime
    owner_id: UUID
    source_identity: SourceIdentity
    session_fingerprint: str
    expected_state_revision: int
    market: MarketSnapshot
    broker: BrokerSnapshot

    def __post_init__(self) -> None:
        if not isinstance(self.as_of, datetime) or self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if not isinstance(self.owner_id, UUID):
            raise TypeError("owner_id must be UUID")
        if not isinstance(self.source_identity, SourceIdentity):
            raise TypeError("source_identity must be SourceIdentity")
        if (
            not isinstance(self.session_fingerprint, str)
            or not self.session_fingerprint
        ):
            raise ValueError("session_fingerprint must be nonblank")
        if (
            not isinstance(self.expected_state_revision, int)
            or isinstance(self.expected_state_revision, bool)
            or self.expected_state_revision < 0
        ):
            raise ValueError("expected_state_revision must be a nonnegative integer")
        if not isinstance(self.market, MarketSnapshot):
            raise TypeError("market must be MarketSnapshot")
        if not isinstance(self.broker, BrokerSnapshot):
            raise TypeError("broker must be BrokerSnapshot")


class ReconciliationStatus(StrEnum):
    RECONCILED_ENTRY = "RECONCILED_ENTRY"
    RECONCILED_FLAT = "RECONCILED_FLAT"
    MATCHED_PENDING_BLOCKED = "MATCHED_PENDING_BLOCKED"
    NO_MATCH_BLOCKED = "NO_MATCH_BLOCKED"
    DUPLICATE_MATCHES_BLOCKED = "DUPLICATE_MATCHES_BLOCKED"
    FACT_MISMATCH_BLOCKED = "FACT_MISMATCH_BLOCKED"
    POSITION_MISMATCH_BLOCKED = "POSITION_MISMATCH_BLOCKED"
    IDENTITY_MISMATCH_BLOCKED = "IDENTITY_MISMATCH_BLOCKED"
    PARTIAL_FILL_BLOCKED = "PARTIAL_FILL_BLOCKED"
    TERMINAL_NONFILL_BLOCKED = "TERMINAL_NONFILL_BLOCKED"


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    status: ReconciliationStatus
    next_state: RuntimeState | None = None
    settled_exit: bool = False


class CycleState(StrEnum):
    READY = "READY"
    FLAT = "FLAT"
    HOLDING = "HOLDING"
    EXIT_REQUIRED = "EXIT_REQUIRED"
    BLOCKED = "BLOCKED"


class CycleApplicationService:
    """Plan one cycle from supplied facts; never opens providers or executes."""

    def __init__(
        self,
        *,
        risk_manager: RiskManager,
        state_store: RuntimeStateStore,
        session_authority: NYSEPublishedRegularSessionAuthority | None = None,
        hard_stop: HardStopPolicy | None = None,
    ) -> None:
        if not isinstance(risk_manager, RiskManager):
            raise TypeError("risk_manager must be a RiskManager")
        if not callable(getattr(state_store, "load", None)) or not callable(
            getattr(state_store, "compare_and_swap", None)
        ):
            raise TypeError("state_store must implement load and compare_and_swap")
        self._risk_manager = risk_manager
        self._state_store = state_store
        self._session_authority = (
            session_authority or NYSEPublishedRegularSessionAuthority()
        )
        self._hard_stop = hard_stop or HardStopPolicy()

    def run_cycle(self, request: CycleRequest) -> CycleResult:
        """Return a sanitized status and optional proposal, with zero effects."""

        if not isinstance(request, CycleRequest):
            raise TypeError("request must be CycleRequest")
        as_of = request.as_of.astimezone(UTC)
        signal = analyze_market(request.market, authority=self._session_authority)
        session = session_decision(as_of, authority=self._session_authority)
        blockers: list[AdmissionBlocker] = []
        if request.market.as_of != as_of:
            blockers.append(AdmissionBlocker.MARKET_DATA_INVALID)

        try:
            state = self._state_store.load(request.owner_id, request.source_identity)
        except Exception:
            state = None
            blockers.append(AdmissionBlocker.STATE_UNAVAILABLE)
        if state is None or not isinstance(state, RuntimeState):
            state = None
            blockers.append(AdmissionBlocker.STATE_UNAVAILABLE)
        elif (
            state.owner_id != request.owner_id
            or state.source_identity != request.source_identity
        ):
            blockers.append(AdmissionBlocker.STATE_IDENTITY_MISMATCH)
        elif state.revision != request.expected_state_revision:
            blockers.append(AdmissionBlocker.STATE_CONFLICT)
        elif state.session_fingerprint != request.session_fingerprint:
            blockers.append(AdmissionBlocker.SESSION_IDENTITY_MISMATCH)
        elif not _state_well_formed(state):
            blockers.append(AdmissionBlocker.STATE_IDENTITY_MISMATCH)
            state = None
        elif state.account_fingerprint != request.broker.account.fingerprint:
            blockers.append(AdmissionBlocker.ACCOUNT_IDENTITY_MISMATCH)

        if request.broker.source_identity != request.source_identity:
            blockers.append(AdmissionBlocker.SOURCE_IDENTITY_MISMATCH)
        if request.broker.session_fingerprint != request.session_fingerprint:
            blockers.append(AdmissionBlocker.SESSION_IDENTITY_MISMATCH)
        if request.broker.state_revision != request.expected_state_revision:
            blockers.append(AdmissionBlocker.STATE_CONFLICT)

        blockers.extend(_market_blockers(signal.quality))
        blockers.extend(_snapshot_blockers(request.broker, as_of))
        if session.schedule is None:
            blockers.append(AdmissionBlocker.SESSION_UNAVAILABLE)

        state, reconciliation_blockers, settled_exit, state_advanced = (
            self._reconcile_pending(request, state, as_of)
        )
        blockers.extend(reconciliation_blockers)
        if state_advanced:
            blockers.append(AdmissionBlocker.STATE_ADVANCED_THIS_CYCLE)
        if state is not None:
            blockers.extend(_state_blockers(state))
        actual, owned_record, position_blockers = _actual_position(
            request.broker, state
        )
        blockers.extend(position_blockers)
        blockers = _unique(blockers)
        mandatory_exit_reasons: list[AdmissionBlocker] = []
        action: IntentKind | None = None
        desired = actual
        protective_stop_ready = False
        held_price: PriceObservation | None = None

        has_traded_position_fact = any(
            symbol in request.broker.positions for symbol in TRADED_SYMBOLS
        )
        if session.force_flat and (
            actual is not TargetPosition.FLAT or has_traded_position_fact
        ):
            mandatory_exit_reasons.append(AdmissionBlocker.FORCED_FLAT)

        if actual is None:
            desired = TargetPosition.FLAT
        elif actual is not TargetPosition.FLAT and owned_record is None:
            desired = TargetPosition.FLAT
        elif actual is not TargetPosition.FLAT and owned_record is not None:
            symbol = actual.symbol
            assert symbol is not None
            threshold = self._hard_stop.threshold(
                owned_record.average_entry_fill, owned_record.hard_stop_price
            )
            if threshold != owned_record.hard_stop_price:
                blockers.append(AdmissionBlocker.STATE_CONFLICT)
                blockers = _unique(blockers)
            coverage, coverage_blocker = _stop_coverage(
                request.broker, state, owned_record, threshold, as_of
            )
            protective_stop_ready = coverage
            if coverage_blocker is not None:
                blockers.append(coverage_blocker)
                blockers = _unique(blockers)
            held_price = request.market.execution_prices.get(symbol)
            price_is_fresh = held_price is not None and _fresh(
                held_price.observed_at, as_of, _MAX_PRICE_AGE
            )
            if not price_is_fresh:
                blockers.append(AdmissionBlocker.PRICE_STALE)
                blockers = _unique(blockers)
            if (
                held_price is not None
                and price_is_fresh
                and self._hard_stop.is_breached(held_price.price, threshold)
            ):
                mandatory_exit_reasons.append(AdmissionBlocker.STOP_BREACH)
            if _requires_safety_flatten(blockers, signal.quality):
                mandatory_exit_reasons.append(AdmissionBlocker.SAFETY_FAILURE)
            if confirmed_regime_exit(signal, actual):
                mandatory_exit_reasons.append(AdmissionBlocker.REGIME_EXIT)
            if session.force_flat:
                mandatory_exit_reasons.append(AdmissionBlocker.FORCED_FLAT)
            mandatory_exit_reasons = _priority_exit_reasons(mandatory_exit_reasons)
            if mandatory_exit_reasons:
                desired = TargetPosition.FLAT
                action = IntentKind.EXIT
            elif not coverage:
                action = IntentKind.PROTECTIVE_STOP
                desired = actual
            else:
                desired = actual
        else:
            if session.force_flat:
                blockers.append(AdmissionBlocker.FORCED_FLAT)
                blockers = _unique(blockers)
            if signal.entry_confirmation is MarketRegime.BULLISH:
                desired = TargetPosition.TQQQ
            elif signal.entry_confirmation is MarketRegime.BEARISH:
                desired = TargetPosition.SQQQ
            if desired is not TargetPosition.FLAT:
                if settled_exit:
                    blockers.append(AdmissionBlocker.SAME_CYCLE_FLIP_BLOCKED)
                    desired = TargetPosition.FLAT
                    blockers = _unique(blockers)
                elif session.can_enter:
                    action = IntentKind.ENTRY
                else:
                    blockers.append(AdmissionBlocker.ENTRY_WINDOW_CLOSED)
                    desired = TargetPosition.FLAT
                    blockers = _unique(blockers)

        proposal: EffectProposal | None = None
        selected_intent: LogicalOrderIntent | None = None
        risk_decision: RiskDecision | None = None
        if action is not None and state is not None:
            action_blockers = _action_blockers(
                action,
                blockers,
                mandatory_exit_reasons,
                signal,
                request.broker,
                owned_record,
                actual,
                session,
            )
            if not action_blockers:
                selected_intent, risk_decision, creation_blockers = self._make_intent(
                    request,
                    state,
                    action,
                    desired,
                    actual,
                    owned_record,
                    as_of,
                )
                action_blockers.extend(creation_blockers)
                if selected_intent is not None and not creation_blockers:
                    gate, approval_required = _review_gate(
                        request.broker, selected_intent, as_of
                    )
                    if approval_required:
                        action_blockers.append(AdmissionBlocker.APPROVAL_REQUIRED)
                    elif gate is not None:
                        action_blockers.append(gate)
                    else:
                        persisted = self._persist_intent(state, selected_intent)
                        if persisted:
                            proposal = EffectProposal(
                                selected_intent,
                                "PROPOSED_FOR_LATER_ADAPTER",
                                execution_attempted=False,
                            )
                        else:
                            action_blockers.append(AdmissionBlocker.STATE_CONFLICT)
            blockers.extend(action_blockers)
            blockers = _unique(blockers)

        if mandatory_exit_reasons:
            cycle_state = CycleState.EXIT_REQUIRED
        elif blockers:
            cycle_state = CycleState.BLOCKED
        elif action is not None and proposal is not None:
            cycle_state = CycleState.READY
        elif actual is TargetPosition.FLAT:
            cycle_state = CycleState.FLAT
        elif action is None:
            cycle_state = CycleState.HOLDING
        else:
            cycle_state = CycleState.READY
        live_ready = (
            actual is not None
            and actual is not TargetPosition.FLAT
            and protective_stop_ready
            and not blockers
            and not mandatory_exit_reasons
        )
        status = CycleStatus(
            as_of=as_of,
            current_candidate=signal.current_candidate,
            entry_confirmation=signal.entry_confirmation,
            desired_position=desired,
            actual_position=actual,
            action=action,
            blockers=tuple(blockers),
            mandatory_exit_reasons=tuple(_unique(mandatory_exit_reasons)),
            protective_stop_ready=protective_stop_ready,
            live_ready=live_ready,
            state=cycle_state.value,
        )
        return CycleResult(signal, status, selected_intent, proposal)

    def _make_intent(
        self,
        request: CycleRequest,
        state: RuntimeState,
        action: IntentKind,
        desired: TargetPosition,
        actual: TargetPosition,
        owned_record: OwnedPositionRecord | None,
        as_of: datetime,
    ) -> tuple[LogicalOrderIntent | None, RiskDecision | None, list[AdmissionBlocker]]:
        blockers: list[AdmissionBlocker] = []
        if action is IntentKind.ENTRY:
            target_symbol = desired.symbol
            if target_symbol is None:
                return None, None, [AdmissionBlocker.POSITION_CONFLICT]
            price = request.market.execution_prices.get(target_symbol)
            if price is None or not _fresh(price.observed_at, as_of, _MAX_PRICE_AGE):
                return None, None, [AdmissionBlocker.PRICE_STALE]
            facts = request.broker.tradability[target_symbol]
            cash_limit = min(
                Decimal("10"),
                request.broker.account.cash,
                request.broker.account.buying_power,
                request.broker.account.unleveraged_buying_power,
            )
            if cash_limit <= 0:
                return None, None, [AdmissionBlocker.BUYING_POWER_UNSAFE]
            with localcontext(_fixed_context()):
                desired_quantity = cash_limit / price.price
                proposal_id = uuid5(
                    _RISK_NAMESPACE,
                    "\n".join(
                        (
                            "arch148-risk-proposal/v1",
                            request.owner_id.hex,
                            request.source_identity.head,
                            request.source_identity.tree,
                            str(state.next_sequence),
                            target_symbol.value,
                            canonical_decimal(desired_quantity),
                        )
                    ),
                )
                trade_proposal = TradeProposal(
                    proposal_id,
                    target_symbol,
                    OrderSide.BUY,
                    desired_quantity,
                    as_of,
                    "ARCH148_CONFIRMED_REGIME",
                )
                risk_decision = self._risk_manager.evaluate(
                    trade_proposal,
                    _risk_context(
                        request.broker.account, request.broker.positions, price, as_of
                    ),
                )
            if risk_decision.outcome is RiskOutcome.REJECTED:
                return None, risk_decision, [AdmissionBlocker.RISK_REJECTED]
            quantity = risk_decision.approved_quantity
            with localcontext(_fixed_context()):
                notional = quantity * price.price
            if notional > Decimal("10") or notional > cash_limit:
                return None, risk_decision, [AdmissionBlocker.RISK_REJECTED]
            fractional = quantity != quantity.to_integral_value(rounding=ROUND_DOWN)
            if fractional and facts.fractional_entry_supported is not True:
                blocker = (
                    AdmissionBlocker.TRADABILITY_UNKNOWN
                    if facts.fractional_entry_supported is None
                    else AdmissionBlocker.NOT_TRADABLE
                )
                return None, risk_decision, [blocker]
            if (
                facts.stop_market_supported is not True
                or facts.exact_stop_price_supported is not True
            ):
                return None, risk_decision, [AdmissionBlocker.STOP_INCOMPATIBLE]
            if fractional and facts.fractional_stop_supported is not True:
                return None, risk_decision, [AdmissionBlocker.STOP_INCOMPATIBLE]
            intent = create_order_intent(
                owner_id=request.owner_id,
                source_identity=request.source_identity,
                logical_sequence=state.next_sequence,
                kind=IntentKind.ENTRY,
                symbol=target_symbol,
                side=OrderSide.BUY,
                quantity=quantity,
                stop_price=None,
                created_at=as_of,
            )
        else:
            if owned_record is None or actual is TargetPosition.FLAT:
                return None, None, [AdmissionBlocker.FOREIGN_POSITION]
            target_symbol = owned_record.symbol
            position = request.broker.positions.get(target_symbol)
            price = request.market.execution_prices.get(target_symbol)
            if position is None or price is None:
                return None, None, [AdmissionBlocker.POSITION_CONFLICT]
            if not _fresh(price.observed_at, as_of, _MAX_PRICE_AGE):
                return None, None, [AdmissionBlocker.PRICE_STALE]
            if action is IntentKind.EXIT:
                side = OrderSide.SELL
                quantity = position.quantity
                stop_price = None
            else:
                side = OrderSide.SELL
                quantity = position.quantity
                stop_price = self._hard_stop.threshold(
                    owned_record.average_entry_fill, owned_record.hard_stop_price
                )
            proposal_id = uuid5(
                _RISK_NAMESPACE,
                "\n".join(
                    (
                        "arch148-risk-proposal/v1",
                        request.owner_id.hex,
                        request.source_identity.head,
                        request.source_identity.tree,
                        str(state.next_sequence),
                        action.value,
                        target_symbol.value,
                        canonical_decimal(quantity),
                    )
                ),
            )
            trade_proposal = TradeProposal(
                proposal_id,
                target_symbol,
                side,
                quantity,
                as_of,
                f"ARCH148_{action.value}",
            )
            with localcontext(_fixed_context()):
                risk_decision = self._risk_manager.evaluate(
                    trade_proposal,
                    _risk_context(
                        request.broker.account, request.broker.positions, price, as_of
                    ),
                )
            if (
                risk_decision.outcome is RiskOutcome.REJECTED
                or risk_decision.approved_quantity != position.quantity
            ):
                return None, risk_decision, [AdmissionBlocker.RISK_REJECTED]
            intent = create_order_intent(
                owner_id=request.owner_id,
                source_identity=request.source_identity,
                logical_sequence=state.next_sequence,
                kind=action,
                symbol=target_symbol,
                side=side,
                quantity=position.quantity,
                stop_price=stop_price,
                created_at=as_of,
            )
        existing, existing_blocker = _pending_intent(state, intent)
        if existing_blocker is not None:
            return None, risk_decision, [existing_blocker]
        return existing or intent, risk_decision, blockers

    def _persist_intent(
        self,
        state: RuntimeState,
        intent: LogicalOrderIntent,
    ) -> bool:
        existing = next(
            (item for item in state.intents if item.intent_id == intent.intent_id),
            None,
        )
        if existing is not None and existing == intent:
            return True
        if existing is not None:
            return False
        retired = tuple(
            replace(item, lifecycle=IntentLifecycle.SUPERSEDED)
            if item.lifecycle is IntentLifecycle.PROPOSED
            else item
            for item in state.intents
        )
        next_state = replace(
            state,
            revision=state.revision + 1,
            next_sequence=state.next_sequence + 1,
            intents=retired + (intent,),
        )
        try:
            return self._state_store.compare_and_swap(state.revision, next_state)
        except Exception:
            return False

    def _reconcile_pending(
        self,
        request: CycleRequest,
        state: RuntimeState | None,
        as_of: datetime,
    ) -> tuple[RuntimeState | None, list[AdmissionBlocker], bool, bool]:
        if state is None:
            return None, [], False, False
        if (
            request.owner_id != state.owner_id
            or request.source_identity != state.source_identity
            or request.expected_state_revision != state.revision
            or request.session_fingerprint != state.session_fingerprint
            or request.broker.account.fingerprint != state.account_fingerprint
            or request.broker.source_identity != state.source_identity
            or request.broker.session_fingerprint != state.session_fingerprint
            or request.broker.state_revision != state.revision
        ):
            return state, [], False, False
        approval_state, approval_blocker = _reconcile_approval_request(
            request, state, as_of
        )
        if approval_blocker is not None:
            return state, [approval_blocker], False, False
        if approval_state is not None:
            try:
                persisted = self._state_store.compare_and_swap(
                    state.revision, approval_state
                )
            except Exception:
                persisted = False
            if not persisted:
                return state, [AdmissionBlocker.STATE_CONFLICT], False, False
            return approval_state, [], False, True
        open_stop_state, stop_blocker = _reconcile_open_protective_stop(
            request, state, as_of
        )
        if stop_blocker is not None:
            return state, [stop_blocker], False, False
        if open_stop_state is not None:
            try:
                persisted = self._state_store.compare_and_swap(
                    state.revision, open_stop_state
                )
            except Exception:
                persisted = False
            if not persisted:
                return state, [AdmissionBlocker.STATE_CONFLICT], False, False
            return open_stop_state, [], False, True
        released_stop_state, release_blocker = _reconcile_terminal_stopped_order(
            request, state, as_of
        )
        if release_blocker is not None:
            return state, [release_blocker], False, False
        if released_stop_state is not None:
            try:
                persisted = self._state_store.compare_and_swap(
                    state.revision, released_stop_state
                )
            except Exception:
                persisted = False
            if not persisted:
                return state, [AdmissionBlocker.STATE_CONFLICT], False, False
            return released_stop_state, [], False, True
        filled_stop_state, filled_stop_blocker = _reconcile_filled_protective_stop(
            request, state, as_of
        )
        if filled_stop_blocker is not None:
            return state, [filled_stop_blocker], False, False
        if filled_stop_state is not None:
            try:
                persisted = self._state_store.compare_and_swap(
                    state.revision, filled_stop_state
                )
            except Exception:
                persisted = False
            if not persisted:
                return state, [AdmissionBlocker.STATE_CONFLICT], False, False
            return filled_stop_state, [], True, True
        pending = tuple(
            intent
            for intent in state.intents
            if intent.lifecycle
            in (IntentLifecycle.MAY_HAVE_OCCURRED, IntentLifecycle.UNKNOWN)
        )
        if not pending:
            return state, [], False, False
        if len(pending) != 1:
            return state, [AdmissionBlocker.UNKNOWN_INTENT], False, False
        result = reconcile_order_intent(
            pending[0],
            state,
            request.broker,
            expected_session_fingerprint=request.session_fingerprint,
            as_of=as_of,
        )
        if result.next_state is None:
            return state, [AdmissionBlocker.UNKNOWN_INTENT], False, False
        try:
            persisted = self._state_store.compare_and_swap(
                state.revision, result.next_state
            )
        except Exception:
            persisted = False
        if not persisted:
            return state, [AdmissionBlocker.STATE_CONFLICT], False, False
        return result.next_state, [], result.settled_exit, True


def reconcile_order_intent(
    intent: LogicalOrderIntent,
    state: RuntimeState,
    broker: BrokerSnapshot,
    *,
    expected_session_fingerprint: str,
    as_of: datetime,
) -> ReconciliationResult:
    """Recover only an exact terminal fill under the bound state/session scope."""

    if (
        not _state_well_formed(state)
        or not any(item == intent for item in state.intents)
        or intent.lifecycle
        not in (IntentLifecycle.MAY_HAVE_OCCURRED, IntentLifecycle.UNKNOWN)
        or intent.owner_id != state.owner_id
        or intent.source_identity != state.source_identity
        or state.session_fingerprint != expected_session_fingerprint
        or broker.source_identity != state.source_identity
        or broker.session_fingerprint != expected_session_fingerprint
        or broker.state_revision != state.revision
        or broker.account.fingerprint != state.account_fingerprint
        or not _fresh(broker.observed_at, as_of, _MAX_FACT_AGE)
        or not _fresh(broker.account.observed_at, as_of, _MAX_FACT_AGE)
        or any(
            not scope.all_agents
            or not scope.exhausted
            or scope.account_fingerprint != state.account_fingerprint
            or scope.symbols not in (None, (TQQQ, SQQQ))
            or not _fresh(scope.observed_at, as_of, _MAX_FACT_AGE)
            for scope in (broker.position_scope, broker.order_scope)
        )
    ):
        return ReconciliationResult(ReconciliationStatus.IDENTITY_MISMATCH_BLOCKED)
    matches = tuple(order for order in broker.orders if order.ref_id == intent.ref_id)
    if not matches:
        return ReconciliationResult(ReconciliationStatus.NO_MATCH_BLOCKED)
    if len(matches) != 1:
        return ReconciliationResult(ReconciliationStatus.DUPLICATE_MATCHES_BLOCKED)
    order = matches[0]
    if (
        order.account_fingerprint != state.account_fingerprint
        or (
            order.source_identity is not None
            and order.source_identity != intent.source_identity
        )
        or (order.intent_id is not None and order.intent_id != intent.intent_id)
        or order.kind is not intent.kind
        or order.symbol != intent.symbol
        or order.side is not intent.side
        or order.requested_quantity != intent.quantity
        or order.stop_price != intent.stop_price
        or not decimal_sum_equals(
            order.filled_quantity,
            order.remaining_quantity,
            order.requested_quantity,
        )
        or not _fresh(order.observed_at, as_of, _MAX_FACT_AGE)
    ):
        return ReconciliationResult(ReconciliationStatus.FACT_MISMATCH_BLOCKED)
    if order.state is OrderState.PARTIALLY_FILLED:
        return ReconciliationResult(ReconciliationStatus.PARTIAL_FILL_BLOCKED)
    if not order.state.terminal:
        return ReconciliationResult(ReconciliationStatus.MATCHED_PENDING_BLOCKED)
    if order.state is not OrderState.FILLED:
        return ReconciliationResult(ReconciliationStatus.TERMINAL_NONFILL_BLOCKED)
    if order.filled_quantity != intent.quantity or order.remaining_quantity != 0:
        return ReconciliationResult(ReconciliationStatus.PARTIAL_FILL_BLOCKED)

    positions = dict(state.positions)
    intents = tuple(
        replace(item, lifecycle=IntentLifecycle.RECONCILED)
        if item.intent_id == intent.intent_id
        else item
        for item in state.intents
    )
    if intent.kind is IntentKind.ENTRY:
        position = broker.positions.get(intent.symbol)
        if (
            intent.symbol in positions
            or position is None
            or position.quantity != intent.quantity
            or broker.position_owners.get(intent.symbol) != intent.intent_id
            or order.average_fill_price is None
            or position.average_cost != order.average_fill_price
            or any(
                symbol in broker.positions
                for symbol in TRADED_SYMBOLS
                if symbol != intent.symbol
            )
            or any(
                other.symbol in TRADED_SYMBOLS
                and not other.state.terminal
                and other != order
                for other in broker.orders
            )
        ):
            return ReconciliationResult(ReconciliationStatus.POSITION_MISMATCH_BLOCKED)
        record = OwnedPositionRecord(
            symbol=intent.symbol,
            entry_intent_id=intent.intent_id,
            quantity=position.quantity,
            average_entry_fill=position.average_cost,
            hard_stop_price=HardStopPolicy().threshold(position.average_cost),
        )
        positions[intent.symbol] = record
        result_status = ReconciliationStatus.RECONCILED_ENTRY
        settled_exit = False
    else:
        record = positions.get(intent.symbol)
        if (
            record is None
            or record.quantity != intent.quantity
            or intent.symbol in broker.positions
            or any(symbol in broker.positions for symbol in TRADED_SYMBOLS)
            or any(
                other.symbol in TRADED_SYMBOLS and not other.state.terminal
                for other in broker.orders
            )
        ):
            return ReconciliationResult(ReconciliationStatus.POSITION_MISMATCH_BLOCKED)
        del positions[intent.symbol]
        result_status = ReconciliationStatus.RECONCILED_FLAT
        settled_exit = True
    next_state = replace(
        state,
        revision=state.revision + 1,
        intents=intents,
        positions=positions,
    )
    return ReconciliationResult(result_status, next_state, settled_exit)


def bind_approval_receipt(
    approval: ProviderApprovalFact,
    intent: LogicalOrderIntent,
    broker: BrokerSnapshot,
) -> ApprovalRequiredReceipt | None:
    """Bind a read-observed approval request to one exact durable intent.

    A broker review flag alone cannot create this receipt. The provider approval
    fact must carry the exact account/source/session/state and order identity.
    """

    if (
        approval.status is not ApprovalRequestStatus.PENDING
        or approval.source_identity is None
        or approval.intent_id != intent.intent_id
        or approval.ref_id != intent.ref_id
        or approval.symbol != intent.symbol
        or approval.side is not intent.side
        or approval.quantity != intent.quantity
        or approval.account_fingerprint != broker.account.fingerprint
        or approval.source_identity != intent.source_identity
        or approval.source_identity != broker.source_identity
        or approval.session_fingerprint != broker.session_fingerprint
        or approval.state_revision != broker.state_revision
    ):
        return None
    return ApprovalRequiredReceipt(
        approval_id=approval.approval_id,
        intent_id=intent.intent_id,
        ref_id=intent.ref_id,
        terms_digest=intent.terms_digest,
        account_fingerprint=approval.account_fingerprint,
        source_identity=intent.source_identity,
        session_fingerprint=approval.session_fingerprint,
        state_revision=approval.state_revision,
        observed_at=approval.observed_at,
    )


def _risk_context(
    account: AccountFacts,
    positions: Mapping[Symbol, Position],
    price: PriceObservation,
    as_of: datetime,
) -> RiskContext:
    with localcontext(_fixed_context()):
        return RiskContext(
            cash=min(
                account.cash, account.buying_power, account.unleveraged_buying_power
            ),
            equity=account.equity,
            positions=positions,
            current_price=price.price,
            total_market_exposure=account.total_market_exposure,
            new_trading_enabled=account.active and account.agentic_allowed,
            as_of=as_of,
        )


def _snapshot_blockers(
    broker: BrokerSnapshot, as_of: datetime
) -> list[AdmissionBlocker]:
    blockers: list[AdmissionBlocker] = []
    if not _fresh(broker.observed_at, as_of, _MAX_FACT_AGE) or not _fresh(
        broker.account.observed_at, as_of, _MAX_FACT_AGE
    ):
        blockers.append(AdmissionBlocker.BROKER_SNAPSHOT_STALE)
    if not broker.account.active or not broker.account.agentic_allowed:
        blockers.append(AdmissionBlocker.ACCOUNT_INELIGIBLE)
    scopes = (broker.position_scope, broker.order_scope)
    if any(
        scope.account_fingerprint != broker.account.fingerprint
        or not scope.all_agents
        or not scope.exhausted
        or scope.symbols not in (None, (TQQQ, SQQQ))
        or not _fresh(scope.observed_at, as_of, _MAX_FACT_AGE)
        for scope in scopes
    ):
        blockers.append(AdmissionBlocker.BROKER_SCOPE_INCOMPLETE)
    if any(
        order.account_fingerprint != broker.account.fingerprint
        for order in broker.orders
    ):
        blockers.append(AdmissionBlocker.BROKER_SCOPE_INCOMPLETE)
    if (
        broker.approvals.setting_enabled is None
        or not broker.approvals.exhaustive
        or not _fresh(broker.approvals.observed_at, as_of, _MAX_FACT_AGE)
        or broker.approvals.account_fingerprint != broker.account.fingerprint
        or broker.approvals.source_identity != broker.source_identity
        or broker.approvals.session_fingerprint != broker.session_fingerprint
        or broker.approvals.state_revision != broker.state_revision
        or any(
            request.account_fingerprint != broker.account.fingerprint
            or request.source_identity != broker.source_identity
            or request.session_fingerprint != broker.session_fingerprint
            or request.state_revision != broker.state_revision
            or not _fresh(request.observed_at, as_of, _MAX_FACT_AGE)
            for request in broker.approvals.requests
        )
    ):
        blockers.append(AdmissionBlocker.APPROVAL_STATE_UNKNOWN)
    elif broker.approvals.unresolved_refs or any(
        request.status in (ApprovalRequestStatus.PENDING, ApprovalRequestStatus.UNKNOWN)
        for request in broker.approvals.requests
    ):
        blockers.append(AdmissionBlocker.APPROVAL_PENDING)
    for symbol in UNIVERSE_SYMBOLS:
        facts = broker.tradability.get(symbol)
        if facts is None or not _fresh(facts.observed_at, as_of, _MAX_FACT_AGE):
            blockers.append(AdmissionBlocker.TRADABILITY_UNKNOWN)
            continue
        if (
            facts.active is None
            or facts.halted is None
            or facts.regular_session_eligible is None
        ):
            blockers.append(AdmissionBlocker.TRADABILITY_UNKNOWN)
        elif not facts.active or facts.halted or not facts.regular_session_eligible:
            blockers.append(AdmissionBlocker.NOT_TRADABLE)
    return _unique(blockers)


def _market_blockers(quality: MarketQuality) -> list[AdmissionBlocker]:
    mapping = {
        MarketQuality.READY: None,
        MarketQuality.NO_CURRENT_SESSION_DATA: AdmissionBlocker.MARKET_DATA_INVALID,
        MarketQuality.INSUFFICIENT_WARMUP: AdmissionBlocker.INSUFFICIENT_WARMUP,
        MarketQuality.STALE: AdmissionBlocker.MARKET_DATA_STALE,
        MarketQuality.GAP: AdmissionBlocker.MARKET_DATA_GAP,
        MarketQuality.INTERPOLATED: AdmissionBlocker.MARKET_DATA_INTERPOLATED,
        MarketQuality.INVALID: AdmissionBlocker.MARKET_DATA_INVALID,
    }
    blocker = mapping[quality]
    return [] if blocker is None else [blocker]


def _state_blockers(state: RuntimeState) -> list[AdmissionBlocker]:
    if state.approval_receipts or any(
        intent.lifecycle is IntentLifecycle.APPROVAL_REQUIRED
        for intent in state.intents
    ):
        return [AdmissionBlocker.APPROVAL_PENDING]
    if any(
        intent.lifecycle in (IntentLifecycle.MAY_HAVE_OCCURRED, IntentLifecycle.UNKNOWN)
        for intent in state.intents
    ):
        return [AdmissionBlocker.UNKNOWN_INTENT]
    return []


def _reconcile_approval_request(
    request: CycleRequest,
    state: RuntimeState,
    as_of: datetime,
) -> tuple[RuntimeState | None, AdmissionBlocker | None]:
    """Persist only an exact approval request read under the bound scope."""

    facts = request.broker.approvals
    if (
        not facts.exhaustive
        or facts.account_fingerprint != state.account_fingerprint
        or facts.source_identity != state.source_identity
        or facts.session_fingerprint != state.session_fingerprint
        or facts.state_revision != state.revision
        or not _fresh(facts.observed_at, as_of, _MAX_FACT_AGE)
    ):
        return None, None
    if facts.setting_enabled is None:
        return None, None
    matches_by_intent: list[tuple[LogicalOrderIntent, ProviderApprovalFact]] = []
    for intent in state.intents:
        if intent.lifecycle not in (
            IntentLifecycle.PROPOSED,
            IntentLifecycle.MAY_HAVE_OCCURRED,
            IntentLifecycle.UNKNOWN,
        ):
            continue
        matched = tuple(
            approval
            for approval in facts.requests
            if approval.status is ApprovalRequestStatus.PENDING
            and (
                approval.intent_id == intent.intent_id
                or approval.ref_id == intent.ref_id
            )
        )
        if len(matched) > 1:
            return None, AdmissionBlocker.APPROVAL_STATE_UNKNOWN
        if matched:
            matches_by_intent.append((intent, matched[0]))
    if not matches_by_intent:
        return None, None
    if len(matches_by_intent) != 1:
        return None, AdmissionBlocker.APPROVAL_STATE_UNKNOWN
    intent, approval = matches_by_intent[0]
    receipt = bind_approval_receipt(approval, intent, request.broker)
    if receipt is None:
        return None, AdmissionBlocker.APPROVAL_STATE_UNKNOWN
    if any(
        order.ref_id in (intent.ref_id, approval.approval_id)
        or order.provider_order_id == approval.approval_id
        for order in request.broker.orders
    ):
        return None, AdmissionBlocker.UNKNOWN_INTENT
    other_unresolved = tuple(
        item
        for item in state.intents
        if item.intent_id != intent.intent_id
        and item.lifecycle
        in (
            IntentLifecycle.PROPOSED,
            IntentLifecycle.APPROVAL_REQUIRED,
            IntentLifecycle.MAY_HAVE_OCCURRED,
            IntentLifecycle.UNKNOWN,
        )
    )
    if other_unresolved:
        return None, AdmissionBlocker.UNKNOWN_INTENT
    updated_intent = replace(intent, lifecycle=IntentLifecycle.APPROVAL_REQUIRED)
    return (
        replace(
            state,
            revision=state.revision + 1,
            intents=tuple(
                updated_intent if item.intent_id == intent.intent_id else item
                for item in state.intents
            ),
            approval_receipts=state.approval_receipts + (receipt,),
        ),
        None,
    )


def _reconcile_open_protective_stop(
    request: CycleRequest,
    state: RuntimeState,
    as_of: datetime,
) -> tuple[RuntimeState | None, AdmissionBlocker | None]:
    """Bind one exact, scoped open stop and settle coherent partial coverage."""

    broker = request.broker
    if (
        not _state_well_formed(state)
        or not broker.account.active
        or not broker.account.agentic_allowed
        or not _fresh(broker.observed_at, as_of, _MAX_FACT_AGE)
        or not _fresh(broker.account.observed_at, as_of, _MAX_FACT_AGE)
        or broker.account.fingerprint != state.account_fingerprint
        or broker.source_identity != state.source_identity
        or broker.session_fingerprint != state.session_fingerprint
        or broker.state_revision != state.revision
        or request.expected_state_revision != state.revision
        or any(
            not scope.all_agents
            or not scope.exhausted
            or scope.account_fingerprint != state.account_fingerprint
            or scope.symbols not in (None, (TQQQ, SQQQ))
            or not _fresh(scope.observed_at, as_of, _MAX_FACT_AGE)
            for scope in (broker.position_scope, broker.order_scope)
        )
    ):
        return None, None
    if len(state.positions) != 1:
        return None, None
    symbol, record = next(iter(state.positions.items()))
    position = broker.positions.get(symbol)
    if (
        position is None
        or broker.position_owners.get(symbol) != record.entry_intent_id
        or position.average_cost != record.average_entry_fill
    ):
        return None, None
    open_stops = tuple(
        order
        for order in broker.orders
        if order.symbol == symbol
        and order.kind is IntentKind.PROTECTIVE_STOP
        and not order.state.terminal
    )
    if not open_stops:
        return None, None
    if len(open_stops) != 1 or any(
        order.symbol in TRADED_SYMBOLS
        and not order.state.terminal
        and order != open_stops[0]
        for order in broker.orders
    ):
        return None, AdmissionBlocker.STOP_CONFLICT
    order = open_stops[0]
    if order.state not in (OrderState.OPEN, OrderState.PARTIALLY_FILLED):
        return None, AdmissionBlocker.STOP_CONFLICT
    candidates = tuple(
        intent
        for intent in state.intents
        if intent.kind is IntentKind.PROTECTIVE_STOP
        and intent.symbol == symbol
        and intent.ref_id == order.ref_id
        and intent.lifecycle
        in (
            IntentLifecycle.MAY_HAVE_OCCURRED,
            IntentLifecycle.UNKNOWN,
            IntentLifecycle.RECONCILED,
        )
    )
    if len(candidates) != 1:
        return None, AdmissionBlocker.STOP_CONFLICT
    intent = candidates[0]
    threshold = HardStopPolicy().threshold(
        record.average_entry_fill, record.hard_stop_price
    )
    already_bound = (
        intent.lifecycle is IntentLifecycle.RECONCILED
        and record.stop_intent_id == intent.intent_id
        and record.quantity == position.quantity
    )
    coherent = (
        decimal_sum_equals(
            order.filled_quantity, order.remaining_quantity, order.requested_quantity
        )
        and decimal_sum_equals(
            order.filled_quantity, position.quantity, intent.quantity
        )
        and (already_bound or record.quantity == intent.quantity)
    )
    if (
        intent.owner_id != state.owner_id
        or intent.source_identity != state.source_identity
        or intent.ref_id != order.ref_id
        or intent.quantity != order.requested_quantity
        or intent.stop_price != threshold
        or order.account_fingerprint != state.account_fingerprint
        or (
            order.source_identity is not None
            and order.source_identity != state.source_identity
        )
        or (order.intent_id is not None and order.intent_id != intent.intent_id)
        or order.kind is not IntentKind.PROTECTIVE_STOP
        or order.side is not OrderSide.SELL
        or order.stop_price != threshold
        or order.remaining_quantity != position.quantity
        or not coherent
        or (order.state is OrderState.OPEN and order.filled_quantity != 0)
        or (order.state is OrderState.PARTIALLY_FILLED and order.filled_quantity == 0)
        or not _fresh(order.observed_at, as_of, _MAX_FACT_AGE)
        or intent.lifecycle is IntentLifecycle.APPROVAL_REQUIRED
    ):
        return None, AdmissionBlocker.STOP_CONFLICT
    if (
        intent.lifecycle is IntentLifecycle.RECONCILED
        and record.stop_intent_id == intent.intent_id
        and record.quantity == position.quantity
    ):
        return None, None
    reconciled_intent = replace(intent, lifecycle=IntentLifecycle.RECONCILED)
    reconciled_record = replace(
        record,
        quantity=position.quantity,
        stop_intent_id=intent.intent_id,
    )
    return (
        replace(
            state,
            revision=state.revision + 1,
            intents=tuple(
                reconciled_intent if item.intent_id == intent.intent_id else item
                for item in state.intents
            ),
            positions={symbol: reconciled_record},
        ),
        None,
    )


def _reconcile_terminal_stopped_order(
    request: CycleRequest,
    state: RuntimeState,
    as_of: datetime,
) -> tuple[RuntimeState | None, AdmissionBlocker | None]:
    """Release a bound stop only from an exact terminal cancel/reject fact."""

    if (
        not _state_well_formed(state)
        or len(state.positions) != 1
        or request.owner_id != state.owner_id
        or request.source_identity != state.source_identity
        or request.expected_state_revision != state.revision
        or request.session_fingerprint != state.session_fingerprint
        or request.broker.source_identity != state.source_identity
        or request.broker.session_fingerprint != state.session_fingerprint
        or request.broker.state_revision != state.revision
        or request.broker.account.fingerprint != state.account_fingerprint
        or not _fresh(request.broker.observed_at, as_of, _MAX_FACT_AGE)
        or not _fresh(request.broker.account.observed_at, as_of, _MAX_FACT_AGE)
        or any(
            scope.account_fingerprint != state.account_fingerprint
            or not scope.all_agents
            or not scope.exhausted
            or scope.symbols not in (None, (TQQQ, SQQQ))
            or not _fresh(scope.observed_at, as_of, _MAX_FACT_AGE)
            for scope in (request.broker.position_scope, request.broker.order_scope)
        )
    ):
        return None, None
    symbol, record = next(iter(state.positions.items()))
    if record.stop_intent_id is None:
        return None, None
    intent = next(
        (item for item in state.intents if item.intent_id == record.stop_intent_id),
        None,
    )
    if intent is None or intent.lifecycle is not IntentLifecycle.RECONCILED:
        return None, None
    matches = tuple(
        order for order in request.broker.orders if order.ref_id == intent.ref_id
    )
    if not matches:
        return None, None
    if len(matches) != 1:
        return None, AdmissionBlocker.STOP_CONFLICT
    order = matches[0]
    if order.state not in (OrderState.CANCELED, OrderState.REJECTED):
        return None, None
    position = request.broker.positions.get(symbol)
    if (
        position is None
        or request.broker.position_owners.get(symbol) != record.entry_intent_id
        or position.average_cost != record.average_entry_fill
        or order.account_fingerprint != state.account_fingerprint
        or (
            order.source_identity is not None
            and order.source_identity != state.source_identity
        )
        or (order.intent_id is not None and order.intent_id != intent.intent_id)
        or order.kind is not IntentKind.PROTECTIVE_STOP
        or order.symbol != symbol
        or order.side is not OrderSide.SELL
        or order.requested_quantity != intent.quantity
        or order.stop_price != intent.stop_price
        or not decimal_sum_equals(
            order.filled_quantity, order.remaining_quantity, intent.quantity
        )
        or not decimal_sum_equals(
            order.filled_quantity, position.quantity, intent.quantity
        )
        or any(
            held in request.broker.positions
            for held in TRADED_SYMBOLS
            if held != symbol
        )
        or any(
            other.symbol in TRADED_SYMBOLS and not other.state.terminal
            for other in request.broker.orders
            if other != order
        )
        or not _fresh(order.observed_at, as_of, _MAX_FACT_AGE)
    ):
        return None, AdmissionBlocker.STOP_CONFLICT
    return replace(
        state,
        revision=state.revision + 1,
        positions={
            symbol: replace(record, quantity=position.quantity, stop_intent_id=None)
        },
    ), None


def _reconcile_filled_protective_stop(
    request: CycleRequest,
    state: RuntimeState,
    as_of: datetime,
) -> tuple[RuntimeState | None, AdmissionBlocker | None]:
    """Settle one exact previously bound stop fill to FLAT through the read path."""

    if (
        not _state_well_formed(state)
        or len(state.positions) != 1
        or request.owner_id != state.owner_id
        or request.source_identity != state.source_identity
        or request.expected_state_revision != state.revision
        or request.session_fingerprint != state.session_fingerprint
        or request.broker.source_identity != state.source_identity
        or request.broker.session_fingerprint != state.session_fingerprint
        or request.broker.state_revision != state.revision
        or request.broker.account.fingerprint != state.account_fingerprint
        or not _fresh(request.broker.observed_at, as_of, _MAX_FACT_AGE)
        or not _fresh(request.broker.account.observed_at, as_of, _MAX_FACT_AGE)
        or any(
            scope.account_fingerprint != state.account_fingerprint
            or not scope.all_agents
            or not scope.exhausted
            or scope.symbols not in (None, (TQQQ, SQQQ))
            or not _fresh(scope.observed_at, as_of, _MAX_FACT_AGE)
            for scope in (request.broker.position_scope, request.broker.order_scope)
        )
    ):
        return None, None
    symbol, record = next(iter(state.positions.items()))
    if record.stop_intent_id is None:
        return None, None
    intent = next(
        (item for item in state.intents if item.intent_id == record.stop_intent_id),
        None,
    )
    if intent is None or intent.lifecycle is not IntentLifecycle.RECONCILED:
        return None, None
    matches = tuple(
        order for order in request.broker.orders if order.ref_id == intent.ref_id
    )
    if not matches:
        return None, None
    if len(matches) != 1:
        return None, AdmissionBlocker.STOP_CONFLICT
    order = matches[0]
    if order.state is not OrderState.FILLED:
        return None, None
    if (
        order.account_fingerprint != state.account_fingerprint
        or (
            order.source_identity is not None
            and order.source_identity != state.source_identity
        )
        or (order.intent_id is not None and order.intent_id != intent.intent_id)
        or order.kind is not IntentKind.PROTECTIVE_STOP
        or order.symbol != symbol
        or order.side is not OrderSide.SELL
        or order.requested_quantity != intent.quantity
        or order.stop_price != intent.stop_price
        or order.filled_quantity != intent.quantity
        or order.remaining_quantity != 0
        or not decimal_sum_equals(
            order.filled_quantity,
            order.remaining_quantity,
            order.requested_quantity,
        )
        or symbol in request.broker.positions
        or any(held in request.broker.positions for held in TRADED_SYMBOLS)
        or any(
            other.symbol in TRADED_SYMBOLS and not other.state.terminal
            for other in request.broker.orders
        )
        or not _fresh(order.observed_at, as_of, _MAX_FACT_AGE)
    ):
        return None, AdmissionBlocker.STOP_CONFLICT
    return replace(
        state,
        revision=state.revision + 1,
        positions={},
    ), None


def _state_well_formed(state: RuntimeState) -> bool:
    """Revalidate canonical IDs, digests, and ownership after state loading."""

    try:
        if (
            not isinstance(state, RuntimeState)
            or not isinstance(state.owner_id, UUID)
            or not isinstance(state.source_identity, SourceIdentity)
            or not isinstance(state.positions, Mapping)
            or not isinstance(state.intents, tuple)
            or not isinstance(state.approval_receipts, tuple)
            or not isinstance(state.revision, int)
            or isinstance(state.revision, bool)
            or state.revision < 0
            or not isinstance(state.next_sequence, int)
            or isinstance(state.next_sequence, bool)
            or state.next_sequence < 1
            or not isinstance(state.session_fingerprint, str)
            or not isinstance(state.account_fingerprint, str)
            or not 8 <= len(state.session_fingerprint) <= 128
            or not 8 <= len(state.account_fingerprint) <= 128
            or not all(
                character.isascii() and (character.isalnum() or character in "_-")
                for character in state.session_fingerprint
            )
            or not all(
                character.isascii() and (character.isalnum() or character in "_-")
                for character in state.account_fingerprint
            )
            or len(state.positions) > 1
        ):
            return False
        if any(
            not isinstance(symbol, Symbol)
            or not isinstance(record, OwnedPositionRecord)
            or record.symbol != symbol
            for symbol, record in state.positions.items()
        ):
            return False
        if any(not isinstance(intent, LogicalOrderIntent) for intent in state.intents):
            return False
        if any(
            not isinstance(receipt, ApprovalRequiredReceipt)
            for receipt in state.approval_receipts
        ):
            return False
        if (
            sum(
                item.lifecycle
                in (
                    IntentLifecycle.PROPOSED,
                    IntentLifecycle.APPROVAL_REQUIRED,
                    IntentLifecycle.MAY_HAVE_OCCURRED,
                    IntentLifecycle.UNKNOWN,
                )
                for item in state.intents
            )
            > 1
        ):
            return False
        if (
            len({item.intent_id for item in state.intents}) != len(state.intents)
            or len({item.ref_id for item in state.intents}) != len(state.intents)
            or len({item.logical_sequence for item in state.intents})
            != len(state.intents)
            or any(
                item.logical_sequence >= state.next_sequence for item in state.intents
            )
        ):
            return False
        for intent in state.intents:
            canonical = create_order_intent(
                owner_id=intent.owner_id,
                source_identity=intent.source_identity,
                logical_sequence=intent.logical_sequence,
                kind=intent.kind,
                symbol=intent.symbol,
                side=intent.side,
                quantity=intent.quantity,
                stop_price=intent.stop_price,
                created_at=intent.created_at,
                lifecycle=intent.lifecycle,
            )
            if (
                canonical.intent_id != intent.intent_id
                or canonical.ref_id != intent.ref_id
                or canonical.terms_digest != intent.terms_digest
                or intent.owner_id != state.owner_id
                or intent.source_identity != state.source_identity
            ):
                return False
        intent_by_id = {item.intent_id: item for item in state.intents}
        for symbol, record in state.positions.items():
            entry = intent_by_id.get(record.entry_intent_id)
            if (
                entry is None
                or entry.kind is not IntentKind.ENTRY
                or entry.symbol != symbol
                or entry.lifecycle is not IntentLifecycle.RECONCILED
                or record.quantity > entry.quantity
                or record.hard_stop_price
                < HardStopPolicy().threshold(record.average_entry_fill)
            ):
                return False
            if record.stop_intent_id is not None:
                stop = intent_by_id.get(record.stop_intent_id)
                if (
                    stop is None
                    or stop.kind is not IntentKind.PROTECTIVE_STOP
                    or stop.symbol != symbol
                    or stop.side is not OrderSide.SELL
                    or stop.lifecycle is not IntentLifecycle.RECONCILED
                    or stop.stop_price != record.hard_stop_price
                    or stop.quantity < record.quantity
                ):
                    return False
        for receipt in state.approval_receipts:
            intent = intent_by_id.get(receipt.intent_id)
            if (
                intent is None
                or intent.lifecycle is not IntentLifecycle.APPROVAL_REQUIRED
                or receipt.ref_id != intent.ref_id
                or receipt.terms_digest != intent.terms_digest
                or receipt.account_fingerprint != state.account_fingerprint
                or receipt.source_identity != state.source_identity
                or receipt.session_fingerprint != state.session_fingerprint
                or receipt.state_revision > state.revision
            ):
                return False
        return True
    except (AttributeError, ArithmeticError, TypeError, ValueError):
        return False


def _requires_safety_flatten(
    blockers: list[AdmissionBlocker], quality: MarketQuality
) -> bool:
    if quality is not MarketQuality.READY:
        return True
    return any(
        blocker
        in {
            AdmissionBlocker.STATE_IDENTITY_MISMATCH,
            AdmissionBlocker.ACCOUNT_IDENTITY_MISMATCH,
            AdmissionBlocker.SESSION_IDENTITY_MISMATCH,
            AdmissionBlocker.STATE_CONFLICT,
            AdmissionBlocker.BROKER_SNAPSHOT_STALE,
            AdmissionBlocker.ACCOUNT_INELIGIBLE,
            AdmissionBlocker.BROKER_SCOPE_INCOMPLETE,
            AdmissionBlocker.PRICE_STALE,
            AdmissionBlocker.POSITION_CONFLICT,
            AdmissionBlocker.FOREIGN_POSITION,
            AdmissionBlocker.UNRESOLVED_ORDER,
            AdmissionBlocker.TRADABILITY_UNKNOWN,
            AdmissionBlocker.NOT_TRADABLE,
            AdmissionBlocker.APPROVAL_STATE_UNKNOWN,
            AdmissionBlocker.APPROVAL_PENDING,
            AdmissionBlocker.UNKNOWN_INTENT,
            AdmissionBlocker.STOP_CONFLICT,
            AdmissionBlocker.SESSION_UNAVAILABLE,
        }
        for blocker in blockers
    )


def _priority_exit_reasons(
    reasons: list[AdmissionBlocker],
) -> list[AdmissionBlocker]:
    order = (
        AdmissionBlocker.STOP_BREACH,
        AdmissionBlocker.SAFETY_FAILURE,
        AdmissionBlocker.REGIME_EXIT,
        AdmissionBlocker.FORCED_FLAT,
    )
    present = set(reasons)
    return [reason for reason in order if reason in present]


def _actual_position(
    broker: BrokerSnapshot, state: RuntimeState | None
) -> tuple[TargetPosition | None, OwnedPositionRecord | None, list[AdmissionBlocker]]:
    held = [
        (symbol, broker.positions[symbol])
        for symbol in TRADED_SYMBOLS
        if symbol in broker.positions and broker.positions[symbol].quantity > 0
    ]
    if len(held) > 1:
        return None, None, [AdmissionBlocker.POSITION_CONFLICT]
    if not held:
        if state is not None and state.positions:
            return None, None, [AdmissionBlocker.POSITION_CONFLICT]
        if any(
            order.symbol in TRADED_SYMBOLS and not order.state.terminal
            for order in broker.orders
        ):
            return None, None, [AdmissionBlocker.UNRESOLVED_ORDER]
        if state is not None and any(
            intent.lifecycle
            in (IntentLifecycle.MAY_HAVE_OCCURRED, IntentLifecycle.UNKNOWN)
            for intent in state.intents
        ):
            return None, None, [AdmissionBlocker.UNKNOWN_INTENT]
        return TargetPosition.FLAT, None, []
    symbol, broker_position = held[0]
    target = TargetPosition(symbol.value)
    if state is None:
        return target, None, [AdmissionBlocker.FOREIGN_POSITION]
    record = state.positions.get(symbol)
    if record is None:
        return target, None, [AdmissionBlocker.FOREIGN_POSITION]
    if (
        broker.position_owners.get(symbol) != record.entry_intent_id
        or broker_position.quantity != record.quantity
        or broker_position.average_cost != record.average_entry_fill
    ):
        return target, record, [AdmissionBlocker.POSITION_CONFLICT]
    entry = next(
        (
            intent
            for intent in state.intents
            if intent.intent_id == record.entry_intent_id
        ),
        None,
    )
    if (
        entry is None
        or entry.kind is not IntentKind.ENTRY
        or entry.symbol != symbol
        or entry.lifecycle is not IntentLifecycle.RECONCILED
    ):
        return target, record, [AdmissionBlocker.FOREIGN_POSITION]
    blockers = []
    if any(
        intent.lifecycle in (IntentLifecycle.MAY_HAVE_OCCURRED, IntentLifecycle.UNKNOWN)
        for intent in state.intents
    ):
        blockers.append(AdmissionBlocker.UNKNOWN_INTENT)
    if any(
        order.symbol in TRADED_SYMBOLS
        and not order.state.terminal
        and (order.symbol != symbol or order.kind is not IntentKind.PROTECTIVE_STOP)
        for order in broker.orders
    ):
        blockers.append(AdmissionBlocker.UNRESOLVED_ORDER)
    return target, record, blockers


def _stop_coverage(
    broker: BrokerSnapshot,
    state: RuntimeState | None,
    record: OwnedPositionRecord,
    threshold: Decimal,
    as_of: datetime,
) -> tuple[bool, AdmissionBlocker | None]:
    active = tuple(
        order
        for order in broker.orders
        if order.symbol == record.symbol
        and order.kind is IntentKind.PROTECTIVE_STOP
        and not order.state.terminal
    )
    other_open = tuple(
        order
        for order in broker.orders
        if order.symbol == record.symbol
        and order.kind is not IntentKind.PROTECTIVE_STOP
        and not order.state.terminal
    )
    if other_open or len(active) > 1:
        return False, AdmissionBlocker.STOP_CONFLICT
    if not active:
        return (
            False,
            AdmissionBlocker.STOP_CONFLICT
            if record.stop_intent_id is not None
            else AdmissionBlocker.STOP_UNPROTECTED,
        )
    if state is None or record.stop_intent_id is None:
        return False, AdmissionBlocker.STOP_CONFLICT
    order = active[0]
    stop_intent = next(
        (item for item in state.intents if item.intent_id == record.stop_intent_id),
        None,
    )
    if (
        stop_intent is None
        or stop_intent.kind is not IntentKind.PROTECTIVE_STOP
        or stop_intent.symbol != record.symbol
        or stop_intent.side is not OrderSide.SELL
        or stop_intent.lifecycle is not IntentLifecycle.RECONCILED
        or order.account_fingerprint != broker.account.fingerprint
        or (
            order.source_identity is not None
            and order.source_identity != state.source_identity
        )
        or (order.intent_id is not None and order.intent_id != stop_intent.intent_id)
        or order.ref_id != stop_intent.ref_id
        or order.side is not OrderSide.SELL
        or order.kind is not IntentKind.PROTECTIVE_STOP
        or order.stop_price != threshold
        or stop_intent.stop_price != threshold
        or order.requested_quantity != stop_intent.quantity
        or not decimal_sum_equals(
            order.filled_quantity,
            order.remaining_quantity,
            order.requested_quantity,
        )
        or order.remaining_quantity != record.quantity
        or stop_intent.quantity < record.quantity
        or not _fresh(order.observed_at, as_of, _MAX_FACT_AGE)
    ):
        return False, AdmissionBlocker.STOP_CONFLICT
    if order.state is not OrderState.OPEN:
        return False, AdmissionBlocker.STOP_CONFLICT
    return True, None


def _action_blockers(
    action: IntentKind,
    blockers: list[AdmissionBlocker],
    mandatory_exit_reasons: list[AdmissionBlocker],
    signal,
    broker: BrokerSnapshot,
    owned_record: OwnedPositionRecord | None,
    actual: TargetPosition,
    session: SessionDecision,
) -> list[AdmissionBlocker]:
    ignore_market = action is IntentKind.EXIT and any(
        reason in mandatory_exit_reasons
        for reason in (
            AdmissionBlocker.STOP_BREACH,
            AdmissionBlocker.SAFETY_FAILURE,
            AdmissionBlocker.FORCED_FLAT,
        )
    )
    ignored = {
        AdmissionBlocker.STOP_UNPROTECTED,
        AdmissionBlocker.ENTRY_WINDOW_CLOSED,
        AdmissionBlocker.FORCED_FLAT,
    }
    if ignore_market:
        ignored.update(
            {
                AdmissionBlocker.MARKET_DATA_INVALID,
                AdmissionBlocker.MARKET_DATA_STALE,
                AdmissionBlocker.MARKET_DATA_GAP,
                AdmissionBlocker.MARKET_DATA_INTERPOLATED,
                AdmissionBlocker.INSUFFICIENT_WARMUP,
            }
        )
    if action is IntentKind.PROTECTIVE_STOP:
        ignored.add(AdmissionBlocker.STOP_UNPROTECTED)
        ignored.update(
            {
                AdmissionBlocker.MARKET_DATA_INVALID,
                AdmissionBlocker.MARKET_DATA_STALE,
                AdmissionBlocker.MARKET_DATA_GAP,
                AdmissionBlocker.MARKET_DATA_INTERPOLATED,
                AdmissionBlocker.INSUFFICIENT_WARMUP,
            }
        )
    result = [item for item in blockers if item not in ignored]
    if action is IntentKind.ENTRY:
        if not session.can_enter:
            result.append(AdmissionBlocker.ENTRY_WINDOW_CLOSED)
        if signal.quality is not MarketQuality.READY:
            result.extend(_market_blockers(signal.quality))
        if actual is not TargetPosition.FLAT:
            result.append(AdmissionBlocker.POSITION_CONFLICT)
        if any(
            order.symbol in TRADED_SYMBOLS and not order.state.terminal
            for order in broker.orders
        ):
            result.append(AdmissionBlocker.UNRESOLVED_ORDER)
        if any(
            value <= 0
            for value in (
                broker.account.cash,
                broker.account.buying_power,
                broker.account.unleveraged_buying_power,
            )
        ):
            result.append(AdmissionBlocker.BUYING_POWER_UNSAFE)
    elif action is IntentKind.PROTECTIVE_STOP:
        if owned_record is None or actual is TargetPosition.FLAT:
            result.append(AdmissionBlocker.FOREIGN_POSITION)
        if owned_record is not None and owned_record.stop_intent_id is not None:
            result.append(AdmissionBlocker.STOP_CONFLICT)
        if owned_record is not None and any(
            order.symbol == owned_record.symbol and not order.state.terminal
            for order in broker.orders
        ):
            result.append(AdmissionBlocker.STOP_CONFLICT)
    elif action is IntentKind.EXIT:
        if owned_record is None or actual is TargetPosition.FLAT:
            result.append(AdmissionBlocker.FOREIGN_POSITION)
        if owned_record is not None and owned_record.stop_intent_id is not None:
            result.append(AdmissionBlocker.STOP_CONFLICT)
        if session.reason is SessionReason.AFTER_SESSION:
            result.append(AdmissionBlocker.AFTER_SESSION_NO_QUEUE)
        if not ignore_market and signal.quality is not MarketQuality.READY:
            result.extend(_market_blockers(signal.quality))
        if owned_record is not None and any(
            order.symbol == owned_record.symbol and not order.state.terminal
            for order in broker.orders
        ):
            result.append(AdmissionBlocker.STOP_CONFLICT)
    return _unique(result)


def _review_gate(
    broker: BrokerSnapshot,
    intent: LogicalOrderIntent,
    as_of: datetime,
) -> tuple[AdmissionBlocker | None, bool]:
    review = broker.review
    if review is None:
        return AdmissionBlocker.BROKER_REVIEW_MISSING, False
    if not _fresh(review.observed_at, as_of, _MAX_FACT_AGE):
        return AdmissionBlocker.BROKER_REVIEW_STALE, False
    if (
        review.account_fingerprint != broker.account.fingerprint
        or review.source_identity != broker.source_identity
        or review.session_fingerprint != broker.session_fingerprint
        or review.state_revision != broker.state_revision
    ):
        return AdmissionBlocker.BROKER_REVIEW_MISMATCH, False
    if review.ref_id != intent.ref_id or review.terms_digest != intent.terms_digest:
        return AdmissionBlocker.BROKER_REVIEW_MISMATCH, False
    if review.approval_required:
        return None, True
    if review.status.value == "REJECTED":
        return AdmissionBlocker.BROKER_REVIEW_REJECTED, False
    if review.status.value != "ACCEPTED":
        return AdmissionBlocker.BROKER_REVIEW_MISMATCH, False
    if review.warnings:
        return AdmissionBlocker.BROKER_REVIEW_WARNING, False
    return None, False


def _pending_intent(
    state: RuntimeState, candidate: LogicalOrderIntent
) -> tuple[LogicalOrderIntent | None, AdmissionBlocker | None]:
    pending = tuple(
        intent
        for intent in state.intents
        if intent.lifecycle
        in (
            IntentLifecycle.PROPOSED,
            IntentLifecycle.APPROVAL_REQUIRED,
            IntentLifecycle.MAY_HAVE_OCCURRED,
            IntentLifecycle.UNKNOWN,
        )
    )
    if not pending:
        return None, None
    if len(pending) != 1:
        return None, AdmissionBlocker.UNKNOWN_INTENT
    existing = pending[0]
    if existing.lifecycle in (
        IntentLifecycle.APPROVAL_REQUIRED,
        IntentLifecycle.UNKNOWN,
        IntentLifecycle.MAY_HAVE_OCCURRED,
    ):
        return (
            None,
            AdmissionBlocker.APPROVAL_PENDING
            if existing.lifecycle is IntentLifecycle.APPROVAL_REQUIRED
            else AdmissionBlocker.UNKNOWN_INTENT,
        )
    if (
        existing.kind is candidate.kind
        and existing.symbol == candidate.symbol
        and existing.side is candidate.side
        and existing.quantity == candidate.quantity
        and existing.stop_price == candidate.stop_price
        and existing.terms_digest == candidate.terms_digest
        and existing.source_identity == candidate.source_identity
        and existing.owner_id == candidate.owner_id
    ):
        return existing, None
    # A PROPOSED intent is known never to have crossed an executor boundary.
    # _persist_intent retires it under the same CAS that appends this replacement.
    return None, None


def _fresh(observed_at: datetime, as_of: datetime, maximum_age: timedelta) -> bool:
    return observed_at <= as_of and as_of - observed_at <= maximum_age


def _unique(values: list[AdmissionBlocker]) -> list[AdmissionBlocker]:
    return list(dict.fromkeys(values))


def _fixed_context() -> Context:
    context = Context(
        prec=48,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
    )
    for signal in context.traps:
        context.traps[signal] = False
    context.traps[InvalidOperation] = True
    context.traps[DivisionByZero] = True
    context.traps[Overflow] = True
    return context
