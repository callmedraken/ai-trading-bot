from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.live_prototype.durable_state import (
    DurableStateError,
    DurableStateStore,
    DurableWriteError,
    IntentStatus,
    L43OriginAnchor,
    OrderObservation,
    OrderStatus,
    ReconciliationSnapshot,
    RuntimeIdentity,
)
from trading_bot.live_prototype.l43_state import (
    L43StateSession,
    L43StateUnavailable,
    read_l43_state_snapshot,
)
from trading_bot.live_prototype.tiny_live_policy import (
    ManualCloseBasis,
    ManualCloseTrigger,
)

_IDENTITY = RuntimeIdentity(
    account_fingerprint="a" * 64,
    source_head="b" * 40,
    source_tree="c" * 40,
    config_digest="d" * 64,
    binding_digest="e" * 64,
    lifecycle_id=str(UUID("eb8e31b2-cb9e-46f4-845d-eab478f43d50")),
)
_ORIGIN = L43OriginAnchor(
    runtime_identity=_IDENTITY,
    journal_sha256="1" * 64,
    initialization_event_sha256="2" * 64,
    consumed_observation_sha256="3" * 64,
)
_PROPOSAL_SHA = "4" * 64
_ARGUMENTS_SHA = "5" * 64
_REVIEW_SHA = "6" * 64
_AUTHORITY_SHA = "7" * 64
_EVIDENCE_SHA = "8" * 64


def _state_path(tmp_path: Path, *, reconcile: bool = True) -> Path:
    path = tmp_path / "l43-state.jsonl"
    DurableStateStore.create(path, _IDENTITY, l43_origin=_ORIGIN)
    path.with_suffix(path.suffix + ".lock").write_bytes(b"")
    if reconcile:
        with L43StateSession.open_existing(path, _ORIGIN) as session:
            session.reconcile(ReconciliationSnapshot(_IDENTITY, Decimal("0")))
    return path


def _owned_state(path: Path) -> str:
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        if not session.state.reconciled:
            session.reconcile(ReconciliationSnapshot(_IDENTITY, Decimal("0")))
        intent_id = session.reserve_entry(Decimal("10.00"))
        prepared = session.prepare_invocation(intent_id)
        assert prepared.kind.value == "ENTRY"
        assert prepared.authority_sha256 is None
        session.bind_provider_order(intent_id, "entry-order")
        session.reconcile(
            ReconciliationSnapshot(
                _IDENTITY,
                Decimal("0.5"),
                (
                    OrderObservation(
                        local_intent_id=intent_id,
                        provider_order_id="entry-order",
                        status=OrderStatus.FILLED,
                        cumulative_quantity=Decimal("0.5"),
                        cumulative_notional=Decimal("10"),
                        working_remainder=Decimal("0"),
                    ),
                ),
            )
        )
    return intent_id


def _accept_review(session: L43StateSession) -> None:
    session.begin_sell_review(
        proposal_sha256=_PROPOSAL_SHA,
        arguments_sha256=_ARGUMENTS_SHA,
    )
    session.accept_sell_review(
        proposal_sha256=_PROPOSAL_SHA,
        arguments_sha256=_ARGUMENTS_SHA,
        review_evidence_sha256=_REVIEW_SHA,
    )


def test_l43_genesis_binds_q62_origin_without_changing_legacy_initialization(
    tmp_path: Path,
):
    path = tmp_path / "l43-state.jsonl"
    store = DurableStateStore.create(path, _IDENTITY, l43_origin=_ORIGIN)
    assert store.state.l43_origin == _ORIGIN
    reopened = DurableStateStore.open(path, _IDENTITY)
    assert reopened.state.identity == _IDENTITY
    assert reopened.state.l43_origin == _ORIGIN
    assert reopened.state.last_sequence == 0
    assert not reopened.state.reconciled

    legacy_path = tmp_path / "legacy-state.jsonl"
    DurableStateStore.create(legacy_path, _IDENTITY)
    legacy_record = json.loads(legacy_path.read_text(encoding="ascii").splitlines()[0])
    assert set(legacy_record["payload"]) == {"identity", "baseline_quantity"}
    assert DurableStateStore.open(legacy_path, _IDENTITY).state.l43_origin is None


def test_missing_or_unprovisioned_state_snapshot_creates_no_files(tmp_path: Path):
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(L43StateUnavailable):
        read_l43_state_snapshot(missing, _ORIGIN)
    assert not missing.exists()
    assert not missing.with_suffix(missing.suffix + ".lock").exists()

    unprovisioned = tmp_path / "unprovisioned.jsonl"
    DurableStateStore.create(unprovisioned, _IDENTITY, l43_origin=_ORIGIN)
    with pytest.raises(L43StateUnavailable):
        read_l43_state_snapshot(unprovisioned, _ORIGIN)
    assert unprovisioned.exists()
    assert not unprovisioned.with_suffix(unprovisioned.suffix + ".lock").exists()


def test_l43_session_replays_origin_and_entry_consumption_without_replenishment(
    tmp_path: Path,
):
    path = _state_path(tmp_path, reconcile=False)
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        initial = session.snapshot()
        assert initial.origin.runtime_identity == _IDENTITY
        assert initial.origin.journal_sha256 == _ORIGIN.journal_sha256
        assert initial.origin.initialization_event_sha256 == (
            _ORIGIN.initialization_event_sha256
        )
        assert initial.origin.consumed_observation_sha256 == (
            _ORIGIN.consumed_observation_sha256
        )
        assert not session.state.reconciled
        with pytest.raises(DurableStateError):
            session.reserve_entry(Decimal("1.00"))

        session.reconcile(ReconciliationSnapshot(_IDENTITY, Decimal("0")))
        intent_id = session.reserve_entry(Decimal("10.00"))
        prepared = session.prepare_invocation(intent_id)
        assert session.state.entry is not None
        assert session.state.entry.status is IntentStatus.MAY_HAVE_OCCURRED
        assert prepared.intent_id == intent_id

    detached = read_l43_state_snapshot(path, _ORIGIN)
    assert detached.state.entries_used == 1
    assert detached.state.entry is not None
    assert detached.state.entry.status is IntentStatus.MAY_HAVE_OCCURRED
    assert detached.last_sequence == detached.state.last_sequence
    assert detached.journal_sha256 == detached.state.journal_hash

    with L43StateSession.open_existing(path, _ORIGIN) as reopened:
        with pytest.raises(DurableStateError):
            reopened.reserve_entry(Decimal("10.00"))
        with pytest.raises(DurableStateError):
            reopened.prepare_invocation(intent_id)


def test_reserved_entry_from_an_earlier_session_cannot_be_prepared(tmp_path: Path):
    path = _state_path(tmp_path)
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        intent_id = session.reserve_entry(Decimal("10.00"))
        assert session.state.entry is not None
        assert session.state.entry.status is IntentStatus.RESERVED

    with L43StateSession.open_existing(path, _ORIGIN) as restarted:
        with pytest.raises(L43StateUnavailable):
            restarted.prepare_invocation(intent_id)
        with pytest.raises(DurableStateError):
            restarted.reserve_entry(Decimal("10.00"))
        assert restarted.state.entry is not None
        assert restarted.state.entry.status is IntentStatus.RESERVED


def test_single_writer_lock_and_session_methods_end_with_lock_lifetime(tmp_path: Path):
    path = _state_path(tmp_path)
    first = L43StateSession.open_existing(path, _ORIGIN)
    with first:
        with pytest.raises(L43StateUnavailable):
            with L43StateSession.open_existing(path, _ORIGIN):
                pytest.fail("a second process owner must not acquire the state lock")
    with pytest.raises(L43StateUnavailable):
        _ = first.state
    with pytest.raises(L43StateUnavailable):
        first.reserve_entry(Decimal("1.00"))


def test_incomplete_review_after_restart_is_blocked_and_cannot_be_accepted(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        session.begin_sell_review(
            proposal_sha256=_PROPOSAL_SHA,
            arguments_sha256=_ARGUMENTS_SHA,
        )
        active = session.snapshot()
        assert active.sell_review_pending
        assert active.review_active
        assert not active.manual_close_required

    restarted = read_l43_state_snapshot(path, _ORIGIN)
    assert restarted.sell_review_pending
    assert not restarted.review_active
    assert restarted.manual_close_required

    with L43StateSession.open_existing(path, _ORIGIN) as session:
        with pytest.raises(L43StateUnavailable):
            session.accept_sell_review(
                proposal_sha256=_PROPOSAL_SHA,
                arguments_sha256=_ARGUMENTS_SHA,
                review_evidence_sha256=_REVIEW_SHA,
            )
        with pytest.raises(DurableStateError):
            session.begin_sell_review(
                proposal_sha256=_PROPOSAL_SHA,
                arguments_sha256=_ARGUMENTS_SHA,
            )
        with pytest.raises(DurableStateError):
            session.reserve_exit(Decimal("0.5"), authority_sha256=_AUTHORITY_SHA)
        close = session.require_manual_close(
            trigger=ManualCloseTrigger.SELL_REVIEW_UNKNOWN,
            effect_evidence_sha256=_EVIDENCE_SHA,
        )
        assert close.exact_residual_quantity == Decimal("0.5")
        assert close.basis is ManualCloseBasis.CONFIRMED_RECONCILED_RESIDUAL
        assert not close.automated_entry_allowed
        assert not close.automated_sell_allowed
        assert close.read_only_reconciliation_allowed

        # Read-only factual replay remains available while the sticky close is set.
        session.reconcile(
            ReconciliationSnapshot(
                _IDENTITY,
                Decimal("0.5"),
                (
                    OrderObservation(
                        local_intent_id=session.state.entry.intent_id,
                        provider_order_id="entry-order",
                        status=OrderStatus.FILLED,
                        cumulative_quantity=Decimal("0.5"),
                        cumulative_notional=Decimal("10"),
                        working_remainder=Decimal("0"),
                    ),
                ),
            )
        )
        assert session.state.manual_close == close
        assert session.state.manual_close_required

    after = read_l43_state_snapshot(path, _ORIGIN)
    assert after.state.manual_close == close
    assert after.manual_close_required


def test_accepted_review_alone_cannot_reserve_or_prepare_exit(tmp_path: Path):
    path = _state_path(tmp_path)
    _owned_state(path)
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        _accept_review(session)
        with pytest.raises(DurableStateError):
            session.reserve_exit(Decimal("0.5"))
        exit_id = session.reserve_exit(Decimal("0.5"), authority_sha256=_AUTHORITY_SHA)
        assert session.state.exit is not None
        assert session.state.exit.authority_sha256 == _AUTHORITY_SHA
        prepared = session.prepare_invocation(exit_id)
        assert prepared.kind.value == "EXIT"
        assert prepared.authority_sha256 == _AUTHORITY_SHA


def test_unknown_sell_consumes_exit_and_preserves_exact_residual_stickily(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        _accept_review(session)
        exit_id = session.reserve_exit(Decimal("0.5"), authority_sha256=_AUTHORITY_SHA)
        session.prepare_invocation(exit_id)
        close = session.require_manual_close(
            trigger=ManualCloseTrigger.SELL_UNKNOWN,
            effect_evidence_sha256=_EVIDENCE_SHA,
        )
        assert close.exact_residual_quantity == Decimal("0.5")
        assert close.basis is ManualCloseBasis.LAST_EXACT_RESIDUAL_BEFORE_UNKNOWN
        assert session.state.entries_used == 1
        assert session.state.exits_used == 1
        assert session.state.manual_close_required
        with pytest.raises(DurableStateError):
            session.prepare_invocation(exit_id)

    after = read_l43_state_snapshot(path, _ORIGIN)
    assert after.state.manual_close == close
    assert after.state.owned_quantity == Decimal("0.5")
    assert after.manual_close_required


def test_terminal_rejected_sell_crash_gap_derives_manual_close_and_blocks_retry(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        _accept_review(session)
        exit_id = session.reserve_exit(Decimal("0.5"), authority_sha256=_AUTHORITY_SHA)
        session.prepare_invocation(exit_id)
        session.bind_provider_order(exit_id, "exit-order")
        session.reconcile(
            ReconciliationSnapshot(
                _IDENTITY,
                Decimal("0.5"),
                (
                    OrderObservation(
                        local_intent_id=exit_id,
                        provider_order_id="exit-order",
                        status=OrderStatus.REJECTED,
                        cumulative_quantity=Decimal("0"),
                        cumulative_notional=Decimal("0"),
                        working_remainder=Decimal("0"),
                    ),
                ),
            )
        )
        assert session.state.exit is not None
        assert session.state.exit.status is IntentStatus.REJECTED
        assert session.state.manual_close is None

    after_crash = read_l43_state_snapshot(path, _ORIGIN)
    assert after_crash.manual_close_required
    assert after_crash.state.owned_quantity == Decimal("0.5")
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        with pytest.raises(DurableStateError):
            session.reserve_exit(Decimal("0.5"), authority_sha256=_AUTHORITY_SHA)
        close = session.require_manual_close(
            trigger=ManualCloseTrigger.SELL_REJECTED,
            effect_evidence_sha256=_EVIDENCE_SHA,
        )
        assert close.exact_residual_quantity == Decimal("0.5")

    persisted = read_l43_state_snapshot(path, _ORIGIN)
    assert persisted.state.manual_close == close
    assert persisted.manual_close_required


def test_abandoned_reserved_or_bound_sell_requires_manual_follow_up(tmp_path: Path):
    path = _state_path(tmp_path)
    _owned_state(path)
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        _accept_review(session)
        exit_id = session.reserve_exit(Decimal("0.5"), authority_sha256=_AUTHORITY_SHA)
        active_reservation = session.snapshot()
        assert not active_reservation.manual_follow_up_required

    after_reservation_crash = read_l43_state_snapshot(path, _ORIGIN)
    assert after_reservation_crash.state.exit is not None
    assert after_reservation_crash.state.exit.status is IntentStatus.RESERVED
    assert after_reservation_crash.state.owned_quantity == Decimal("0.5")
    assert after_reservation_crash.manual_follow_up_required
    assert not after_reservation_crash.manual_close_required
    with L43StateSession.open_existing(path, _ORIGIN) as restarted:
        with pytest.raises(L43StateUnavailable):
            restarted.prepare_invocation(exit_id)
        with pytest.raises(DurableStateError):
            restarted.reserve_exit(Decimal("0.5"), authority_sha256=_AUTHORITY_SHA)

    bound_path = tmp_path / "bound-state.jsonl"
    DurableStateStore.create(bound_path, _IDENTITY, l43_origin=_ORIGIN)
    bound_path.with_suffix(bound_path.suffix + ".lock").write_bytes(b"")
    _owned_state(bound_path)
    with L43StateSession.open_existing(bound_path, _ORIGIN) as session:
        _accept_review(session)
        bound_exit_id = session.reserve_exit(
            Decimal("0.5"), authority_sha256=_AUTHORITY_SHA
        )
        session.prepare_invocation(bound_exit_id)
        session.bind_provider_order(bound_exit_id, "exit-order")

    after_bind_crash = read_l43_state_snapshot(bound_path, _ORIGIN)
    assert after_bind_crash.state.exit is not None
    assert after_bind_crash.state.exit.status is IntentStatus.WORKING
    assert after_bind_crash.state.owned_quantity == Decimal("0.5")
    assert after_bind_crash.manual_follow_up_required
    assert not after_bind_crash.manual_close_required
    with L43StateSession.open_existing(bound_path, _ORIGIN) as restarted:
        restarted.reconcile(
            ReconciliationSnapshot(
                _IDENTITY,
                Decimal("0.5"),
                (
                    OrderObservation(
                        local_intent_id=bound_exit_id,
                        provider_order_id="exit-order",
                        status=OrderStatus.WORKING,
                        cumulative_quantity=Decimal("0"),
                        cumulative_notional=Decimal("0"),
                        working_remainder=Decimal("0.5"),
                    ),
                    OrderObservation(
                        local_intent_id=restarted.state.entry.intent_id,
                        provider_order_id="entry-order",
                        status=OrderStatus.FILLED,
                        cumulative_quantity=Decimal("0.5"),
                        cumulative_notional=Decimal("10"),
                        working_remainder=Decimal("0"),
                    ),
                ),
            )
        )
        assert restarted.state.owned_quantity == Decimal("0.5")
        assert restarted.state.manual_follow_up_required
        with pytest.raises(L43StateUnavailable):
            restarted.prepare_invocation(bound_exit_id)


def test_manual_close_append_failure_keeps_terminal_sell_fail_closed(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    with L43StateSession.open_existing(path, _ORIGIN) as session:
        _accept_review(session)
        exit_id = session.reserve_exit(Decimal("0.5"), authority_sha256=_AUTHORITY_SHA)
        session.prepare_invocation(exit_id)
        session.bind_provider_order(exit_id, "exit-order")
        session.reconcile(
            ReconciliationSnapshot(
                _IDENTITY,
                Decimal("0.5"),
                (
                    OrderObservation(
                        local_intent_id=exit_id,
                        provider_order_id="exit-order",
                        status=OrderStatus.CANCELED,
                        cumulative_quantity=Decimal("0"),
                        cumulative_notional=Decimal("0"),
                        working_remainder=Decimal("0"),
                    ),
                ),
            )
        )

    def fail_open(_path: Path, _mode: str):
        raise OSError("synthetic append-open failure")

    reopened = DurableStateStore.open(path, _IDENTITY, file_opener=fail_open)
    with pytest.raises(DurableWriteError):
        reopened.require_manual_close(
            trigger=ManualCloseTrigger.SELL_CANCELED,
            effect_evidence_sha256=_EVIDENCE_SHA,
        )

    after_failure = DurableStateStore.open(path, _IDENTITY)
    assert after_failure.state.manual_close is None
    assert after_failure.state.manual_close_required
    with pytest.raises(DurableStateError):
        after_failure.reserve_entry(Decimal("1.00"))


def test_wrong_origin_and_ambiguous_journal_fail_without_repair(tmp_path: Path):
    path = _state_path(tmp_path)
    wrong_origin = L43OriginAnchor(
        runtime_identity=_IDENTITY,
        journal_sha256="9" * 64,
        initialization_event_sha256="2" * 64,
        consumed_observation_sha256="3" * 64,
    )
    with pytest.raises(L43StateUnavailable):
        with L43StateSession.open_existing(path, wrong_origin):
            pytest.fail("mismatched Q62 origin must be rejected")

    path.write_bytes(path.read_bytes() + b"{")
    with pytest.raises(L43StateUnavailable):
        with L43StateSession.open_existing(path, _ORIGIN):
            pytest.fail("an incomplete record must not be repaired")
    assert path.read_bytes().endswith(b"{")
