"""Focused lifetime coverage for production G6 selected-C3 readers."""

from __future__ import annotations

import gc
import weakref
from datetime import date

import pytest

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import personal_desktop_unattended_daily_cycle as daily_cycle


def test_production_dependencies_retain_every_selected_reader_for_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader_refs: list[weakref.ReferenceType[object]] = []

    class Reader:
        def __init__(self, authority: object) -> None:
            self.authority = authority
            reader_refs.append(weakref.ref(self))

        def read_selected_snapshot_for_session(self, session: TradingSession) -> object:
            return object()

    monkeypatch.setattr(
        daily_cycle,
        "WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority",
        Reader,
    )

    dependencies = daily_cycle._production_dependencies()
    authority = object()

    dependencies.read_selected(authority, TradingSession(date(2026, 9, 10)))
    gc.collect()
    assert len(reader_refs) == 1
    assert reader_refs[0]() is not None

    dependencies.read_selected(authority, TradingSession(date(2026, 9, 11)))
    gc.collect()
    assert len(reader_refs) == 2
    assert all(reference() is not None for reference in reader_refs)

    del dependencies
    gc.collect()
    assert all(reference() is None for reference in reader_refs)
