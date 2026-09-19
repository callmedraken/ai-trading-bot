"""Focused lifetime coverage for production G6 selected-C3 readers."""

from __future__ import annotations

import gc
import weakref
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import personal_desktop_unattended_daily_cycle as daily_cycle
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    require_selected_c3_strategy_history_binding,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification,
    run_personal_desktop_unattended_daily_cycle_for_test,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

from ._selected_c3_history_lifetime import (
    install_weak_selected_c3_history_reader,
)
from .test_personal_desktop_unattended_c3_history import _valid_chain
from .test_personal_desktop_unattended_daily_cycle import _OBSERVED, _dependencies
from .test_personal_desktop_unattended_paper_decision_intent import _session_read


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


def test_shared_production_history_retains_exact_permit_provenance_until_released(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_history, current = _valid_chain()
    selected = (*selected_history, current)
    authority = object()
    config = MovingAverageCrossoverConfig(3, 5, Decimal("1"))
    reader_refs, require_live_provenance = install_weak_selected_c3_history_reader(
        monkeypatch,
        authority=authority,
        selected=selected,
        current=current,
        config=config,
    )

    binding = daily_cycle.build_personal_desktop_unattended_c3_history(
        authority, current, config
    )
    gc.collect()
    assert len(reader_refs) == 1
    assert reader_refs[0]() is not None
    assert require_selected_c3_strategy_history_binding(binding, authority) is binding

    del binding
    gc.collect()
    assert reader_refs[0]() is None
    with pytest.raises(ValueError, match="provenance"):
        require_live_provenance(
            selected[0].selected.permit,
            selected[0].selected.audit,
            authority,
        )


def test_daily_cycle_consumes_shared_history_while_provenance_is_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = object()
    dependencies = _dependencies(monkeypatch)
    current = dependencies.read_selected(authority, TradingSession(date(2026, 8, 25)))
    selected_history = tuple(
        _session_read(day, 100 + index)
        for index, day in enumerate(
            (
                date(2026, 8, 18),
                date(2026, 8, 19),
                date(2026, 8, 20),
                date(2026, 8, 21),
                date(2026, 8, 24),
            )
        )
    )
    selected = (*selected_history, current)
    reader_refs, _ = install_weak_selected_c3_history_reader(
        monkeypatch,
        authority=authority,
        selected=selected,
        current=current,
        config=daily_cycle.personal_desktop_unattended_strategy_config(),
    )

    original_build_next = dependencies.build_next_decision

    def build_next(authority_value, selected_value, binding, *args):
        assert (
            require_selected_c3_strategy_history_binding(binding, authority_value)
            is binding
        )
        return original_build_next(authority_value, selected_value, binding, *args)

    dependencies = replace(
        dependencies,
        build_history=daily_cycle.build_personal_desktop_unattended_c3_history,
        build_next_decision=build_next,
    )
    result = run_personal_desktop_unattended_daily_cycle_for_test(
        authority, _OBSERVED, dependencies
    )

    assert result.classification is (
        PersonalDesktopUnattendedDailyCycleClassification.DECISION_READY
    )
    gc.collect()
    assert reader_refs and all(reference() is None for reference in reader_refs)
