from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from scripts import d10_arch130_r8i_d1 as d1

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("2026-10-01T08:30:09Z", "BOUNDARY_SECOND"),
        ("2026-10-01T08:30:10Z", "DEFINITE_INCIDENT_SECOND"),
        ("2026-10-01T08:30:21Z", "DEFINITE_INCIDENT_SECOND"),
        ("2026-10-01T08:30:22Z", "OUTSIDE_INCIDENT_SECONDS"),
        (None, None),
    ),
)
def test_incident_second_bucket_is_conservative(value, expected) -> None:
    assert d1._second_bucket(value) == expected


def test_incident_second_bucket_rejects_noncanonical_timestamp() -> None:
    with pytest.raises(d1.IncidentReconciliationBlocked):
        d1._second_bucket("2026-10-01T08:30:09.370767Z")


def test_decision_attribution_separates_presence_from_causality() -> None:
    c3 = {
        "selected": {
            "selection_id": "11111111-1111-1111-1111-111111111111",
            "snapshot_id": "22222222-2222-2222-2222-222222222222",
        }
    }
    decisions = {
        "incident_next_decisions": [
            {
                "current_selection_id": "11111111-1111-1111-1111-111111111111",
                "current_snapshot_id": "22222222-2222-2222-2222-222222222222",
            }
        ]
    }
    assert (
        d1._decision_attribution(c3, decisions)
        == "INCIDENT_C3_DEPENDENT_NO_PUBLICATION_TIMESTAMP"
    )


def test_decision_absence_is_only_durable_absence_fact() -> None:
    assert (
        d1._decision_attribution({"selected": None}, {"incident_next_decisions": []})
        == "NO_DURABLE_INCIDENT_NEXT_DECISION"
    )


def test_paper_attribution_preserves_missing_effect_timestamp() -> None:
    snapshot_id = "22222222-2222-2222-2222-222222222222"
    c3 = {"selected": {"snapshot_id": snapshot_id}}
    invocations = {"incident_execution_invocations": []}
    operations = {
        "transitions": [{"snapshot_id": snapshot_id}],
        "operations": [],
    }
    assert (
        d1._paper_attribution(c3, invocations, operations)
        == "INCIDENT_C3_DEPENDENT_PAPER_STATE_NO_EFFECT_TIMESTAMP"
    )


def test_invocation_dependency_is_not_promoted_to_paper_effect() -> None:
    snapshot_id = "22222222-2222-2222-2222-222222222222"
    c3 = {"selected": {"snapshot_id": snapshot_id}}
    invocations = {
        "incident_execution_invocations": [{"selected_snapshot_id": snapshot_id}]
    }
    operations = {"transitions": [], "operations": []}
    assert (
        d1._paper_attribution(c3, invocations, operations)
        == "INCIDENT_C3_DEPENDENT_INVOCATION_NO_EFFECT_TIMESTAMP"
    )


def test_highest_dependency_is_descriptive_not_causal() -> None:
    assert (
        d1._highest_dependency(
            "CONFIRMED_INCIDENT_WINDOW",
            "INCIDENT_C3_DEPENDENT_NO_PUBLICATION_TIMESTAMP",
            "INCIDENT_C3_DEPENDENT_PAPER_STATE_NO_EFFECT_TIMESTAMP",
        )
        == "PAPER_V2_DURABLE_STATE"
    )


def test_observer_source_has_no_effect_boundary() -> None:
    source = inspect.getsource(d1)
    for forbidden in (
        "run_personal_desktop_unattended_one_week_soak",
        "run_personal_desktop_unattended_market_data_capture",
        "publish_personal_desktop_unattended",
        "execute_personal_desktop",
        "open_writable_authority_sqlite_connection",
        "RegisterTask",
        "Start-ScheduledTask",
        "Stop-ScheduledTask",
        ".Enabled =",
        "subprocess.run",
        "requests.",
        "alpaca",
    ):
        assert forbidden not in source


def test_observer_declares_all_effects_closed() -> None:
    assert set(d1.CLOSED_EFFECTS) == {
        "production_filesystem_mutation",
        "evidence_mutation",
        "lease_mutation",
        "scheduler_mutation",
        "manual_task_start",
        "source_launch",
        "provider",
        "decision_publication",
        "Paper-v2",
        "broker",
        "live",
    }
    base = d1._base()
    assert all(base[field] == "NOT_RUN" for field in d1.CLOSED_EFFECTS)


def test_incident_times_and_sessions_are_frozen() -> None:
    assert d1.INCIDENT_START.isoformat() == "2026-10-01T08:30:09.370767+00:00"
    assert d1.INCIDENT_END.isoformat() == "2026-10-01T08:30:21.815609+00:00"
    completed, execution = d1._sessions()
    assert completed.session_date.isoformat() == "2026-09-30"
    assert execution.session_date.isoformat() == "2026-10-01"


def test_architecture_document_states_attribution_limit() -> None:
    text = (
        ROOT / "docs/architecture/130-d10-first-wake-incident-reconciliation.md"
    ).read_text(encoding="utf-8")
    assert "durable presence into causal authorship" in text
    assert "no trusted publication timestamp" in text
    assert "**no protected execute function**" in text


def test_tracing_paper_api_reports_only_source_owned_role(monkeypatch) -> None:
    api = object.__new__(d1._TracingPaperReadNativeApi)
    api.last_role = None

    class Spec:
        role = type("Role", (), {"value": "unattended-decisions"})()

    monkeypatch.setattr(api, "object_spec", lambda path: Spec())
    monkeypatch.setattr(
        d1.WindowsPaperReadNativeApi,
        "inspect",
        lambda self, handle, path, kind: "observed",
    )

    assert api.inspect(object(), "ignored", object()) == "observed"
    assert api.last_role == "unattended-decisions"


def test_preflight_source_exposes_only_sanitized_paper_security_diagnostic() -> None:
    source = inspect.getsource(d1.preflight)
    assert '"paper_security_diagnostic"' in source
    assert '"stage": paper_read_stage' in source
    assert '"last_role": paper_api.last_role' in source
    assert "aces" not in source
    assert "owner_sid" not in source
