from __future__ import annotations

import ast
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts import d10_durable_wake_evidence_observe as observer
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    build_activation_lease_model,
)
from trading_bot.runtime.personal_desktop_d10_wake_evidence_log import (
    D10_GUARD_WAKE_START_EVIDENCE_SCHEMA,
    D10GuardWakeStartEvidence,
    d10_wake_evidence_path,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    D10OneWeekWakeEvidence,
    D10WakeOutcome,
    serialize_d10_wake_evidence,
)

NOW = datetime(2026, 9, 29, 8, 30, tzinfo=UTC)


def _facts():
    attestation = {
        "deployment_id": "11111111-1111-5111-8111-111111111111",
        "certified_source_head": "b" * 40,
        "certified_source_tree": "c" * 40,
    }
    attestation_sha = hashlib.sha256(
        observer.guard._canonical_json(attestation)
    ).hexdigest()
    lease = build_activation_lease_model(
        deployment_id=attestation["deployment_id"],
        attestation_sha256=attestation_sha,
        accepted_activation_utc=datetime(2026, 9, 29, 0, 45, 22, tzinfo=UTC),
        certified_source_head=attestation["certified_source_head"],
        certified_source_tree=attestation["certified_source_tree"],
    )
    start = D10GuardWakeStartEvidence(
        D10_GUARD_WAKE_START_EVIDENCE_SCHEMA,
        NOW,
        lease.deployment_id,
        lease.soak_id,
    )
    wake = D10OneWeekWakeEvidence(
        outcome=D10WakeOutcome.NO_ACTION,
        stop_reason=None,
        observed_at_utc=NOW,
        deployment_id=lease.deployment_id,
        attestation_sha256=lease.attestation_sha256,
        certified_source_head=lease.certified_source_head,
        certified_source_tree=lease.certified_source_tree,
        executable_file_count=306,
        soak_id=lease.soak_id,
        activation_utc=lease.accepted_activation_utc,
        end_utc=lease.end_utc,
    )
    evidence = (
        start.canonical_bytes()
        + b"\n"
        + serialize_d10_wake_evidence(wake).encode()
        + b"\n"
    )
    return attestation, lease, evidence


def test_observer_reports_only_exact_current_soak_sanitized_summary(monkeypatch):
    attestation, lease, evidence = _facts()
    path = str(d10_wake_evidence_path(lease))
    marker = object()

    monkeypatch.setattr(observer, "_verified_attestation", lambda native: attestation)
    monkeypatch.setattr(
        observer, "_read_activation_lease", lambda native: lease.canonical_bytes()
    )
    monkeypatch.setattr(
        observer, "_read_evidence", lambda native, model: (path, evidence)
    )

    record = observer.observe(marker)
    assert record["schema"] == observer.D10_EVIDENCE_OBSERVATION_SCHEMA
    assert record["status"] == "OBSERVED"
    assert record["deployment_id"] == lease.deployment_id
    assert record["soak_id"] == lease.soak_id
    assert record["evidence_path"] == path
    assert record["evidence_byte_length"] == len(evidence)
    assert record["record_count"] == 2
    assert record["wake_count"] == 1
    assert record["terminal"] is False
    assert record["terminal_kind"] is None
    assert record["last_outcome"] == "NO_ACTION"
    assert record["scheduler_mutation"] == "NOT_RUN"
    assert record["source_launch"] == "NOT_RUN"
    assert record["provider"] == "NOT_RUN"
    assert record["Paper-v2"] == "NOT_RUN"
    assert record["broker"] == "NOT_RUN"
    assert record["live"] == "NOT_RUN"


def test_observer_exposes_unresolved_start_only_as_terminal_summary(monkeypatch):
    attestation, lease, _evidence = _facts()
    path = str(d10_wake_evidence_path(lease))
    start = (
        D10GuardWakeStartEvidence(
            D10_GUARD_WAKE_START_EVIDENCE_SCHEMA,
            NOW,
            lease.deployment_id,
            lease.soak_id,
        ).canonical_bytes()
        + b"\n"
    )

    monkeypatch.setattr(observer, "_verified_attestation", lambda native: attestation)
    monkeypatch.setattr(
        observer, "_read_activation_lease", lambda native: lease.canonical_bytes()
    )
    monkeypatch.setattr(observer, "_read_evidence", lambda native, model: (path, start))

    record = observer.observe(object())
    assert record["record_count"] == 1
    assert record["wake_count"] == 0
    assert record["terminal"] is True
    assert record["terminal_kind"] == "WAKE_STARTED_INCOMPLETE"
    assert record["last_outcome"] is None


def test_observer_source_has_no_effect_or_discovery_surface() -> None:
    source = Path(observer.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "open_evidence_file",
        "append_exact",
        "WriteFile",
        "FlushFileBuffers",
        "subprocess",
        "RegisterTaskDefinition",
        "Start-ScheduledTask",
        "Set-ScheduledTask",
        "glob",
        "rglob",
        "listdir",
    }
    assert not any(token in source for token in forbidden)
    assert "wake-" in source
    assert "d10_wake_evidence_path" in source
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "observe"
        for node in ast.walk(tree)
    )


def test_observer_json_surface_contains_no_raw_record_bytes(monkeypatch) -> None:
    attestation, lease, evidence = _facts()
    path = str(d10_wake_evidence_path(lease))
    monkeypatch.setattr(observer, "_verified_attestation", lambda native: attestation)
    monkeypatch.setattr(
        observer, "_read_activation_lease", lambda native: lease.canonical_bytes()
    )
    monkeypatch.setattr(
        observer, "_read_evidence", lambda native, model: (path, evidence)
    )
    rendered = json.dumps(observer.observe(object()), sort_keys=True)
    assert (
        serialize_d10_wake_evidence(
            D10OneWeekWakeEvidence(
                outcome=D10WakeOutcome.NO_ACTION,
                stop_reason=None,
                observed_at_utc=NOW,
            )
        )
        not in rendered
    )
