from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.live_prototype.durable_state import (
    BlockReason,
    DurableStateStore,
    DurableWriteError,
    IntentStatus,
    OrderObservation,
    OrderStatus,
    ReconciliationSnapshot,
    RuntimeIdentity,
)


def _identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        account_fingerprint="a" * 64,
        source_head="b" * 40,
        source_tree="c" * 40,
        config_digest="d" * 64,
        binding_digest="e" * 64,
        lifecycle_id="12345678-1234-5678-1234-567812345678",
    )


def _ready_store(tmp_path: Path) -> DurableStateStore:
    identity = _identity()
    store = DurableStateStore.create(tmp_path / "state.jsonl", identity)
    store.reconcile(ReconciliationSnapshot(identity, Decimal("0")))
    return store


def test_entry_reservation_is_durable_and_partial_fill_is_owned(tmp_path: Path):
    store = _ready_store(tmp_path)
    intent_id = store.reserve_entry(Decimal("9.00"))
    assert store.state.entry_reserved_dollars == Decimal("9.00")
    store.mark_may_have_occurred(intent_id)
    store.bind_provider_order(intent_id, "provider-order-1")
    store.reconcile(
        ReconciliationSnapshot(
            _identity(),
            Decimal("0.03"),
            (
                OrderObservation(
                    intent_id,
                    "provider-order-1",
                    OrderStatus.PARTIAL,
                    Decimal("0.03"),
                    Decimal("3.00"),
                    Decimal("0.01"),
                ),
            ),
        )
    )
    assert store.state.owned_quantity == Decimal("0.03")
    assert store.state.entry_reserved_dollars == Decimal("9.00")
    assert store.state.entry_budget_remaining == Decimal("1.00")


def test_restart_replays_hash_chain_and_requires_exact_identity(tmp_path: Path):
    store = _ready_store(tmp_path)
    store.reserve_entry(Decimal("2.00"))
    reopened = DurableStateStore.open(tmp_path / "state.jsonl", _identity())
    assert reopened.state.entry is not None
    assert reopened.state.entry.status is IntentStatus.RESERVED
    other = RuntimeIdentity(
        account_fingerprint="f" * 64,
        source_head="b" * 40,
        source_tree="c" * 40,
        config_digest="d" * 64,
        binding_digest="e" * 64,
        lifecycle_id="12345678-1234-5678-1234-567812345678",
    )
    with pytest.raises(ValueError, match="identity"):
        DurableStateStore.open(tmp_path / "state.jsonl", other)


def test_unknown_or_may_have_occurred_blocks_retry(tmp_path: Path):
    store = _ready_store(tmp_path)
    intent_id = store.reserve_entry(Decimal("2.00"))
    store.mark_may_have_occurred(intent_id)
    assert store.state.entry is not None
    assert store.state.entry.status is IntentStatus.MAY_HAVE_OCCURRED
    with pytest.raises(ValueError, match="uncertain|reconciled"):
        store.reserve_entry(Decimal("1.00"))
    store.mark_unknown(intent_id)
    assert store.state.blocked_reason is BlockReason.UNCERTAIN_EFFECT


def test_nonflat_baseline_and_manual_position_adoption_block(tmp_path: Path):
    identity = _identity()
    with pytest.raises(ValueError, match="nonflat"):
        DurableStateStore.create(
            tmp_path / "bad.jsonl", identity, initial_position=Decimal("1")
        )
    store = _ready_store(tmp_path)
    blocked = store.reconcile(ReconciliationSnapshot(identity, Decimal("1")))
    assert blocked.blocked_reason is BlockReason.POSITION_MISMATCH
    with pytest.raises(ValueError, match="reconciled"):
        store.reserve_entry(Decimal("1.00"))


def test_exit_uses_exact_owned_remainder_and_monotone_fills(tmp_path: Path):
    store = _ready_store(tmp_path)
    entry_id = store.reserve_entry(Decimal("2.00"))
    store.mark_may_have_occurred(entry_id)
    store.bind_provider_order(entry_id, "entry-order")
    store.reconcile(
        ReconciliationSnapshot(
            _identity(),
            Decimal("0.05"),
            (
                OrderObservation(
                    entry_id,
                    "entry-order",
                    OrderStatus.FILLED,
                    Decimal("0.05"),
                    Decimal("2.00"),
                    Decimal("0"),
                ),
            ),
        )
    )
    with pytest.raises(ValueError, match="exact"):
        store.reserve_exit(Decimal("0.04"))
    exit_id = store.reserve_exit(Decimal("0.05"))
    store.mark_may_have_occurred(exit_id)
    store.bind_provider_order(exit_id, "exit-order")
    reconciled = store.reconcile(
        ReconciliationSnapshot(
            _identity(),
            Decimal("0.04"),
            (
                OrderObservation(
                    exit_id,
                    "exit-order",
                    OrderStatus.PARTIAL,
                    Decimal("0.01"),
                    Decimal("0.40"),
                    Decimal("0.04"),
                ),
            ),
        )
    )
    assert reconciled.blocked_reason is None
    assert reconciled.owned_quantity == Decimal("0.04")
    regressed = store.reconcile(
        ReconciliationSnapshot(
            _identity(),
            Decimal("0.04"),
            (
                OrderObservation(
                    exit_id,
                    "exit-order",
                    OrderStatus.PARTIAL,
                    Decimal("0.005"),
                    Decimal("0.20"),
                    Decimal("0.045"),
                ),
            ),
        )
    )
    assert regressed.blocked_reason is BlockReason.FILL_REGRESSION


def test_save_fsync_failure_poisoned_store_never_invokes_provider(tmp_path: Path):
    calls: list[str] = []

    def failing_fsync(_fd: int) -> None:
        calls.append("fsync")
        raise OSError("secret provider text must not escape")

    with pytest.raises(DurableWriteError, match="fsync"):
        DurableStateStore.create(
            tmp_path / "state.jsonl", _identity(), fsync=failing_fsync
        )
    assert calls == ["fsync"]
