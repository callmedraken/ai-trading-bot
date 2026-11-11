"""Frozen tiny-live source policy and prospective exact-owned sell contracts.

All values here are pure typed evidence contracts. They neither authenticate
provider observations nor authorize live effects. A later L43 owner must qualify
the source/provider boundary before any placement can be considered.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, fields
from decimal import Decimal
from enum import StrEnum
from typing import Final

from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.live_contract import (
    MAX_EXIT_DECIMAL_PLACES,
    IntentKind,
    OwnershipSnapshot,
)
from trading_bot.live_prototype.readiness_contracts import ReadinessIdentity

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_OPAQUE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_ZERO = Decimal("0")


def _is_sha256(value: object) -> bool:
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _is_finite_decimal(value: object) -> bool:
    return type(value) is Decimal and value.is_finite()


def _is_bounded_decimal(value: object) -> bool:
    if not _is_finite_decimal(value):
        return False
    parts = value.as_tuple()
    return (
        -12 <= parts.exponent <= 12
        and len(parts.digits) <= 64
        and value.adjusted() <= 12
    )


def _decimal_text(value: Decimal) -> str:
    """Return exact context-free fixed-point text for canonical evidence."""
    if not _is_bounded_decimal(value):
        raise ValueError("canonical Decimal is outside the bounded domain")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _effective_decimal_places(value: Decimal) -> int | None:
    """Count significant fractional places without Decimal.normalize/context."""
    if not _is_finite_decimal(value):
        return None
    parts = value.as_tuple()
    exponent = parts.exponent
    if type(exponent) is not int:
        return None
    if exponent >= 0:
        return 0
    trailing_zeroes = 0
    for digit in reversed(parts.digits):
        if digit != 0:
            break
        trailing_zeroes += 1
    return max(0, -exponent - trailing_zeroes)


@dataclass(frozen=True, slots=True)
class TinyLivePolicy:
    """Zero-argument immutable source-owned contract; no caller policy knobs."""

    policy_id: str = field(init=False, default="ARCH147_TINY_LIVE_SPY_SINGLE_ENTRY_V1")
    product_scope: str = field(
        init=False, default="PRIVATE_SINGLE_USER_WINDOWS_DESKTOP"
    )
    account_scope: str = field(
        init=False, default="EXPLICITLY_ARMED_SINGLE_USER_ACCOUNT"
    )
    symbol: str = field(init=False, default="SPY")
    strategy: str = field(init=False, default="BASE_MA35_50_V1")
    position_model: str = field(init=False, default="CASH_LONG_ONLY")
    entry_request_unit: str = field(init=False, default="USD_CENTS")
    exit_request_unit: str = field(init=False, default="EXACT_OWNED_QUANTITY")
    entry_order_type: str = field(init=False, default="MARKET")
    exit_order_type: str = field(init=False, default="MARKET")
    session: str = field(init=False, default="REGULAR_HOURS")
    time_in_force: str = field(init=False, default="DAY")
    entry_limit_usd_cents: int = field(init=False, default=1000)
    max_entry_intents: int = field(init=False, default=1)
    max_exit_decimal_places: int = field(init=False, default=MAX_EXIT_DECIMAL_PLACES)
    private_single_user_desktop: bool = field(init=False, default=True)
    explicit_user_arm_required: bool = field(init=False, default=True)
    cash_long_only: bool = field(init=False, default=True)
    regular_hours_only: bool = field(init=False, default=True)
    reserve_full_entry_request: bool = field(init=False, default=True)
    entry_budget_replenishes: bool = field(init=False, default=False)
    require_terminal_entry_before_sell_review: bool = field(init=False, default=True)
    require_exact_source_config_account_session_strategy_identity: bool = field(
        init=False, default=True
    )
    no_second_entry_after_rejection: bool = field(init=False, default=True)
    no_second_entry_after_cancellation: bool = field(init=False, default=True)
    no_second_entry_after_partial_fill: bool = field(init=False, default=True)
    no_second_entry_after_unknown_outcome: bool = field(init=False, default=True)
    no_second_entry_after_restart: bool = field(init=False, default=True)
    no_second_entry_after_date_change: bool = field(init=False, default=True)
    no_second_entry_after_exit: bool = field(init=False, default=True)
    no_provider_fallback: bool = field(init=False, default=True)
    no_margin: bool = field(init=False, default=True)
    no_short: bool = field(init=False, default=True)
    no_options: bool = field(init=False, default=True)
    no_crypto: bool = field(init=False, default=True)
    no_paper_soak: bool = field(init=False, default=True)
    review_required_before_automated_sell: bool = field(init=False, default=True)
    sell_must_equal_exact_owned_quantity: bool = field(init=False, default=True)
    sell_must_be_supported_exact_decimal: bool = field(init=False, default=True)
    no_round_up: bool = field(init=False, default=True)
    no_unsupported_truncation: bool = field(init=False, default=True)
    no_dollar_substitution_for_owned_sell: bool = field(init=False, default=True)
    no_automatic_replacement_sell: bool = field(init=False, default=True)
    manual_close_required_for_unsupported_residual: bool = field(
        init=False, default=True
    )
    final_holdout_sealed: bool = field(init=False, default=True)
    placement_authority_in_this_checkpoint: bool = field(init=False, default=False)
    l43_source_provider_qualification_required: bool = field(init=False, default=True)

    def canonical_material(self) -> tuple[tuple[str, str | bool | int], ...]:
        """Fixed-order primitive digest material; contains no runtime identity."""
        return tuple((item.name, getattr(self, item.name)) for item in fields(self))

    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.canonical_material())


def _canonical_sha256(
    material: tuple[tuple[str, str | bool | int], ...],
) -> str:
    payload = json.dumps(material, ensure_ascii=True, separators=(",", ":")).encode(
        "ascii"
    )
    return hashlib.sha256(payload).hexdigest()


TINY_LIVE_POLICY: Final[TinyLivePolicy] = TinyLivePolicy()


class EntryTerminalOutcome(StrEnum):
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class TerminalEntryEvidence:
    """Factual terminal entry summary; full request reservation stays consumed."""

    local_intent_id: str
    provider_order_id: str
    outcome: EntryTerminalOutcome
    requested_usd_cents: int
    reserved_usd_cents: int
    confirmed_filled_quantity: Decimal
    confirmed_filled_notional: Decimal

    def __post_init__(self) -> None:
        for value in (self.local_intent_id, self.provider_order_id):
            if type(value) is not str or _OPAQUE_ID.fullmatch(value) is None:
                raise ValueError("entry order identities must be bounded opaque IDs")
        if not isinstance(self.outcome, EntryTerminalOutcome):
            raise TypeError("entry outcome must be a closed terminal outcome")
        if (
            type(self.requested_usd_cents) is not int
            or not 1
            <= self.requested_usd_cents
            <= TINY_LIVE_POLICY.entry_limit_usd_cents
            or type(self.reserved_usd_cents) is not int
            or self.reserved_usd_cents != self.requested_usd_cents
        ):
            raise ValueError(
                "the full requested entry reservation must remain consumed"
            )
        if (
            not _is_bounded_decimal(self.confirmed_filled_quantity)
            or self.confirmed_filled_quantity < _ZERO
            or not _is_bounded_decimal(self.confirmed_filled_notional)
            or self.confirmed_filled_notional < _ZERO
        ):
            raise ValueError("invalid confirmed entry fill facts")
        if (self.confirmed_filled_quantity == _ZERO) != (
            self.confirmed_filled_notional == _ZERO
        ):
            raise ValueError("entry quantity and notional fills must agree")


class SellSide(StrEnum):
    SELL = "SELL"


class SellOrderType(StrEnum):
    MARKET = "MARKET"


class SellSession(StrEnum):
    REGULAR_HOURS = "REGULAR_HOURS"


class SellTimeInForce(StrEnum):
    DAY = "DAY"


@dataclass(frozen=True, slots=True)
class SellOrderContext:
    """Exact identity and ownership context shared by review and placement args."""

    identity: ReadinessIdentity
    binding_digest: str
    lifecycle_id: str
    entry_local_intent_id: str
    entry_provider_order_id: str
    exact_owned_remainder: Decimal
    broker_position_quantity: Decimal
    broker_sellable_quantity: Decimal
    terminal_entry_outcome: EntryTerminalOutcome
    reserved_usd_cents: int
    confirmed_entry_filled_quantity: Decimal
    confirmed_entry_filled_notional: Decimal

    def __post_init__(self) -> None:
        if type(self.identity) is not ReadinessIdentity:
            raise TypeError("sell context identity must be ReadinessIdentity")
        if not _is_sha256(self.binding_digest):
            raise ValueError("sell context binding digest must be SHA-256")
        for value in (
            self.lifecycle_id,
            self.entry_local_intent_id,
            self.entry_provider_order_id,
        ):
            if type(value) is not str or _OPAQUE_ID.fullmatch(value) is None:
                raise ValueError("sell context IDs must be bounded opaque IDs")
        for value in (
            self.exact_owned_remainder,
            self.broker_position_quantity,
            self.broker_sellable_quantity,
            self.confirmed_entry_filled_quantity,
        ):
            if not _is_bounded_decimal(value) or value < _ZERO:
                raise ValueError(
                    "sell context quantities must be finite and nonnegative"
                )
        if (
            not _is_bounded_decimal(self.confirmed_entry_filled_notional)
            or self.confirmed_entry_filled_notional < _ZERO
        ):
            raise ValueError("confirmed fill notional must be bounded Decimal dollars")
        if not isinstance(self.terminal_entry_outcome, EntryTerminalOutcome):
            raise TypeError("sell context entry outcome must be terminal")
        if type(self.reserved_usd_cents) is not int or self.reserved_usd_cents <= 0:
            raise ValueError("invalid sell context entry accounting")
        if (self.confirmed_entry_filled_quantity == _ZERO) != (
            self.confirmed_entry_filled_notional == _ZERO
        ):
            raise ValueError("entry quantity and notional fills must agree")


@dataclass(frozen=True, slots=True)
class SellOrderArguments:
    """Normalized method arguments, not a provider wire-schema object."""

    side: SellSide
    symbol: str
    order_type: SellOrderType
    session: SellSession
    time_in_force: SellTimeInForce
    quantity: Decimal
    context: SellOrderContext
    dollar_amount: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.side, SellSide):
            raise TypeError("sell side must use the closed SellSide type")
        if not isinstance(self.order_type, SellOrderType):
            raise TypeError("order type must use the closed SellOrderType type")
        if not isinstance(self.session, SellSession):
            raise TypeError("session must use the closed SellSession type")
        if not isinstance(self.time_in_force, SellTimeInForce):
            raise TypeError("time in force must use the closed type")
        if type(self.symbol) is not str or not self.symbol:
            raise TypeError("symbol must be text")
        if not _is_bounded_decimal(self.quantity):
            raise TypeError("quantity must be a bounded finite Decimal")
        if self.dollar_amount is not None and not _is_bounded_decimal(
            self.dollar_amount
        ):
            raise TypeError(
                "dollar amount must be a bounded finite Decimal when supplied"
            )
        if type(self.context) is not SellOrderContext:
            raise TypeError("sell arguments require the closed SellOrderContext type")


@dataclass(frozen=True, slots=True)
class ReconciledOwnedPosition:
    """Normalized read-only reconciliation facts for one exact owned remainder.

    The digest is an evidence reference, not authentication. This contract never
    calls a provider and never grants an effect.
    """

    identity: ReadinessIdentity
    ownership_snapshot: OwnershipSnapshot
    broker_position_quantity: Decimal
    broker_sellable_quantity: Decimal
    working_order_count: int
    unresolved_order_count: int
    evidence_sha256: str

    def __post_init__(self) -> None:
        if type(self.identity) is not ReadinessIdentity:
            raise TypeError("reconciliation identity must be ReadinessIdentity")
        if type(self.ownership_snapshot) is not OwnershipSnapshot:
            raise TypeError("reconciliation requires OwnershipSnapshot")
        if not _is_sha256(self.evidence_sha256):
            raise ValueError("reconciliation evidence requires SHA-256")
        snapshot = self.ownership_snapshot
        if (
            snapshot.account_fingerprint != self.identity.account_fingerprint
            or snapshot.source_head != self.identity.source_head
            or snapshot.source_tree != self.identity.source_tree
            or snapshot.config_digest != self.identity.config_digest
            or snapshot.target_session != self.identity.target_session
        ):
            raise ValueError("reconciliation identity does not match ownership")
        if (
            snapshot.symbol != TINY_LIVE_POLICY.symbol
            or snapshot.strategy != TINY_LIVE_POLICY.strategy
        ):
            raise ValueError("reconciliation must bind SPY and the frozen strategy")
        if snapshot.baseline_quantity != _ZERO or snapshot.entries_used != 1:
            raise ValueError(
                "tiny-live ownership requires a flat baseline and one entry"
            )
        if snapshot.effect_disposition is not EffectDisposition.CONFIRMED:
            raise ValueError("exact residual requires confirmed effects")
        if snapshot.lifecycle in {Lifecycle.UNKNOWN, Lifecycle.BLOCKED}:
            raise ValueError("exact residual requires a known nonblocked lifecycle")
        if (
            snapshot.pending_intent_id is not None
            or snapshot.pending_kind is not None
            or snapshot.working_remainder != _ZERO
        ):
            raise ValueError(
                "unresolved effects cannot be reconciled as exact ownership"
            )
        if (
            snapshot.entry_local_intent_id is None
            or snapshot.entry_provider_order_id is None
            or snapshot.entry_reserved_dollars <= _ZERO
            or snapshot.binding_digest is None
            or snapshot.lifecycle_id is None
            or snapshot.owned_quantity <= _ZERO
        ):
            raise ValueError(
                "exact residual requires ownership and complete source context"
            )
        if (
            not _is_bounded_decimal(self.broker_position_quantity)
            or self.broker_position_quantity < _ZERO
        ):
            raise ValueError("broker position must be finite and nonnegative")
        if (
            not _is_bounded_decimal(self.broker_sellable_quantity)
            or self.broker_sellable_quantity < _ZERO
        ):
            raise ValueError("broker sellable quantity must be finite and nonnegative")
        if self.broker_sellable_quantity > self.broker_position_quantity:
            raise ValueError("broker sellable quantity cannot exceed position quantity")
        if (
            type(self.working_order_count) is not int
            or self.working_order_count < 0
            or type(self.unresolved_order_count) is not int
            or self.unresolved_order_count < 0
        ):
            raise ValueError("order counts must be nonnegative integers")
        if self.working_order_count != 0 or self.unresolved_order_count != 0:
            raise ValueError("reconciliation must establish terminal order state")
        if self.broker_position_quantity != snapshot.owned_quantity:
            raise ValueError("broker position must equal exact bot-owned quantity")


@dataclass(frozen=True, slots=True)
class ExactOwnedSellProposal:
    """A prospective exact full-owned sell proposal awaiting nonplacing review."""

    position: ReconciledOwnedPosition
    terminal_entry: TerminalEntryEvidence
    review_arguments: SellOrderArguments
    placement_arguments: SellOrderArguments

    def __post_init__(self) -> None:
        if type(self.position) is not ReconciledOwnedPosition:
            raise TypeError("sell proposal requires ReconciledOwnedPosition")
        if type(self.terminal_entry) is not TerminalEntryEvidence:
            raise TypeError("sell proposal requires terminal entry facts")
        if (
            type(self.review_arguments) is not SellOrderArguments
            or type(self.placement_arguments) is not SellOrderArguments
        ):
            raise TypeError("review and placement arguments must be normalized")

    def canonical_material(self) -> tuple[str, ...]:
        """Bind proposal, identity, reservation, fills, and both exact arg sets."""
        return (
            "ARCH147_TINY_LIVE_EXACT_OWNED_SELL_PROPOSAL_V1",
            *_identity_material(self.position.identity),
            self.position.evidence_sha256,
            self.terminal_entry.local_intent_id,
            self.terminal_entry.provider_order_id,
            self.terminal_entry.outcome.value,
            str(self.terminal_entry.requested_usd_cents),
            str(self.terminal_entry.reserved_usd_cents),
            _decimal_text(self.terminal_entry.confirmed_filled_quantity),
            _decimal_text(self.terminal_entry.confirmed_filled_notional),
            _decimal_text(self.position.ownership_snapshot.owned_quantity),
            _decimal_text(self.position.broker_position_quantity),
            _decimal_text(self.position.broker_sellable_quantity),
            *_sell_arguments_material(self.review_arguments),
            *_sell_arguments_material(self.placement_arguments),
        )

    def proposal_sha256(self) -> str:
        payload = json.dumps(
            self.canonical_material(),
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()


def _identity_material(identity: ReadinessIdentity) -> tuple[str, ...]:
    return (
        identity.source_head,
        identity.source_tree,
        identity.config_digest,
        identity.account_fingerprint,
        identity.target_session,
    )


def _sell_arguments_material(arguments: SellOrderArguments) -> tuple[str, ...]:
    context = arguments.context
    return (
        arguments.side.value,
        arguments.symbol,
        arguments.order_type.value,
        arguments.session.value,
        arguments.time_in_force.value,
        _decimal_text(arguments.quantity),
        ""
        if arguments.dollar_amount is None
        else _decimal_text(arguments.dollar_amount),
        *_identity_material(context.identity),
        context.binding_digest,
        context.lifecycle_id,
        context.entry_local_intent_id,
        context.entry_provider_order_id,
        _decimal_text(context.exact_owned_remainder),
        _decimal_text(context.broker_position_quantity),
        _decimal_text(context.broker_sellable_quantity),
        context.terminal_entry_outcome.value,
        str(context.reserved_usd_cents),
        _decimal_text(context.confirmed_entry_filled_quantity),
        _decimal_text(context.confirmed_entry_filled_notional),
    )


class ExactSellBlocker(StrEnum):
    INVALID_PROPOSAL = "INVALID_PROPOSAL"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    ENTRY_NOT_TERMINAL = "ENTRY_NOT_TERMINAL"
    FULL_RESERVATION_NOT_PRESERVED = "FULL_RESERVATION_NOT_PRESERVED"
    OWNERSHIP_NOT_EXACT = "OWNERSHIP_NOT_EXACT"
    BROKER_POSITION_MISMATCH = "BROKER_POSITION_MISMATCH"
    BROKER_SELLABLE_INSUFFICIENT = "BROKER_SELLABLE_INSUFFICIENT"
    QUANTITY_NOT_EXACT_FULL_OWNED = "QUANTITY_NOT_EXACT_FULL_OWNED"
    QUANTITY_SCALE_UNSUPPORTED = "QUANTITY_SCALE_UNSUPPORTED"
    ORDER_ARGUMENTS_MISMATCH = "ORDER_ARGUMENTS_MISMATCH"
    DOLLAR_SUBSTITUTION_FORBIDDEN = "DOLLAR_SUBSTITUTION_FORBIDDEN"
    EXIT_ALREADY_USED = "EXIT_ALREADY_USED"
    EFFECT_UNRESOLVED = "EFFECT_UNRESOLVED"


class ManualCloseTrigger(StrEnum):
    SELL_REVIEW_REJECTED = "SELL_REVIEW_REJECTED"
    SELL_REVIEW_MALFORMED = "SELL_REVIEW_MALFORMED"
    SELL_REVIEW_WARNING = "SELL_REVIEW_WARNING"
    SELL_REVIEW_UNKNOWN = "SELL_REVIEW_UNKNOWN"
    UNSUPPORTED_EXACT_RESIDUAL = "UNSUPPORTED_EXACT_RESIDUAL"
    SELL_REJECTED = "SELL_REJECTED"
    SELL_CANCELED = "SELL_CANCELED"
    SELL_PARTIAL = "SELL_PARTIAL"
    SELL_UNKNOWN = "SELL_UNKNOWN"


class ExactSellStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_NONPLACING_REVIEW = "READY_FOR_NONPLACING_REVIEW"


@dataclass(frozen=True, slots=True)
class ExactSellEligibility:
    status: ExactSellStatus
    blockers: tuple[ExactSellBlocker, ...]
    proposal_sha256: str | None
    manual_close_trigger: ManualCloseTrigger | None = None
    provider_mutation_count: int = 0
    placement_authority_granted: bool = False
    trade_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExactSellStatus):
            raise TypeError("exact-sell status must be typed")
        if type(self.blockers) is not tuple or any(
            not isinstance(item, ExactSellBlocker) for item in self.blockers
        ):
            raise TypeError("exact-sell blockers must be typed")
        if self.status is ExactSellStatus.READY_FOR_NONPLACING_REVIEW and self.blockers:
            raise ValueError("review-ready proposal cannot contain blockers")
        if self.manual_close_trigger is not None and not isinstance(
            self.manual_close_trigger, ManualCloseTrigger
        ):
            raise TypeError("manual-close escalation trigger must be typed")
        if self.status is ExactSellStatus.READY_FOR_NONPLACING_REVIEW and (
            self.manual_close_trigger is not None
        ):
            raise ValueError("review-ready proposal has no manual-close trigger")
        if (
            type(self.provider_mutation_count) is not int
            or self.provider_mutation_count != 0
            or self.placement_authority_granted is not False
            or self.trade_authority_granted is not False
        ):
            raise ValueError("prospective exact-sell result grants no effects")

    @property
    def eligible_for_nonplacing_review(self) -> bool:
        return self.status is ExactSellStatus.READY_FOR_NONPLACING_REVIEW


def evaluate_exact_owned_sell_proposal(
    proposal: ExactOwnedSellProposal,
) -> ExactSellEligibility:
    """Check only whether an exact full-owned proposal can enter future review."""
    if type(proposal) is not ExactOwnedSellProposal:
        return ExactSellEligibility(
            ExactSellStatus.BLOCKED,
            (ExactSellBlocker.INVALID_PROPOSAL,),
            None,
        )
    position = proposal.position
    snapshot = position.ownership_snapshot
    entry = proposal.terminal_entry
    blockers: list[ExactSellBlocker] = []
    identity = position.identity
    if (
        snapshot.account_fingerprint != identity.account_fingerprint
        or snapshot.source_head != identity.source_head
        or snapshot.source_tree != identity.source_tree
        or snapshot.config_digest != identity.config_digest
        or snapshot.target_session != identity.target_session
    ):
        blockers.append(ExactSellBlocker.IDENTITY_MISMATCH)
    if snapshot.effect_disposition is EffectDisposition.MAY_HAVE_OCCURRED:
        blockers.append(ExactSellBlocker.EFFECT_UNRESOLVED)
    if snapshot.lifecycle in {Lifecycle.UNKNOWN, Lifecycle.BLOCKED}:
        blockers.append(ExactSellBlocker.EFFECT_UNRESOLVED)
    if snapshot.entries_used != 1 or snapshot.entry_provider_order_id is None:
        blockers.append(ExactSellBlocker.ENTRY_NOT_TERMINAL)
    if (
        snapshot.entry_local_intent_id != entry.local_intent_id
        or snapshot.entry_provider_order_id != entry.provider_order_id
        or snapshot.cumulative_bought != entry.confirmed_filled_quantity
        or snapshot.cumulative_entry_filled_dollars != entry.confirmed_filled_notional
    ):
        blockers.append(ExactSellBlocker.ENTRY_NOT_TERMINAL)
    if (
        snapshot.entry_reserved_dollars != _cents_as_decimal(entry.requested_usd_cents)
        or entry.reserved_usd_cents != entry.requested_usd_cents
        or snapshot.entries_used != 1
    ):
        blockers.append(ExactSellBlocker.FULL_RESERVATION_NOT_PRESERVED)
    if (
        snapshot.pending_intent_id is not None
        or snapshot.pending_kind is not None
        or snapshot.working_remainder != _ZERO
        or snapshot.pending_requested_dollars != _ZERO
        or snapshot.pending_requested_quantity != _ZERO
        or snapshot.effect_disposition is not EffectDisposition.CONFIRMED
    ):
        blockers.append(ExactSellBlocker.EFFECT_UNRESOLVED)
    owned = snapshot.owned_quantity
    if (
        snapshot.symbol != TINY_LIVE_POLICY.symbol
        or snapshot.strategy != TINY_LIVE_POLICY.strategy
        or snapshot.baseline_quantity != _ZERO
        or owned <= _ZERO
        or position.broker_position_quantity != owned
        or entry.confirmed_filled_quantity != snapshot.cumulative_bought
    ):
        blockers.append(ExactSellBlocker.OWNERSHIP_NOT_EXACT)
    if position.broker_position_quantity != owned:
        blockers.append(ExactSellBlocker.BROKER_POSITION_MISMATCH)
    if position.broker_sellable_quantity < owned:
        blockers.append(ExactSellBlocker.BROKER_SELLABLE_INSUFFICIENT)
    if (
        snapshot.exits_used != 0
        or snapshot.cumulative_sold != _ZERO
        or snapshot.exit_local_intent_id is not None
        or snapshot.exit_provider_order_id is not None
    ):
        blockers.append(ExactSellBlocker.EXIT_ALREADY_USED)

    review = proposal.review_arguments
    placement = proposal.placement_arguments
    complete_context = all(
        value is not None
        for value in (
            snapshot.binding_digest,
            snapshot.lifecycle_id,
            snapshot.entry_local_intent_id,
            snapshot.entry_provider_order_id,
        )
    )
    expected_context = (
        _expected_sell_context(position, entry) if complete_context else None
    )
    expected = (
        review.side is SellSide.SELL
        and review.symbol == TINY_LIVE_POLICY.symbol
        and review.order_type is SellOrderType.MARKET
        and review.session is SellSession.REGULAR_HOURS
        and review.time_in_force is SellTimeInForce.DAY
        and placement.side is SellSide.SELL
        and placement.symbol == TINY_LIVE_POLICY.symbol
        and placement.order_type is SellOrderType.MARKET
        and placement.session is SellSession.REGULAR_HOURS
        and placement.time_in_force is SellTimeInForce.DAY
        and expected_context is not None
        and review.context == expected_context
        and placement.context == expected_context
        and review == placement
    )
    if not expected:
        blockers.append(ExactSellBlocker.ORDER_ARGUMENTS_MISMATCH)
    if review.dollar_amount is not None or placement.dollar_amount is not None:
        blockers.append(ExactSellBlocker.DOLLAR_SUBSTITUTION_FORBIDDEN)
    quantity = review.quantity
    if (
        not _is_finite_decimal(quantity)
        or quantity <= _ZERO
        or quantity != owned
        or placement.quantity != owned
        or quantity != placement.quantity
    ):
        blockers.append(ExactSellBlocker.QUANTITY_NOT_EXACT_FULL_OWNED)
    scale = (
        _effective_decimal_places(quantity) if _is_finite_decimal(quantity) else None
    )
    if scale is None or scale > TINY_LIVE_POLICY.max_exit_decimal_places:
        blockers.append(ExactSellBlocker.QUANTITY_SCALE_UNSUPPORTED)

    unique = tuple(dict.fromkeys(blockers))
    digest = proposal.proposal_sha256()
    manual_close_trigger = (
        ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL
        if unique and owned > _ZERO
        else None
    )
    return ExactSellEligibility(
        ExactSellStatus.BLOCKED
        if unique
        else ExactSellStatus.READY_FOR_NONPLACING_REVIEW,
        unique,
        digest,
        manual_close_trigger,
    )


def _cents_as_decimal(value: int) -> Decimal:
    whole, cents = divmod(value, 100)
    return Decimal(f"{whole}.{cents:02d}")


def _expected_sell_context(
    position: ReconciledOwnedPosition, entry: TerminalEntryEvidence
) -> SellOrderContext:
    snapshot = position.ownership_snapshot
    binding_digest = snapshot.binding_digest
    lifecycle_id = snapshot.lifecycle_id
    entry_intent_id = snapshot.entry_local_intent_id
    entry_order_id = snapshot.entry_provider_order_id
    if any(
        value is None
        for value in (binding_digest, lifecycle_id, entry_intent_id, entry_order_id)
    ):
        raise ValueError("exact sell context identity is incomplete")
    return SellOrderContext(
        identity=position.identity,
        binding_digest=binding_digest,
        lifecycle_id=lifecycle_id,
        entry_local_intent_id=entry_intent_id,
        entry_provider_order_id=entry_order_id,
        exact_owned_remainder=snapshot.owned_quantity,
        broker_position_quantity=position.broker_position_quantity,
        broker_sellable_quantity=position.broker_sellable_quantity,
        terminal_entry_outcome=entry.outcome,
        reserved_usd_cents=entry.reserved_usd_cents,
        confirmed_entry_filled_quantity=entry.confirmed_filled_quantity,
        confirmed_entry_filled_notional=entry.confirmed_filled_notional,
    )


EXACT_SELL_REVIEW_CONTRACT_ID: Final = "ARCH147_TINY_LIVE_EXACT_SELL_REVIEW_V1"


class NormalizedReviewOutcome(StrEnum):
    AFFIRMATIVE = "AFFIRMATIVE"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    MALFORMED = "MALFORMED"


class NormalizedReviewSemantics(StrEnum):
    NONPLACING_PREVIEW = "NONPLACING_PREVIEW"
    PLACEMENT_POSSIBLE = "PLACEMENT_POSSIBLE"
    UNKNOWN = "UNKNOWN"


class SellReviewBlocker(StrEnum):
    INVALID_PROPOSAL = "INVALID_PROPOSAL"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    CONTRACT_ID_MISMATCH = "CONTRACT_ID_MISMATCH"
    PROPOSAL_IDENTITY_MISMATCH = "PROPOSAL_IDENTITY_MISMATCH"
    REVIEW_ARGUMENTS_MISMATCH = "REVIEW_ARGUMENTS_MISMATCH"
    NON_AFFIRMATIVE_OUTCOME = "NON_AFFIRMATIVE_OUTCOME"
    NOT_PROVEN_NONPLACING = "NOT_PROVEN_NONPLACING"
    WARNINGS_PRESENT = "WARNINGS_PRESENT"
    UNKNOWN_FIELDS_PRESENT = "UNKNOWN_FIELDS_PRESENT"
    REJECTION_PRESENT = "REJECTION_PRESENT"
    PLACEMENT_ID_PRESENT = "PLACEMENT_ID_PRESENT"


@dataclass(frozen=True, slots=True)
class NormalizedSellReview:
    """Closed normalized evidence contract, deliberately not a live wire schema."""

    contract_id: str
    review_id: str
    evidence_sha256: str
    proposal_sha256: str
    identity: ReadinessIdentity
    reviewed_arguments: SellOrderArguments
    outcome: NormalizedReviewOutcome
    semantics: NormalizedReviewSemantics
    warnings: tuple[str, ...]
    unknown_fields: tuple[str, ...]
    rejection_code: str | None
    provider_order_id: str | None

    def __post_init__(self) -> None:
        if type(self.contract_id) is not str or not self.contract_id:
            raise TypeError("review contract ID must be text")
        if (
            type(self.review_id) is not str
            or _OPAQUE_ID.fullmatch(self.review_id) is None
        ):
            raise ValueError("review ID must be a bounded opaque identifier")
        if not _is_sha256(self.evidence_sha256) or not _is_sha256(self.proposal_sha256):
            raise ValueError("review evidence and proposal digests must be SHA-256")
        if type(self.identity) is not ReadinessIdentity:
            raise TypeError("review identity must be ReadinessIdentity")
        if type(self.reviewed_arguments) is not SellOrderArguments:
            raise TypeError("review arguments must use the normalized contract")
        if not isinstance(self.outcome, NormalizedReviewOutcome) or not isinstance(
            self.semantics, NormalizedReviewSemantics
        ):
            raise TypeError("review outcome and semantics must be closed types")
        if type(self.warnings) is not tuple or any(
            type(x) is not str for x in self.warnings
        ):
            raise TypeError("review warnings must be a tuple of text")
        if type(self.unknown_fields) is not tuple or any(
            type(x) is not str for x in self.unknown_fields
        ):
            raise TypeError("unknown fields must be a tuple of text")
        if self.rejection_code is not None and type(self.rejection_code) is not str:
            raise TypeError("rejection code must be text when present")
        if (
            self.provider_order_id is not None
            and type(self.provider_order_id) is not str
        ):
            raise TypeError("provider order ID must be text when present")


class SellReviewValidationStatus(StrEnum):
    BLOCKED = "BLOCKED"
    ACCEPTED_FOR_PROSPECTIVE_CONTRACT = "ACCEPTED_FOR_PROSPECTIVE_CONTRACT"


@dataclass(frozen=True, slots=True)
class SellReviewValidation:
    status: SellReviewValidationStatus
    blockers: tuple[SellReviewBlocker, ...]
    proposal_sha256: str | None
    manual_close_trigger: ManualCloseTrigger | None = None
    provider_mutation_count: int = 0
    placement_authority_granted: bool = False
    trade_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, SellReviewValidationStatus):
            raise TypeError("sell review validation status must be typed")
        if type(self.blockers) is not tuple or any(
            not isinstance(item, SellReviewBlocker) for item in self.blockers
        ):
            raise TypeError("sell review blockers must be typed")
        if (
            self.status is SellReviewValidationStatus.ACCEPTED_FOR_PROSPECTIVE_CONTRACT
            and self.blockers
        ):
            raise ValueError("accepted normalized review cannot have blockers")
        if self.manual_close_trigger is not None and not isinstance(
            self.manual_close_trigger, ManualCloseTrigger
        ):
            raise TypeError("manual-close escalation trigger must be typed")
        if (
            self.status is SellReviewValidationStatus.ACCEPTED_FOR_PROSPECTIVE_CONTRACT
            and self.manual_close_trigger is not None
        ):
            raise ValueError("accepted normalized review has no manual-close trigger")
        if (
            type(self.provider_mutation_count) is not int
            or self.provider_mutation_count != 0
            or self.placement_authority_granted is not False
            or self.trade_authority_granted is not False
        ):
            raise ValueError("review validation grants no effect authority")


def validate_normalized_sell_review(
    proposal: ExactOwnedSellProposal,
    response: NormalizedSellReview,
) -> SellReviewValidation:
    """Accept only complete affirmative nonplacing normalized evidence.

    The caller supplies facts, never an accepted token. Identity, proposal digest,
    exact full review/place arguments, outcome, semantics, warnings, unknowns,
    rejection, and placement fields are all revalidated here.
    """
    if type(proposal) is not ExactOwnedSellProposal:
        return _review_validation(
            [SellReviewBlocker.INVALID_PROPOSAL],
            None,
            None,
        )
    eligibility = evaluate_exact_owned_sell_proposal(proposal)
    blockers: list[SellReviewBlocker] = []
    if not eligibility.eligible_for_nonplacing_review:
        blockers.append(SellReviewBlocker.INVALID_PROPOSAL)
    if type(response) is not NormalizedSellReview:
        blockers.append(SellReviewBlocker.MALFORMED_RESPONSE)
        return _review_validation(
            blockers,
            eligibility.proposal_sha256,
            ManualCloseTrigger.SELL_REVIEW_MALFORMED
            if eligibility.proposal_sha256 is not None
            else eligibility.manual_close_trigger,
        )
    if response.contract_id != EXACT_SELL_REVIEW_CONTRACT_ID:
        blockers.append(SellReviewBlocker.CONTRACT_ID_MISMATCH)
    if (
        response.proposal_sha256 != eligibility.proposal_sha256
        or response.identity != proposal.position.identity
    ):
        blockers.append(SellReviewBlocker.PROPOSAL_IDENTITY_MISMATCH)
    if (
        response.reviewed_arguments != proposal.review_arguments
        or response.reviewed_arguments != proposal.placement_arguments
    ):
        blockers.append(SellReviewBlocker.REVIEW_ARGUMENTS_MISMATCH)
    if response.outcome is not NormalizedReviewOutcome.AFFIRMATIVE:
        blockers.append(SellReviewBlocker.NON_AFFIRMATIVE_OUTCOME)
    if response.semantics is not NormalizedReviewSemantics.NONPLACING_PREVIEW:
        blockers.append(SellReviewBlocker.NOT_PROVEN_NONPLACING)
    if response.warnings:
        blockers.append(SellReviewBlocker.WARNINGS_PRESENT)
    if response.unknown_fields:
        blockers.append(SellReviewBlocker.UNKNOWN_FIELDS_PRESENT)
    if response.rejection_code is not None:
        blockers.append(SellReviewBlocker.REJECTION_PRESENT)
    if response.provider_order_id is not None:
        blockers.append(SellReviewBlocker.PLACEMENT_ID_PRESENT)
    trigger = _review_failure_trigger(
        response,
        blockers,
        eligibility.manual_close_trigger,
    )
    return _review_validation(blockers, eligibility.proposal_sha256, trigger)


def _review_failure_trigger(
    response: NormalizedSellReview,
    blockers: list[SellReviewBlocker],
    fallback: ManualCloseTrigger | None,
) -> ManualCloseTrigger | None:
    if not blockers:
        return None
    if response.warnings:
        return ManualCloseTrigger.SELL_REVIEW_WARNING
    if response.outcome is NormalizedReviewOutcome.UNKNOWN or (
        response.semantics is NormalizedReviewSemantics.UNKNOWN
    ):
        return ManualCloseTrigger.SELL_REVIEW_UNKNOWN
    if (
        response.outcome is NormalizedReviewOutcome.MALFORMED
        or response.unknown_fields
        or response.contract_id != EXACT_SELL_REVIEW_CONTRACT_ID
        or response.provider_order_id is not None
        or SellReviewBlocker.REVIEW_ARGUMENTS_MISMATCH in blockers
        or SellReviewBlocker.PROPOSAL_IDENTITY_MISMATCH in blockers
    ):
        return ManualCloseTrigger.SELL_REVIEW_MALFORMED
    if (
        response.outcome is NormalizedReviewOutcome.REJECTED
        or response.rejection_code is not None
    ):
        return ManualCloseTrigger.SELL_REVIEW_REJECTED
    return fallback or ManualCloseTrigger.SELL_REVIEW_MALFORMED


def _review_validation(
    blockers: list[SellReviewBlocker],
    proposal_sha256: str | None,
    manual_close_trigger: ManualCloseTrigger | None,
) -> SellReviewValidation:
    unique = tuple(dict.fromkeys(blockers))
    return SellReviewValidation(
        SellReviewValidationStatus.BLOCKED
        if unique
        else SellReviewValidationStatus.ACCEPTED_FOR_PROSPECTIVE_CONTRACT,
        unique,
        proposal_sha256,
        manual_close_trigger,
    )


class ManualCloseStatus(StrEnum):
    MANUAL_CLOSE_REQUIRED = "MANUAL_CLOSE_REQUIRED"


class ManualCloseBasis(StrEnum):
    CONFIRMED_RECONCILED_RESIDUAL = "CONFIRMED_RECONCILED_RESIDUAL"
    LAST_EXACT_RESIDUAL_BEFORE_UNKNOWN = "LAST_EXACT_RESIDUAL_BEFORE_UNKNOWN"


@dataclass(frozen=True, slots=True)
class ManualCloseRequiredState:
    """Sticky disabled state; only later accepted reconciliation may resolve it."""

    status: ManualCloseStatus
    trigger: ManualCloseTrigger
    identity: ReadinessIdentity
    last_confirmed_position: ReconciledOwnedPosition
    current_ownership_snapshot: OwnershipSnapshot
    effect_evidence_sha256: str
    exact_residual_quantity: Decimal
    basis: ManualCloseBasis
    effect_disposition: EffectDisposition

    def __post_init__(self) -> None:
        if self.status is not ManualCloseStatus.MANUAL_CLOSE_REQUIRED:
            raise ValueError("manual-close state is sticky")
        if not isinstance(self.trigger, ManualCloseTrigger):
            raise TypeError("manual-close trigger must be typed")
        if type(self.identity) is not ReadinessIdentity:
            raise TypeError("manual-close identity must be ReadinessIdentity")
        if type(self.last_confirmed_position) is not ReconciledOwnedPosition:
            raise TypeError("manual-close state requires prior exact reconciliation")
        if type(self.current_ownership_snapshot) is not OwnershipSnapshot:
            raise TypeError("manual-close state requires current ownership evidence")
        if not isinstance(self.basis, ManualCloseBasis) or not isinstance(
            self.effect_disposition, EffectDisposition
        ):
            raise TypeError("manual-close basis and effect disposition must be typed")
        if not _is_sha256(self.effect_evidence_sha256):
            raise ValueError("manual-close transition requires effect evidence SHA-256")
        if (
            not _is_finite_decimal(self.exact_residual_quantity)
            or self.exact_residual_quantity <= _ZERO
        ):
            raise ValueError(
                "manual-close state must preserve a positive exact residual"
            )
        prior = self.last_confirmed_position
        snapshot = self.current_ownership_snapshot
        if self.identity != prior.identity:
            raise ValueError(
                "manual-close identity must retain prior source/account/session"
            )
        if (
            snapshot.account_fingerprint != self.identity.account_fingerprint
            or snapshot.source_head != self.identity.source_head
            or snapshot.source_tree != self.identity.source_tree
            or snapshot.config_digest != self.identity.config_digest
            or snapshot.target_session != self.identity.target_session
            or snapshot.binding_digest != prior.ownership_snapshot.binding_digest
            or snapshot.lifecycle_id != prior.ownership_snapshot.lifecycle_id
            or snapshot.symbol != prior.ownership_snapshot.symbol
            or snapshot.strategy != prior.ownership_snapshot.strategy
        ):
            raise ValueError("manual-close state cannot reset identity")
        prior_snapshot = prior.ownership_snapshot
        if (
            snapshot.entries_used != prior_snapshot.entries_used
            or snapshot.entry_reserved_dollars != prior_snapshot.entry_reserved_dollars
            or snapshot.entry_local_intent_id != prior_snapshot.entry_local_intent_id
            or snapshot.entry_provider_order_id
            != prior_snapshot.entry_provider_order_id
        ):
            raise ValueError("manual-close state must preserve entry consumption")
        if (
            snapshot.exits_used not in (0, 1)
            or snapshot.exit_local_intent_id == snapshot.entry_local_intent_id
            or snapshot.exit_provider_order_id == snapshot.entry_provider_order_id
            or (
                snapshot.exit_provider_order_id is not None
                and snapshot.exit_local_intent_id is None
            )
            or (
                snapshot.exits_used == 0
                and (
                    snapshot.exit_local_intent_id is not None
                    or snapshot.exit_provider_order_id is not None
                )
            )
            or (snapshot.exits_used == 1 and snapshot.exit_local_intent_id is None)
            or (
                snapshot.pending_intent_id is not None
                and (
                    snapshot.pending_intent_id != snapshot.exit_local_intent_id
                    or snapshot.pending_kind
                    not in {IntentKind.STRATEGY_EXIT, IntentKind.SAFETY_EXIT}
                )
            )
        ):
            raise ValueError("manual-close state has contradictory exit identities")
        expected_residual = (
            snapshot.owned_quantity
            if self.trigger is ManualCloseTrigger.SELL_PARTIAL
            else prior_snapshot.owned_quantity
        )
        if self.exact_residual_quantity != expected_residual:
            raise ValueError(
                "manual-close quantity must preserve exact owned remainder"
            )
        if self.effect_disposition is not snapshot.effect_disposition:
            raise ValueError("manual-close effect evidence must match current snapshot")
        if self.trigger is ManualCloseTrigger.SELL_UNKNOWN:
            if (
                self.basis is not ManualCloseBasis.LAST_EXACT_RESIDUAL_BEFORE_UNKNOWN
                or snapshot.effect_disposition
                is not EffectDisposition.MAY_HAVE_OCCURRED
                or snapshot.pending_intent_id is None
                or snapshot.pending_intent_id != snapshot.exit_local_intent_id
                or snapshot.pending_kind
                not in {IntentKind.STRATEGY_EXIT, IntentKind.SAFETY_EXIT}
                or snapshot.exits_used != 1
                or prior_snapshot.exits_used != 0
                or prior_snapshot.exit_local_intent_id is not None
                or prior_snapshot.exit_provider_order_id is not None
                or snapshot.exit_local_intent_id is None
                or snapshot.exit_local_intent_id == snapshot.entry_local_intent_id
                or snapshot.exit_provider_order_id == snapshot.entry_provider_order_id
                or snapshot.pending_requested_quantity != prior_snapshot.owned_quantity
                or snapshot.pending_requested_dollars != _ZERO
                or snapshot.cumulative_bought != prior_snapshot.cumulative_bought
                or snapshot.cumulative_sold != prior_snapshot.cumulative_sold
            ):
                raise ValueError(
                    "unknown exit preserves prior exact residual and MAY_HAVE_OCCURRED"
                )
        else:
            if self.basis is not ManualCloseBasis.CONFIRMED_RECONCILED_RESIDUAL:
                raise ValueError("known outcomes require confirmed reconciled residual")
            if snapshot.effect_disposition is not EffectDisposition.CONFIRMED:
                raise ValueError(
                    "known manual-close outcomes require confirmed effects"
                )
            if snapshot.lifecycle is Lifecycle.UNKNOWN:
                raise ValueError(
                    "known manual-close outcomes cannot use unknown lifecycle"
                )
            if snapshot.pending_requested_dollars != _ZERO:
                raise ValueError("sell outcomes cannot carry a dollar request")
            if (
                self.trigger
                in {
                    ManualCloseTrigger.SELL_REJECTED,
                    ManualCloseTrigger.SELL_CANCELED,
                    ManualCloseTrigger.SELL_PARTIAL,
                }
                and snapshot.exits_used != 1
            ):
                raise ValueError("sell outcomes consume the one exit attempt")
            if (
                self.trigger is ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL
                and snapshot.exits_used not in (0, 1)
            ):
                raise ValueError("unsupported exact close preserves one-shot exit use")
            if (
                self.trigger
                in {
                    ManualCloseTrigger.SELL_REVIEW_REJECTED,
                    ManualCloseTrigger.SELL_REVIEW_MALFORMED,
                    ManualCloseTrigger.SELL_REVIEW_WARNING,
                    ManualCloseTrigger.SELL_REVIEW_UNKNOWN,
                }
                and snapshot.exits_used != 0
            ):
                raise ValueError("review refusal precedes the sole sell attempt")
            if (
                snapshot.pending_intent_id is not None
                or snapshot.pending_kind is not None
                or snapshot.pending_requested_dollars != _ZERO
            ):
                if self.trigger is not ManualCloseTrigger.SELL_PARTIAL:
                    raise ValueError(
                        "known outcomes require terminal reconciled order state"
                    )
            if snapshot.cumulative_bought != prior_snapshot.cumulative_bought:
                raise ValueError("known exit cannot change confirmed entry fills")
            if self.trigger is ManualCloseTrigger.SELL_PARTIAL:
                if (
                    prior_snapshot.exits_used != 0
                    or prior_snapshot.cumulative_sold != _ZERO
                    or prior_snapshot.exit_local_intent_id is not None
                    or prior_snapshot.exit_provider_order_id is not None
                    or snapshot.exits_used != 1
                    or snapshot.exit_local_intent_id is None
                    or snapshot.exit_provider_order_id is None
                    or snapshot.exit_local_intent_id == snapshot.entry_local_intent_id
                    or snapshot.exit_provider_order_id
                    == snapshot.entry_provider_order_id
                    or snapshot.cumulative_sold <= prior_snapshot.cumulative_sold
                    or snapshot.owned_quantity <= _ZERO
                    or snapshot.owned_quantity >= prior_snapshot.owned_quantity
                ):
                    raise ValueError(
                        "partial exit must preserve a positive confirmed residual"
                    )
                if snapshot.pending_intent_id is None:
                    if (
                        snapshot.working_remainder != _ZERO
                        or snapshot.pending_requested_quantity != _ZERO
                    ):
                        raise ValueError(
                            "terminal partial exit cannot retain working evidence"
                        )
                elif (
                    snapshot.pending_intent_id != snapshot.exit_local_intent_id
                    or snapshot.pending_kind
                    not in {IntentKind.STRATEGY_EXIT, IntentKind.SAFETY_EXIT}
                    or snapshot.pending_requested_quantity
                    != prior_snapshot.owned_quantity
                    or snapshot.working_remainder != snapshot.owned_quantity
                ):
                    raise ValueError(
                        "working partial exit evidence must match exact residual"
                    )
            elif (
                snapshot.pending_intent_id is not None
                or snapshot.working_remainder != _ZERO
                or snapshot.pending_requested_quantity != _ZERO
                or snapshot.cumulative_sold != prior_snapshot.cumulative_sold
                or snapshot.owned_quantity != self.exact_residual_quantity
            ):
                raise ValueError("known outcome residual must match terminal facts")

    @property
    def automated_entry_allowed(self) -> bool:
        return False

    @property
    def automated_sell_allowed(self) -> bool:
        return False

    @property
    def automatic_replacement_sell_allowed(self) -> bool:
        return False

    @property
    def automated_order_allowed(self) -> bool:
        return False

    @property
    def read_only_reconciliation_allowed(self) -> bool:
        return True

    @property
    def user_manual_resolution_required(self) -> bool:
        return True

    @property
    def separate_accepted_reconciliation_required_to_resolve(self) -> bool:
        return True


def require_manual_close(
    *,
    last_confirmed_position: ReconciledOwnedPosition,
    current_ownership_snapshot: OwnershipSnapshot,
    trigger: ManualCloseTrigger,
    effect_evidence_sha256: str,
) -> ManualCloseRequiredState:
    """Build sticky manual-close state without inventing fills or clearing UNKNOWN."""
    if type(last_confirmed_position) is not ReconciledOwnedPosition:
        raise TypeError("last confirmed position evidence is required")
    if type(current_ownership_snapshot) is not OwnershipSnapshot:
        raise TypeError("current ownership snapshot is required")
    if not isinstance(trigger, ManualCloseTrigger):
        raise TypeError("manual-close trigger must be typed")
    if not _is_sha256(effect_evidence_sha256):
        raise ValueError("manual-close transition requires effect evidence SHA-256")
    unknown_exit = trigger is ManualCloseTrigger.SELL_UNKNOWN
    basis = (
        ManualCloseBasis.LAST_EXACT_RESIDUAL_BEFORE_UNKNOWN
        if unknown_exit
        else ManualCloseBasis.CONFIRMED_RECONCILED_RESIDUAL
    )
    return ManualCloseRequiredState(
        status=ManualCloseStatus.MANUAL_CLOSE_REQUIRED,
        trigger=trigger,
        identity=last_confirmed_position.identity,
        last_confirmed_position=last_confirmed_position,
        current_ownership_snapshot=current_ownership_snapshot,
        effect_evidence_sha256=effect_evidence_sha256,
        exact_residual_quantity=(
            current_ownership_snapshot.owned_quantity
            if trigger is ManualCloseTrigger.SELL_PARTIAL
            else last_confirmed_position.ownership_snapshot.owned_quantity
        ),
        basis=basis,
        effect_disposition=current_ownership_snapshot.effect_disposition,
    )
