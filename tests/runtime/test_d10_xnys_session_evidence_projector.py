from __future__ import annotations

import hashlib
import json
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from scripts import d10_xnys_session_coverage_policy as policy
from scripts import d10_xnys_session_evidence_projector as projector
from trading_bot.runtime import personal_desktop_d10_wake_evidence_log as wake_log
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10ActivationLease,
    build_activation_lease_model,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    D10OneWeekWakeEvidence,
    D10WakeOutcome,
    D10WakeStopReason,
    serialize_d10_wake_evidence,
)

EFFECTS = (
    "production_filesystem_mutation",
    "evidence_mutation",
    "scheduler_mutation",
    "source_launch",
    "provider",
    "Paper-v2",
    "broker",
    "live",
)


@pytest.fixture
def lease():
    # Synthetic model using reviewed public source identity; never a host read.
    result = build_activation_lease_model(
        deployment_id="d2071f25-5a7c-5293-a28f-5b722c9917a2",
        attestation_sha256="3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71",
        accepted_activation_utc=datetime(2026, 9, 30, 22, 7, 24, tzinfo=UTC),
        certified_source_head="0f9551e13486ef65b35a5a9633da19081571144b",
        certified_source_tree="1186e92669af100542c055368c1b72495c36bc11",
    )
    assert result.soak_id == "30e31396-9f51-57ca-a480-d2a3e9cae4a0"
    return result


@pytest.fixture
def wakes(lease):
    result = []
    for index, instant in enumerate(policy.slot_policy.expected_slots_utc()):
        completed = policy.timing.completed_xnys_session_at(instant)
        execution = policy.timing.next_xnys_execution_session(completed)
        result.append(
            D10OneWeekWakeEvidence(
                outcome=D10WakeOutcome.COMPLETED,
                stop_reason=None,
                observed_at_utc=instant,
                deployment_id=lease.deployment_id,
                attestation_sha256=lease.attestation_sha256,
                certified_source_head=lease.certified_source_head,
                certified_source_tree=lease.certified_source_tree,
                executable_file_count=307,
                soak_id=lease.soak_id,
                activation_utc=lease.accepted_activation_utc,
                end_utc=lease.end_utc,
                completed_session=completed.session_date.isoformat(),
                next_execution_session=execution.session_date.isoformat(),
                preopen_deadline_utc=policy.timing.xnys_regular_open(execution),
                capture_classification="capture-" + str(index),
                capture_selection_id="selection-" + str(index),
                capture_snapshot_id="snapshot-" + str(index),
                provider_attempt_id="attempt-" + str(index),
                provider_terminal_state="terminal-" + str(index),
                provider_call_disposition="disposition-" + str(index),
                historical_audit_classification="audit-" + str(index),
                historical_reconciled_count=index + 3,
                historical_current_decision_id="current-" + str(index),
                historical_unresolved_decision_id="historical-" + str(index),
                settlement_decision_id="settled-" + str(index),
                settlement_classification="settlement-" + str(index),
                settlement_reconciliation="settlement-recon-" + str(index),
                final_plan_id="plan-" + str(index),
                invocation_id="invocation-" + str(index),
                operation_id="operation-" + str(index),
                application_id="application-" + str(index),
                predecessor_checkpoint_id="predecessor-" + str(index),
                successor_checkpoint_id="successor-" + str(index),
                next_decision_id="next-" + str(index),
                publication_classification="publication-" + str(index),
                decision_reconciliation="decision-recon-" + str(index),
                finalized_decision_id="finalized-" + str(index),
                provider_attempts=1,
                settlement_attempts=int(index % 2 == 0),
                publication_attempts=int(index % 2 != 0),
                receipt_recovery_attempts=0,
                broker_live_calls=0,
                provider_effect_crossed=True,
                settlement_effect_crossed=index % 2 == 0,
                publication_effect_crossed=index % 2 != 0,
                all_effect_gates_closed=True,
                closed_effect_gate_count=8,
            )
        )
    return tuple(result)


def _triplet(wake, lease):
    ordinary = serialize_d10_wake_evidence(wake).encode()
    start = wake_log.D10GuardWakeStartEvidence(
        wake_log.D10_GUARD_WAKE_START_EVIDENCE_SCHEMA,
        wake.observed_at_utc,
        lease.deployment_id,
        lease.soak_id,
    ).canonical_bytes()
    acceptance = wake_log.D10GuardResultAcceptanceEvidence(
        wake_log.D10_GUARD_RESULT_ACCEPT_EVIDENCE_SCHEMA,
        wake.observed_at_utc,
        lease.deployment_id,
        lease.soak_id,
        hashlib.sha256(ordinary).hexdigest(),
    ).canonical_bytes()
    return start, ordinary, acceptance


def _log(wakes, lease):
    return b"".join(line + b"\n" for wake in wakes for line in _triplet(wake, lease))


def _safe(value):
    if type(value) is dict:
        assert all(type(key) is str for key in value)
        for item in value.values():
            _safe(item)
    elif type(value) is tuple:
        for item in value:
            _safe(item)
    else:
        assert type(value) in (str, int, bool)
        if type(value) is str:
            assert not value.startswith(("{", "["))


def _project(data, lease, *, reviewed=policy.END_UTC):
    result = projector.project(data, lease, reviewed_at_utc=reviewed)
    assert {field: result[field] for field in EFFECTS} == dict.fromkeys(
        EFFECTS, "NOT_RUN"
    )
    assert result["d10_accepted"] is False
    assert result["broker_paper_authorized"] is False
    assert result["operator_decision_required"] is True
    _safe(result)
    return result


def _blocked(data, lease, reason, **kwargs):
    result = _project(data, lease, **kwargs)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == reason
    assert set(result) <= {
        "schema",
        "status",
        "category",
        "reason",
        "policy_reason",
        "d10_accepted",
        "broker_paper_authorized",
        "operator_decision_required",
        *EFFECTS,
    }
    return result


def test_canonical_seven_triplets_pass_and_exact_output(wakes, lease):
    data = _log(wakes, lease)
    result = _project(data, lease)
    assert result == {
        "schema": "d10-xnys-session-evidence-projector/v1",
        "status": "PASS",
        "category": "ELIGIBLE_XNYS_SESSION_COVERAGE",
        "wake_count": 7,
        "record_count": 21,
        "input_log_byte_length": len(data),
        "input_log_sha256": hashlib.sha256(data).hexdigest(),
        "policy": policy.analyze(wakes, reviewed_at_utc=policy.END_UTC),
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
        **dict.fromkeys(EFFECTS, "NOT_RUN"),
    }
    assert _project(data, lease) == result


def test_duplicate_wake_not_deduplicated(wakes, lease, monkeypatch):
    expanded = (*wakes[:3], wakes[2], *wakes[3:])
    received = []
    original = policy.analyze

    def analyze(values, *, reviewed_at_utc):
        received.append(values)
        return original(values, reviewed_at_utc=reviewed_at_utc)

    monkeypatch.setattr(policy, "analyze", analyze)
    result = _project(_log(expanded, lease), lease)
    assert result["status"] == "PASS"
    assert result["wake_count"] == 8
    assert result["record_count"] == 24
    assert received == [expanded]


def test_summary_once_first_parser_per_wake_and_policy_once(wakes, lease, monkeypatch):
    data = _log(wakes, lease)
    events = []
    summarizer = wake_log.summarize_d10_wake_evidence_log
    parser = wake_log.parse_persisted_d10_wake_record
    analyzer = policy.analyze
    in_summary = False

    def summarize(payload, supplied_lease):
        nonlocal in_summary
        assert events == []
        assert payload is data and supplied_lease is lease
        events.append("summary")
        in_summary = True
        result = summarizer(payload, supplied_lease)
        in_summary = False
        events.append("validated")
        return result

    def parse(payload, supplied_lease):
        if not in_summary:
            events.append(payload)
        return parser(payload, supplied_lease)

    def analyze(values, *, reviewed_at_utc):
        events.append("policy")
        assert values == wakes
        assert reviewed_at_utc is policy.END_UTC
        return analyzer(values, reviewed_at_utc=reviewed_at_utc)

    monkeypatch.setattr(wake_log, "summarize_d10_wake_evidence_log", summarize)
    monkeypatch.setattr(wake_log, "parse_persisted_d10_wake_record", parse)
    monkeypatch.setattr(policy, "analyze", analyze)
    assert _project(data, lease)["status"] == "PASS"
    assert events == [
        "summary",
        "validated",
        *(serialize_d10_wake_evidence(wake).encode() for wake in wakes),
        "policy",
    ]


def test_every_model_field_reconstructed_and_roundtrips(wakes, lease, monkeypatch):
    original = policy.analyze
    received = []

    def analyze(values, *, reviewed_at_utc):
        received.append(values)
        for reconstructed, expected in zip(values, wakes, strict=True):
            assert type(reconstructed) is D10OneWeekWakeEvidence
            assert {
                field.name: getattr(reconstructed, field.name)
                for field in fields(D10OneWeekWakeEvidence)
            } == {
                field.name: getattr(expected, field.name)
                for field in fields(D10OneWeekWakeEvidence)
            }
            assert serialize_d10_wake_evidence(
                reconstructed
            ) == serialize_d10_wake_evidence(expected)
            assert reconstructed.activation_utc is lease.accepted_activation_utc
            assert reconstructed.end_utc is lease.end_utc
        return original(values, reviewed_at_utc=reviewed_at_utc)

    monkeypatch.setattr(policy, "analyze", analyze)
    assert _project(_log(wakes, lease), lease)["status"] == "PASS"
    assert received == [wakes]


def test_none_optional_fields_zero_attempts_and_no_action(wakes, lease):
    optional = {
        field.name: None
        for field in fields(D10OneWeekWakeEvidence)
        if field.name
        in (
            "capture_classification",
            "capture_selection_id",
            "capture_snapshot_id",
            "provider_attempt_id",
            "provider_terminal_state",
            "provider_call_disposition",
            "historical_audit_classification",
            "historical_current_decision_id",
            "historical_unresolved_decision_id",
            "settlement_decision_id",
            "settlement_classification",
            "settlement_reconciliation",
            "final_plan_id",
            "invocation_id",
            "operation_id",
            "application_id",
            "predecessor_checkpoint_id",
            "successor_checkpoint_id",
            "next_decision_id",
            "publication_classification",
            "decision_reconciliation",
            "finalized_decision_id",
        )
    }
    values = tuple(
        replace(
            wake,
            **optional,
            outcome=D10WakeOutcome.NO_ACTION,
            historical_reconciled_count=0,
            provider_attempts=0,
            settlement_attempts=0,
            publication_attempts=0,
            provider_effect_crossed=False,
            settlement_effect_crossed=False,
            publication_effect_crossed=False,
        )
        for wake in wakes
    )
    assert _project(_log(values, lease), lease)["status"] == "PASS"


@pytest.mark.parametrize("value", (None, {}, object(), "lease"))
def test_wrong_lease_type(wakes, lease, value):
    _blocked(_log(wakes, lease), value, "lease_invalid")


def test_lease_subclass_rejected(wakes, lease):
    class SubLease(D10ActivationLease):
        pass

    value = SubLease(
        **{field.name: getattr(lease, field.name) for field in fields(lease)}
    )
    _blocked(_log(wakes, lease), value, "lease_invalid")


@pytest.mark.parametrize(
    "field,value",
    (
        ("deployment_id", "11111111-1111-5111-8111-111111111111"),
        ("attestation_sha256", "a" * 64),
        ("accepted_activation_utc", policy.ACTIVATION_UTC + timedelta(seconds=1)),
        ("certified_source_head", "a" * 40),
        ("certified_source_tree", "b" * 40),
    ),
)
def test_valid_foreign_lease_identity_blocks(wakes, lease, field, value):
    facts = {
        name: getattr(lease, name)
        for name in (
            "deployment_id",
            "attestation_sha256",
            "accepted_activation_utc",
            "certified_source_head",
            "certified_source_tree",
        )
    }
    facts[field] = value
    foreign = build_activation_lease_model(**facts)
    _blocked(_log(wakes, lease), foreign, "lease_identity_mismatch")


@pytest.mark.parametrize(
    "field,value",
    (
        ("soak_id", "11111111-1111-5111-8111-111111111111"),
        ("end_utc", policy.END_UTC + timedelta(seconds=1)),
        ("accepted_activation_utc", policy.ACTIVATION_UTC.replace(tzinfo=None)),
        ("schema", "foreign"),
    ),
)
def test_frozen_lease_revalidated(wakes, lease, field, value):
    object.__setattr__(lease, field, value)
    _blocked(b"", lease, "lease_invalid")


@pytest.mark.parametrize("value", (None, "", {}, bytearray(b""), memoryview(b"")))
def test_exact_bytes_required(lease, value):
    _blocked(value, lease, "input_invalid")


def test_bytes_subclass_rejected(lease):
    class SubBytes(bytes):
        pass

    _blocked(SubBytes(b""), lease, "input_invalid")


@pytest.mark.parametrize("count", (0, 1, 6))
def test_insufficient_complete_wakes_blocks(wakes, lease, count):
    _blocked(_log(wakes[:count], lease), lease, "durable_log_incomplete")


@pytest.mark.parametrize(
    "damage",
    (
        "partial",
        "malformed",
        "duplicate_key",
        "wrong_schema",
        "acceptance_hash",
        "oversized_record",
        "blank_line",
        "backward_order",
    ),
)
def test_log_invalid_through_architecture127(wakes, lease, damage):
    data = _log(wakes, lease)
    lines = data[:-1].split(b"\n")
    if damage == "partial":
        data = data[:-1]
    elif damage == "malformed":
        lines[1] = b"{"
    elif damage == "duplicate_key":
        lines[1] = lines[1].replace(
            b'{"budgets":', b'{"outcome":"NO_ACTION","budgets":', 1
        )
    elif damage == "wrong_schema":
        lines[1] = lines[1].replace(
            b"personal-desktop-d10-wake-evidence/v1", b"foreign"
        )
    elif damage == "acceptance_hash":
        value = json.loads(lines[2])
        value["result_sha256"] = "0" * 64
        lines[2] = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    elif damage == "oversized_record":
        lines[1] += b" " * 16384
    elif damage == "blank_line":
        lines.insert(3, b"")
    elif damage == "backward_order":
        lines = [*lines[3:6], *lines[:3], *lines[6:]]
    if damage != "partial":
        data = b"\n".join(lines) + b"\n"
    _blocked(data, lease, "durable_log_invalid")


@pytest.mark.parametrize("kind", ("start", "unaccepted", "stopped", "guard"))
def test_terminal_states_never_skipped(wakes, lease, kind):
    prefix = _log(wakes[:6], lease)
    start, ordinary, _ = _triplet(wakes[6], lease)
    if kind == "start":
        suffix = start + b"\n"
    elif kind == "unaccepted":
        suffix = start + b"\n" + ordinary + b"\n"
    elif kind == "stopped":
        stopped = replace(
            wakes[6],
            outcome=D10WakeOutcome.STOPPED,
            stop_reason=D10WakeStopReason.BLOCKED,
        )
        suffix = start + b"\n" + serialize_d10_wake_evidence(stopped).encode() + b"\n"
    else:
        terminal = wake_log.D10GuardTerminalEvidence(
            wake_log.D10_GUARD_TERMINAL_EVIDENCE_SCHEMA,
            wake_log.D10GuardTerminalReason.CHILD_OUTPUT_INVALID,
            wakes[6].observed_at_utc,
            lease.deployment_id,
            lease.soak_id,
        )
        suffix = start + b"\n" + terminal.canonical_bytes() + b"\n"
    _blocked(prefix + suffix, lease, "durable_log_terminal")


def test_summarizer_exception_does_not_extract_or_delegate(wakes, lease, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("private unbounded detail")

    def forbidden(*args, **kwargs):
        pytest.fail("unvalidated payload extracted or delegated")

    monkeypatch.setattr(wake_log, "summarize_d10_wake_evidence_log", fail)
    monkeypatch.setattr(wake_log, "parse_persisted_d10_wake_record", forbidden)
    monkeypatch.setattr(projector.json, "loads", forbidden)
    monkeypatch.setattr(policy, "analyze", forbidden)
    _blocked(b"untrusted", lease, "durable_log_invalid")


@pytest.mark.parametrize(
    "change",
    (
        {"record_count": 20},
        {"wake_count": 8, "record_count": 24},
    ),
)
def test_nontriplet_summary_or_line_count_blocks(wakes, lease, monkeypatch, change):
    data = _log(wakes, lease)
    summary = replace(wake_log.summarize_d10_wake_evidence_log(data, lease), **change)
    monkeypatch.setattr(wake_log, "summarize_d10_wake_evidence_log", lambda *_: summary)
    _blocked(data, lease, "durable_log_shape_invalid")


@pytest.mark.parametrize("summary", (None, {}, object()))
def test_invalid_summary_type_blocks(lease, monkeypatch, summary):
    monkeypatch.setattr(wake_log, "summarize_d10_wake_evidence_log", lambda *_: summary)
    _blocked(b"", lease, "durable_log_shape_invalid")


def test_ordinary_parse_exception_blocks_without_decode(wakes, lease, monkeypatch):
    data = _log(wakes, lease)
    summary = wake_log.summarize_d10_wake_evidence_log(data, lease)
    monkeypatch.setattr(wake_log, "summarize_d10_wake_evidence_log", lambda *_: summary)
    calls = []

    def fail(*args):
        calls.append(args)
        raise ValueError("private ordinary failure")

    monkeypatch.setattr(wake_log, "parse_persisted_d10_wake_record", fail)
    monkeypatch.setattr(projector, "_reconstruct", lambda *_: pytest.fail("decode ran"))
    _blocked(data, lease, "ordinary_record_invalid")
    assert len(calls) == 1


def test_invalid_reconstructed_model_blocks(wakes, lease, monkeypatch):
    data = _log(wakes, lease)

    def reject(self):
        raise ValueError("private reconstruction detail")

    monkeypatch.setattr(D10OneWeekWakeEvidence, "__post_init__", reject)
    _blocked(data, lease, "wake_projection_invalid")


@pytest.mark.parametrize(
    "deadline",
    (
        "2026-10-01T13:30:00+00:00",
        "2026-10-01T13:30:00.000000Z",
        "2026-10-01T13:30:00+01:00",
        "not-a-time",
        42,
    ),
)
def test_malformed_optional_deadline_arch127_blocks(wakes, lease, deadline):
    lines = list(_triplet(wakes[0], lease))
    value = json.loads(lines[1])
    value["session"]["preopen_deadline_utc"] = deadline
    lines[1] = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    _blocked(
        b"\n".join(lines) + b"\n" + _log(wakes[1:], lease), lease, "durable_log_invalid"
    )


@pytest.mark.parametrize(
    "value",
    (
        "2026-10-01T13:30:00+00:00",
        "2026-10-01T13:30:00.000000Z",
        "2026-10-01T13:30:00",
        "2026-10-01T13:30:00+01:00",
        "bad",
        12,
    ),
)
def test_projection_requires_canonical_utc_deadline(value):
    with pytest.raises(ValueError):
        projector._wake_deadline(value)


def test_optional_deadline_projection_keeps_precision():
    assert projector._wake_deadline(None) is None
    assert projector._wake_deadline("2026-10-01T13:30:00.123456Z") == datetime(
        2026, 10, 1, 13, 30, 0, 123456, tzinfo=UTC
    )


def test_optional_missing_deadline_delegates_bounded_policy_block(wakes, lease):
    values = (replace(wakes[0], preopen_deadline_utc=None), *wakes[1:])
    result = _blocked(_log(values, lease), lease, "xnys_session_policy_blocked")
    assert result["policy_reason"] == "preopen_deadline_mismatch"


def test_projection_defends_against_reversed_parser_observations(
    wakes, lease, monkeypatch
):
    data = _log(wakes, lease)
    summary = wake_log.summarize_d10_wake_evidence_log(data, lease)
    records = [
        wake_log.parse_persisted_d10_wake_record(_triplet(wake, lease)[1], lease)
        for wake in wakes
    ]
    records[0], records[1] = records[1], records[0]
    iterator = iter(records)
    monkeypatch.setattr(wake_log, "summarize_d10_wake_evidence_log", lambda *_: summary)
    monkeypatch.setattr(
        wake_log, "parse_persisted_d10_wake_record", lambda *_: next(iterator)
    )
    _blocked(data, lease, "wake_projection_order_invalid")


@pytest.mark.parametrize(
    "reviewed,reason",
    (
        (policy.END_UTC - timedelta(microseconds=1), "review_window_not_complete"),
        (None, "review_time_invalid"),
        (policy.END_UTC.replace(tzinfo=None), "review_time_invalid"),
        (
            policy.END_UTC.replace(tzinfo=timezone(timedelta(0), "OtherUTC")),
            "review_time_invalid",
        ),
    ),
)
def test_real_policy_blocked_is_bounded(wakes, lease, reviewed, reason):
    result = _blocked(
        _log(wakes, lease), lease, "xnys_session_policy_blocked", reviewed=reviewed
    )
    assert result["policy_reason"] == reason


@pytest.mark.parametrize(
    "case",
    (
        "none",
        "list",
        "missing",
        "extra",
        "status",
        "schema",
        "category",
        "reason",
        "d10_accepted",
        "broker_paper_authorized",
        "operator_decision_required",
        "wake_count",
        "executable_file_count",
        "deployment_id",
        "soak_id",
        "attestation_sha256",
        "certified_source_head",
        "certified_source_tree",
        "activation_utc",
        "end_utc",
        "reviewed_at_utc",
        "session_list",
        "session_text",
        "session_empty",
        "session_large",
        "coverage_mismatch",
        "rows_list",
        "row_missing",
        "row_extra",
        "row_session",
        "row_time",
        "row_count",
        "row_attempt",
        "row_total",
    ),
)
def test_malformed_policy_envelope_blocks(wakes, lease, monkeypatch, case):
    result = policy.analyze(wakes, reviewed_at_utc=policy.END_UTC)
    if case == "none":
        result = None
    elif case == "list":
        result = [result]
    elif case == "missing":
        del result["schema"]
    elif case == "extra":
        result["raw"] = b"private evidence"
    elif case == "status":
        result["status"] = "PASS"
    elif case in ("schema", "category"):
        result[case] = "foreign"
    elif case == "reason":
        result = {
            "schema": policy.SCHEMA,
            "status": "BLOCKED",
            "category": "ELIGIBLE_XNYS_SESSION_COVERAGE",
            "reason": "private detail",
            "d10_accepted": False,
            "broker_paper_authorized": False,
            "operator_decision_required": True,
        }
    elif case in ("d10_accepted", "broker_paper_authorized"):
        result[case] = 0
    elif case == "operator_decision_required":
        result[case] = 1
    elif case in ("wake_count", "executable_file_count"):
        result[case] = float(result[case])
    elif case in (
        "deployment_id",
        "soak_id",
        "attestation_sha256",
        "certified_source_head",
        "certified_source_tree",
        "activation_utc",
        "end_utc",
        "reviewed_at_utc",
    ):
        result[case] = "foreign"
    elif case.startswith("session_"):
        result["expected_slot_completed_sessions"] = {
            "session_list": list(result["expected_slot_completed_sessions"]),
            "session_text": ("raw-json",) * 7,
            "session_empty": (),
            "session_large": ("2026-09-30",) * 8,
        }[case]
    elif case == "coverage_mismatch":
        result["covered_completed_sessions"] = ("2026-09-30",)
    elif case == "rows_list":
        result["session_rows"] = list(result["session_rows"])
    else:
        rows = [dict(row) for row in result["session_rows"]]
        row = rows[0]
        if case == "row_missing":
            del row["preopen_deadline_utc"]
        elif case == "row_extra":
            row["raw_json"] = "{}"
        elif case == "row_session":
            row["completed_session"] = "2026-10-01"
        elif case == "row_time":
            row["preopen_deadline_utc"] = "2026-10-01T13:30:00Z"
        elif case == "row_count":
            row["wake_count"] = True
        elif case == "row_attempt":
            row["provider_attempts"] = 2
        elif case == "row_total":
            row["wake_count"] = 2
        result["session_rows"] = tuple(rows)
    monkeypatch.setattr(policy, "analyze", lambda *args, **kwargs: result)
    _blocked(_log(wakes, lease), lease, "xnys_session_policy_invalid")


def test_policy_exception_is_bounded(wakes, lease, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("private policy exception")

    monkeypatch.setattr(policy, "analyze", fail)
    _blocked(_log(wakes, lease), lease, "xnys_session_policy_invalid")


@pytest.mark.parametrize("field,value", (("all_closed", 1), ("closed_count", 8.0)))
def test_model_reconstruction_rejects_nonexact_gate_types(wakes, lease, field, value):
    # Architecture 127 accepts equality for this envelope; the model constructor
    # still must pass and rejects these nonexact types. Do not override either.
    triplets = [list(_triplet(wake, lease)) for wake in wakes]
    payload = json.loads(triplets[0][1])
    payload["final_gates"][field] = value
    ordinary = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    triplets[0][1] = ordinary
    acceptance = json.loads(triplets[0][2])
    acceptance["result_sha256"] = hashlib.sha256(ordinary).hexdigest()
    triplets[0][2] = json.dumps(
        acceptance, sort_keys=True, separators=(",", ":")
    ).encode()
    data = b"".join(line + b"\n" for triplet in triplets for line in triplet)
    assert wake_log.summarize_d10_wake_evidence_log(data, lease).wake_count == 7
    _blocked(data, lease, "wake_projection_invalid")


def test_non_model_parser_result_blocks(wakes, lease, monkeypatch):
    data = _log(wakes, lease)
    summary = wake_log.summarize_d10_wake_evidence_log(data, lease)
    monkeypatch.setattr(wake_log, "summarize_d10_wake_evidence_log", lambda *_: summary)
    monkeypatch.setattr(wake_log, "parse_persisted_d10_wake_record", lambda *_: {})
    _blocked(data, lease, "wake_projection_invalid")
