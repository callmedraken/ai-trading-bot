"""Strict immutable GUI-owned runtime models; synthetic inputs only."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from pathlib import Path

import pytest

from trading_bot.gui import (
    ProductionRuntimeEvidenceInspectionService,
    RuntimeDiagnostic,
    RuntimePageState,
    RuntimePageStatus,
    unavailable_runtime_state,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/gui/runtime"


def _state():
    return ProductionRuntimeEvidenceInspectionService(
        acl=FIXTURES / "acl-provisioned.json",
        qualification=FIXTURES / "qualification-ready.json",
        session=FIXTURES / "session-executed.json",
    ).get_runtime_state()


def test_frozen_path_free_and_deterministic():
    state = _state()
    assert state.status is RuntimePageStatus.AVAILABLE
    assert unavailable_runtime_state() == unavailable_runtime_state()
    assert not hasattr(state, "path")
    with pytest.raises(FrozenInstanceError):
        state.session.status = "BLOCKED"
    assert "Path(" not in repr(state)


@pytest.mark.parametrize(
    "role,field,value",
    [
        ("acl", "runtime_sid_digest", "A" * 64),
        ("acl", "runtime_sid_digest", "a" * 65),
        ("acl", "acl_apply_attempts", -1),
        ("acl", "provider_calls", True),
        ("acl", "parent_mutations", 1_000_001),
        ("acl", "status", "PROVISIONED"),
        ("qualification", "source_head", "b" * 41),
        ("qualification", "source_tree", "G" * 40),
        ("qualification", "persisted_oauth_available", 1),
        ("qualification", "effect_counts_complete", 0),
        ("qualification", "paper_records", -1),
        ("qualification", "session_reservations", 1_000_001),
        ("qualification", "alpaca_credential_reads", False),
        ("qualification", "alpaca_http_calls", 0.0),
        ("qualification", "paper_store_write_readiness", "WRITE_READY"),
        ("session", "contract_id", "not-a-uuid"),
        ("session", "target_session", datetime(2026, 10, 12)),
        ("session", "historical_provider", "a" * 1000),
        ("session", "historical_sessions", (date(2026, 10, 9),) * 254),
        ("session", "historical_sessions", [date(2026, 10, 9)]),
        ("session", "admitted_at", datetime(2026, 10, 12)),
        ("session", "alpaca_reads", 254),
        ("session", "strategy_evaluations", 2),
        ("session", "execute_attempts", True),
        ("session", "broker_placement_count", 1),
        ("session", "paper_mutations", None),
        ("session", "effect_counts_complete", 1),
    ],
)
def test_model_rejects_unbounded_wrong_types_and_classifications(role, field, value):
    with pytest.raises((ValueError, TypeError)):
        replace(getattr(_state(), role), **{field: value})


def test_page_status_requires_closed_consistent_diagnostic_and_views():
    with pytest.raises(TypeError):
        RuntimePageState("AVAILABLE", RuntimeDiagnostic.RECORDED)
    with pytest.raises(ValueError):
        RuntimePageState(RuntimePageStatus.AVAILABLE, RuntimeDiagnostic.RECORDED)
    with pytest.raises(ValueError):
        RuntimePageState(RuntimePageStatus.AVAILABLE, RuntimeDiagnostic.INVALID)
    with pytest.raises(TypeError):
        RuntimePageState(RuntimePageStatus.ATTENTION, RuntimeDiagnostic.INVALID, acl={})
