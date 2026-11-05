"""Pure effect-disabled L40 ownership, budget, and admission contract.

The contract checks a caller-supplied immutable snapshot and creates a pending
reservation. It does not authenticate evidence, persist state, reconcile provider
observations, or authorize an external effect. Those remain later source owners.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum
from typing import Final

from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle

SYMBOL: Final = "SPY"
STRATEGY: Final = "BASE_MA35_50_V1"
ENTRY_ORDER_LIMIT: Final = Decimal("10.00")
ENTRY_GROSS_LIMIT: Final = Decimal("10.00")
ENTRY_BUDGET: Final = Decimal("10.00")
MAX_EXIT_DECIMAL_PLACES: Final = 6
_ZERO: Final = Decimal("0")
_CENT: Final = Decimal("0.01")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_GIT_ID = re.compile(r"[0-9a-f]{40}\Z")
_OPAQUE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_ARITHMETIC = Context(prec=80, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999)


def _optional_match(value: str | None, pattern: re.Pattern[str], label: str) -> None:
    if value is not None and (
        not isinstance(value, str) or pattern.fullmatch(value) is None
    ):
        raise ValueError(f"{label} has invalid format")


def _decimal(value: Decimal, label: str, *, nonnegative: bool) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise TypeError(f"{label} must be a finite Decimal")
    parts = value.as_tuple()
    if (
        parts.exponent < -12
        or parts.exponent > 12
        or len(parts.digits) > 64
        or value.adjusted() > 12
    ):
        raise ValueError(f"{label} is outside the bounded Decimal domain")
    if nonnegative and value < _ZERO:
        raise ValueError(f"{label} cannot be negative")


class IntentKind(StrEnum):
    ENTRY = "ENTRY"
    STRATEGY_EXIT = "STRATEGY_EXIT"
    SAFETY_EXIT = "SAFETY_EXIT"


class StrategySignal(StrEnum):
    UNKNOWN = "UNKNOWN"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class GateStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    PASS = "PASS"
    FAIL = "FAIL"


class CapabilityStatus(StrEnum):
    UNPROVEN = "UNPROVEN"
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"


class Blocker(StrEnum):
    MISSING_IDENTITY = "MISSING_IDENTITY"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    INVALID_SNAPSHOT = "INVALID_SNAPSHOT"
    STATE_NOT_RUNNING = "STATE_NOT_RUNNING"
    STATE_UNKNOWN = "STATE_UNKNOWN"
    INTENT_UNRESOLVED = "INTENT_UNRESOLVED"
    WORKING_ORDER_PRESENT = "WORKING_ORDER_PRESENT"
    GATE_UNKNOWN = "GATE_UNKNOWN"
    GATE_FAILED = "GATE_FAILED"
    STRATEGY_SIGNAL_REQUIRED = "STRATEGY_SIGNAL_REQUIRED"
    BASELINE_POSITION_UNPROVEN = "BASELINE_POSITION_UNPROVEN"
    POSITION_MISMATCH = "POSITION_MISMATCH"
    OWNERSHIP_UNPROVEN = "OWNERSHIP_UNPROVEN"
    ENTRY_ALREADY_USED = "ENTRY_ALREADY_USED"
    EXIT_ALREADY_USED = "EXIT_ALREADY_USED"
    INVALID_ENTRY_AMOUNT = "INVALID_ENTRY_AMOUNT"
    ENTRY_ORDER_LIMIT = "ENTRY_ORDER_LIMIT"
    ENTRY_BUDGET_EXHAUSTED = "ENTRY_BUDGET_EXHAUSTED"
    ENTRY_GROSS_LIMIT = "ENTRY_GROSS_LIMIT"
    EXIT_CAPABILITY_UNPROVEN = "EXIT_CAPABILITY_UNPROVEN"
    EXIT_NOT_EXACT_OWNED_QUANTITY = "EXIT_NOT_EXACT_OWNED_QUANTITY"
    EXIT_NOT_SELLABLE = "EXIT_NOT_SELLABLE"
    EXIT_SIZE_UNSUPPORTED = "EXIT_SIZE_UNSUPPORTED"
    INTENT_ID_REUSED = "INTENT_ID_REUSED"


@dataclass(frozen=True, slots=True)
class GateEvidence:
    """Fail-closed reference; its digest is not authenticated by this module."""

    status: GateStatus = GateStatus.UNKNOWN
    evidence_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, GateStatus):
            raise TypeError("gate status must be GateStatus")
        _optional_match(self.evidence_digest, _DIGEST, "gate evidence digest")
        if self.status is GateStatus.PASS and self.evidence_digest is None:
            raise ValueError("PASS gate requires an evidence reference")


@dataclass(frozen=True, slots=True)
class GateSet:
    source: GateEvidence = GateEvidence()
    account: GateEvidence = GateEvidence()
    position: GateEvidence = GateEvidence()
    orders: GateEvidence = GateEvidence()
    signal: GateEvidence = GateEvidence()
    quote: GateEvidence = GateEvidence()
    session: GateEvidence = GateEvidence()
    readiness: GateEvidence = GateEvidence()
    risk: GateEvidence = GateEvidence()
    sellable: GateEvidence = GateEvidence()

    def __post_init__(self) -> None:
        if any(not isinstance(item, GateEvidence) for item in self.all):
            raise TypeError("gate set fields must be GateEvidence")

    @property
    def all(self) -> tuple[GateEvidence, ...]:
        return (
            self.source,
            self.account,
            self.position,
            self.orders,
            self.signal,
            self.quote,
            self.session,
            self.readiness,
            self.risk,
            self.sellable,
        )


@dataclass(frozen=True, slots=True)
class ExitCapability:
    """Externally sourced exit facts; L40 collects none of them.

    Unknown size rules block. Positive minimum sell notional also requires an
    evidence-backed exact-full-close exception; a market quote is not a fill
    guarantee. Pre-entry admission additionally requires residual-close proof.
    """

    status: CapabilityStatus = CapabilityStatus.UNPROVEN
    evidence_digest: str | None = None
    regular_hours_market_sell: bool | None = None
    fractional_quantity: bool | None = None
    minimum_quantity: Decimal | None = None
    quantity_increment: Decimal | None = None
    maximum_quantity: Decimal | None = None
    no_maximum_quantity_limit: bool | None = None
    minimum_sell_notional: Decimal | None = None
    exact_full_close_below_minimum_supported: bool | None = None
    exact_residual_close_supported: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CapabilityStatus):
            raise TypeError("capability status must be CapabilityStatus")
        _optional_match(self.evidence_digest, _DIGEST, "capability evidence digest")
        for fact in (
            self.regular_hours_market_sell,
            self.fractional_quantity,
            self.no_maximum_quantity_limit,
            self.exact_full_close_below_minimum_supported,
            self.exact_residual_close_supported,
        ):
            if fact is not None and type(fact) is not bool:
                raise TypeError("capability facts must be bool or unknown")
        for value in (
            self.minimum_quantity,
            self.quantity_increment,
            self.maximum_quantity,
            self.minimum_sell_notional,
        ):
            if value is not None:
                _decimal(value, "capability fact", nonnegative=True)

    @property
    def usable(self) -> bool:
        vals = (
            self.minimum_quantity,
            self.quantity_increment,
            self.minimum_sell_notional,
        )
        return (
            self.status is CapabilityStatus.EVIDENCE_RECORDED
            and self.evidence_digest is not None
            and self.regular_hours_market_sell is True
            and self.fractional_quantity is True
            and all(value is not None for value in vals)
            and self.minimum_quantity >= _ZERO  # type: ignore[operator]
            and self.quantity_increment > _ZERO  # type: ignore[operator]
            and (
                (
                    self.maximum_quantity is None
                    and self.no_maximum_quantity_limit is True
                )
                or (
                    self.maximum_quantity is not None
                    and self.no_maximum_quantity_limit is not True
                    and self.maximum_quantity > _ZERO
                    and self.maximum_quantity >= self.minimum_quantity
                )
            )
            and (
                self.minimum_sell_notional == _ZERO
                or self.exact_full_close_below_minimum_supported is True
            )
        )

    @property
    def permits_entry(self) -> bool:
        return self.usable and self.exact_residual_close_supported is True


@dataclass(frozen=True, slots=True)
class OwnershipSnapshot:
    """Immutable owner/budget facts; V1 rejects every nonzero initial baseline."""

    account_fingerprint: str | None = None
    symbol: str = SYMBOL
    strategy: str = STRATEGY
    source_head: str | None = None
    source_tree: str | None = None
    config_digest: str | None = None
    binding_digest: str | None = None
    lifecycle_id: str | None = None
    target_session: str | None = None
    lifecycle: Lifecycle = Lifecycle.DISARMED
    effect_disposition: EffectDisposition = EffectDisposition.NO_EFFECT
    baseline_quantity: Decimal = _ZERO
    cumulative_bought: Decimal = _ZERO
    cumulative_sold: Decimal = _ZERO
    cumulative_entry_filled_dollars: Decimal = _ZERO
    entry_reserved_dollars: Decimal = _ZERO
    working_remainder: Decimal = _ZERO
    entries_used: int = 0
    exits_used: int = 0
    entry_local_intent_id: str | None = None
    entry_provider_order_id: str | None = None
    exit_local_intent_id: str | None = None
    exit_provider_order_id: str | None = None
    pending_intent_id: str | None = None
    pending_kind: IntentKind | None = None
    pending_requested_dollars: Decimal = _ZERO
    pending_requested_quantity: Decimal = _ZERO

    def __post_init__(self) -> None:
        _optional_match(self.account_fingerprint, _DIGEST, "account fingerprint")
        _optional_match(self.source_head, _GIT_ID, "source HEAD")
        _optional_match(self.source_tree, _GIT_ID, "source tree")
        for value in (self.config_digest, self.binding_digest):
            _optional_match(value, _DIGEST, "config/binding digest")
        for value in (
            self.lifecycle_id,
            self.entry_local_intent_id,
            self.entry_provider_order_id,
            self.exit_local_intent_id,
            self.exit_provider_order_id,
            self.pending_intent_id,
        ):
            _optional_match(value, _OPAQUE_ID, "intent/order ID")
        _session(self.target_session)
        if not isinstance(self.lifecycle, Lifecycle) or not isinstance(
            self.effect_disposition, EffectDisposition
        ):
            raise TypeError("snapshot lifecycle/disposition must be typed")
        if self.pending_kind is not None and not isinstance(
            self.pending_kind, IntentKind
        ):
            raise TypeError("pending kind must be IntentKind")
        for value in (
            self.baseline_quantity,
            self.cumulative_bought,
            self.cumulative_sold,
            self.cumulative_entry_filled_dollars,
            self.entry_reserved_dollars,
            self.working_remainder,
            self.pending_requested_dollars,
            self.pending_requested_quantity,
        ):
            _decimal(value, "snapshot value", nonnegative=True)
        if any(
            type(n) is not int or n < 0 for n in (self.entries_used, self.exits_used)
        ):
            raise ValueError("usage counters must be nonnegative integers")
        if (self.pending_intent_id is None) != (self.pending_kind is None):
            raise ValueError("pending intent ID and kind must be paired")

    @property
    def owned_quantity(self) -> Decimal:
        return _sub(self.cumulative_bought, self.cumulative_sold)

    @property
    def budget_remaining(self) -> Decimal:
        return _sub(ENTRY_BUDGET, self.entry_reserved_dollars)


@dataclass(frozen=True, slots=True)
class IntentProposal:
    intent_id: str
    target_session: str
    kind: IntentKind
    requested_dollars: Decimal | None = None
    requested_quantity: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str):
            raise TypeError("intent ID must be text")
        _optional_match(self.intent_id, _OPAQUE_ID, "intent ID")
        _session(self.target_session, required=True)
        if not isinstance(self.kind, IntentKind):
            raise TypeError("intent kind must be IntentKind")
        if self.kind is IntentKind.ENTRY:
            if self.requested_dollars is None or self.requested_quantity is not None:
                raise ValueError("entry requires dollars and forbids quantity")
            _decimal(self.requested_dollars, "entry amount", nonnegative=False)
        elif self.requested_quantity is None or self.requested_dollars is not None:
            raise ValueError("exit requires exact quantity and forbids dollars")
        else:
            _decimal(self.requested_quantity, "exit quantity", nonnegative=False)


@dataclass(frozen=True, slots=True)
class AdmissionContext:
    account_fingerprint: str | None = None
    symbol: str | None = None
    strategy: str | None = None
    source_head: str | None = None
    source_tree: str | None = None
    config_digest: str | None = None
    binding_digest: str | None = None
    lifecycle_id: str | None = None
    target_session: str | None = None
    lifecycle: Lifecycle = Lifecycle.DISARMED
    strategy_signal: StrategySignal = StrategySignal.UNKNOWN
    observed_position: Decimal | None = None
    sellable_quantity: Decimal | None = None
    current_price: Decimal | None = None
    working_order_count: int | None = None
    gates: GateSet = GateSet()
    exit_capability: ExitCapability = ExitCapability()

    def __post_init__(self) -> None:
        _optional_match(self.account_fingerprint, _DIGEST, "account fingerprint")
        _optional_match(self.source_head, _GIT_ID, "source HEAD")
        _optional_match(self.source_tree, _GIT_ID, "source tree")
        for value in (self.config_digest, self.binding_digest):
            _optional_match(value, _DIGEST, "config/binding digest")
        _optional_match(self.lifecycle_id, _OPAQUE_ID, "lifecycle ID")
        _session(self.target_session, required=True)
        if not isinstance(self.lifecycle, Lifecycle) or not isinstance(
            self.strategy_signal, StrategySignal
        ):
            raise TypeError("context lifecycle/signal must be typed")
        if not isinstance(self.gates, GateSet) or not isinstance(
            self.exit_capability, ExitCapability
        ):
            raise TypeError("context gates/capability must be typed")
        for value in (
            self.observed_position,
            self.sellable_quantity,
            self.current_price,
        ):
            if value is not None:
                _decimal(value, "current fact", nonnegative=True)
        if self.current_price == _ZERO:
            raise ValueError("current price must be positive")
        if self.working_order_count is not None and (
            type(self.working_order_count) is not int or self.working_order_count < 0
        ):
            raise ValueError("working order count must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class ContractAdmission:
    """Necessary-only result: admissible never grants mutation authority."""

    proposal: IntentProposal = field(repr=False)
    snapshot: OwnershipSnapshot = field(repr=False)
    context: AdmissionContext = field(repr=False)
    blockers: tuple[Blocker, ...] = ()

    @property
    def admissible(self) -> bool:
        return not self.blockers


def admit_intent(
    snapshot: OwnershipSnapshot,
    proposal: IntentProposal,
    context: AdmissionContext,
) -> ContractAdmission:
    """Check frozen constraints only; result never authorizes invocation."""
    if (
        not isinstance(snapshot, OwnershipSnapshot)
        or not isinstance(proposal, IntentProposal)
        or not isinstance(context, AdmissionContext)
    ):
        raise TypeError("typed ownership snapshot, intent, and context required")
    blockers = list(_snapshot_blockers(snapshot))
    blockers.extend(_identity_blockers(snapshot, context))
    if proposal.target_session != context.target_session:
        blockers.append(Blocker.IDENTITY_MISMATCH)
    if (
        snapshot.target_session is not None
        and context.target_session is not None
        and context.target_session < snapshot.target_session
    ):
        blockers.append(Blocker.IDENTITY_MISMATCH)
    blockers.extend(_gate_blockers(context))
    if (
        snapshot.lifecycle is not Lifecycle.RUNNING
        or context.lifecycle is not Lifecycle.RUNNING
    ):
        blockers.append(Blocker.STATE_NOT_RUNNING)
    if (
        snapshot.lifecycle in (Lifecycle.UNKNOWN, Lifecycle.BLOCKED)
        or snapshot.effect_disposition is EffectDisposition.MAY_HAVE_OCCURRED
    ):
        blockers.append(Blocker.STATE_UNKNOWN)
    if snapshot.pending_intent_id is not None or snapshot.pending_kind is not None:
        blockers.append(Blocker.INTENT_UNRESOLVED)
    if snapshot.working_remainder > _ZERO or context.working_order_count != 0:
        blockers.append(Blocker.WORKING_ORDER_PRESENT)
    if context.working_order_count is None or context.current_price is None:
        blockers.append(Blocker.GATE_UNKNOWN)
    blockers.extend(_position_blockers(snapshot, context))
    if proposal.intent_id in (
        snapshot.entry_local_intent_id,
        snapshot.exit_local_intent_id,
    ):
        blockers.append(Blocker.INTENT_ID_REUSED)
    blockers.extend(_intent_blockers(snapshot, proposal, context))
    return ContractAdmission(
        proposal, snapshot, context, tuple(dict.fromkeys(blockers))
    )


def reserve_intent(
    admission: ContractAdmission,
    *,
    current_snapshot: OwnershipSnapshot,
    current_context: AdmissionContext,
) -> OwnershipSnapshot:
    """Purely reserve before invocation; caller persists and later reconciles.

    Reservation consumes the entry budget permanently and blocks all further
    intents. No L40 API clears pending/UNKNOWN state or applies a fill.
    """
    if not isinstance(admission, ContractAdmission):
        raise TypeError("admission must be ContractAdmission")
    if admission.snapshot != current_snapshot or admission.context != current_context:
        raise ValueError("admission facts changed before reservation")
    checked = admit_intent(current_snapshot, admission.proposal, current_context)
    if admission.blockers or checked.blockers:
        raise ValueError("intent is not contract-admissible")
    proposal, state = admission.proposal, admission.snapshot
    if proposal.kind is IntentKind.ENTRY:
        assert proposal.requested_dollars is not None
        return replace(
            state,
            lifecycle=Lifecycle.RECONCILING,
            effect_disposition=EffectDisposition.NO_EFFECT,
            entries_used=state.entries_used + 1,
            entry_reserved_dollars=_add(
                state.entry_reserved_dollars, proposal.requested_dollars
            ),
            entry_local_intent_id=proposal.intent_id,
            target_session=proposal.target_session,
            pending_intent_id=proposal.intent_id,
            pending_kind=proposal.kind,
            pending_requested_dollars=proposal.requested_dollars,
        )
    assert proposal.requested_quantity is not None
    return replace(
        state,
        lifecycle=Lifecycle.RECONCILING,
        effect_disposition=EffectDisposition.NO_EFFECT,
        exits_used=state.exits_used + 1,
        exit_local_intent_id=proposal.intent_id,
        target_session=proposal.target_session,
        pending_intent_id=proposal.intent_id,
        pending_kind=proposal.kind,
        pending_requested_quantity=proposal.requested_quantity,
    )


def _snapshot_blockers(state: OwnershipSnapshot) -> tuple[Blocker, ...]:
    result: list[Blocker] = []
    if any(
        value is None
        for value in (
            state.account_fingerprint,
            state.source_head,
            state.source_tree,
            state.config_digest,
            state.binding_digest,
            state.lifecycle_id,
        )
    ):
        result.append(Blocker.MISSING_IDENTITY)
    if state.symbol != SYMBOL or state.strategy != STRATEGY:
        result.append(Blocker.IDENTITY_MISMATCH)
    if state.baseline_quantity != _ZERO:
        result.append(Blocker.BASELINE_POSITION_UNPROVEN)
    if (
        state.entries_used not in (0, 1)
        or state.exits_used not in (0, 1)
        or state.exits_used > state.entries_used
        or state.entry_reserved_dollars > ENTRY_BUDGET
        or state.cumulative_sold > state.cumulative_bought
        or state.owned_quantity < _ZERO
        or (state.cumulative_bought == _ZERO)
        != (state.cumulative_entry_filled_dollars == _ZERO)
    ):
        result.append(Blocker.INVALID_SNAPSHOT)
    if (
        state.entries_used
        or state.exits_used
        or state.pending_intent_id is not None
        or state.cumulative_bought > _ZERO
        or state.cumulative_sold > _ZERO
    ) and state.target_session is None:
        result.append(Blocker.INVALID_SNAPSHOT)
    if state.entries_used == 0 and any(
        (
            state.entry_reserved_dollars != _ZERO,
            state.cumulative_bought != _ZERO,
            state.cumulative_entry_filled_dollars != _ZERO,
            state.entry_local_intent_id is not None,
            state.entry_provider_order_id is not None,
        )
    ):
        result.append(Blocker.INVALID_SNAPSHOT)
    if state.entries_used == 1 and (
        state.entry_reserved_dollars <= _ZERO or state.entry_local_intent_id is None
    ):
        result.append(Blocker.INVALID_SNAPSHOT)
    if state.exits_used == 0 and any(
        (
            state.cumulative_sold != _ZERO,
            state.exit_local_intent_id is not None,
            state.exit_provider_order_id is not None,
        )
    ):
        result.append(Blocker.INVALID_SNAPSHOT)
    if state.exits_used == 1 and state.exit_local_intent_id is None:
        result.append(Blocker.INVALID_SNAPSHOT)
    if state.cumulative_bought > _ZERO and (
        state.entry_local_intent_id is None or state.entry_provider_order_id is None
    ):
        result.append(Blocker.OWNERSHIP_UNPROVEN)
    if state.cumulative_sold > _ZERO and (
        state.exit_local_intent_id is None or state.exit_provider_order_id is None
    ):
        result.append(Blocker.OWNERSHIP_UNPROVEN)
    if (
        state.entry_local_intent_id is not None
        and state.entry_local_intent_id == state.exit_local_intent_id
    ) or (
        state.entry_provider_order_id is not None
        and state.entry_provider_order_id == state.exit_provider_order_id
    ):
        result.append(Blocker.INVALID_SNAPSHOT)
    if state.pending_intent_id is not None:
        expected = (
            state.entry_local_intent_id
            if state.pending_kind is IntentKind.ENTRY
            else state.exit_local_intent_id
        )
        if state.pending_intent_id != expected:
            result.append(Blocker.INVALID_SNAPSHOT)
    if state.working_remainder > _ZERO:
        provider_id = (
            state.entry_provider_order_id
            if state.pending_kind is IntentKind.ENTRY
            else state.exit_provider_order_id
        )
        if state.pending_kind is None or provider_id is None:
            result.append(Blocker.INVALID_SNAPSHOT)
    return tuple(dict.fromkeys(result))


def _identity_blockers(
    state: OwnershipSnapshot, context: AdmissionContext
) -> tuple[Blocker, ...]:
    expected = (
        state.account_fingerprint,
        state.symbol,
        state.strategy,
        state.source_head,
        state.source_tree,
        state.config_digest,
        state.binding_digest,
        state.lifecycle_id,
    )
    actual = (
        context.account_fingerprint,
        context.symbol,
        context.strategy,
        context.source_head,
        context.source_tree,
        context.config_digest,
        context.binding_digest,
        context.lifecycle_id,
    )
    result = []
    if any(value is None for value in actual):
        result.append(Blocker.MISSING_IDENTITY)
    if expected != actual or context.symbol != SYMBOL or context.strategy != STRATEGY:
        result.append(Blocker.IDENTITY_MISMATCH)
    return tuple(result)


def _gate_blockers(context: AdmissionContext) -> tuple[Blocker, ...]:
    if any(g.status is GateStatus.UNKNOWN for g in context.gates.all):
        return (Blocker.GATE_UNKNOWN,)
    if any(g.status is GateStatus.FAIL for g in context.gates.all):
        return (Blocker.GATE_FAILED,)
    return ()


def _position_blockers(
    state: OwnershipSnapshot, context: AdmissionContext
) -> tuple[Blocker, ...]:
    if context.observed_position is None:
        return (Blocker.GATE_UNKNOWN,)
    expected = _add(state.baseline_quantity, state.owned_quantity)
    return () if context.observed_position == expected else (Blocker.POSITION_MISMATCH,)


def _intent_blockers(
    state: OwnershipSnapshot, proposal: IntentProposal, context: AdmissionContext
) -> tuple[Blocker, ...]:
    result: list[Blocker] = []
    if proposal.kind is IntentKind.ENTRY:
        amount = proposal.requested_dollars
        if context.strategy_signal is not StrategySignal.BUY:
            result.append(Blocker.STRATEGY_SIGNAL_REQUIRED)
        if state.entries_used:
            result.append(Blocker.ENTRY_ALREADY_USED)
        if state.owned_quantity != _ZERO:
            result.append(Blocker.OWNERSHIP_UNPROVEN)
        if amount is None or amount <= _ZERO or not _multiple(amount, _CENT):
            result.append(Blocker.INVALID_ENTRY_AMOUNT)
            return tuple(result)
        if amount > ENTRY_ORDER_LIMIT:
            result.append(Blocker.ENTRY_ORDER_LIMIT)
        if _add(state.entry_reserved_dollars, amount) > ENTRY_BUDGET:
            result.append(Blocker.ENTRY_BUDGET_EXHAUSTED)
        if context.current_price is None or context.observed_position is None:
            result.append(Blocker.GATE_UNKNOWN)
        elif (
            _add(_multiply(context.current_price, context.observed_position), amount)
            > ENTRY_GROSS_LIMIT
        ):
            result.append(Blocker.ENTRY_GROSS_LIMIT)
        if not context.exit_capability.permits_entry:
            result.append(Blocker.EXIT_CAPABILITY_UNPROVEN)
        return tuple(result)

    if state.exits_used:
        result.append(Blocker.EXIT_ALREADY_USED)
    if (
        state.entries_used != 1
        or state.owned_quantity <= _ZERO
        or state.entry_provider_order_id is None
        or state.effect_disposition is not EffectDisposition.CONFIRMED
    ):
        result.append(Blocker.OWNERSHIP_UNPROVEN)
    if proposal.kind is IntentKind.STRATEGY_EXIT:
        if context.strategy_signal is not StrategySignal.SELL:
            result.append(Blocker.STRATEGY_SIGNAL_REQUIRED)
    elif context.strategy_signal not in (StrategySignal.HOLD, StrategySignal.SELL):
        result.append(Blocker.STRATEGY_SIGNAL_REQUIRED)
    quantity = proposal.requested_quantity
    if quantity is None or quantity <= _ZERO or quantity != state.owned_quantity:
        result.append(Blocker.EXIT_NOT_EXACT_OWNED_QUANTITY)
        return tuple(result)
    if context.sellable_quantity is None:
        result.append(Blocker.GATE_UNKNOWN)
    elif context.sellable_quantity < quantity:
        result.append(Blocker.EXIT_NOT_SELLABLE)
    capability = context.exit_capability
    if not capability.usable:
        result.append(Blocker.EXIT_CAPABILITY_UNPROVEN)
        return tuple(result)
    low, step, high = (
        capability.minimum_quantity,
        capability.quantity_increment,
        capability.maximum_quantity,
    )
    minimum_notional = capability.minimum_sell_notional
    assert low is not None and step is not None and minimum_notional is not None
    if (
        quantity < low
        or (high is not None and quantity > high)
        or not _multiple(quantity, step)
        or _decimal_places(quantity) > MAX_EXIT_DECIMAL_PLACES
    ):
        result.append(Blocker.EXIT_SIZE_UNSUPPORTED)
    elif (
        minimum_notional > _ZERO
        and capability.exact_full_close_below_minimum_supported is not True
    ):
        result.append(Blocker.EXIT_CAPABILITY_UNPROVEN)
    # Reducing exits can exceed $10 current notional; market fills have no
    # price guarantee.
    return tuple(result)


def _session(value: str | None, *, required: bool = False) -> None:
    if value is None:
        if required:
            raise ValueError("ISO market session is required")
        return
    if not isinstance(value, str):
        raise TypeError("market session must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("market session must be an ISO date") from error
    if parsed.isoformat() != value:
        raise ValueError("market session must use canonical ISO date form")


def _add(left: Decimal, right: Decimal) -> Decimal:
    with localcontext(_ARITHMETIC) as context:
        return context.add(left, right)


def _sub(left: Decimal, right: Decimal) -> Decimal:
    with localcontext(_ARITHMETIC) as context:
        return context.subtract(left, right)


def _multiply(left: Decimal, right: Decimal) -> Decimal:
    with localcontext(_ARITHMETIC) as context:
        return context.multiply(left, right)


def _integer_at(value: Decimal, exponent: int) -> int:
    parts = value.as_tuple()
    coefficient = int("".join(str(digit) for digit in parts.digits) or "0")
    return (-coefficient if parts.sign else coefficient) * 10 ** (
        parts.exponent - exponent
    )


def _multiple(value: Decimal, increment: Decimal) -> bool:
    exponent = min(value.as_tuple().exponent, increment.as_tuple().exponent)
    divisor = _integer_at(increment, exponent)
    return divisor != 0 and _integer_at(value, exponent) % divisor == 0


def _decimal_places(value: Decimal) -> int:
    parts = value.as_tuple()
    exponent, digits = parts.exponent, list(parts.digits)
    while exponent < 0 and digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    return max(0, -exponent)
