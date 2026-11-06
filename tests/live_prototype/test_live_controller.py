from decimal import Decimal
from pathlib import Path
from threading import Barrier, Thread

import pytest

from trading_bot.live_prototype.durable_state import (
    BlockReason,
    DurableStateError,
    DurableStateStore,
    IntentStatus,
    ReconciliationSnapshot,
    RuntimeIdentity,
)
from trading_bot.live_prototype.live_controller import LiveController


def _identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        account_fingerprint="a" * 64,
        source_head="b" * 40,
        source_tree="c" * 40,
        config_digest="d" * 64,
        binding_digest="e" * 64,
        lifecycle_id="12345678-1234-5678-1234-567812345678",
    )


def _controller(tmp_path: Path) -> LiveController:
    store = DurableStateStore.create(tmp_path / "state.jsonl", _identity())
    store.reconcile(ReconciliationSnapshot(_identity(), Decimal("0")))
    return LiveController(store)


def test_prepare_persists_before_external_boundary_and_never_retries(tmp_path: Path):
    controller = _controller(tmp_path)
    intent_id = controller.reserve_entry(Decimal("2.00"))
    permit = controller.prepare_invocation(intent_id)

    assert permit.intent_id == intent_id
    assert permit.requested_dollars == Decimal("2.00")
    assert controller.state.entry is not None
    assert controller.state.entry.status is IntentStatus.MAY_HAVE_OCCURRED
    with pytest.raises(DurableStateError, match="reconciled|current"):
        controller.prepare_invocation(intent_id)

    controller.mark_unknown(intent_id)
    assert controller.state.blocked_reason is BlockReason.UNCERTAIN_EFFECT


def test_controller_serializes_competing_entry_reservations(tmp_path: Path):
    controller = _controller(tmp_path)
    barrier = Barrier(3)
    outcomes: list[object] = []

    def reserve() -> None:
        barrier.wait()
        try:
            outcomes.append(controller.reserve_entry(Decimal("1.00")))
        except Exception as error:
            outcomes.append(error)

    workers = [Thread(target=reserve), Thread(target=reserve)]
    for worker in workers:
        worker.start()
    barrier.wait()
    for worker in workers:
        worker.join(timeout=2)

    assert sum(isinstance(outcome, str) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, Exception) for outcome in outcomes) == 1
    assert controller.state.entry is not None
