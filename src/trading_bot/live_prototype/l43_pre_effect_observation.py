"""Source-owned, read-only Architecture 147 L43 pre-effect observation.

The callable below assembles one fresh observation from narrow injected
boundaries.  It never creates, reserves, reviews, places, cancels, or repairs
durable state.  Its plan is a detached request for a later separately reviewed
effect boundary; it is not placement authority.

Provider construction is deliberately an injected boundary.  Importing this
module constructs no broker transport, credentials, Alpaca provider, filesystem
state, or session.  The only Robinhood methods the observer uses are the three
bounded account/position/order reads.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo

from trading_bot.desktop_paper.robinhood_read import (
    AgenticAccountIdentity,
    EquityPositionObservation,
    parse_position,
    resolve_account,
)
from trading_bot.domain import OrderSide
from trading_bot.live_prototype.alpaca_runtime_signal_provider import (
    RuntimeSignalSnapshot,
)
from trading_bot.live_prototype.alpaca_signal_inputs import (
    LIVE_SIGNAL_PRICE_BASIS,
    REQUIRED_COMPLETED_SESSIONS,
    SIGNAL_SYMBOL,
    SignalDecision,
    decide_35_50,
    select_latest_completed_sessions,
)
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.durable_state import (
    ENTRY_LIMIT,
    DurableState,
    IntentStatus,
    OrderObservation,
    OrderState,
    OrderStatus,
    ReconciliationSnapshot,
    RuntimeIdentity,
)
from trading_bot.live_prototype.l43_production_owner import (
    D34SignalFacts,
    ExactOwnedSellProposal,
    L43ContinuityResult,
    L43ProductionOwner,
    L43Provenance,
    L43SourceIdentity,
    Q62JournalOrigin,
    RecoveryFacts,
    XnysSessionFacts,
)
from trading_bot.live_prototype.l43_state import L43StateSnapshot
from trading_bot.live_prototype.live_contract import OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import ReadinessIdentity
from trading_bot.live_prototype.tiny_live_policy import (
    TINY_LIVE_POLICY,
    EntryTerminalOutcome,
    ExactSellBlocker,
    ExactSellStatus,
    ManualCloseTrigger,
    ReconciledOwnedPosition,
    SellOrderArguments,
    SellOrderContext,
    SellOrderType,
    SellSession,
    SellSide,
    SellTimeInForce,
    TerminalEntryEvidence,
    evaluate_exact_owned_sell_proposal,
)
from trading_bot.live_prototype.tiny_live_readiness_observer import (
    BINDING_SHA256,
    CONFIGURATION_SHA256,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.robinhood_mcp.models import (
    RobinhoodEquityOrder,
    RobinhoodEquityOrdersPage,
)
from trading_bot.robinhood_mcp.parsing import parse_equity_orders_response

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ZERO = Decimal("0")
_NEW_YORK = ZoneInfo("America/New_York")
_SANITIZED_TIME = datetime(1970, 1, 1, tzinfo=UTC)
_NOTIONAL_CONTEXT = Context(prec=80, Emin=-999999, Emax=999999)
_ACCOUNT_TTL = timedelta(minutes=2)
_POSITION_TTL = timedelta(minutes=2)
_ORDERS_TTL = timedelta(minutes=2)
_MAX_POSITION_PAGES = 8
_MAX_POSITIONS = 2_000
_MAX_ORDER_PAGES = 40
_MAX_ORDERS = 10_000
_TERMINAL_ENTRY_MAP = {
    IntentStatus.FILLED: EntryTerminalOutcome.FILLED,
    IntentStatus.CANCELED: EntryTerminalOutcome.CANCELED,
    IntentStatus.REJECTED: EntryTerminalOutcome.REJECTED,
}
_PROVIDER_TERMINAL_TO_STATE = {
    "filled": (IntentStatus.FILLED, OrderStatus.FILLED),
    "canceled": (IntentStatus.CANCELED, OrderStatus.CANCELED),
    "cancelled": (IntentStatus.CANCELED, OrderStatus.CANCELED),
    "rejected": (IntentStatus.REJECTED, OrderStatus.REJECTED),
}
_TERMINAL_ENTRY_TO_ORDER_STATUS = {
    IntentStatus.FILLED: OrderStatus.FILLED,
    IntentStatus.CANCELED: OrderStatus.CANCELED,
    IntentStatus.REJECTED: OrderStatus.REJECTED,
}


class L43PreEffectOutcome(StrEnum):
    """Closed source-only outcomes; none is placement authority."""

    NO_ACTION_SIGNAL = "NO_ACTION_SIGNAL"
    BLOCKED = "BLOCKED"
    MANUAL_CLOSE_REQUIRED = "MANUAL_CLOSE_REQUIRED"
    READY_FOR_L43_ENTRY_EFFECT_REVIEW = "READY_FOR_L43_ENTRY_EFFECT_REVIEW"
    READY_FOR_L43_EXACT_OWNED_REVIEW = "READY_FOR_L43_EXACT_OWNED_REVIEW"


class L43PreEffectBlocker(StrEnum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    CONTINUITY_UNPROVEN = "CONTINUITY_UNPROVEN"
    STATE_SNAPSHOT_UNAVAILABLE = "STATE_SNAPSHOT_UNAVAILABLE"
    STATE_ORIGIN_MISMATCH = "STATE_ORIGIN_MISMATCH"
    STATE_IDENTITY_MISMATCH = "STATE_IDENTITY_MISMATCH"
    STATE_TAIL_CHANGED = "STATE_TAIL_CHANGED"
    CONFIGURATION_MISMATCH = "CONFIGURATION_MISMATCH"
    CLOCK_UNAVAILABLE = "CLOCK_UNAVAILABLE"
    SESSION_UNPROVEN = "SESSION_UNPROVEN"
    SIGNAL_UNAVAILABLE = "SIGNAL_UNAVAILABLE"
    SIGNAL_STALE = "SIGNAL_STALE"
    ACCOUNT_READ_FAILED = "ACCOUNT_READ_FAILED"
    ACCOUNT_INVALID = "ACCOUNT_INVALID"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
    ACCOUNT_STALE = "ACCOUNT_STALE"
    POSITION_READ_FAILED = "POSITION_READ_FAILED"
    POSITION_INVALID = "POSITION_INVALID"
    POSITION_DUPLICATE = "POSITION_DUPLICATE"
    POSITION_STALE = "POSITION_STALE"
    ORDER_READ_FAILED = "ORDER_READ_FAILED"
    ORDER_INVALID = "ORDER_INVALID"
    ORDERS_STALE = "ORDERS_STALE"
    ORDER_SCOPE_UNPROVEN = "ORDER_SCOPE_UNPROVEN"
    ORDER_COVERAGE_INCOMPLETE = "ORDER_COVERAGE_INCOMPLETE"
    WORKING_OR_UNKNOWN_ORDER = "WORKING_OR_UNKNOWN_ORDER"
    UNRELATED_SPY_ORDER = "UNRELATED_SPY_ORDER"
    STATE_UNRESOLVED = "STATE_UNRESOLVED"
    ENTRY_ALREADY_CONSUMED = "ENTRY_ALREADY_CONSUMED"
    ENTRY_RISK_INVALID = "ENTRY_RISK_INVALID"
    POSITION_NOT_FLAT = "POSITION_NOT_FLAT"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    SELL_NOT_TERMINAL = "SELL_NOT_TERMINAL"
    SELL_POSITION_MISMATCH = "SELL_POSITION_MISMATCH"
    SELLABLE_QUANTITY_INSUFFICIENT = "SELLABLE_QUANTITY_INSUFFICIENT"
    EXACT_RESIDUAL_UNSUPPORTED = "EXACT_RESIDUAL_UNSUPPORTED"
    SELL_PROPOSAL_INVALID = "SELL_PROPOSAL_INVALID"
    OBSERVATION_INDETERMINATE = "OBSERVATION_INDETERMINATE"


class L43PlanKind(StrEnum):
    ENTRY = "ENTRY"
    EXACT_OWNED_SELL_REVIEW = "EXACT_OWNED_SELL_REVIEW"


class L43OrderScope(StrEnum):
    ACCOUNT_WIDE_ALL_AGENTS = "ACCOUNT_WIDE_ALL_AGENTS"


@dataclass(frozen=True, slots=True)
class L43OrderScopeProof:
    """A verifier result for complete account-wide SPY order visibility.

    Current checked-in Robinhood transport/schema evidence does not produce
    this proof.  Therefore normal composition must leave the verifier absent,
    which fails closed.  Fake tests may inject a verifier to exercise the
    positive derivation path without claiming production scope qualification.
    """

    scope: L43OrderScope
    query_sha256: str
    pages_read: int
    row_count: int
    exhausted: bool
    evidence_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope, L43OrderScope):
            raise TypeError("order scope must use the closed scope type")
        _sha256(self.query_sha256, "order query digest")
        _sha256(self.evidence_sha256, "order scope evidence digest")
        if (
            type(self.pages_read) is not int
            or self.pages_read <= 0
            or type(self.row_count) is not int
            or self.row_count < 0
            or type(self.exhausted) is not bool
        ):
            raise ValueError("order scope counts are invalid")


class RobinhoodPreEffectReadBoundary(Protocol):
    """Narrow account/position/order-only subset of the current read transport."""

    def get_accounts(self) -> Mapping[str, object]: ...

    def get_equity_positions(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...


class L43StateSnapshotReader(Protocol):
    """Read one detached origin-bound durable-state snapshot."""

    def __call__(self) -> L43StateSnapshot: ...


class L43OrderScopeVerifier(Protocol):
    """Separately source-owned assertion of complete all-agent order scope."""

    def verify_account_wide_spy_orders(
        self,
        *,
        account_fingerprint: str,
        query_sha256: str,
        pages_read: int,
        row_count: int,
        exhausted: bool,
    ) -> L43OrderScopeProof | None: ...


class _PublishedSessionAuthority(Protocol):
    manifest_version: str

    def schedule_for(self, session_date: date) -> object | None: ...


@dataclass(frozen=True, slots=True)
class L43PreEffectDependencies:
    """Injected read boundaries for one source-owned L43 observation.

    The callbacks construct providers only when the observation calls them.
    Tests inject fakes.  No production Robinhood or Alpaca builder is supplied
    by this module, and no dependency accepts caller-assembled broker facts.
    """

    source_reader: Callable[[], L43SourceIdentity]
    continuity_owner: L43ProductionOwner
    origin: Q62JournalOrigin
    state_snapshot_reader: L43StateSnapshotReader
    robinhood_builder: Callable[[], RobinhoodPreEffectReadBoundary]
    signal_provider_builder: Callable[[], object]
    clock: Callable[[], datetime]
    session_authority: _PublishedSessionAuthority | None = None
    order_scope_verifier: L43OrderScopeVerifier | None = None

    def __post_init__(self) -> None:
        for callback, label in (
            (self.source_reader, "source reader"),
            (self.state_snapshot_reader, "state snapshot reader"),
            (self.robinhood_builder, "Robinhood read builder"),
            (self.signal_provider_builder, "signal provider builder"),
            (self.clock, "clock"),
        ):
            if not callable(callback):
                raise TypeError(f"{label} must be callable")
        if type(self.continuity_owner) is not L43ProductionOwner:
            raise TypeError("continuity owner must be exact L43ProductionOwner")
        if type(self.origin) is not Q62JournalOrigin:
            raise TypeError("origin must be exact Q62JournalOrigin")
        if self.session_authority is not None and not callable(
            getattr(self.session_authority, "schedule_for", None)
        ):
            raise TypeError("session authority must provide schedule_for")
        if self.order_scope_verifier is not None and not callable(
            getattr(self.order_scope_verifier, "verify_account_wide_spy_orders", None)
        ):
            raise TypeError("order scope verifier is invalid")


@dataclass(frozen=True, slots=True)
class L43PreEffectPlan:
    """Detached semantic plan; provider IDs remain internal in typed contracts.

    ``binding_sha256`` binds every material source, continuity, durable tail,
    account, position/order, signal/session/recovery and plan fact.  A separate
    effect boundary must reobserve and compare this digest before it acts.
    """

    kind: L43PlanKind
    current_source: L43SourceIdentity
    provenance: L43Provenance
    continuity: L43ContinuityResult
    state_last_sequence: int
    state_tail_sha256: str
    state_journal_sha256: str
    reconciliation_snapshot: ReconciliationSnapshot
    account_fingerprint: str
    positions_digest: str
    relevant_orders_digest: str
    order_scope_digest: str
    session: XnysSessionFacts
    signal: D34SignalFacts
    recovery: RecoveryFacts
    observation_as_of: datetime
    signal_observation_digest: str
    positions_observation_digest: str
    orders_observation_digest: str
    order_scope_evidence_digest: str
    requested_entry_risk: Decimal | None = None
    sell_proposal: ExactOwnedSellProposal | None = None
    binding_sha256: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, L43PlanKind):
            raise TypeError("plan kind must be closed")
        if type(self.current_source) is not L43SourceIdentity:
            raise TypeError("plan source must be L43SourceIdentity")
        if type(self.provenance) is not L43Provenance:
            raise TypeError("plan provenance must be L43Provenance")
        if (
            type(self.continuity) is not L43ContinuityResult
            or not self.continuity.accepted
        ):
            raise ValueError("plan requires accepted source/Q62 continuity")
        if type(self.state_last_sequence) is not int or self.state_last_sequence < 0:
            raise ValueError("durable state sequence must be nonnegative")
        _sha256(self.state_tail_sha256, "durable state tail digest")
        _sha256(self.state_journal_sha256, "durable state journal digest")
        if type(self.reconciliation_snapshot) is not ReconciliationSnapshot:
            raise TypeError("plan requires detached factual reconciliation")
        for digest, label in (
            (self.account_fingerprint, "account fingerprint"),
            (self.positions_digest, "positions digest"),
            (self.relevant_orders_digest, "orders digest"),
            (self.order_scope_digest, "order scope digest"),
        ):
            _sha256(digest, label)
        if type(self.session) is not XnysSessionFacts:
            raise TypeError("plan session facts are invalid")
        if type(self.signal) is not D34SignalFacts:
            raise TypeError("plan signal facts are invalid")
        if type(self.recovery) is not RecoveryFacts:
            raise TypeError("plan recovery facts are invalid")
        _utc_datetime(self.observation_as_of, "plan observation time")
        for digest, label in (
            (self.signal_observation_digest, "signal observation digest"),
            (self.positions_observation_digest, "positions observation digest"),
            (self.orders_observation_digest, "orders observation digest"),
            (self.order_scope_evidence_digest, "order scope evidence digest"),
        ):
            _sha256(digest, label)
        if self.kind is L43PlanKind.ENTRY:
            if (
                type(self.requested_entry_risk) is not Decimal
                or not self.requested_entry_risk.is_finite()
                or self.requested_entry_risk <= _ZERO
                or self.requested_entry_risk > ENTRY_LIMIT
                or self.sell_proposal is not None
            ):
                raise ValueError("entry plan has invalid risk or sell proposal")
        elif (
            self.requested_entry_risk is not None
            or type(self.sell_proposal) is not ExactOwnedSellProposal
        ):
            raise ValueError("sell plan requires only an exact-owned proposal")
        computed = _plan_digest(self)
        if self.binding_sha256 and self.binding_sha256 != computed:
            raise ValueError("plan binding digest differs")
        object.__setattr__(self, "binding_sha256", computed)


@dataclass(frozen=True, slots=True)
class L43PreEffectResult:
    """Sanitized observation result with zero authority/effect counters."""

    outcome: L43PreEffectOutcome
    blockers: tuple[L43PreEffectBlocker, ...]
    evidence_sha256: str
    evidence_json: bytes
    plan: L43PreEffectPlan | None
    observed_at: datetime
    robinhood_read_count: int
    robinhood_page_count: int
    alpaca_provider_call_count: int
    credential_read_count: int
    manual_close_trigger: ManualCloseTrigger | None = None
    manual_close_residual_quantity: Decimal | None = None
    manual_close_state_sequence: int | None = None
    manual_close_state_tail_sha256: str | None = None
    manual_close_basis_sha256: str | None = None
    reservation_count: int = 0
    review_count: int = 0
    placement_count: int = 0
    cancellation_count: int = 0
    provider_mutation_count: int = 0
    placement_authority_granted: bool = False
    trade_authority_granted: bool = False
    live_ready: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, L43PreEffectOutcome):
            raise TypeError("pre-effect outcome must be closed")
        if type(self.blockers) is not tuple or any(
            not isinstance(item, L43PreEffectBlocker) for item in self.blockers
        ):
            raise TypeError("pre-effect blockers must be a typed tuple")
        _sha256(self.evidence_sha256, "pre-effect evidence digest")
        if type(self.evidence_json) is not bytes:
            raise TypeError("evidence JSON must be detached bytes")
        if hashlib.sha256(self.evidence_json).hexdigest() != self.evidence_sha256:
            raise ValueError("evidence digest does not match canonical bytes")
        _utc_datetime(self.observed_at, "result observation time")
        for value, label in (
            (self.robinhood_read_count, "Robinhood read count"),
            (self.robinhood_page_count, "Robinhood page count"),
            (self.alpaca_provider_call_count, "Alpaca provider call count"),
            (self.credential_read_count, "credential read count"),
            (self.reservation_count, "reservation count"),
            (self.review_count, "review count"),
            (self.placement_count, "placement count"),
            (self.cancellation_count, "cancellation count"),
            (self.provider_mutation_count, "provider mutation count"),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be nonnegative")
        if any(
            (
                self.reservation_count,
                self.review_count,
                self.placement_count,
                self.cancellation_count,
                self.provider_mutation_count,
            )
        ) or any(
            (
                self.placement_authority_granted,
                self.trade_authority_granted,
                self.live_ready,
            )
        ):
            raise ValueError("pre-effect result cannot grant or report effects")
        ready = self.outcome in {
            L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW,
            L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW,
        }
        if ready != (type(self.plan) is L43PreEffectPlan):
            raise ValueError("only ready outcomes carry a detached plan")
        manual_close = self.outcome is L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED
        if manual_close != (self.manual_close_trigger is not None):
            raise ValueError("manual-close outcome requires its typed trigger")
        if self.manual_close_trigger is not None and not isinstance(
            self.manual_close_trigger, ManualCloseTrigger
        ):
            raise TypeError("manual-close trigger must be typed")
        if manual_close:
            if (
                self.manual_close_trigger
                is not ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL
            ):
                raise ValueError("only unsupported residual has an observation outcome")
            if (
                type(self.manual_close_residual_quantity) is not Decimal
                or not self.manual_close_residual_quantity.is_finite()
                or self.manual_close_residual_quantity <= _ZERO
            ):
                raise ValueError(
                    "manual-close result requires an exact positive residual"
                )
            if self.blockers != (L43PreEffectBlocker.EXACT_RESIDUAL_UNSUPPORTED,):
                raise ValueError("manual-close result requires its exact blocker")
            if (
                type(self.manual_close_state_sequence) is not int
                or self.manual_close_state_sequence < 0
            ):
                raise ValueError("manual-close result requires a state sequence")
            _sha256(self.manual_close_state_tail_sha256, "manual-close state tail")
            _sha256(self.manual_close_basis_sha256, "manual-close basis digest")
        elif any(
            value is not None
            for value in (
                self.manual_close_residual_quantity,
                self.manual_close_state_sequence,
                self.manual_close_state_tail_sha256,
                self.manual_close_basis_sha256,
            )
        ):
            raise ValueError("only manual-close results carry a residual basis")
        if self.outcome is L43PreEffectOutcome.NO_ACTION_SIGNAL and self.blockers:
            raise ValueError("no-action outcome cannot contain blockers")
        if self.outcome is L43PreEffectOutcome.BLOCKED and not self.blockers:
            raise ValueError("blocked outcome requires a sanitized blocker")


@dataclass(frozen=True, slots=True)
class _PageRead:
    rows: tuple[object, ...]
    page_count: int
    row_count: int
    exhausted: bool


@dataclass(frozen=True, slots=True)
class _StateView:
    origin: Q62JournalOrigin
    state: DurableState
    last_sequence: int
    tail_sha256: str
    journal_sha256: str
    sell_review_pending: bool
    manual_close_required: bool


@dataclass(frozen=True, slots=True)
class _BrokerView:
    account: AgenticAccountIdentity
    positions: tuple[EquityPositionObservation, ...]
    spy_position_quantity: Decimal
    spy_sellable_quantity: Decimal
    spy_orders: tuple[RobinhoodEquityOrder, ...]
    all_order_count: int
    positions_digest: str
    orders_digest: str
    order_scope_digest: str
    positions_observation_digest: str
    orders_observation_digest: str
    order_scope_evidence_digest: str
    reconciliation: ReconciliationSnapshot
    account_observed_at: datetime
    positions_observed_at: datetime
    orders_observed_at: datetime
    robinhood_read_count: int
    robinhood_page_count: int


@dataclass(frozen=True, slots=True)
class _SessionView:
    facts: XnysSessionFacts
    opens_at: datetime
    closes_at: datetime


@dataclass(frozen=True, slots=True)
class _ManualCloseEvidence:
    trigger: ManualCloseTrigger
    residual_quantity: Decimal
    state_sequence: int
    state_tail_sha256: str
    basis_sha256: str
    safe_facts: tuple[tuple[str, str | int], ...]


def observe_l43_pre_effect(
    dependencies: L43PreEffectDependencies,
    *,
    requested_entry_risk: Decimal = Decimal("10.00"),
) -> L43PreEffectResult:
    """Observe fresh L43 source/account/state/session/signal facts once.

    There are no state mutations, reservations, reviews, placements, cancels,
    or retries here.  Account-wide order coverage is an independently verified
    requirement.  As the current checked-in transport does not prove that
    scope, a missing/unknown verifier produces a closed BLOCKED result.
    """

    if type(dependencies) is not L43PreEffectDependencies:
        raise TypeError("exact L43PreEffectDependencies required")
    counters = _Counters()
    now = _SANITIZED_TIME
    source: L43SourceIdentity | None = None
    plan: L43PreEffectPlan | None = None
    outcome = L43PreEffectOutcome.BLOCKED
    blockers: list[L43PreEffectBlocker] = []
    manual_close: _ManualCloseEvidence | None = None
    state_before: _StateView | None = None
    try:
        source = _read_source(dependencies.source_reader)
        state_before = _read_state_snapshot(
            dependencies.state_snapshot_reader, dependencies.origin
        )
        if state_before.origin != dependencies.origin:
            raise _Blocked(L43PreEffectBlocker.STATE_ORIGIN_MISMATCH)
        if state_before.state.identity != dependencies.origin.runtime_identity:
            raise _Blocked(L43PreEffectBlocker.STATE_IDENTITY_MISMATCH)
        if (
            state_before.manual_close_required
            or state_before.sell_review_pending
            or state_before.state.blocked_reason is not None
        ):
            raise _Blocked(L43PreEffectBlocker.STATE_UNRESOLVED)

        provenance = _source_provenance(dependencies.origin.runtime_identity)
        if (
            provenance.config_digest
            != dependencies.origin.runtime_identity.config_digest
            or provenance.binding_digest
            != dependencies.origin.runtime_identity.binding_digest
        ):
            raise _Blocked(L43PreEffectBlocker.CONFIGURATION_MISMATCH)
        try:
            continuity = dependencies.continuity_owner.prove_continuity(
                origin=dependencies.origin,
                current=source,
                provenance=provenance,
            )
        except Exception:
            raise _Blocked(L43PreEffectBlocker.CONTINUITY_UNPROVEN) from None
        if type(continuity) is not L43ContinuityResult or not continuity.accepted:
            raise _Blocked(L43PreEffectBlocker.CONTINUITY_UNPROVEN)
        if continuity.current != source or continuity.origin != dependencies.origin:
            raise _Blocked(L43PreEffectBlocker.CONTINUITY_UNPROVEN)

        observed_at = _clock(dependencies.clock)
        now = observed_at
        session_authority = dependencies.session_authority or (
            NYSEPublishedRegularSessionAuthority()
        )
        session_view = _session_view(session_authority, observed_at)

        try:
            signal_provider = dependencies.signal_provider_builder()
            snapshot_method = getattr(signal_provider, "snapshot", None)
            if not callable(snapshot_method):
                raise _Blocked(L43PreEffectBlocker.SIGNAL_UNAVAILABLE)
            counters.alpaca_snapshots += 1
            signal_snapshot = snapshot_method(observed_at)
        except _Blocked:
            raise
        except Exception:
            raise _Blocked(L43PreEffectBlocker.SIGNAL_UNAVAILABLE) from None
        if type(signal_snapshot) is RuntimeSignalSnapshot:
            counters.alpaca_provider_calls = signal_snapshot.provider_call_count
            counters.credential_reads = signal_snapshot.credential_read_count
        inputs, signal_decision = _signal_facts(
            signal_snapshot,
            observed_at=observed_at,
            authority=session_authority,
            invested=state_before.state.owned_quantity > _ZERO,
        )
        counters.signal_observation_digest = inputs.digest
        counters.observed_times.append(("signal", observed_at))

        try:
            robinhood = dependencies.robinhood_builder()
        except Exception:
            raise _Blocked(L43PreEffectBlocker.ACCOUNT_READ_FAILED) from None
        broker = _read_broker(
            robinhood,
            dependencies=dependencies,
            origin=dependencies.origin,
            state=state_before.state,
            source=source,
            provenance=provenance,
            target_session=session_view.facts.target_session,
            observed_at=observed_at,
            counters=counters,
        )

        final_as_of = _clock(dependencies.clock)
        now = final_as_of
        _require_fresh(
            observed_at=broker.account_observed_at,
            final_as_of=final_as_of,
            ttl=_ACCOUNT_TTL,
            blocker=L43PreEffectBlocker.ACCOUNT_STALE,
        )
        _require_fresh(
            observed_at=broker.positions_observed_at,
            final_as_of=final_as_of,
            ttl=_POSITION_TTL,
            blocker=L43PreEffectBlocker.POSITION_STALE,
        )
        _require_fresh(
            observed_at=broker.orders_observed_at,
            final_as_of=final_as_of,
            ttl=_ORDERS_TTL,
            blocker=L43PreEffectBlocker.ORDERS_STALE,
        )
        if final_as_of < observed_at:
            raise _Blocked(L43PreEffectBlocker.CLOCK_UNAVAILABLE)
        if final_as_of - observed_at > _ACCOUNT_TTL:
            raise _Blocked(L43PreEffectBlocker.SIGNAL_STALE)
        if not _session_view(session_authority, final_as_of).facts.proven:
            raise _Blocked(L43PreEffectBlocker.SESSION_UNPROVEN)
        if final_as_of.astimezone(_NEW_YORK).date().isoformat() != (
            session_view.facts.target_session
        ):
            raise _Blocked(L43PreEffectBlocker.SESSION_UNPROVEN)

        state_after = _read_state_snapshot(
            dependencies.state_snapshot_reader, dependencies.origin
        )
        if (
            state_after.origin != state_before.origin
            or state_after.last_sequence != state_before.last_sequence
            or state_after.tail_sha256 != state_before.tail_sha256
            or state_after.journal_sha256 != state_before.journal_sha256
            or state_after.state != state_before.state
        ):
            raise _Blocked(L43PreEffectBlocker.STATE_TAIL_CHANGED)
        final_source = _read_source(dependencies.source_reader)
        if final_source != source:
            raise _Blocked(L43PreEffectBlocker.SOURCE_CHANGED)

        recovery = _recovery_facts(
            state=state_before.state,
            broker=broker,
            source=source,
            provenance=provenance,
            continuity=continuity,
            session=session_view.facts,
            signal_inputs_digest=_signal_semantic_digest(inputs, signal_decision),
            signal=signal_decision,
        )
        decision_facts = D34SignalFacts(
            inputs_digest=_signal_semantic_digest(inputs, signal_decision),
            decision=signal_decision,
        )
        state = state_before.state
        if state.entry is not None and state.entry.status not in _TERMINAL_ENTRY_MAP:
            raise _Blocked(L43PreEffectBlocker.STATE_UNRESOLVED)
        if state.exit is not None:
            raise _Blocked(L43PreEffectBlocker.STATE_UNRESOLVED)
        if broker.account.fingerprint != provenance.account_fingerprint:
            raise _Blocked(L43PreEffectBlocker.ACCOUNT_MISMATCH)

        if state.entry is None:
            if broker.spy_position_quantity != _ZERO:
                raise _Blocked(L43PreEffectBlocker.POSITION_NOT_FLAT)
            if any(not _order_terminal(order) for order in broker.spy_orders):
                raise _Blocked(L43PreEffectBlocker.WORKING_OR_UNKNOWN_ORDER)
            if signal_decision is not SignalDecision.BUY:
                outcome = L43PreEffectOutcome.NO_ACTION_SIGNAL
            else:
                _validate_entry_risk(requested_entry_risk)
                if not recovery.reconciled or recovery.unresolved_effects:
                    raise _Blocked(L43PreEffectBlocker.RECONCILIATION_FAILED)
                reconciliation = broker.reconciliation
                plan = _make_plan(
                    kind=L43PlanKind.ENTRY,
                    source=source,
                    provenance=provenance,
                    continuity=continuity,
                    state=state_before,
                    reconciliation=reconciliation,
                    broker=broker,
                    scope_digest=broker.order_scope_digest,
                    session=session_view.facts,
                    signal=decision_facts,
                    recovery=recovery,
                    observed_at=final_as_of,
                    signal_observation_digest=inputs.digest,
                    requested_entry_risk=requested_entry_risk,
                )
                outcome = L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
        else:
            entry = state.entry
            if state.entries_used != 1:
                raise _Blocked(L43PreEffectBlocker.STATE_UNRESOLVED)
            if entry.cumulative_quantity <= _ZERO:
                if signal_decision is SignalDecision.BUY:
                    raise _Blocked(L43PreEffectBlocker.ENTRY_ALREADY_CONSUMED)
                outcome = L43PreEffectOutcome.NO_ACTION_SIGNAL
            else:
                if not state.reconciled or not recovery.reconciled:
                    raise _Blocked(L43PreEffectBlocker.RECONCILIATION_FAILED)
                if broker.spy_position_quantity != state.owned_quantity:
                    raise _Blocked(L43PreEffectBlocker.SELL_POSITION_MISMATCH)
                if broker.spy_sellable_quantity < state.owned_quantity:
                    raise _Blocked(L43PreEffectBlocker.SELLABLE_QUANTITY_INSUFFICIENT)
                if signal_decision is not SignalDecision.SELL:
                    outcome = L43PreEffectOutcome.NO_ACTION_SIGNAL
                else:
                    _require_terminal_entry_reconciled(state, broker.reconciliation)
                    proposal = _exact_owned_sell_proposal(
                        state=state,
                        origin_identity=dependencies.origin.runtime_identity,
                        target_session=session_view.facts.target_session,
                        broker_position=broker.spy_position_quantity,
                        broker_sellable=broker.spy_sellable_quantity,
                        reconciliation=broker.reconciliation,
                    )
                    eligibility = evaluate_exact_owned_sell_proposal(proposal)
                    if (
                        eligibility.status
                        is ExactSellStatus.READY_FOR_NONPLACING_REVIEW
                    ):
                        plan = _make_plan(
                            kind=L43PlanKind.EXACT_OWNED_SELL_REVIEW,
                            source=source,
                            provenance=provenance,
                            continuity=continuity,
                            state=state_before,
                            reconciliation=broker.reconciliation,
                            broker=broker,
                            scope_digest=broker.order_scope_digest,
                            session=session_view.facts,
                            signal=decision_facts,
                            recovery=recovery,
                            observed_at=final_as_of,
                            signal_observation_digest=inputs.digest,
                            sell_proposal=proposal,
                        )
                        outcome = L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW
                    elif (
                        eligibility.manual_close_trigger
                        is ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL
                        and ExactSellBlocker.QUANTITY_SCALE_UNSUPPORTED
                        in eligibility.blockers
                    ):
                        manual_close = _manual_close_evidence(
                            source=source,
                            provenance=provenance,
                            continuity=continuity,
                            state=state_before,
                            broker=broker,
                            session=session_view.facts,
                            signal=decision_facts,
                            recovery=recovery,
                            observed_at=final_as_of,
                            unsupported_proposal_sha256=eligibility.proposal_sha256,
                        )
                        blockers.append(L43PreEffectBlocker.EXACT_RESIDUAL_UNSUPPORTED)
                        outcome = L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED
                    else:
                        raise _Blocked(L43PreEffectBlocker.SELL_PROPOSAL_INVALID)
    except _Blocked as error:
        blockers.append(error.blocker)
        plan = None
        outcome = L43PreEffectOutcome.BLOCKED
    except Exception:
        blockers.append(L43PreEffectBlocker.OBSERVATION_INDETERMINATE)
        plan = None
        outcome = L43PreEffectOutcome.BLOCKED

    if outcome is L43PreEffectOutcome.NO_ACTION_SIGNAL:
        blockers = []
    return _result(
        outcome=outcome,
        blockers=tuple(dict.fromkeys(blockers)),
        plan=plan,
        observed_at=now,
        counters=counters,
        manual_close=manual_close,
    )


@dataclass(slots=True)
class _Counters:
    robinhood_reads: int = 0
    robinhood_pages: int = 0
    alpaca_snapshots: int = 0
    alpaca_provider_calls: int = 0
    credential_reads: int = 0
    observed_times: list[tuple[str, datetime]] = field(default_factory=list)
    signal_observation_digest: str | None = None
    positions_observation_digest: str | None = None
    orders_observation_digest: str | None = None
    order_scope_evidence_digest: str | None = None


class _Blocked(RuntimeError):
    def __init__(self, blocker: L43PreEffectBlocker) -> None:
        self.blocker = blocker
        super().__init__(blocker.value)


def _read_source(reader: Callable[[], L43SourceIdentity]) -> L43SourceIdentity:
    try:
        source = reader()
    except Exception:
        raise _Blocked(L43PreEffectBlocker.SOURCE_UNAVAILABLE) from None
    if type(source) is not L43SourceIdentity:
        raise _Blocked(L43PreEffectBlocker.SOURCE_UNAVAILABLE)
    return source


def _source_provenance(identity: RuntimeIdentity) -> L43Provenance:
    return L43Provenance(
        config_digest=CONFIGURATION_SHA256,
        binding_digest=BINDING_SHA256,
        account_fingerprint=identity.account_fingerprint,
        strategy=identity.strategy,
        symbol=identity.symbol,
    )


def _read_state_snapshot(
    reader: L43StateSnapshotReader,
    expected_origin: Q62JournalOrigin,
) -> _StateView:
    try:
        snapshot = reader()
        if type(snapshot) is not L43StateSnapshot:
            raise ValueError
        anchor = snapshot.origin
        identity = anchor.runtime_identity
        origin = Q62JournalOrigin(
            runtime_identity=identity,
            journal_label=anchor.journal_label,
            journal_sha256=anchor.journal_sha256,
            initialization_event_sha256=anchor.initialization_event_sha256,
            consumed_observation_sha256=anchor.consumed_observation_sha256,
        )
        state = snapshot.state
        sequence = snapshot.last_sequence
        journal_sha256 = snapshot.journal_sha256
        sell_review_pending = snapshot.sell_review_pending
        manual_close_required = snapshot.manual_close_required
    except Exception:
        raise _Blocked(L43PreEffectBlocker.STATE_SNAPSHOT_UNAVAILABLE) from None
    if origin != expected_origin:
        raise _Blocked(L43PreEffectBlocker.STATE_ORIGIN_MISMATCH)
    if type(state) is not DurableState:
        raise _Blocked(L43PreEffectBlocker.STATE_SNAPSHOT_UNAVAILABLE)
    if type(sequence) is not int or sequence < 0:
        raise _Blocked(L43PreEffectBlocker.STATE_SNAPSHOT_UNAVAILABLE)
    _sha256(journal_sha256, "durable state digest")
    tail_sha256 = state.journal_hash
    _sha256(tail_sha256, "durable state tail digest")
    if (
        state.l43_origin != anchor
        or state.last_sequence != sequence
        or state.journal_hash != journal_sha256
        or snapshot.sell_review_pending != state.sell_review_pending
        or type(sell_review_pending) is not bool
        or type(manual_close_required) is not bool
    ):
        raise _Blocked(L43PreEffectBlocker.STATE_SNAPSHOT_UNAVAILABLE)
    return _StateView(
        origin,
        state,
        sequence,
        tail_sha256,
        journal_sha256,
        sell_review_pending,
        manual_close_required,
    )


def _clock(clock: Callable[[], datetime]) -> datetime:
    try:
        value = clock()
    except Exception:
        raise _Blocked(L43PreEffectBlocker.CLOCK_UNAVAILABLE) from None
    return _utc_datetime(value, "clock")


def _session_view(
    authority: _PublishedSessionAuthority,
    as_of: datetime,
) -> _SessionView:
    session_date = as_of.astimezone(_NEW_YORK).date()
    try:
        schedule = authority.schedule_for(session_date)
        opens_at = getattr(schedule, "opens_at", None)
        closes_at = getattr(schedule, "closes_at", None)
        target = getattr(schedule, "session_date", None)
        if (
            schedule is None
            or type(target) is not date
            or target != session_date
            or type(opens_at) is not datetime
            or type(closes_at) is not datetime
            or opens_at.tzinfo is None
            or closes_at.tzinfo is None
            or opens_at >= closes_at
        ):
            raise ValueError
        opens_utc = opens_at.astimezone(UTC)
        closes_utc = closes_at.astimezone(UTC)
        regular = opens_utc <= as_of < closes_utc
        authority_name = getattr(authority, "manifest_version", None)
        if not isinstance(authority_name, str) or not authority_name:
            raise ValueError
        digest = _digest(
            (
                "ARCH147_L43_XNYS_SESSION_V1",
                authority_name,
                session_date.isoformat(),
                opens_utc.isoformat(),
                closes_utc.isoformat(),
                regular,
            )
        )
        facts = XnysSessionFacts(
            target_session=session_date.isoformat(),
            regular_hours=regular,
            session_open=regular,
            authority_digest=digest,
        )
        return _SessionView(facts, opens_utc, closes_utc)
    except Exception:
        raise _Blocked(L43PreEffectBlocker.SESSION_UNPROVEN) from None


def _signal_facts(
    snapshot: object,
    *,
    observed_at: datetime,
    authority: _PublishedSessionAuthority,
    invested: bool,
) -> tuple[CompletedSignalInputs, SignalDecision]:
    if type(snapshot) is not RuntimeSignalSnapshot:
        raise _Blocked(L43PreEffectBlocker.SIGNAL_UNAVAILABLE)
    inputs = snapshot.inputs_for_trading
    if (
        snapshot.status != "READY"
        or snapshot.stale
        or not snapshot.refreshed
        or snapshot.observation_as_of != observed_at
        or snapshot.provider_call_count != 1
        or snapshot.credential_read_count != 1
        or type(inputs) is not CompletedSignalInputs
        or inputs.symbol != SIGNAL_SYMBOL
        or inputs.price_basis != LIVE_SIGNAL_PRICE_BASIS
        or len(inputs.sessions) != REQUIRED_COMPLETED_SESSIONS
        or len(inputs.closes) != REQUIRED_COMPLETED_SESSIONS
        or snapshot.selected_sessions != inputs.selected_sessions
        or inputs.as_of != observed_at
    ):
        raise _Blocked(L43PreEffectBlocker.SIGNAL_STALE)
    try:
        expected = select_latest_completed_sessions(
            observed_at,
            authority=authority,
        )
    except Exception:
        raise _Blocked(L43PreEffectBlocker.SIGNAL_STALE) from None
    if inputs.selected_sessions != expected:
        raise _Blocked(L43PreEffectBlocker.SIGNAL_STALE)
    return inputs, decide_35_50(inputs, invested=invested)


def _signal_semantic_digest(
    inputs: CompletedSignalInputs,
    decision: SignalDecision,
) -> str:
    """Bind exact decision inputs while leaving observation time to evidence."""
    return _digest(
        (
            "ARCH147_L43_D34_SIGNAL_SEMANTICS_V1",
            inputs.symbol,
            tuple(item.isoformat() for item in inputs.selected_sessions),
            tuple(_decimal_text(value) for value in inputs.closes),
            inputs.price_basis,
            inputs.cutoff.isoformat(),
            decision.value,
        )
    )


def _read_broker(
    robinhood: RobinhoodPreEffectReadBoundary,
    *,
    dependencies: L43PreEffectDependencies,
    origin: Q62JournalOrigin,
    state: DurableState,
    source: L43SourceIdentity,
    provenance: L43Provenance,
    target_session: str,
    observed_at: datetime,
    counters: _Counters,
) -> _BrokerView:
    if not all(
        callable(getattr(robinhood, name, None))
        for name in ("get_accounts", "get_equity_positions", "get_equity_orders")
    ):
        raise _Blocked(L43PreEffectBlocker.ACCOUNT_READ_FAILED)
    try:
        counters.robinhood_reads += 1
        account_payload = robinhood.get_accounts()
        account = resolve_account(account_payload)
        if type(account) is not AgenticAccountIdentity:
            raise ValueError
        account_at = _clock(dependencies.clock)
        counters.observed_times.append(("account", account_at))
    except Exception:
        raise _Blocked(L43PreEffectBlocker.ACCOUNT_INVALID) from None

    if account.fingerprint != origin.runtime_identity.account_fingerprint:
        raise _Blocked(L43PreEffectBlocker.ACCOUNT_MISMATCH)

    position_pages = _read_pages(
        reader=robinhood.get_equity_positions,
        arguments={"account_number": account.account_number},
        collection_key="positions",
        parser=_parse_position_page,
        max_pages=_MAX_POSITION_PAGES,
        max_rows=_MAX_POSITIONS,
        counters=counters,
        read_failure=L43PreEffectBlocker.POSITION_READ_FAILED,
        invalid=L43PreEffectBlocker.POSITION_INVALID,
    )
    positions_at = _clock(dependencies.clock)
    try:
        positions = tuple(parse_position(row) for row in position_pages.rows)
    except Exception:
        raise _Blocked(L43PreEffectBlocker.POSITION_INVALID) from None
    spy_positions = tuple(item for item in positions if item.symbol == "SPY")
    if len(spy_positions) > 1:
        raise _Blocked(L43PreEffectBlocker.POSITION_DUPLICATE)
    spy_position = spy_positions[0] if spy_positions else None
    position_quantity = _ZERO if spy_position is None else spy_position.quantity
    sellable_quantity = (
        _ZERO if spy_position is None else spy_position.shares_available_for_sells
    )
    spy_position_material = (
        None
        if spy_position is None
        else (
            spy_position.symbol,
            _decimal_text(spy_position.quantity),
            _decimal_text(spy_position.shares_available_for_sells),
            spy_position.position_type,
        )
    )
    positions_digest = _digest(
        (
            "ARCH147_L43_SPY_POSITION_FACTS_V1",
            account.fingerprint,
            spy_position_material,
        )
    )
    positions_observation_digest = _digest(
        (
            "ARCH147_L43_SPY_POSITION_READ_V1",
            positions_digest,
            tuple(
                sorted(
                    (
                        item.symbol,
                        _decimal_text(item.quantity),
                        _decimal_text(item.shares_available_for_sells),
                        item.position_type,
                    )
                    for item in positions
                )
            ),
            position_pages.page_count,
            position_pages.row_count,
            position_pages.exhausted,
            positions_at.isoformat(),
        )
    )
    counters.positions_observation_digest = positions_observation_digest
    counters.observed_times.append(("positions", positions_at))

    order_arguments = {"account_number": account.account_number, "symbol": "SPY"}
    orders_page = _read_pages(
        reader=robinhood.get_equity_orders,
        arguments=order_arguments,
        collection_key="orders",
        parser=_parse_order_page,
        max_pages=_MAX_ORDER_PAGES,
        max_rows=_MAX_ORDERS,
        counters=counters,
        read_failure=L43PreEffectBlocker.ORDER_READ_FAILED,
        invalid=L43PreEffectBlocker.ORDER_INVALID,
    )
    orders_at = _clock(dependencies.clock)
    orders = tuple(orders_page.rows)
    if any(type(order) is not RobinhoodEquityOrder for order in orders):
        raise _Blocked(L43PreEffectBlocker.ORDER_INVALID)
    order_ids = tuple(order.order_id for order in orders)
    if len(order_ids) != len(set(order_ids)):
        raise _Blocked(L43PreEffectBlocker.ORDER_INVALID)
    spy_orders = tuple(order for order in orders if str(order.symbol) == "SPY")
    if any(str(order.symbol) != "SPY" for order in orders):
        # The read was requested for SPY; ignored symbol scope is not accepted.
        raise _Blocked(L43PreEffectBlocker.ORDER_SCOPE_UNPROVEN)
    query_digest = _digest(
        (
            "ARCH147_L43_ACCOUNT_WIDE_SPY_ORDER_QUERY_V1",
            account.fingerprint,
            tuple(sorted(order_arguments.items())),
        )
    )
    proof: L43OrderScopeProof | None = None
    verifier = dependencies.order_scope_verifier
    if verifier is not None:
        try:
            proof = verifier.verify_account_wide_spy_orders(
                account_fingerprint=account.fingerprint,
                query_sha256=query_digest,
                pages_read=orders_page.page_count,
                row_count=orders_page.row_count,
                exhausted=orders_page.exhausted,
            )
        except Exception:
            proof = None
    if (
        type(proof) is not L43OrderScopeProof
        or proof.scope is not L43OrderScope.ACCOUNT_WIDE_ALL_AGENTS
        or proof.query_sha256 != query_digest
        or proof.pages_read != orders_page.page_count
        or proof.row_count != orders_page.row_count
        or proof.exhausted is not True
        or orders_page.exhausted is not True
    ):
        raise _Blocked(L43PreEffectBlocker.ORDER_SCOPE_UNPROVEN)
    order_scope_digest = _digest(
        (
            "ARCH147_L43_ACCOUNT_WIDE_SPY_ORDER_SCOPE_V1",
            proof.scope.value,
            proof.query_sha256,
            proof.pages_read,
            proof.row_count,
            proof.exhausted,
        )
    )
    counters.order_scope_evidence_digest = proof.evidence_sha256
    if not orders_page.exhausted:
        raise _Blocked(L43PreEffectBlocker.ORDER_COVERAGE_INCOMPLETE)
    orders_digest = _digest(
        (
            "ARCH147_L43_RELEVANT_SPY_ORDERS_V1",
            account.fingerprint,
            tuple(sorted(_order_material(order) for order in spy_orders)),
            orders_page.page_count,
            orders_page.row_count,
            order_scope_digest,
        )
    )
    orders_observation_digest = _digest(
        (
            "ARCH147_L43_RELEVANT_SPY_ORDERS_READ_V1",
            orders_digest,
            proof.evidence_sha256,
            orders_at.isoformat(),
        )
    )
    counters.orders_observation_digest = orders_observation_digest
    counters.observed_times.append(("orders", orders_at))

    unresolved_spy = tuple(order for order in spy_orders if not _order_terminal(order))
    if unresolved_spy:
        raise _Blocked(L43PreEffectBlocker.WORKING_OR_UNKNOWN_ORDER)

    reconciliation = _reconciliation_snapshot(
        state=state,
        origin_identity=origin.runtime_identity,
        spy_position=position_quantity,
        spy_orders=spy_orders,
    )
    del source, provenance, target_session, observed_at
    return _BrokerView(
        account=account,
        positions=positions,
        spy_position_quantity=position_quantity,
        spy_sellable_quantity=sellable_quantity,
        spy_orders=spy_orders,
        all_order_count=orders_page.row_count,
        positions_digest=positions_digest,
        orders_digest=orders_digest,
        order_scope_digest=order_scope_digest,
        positions_observation_digest=positions_observation_digest,
        orders_observation_digest=orders_observation_digest,
        order_scope_evidence_digest=proof.evidence_sha256,
        reconciliation=reconciliation,
        account_observed_at=account_at,
        positions_observed_at=positions_at,
        orders_observed_at=orders_at,
        robinhood_read_count=counters.robinhood_reads,
        robinhood_page_count=counters.robinhood_pages,
    )


def _read_pages(
    *,
    reader: Callable[[Mapping[str, object]], Mapping[str, object]],
    arguments: dict[str, object],
    collection_key: str,
    parser: Callable[[Mapping[str, object]], Sequence[object]],
    max_pages: int,
    max_rows: int,
    counters: _Counters,
    read_failure: L43PreEffectBlocker,
    invalid: L43PreEffectBlocker,
) -> _PageRead:
    rows: list[object] = []
    seen: set[str] = set()
    request = dict(arguments)
    local_pages = 0
    for _ in range(max_pages):
        counters.robinhood_reads += 1
        counters.robinhood_pages += 1
        local_pages += 1
        try:
            response = reader(request)
        except Exception:
            raise _Blocked(read_failure) from None
        if not isinstance(response, Mapping):
            raise _Blocked(invalid)
        data = response.get("data")
        if (
            not isinstance(data, Mapping)
            or collection_key not in data
            or "next" not in data
        ):
            raise _Blocked(invalid)
        cursor = data.get("next")
        if cursor is not None and (
            type(cursor) is not str
            or not cursor
            or len(cursor) > 4096
            or cursor in seen
        ):
            raise _Blocked(invalid)
        try:
            page_rows = tuple(parser(response))
        except Exception:
            raise _Blocked(invalid) from None
        if len(rows) + len(page_rows) > max_rows:
            raise _Blocked(L43PreEffectBlocker.ORDER_COVERAGE_INCOMPLETE)
        rows.extend(page_rows)
        if cursor is None or cursor == "":
            return _PageRead(tuple(rows), local_pages, len(rows), True)
        seen.add(cursor)
        request = {**arguments, "cursor": cursor}
    raise _Blocked(L43PreEffectBlocker.ORDER_COVERAGE_INCOMPLETE)


def _parse_position_page(payload: Mapping[str, object]) -> tuple[object, ...]:
    data = payload.get("data")
    if not isinstance(data, Mapping) or not isinstance(data.get("positions"), list):
        raise ValueError
    return tuple(data["positions"])


def _parse_order_page(payload: Mapping[str, object]) -> tuple[object, ...]:
    data = payload.get("data")
    if not isinstance(data, Mapping) or not isinstance(data.get("orders"), list):
        raise ValueError
    parsed = parse_equity_orders_response(payload)
    if type(parsed) is not RobinhoodEquityOrdersPage:
        raise ValueError
    if len(parsed.orders) != len(data["orders"]):
        raise ValueError
    if any(order is None for order in parsed.orders):
        raise ValueError
    return tuple(parsed.orders)


def _reconciliation_snapshot(
    *,
    state: DurableState,
    origin_identity: RuntimeIdentity,
    spy_position: Decimal,
    spy_orders: tuple[RobinhoodEquityOrder, ...],
) -> ReconciliationSnapshot:
    if state.identity != origin_identity:
        raise _Blocked(L43PreEffectBlocker.STATE_IDENTITY_MISMATCH)
    matches: list[OrderObservation] = []
    for order_state in (state.entry, state.exit):
        if order_state is None or order_state.provider_order_id is None:
            continue
        provider_matches = tuple(
            order
            for order in spy_orders
            if order.order_id == order_state.provider_order_id
        )
        if not provider_matches:
            if order_state.status in {
                IntentStatus.MAY_HAVE_OCCURRED,
                IntentStatus.UNKNOWN,
                IntentStatus.WORKING,
                IntentStatus.PARTIAL,
            }:
                raise _Blocked(L43PreEffectBlocker.STATE_UNRESOLVED)
            continue
        if len(provider_matches) != 1:
            raise _Blocked(L43PreEffectBlocker.ORDER_INVALID)
        order = provider_matches[0]
        if not _order_matches_state(order, order_state):
            raise _Blocked(L43PreEffectBlocker.RECONCILIATION_FAILED)
        provider_status = _PROVIDER_TERMINAL_TO_STATE.get(order.state.casefold())
        if provider_status is None:
            raise _Blocked(L43PreEffectBlocker.WORKING_OR_UNKNOWN_ORDER)
        _, order_status = provider_status
        matches.append(
            OrderObservation(
                local_intent_id=order_state.intent_id,
                provider_order_id=order.order_id,
                status=order_status,
                cumulative_quantity=order.cumulative_quantity,
                cumulative_notional=order_state.cumulative_notional,
                working_remainder=_ZERO,
            )
        )
    unrelated = tuple(
        order
        for order in spy_orders
        if not any(
            order_state is not None and order_state.provider_order_id == order.order_id
            for order_state in (state.entry, state.exit)
        )
    )
    if unrelated and state.entry is not None and state.owned_quantity > _ZERO:
        entry_order = next(
            (
                order
                for order in spy_orders
                if order.order_id == state.entry.provider_order_id
            ),
            None,
        )
        if entry_order is None or any(
            order.created_at >= entry_order.created_at for order in unrelated
        ):
            # Any post-entry manual order makes exact share ownership ambiguous.
            raise _Blocked(L43PreEffectBlocker.UNRELATED_SPY_ORDER)
    return ReconciliationSnapshot(
        identity=origin_identity,
        observed_position=spy_position,
        orders=tuple(matches),
    )


def _order_matches_state(
    order: RobinhoodEquityOrder,
    state_order: OrderState,
) -> bool:
    try:
        requested_dollars = state_order.requested_dollars
        state_status = state_order.status
        quantity = state_order.cumulative_quantity
        notional = state_order.cumulative_notional
        if order.side is not OrderSide.BUY or order.symbol.value != "SPY":
            return False
        if order.order_type.casefold() != "market":
            return False
        if order.market_hours.casefold() != "regular_hours":
            return False
        if order.time_in_force.casefold() not in {"gfd", "day"}:
            return False
        if requested_dollars is None or order.dollar_based_amount is None:
            return False
        if (
            order.dollar_based_amount.currency_code != "USD"
            or order.dollar_based_amount.amount != requested_dollars
        ):
            return False
        mapped = _PROVIDER_TERMINAL_TO_STATE.get(order.state.casefold())
        if mapped is None or mapped[0] is not state_status:
            return False
        if order.cumulative_quantity != quantity:
            return False
        fill_quantity = _ZERO
        fill_notional = _ZERO
        seen_executions: set[str] = set()
        with localcontext(_NOTIONAL_CONTEXT):
            for execution in order.executions:
                if execution.execution_id in seen_executions:
                    return False
                seen_executions.add(execution.execution_id)
                fill_quantity += execution.quantity
                fill_notional += execution.quantity * execution.price
        return fill_quantity == quantity and fill_notional == notional
    except Exception:
        return False


def _order_terminal(order: RobinhoodEquityOrder) -> bool:
    return order.state.casefold() in _PROVIDER_TERMINAL_TO_STATE


def _exact_owned_sell_proposal(
    *,
    state: DurableState,
    origin_identity: RuntimeIdentity,
    target_session: str,
    broker_position: Decimal,
    broker_sellable: Decimal,
    reconciliation: ReconciliationSnapshot,
) -> ExactOwnedSellProposal:
    entry = state.entry
    if entry is None or entry.status not in _TERMINAL_ENTRY_MAP:
        raise _Blocked(L43PreEffectBlocker.SELL_NOT_TERMINAL)
    if (
        entry.provider_order_id is None
        or entry.requested_dollars is None
        or state.entries_used != 1
        or state.exits_used != 0
        or state.baseline_quantity != _ZERO
        or state.owned_quantity <= _ZERO
        or not state.reconciled
        or state.blocked_reason is not None
        or broker_position != state.owned_quantity
        or broker_sellable < state.owned_quantity
        or reconciliation.observed_position != state.owned_quantity
    ):
        raise _Blocked(L43PreEffectBlocker.SELL_POSITION_MISMATCH)
    requested_cents = _dollars_to_cents(entry.requested_dollars)
    terminal_entry = TerminalEntryEvidence(
        local_intent_id=entry.intent_id,
        provider_order_id=entry.provider_order_id,
        outcome=_TERMINAL_ENTRY_MAP[entry.status],
        requested_usd_cents=requested_cents,
        reserved_usd_cents=requested_cents,
        confirmed_filled_quantity=entry.cumulative_quantity,
        confirmed_filled_notional=entry.cumulative_notional,
    )
    identity = ReadinessIdentity(
        source_head=origin_identity.source_head,
        source_tree=origin_identity.source_tree,
        config_digest=origin_identity.config_digest,
        account_fingerprint=origin_identity.account_fingerprint,
        target_session=target_session,
    )
    ownership = OwnershipSnapshot(
        account_fingerprint=origin_identity.account_fingerprint,
        symbol=origin_identity.symbol,
        strategy=origin_identity.strategy,
        source_head=origin_identity.source_head,
        source_tree=origin_identity.source_tree,
        config_digest=origin_identity.config_digest,
        binding_digest=origin_identity.binding_digest,
        lifecycle_id=origin_identity.lifecycle_id,
        target_session=target_session,
        lifecycle=Lifecycle.STOPPED,
        effect_disposition=EffectDisposition.CONFIRMED,
        baseline_quantity=state.baseline_quantity,
        cumulative_bought=entry.cumulative_quantity,
        cumulative_sold=_ZERO,
        cumulative_entry_filled_dollars=entry.cumulative_notional,
        entry_reserved_dollars=entry.requested_dollars,
        working_remainder=_ZERO,
        entries_used=state.entries_used,
        exits_used=state.exits_used,
        entry_local_intent_id=entry.intent_id,
        entry_provider_order_id=entry.provider_order_id,
    )
    position = ReconciledOwnedPosition(
        identity=identity,
        ownership_snapshot=ownership,
        broker_position_quantity=broker_position,
        broker_sellable_quantity=broker_sellable,
        working_order_count=0,
        unresolved_order_count=0,
        evidence_sha256=_digest(
            (
                "ARCH147_L43_EXACT_OWNED_POSITION_V1",
                origin_identity.to_record(),
                target_session,
                entry.intent_id,
                entry.provider_order_id,
                entry.status.value,
                _decimal_text(entry.requested_dollars),
                _decimal_text(entry.cumulative_quantity),
                _decimal_text(entry.cumulative_notional),
                reconciliation.observed_position,
                broker_sellable,
                tuple(
                    (
                        item.local_intent_id,
                        item.provider_order_id,
                        item.status.value,
                        _decimal_text(item.cumulative_quantity),
                        _decimal_text(item.cumulative_notional),
                        _decimal_text(item.working_remainder),
                    )
                    for item in reconciliation.orders
                ),
            )
        ),
    )
    context = SellOrderContext(
        identity=identity,
        binding_digest=origin_identity.binding_digest,
        lifecycle_id=origin_identity.lifecycle_id,
        entry_local_intent_id=entry.intent_id,
        entry_provider_order_id=entry.provider_order_id,
        exact_owned_remainder=state.owned_quantity,
        broker_position_quantity=broker_position,
        broker_sellable_quantity=broker_sellable,
        terminal_entry_outcome=terminal_entry.outcome,
        reserved_usd_cents=requested_cents,
        confirmed_entry_filled_quantity=entry.cumulative_quantity,
        confirmed_entry_filled_notional=entry.cumulative_notional,
    )
    arguments = SellOrderArguments(
        side=SellSide.SELL,
        symbol="SPY",
        order_type=SellOrderType.MARKET,
        session=SellSession.REGULAR_HOURS,
        time_in_force=SellTimeInForce.DAY,
        quantity=state.owned_quantity,
        context=context,
    )
    proposal = ExactOwnedSellProposal(
        position=position,
        terminal_entry=terminal_entry,
        review_arguments=arguments,
        placement_arguments=arguments,
    )
    return proposal


def _require_terminal_entry_reconciled(
    state: DurableState,
    reconciliation: ReconciliationSnapshot,
) -> None:
    entry = state.entry
    if entry is None or entry.status not in _TERMINAL_ENTRY_MAP:
        raise _Blocked(L43PreEffectBlocker.SELL_NOT_TERMINAL)
    if not any(
        order.local_intent_id == entry.intent_id
        and order.provider_order_id == entry.provider_order_id
        and order.status is _TERMINAL_ENTRY_TO_ORDER_STATUS[entry.status]
        and order.cumulative_quantity == entry.cumulative_quantity
        and order.cumulative_notional == entry.cumulative_notional
        and order.working_remainder == _ZERO
        for order in reconciliation.orders
    ):
        raise _Blocked(L43PreEffectBlocker.RECONCILIATION_FAILED)


def _manual_close_evidence(
    *,
    source: L43SourceIdentity,
    provenance: L43Provenance,
    continuity: L43ContinuityResult,
    state: _StateView,
    broker: _BrokerView,
    session: XnysSessionFacts,
    signal: D34SignalFacts,
    recovery: RecoveryFacts,
    observed_at: datetime,
    unsupported_proposal_sha256: str | None,
) -> _ManualCloseEvidence:
    quantity = state.state.owned_quantity
    if (
        type(quantity) is not Decimal
        or quantity <= _ZERO
        or broker.spy_position_quantity != quantity
        or broker.spy_sellable_quantity < quantity
        or broker.reconciliation.observed_position != quantity
        or not state.state.reconciled
        or not recovery.reconciled
        or recovery.unresolved_effects
        or state.state.exit is not None
        or state.state.exits_used != 0
        or state.state.baseline_quantity != _ZERO
        or state.state.entry is None
        or state.state.entry.status not in _TERMINAL_ENTRY_MAP
        or state.state.entries_used != 1
        or state.sell_review_pending
        or state.manual_close_required
        or _valid_exact_quantity(quantity)
    ):
        raise _Blocked(L43PreEffectBlocker.SELL_POSITION_MISMATCH)
    _require_terminal_entry_reconciled(state.state, broker.reconciliation)
    if unsupported_proposal_sha256 is None:
        raise _Blocked(L43PreEffectBlocker.SELL_PROPOSAL_INVALID)
    _sha256(unsupported_proposal_sha256, "unsupported sell proposal digest")
    reconciliation_digest = _digest(
        (
            "ARCH147_L43_RECONCILIATION_FACTS_V1",
            broker.reconciliation.identity.to_record(),
            broker.reconciliation.observed_position,
            tuple(
                sorted(
                    (
                        item.local_intent_id,
                        _digest(("provider-order-id", item.provider_order_id)),
                        item.status.value,
                        _decimal_text(item.cumulative_quantity),
                        _decimal_text(item.cumulative_notional),
                        _decimal_text(item.working_remainder),
                    )
                    for item in broker.reconciliation.orders
                )
            ),
        )
    )
    origin = continuity.origin
    facts: tuple[tuple[str, str | int], ...] = (
        ("source_head", source.source_head),
        ("source_tree", source.source_tree),
        ("config_digest", provenance.config_digest),
        ("binding_digest", provenance.binding_digest),
        ("q62_journal_digest", origin.journal_sha256),
        ("q62_initialization_digest", origin.initialization_event_sha256),
        ("q62_consumed_observation_digest", origin.consumed_observation_sha256),
        ("state_sequence", state.last_sequence),
        ("state_tail_digest", state.tail_sha256),
        ("state_journal_digest", state.journal_sha256),
        ("account_fingerprint_digest", broker.account.fingerprint),
        ("positions_digest", broker.positions_digest),
        ("orders_digest", broker.orders_digest),
        ("order_scope_digest", broker.order_scope_digest),
        ("reconciliation_digest", reconciliation_digest),
        ("target_session", session.target_session),
        ("session_authority_digest", session.authority_digest),
        ("signal_inputs_digest", signal.inputs_digest),
        ("signal_decision", signal.decision.value),
        ("recovery_digest", recovery.evidence_digest),
        ("unsupported_proposal_digest", unsupported_proposal_sha256),
        (
            "unsupported_proposal_blocker",
            ExactSellBlocker.QUANTITY_SCALE_UNSUPPORTED.value,
        ),
        (
            "continuity_evidence_digest",
            ""
            if continuity.authority is None
            else continuity.authority.evidence_sha256,
        ),
        ("observed_at", _utc_datetime(observed_at, "manual-close time").isoformat()),
        ("residual_quantity", _decimal_text(quantity)),
    )
    basis = _digest(("ARCH147_L43_UNSUPPORTED_EXACT_RESIDUAL_V1", facts))
    return _ManualCloseEvidence(
        trigger=ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL,
        residual_quantity=quantity,
        state_sequence=state.last_sequence,
        state_tail_sha256=state.tail_sha256,
        basis_sha256=basis,
        safe_facts=facts,
    )


def _recovery_facts(
    *,
    state: DurableState,
    broker: _BrokerView,
    source: L43SourceIdentity,
    provenance: L43Provenance,
    continuity: L43ContinuityResult,
    session: XnysSessionFacts,
    signal_inputs_digest: str,
    signal: SignalDecision,
) -> RecoveryFacts:
    unresolved_state = any(
        order is not None
        and order.status
        in {
            IntentStatus.RESERVED,
            IntentStatus.MAY_HAVE_OCCURRED,
            IntentStatus.UNKNOWN,
            IntentStatus.WORKING,
            IntentStatus.PARTIAL,
        }
        for order in (state.entry, state.exit)
    )
    unresolved_orders = any(not _order_terminal(order) for order in broker.spy_orders)
    owned = state.owned_quantity
    if state.baseline_quantity != _ZERO or broker.spy_position_quantity != owned:
        reconciled = False
    else:
        reconciled = not unresolved_state and not unresolved_orders
    evidence_digest = _digest(
        (
            "ARCH147_L43_READ_ONLY_RECOVERY_V1",
            continuity.origin.journal_sha256,
            continuity.journal.tail_sequence if continuity.journal else None,
            continuity.journal.tail_sha256 if continuity.journal else None,
            source.source_head,
            source.source_tree,
            provenance.config_digest,
            provenance.binding_digest,
            provenance.account_fingerprint,
            state.last_sequence,
            state.journal_hash,
            broker.positions_digest,
            broker.orders_digest,
            broker.order_scope_digest,
            broker.spy_position_quantity,
            broker.spy_sellable_quantity,
            unresolved_state,
            unresolved_orders,
            reconciled,
            owned,
            session.target_session,
            session.authority_digest,
            signal_inputs_digest,
            signal.value,
        )
    )
    return RecoveryFacts(
        reconciled=reconciled,
        unresolved_effects=unresolved_state or unresolved_orders,
        terminal_entry=state.entry is None or state.entry.status in _TERMINAL_ENTRY_MAP,
        exact_owned_remainder=owned,
        evidence_digest=evidence_digest,
    )


def _make_plan(
    *,
    kind: L43PlanKind,
    source: L43SourceIdentity,
    provenance: L43Provenance,
    continuity: L43ContinuityResult,
    state: _StateView,
    reconciliation: ReconciliationSnapshot,
    broker: _BrokerView,
    scope_digest: str,
    session: XnysSessionFacts,
    signal: D34SignalFacts,
    recovery: RecoveryFacts,
    observed_at: datetime,
    signal_observation_digest: str,
    requested_entry_risk: Decimal | None = None,
    sell_proposal: ExactOwnedSellProposal | None = None,
) -> L43PreEffectPlan:
    return L43PreEffectPlan(
        kind=kind,
        current_source=source,
        provenance=provenance,
        continuity=continuity,
        state_last_sequence=state.last_sequence,
        state_tail_sha256=state.tail_sha256,
        state_journal_sha256=state.journal_sha256,
        reconciliation_snapshot=reconciliation,
        account_fingerprint=broker.account.fingerprint,
        positions_digest=broker.positions_digest,
        relevant_orders_digest=broker.orders_digest,
        order_scope_digest=scope_digest,
        session=session,
        signal=signal,
        recovery=recovery,
        observation_as_of=observed_at,
        signal_observation_digest=signal_observation_digest,
        positions_observation_digest=broker.positions_observation_digest,
        orders_observation_digest=broker.orders_observation_digest,
        order_scope_evidence_digest=broker.order_scope_evidence_digest,
        requested_entry_risk=requested_entry_risk,
        sell_proposal=sell_proposal,
    )


def _result(
    *,
    outcome: L43PreEffectOutcome,
    blockers: tuple[L43PreEffectBlocker, ...],
    plan: L43PreEffectPlan | None,
    observed_at: datetime,
    counters: _Counters,
    manual_close: _ManualCloseEvidence | None = None,
) -> L43PreEffectResult:
    safe: dict[str, object] = {
        "schema": "arch147-l43-pre-effect-observation/v1",
        "outcome": outcome.value,
        "blockers": tuple(item.value for item in blockers),
        "observed_at": observed_at.isoformat(),
        "robinhood_read_count": counters.robinhood_reads,
        "robinhood_page_count": counters.robinhood_pages,
        "alpaca_provider_call_count": counters.alpaca_provider_calls,
        "credential_read_count": counters.credential_reads,
        "reservation_count": 0,
        "review_count": 0,
        "placement_count": 0,
        "cancellation_count": 0,
        "provider_mutation_count": 0,
        "placement_authority_granted": False,
        "trade_authority_granted": False,
        "live_ready": False,
        "component_observed_at": tuple(
            (name, observed_at.isoformat())
            for name, observed_at in counters.observed_times
        ),
    }
    if counters.signal_observation_digest is not None:
        safe["signal_observation_digest"] = counters.signal_observation_digest
    if counters.positions_observation_digest is not None:
        safe["positions_observation_digest"] = counters.positions_observation_digest
    if counters.orders_observation_digest is not None:
        safe["orders_observation_digest"] = counters.orders_observation_digest
    if counters.order_scope_evidence_digest is not None:
        safe["order_scope_evidence_digest"] = counters.order_scope_evidence_digest
    if manual_close is not None:
        safe.update(
            {
                "manual_close_trigger": manual_close.trigger.value,
                "manual_close_residual_quantity": _decimal_text(
                    manual_close.residual_quantity
                ),
                "manual_close_state_sequence": manual_close.state_sequence,
                "manual_close_state_tail_digest": manual_close.state_tail_sha256,
                "manual_close_basis_digest": manual_close.basis_sha256,
                "manual_close_basis_facts": manual_close.safe_facts,
            }
        )
    if plan is not None:
        safe.update(
            {
                "source_head": plan.current_source.source_head,
                "source_tree": plan.current_source.source_tree,
                "config_digest": plan.provenance.config_digest,
                "binding_digest": plan.provenance.binding_digest,
                "account_fingerprint_digest": plan.account_fingerprint,
                "q62_journal_digest": plan.continuity.origin.journal_sha256,
                "durable_state_tail_digest": plan.state_tail_sha256,
                "positions_digest": plan.positions_digest,
                "orders_digest": plan.relevant_orders_digest,
                "order_scope_digest": plan.order_scope_digest,
                "signal_inputs_digest": plan.signal.inputs_digest,
                "session_authority_digest": plan.session.authority_digest,
                "recovery_digest": plan.recovery.evidence_digest,
                "plan_binding_digest": plan.binding_sha256,
                "plan_kind": plan.kind.value,
                "target_session": plan.session.target_session,
                "signal_observation_digest": plan.signal_observation_digest,
                "positions_observation_digest": plan.positions_observation_digest,
                "orders_observation_digest": plan.orders_observation_digest,
                "order_scope_evidence_digest": plan.order_scope_evidence_digest,
                "continuity_evidence_digest": (
                    ""
                    if plan.continuity.authority is None
                    else plan.continuity.authority.evidence_sha256
                ),
            }
        )
    evidence_json = json.dumps(
        safe, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return L43PreEffectResult(
        outcome=outcome,
        blockers=blockers,
        evidence_sha256=hashlib.sha256(evidence_json).hexdigest(),
        evidence_json=evidence_json,
        plan=plan,
        observed_at=observed_at,
        robinhood_read_count=counters.robinhood_reads,
        robinhood_page_count=counters.robinhood_pages,
        alpaca_provider_call_count=counters.alpaca_provider_calls,
        credential_read_count=counters.credential_reads,
        manual_close_trigger=(None if manual_close is None else manual_close.trigger),
        manual_close_residual_quantity=(
            None if manual_close is None else manual_close.residual_quantity
        ),
        manual_close_state_sequence=(
            None if manual_close is None else manual_close.state_sequence
        ),
        manual_close_state_tail_sha256=(
            None if manual_close is None else manual_close.state_tail_sha256
        ),
        manual_close_basis_sha256=(
            None if manual_close is None else manual_close.basis_sha256
        ),
    )


def _plan_digest(plan: L43PreEffectPlan) -> str:
    reconciliation = plan.reconciliation_snapshot
    order_material = tuple(
        sorted(
            (
                item.local_intent_id,
                item.provider_order_id,
                item.status.value,
                _decimal_text(item.cumulative_quantity),
                _decimal_text(item.cumulative_notional),
                _decimal_text(item.working_remainder),
            )
            for item in reconciliation.orders
        )
    )
    proposal_sha = (
        None if plan.sell_proposal is None else plan.sell_proposal.proposal_sha256()
    )
    return _digest(
        (
            "ARCH147_L43_PREFLIGHT_PLAN_V1",
            plan.kind.value,
            plan.current_source.source_head,
            plan.current_source.source_tree,
            plan.provenance.config_digest,
            plan.provenance.binding_digest,
            plan.provenance.account_fingerprint,
            plan.provenance.strategy,
            plan.provenance.symbol,
            plan.continuity.origin.journal_sha256,
            plan.continuity.origin.initialization_event_sha256,
            plan.continuity.origin.consumed_observation_sha256,
            None
            if plan.continuity.authority is None
            else plan.continuity.authority.evidence_sha256,
            None
            if plan.continuity.journal is None
            else plan.continuity.journal.journal_sha256,
            plan.continuity.journal.tail_sequence
            if plan.continuity.journal is not None
            else None,
            plan.continuity.journal.tail_sha256
            if plan.continuity.journal is not None
            else None,
            plan.state_last_sequence,
            plan.state_tail_sha256,
            plan.state_journal_sha256,
            reconciliation.identity.to_record(),
            _decimal_text(reconciliation.observed_position),
            order_material,
            plan.account_fingerprint,
            plan.positions_digest,
            plan.relevant_orders_digest,
            plan.order_scope_digest,
            plan.session.target_session,
            plan.session.regular_hours,
            plan.session.session_open,
            plan.session.authority_digest,
            plan.signal.decision.value,
            plan.signal.inputs_digest,
            plan.signal.completed_sessions,
            plan.signal.price_basis,
            plan.recovery.reconciled,
            plan.recovery.unresolved_effects,
            plan.recovery.terminal_entry,
            _decimal_text(plan.recovery.exact_owned_remainder),
            plan.recovery.evidence_digest,
            None
            if plan.requested_entry_risk is None
            else _decimal_text(plan.requested_entry_risk),
            proposal_sha,
        )
    )


def _order_material(order: RobinhoodEquityOrder) -> tuple[str, ...]:
    return (
        order.order_id,
        str(order.symbol),
        order.side.value,
        order.state.casefold(),
        order.placed_agent,
        order.created_at.isoformat(),
        _decimal_text(order.cumulative_quantity),
        "" if order.average_price is None else _decimal_text(order.average_price),
        order.order_type.casefold(),
        order.market_hours.casefold(),
        order.time_in_force.casefold(),
        ""
        if order.dollar_based_amount is None
        else _decimal_text(order.dollar_based_amount.amount),
        ""
        if order.dollar_based_amount is None
        else order.dollar_based_amount.currency_code,
        tuple(
            (
                item.execution_id,
                _decimal_text(item.quantity),
                _decimal_text(item.price),
                item.timestamp.isoformat(),
            )
            for item in order.executions
        ),
    )


def _validate_entry_risk(risk: Decimal) -> None:
    if type(risk) is not Decimal or not risk.is_finite() or risk <= _ZERO:
        raise _Blocked(L43PreEffectBlocker.ENTRY_RISK_INVALID)
    if risk > ENTRY_LIMIT or _effective_decimal_places(risk) > 2:
        raise _Blocked(L43PreEffectBlocker.ENTRY_RISK_INVALID)


def _dollars_to_cents(value: Decimal) -> int:
    if type(value) is not Decimal or not value.is_finite() or value <= _ZERO:
        raise _Blocked(L43PreEffectBlocker.SELL_PROPOSAL_INVALID)
    with localcontext(_NOTIONAL_CONTEXT):
        cents = value * Decimal("100")
    if cents != cents.to_integral_value():
        raise _Blocked(L43PreEffectBlocker.SELL_PROPOSAL_INVALID)
    integer = int(cents)
    if not 1 <= integer <= TINY_LIVE_POLICY.entry_limit_usd_cents:
        raise _Blocked(L43PreEffectBlocker.SELL_PROPOSAL_INVALID)
    return integer


def _valid_exact_quantity(value: Decimal) -> bool:
    if type(value) is not Decimal or not value.is_finite() or value <= _ZERO:
        return False
    parts = value.as_tuple()
    exponent = parts.exponent
    trailing = 0
    for digit in reversed(parts.digits):
        if digit != 0:
            break
        trailing += 1
    effective = max(0, -exponent - trailing) if exponent < 0 else 0
    return effective <= TINY_LIVE_POLICY.max_exit_decimal_places


def _effective_decimal_places(value: Decimal) -> int:
    parts = value.as_tuple()
    if parts.exponent >= 0:
        return 0
    trailing = 0
    for digit in reversed(parts.digits):
        if digit != 0:
            break
        trailing += 1
    return max(0, -parts.exponent - trailing)


def _require_fresh(
    *,
    observed_at: datetime,
    final_as_of: datetime,
    ttl: timedelta,
    blocker: L43PreEffectBlocker,
) -> None:
    if observed_at > final_as_of or final_as_of - observed_at > ttl:
        raise _Blocked(blocker)


def _utc_datetime(value: object, label: str) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise ValueError(f"{label} must be UTC-aware")
    return value.astimezone(UTC)


def _sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be lowercase SHA-256")


def _decimal_text(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError("canonical number must be finite Decimal")
    if value == _ZERO:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _digest(material: object) -> str:
    payload = json.dumps(
        material,
        default=_json_scalar,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _json_scalar(value: object) -> str:
    if type(value) is Decimal:
        return _decimal_text(value)
    if type(value) is datetime:
        return _utc_datetime(value, "canonical timestamp").isoformat()
    if type(value) is date:
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError("unsupported canonical evidence value")


__all__ = [
    "L43OrderScope",
    "L43OrderScopeProof",
    "L43PlanKind",
    "L43PreEffectBlocker",
    "L43PreEffectDependencies",
    "L43PreEffectOutcome",
    "L43PreEffectPlan",
    "L43PreEffectResult",
    "L43StateSnapshotReader",
    "RobinhoodPreEffectReadBoundary",
    "observe_l43_pre_effect",
]
