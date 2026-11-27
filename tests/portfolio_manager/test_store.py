from __future__ import annotations

import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID

import pytest

from trading_bot.portfolio_manager.store import (
    PortfolioManagerStore,
    PortfolioManagerStoreConflict,
    PortfolioManagerStoreCorruption,
)

_ACCOUNT_A = "a" * 64
_ACCOUNT_B = "b" * 64
_INTENT = "c" * 64
_SEMANTIC = "d" * 64
_OTHER_SEMANTIC = "e" * 64
_SNAPSHOT = UUID("8a3d7c3a-d2f9-5f10-91e6-ba06c3935d84")
_AT = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)


def _record(store: PortfolioManagerStore, semantic_digest: str = _SEMANTIC):
    return store.record_outcome(
        intent_key=_INTENT,
        snapshot_id=_SNAPSHOT,
        semantic_digest=semantic_digest,
        recorded_at=_AT,
        payload={"model": "SYNTHETIC_REFERENCE_V1", "preview": "PREVIEW_ONLY"},
    )


def test_store_is_lazy_account_bound_and_restart_idempotent(tmp_path):
    first = PortfolioManagerStore(tmp_path, _ACCOUNT_A)
    assert first.path == (
        tmp_path / "portfolio-manager" / _ACCOUNT_A / "decision-history.sqlite3"
    )
    assert not first.path.exists()

    saved, inserted = _record(first)
    assert inserted
    assert saved.intent_key == _INTENT
    assert saved.snapshot_id == _SNAPSHOT

    restarted = PortfolioManagerStore(tmp_path, _ACCOUNT_A)
    duplicate, inserted_again = _record(restarted)
    assert not inserted_again
    assert duplicate == saved
    assert restarted.load_recent() == (saved,)

    isolated = PortfolioManagerStore(tmp_path, _ACCOUNT_B)
    assert isolated.path != first.path
    assert isolated.load_recent() == ()


def test_portfolio_manager_uses_its_namespace_not_intraday_sibling(tmp_path):
    store = PortfolioManagerStore(tmp_path, _ACCOUNT_A)
    intraday_path = tmp_path / "intraday" / _ACCOUNT_A / "decision-history.sqlite3"
    intraday_path.parent.mkdir(parents=True)
    intraday_path.write_bytes(b"intraday-owned state")

    assert store.load_recent() == ()
    assert store.path.exists()
    assert intraday_path.read_bytes() == b"intraday-owned state"


def test_concurrent_instances_reserve_same_semantic_intent_once(tmp_path):
    stores = (
        PortfolioManagerStore(tmp_path, _ACCOUNT_A),
        PortfolioManagerStore(tmp_path, _ACCOUNT_A),
    )
    barrier = Barrier(2)

    def insert(store):
        barrier.wait(timeout=5)
        return _record(store)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(insert, stores))

    assert sum(inserted for _, inserted in results) == 1
    assert results[0][0] == results[1][0]
    assert stores[0].load_recent() == (results[0][0],)


def test_same_intent_cannot_be_rebound_to_different_semantics(tmp_path):
    store = PortfolioManagerStore(tmp_path, _ACCOUNT_A)
    _record(store)

    with pytest.raises(PortfolioManagerStoreConflict):
        _record(store, _OTHER_SEMANTIC)

    assert len(store.load_recent()) == 1


def test_existing_database_for_another_account_fails_before_history_read(tmp_path):
    account_a = PortfolioManagerStore(tmp_path, _ACCOUNT_A)
    _record(account_a)
    account_b = PortfolioManagerStore(tmp_path, _ACCOUNT_B)
    account_b.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(account_a.path, account_b.path)

    with pytest.raises(PortfolioManagerStoreCorruption):
        account_b.load_recent()


def test_populated_unmarked_database_is_not_silently_account_bound(tmp_path):
    store = PortfolioManagerStore(tmp_path, _ACCOUNT_A)
    store.path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "CREATE TABLE outcomes ("
            "sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
            "intent_key TEXT NOT NULL UNIQUE, snapshot_id TEXT NOT NULL, "
            "semantic_digest TEXT NOT NULL, recorded_at TEXT NOT NULL, "
            "payload_json TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO outcomes "
            "(intent_key, snapshot_id, semantic_digest, recorded_at, payload_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                _INTENT,
                str(_SNAPSHOT),
                _SEMANTIC,
                _AT.isoformat(),
                '{"existing":"unbound"}',
            ),
        )

    with pytest.raises(PortfolioManagerStoreCorruption):
        store.load_recent()

    with sqlite3.connect(store.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "store_metadata" not in tables
