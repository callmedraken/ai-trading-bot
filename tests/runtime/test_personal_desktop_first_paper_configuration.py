"""Focused lifetime coverage for frozen first Paper-v2 configuration replay."""

from __future__ import annotations

import weakref
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

import trading_bot.runtime.personal_desktop_first_paper_configuration as first_config


_ROOT = Path(__file__).resolve().parents[2]
_SEED_RELATIVE_PATH = (
    "docs/validation/evidence/"
    "pd2d1-spy-strategy-history-seed-2026-08-28.json"
)
_SEED_SHA256 = "40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64"
_SEED_BYTE_LENGTH = 1060


class _StopAfterAuthorityMatch(Exception):
    pass


def test_frozen_first_configuration_history_seed_is_exact_checkout_bytes() -> None:
    seed_path = _ROOT / _SEED_RELATIVE_PATH
    payload = seed_path.read_bytes()

    assert len(payload) == _SEED_BYTE_LENGTH
    assert sha256(payload).hexdigest() == _SEED_SHA256
    assert payload.endswith(b"\n")
    assert not payload.endswith(b"\r\n")

    attributes = (_ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert f"{_SEED_RELATIVE_PATH} text eol=lf" in attributes


def test_first_configuration_retains_p2_reader_until_authority_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = first_config.PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE
    c1 = SimpleNamespace(
        machine_authority_id=first_config._MACHINE_AUTHORITY_ID,
        authority_epoch_id=first_config._AUTHORITY_EPOCH_ID,
        approved_account_sid=profile.approved_trading_sid,
    )
    selected = SimpleNamespace(permit=object(), audit=object())
    reader_ref: weakref.ReferenceType[object] | None = None

    class Reader:
        def __init__(self, authority: object) -> None:
            nonlocal reader_ref
            assert authority is c1
            reader_ref = weakref.ref(self)

        def read_selected_snapshot(self, selection_id: str) -> object:
            assert selection_id == str(first_config._SELECTION_ID)
            return selected

    def validate_authority(authority: object) -> object:
        assert authority is c1
        return c1

    def load_history_seed(calendar: object) -> object:
        del calendar
        return object()

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
        validate_authority,
    )
    monkeypatch.setattr(first_config, "_require_publication_freeze", lambda: None)
    monkeypatch.setattr(first_config, "_load_history_seed", load_history_seed)
    monkeypatch.setattr(first_config, "WindowsSelectedC3SnapshotReadAuthority", Reader)
    monkeypatch.setattr(
        first_config,
        "require_selected_c3_snapshot_matches_authority",
        require_match,
    )

    with pytest.raises(_StopAfterAuthorityMatch):
        first_config.read_personal_desktop_first_paper_cycle_configuration(c1)
