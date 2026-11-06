from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.live_contract import IntentKind, OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import ReadinessIdentity
from trading_bot.live_prototype.recovery_operator import (
    RecoveryBlocker,
    RecoveryObservation,
    RecoveryStatus,
    reconcile_read_only,
)

_NOW = datetime(2026, 11, 6, 20, 0, tzinfo=UTC)


def _identity() -> ReadinessIdentity:
    return ReadinessIdentity("a" * 40, "b" * 40, "c" * 64, "d" * 64, "2026-11-06")


def _snapshot(identity: ReadinessIdentity, **overrides: object) -> OwnershipSnapshot:
    values: dict[str, object] = {
        "account_fingerprint": identity.account_fingerprint,
        "source_head": identity.source_head,
        "source_tree": identity.source_tree,
        "config_digest": identity.config_digest,
        "target_session": identity.target_session,
        "lifecycle": Lifecycle.DISARMED,
    }
    values.update(overrides)
    return OwnershipSnapshot(**values)  # type: ignore[arg-type]


def _observation(
    identity: ReadinessIdentity, **overrides: object
) -> RecoveryObservation:
    values: dict[str, object] = {
        "identity": identity,
        "evidence_sha256": "e" * 64,
        "observed_at": _NOW,
        "valid_until": _NOW + timedelta(minutes=5),
        "position_quantity": Decimal("0"),
        "working_order_count": 0,
        "unresolved_effect": False,
    }
    values.update(overrides)
    return RecoveryObservation(**values)  # type: ignore[arg-type]


def test_exact_fresh_stopped_state_reconciles_read_only() -> None:
    identity = _identity()

    report = reconcile_read_only(
        identity, _snapshot(identity), _observation(identity), as_of=_NOW
    )

    assert report.status is RecoveryStatus.CLEAN
    assert report.blockers == ()
    assert report.observed_position == Decimal("0")
    assert report.working_order_count == 0


def test_missing_or_expired_recovery_observation_is_not_clean() -> None:
    identity = _identity()
    missing = reconcile_read_only(identity, _snapshot(identity), None, as_of=_NOW)
    assert missing.status is RecoveryStatus.UNKNOWN
    assert RecoveryBlocker.OBSERVATION_MISSING in missing.blockers

    expired = reconcile_read_only(
        identity,
        _snapshot(identity),
        _observation(
            identity,
            observed_at=_NOW - timedelta(seconds=2),
            valid_until=_NOW - timedelta(seconds=1),
        ),
        as_of=_NOW,
    )
    assert expired.status is RecoveryStatus.BLOCKED
    assert RecoveryBlocker.OBSERVATION_NOT_FRESH in expired.blockers


def test_identity_position_working_order_and_effect_ambiguity_block() -> None:
    identity = _identity()
    other = replace(identity, account_fingerprint="9" * 64)
    account_drift = reconcile_read_only(
        identity, _snapshot(identity), _observation(other), as_of=_NOW
    )
    assert RecoveryBlocker.IDENTITY_MISMATCH in account_drift.blockers

    wrong_position = reconcile_read_only(
        identity,
        _snapshot(identity),
        _observation(identity, position_quantity=Decimal("0.01")),
        as_of=_NOW,
    )
    assert RecoveryBlocker.POSITION_MISMATCH in wrong_position.blockers

    working = reconcile_read_only(
        identity,
        _snapshot(identity),
        _observation(identity, working_order_count=1),
        as_of=_NOW,
    )
    assert RecoveryBlocker.WORKING_ORDERS_PRESENT in working.blockers

    ambiguous = reconcile_read_only(
        identity,
        _snapshot(identity, effect_disposition=EffectDisposition.MAY_HAVE_OCCURRED),
        _observation(identity, unresolved_effect=True),
        as_of=_NOW,
    )
    assert RecoveryBlocker.UNRESOLVED_EFFECT in ambiguous.blockers


def test_pending_order_and_owned_position_are_not_repaired_or_adopted() -> None:
    identity = _identity()
    pending = _snapshot(
        identity,
        lifecycle=Lifecycle.RECONCILING,
        pending_intent_id="intent-1",
        pending_kind=IntentKind.ENTRY,
        pending_requested_dollars=Decimal("10.00"),
    )
    report = reconcile_read_only(
        identity,
        pending,
        _observation(identity),
        as_of=_NOW,
    )
    assert RecoveryBlocker.STATE_NOT_STOPPED in report.blockers
    assert RecoveryBlocker.PENDING_INTENT_PRESENT in report.blockers

    owned = _snapshot(
        identity,
        cumulative_bought=Decimal("0.1"),
        entries_used=1,
        entry_local_intent_id="intent-1",
        entry_provider_order_id="order-1",
    )
    report = reconcile_read_only(
        identity,
        owned,
        _observation(identity, position_quantity=Decimal("0.1")),
        as_of=_NOW,
    )
    assert RecoveryBlocker.OWNED_POSITION_PRESENT in report.blockers
