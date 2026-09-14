"""Focused lifetime coverage for frozen first Paper-v2 configuration replay."""

from __future__ import annotations

import weakref
from types import SimpleNamespace

import pytest

import trading_bot.runtime.personal_desktop_first_paper_configuration as first_config


class _StopAfterAuthorityMatch(Exception):
    pass


def test_first_configuration_retains_p2_reader_until_authority_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c1 = SimpleNamespace(
        machine_authority_id="223f0d4e-36f9-4b9f-bf0e-febf16fcd3f1",
        authority_epoch_id="e6f3de5d-1412-40ad-a022-8b33e72a5f6d",
        approved_account_sid=(
            first_config.PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
        ),
    )
    selected = SimpleNamespace(permit=object(), audit=object())
    reader_ref: weakref.ReferenceType[object] | None = None

    class Reader:
        def __init__(self, authority: object) -> None:
            nonlocal reader_ref
            assert authority is c1
            reader_ref = weakref.ref(self)

        def read_selected_snapshot(self, selection_id: str) -> object:
            assert selection_id == "36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280"
            return selected

    def require_match(permit: object, audit: object, authority: object) -> None:
        assert permit is selected.permit
        assert audit is selected.audit
        assert authority is c1
        assert reader_ref is not None
        assert reader_ref() is not None
        raise _StopAfterAuthorityMatch

    monkeypatch.setattr(
        first_config,
        "require_validated_production_authority",
        lambda authority: c1,
    )
    monkeypatch.setattr(first_config, "_require_publication_freeze", lambda: None)
    monkeypatch.setattr(first_config, "_load_history_seed", lambda calendar: object())
    monkeypatch.setattr(first_config, "WindowsSelectedC3SnapshotReadAuthority", Reader)
    monkeypatch.setattr(
        first_config,
        "require_selected_c3_snapshot_matches_authority",
        require_match,
    )

    with pytest.raises(_StopAfterAuthorityMatch):
        first_config.read_personal_desktop_first_paper_cycle_configuration(c1)
