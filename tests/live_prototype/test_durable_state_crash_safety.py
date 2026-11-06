from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO

import pytest

from trading_bot.live_prototype.durable_state import (
    DurableStateError,
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


def _reconcile(
    store: DurableStateStore,
    position: str,
    orders: tuple[OrderObservation, ...] = (),
) -> None:
    store.reconcile(
        ReconciliationSnapshot(
            store.state.identity,
            Decimal(position),
            orders,
        )
    )


def _ready_store(path: Path) -> DurableStateStore:
    store = DurableStateStore.create(path, _identity())
    _reconcile(store, "0")
    return store


def test_partial_exit_decrements_only_confirmed_fill_and_preserves_residual(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.jsonl"
    store = _ready_store(path)
    entry_id = store.reserve_entry(Decimal("10"))
    store.mark_may_have_occurred(entry_id)
    store.bind_provider_order(entry_id, "entry-order")
    _reconcile(
        store,
        "0.05",
        (
            OrderObservation(
                entry_id,
                "entry-order",
                OrderStatus.CANCELED,
                Decimal("0.05"),
                Decimal("10.25"),
                Decimal("0"),
            ),
        ),
    )

    exit_id = store.reserve_exit(Decimal("0.05"))
    store.mark_may_have_occurred(exit_id)
    store.bind_provider_order(exit_id, "exit-order")
    _reconcile(
        store,
        "0.03",
        (
            OrderObservation(
                exit_id,
                "exit-order",
                OrderStatus.PARTIAL,
                Decimal("0.02"),
                Decimal("2.40"),
                Decimal("0.03"),
            ),
        ),
    )
    assert store.state.owned_quantity == Decimal("0.03")
    assert store.state.exit.status is IntentStatus.PARTIAL
    assert store.state.exit.requested_quantity == Decimal("0.05")
    assert store.state.exit.working_remainder == Decimal("0.03")

    _reconcile(
        store,
        "0.03",
        (
            OrderObservation(
                exit_id,
                "exit-order",
                OrderStatus.CANCELED,
                Decimal("0.02"),
                Decimal("2.40"),
                Decimal("0"),
            ),
        ),
    )
    reopened = DurableStateStore.open(path, _identity())
    assert reopened.state == store.state
    assert reopened.state.owned_quantity == Decimal("0.03")
    with pytest.raises(DurableStateError, match="consumed"):
        reopened.reserve_exit(Decimal("0.03"))


class _RecordingStream:
    def __init__(
        self,
        inner: BinaryIO,
        calls: list[str],
        fail_at: str | None,
    ) -> None:
        self.inner = inner
        self.calls = calls
        self.fail_at = fail_at

    def write(self, data: bytes) -> int:
        self.calls.append("write")
        written = self.inner.write(data)
        if self.fail_at == "write":
            raise OSError
        return written

    def flush(self) -> None:
        self.calls.append("flush")
        self.inner.flush()
        if self.fail_at == "flush":
            raise OSError

    def fileno(self) -> int:
        return self.inner.fileno()

    def close(self) -> None:
        self.calls.append("close")
        self.inner.close()
        if self.fail_at == "close":
            raise OSError


@pytest.mark.parametrize("failure", ["write", "flush", "fsync", "close", None])
def test_may_have_occurred_is_fsynced_and_closed_before_return(
    tmp_path: Path, failure: str | None
) -> None:
    calls: list[str] = []
    active_failure: list[str | None] = [None]
    path = tmp_path / f"{failure or 'success'}.jsonl"

    def opener(target: Path, mode: str) -> BinaryIO:
        calls.append("open")
        return _RecordingStream(target.open(mode), calls, active_failure[0])  # type: ignore[return-value]

    def sync(fd: int) -> None:
        calls.append("fsync")
        if active_failure[0] == "fsync":
            raise OSError
        os.fsync(fd)

    store = DurableStateStore.create(path, _identity(), file_opener=opener, fsync=sync)
    _reconcile(store, "0")
    intent_id = store.reserve_entry(Decimal("10"))
    _reconcile(store, "0")
    calls.clear()
    active_failure[0] = failure

    if failure is None:
        store.mark_may_have_occurred(intent_id)
        assert calls == ["open", "write", "flush", "fsync", "close"]
        reopened = DurableStateStore.open(path, _identity())
        assert reopened.state.entry.status is IntentStatus.MAY_HAVE_OCCURRED
    else:
        with pytest.raises(DurableWriteError) as raised:
            store.mark_may_have_occurred(intent_id)
        assert raised.value.phase == failure
        assert store.state.entry.status is IntentStatus.RESERVED
        with pytest.raises(DurableStateError, match="poisoned"):
            store.mark_may_have_occurred(intent_id)
        assert calls[-1] == "close"
