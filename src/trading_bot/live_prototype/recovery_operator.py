"""Pure read-only recovery comparison used by the Q62 readiness evaluator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum

from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.live_contract import OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import (
    ReadinessIdentity,
    is_current_utc,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ARITHMETIC = Context(prec=128, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999)


class RecoveryStatus(StrEnum):
    CLEAN = "CLEAN"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class RecoveryBlocker(StrEnum):
    SNAPSHOT_MISSING = "SNAPSHOT_MISSING"
    OBSERVATION_MISSING = "OBSERVATION_MISSING"
    OBSERVATION_NOT_FRESH = "OBSERVATION_NOT_FRESH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    POSITION_MISMATCH = "POSITION_MISMATCH"
    WORKING_ORDERS_PRESENT = "WORKING_ORDERS_PRESENT"
    UNRESOLVED_EFFECT = "UNRESOLVED_EFFECT"
    STATE_NOT_STOPPED = "STATE_NOT_STOPPED"
    PENDING_INTENT_PRESENT = "PENDING_INTENT_PRESENT"
    OWNED_POSITION_PRESENT = "OWNED_POSITION_PRESENT"


@dataclass(frozen=True, slots=True)
class RecoveryObservation:
    """Injected read-only account/state observation; no provider is constructed."""

    identity: ReadinessIdentity
    evidence_sha256: str
    observed_at: datetime
    valid_until: datetime
    position_quantity: Decimal
    working_order_count: int
    unresolved_effect: bool

    def __post_init__(self) -> None:
        if type(self.identity) is not ReadinessIdentity:
            raise TypeError("recovery identity must be ReadinessIdentity")
        if (
            type(self.evidence_sha256) is not str
            or _SHA256.fullmatch(self.evidence_sha256) is None
        ):
            raise ValueError("recovery evidence digest must be lowercase SHA-256")
        for value in (self.observed_at, self.valid_until):
            if (
                type(value) is not datetime
                or value.tzinfo is None
                or value.utcoffset() != timedelta(0)
            ):
                raise ValueError("recovery timestamps must be timezone-aware UTC")
        if self.valid_until < self.observed_at:
            raise ValueError("recovery validity cannot end before observation")
        if (
            type(self.position_quantity) is not Decimal
            or not self.position_quantity.is_finite()
            or self.position_quantity < 0
        ):
            raise ValueError("observed position must be a finite nonnegative Decimal")
        if type(self.working_order_count) is not int or self.working_order_count < 0:
            raise ValueError("working-order count must be a nonnegative integer")
        if type(self.unresolved_effect) is not bool:
            raise TypeError("unresolved-effect flag must be bool")


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    identity: ReadinessIdentity | None
    status: RecoveryStatus
    blockers: tuple[RecoveryBlocker, ...]
    evidence_sha256: str | None
    observed_at: datetime | None
    valid_until: datetime | None
    observed_position: Decimal | None
    working_order_count: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, RecoveryStatus):
            raise TypeError("recovery status must be RecoveryStatus")
        if type(self.blockers) is not tuple or any(
            not isinstance(item, RecoveryBlocker) for item in self.blockers
        ):
            raise TypeError("recovery blockers must be a typed tuple")
        if self.status is RecoveryStatus.CLEAN and self.blockers:
            raise ValueError("clean recovery cannot contain blockers")


def reconcile_read_only(
    identity: ReadinessIdentity,
    snapshot: OwnershipSnapshot | None,
    observation: RecoveryObservation | None,
    *,
    as_of: datetime,
) -> RecoveryReport:
    """Compare exact durable ownership with one fresh, read-only observation."""

    if type(identity) is not ReadinessIdentity:
        raise TypeError("identity must be ReadinessIdentity")
    if snapshot is not None and type(snapshot) is not OwnershipSnapshot:
        raise TypeError("snapshot must be OwnershipSnapshot")
    if observation is not None and type(observation) is not RecoveryObservation:
        raise TypeError("observation must be RecoveryObservation")
    if (
        type(as_of) is not datetime
        or as_of.tzinfo is None
        or as_of.utcoffset() != timedelta(0)
    ):
        return _report(
            identity,
            RecoveryStatus.UNKNOWN,
            (RecoveryBlocker.OBSERVATION_NOT_FRESH,),
            None,
            None,
            None,
            None,
            None,
        )

    blockers: list[RecoveryBlocker] = []
    if snapshot is None:
        blockers.append(RecoveryBlocker.SNAPSHOT_MISSING)
    if observation is None:
        blockers.append(RecoveryBlocker.OBSERVATION_MISSING)
    if snapshot is None or observation is None:
        return _report(
            identity,
            RecoveryStatus.UNKNOWN,
            tuple(blockers),
            None if observation is None else observation.evidence_sha256,
            None if observation is None else observation.observed_at,
            None if observation is None else observation.valid_until,
            None if observation is None else observation.position_quantity,
            None if observation is None else observation.working_order_count,
        )

    if (
        not is_current_utc(observation.observed_at, as_of=as_of)
        or as_of > observation.valid_until
    ):
        blockers.append(RecoveryBlocker.OBSERVATION_NOT_FRESH)
    if observation.identity != identity or not _snapshot_matches(snapshot, identity):
        blockers.append(RecoveryBlocker.IDENTITY_MISMATCH)
    if snapshot.symbol != "SPY" or snapshot.strategy != "BASE_MA35_50_V1":
        blockers.append(RecoveryBlocker.IDENTITY_MISMATCH)
    with localcontext(_ARITHMETIC):
        expected_position = snapshot.baseline_quantity + snapshot.owned_quantity
    if observation.position_quantity != expected_position:
        blockers.append(RecoveryBlocker.POSITION_MISMATCH)
    if observation.working_order_count != 0:
        blockers.append(RecoveryBlocker.WORKING_ORDERS_PRESENT)
    if (
        observation.unresolved_effect
        or snapshot.effect_disposition is EffectDisposition.MAY_HAVE_OCCURRED
    ):
        blockers.append(RecoveryBlocker.UNRESOLVED_EFFECT)
    if snapshot.lifecycle not in (Lifecycle.DISARMED, Lifecycle.STOPPED):
        blockers.append(RecoveryBlocker.STATE_NOT_STOPPED)
    if (
        snapshot.pending_intent_id is not None
        or snapshot.pending_kind is not None
        or snapshot.working_remainder != Decimal("0")
    ):
        blockers.append(RecoveryBlocker.PENDING_INTENT_PRESENT)
    if snapshot.baseline_quantity != Decimal("0") or snapshot.owned_quantity != Decimal(
        "0"
    ):
        blockers.append(RecoveryBlocker.OWNED_POSITION_PRESENT)

    unique = tuple(dict.fromkeys(blockers))
    status = RecoveryStatus.CLEAN if not unique else RecoveryStatus.BLOCKED
    return _report(
        identity,
        status,
        unique,
        observation.evidence_sha256,
        observation.observed_at,
        observation.valid_until,
        observation.position_quantity,
        observation.working_order_count,
    )


def _snapshot_matches(snapshot: OwnershipSnapshot, identity: ReadinessIdentity) -> bool:
    return (
        type(snapshot) is OwnershipSnapshot
        and snapshot.source_head == identity.source_head
        and snapshot.source_tree == identity.source_tree
        and snapshot.config_digest == identity.config_digest
        and snapshot.account_fingerprint == identity.account_fingerprint
        and snapshot.target_session == identity.target_session
    )


def _report(
    identity: ReadinessIdentity | None,
    status: RecoveryStatus,
    blockers: tuple[RecoveryBlocker, ...],
    evidence_sha256: str | None,
    observed_at: datetime | None,
    valid_until: datetime | None,
    observed_position: Decimal | None,
    working_order_count: int | None,
) -> RecoveryReport:
    return RecoveryReport(
        identity,
        status,
        blockers,
        evidence_sha256,
        observed_at,
        valid_until,
        observed_position,
        working_order_count,
    )
