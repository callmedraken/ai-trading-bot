"""Effect-disabled, append-only L42 ownership and budget state.

This module persists intent and factual reconciliation records. It has no
provider, credential, OAuth, or order-dispatch dependency.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

from trading_bot.live_prototype.tiny_live_policy import (
    ManualCloseBasis,
    ManualCloseTrigger,
)

SCHEMA = "arch147-l42-durable-state/v1"
ENTRY_LIMIT = Decimal("10.00")
_ZERO = Decimal("0")
_ZERO_HASH = "0" * 64
_ARITHMETIC = Context(prec=80, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999)
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_OPAQUE = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class DurableStateError(ValueError):
    """A sanitized state or transition rejection."""


class JournalCorruption(DurableStateError):
    """The journal is incomplete, malformed, or has an invalid hash chain."""


class DurableWriteError(RuntimeError):
    """A journal write failed; the store is poisoned until reopened."""

    def __init__(self, phase: str) -> None:
        self.phase = phase
        super().__init__(f"durable journal {phase} failed")


class IntentKind(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


class IntentStatus(StrEnum):
    RESERVED = "RESERVED"
    MAY_HAVE_OCCURRED = "MAY_HAVE_OCCURRED"
    UNKNOWN = "UNKNOWN"
    WORKING = "WORKING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


class OrderStatus(StrEnum):
    WORKING = "WORKING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


class BlockReason(StrEnum):
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    UNRELATED_ORDER = "UNRELATED_ORDER"
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    ORDER_BINDING_MISMATCH = "ORDER_BINDING_MISMATCH"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    ORDER_ID_UNBOUND = "ORDER_ID_UNBOUND"
    FILL_REGRESSION = "FILL_REGRESSION"
    POSITION_MISMATCH = "POSITION_MISMATCH"
    UNCERTAIN_EFFECT = "UNCERTAIN_EFFECT"


@dataclass(frozen=True, slots=True)
class L43OriginAnchor:
    """Immutable Q62 origin bound into a separate additive L43 journal."""

    runtime_identity: RuntimeIdentity
    journal_sha256: str
    initialization_event_sha256: str
    consumed_observation_sha256: str
    journal_label: str = "arch147-q62-live-state-v1"

    def __post_init__(self) -> None:
        if type(self.runtime_identity) is not RuntimeIdentity:
            raise TypeError("L43 origin requires the original RuntimeIdentity")
        for value, label in (
            (self.journal_sha256, "Q62 journal digest"),
            (self.initialization_event_sha256, "Q62 initialization digest"),
            (self.consumed_observation_sha256, "Q62 observation digest"),
        ):
            _require_pattern(value, _HEX64, label)
        if self.journal_label != "arch147-q62-live-state-v1":
            raise ValueError("L43 origin label differs from the accepted Q62 owner")

    def to_record(self) -> dict[str, object]:
        return {
            "runtime_identity": self.runtime_identity.to_record(),
            "journal_sha256": self.journal_sha256,
            "initialization_event_sha256": self.initialization_event_sha256,
            "consumed_observation_sha256": self.consumed_observation_sha256,
            "journal_label": self.journal_label,
        }


@dataclass(frozen=True, slots=True)
class ManualCloseRequired:
    """Sticky L43-only close state; no automated order authority is carried."""

    trigger: ManualCloseTrigger
    exact_residual_quantity: Decimal
    basis: ManualCloseBasis
    effect_evidence_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.trigger, ManualCloseTrigger):
            raise TypeError("manual-close trigger must be a closed typed value")
        if not isinstance(self.basis, ManualCloseBasis):
            raise TypeError("manual-close basis must be typed")
        _validate_decimal(
            self.exact_residual_quantity, "manual-close residual", positive=True
        )
        _require_pattern(
            self.effect_evidence_sha256, _HEX64, "manual-close evidence digest"
        )
        expected_basis = (
            ManualCloseBasis.LAST_EXACT_RESIDUAL_BEFORE_UNKNOWN
            if self.trigger is ManualCloseTrigger.SELL_UNKNOWN
            else ManualCloseBasis.CONFIRMED_RECONCILED_RESIDUAL
        )
        if self.basis is not expected_basis:
            raise ValueError("manual-close basis differs from trigger semantics")

    @property
    def automated_order_allowed(self) -> bool:
        return False

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
    def read_only_reconciliation_allowed(self) -> bool:
        return True

    @property
    def separate_accepted_reconciliation_required_to_resolve(self) -> bool:
        return True


class L43SellReviewStatus(StrEnum):
    ATTEMPTED = "ATTEMPTED"
    ACCEPTED = "ACCEPTED"


@dataclass(frozen=True, slots=True)
class L43SellReviewState:
    """Durable review evidence; ACCEPTED alone is not sell authority."""

    status: L43SellReviewStatus
    proposal_sha256: str
    arguments_sha256: str
    started_at_sequence: int
    review_evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, L43SellReviewStatus):
            raise TypeError("sell-review status must be typed")
        _require_pattern(self.proposal_sha256, _HEX64, "sell proposal digest")
        _require_pattern(self.arguments_sha256, _HEX64, "sell arguments digest")
        if type(self.started_at_sequence) is not int or self.started_at_sequence < 0:
            raise ValueError("sell-review sequence is invalid")
        if self.status is L43SellReviewStatus.ATTEMPTED:
            if self.review_evidence_sha256 is not None:
                raise ValueError("unresolved review cannot carry accepted evidence")
        else:
            _require_pattern(
                self.review_evidence_sha256,
                _HEX64,
                "accepted review evidence digest",
            )


def _validate_decimal(value: Decimal, label: str, *, positive: bool = False) -> None:
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
    if value < _ZERO or (positive and value == _ZERO):
        qualifier = "positive" if positive else "nonnegative"
        raise ValueError(f"{label} must be {qualifier}")


def _decimal_text(value: Decimal) -> str:
    _validate_decimal(value, "decimal")
    if value == _ZERO:
        return "0"
    result = format(value, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return result


def _parse_decimal(value: object) -> Decimal:
    if not isinstance(value, str):
        raise JournalCorruption("decimal field is not text")
    try:
        parsed = Decimal(value)
        _validate_decimal(parsed, "journal decimal")
    except Exception:
        raise JournalCorruption("decimal field is malformed") from None
    if _decimal_text(parsed) != value:
        raise JournalCorruption("decimal field is not canonical")
    return parsed


def _add(left: Decimal, right: Decimal) -> Decimal:
    with localcontext(_ARITHMETIC) as context:
        return context.add(left, right)


def _subtract(left: Decimal, right: Decimal) -> Decimal:
    with localcontext(_ARITHMETIC) as context:
        return context.subtract(left, right)


def _scaled_integer(value: Decimal, exponent: int) -> int:
    parts = value.as_tuple()
    digits = int("".join(str(digit) for digit in parts.digits) or "0")
    return (-digits if parts.sign else digits) * 10 ** (parts.exponent - exponent)


def _is_multiple(value: Decimal, increment: Decimal) -> bool:
    exponent = min(value.as_tuple().exponent, increment.as_tuple().exponent)
    divisor = _scaled_integer(increment, exponent)
    return divisor != 0 and _scaled_integer(value, exponent) % divisor == 0


def _decimal_places(value: Decimal) -> int:
    parts = value.as_tuple()
    exponent = parts.exponent
    digits = list(parts.digits)
    while exponent < 0 and digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    return max(0, -exponent)


def _require_pattern(value: str, pattern: re.Pattern[str], label: str) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{label} has invalid format")


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    """Only non-secret, source-owned identity fields enter durable state."""

    account_fingerprint: str
    source_head: str
    source_tree: str
    config_digest: str
    binding_digest: str
    lifecycle_id: str
    symbol: str = "SPY"
    strategy: str = "BASE_MA35_50_V1"

    def __post_init__(self) -> None:
        _require_pattern(self.account_fingerprint, _HEX64, "account fingerprint")
        _require_pattern(self.source_head, _HEX40, "source HEAD")
        _require_pattern(self.source_tree, _HEX40, "source tree")
        _require_pattern(self.config_digest, _HEX64, "configuration digest")
        _require_pattern(self.binding_digest, _HEX64, "binding digest")
        _require_pattern(self.lifecycle_id, _UUID, "lifecycle identity")
        if self.symbol != "SPY" or self.strategy != "BASE_MA35_50_V1":
            raise ValueError("identity is outside the bounded L42 product")

    def to_record(self) -> dict[str, str]:
        return {
            "account_fingerprint": self.account_fingerprint,
            "source_head": self.source_head,
            "source_tree": self.source_tree,
            "config_digest": self.config_digest,
            "binding_digest": self.binding_digest,
            "lifecycle_id": self.lifecycle_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
        }


@dataclass(frozen=True, slots=True)
class OrderState:
    kind: IntentKind
    intent_id: str
    requested_dollars: Decimal | None = None
    requested_quantity: Decimal | None = None
    provider_order_id: str | None = None
    status: IntentStatus = IntentStatus.RESERVED
    cumulative_quantity: Decimal = _ZERO
    cumulative_notional: Decimal = _ZERO
    working_remainder: Decimal = _ZERO
    authority_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class DurableState:
    identity: RuntimeIdentity
    baseline_quantity: Decimal
    entry: OrderState | None = None
    exit: OrderState | None = None
    reconciled: bool = False
    blocked_reason: BlockReason | None = None
    last_sequence: int = -1
    journal_hash: str = _ZERO_HASH
    l43_origin: L43OriginAnchor | None = None
    sell_review: L43SellReviewState | None = None
    manual_close: ManualCloseRequired | None = None

    @property
    def owned_quantity(self) -> Decimal:
        bought = self.entry.cumulative_quantity if self.entry is not None else _ZERO
        sold = self.exit.cumulative_quantity if self.exit is not None else _ZERO
        return _subtract(bought, sold)

    @property
    def expected_position(self) -> Decimal:
        return _add(self.baseline_quantity, self.owned_quantity)

    @property
    def entry_reserved_dollars(self) -> Decimal:
        if self.entry is None or self.entry.requested_dollars is None:
            return _ZERO
        return self.entry.requested_dollars

    @property
    def entry_budget_remaining(self) -> Decimal:
        return _subtract(ENTRY_LIMIT, self.entry_reserved_dollars)

    @property
    def entries_used(self) -> int:
        return int(self.entry is not None)

    @property
    def exits_used(self) -> int:
        return int(self.exit is not None)

    @property
    def sell_review_pending(self) -> bool:
        return (
            self.sell_review is not None
            and self.sell_review.status is L43SellReviewStatus.ATTEMPTED
        )

    @property
    def manual_close_required(self) -> bool:
        if self.l43_origin is None:
            return self.manual_close is not None
        if self.manual_close is not None:
            return True
        return (
            self.exit is not None
            and self.owned_quantity > _ZERO
            and self.exit.status
            in {
                IntentStatus.MAY_HAVE_OCCURRED,
                IntentStatus.UNKNOWN,
                IntentStatus.PARTIAL,
                IntentStatus.CANCELED,
                IntentStatus.REJECTED,
            }
        )

    @property
    def manual_follow_up_required(self) -> bool:
        return self.manual_close_required or (
            self.l43_origin is not None
            and self.exit is not None
            and self.owned_quantity > _ZERO
            and self.exit.status
            in {
                IntentStatus.RESERVED,
                IntentStatus.MAY_HAVE_OCCURRED,
                IntentStatus.UNKNOWN,
                IntentStatus.WORKING,
                IntentStatus.PARTIAL,
            }
        )

    @property
    def automated_order_allowed(self) -> bool:
        return not (
            self.manual_close_required
            or self.sell_review_pending
            or self.blocked_reason is not None
            or not self.reconciled
            or _has_uncertain_intent(self)
            or any(
                order is not None
                and order.status in {IntentStatus.WORKING, IntentStatus.PARTIAL}
                for order in (self.entry, self.exit)
            )
        )


@dataclass(frozen=True, slots=True)
class OrderObservation:
    local_intent_id: str
    provider_order_id: str
    status: OrderStatus
    cumulative_quantity: Decimal
    cumulative_notional: Decimal
    working_remainder: Decimal

    def __post_init__(self) -> None:
        _require_pattern(self.local_intent_id, _UUID, "local intent identity")
        _require_pattern(self.provider_order_id, _OPAQUE, "provider order identity")
        if not isinstance(self.status, OrderStatus):
            raise TypeError("order status must be OrderStatus")
        for value in (
            self.cumulative_quantity,
            self.cumulative_notional,
            self.working_remainder,
        ):
            _validate_decimal(value, "order observation")
        if self.cumulative_quantity > _ZERO and self.cumulative_notional == _ZERO:
            raise ValueError("positive fill quantity requires positive notional")
        if self.status is OrderStatus.WORKING:
            if self.cumulative_quantity != _ZERO or self.working_remainder <= _ZERO:
                raise ValueError("WORKING order must be unfilled with remainder")
        elif self.status is OrderStatus.PARTIAL:
            if self.cumulative_quantity <= _ZERO or self.working_remainder <= _ZERO:
                raise ValueError("PARTIAL order requires fills and remainder")
        elif self.status is OrderStatus.FILLED:
            if self.cumulative_quantity <= _ZERO or self.working_remainder != _ZERO:
                raise ValueError("FILLED order requires fills and no remainder")
        elif self.working_remainder != _ZERO:
            raise ValueError("terminal order cannot have a working remainder")


@dataclass(frozen=True, slots=True)
class ReconciliationSnapshot:
    identity: RuntimeIdentity
    observed_position: Decimal
    orders: tuple[OrderObservation, ...] = ()

    def __post_init__(self) -> None:
        _validate_decimal(self.observed_position, "observed position")
        if not isinstance(self.orders, tuple) or any(
            not isinstance(order, OrderObservation) for order in self.orders
        ):
            raise TypeError("orders must be an immutable tuple of observations")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise JournalCorruption("journal contains duplicate object keys")
        result[key] = value
    return result


def _identity_from_record(record: object) -> RuntimeIdentity:
    fields = {
        "account_fingerprint",
        "source_head",
        "source_tree",
        "config_digest",
        "binding_digest",
        "lifecycle_id",
        "symbol",
        "strategy",
    }
    if not isinstance(record, dict) or set(record) != fields:
        raise JournalCorruption("identity record has an invalid schema")
    try:
        return RuntimeIdentity(**record)
    except (TypeError, ValueError):
        raise JournalCorruption("identity record is invalid") from None


def _origin_anchor_from_record(record: object) -> L43OriginAnchor:
    fields = {
        "runtime_identity",
        "journal_sha256",
        "initialization_event_sha256",
        "consumed_observation_sha256",
        "journal_label",
    }
    if not isinstance(record, dict) or set(record) != fields:
        raise JournalCorruption("L43 origin anchor has an invalid schema")
    try:
        return L43OriginAnchor(
            runtime_identity=_identity_from_record(record["runtime_identity"]),
            journal_sha256=record["journal_sha256"],
            initialization_event_sha256=record["initialization_event_sha256"],
            consumed_observation_sha256=record["consumed_observation_sha256"],
            journal_label=record["journal_label"],
        )
    except (TypeError, ValueError):
        raise JournalCorruption("L43 origin anchor is invalid") from None


def _manual_close_from_record(record: object) -> ManualCloseRequired:
    fields = {
        "trigger",
        "exact_residual_quantity",
        "basis",
        "effect_evidence_sha256",
    }
    if not isinstance(record, dict) or set(record) != fields:
        raise JournalCorruption("manual-close record has an invalid schema")
    try:
        return ManualCloseRequired(
            trigger=ManualCloseTrigger(record["trigger"]),
            exact_residual_quantity=_parse_decimal(record["exact_residual_quantity"]),
            basis=ManualCloseBasis(record["basis"]),
            effect_evidence_sha256=record["effect_evidence_sha256"],
        )
    except (TypeError, ValueError):
        raise JournalCorruption("manual-close record is invalid") from None


def _intent_id(identity: RuntimeIdentity, kind: IntentKind, amount: Decimal) -> str:
    seed = f"arch147-l42:{kind.value}:{_decimal_text(amount)}"
    return str(uuid.uuid5(uuid.UUID(identity.lifecycle_id), seed))


def _make_event(
    identity: RuntimeIdentity,
    sequence: int,
    previous_hash: str,
    kind: str,
    payload: dict[str, object],
) -> dict[str, object]:
    material = {
        "schema": SCHEMA,
        "sequence": sequence,
        "previous_hash": previous_hash,
        "kind": kind,
        "payload": payload,
    }
    event_id = str(
        uuid.uuid5(
            uuid.UUID(identity.lifecycle_id),
            _canonical_json(material).decode("ascii"),
        )
    )
    body = {**material, "event_id": event_id}
    return {**body, "event_hash": hashlib.sha256(_canonical_json(body)).hexdigest()}


def _event_payload(event: dict[str, object], expected: set[str]) -> dict[str, object]:
    payload = event["payload"]
    if not isinstance(payload, dict) or set(payload) != expected:
        raise JournalCorruption("event payload has an invalid schema")
    return payload


def _apply_event(state: DurableState | None, event: dict[str, object]) -> DurableState:
    kind = event["kind"]
    sequence = event["sequence"]
    event_hash = event["event_hash"]
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise JournalCorruption("event sequence is invalid")
    if not isinstance(event_hash, str):
        raise JournalCorruption("event hash is invalid")

    if kind == "INITIALIZED":
        if state is not None or sequence != 0:
            raise JournalCorruption("initialization event is out of order")
        payload = event["payload"]
        if not isinstance(payload, dict) or set(payload) not in (
            {"identity", "baseline_quantity"},
            {"identity", "baseline_quantity", "l43_origin"},
        ):
            raise JournalCorruption("initialization event has an invalid schema")
        data = payload
        identity = _identity_from_record(data["identity"])
        baseline = _parse_decimal(data["baseline_quantity"])
        if baseline != _ZERO:
            raise JournalCorruption("nonflat initial baseline has no ownership proof")
        origin = (
            _origin_anchor_from_record(data["l43_origin"])
            if "l43_origin" in data
            else None
        )
        if origin is not None and origin.runtime_identity != identity:
            raise JournalCorruption("L43 origin identity differs from journal identity")
        return DurableState(
            identity=identity,
            baseline_quantity=baseline,
            last_sequence=sequence,
            journal_hash=event_hash,
            l43_origin=origin,
        )

    if state is None:
        raise JournalCorruption("journal does not begin with initialization")
    if sequence != state.last_sequence + 1:
        raise JournalCorruption("event sequence is discontinuous")

    updated = state
    if kind == "ENTRY_RESERVED":
        data = _event_payload(event, {"intent_id", "requested_dollars"})
        amount = _parse_decimal(data["requested_dollars"])
        intent_id = data["intent_id"]
        if (
            not isinstance(intent_id, str)
            or intent_id != _intent_id(state.identity, IntentKind.ENTRY, amount)
            or state.entry is not None
            or amount <= _ZERO
            or amount > ENTRY_LIMIT
            or not _is_multiple(amount, Decimal("0.01"))
            or state.manual_close is not None
            or state.sell_review_pending
        ):
            raise JournalCorruption("entry reservation violates the L42 limit")
        updated = replace(
            state,
            entry=OrderState(
                kind=IntentKind.ENTRY,
                intent_id=intent_id,
                requested_dollars=amount,
            ),
            reconciled=state.reconciled,
            blocked_reason=None,
        )
    elif kind == "EXIT_RESERVED":
        payload = event["payload"]
        legacy_fields = {"intent_id", "requested_quantity"}
        l43_fields = {
            "intent_id",
            "requested_quantity",
            "authority_sha256",
            "review_proposal_sha256",
            "review_arguments_sha256",
            "review_evidence_sha256",
        }
        if not isinstance(payload, dict) or set(payload) not in (
            legacy_fields,
            l43_fields,
        ):
            raise JournalCorruption("exit reservation has an invalid schema")
        data = payload
        quantity = _parse_decimal(data["requested_quantity"])
        intent_id = data["intent_id"]
        authority_sha256 = data.get("authority_sha256")
        if (
            not isinstance(intent_id, str)
            or intent_id != _intent_id(state.identity, IntentKind.EXIT, quantity)
            or state.exit is not None
            or state.entry is None
            or state.owned_quantity <= _ZERO
            or quantity != state.owned_quantity
            or _decimal_places(quantity) > 6
            or state.manual_close is not None
            or state.sell_review_pending
        ):
            raise JournalCorruption("exit intent is not the exact owned remainder")
        if state.l43_origin is not None:
            review = state.sell_review
            if (
                set(data) != l43_fields
                or authority_sha256 is None
                or review is None
                or review.status is not L43SellReviewStatus.ACCEPTED
                or data["review_proposal_sha256"] != review.proposal_sha256
                or data["review_arguments_sha256"] != review.arguments_sha256
                or data["review_evidence_sha256"] != review.review_evidence_sha256
            ):
                raise JournalCorruption("L43 exit lacks its accepted review authority")
            try:
                _require_pattern(authority_sha256, _HEX64, "sell authority digest")
            except ValueError:
                raise JournalCorruption(
                    "L43 sell authority digest is invalid"
                ) from None
        elif set(data) != legacy_fields:
            raise JournalCorruption("legacy exit cannot carry L43 authority")
        updated = replace(
            state,
            exit=OrderState(
                kind=IntentKind.EXIT,
                intent_id=intent_id,
                requested_quantity=quantity,
                authority_sha256=authority_sha256,
            ),
            reconciled=state.reconciled,
            blocked_reason=None,
        )
    elif kind in {"MAY_HAVE_OCCURRED", "UNKNOWN"}:
        data = _event_payload(event, {"intent_id"})
        target = _find_intent(state, data["intent_id"])
        allowed = (
            {IntentStatus.RESERVED}
            if kind == "MAY_HAVE_OCCURRED"
            else {IntentStatus.MAY_HAVE_OCCURRED, IntentStatus.WORKING}
        )
        if target is None or target.status not in allowed:
            raise JournalCorruption("uncertainty event has no eligible intent")
        if (
            target.kind is IntentKind.EXIT
            and state.l43_origin is not None
            and (
                target.authority_sha256 is None
                or state.sell_review is None
                or state.sell_review.status is not L43SellReviewStatus.ACCEPTED
                or state.manual_close is not None
            )
        ):
            raise JournalCorruption(
                "L43 exit invocation lacks separately bound authority"
            )
        status = (
            IntentStatus.MAY_HAVE_OCCURRED
            if kind == "MAY_HAVE_OCCURRED"
            else IntentStatus.UNKNOWN
        )
        updated = _update_intent(
            state, replace(target, status=status), reconciled=False
        )
        if kind == "UNKNOWN":
            updated = replace(updated, blocked_reason=BlockReason.UNCERTAIN_EFFECT)
    elif kind == "ORDER_BOUND":
        data = _event_payload(event, {"intent_id", "provider_order_id"})
        target = _find_intent(state, data["intent_id"])
        provider_id = data["provider_order_id"]
        if (
            target is None
            or target.status
            not in {IntentStatus.MAY_HAVE_OCCURRED, IntentStatus.UNKNOWN}
            or target.provider_order_id is not None
            or not isinstance(provider_id, str)
            or _OPAQUE.fullmatch(provider_id) is None
            or _provider_id_used(state, provider_id)
        ):
            raise JournalCorruption("provider order binding is invalid")
        updated = _update_intent(
            state,
            replace(
                target,
                provider_order_id=provider_id,
                status=IntentStatus.WORKING,
            ),
            reconciled=False,
        )
    elif kind == "ORDER_OBSERVED":
        data = _event_payload(
            event,
            {
                "intent_id",
                "provider_order_id",
                "status",
                "cumulative_quantity",
                "cumulative_notional",
                "working_remainder",
            },
        )
        target = _find_intent(state, data["intent_id"])
        if (
            target is None
            or target.provider_order_id != data["provider_order_id"]
            or target.status
            not in {
                IntentStatus.MAY_HAVE_OCCURRED,
                IntentStatus.UNKNOWN,
                IntentStatus.WORKING,
                IntentStatus.PARTIAL,
            }
        ):
            raise JournalCorruption("order observation lacks exact provenance")
        try:
            status = IntentStatus(data["status"])
        except (TypeError, ValueError):
            raise JournalCorruption("observed order status is invalid") from None
        quantity = _parse_decimal(data["cumulative_quantity"])
        notional = _parse_decimal(data["cumulative_notional"])
        remainder = _parse_decimal(data["working_remainder"])
        if (
            quantity < target.cumulative_quantity
            or notional < target.cumulative_notional
        ):
            raise JournalCorruption("cumulative fills are not monotone")
        _validate_observed_transition(target, status, quantity, notional, remainder)
        updated = _update_intent(
            state,
            replace(
                target,
                status=status,
                cumulative_quantity=quantity,
                cumulative_notional=notional,
                working_remainder=remainder,
            ),
            reconciled=False,
        )
    elif kind == "RECONCILIATION_BLOCKED":
        data = _event_payload(event, {"reason"})
        try:
            reason = BlockReason(data["reason"])
        except (TypeError, ValueError):
            raise JournalCorruption("reconciliation reason is invalid") from None
        updated = replace(state, reconciled=False, blocked_reason=reason)
    elif kind == "RECONCILIATION_PASSED":
        data = _event_payload(event, {"observed_position"})
        position = _parse_decimal(data["observed_position"])
        if position != state.expected_position:
            raise JournalCorruption("reconciled position differs from ownership")
        if _has_uncertain_intent(state):
            raise JournalCorruption("uncertain intent cannot be cleared by a flag")
        updated = replace(state, reconciled=True, blocked_reason=None)
    elif kind == "SELL_REVIEW_STARTED":
        data = _event_payload(event, {"proposal_sha256", "arguments_sha256"})
        if (
            state.l43_origin is None
            or state.sell_review is not None
            or state.manual_close is not None
            or state.entry is None
            or state.entry.status
            not in {
                IntentStatus.FILLED,
                IntentStatus.CANCELED,
                IntentStatus.REJECTED,
            }
            or state.entry.provider_order_id is None
            or state.owned_quantity <= _ZERO
            or not state.reconciled
            or state.exit is not None
        ):
            raise JournalCorruption("sell review is not eligible from durable state")
        try:
            review = L43SellReviewState(
                status=L43SellReviewStatus.ATTEMPTED,
                proposal_sha256=data["proposal_sha256"],
                arguments_sha256=data["arguments_sha256"],
                started_at_sequence=sequence,
            )
        except (TypeError, ValueError):
            raise JournalCorruption("sell review binding is invalid") from None
        updated = replace(state, sell_review=review)
    elif kind == "SELL_REVIEW_ACCEPTED":
        data = _event_payload(
            event,
            {
                "proposal_sha256",
                "arguments_sha256",
                "review_evidence_sha256",
            },
        )
        review = state.sell_review
        if (
            state.l43_origin is None
            or state.manual_close is not None
            or review is None
            or review.status is not L43SellReviewStatus.ATTEMPTED
            or state.last_sequence != review.started_at_sequence
            or data["proposal_sha256"] != review.proposal_sha256
            or data["arguments_sha256"] != review.arguments_sha256
        ):
            raise JournalCorruption(
                "accepted review differs from its attempted proposal"
            )
        try:
            updated_review = L43SellReviewState(
                status=L43SellReviewStatus.ACCEPTED,
                proposal_sha256=review.proposal_sha256,
                arguments_sha256=review.arguments_sha256,
                started_at_sequence=review.started_at_sequence,
                review_evidence_sha256=data["review_evidence_sha256"],
            )
        except (TypeError, ValueError):
            raise JournalCorruption("accepted review evidence is invalid") from None
        updated = replace(state, sell_review=updated_review)
    elif kind == "MANUAL_CLOSE_REQUIRED":
        data = _event_payload(
            event,
            {
                "trigger",
                "exact_residual_quantity",
                "basis",
                "effect_evidence_sha256",
            },
        )
        if state.l43_origin is None or state.manual_close is not None:
            raise JournalCorruption(
                "manual-close transition is not an L43 first-use event"
            )
        try:
            requirement = _manual_close_from_record(data)
        except JournalCorruption:
            raise
        if requirement.exact_residual_quantity != state.owned_quantity:
            raise JournalCorruption(
                "manual-close residual differs from durable ownership"
            )
        if not _manual_close_trigger_matches_state(requirement.trigger, state):
            raise JournalCorruption("manual-close trigger differs from durable outcome")
        updated = replace(state, manual_close=requirement)
    else:
        raise JournalCorruption("journal contains an unknown event kind")
    return replace(updated, last_sequence=sequence, journal_hash=event_hash)


def _validate_observed_transition(
    target: OrderState,
    status: IntentStatus,
    quantity: Decimal,
    notional: Decimal,
    remainder: Decimal,
) -> None:
    if status not in {
        IntentStatus.WORKING,
        IntentStatus.PARTIAL,
        IntentStatus.FILLED,
        IntentStatus.CANCELED,
        IntentStatus.REJECTED,
    }:
        raise JournalCorruption("order observation status is invalid")
    if quantity < target.cumulative_quantity or notional < target.cumulative_notional:
        raise JournalCorruption("cumulative fills are not monotone")
    if quantity > _ZERO and notional == _ZERO:
        raise JournalCorruption("positive fill quantity has no notional")
    terminal = {
        IntentStatus.FILLED,
        IntentStatus.CANCELED,
        IntentStatus.REJECTED,
    }
    if target.status in terminal and (
        status is not target.status
        or quantity != target.cumulative_quantity
        or notional != target.cumulative_notional
    ):
        raise JournalCorruption("terminal order observation changed")
    if target.kind is IntentKind.EXIT:
        requested = target.requested_quantity
        assert requested is not None
        if quantity > requested:
            raise JournalCorruption("exit fill exceeds the exact owned request")
        if status is IntentStatus.FILLED and quantity != requested:
            raise JournalCorruption("filled exit does not match its exact request")
        if status in {IntentStatus.WORKING, IntentStatus.PARTIAL}:
            if remainder != _subtract(requested, quantity):
                raise JournalCorruption("exit remainder differs from requested shares")
    if status is IntentStatus.WORKING and (quantity != _ZERO or remainder <= _ZERO):
        raise JournalCorruption("working order observation is inconsistent")
    if status is IntentStatus.PARTIAL and (quantity <= _ZERO or remainder <= _ZERO):
        raise JournalCorruption("partial order observation is inconsistent")
    if status is IntentStatus.FILLED and (quantity <= _ZERO or remainder != _ZERO):
        raise JournalCorruption("filled order observation is inconsistent")
    if status in {IntentStatus.CANCELED, IntentStatus.REJECTED} and remainder != _ZERO:
        raise JournalCorruption("terminal order has a working remainder")


def _find_intent(state: DurableState, intent_id: object) -> OrderState | None:
    for order in (state.entry, state.exit):
        if order is not None and order.intent_id == intent_id:
            return order
    return None


def _update_intent(
    state: DurableState,
    target: OrderState,
    *,
    reconciled: bool,
) -> DurableState:
    if target.kind is IntentKind.ENTRY:
        return replace(state, entry=target, reconciled=reconciled)
    return replace(state, exit=target, reconciled=reconciled)


def _provider_id_used(state: DurableState, provider_id: str) -> bool:
    return any(
        order is not None and order.provider_order_id == provider_id
        for order in (state.entry, state.exit)
    )


def _has_uncertain_intent(state: DurableState) -> bool:
    return any(
        order is not None
        and order.status in {IntentStatus.MAY_HAVE_OCCURRED, IntentStatus.UNKNOWN}
        for order in (state.entry, state.exit)
    )


def _manual_close_trigger_matches_state(
    trigger: ManualCloseTrigger, state: DurableState
) -> bool:
    if state.l43_origin is None or state.owned_quantity <= _ZERO:
        return False
    if trigger in {
        ManualCloseTrigger.SELL_REVIEW_REJECTED,
        ManualCloseTrigger.SELL_REVIEW_MALFORMED,
        ManualCloseTrigger.SELL_REVIEW_WARNING,
        ManualCloseTrigger.SELL_REVIEW_UNKNOWN,
    }:
        return (
            state.sell_review is not None
            and state.sell_review.status is L43SellReviewStatus.ATTEMPTED
            and state.exit is None
        )
    if trigger is ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL:
        return state.exit is None and not state.sell_review_pending
    if state.exit is None:
        return False
    expected = {
        ManualCloseTrigger.SELL_REJECTED: {IntentStatus.REJECTED},
        ManualCloseTrigger.SELL_CANCELED: {IntentStatus.CANCELED},
        ManualCloseTrigger.SELL_PARTIAL: {IntentStatus.PARTIAL},
        ManualCloseTrigger.SELL_UNKNOWN: {
            IntentStatus.MAY_HAVE_OCCURRED,
            IntentStatus.UNKNOWN,
        },
    }.get(trigger)
    return expected is not None and state.exit.status in expected


class DurableStateStore:
    """Append-only journal with write/flush/fsync/close before returning."""

    def __init__(
        self,
        path: Path,
        *,
        file_opener: Callable[[Path, str], BinaryIO] | None = None,
        fsync: Callable[[int], None] = os.fsync,
    ) -> None:
        self.path = Path(path)
        self._file_opener = file_opener or (lambda path, mode: path.open(mode))
        self._fsync = fsync
        self._state: DurableState | None = None
        self._poisoned = False
        self._active_review_session_token: object | None = None

    @classmethod
    def create(
        cls,
        path: Path,
        identity: RuntimeIdentity,
        *,
        initial_position: Decimal = _ZERO,
        l43_origin: L43OriginAnchor | None = None,
        file_opener: Callable[[Path, str], BinaryIO] | None = None,
        fsync: Callable[[int], None] = os.fsync,
    ) -> DurableStateStore:
        _validate_decimal(initial_position, "initial position")
        if l43_origin is not None:
            if type(l43_origin) is not L43OriginAnchor:
                raise TypeError("L43 initialization requires a typed Q62 origin")
            if l43_origin.runtime_identity != identity:
                raise DurableStateError(
                    "L43 origin identity differs from state identity"
                )
        if initial_position != _ZERO:
            raise DurableStateError(
                "nonflat initial position requires exact prior ownership proof"
            )
        store = cls(path, file_opener=file_opener, fsync=fsync)
        payload: dict[str, object] = {
            "identity": identity.to_record(),
            "baseline_quantity": _decimal_text(initial_position),
        }
        if l43_origin is not None:
            payload["l43_origin"] = l43_origin.to_record()
        store._append(
            "INITIALIZED",
            payload,
            create=True,
            identity=identity,
        )
        return store

    @classmethod
    def open(
        cls,
        path: Path,
        expected_identity: RuntimeIdentity,
        *,
        file_opener: Callable[[Path, str], BinaryIO] | None = None,
        fsync: Callable[[int], None] = os.fsync,
    ) -> DurableStateStore:
        store = cls(path, file_opener=file_opener, fsync=fsync)
        try:
            raw = store.path.read_bytes()
        except OSError:
            raise JournalCorruption("durable journal could not be read") from None
        if not raw or not raw.endswith(b"\n"):
            raise JournalCorruption("durable journal is empty or incomplete")
        previous_hash = _ZERO_HASH
        state: DurableState | None = None
        for expected_sequence, line in enumerate(raw.splitlines()):
            if not line:
                raise JournalCorruption("durable journal contains an empty record")
            try:
                event = json.loads(
                    line.decode("ascii"), object_pairs_hook=_reject_duplicate_keys
                )
            except JournalCorruption:
                raise
            except Exception:
                raise JournalCorruption("durable journal record is malformed") from None
            fields = {
                "schema",
                "sequence",
                "previous_hash",
                "kind",
                "payload",
                "event_id",
                "event_hash",
            }
            if not isinstance(event, dict) or set(event) != fields:
                raise JournalCorruption("event record has an invalid schema")
            if event["schema"] != SCHEMA:
                raise JournalCorruption("event schema is unsupported")
            if event["sequence"] != expected_sequence:
                raise JournalCorruption("event sequence is discontinuous")
            if event["previous_hash"] != previous_hash:
                raise JournalCorruption("event predecessor hash differs")
            if not isinstance(event["kind"], str) or not isinstance(
                event["payload"], dict
            ):
                raise JournalCorruption("event fields are malformed")
            lifecycle_identity = expected_identity if state is None else state.identity
            if state is None:
                initial_payload = event["payload"]
                if (
                    not isinstance(initial_payload, dict)
                    or "identity" not in initial_payload
                ):
                    raise JournalCorruption("initial identity is missing")
                lifecycle_identity = _identity_from_record(initial_payload["identity"])
            rebuilt = _make_event(
                lifecycle_identity,
                expected_sequence,
                previous_hash,
                event["kind"],
                event["payload"],
            )
            if event != rebuilt:
                raise JournalCorruption("event identity or digest differs")
            state = _apply_event(state, event)
            previous_hash = event["event_hash"]
        if state is None:
            raise JournalCorruption("durable journal has no state")
        if state.identity != expected_identity:
            raise DurableStateError("durable identity differs from current runtime")
        store._state = state
        return store

    @property
    def state(self) -> DurableState:
        if self._state is None:
            raise DurableStateError("durable state is not initialized")
        return self._state

    def reserve_entry(self, requested_dollars: Decimal) -> str:
        _validate_decimal(requested_dollars, "entry request", positive=True)
        if requested_dollars > ENTRY_LIMIT or not _is_multiple(
            requested_dollars, Decimal("0.01")
        ):
            raise DurableStateError("entry request exceeds the one-time $10 limit")
        self._require_ready()
        if self.state.entry is not None:
            raise DurableStateError("entry intent is already consumed")
        if self.state.owned_quantity != _ZERO:
            raise DurableStateError("entry requires a flat owned position")
        intent_id = _intent_id(self.state.identity, IntentKind.ENTRY, requested_dollars)
        self._append(
            "ENTRY_RESERVED",
            {
                "intent_id": intent_id,
                "requested_dollars": _decimal_text(requested_dollars),
            },
        )
        return intent_id

    def reserve_exit(
        self,
        requested_quantity: Decimal,
        *,
        authority_sha256: str | None = None,
    ) -> str:
        _validate_decimal(requested_quantity, "exit request", positive=True)
        self._require_ready()
        entry = self.state.entry
        if self.state.exit is not None:
            raise DurableStateError("exit intent is already consumed")
        if (
            entry is None
            or entry.status
            not in {
                IntentStatus.FILLED,
                IntentStatus.CANCELED,
                IntentStatus.REJECTED,
            }
            or entry.provider_order_id is None
            or self.state.owned_quantity <= _ZERO
        ):
            raise DurableStateError("exit requires confirmed exact owned shares")
        if (
            requested_quantity != self.state.owned_quantity
            or _decimal_places(requested_quantity) > 6
        ):
            raise DurableStateError("exit must equal the exact supported remainder")
        payload: dict[str, object] = {
            "intent_id": _intent_id(
                self.state.identity, IntentKind.EXIT, requested_quantity
            ),
            "requested_quantity": _decimal_text(requested_quantity),
        }
        if self.state.l43_origin is not None:
            review = self.state.sell_review
            if (
                authority_sha256 is None
                or review is None
                or review.status is not L43SellReviewStatus.ACCEPTED
            ):
                raise DurableStateError("L43 exit lacks separate placement authority")
            _require_pattern(authority_sha256, _HEX64, "sell authority digest")
            payload.update(
                {
                    "authority_sha256": authority_sha256,
                    "review_proposal_sha256": review.proposal_sha256,
                    "review_arguments_sha256": review.arguments_sha256,
                    "review_evidence_sha256": review.review_evidence_sha256,
                }
            )
        elif authority_sha256 is not None:
            raise DurableStateError("L43 authority is unavailable to legacy state")
        intent_id = _intent_id(self.state.identity, IntentKind.EXIT, requested_quantity)
        payload["intent_id"] = intent_id
        self._append("EXIT_RESERVED", payload)
        return intent_id

    def begin_sell_review(
        self,
        *,
        proposal_sha256: str,
        arguments_sha256: str,
        session_token: object,
    ) -> None:
        self._require_ready()
        if self.state.l43_origin is None:
            raise DurableStateError("sell review is available only in L43 state")
        if session_token is None:
            raise DurableStateError("active L43 review session is required")
        if self.state.sell_review is not None:
            raise DurableStateError("L43 sell review attempt is already consumed")
        self._append(
            "SELL_REVIEW_STARTED",
            {
                "proposal_sha256": proposal_sha256,
                "arguments_sha256": arguments_sha256,
            },
        )
        self._active_review_session_token = session_token

    def accept_sell_review(
        self,
        *,
        proposal_sha256: str,
        arguments_sha256: str,
        review_evidence_sha256: str,
        session_token: object,
    ) -> None:
        if self.state.l43_origin is None:
            raise DurableStateError("sell review is available only in L43 state")
        review = self.state.sell_review
        if (
            review is None
            or review.status is not L43SellReviewStatus.ATTEMPTED
            or session_token is None
            or self._active_review_session_token is not session_token
            or self.state.last_sequence != review.started_at_sequence
            or proposal_sha256 != review.proposal_sha256
            or arguments_sha256 != review.arguments_sha256
        ):
            raise DurableStateError("accepted review differs from the active proposal")
        _require_pattern(review_evidence_sha256, _HEX64, "review evidence digest")
        self._append(
            "SELL_REVIEW_ACCEPTED",
            {
                "proposal_sha256": proposal_sha256,
                "arguments_sha256": arguments_sha256,
                "review_evidence_sha256": review_evidence_sha256,
            },
        )
        self._active_review_session_token = None

    def require_manual_close(
        self,
        *,
        trigger: ManualCloseTrigger,
        effect_evidence_sha256: str,
    ) -> ManualCloseRequired:
        if self.state.l43_origin is None:
            raise DurableStateError("manual close is available only in L43 state")
        if self.state.manual_close is not None:
            if (
                self.state.manual_close.trigger is trigger
                and self.state.manual_close.effect_evidence_sha256
                == effect_evidence_sha256
            ):
                return self.state.manual_close
            raise DurableStateError("manual close is already sticky")
        _require_pattern(effect_evidence_sha256, _HEX64, "manual-close evidence digest")
        residual = self.state.owned_quantity
        if not _manual_close_trigger_matches_state(trigger, self.state):
            raise DurableStateError("manual-close trigger differs from durable state")
        basis = (
            ManualCloseBasis.LAST_EXACT_RESIDUAL_BEFORE_UNKNOWN
            if trigger is ManualCloseTrigger.SELL_UNKNOWN
            else ManualCloseBasis.CONFIRMED_RECONCILED_RESIDUAL
        )
        record = ManualCloseRequired(
            trigger=trigger,
            exact_residual_quantity=residual,
            basis=basis,
            effect_evidence_sha256=effect_evidence_sha256,
        )
        self._append(
            "MANUAL_CLOSE_REQUIRED",
            {
                "trigger": record.trigger.value,
                "exact_residual_quantity": _decimal_text(
                    record.exact_residual_quantity
                ),
                "basis": record.basis.value,
                "effect_evidence_sha256": record.effect_evidence_sha256,
            },
        )
        return self.state.manual_close  # type: ignore[return-value]

    def mark_may_have_occurred(self, intent_id: str) -> None:
        self._require_ready()
        target = _find_intent(self.state, intent_id)
        if target is None or target.status is not IntentStatus.RESERVED:
            raise DurableStateError("intent is not available for its one invocation")
        self._append("MAY_HAVE_OCCURRED", {"intent_id": intent_id})

    def mark_unknown(self, intent_id: str) -> None:
        target = _find_intent(self.state, intent_id)
        if target is None or target.status not in {
            IntentStatus.MAY_HAVE_OCCURRED,
            IntentStatus.WORKING,
        }:
            raise DurableStateError("only a possibly invoked intent can become unknown")
        self._append("UNKNOWN", {"intent_id": intent_id})

    def bind_provider_order(self, intent_id: str, provider_order_id: str) -> None:
        _require_pattern(provider_order_id, _OPAQUE, "provider order identity")
        target = _find_intent(self.state, intent_id)
        if (
            target is None
            or target.status
            not in {
                IntentStatus.MAY_HAVE_OCCURRED,
                IntentStatus.UNKNOWN,
            }
            or _provider_id_used(self.state, provider_order_id)
        ):
            raise DurableStateError("provider order cannot be bound to this intent")
        self._append(
            "ORDER_BOUND",
            {"intent_id": intent_id, "provider_order_id": provider_order_id},
        )

    def reconcile(self, snapshot: ReconciliationSnapshot) -> DurableState:
        if snapshot.identity != self.state.identity:
            return self._block(BlockReason.IDENTITY_MISMATCH)
        seen_ids: set[str] = set()
        known: dict[str, OrderState] = {}
        for order in (self.state.entry, self.state.exit):
            if order is not None and order.provider_order_id is not None:
                known[order.provider_order_id] = order
        observations: list[tuple[OrderState, OrderObservation]] = []
        for observation in snapshot.orders:
            if observation.provider_order_id in seen_ids:
                return self._block(BlockReason.DUPLICATE_ORDER)
            seen_ids.add(observation.provider_order_id)
            order = known.get(observation.provider_order_id)
            if order is None:
                return self._block(BlockReason.UNRELATED_ORDER)
            if observation.local_intent_id != order.intent_id:
                return self._block(BlockReason.ORDER_BINDING_MISMATCH)
            if (
                observation.cumulative_quantity < order.cumulative_quantity
                or observation.cumulative_notional < order.cumulative_notional
            ):
                return self._block(BlockReason.FILL_REGRESSION)
            try:
                _validate_observed_transition(
                    order,
                    IntentStatus(observation.status.value),
                    observation.cumulative_quantity,
                    observation.cumulative_notional,
                    observation.working_remainder,
                )
            except (JournalCorruption, ValueError):
                return self._block(BlockReason.ORDER_BINDING_MISMATCH)
            observations.append((order, observation))
        for order in (self.state.entry, self.state.exit):
            if order is None:
                continue
            if (
                order.status
                in {
                    IntentStatus.MAY_HAVE_OCCURRED,
                    IntentStatus.UNKNOWN,
                }
                and order.provider_order_id is None
            ):
                return self._block(BlockReason.ORDER_ID_UNBOUND)
            if (
                order.status
                in {
                    IntentStatus.MAY_HAVE_OCCURRED,
                    IntentStatus.UNKNOWN,
                    IntentStatus.WORKING,
                    IntentStatus.PARTIAL,
                }
                and order.provider_order_id not in seen_ids
            ):
                return self._block(BlockReason.ORDER_NOT_FOUND)
        for order, observation in observations:
            next_status = IntentStatus(observation.status.value)
            if (
                order.status is next_status
                and order.cumulative_quantity == observation.cumulative_quantity
                and order.cumulative_notional == observation.cumulative_notional
                and order.working_remainder == observation.working_remainder
            ):
                continue
            self._append(
                "ORDER_OBSERVED",
                {
                    "intent_id": observation.local_intent_id,
                    "provider_order_id": observation.provider_order_id,
                    "status": next_status.value,
                    "cumulative_quantity": _decimal_text(
                        observation.cumulative_quantity
                    ),
                    "cumulative_notional": _decimal_text(
                        observation.cumulative_notional
                    ),
                    "working_remainder": _decimal_text(observation.working_remainder),
                },
            )
        if snapshot.observed_position != self.state.expected_position:
            return self._block(BlockReason.POSITION_MISMATCH)
        self._append(
            "RECONCILIATION_PASSED",
            {"observed_position": _decimal_text(snapshot.observed_position)},
        )
        return self.state

    def _require_ready(self) -> None:
        state = self.state
        if self._poisoned:
            raise DurableStateError("store is poisoned after a persistence failure")
        if state.blocked_reason is not None or not state.reconciled:
            raise DurableStateError("durable state is not reconciled or current")
        if state.manual_close_required or state.sell_review_pending:
            raise DurableStateError("L43 state is blocked for manual close/review")
        if _has_uncertain_intent(state):
            raise DurableStateError("an effect remains uncertain")
        if any(
            order is not None
            and order.status in {IntentStatus.WORKING, IntentStatus.PARTIAL}
            for order in (state.entry, state.exit)
        ):
            raise DurableStateError("a working order remains unresolved")

    def _block(self, reason: BlockReason) -> DurableState:
        self._append("RECONCILIATION_BLOCKED", {"reason": reason.value})
        return self.state

    def _append(
        self,
        kind: str,
        payload: dict[str, object],
        *,
        create: bool = False,
        identity: RuntimeIdentity | None = None,
    ) -> None:
        if self._poisoned:
            raise DurableStateError("store is poisoned after a persistence failure")
        current = self._state
        if current is None:
            if kind != "INITIALIZED" or identity is None:
                raise DurableStateError("durable state has not been initialized")
            sequence = 0
            previous_hash = _ZERO_HASH
            active_identity = identity
        else:
            sequence = current.last_sequence + 1
            previous_hash = current.journal_hash
            active_identity = current.identity
        event = _make_event(active_identity, sequence, previous_hash, kind, payload)
        next_state = _apply_event(current, event)
        line = _canonical_json(event) + b"\n"
        stream: BinaryIO | None = None
        phase = "open"
        close_attempted = False
        try:
            stream = self._file_opener(self.path, "xb" if create else "ab")
            phase = "write"
            written = stream.write(line)
            if written != len(line):
                raise OSError
            phase = "flush"
            stream.flush()
            phase = "fsync"
            self._fsync(stream.fileno())
            phase = "close"
            close_attempted = True
            stream.close()
        except Exception:
            if stream is not None and not close_attempted:
                close_attempted = True
                try:
                    stream.close()
                except Exception:
                    pass
            self._poisoned = True
            raise DurableWriteError(phase) from None
        self._state = next_state
