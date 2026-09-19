"""Reusable weak-provenance harness for selected-C3 history composition tests."""

from __future__ import annotations

import weakref
from collections.abc import Callable

import pytest

from trading_bot.runtime import personal_desktop_unattended_c3_history as history
from trading_bot.runtime import personal_desktop_unattended_daily_cycle as daily_cycle
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SelectedC3StrategyHistoryWindowClassification,
    SelectedC3StrategyHistoryWindowResult,
    SessionIndexedSelectedC3SnapshotReadResult,
)
from trading_bot.strategies import MovingAverageCrossoverConfig


def install_weak_selected_c3_history_reader(
    monkeypatch: pytest.MonkeyPatch,
    *,
    authority: object,
    selected: tuple[SessionIndexedSelectedC3SnapshotReadResult, ...],
    current: SessionIndexedSelectedC3SnapshotReadResult,
    config: MovingAverageCrossoverConfig,
) -> tuple[
    list[weakref.ReferenceType[object]],
    Callable[[object, object, object], None],
]:
    """Install a production-shaped reader whose permits die with the reader."""

    permits = tuple(item.selected.permit for item in selected)
    registry: dict[object, weakref.ReferenceType[object]] = {}
    reader_refs: list[weakref.ReferenceType[object]] = []

    class Reader:
        __slots__ = ("__weakref__",)

        def __init__(self, candidate_authority: object) -> None:
            assert candidate_authority is authority
            reference = weakref.ref(self)
            reader_refs.append(reference)
            for permit in permits:
                registry[permit] = reference

        def inspect_strategy_history_window(
            self, candidate_current: object, candidate_config: object
        ) -> SelectedC3StrategyHistoryWindowResult:
            assert candidate_current is current
            assert candidate_config == config
            return SelectedC3StrategyHistoryWindowResult(
                SelectedC3StrategyHistoryWindowClassification.READY,
                tuple(item.session for item in selected),
                selected,
            )

    def require_live_provenance(
        permit: object, audit: object, candidate_authority: object
    ) -> None:
        del audit
        reference = registry.get(permit)
        if (
            candidate_authority is not authority
            or reference is None
            or reference() is None
        ):
            raise ValueError("selected C3 snapshot permit provenance is invalid")

    def retain_live_provenance(
        evidence: tuple[tuple[object, object], ...], candidate_authority: object
    ) -> object:
        retained = []
        for permit, audit in evidence:
            require_live_provenance(permit, audit, candidate_authority)
            reader = registry[permit]()
            assert reader is not None
            if all(item is not reader for item in retained):
                retained.append(reader)
        return tuple(retained)

    monkeypatch.setattr(
        daily_cycle,
        "require_validated_production_authority",
        lambda value: value,
    )
    monkeypatch.setattr(
        daily_cycle,
        "WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority",
        Reader,
    )
    monkeypatch.setattr(
        history,
        "require_validated_production_authority",
        lambda value: value,
    )
    monkeypatch.setattr(
        history,
        "require_selected_c3_snapshot_matches_authority",
        require_live_provenance,
    )
    monkeypatch.setattr(
        history,
        "retain_selected_c3_snapshot_provenance_lifetime",
        retain_live_provenance,
    )
    return reader_refs, require_live_provenance
