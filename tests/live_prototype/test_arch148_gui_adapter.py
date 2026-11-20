from __future__ import annotations

import sys
import types
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from trading_bot.live_prototype.contracts import Command, Lifecycle, Reason
from trading_bot.live_runtime.gui_adapter import (
    Arch148GuiAdapter,
    Arch148RuntimeDisplayCache,
    Arch148RuntimeDisplayFacts,
    create_arch148_window,
)
from trading_bot.live_runtime.worker import Arch148RuntimeWorker


def _worker() -> Arch148RuntimeWorker:
    return Arch148RuntimeWorker(
        lambda: None,
        owner_lease_factory=lambda: None,
        cadence=timedelta(seconds=1),
    )


def test_snapshot_projects_only_cached_facts_and_keeps_live_authority_closed() -> None:
    as_of = datetime(2026, 11, 19, 17, 0, tzinfo=UTC)
    cache = Arch148RuntimeDisplayCache(
        Arch148RuntimeDisplayFacts(
            session="ENTRY_OPEN",
            strategy="ARCH148_QQQ_5M_TQQQ_SQQQ",
            source_head="a" * 40,
            source_tree="b" * 40,
            signal_as_of=as_of,
            quote_as_of=as_of,
            signal_fresh=True,
            quote_fresh=True,
            connected=True,
            current_regime="BULLISH",
            entry_confirmation="BULLISH",
            desired_position="TQQQ",
            actual_position="TQQQ",
            owned_quantity=Decimal("2"),
            working_orders=1,
            fills=2,
            entries_used=1,
            exits_used=0,
            latest_reconciled_fill="entry average 10.00",
            hard_stop_price=Decimal("9.70"),
            protection_status="READY",
            pending_intent="NONE",
            effect_status="NONE",
            latest_result="HOLDING",
            blockers=(),
            health="HEALTHY",
            reasons=(Reason.NO_ACTION,),
        )
    )
    adapter = Arch148GuiAdapter(_worker(), cache.read)

    snapshot = adapter.snapshot()
    detail_text = "\n".join(adapter.display_details())

    assert snapshot.mode == "RESTRICTED_LIVE"
    assert snapshot.lifecycle is Lifecycle.STOPPED
    assert snapshot.source_head == "a" * 40
    assert snapshot.source_tree == "b" * 40
    assert snapshot.signal_as_of == as_of.isoformat()
    assert snapshot.exposure == "TQQQ"
    assert snapshot.owned_quantity == "2"
    assert snapshot.working_orders == 1
    assert snapshot.fills == 2
    assert snapshot.ready_to_trade is False
    assert snapshot.effect_authority_granted is False
    assert "Session: ENTRY_OPEN" in detail_text
    assert "BULLISH" in detail_text
    assert "Hard stop: 9.70; protection: READY" in detail_text
    assert "Source head/tree: " + "a" * 40 in detail_text


def test_window_factory_lazily_uses_existing_window_protocol(monkeypatch) -> None:
    calls: list[tuple[object, str]] = []

    class FakeWindow:
        def __init__(self, service, *, mode):
            calls.append((service, mode))

    fake_module = types.ModuleType("trading_bot.live_prototype.window")
    fake_module.PrototypeWindow = FakeWindow
    monkeypatch.setitem(sys.modules, "trading_bot.live_prototype.window", fake_module)
    service = Arch148GuiAdapter(_worker(), lambda: Arch148RuntimeDisplayFacts())

    result = create_arch148_window(service)

    assert isinstance(result, FakeWindow)
    assert calls == [(service, "RESTRICTED_LIVE")]


def test_gui_stop_and_report_commands_have_no_direct_provider_path() -> None:
    adapter = Arch148GuiAdapter(_worker(), lambda: Arch148RuntimeDisplayFacts())

    result = adapter.submit(Command.STOP)

    assert result.accepted
    assert result.reason is Reason.STOP_PENDING
    assert adapter.request_report(Path("ignored.json")) is False
    assert adapter.shutdown_complete()
