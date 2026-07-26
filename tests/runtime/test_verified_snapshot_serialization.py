"""Canonical report and offline verification tests for one snapshot paper cycle."""

import builtins
import json
import socket
from dataclasses import FrozenInstanceError
from decimal import ROUND_DOWN, ROUND_UP, localcontext
from hashlib import sha256

import pytest
from tests.market_data.daily_snapshot_test_support import accepted_result, calendar
from tests.runtime.test_verified_snapshot_execution import _prepared

from trading_bot.market_data import serialize_daily_snapshot
from trading_bot.runtime import (
    VerifiedSnapshotPaperCycleReplayError,
    VerifiedSnapshotPaperCycleReportReconciliationError,
    VerifiedSnapshotPaperCycleReportSchemaError,
    VerifiedSnapshotPaperCycleReportSyntaxError,
    VerifiedSnapshotPaperCycleReportVerificationCode,
    VerifiedSnapshotPaperCycleReportVerificationStatus,
    execute_prepared_verified_snapshot_paper_cycle,
    parse_verified_snapshot_paper_cycle_result,
    replay_verified_snapshot_paper_cycle_report,
    serialize_verified_snapshot_paper_cycle_result,
    verify_verified_snapshot_paper_cycle_report,
)


def _evidence():
    result = execute_prepared_verified_snapshot_paper_cycle(_prepared())
    report = serialize_verified_snapshot_paper_cycle_result(result)
    snapshot = accepted_result().snapshot
    assert snapshot is not None
    return result, report, serialize_daily_snapshot(snapshot)


def _tree(payload: bytes) -> dict:
    return json.loads(payload)


def _bytes(tree: dict) -> bytes:
    return (
        json.dumps(
            tree,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _set_path(tree: dict, path: tuple[object, ...], value: object) -> bytes:
    current = tree
    for item in path[:-1]:
        current = current[item]
    current[path[-1]] = value
    return _bytes(tree)


def test_golden_canonical_report_and_identity_vector() -> None:
    result, payload, _ = _evidence()

    assert len(payload) == 45100
    assert (
        sha256(payload).hexdigest()
        == "d3431faeaead1897d2471e683af4458708296c9d401d232d04b3da3e00486e1e"
    )
    assert str(result.preparation.preparation_id) == (
        "e27ef863-e551-5eaa-974d-8cd69d8f9f62"
    )
    assert str(result.runtime_result.result_id) == (
        "e8ef6132-d0ab-5fd2-9f8c-35735bf1c94b"
    )
    assert str(result.result_id) == "afac18a6-bd93-5dc0-bf9e-518751a88a33"
    assert str(result.pre_engine_state_id) == ("6bec5d03-e88e-5383-b8ec-82b2ec4db4d4")
    assert str(result.post_engine_state_id) == ("2e419511-dfa6-58a6-8f76-0d75234bf261")
    assert str(result.pre_ledger_state_id) == ("86f1871b-d351-5d2a-90de-15d45076b1c7")
    assert str(result.post_ledger_state_id) == ("5b17c830-b5cb-5d07-9994-cb3e70cf4e60")


def test_strict_parse_round_trip_and_independent_execution_bytes() -> None:
    first, first_payload, _ = _evidence()
    second, second_payload, _ = _evidence()

    assert parse_verified_snapshot_paper_cycle_result(first_payload) == first
    assert first == second
    assert first_payload == second_payload


def test_serialization_and_verification_ignore_ambient_decimal_context() -> None:
    result, payload, snapshot = _evidence()
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        low_payload = serialize_verified_snapshot_paper_cycle_result(result)
        low = verify_verified_snapshot_paper_cycle_report(
            low_payload, snapshot, calendar()
        )
        assert (context.prec, context.rounding) == (6, ROUND_DOWN)
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_UP
        high_payload = serialize_verified_snapshot_paper_cycle_result(result)
        high = verify_verified_snapshot_paper_cycle_report(
            high_payload, snapshot, calendar()
        )
        assert (context.prec, context.rounding) == (50, ROUND_UP)

    assert low_payload == high_payload == payload
    assert low == high
    assert low.result == result


@pytest.mark.parametrize(
    ("payload_factory", "error_type"),
    (
        (
            lambda payload: b"\xef\xbb\xbf" + payload,
            VerifiedSnapshotPaperCycleReportSyntaxError,
        ),
        (lambda payload: b"\xff", VerifiedSnapshotPaperCycleReportSyntaxError),
        (lambda payload: payload[:-1], VerifiedSnapshotPaperCycleReportSchemaError),
        (
            lambda payload: payload.replace(
                b'"schema_version":1',
                b'"schema_version":1,"schema_version":1',
                1,
            ),
            VerifiedSnapshotPaperCycleReportSchemaError,
        ),
        (
            lambda payload: payload.replace(
                b'"schema_version":1', b'"schema_version":true', 1
            ),
            VerifiedSnapshotPaperCycleReportSchemaError,
        ),
        (
            lambda payload: payload.replace(
                b'"schema_version":1', b'"schema_version":1.0', 1
            ),
            VerifiedSnapshotPaperCycleReportSchemaError,
        ),
        (
            lambda payload: payload[:-1] + b" trailing\n",
            VerifiedSnapshotPaperCycleReportSyntaxError,
        ),
        (
            lambda payload: payload.replace(
                b'"schema_version":1', b'"schema_version":NaN', 1
            ),
            VerifiedSnapshotPaperCycleReportSchemaError,
        ),
    ),
)
def test_strict_parser_rejects_hostile_json(payload_factory, error_type) -> None:
    _, payload, _ = _evidence()

    with pytest.raises(error_type):
        parse_verified_snapshot_paper_cycle_result(payload_factory(payload))


@pytest.mark.parametrize(
    ("path", "value", "error_type"),
    (
        (("schema_version",), 2, VerifiedSnapshotPaperCycleReportSchemaError),
        (
            ("result", "result_id"),
            "AFAC18A6-BD93-5DC0-BF9E-518751A88A33",
            VerifiedSnapshotPaperCycleReportSchemaError,
        ),
        (
            ("result", "preparation", "snapshot_audit_sha256"),
            "A" * 64,
            VerifiedSnapshotPaperCycleReportSchemaError,
        ),
        (
            ("result", "preparation", "planning_at"),
            "2025-01-06T20:01:00+00:00",
            VerifiedSnapshotPaperCycleReportSchemaError,
        ),
        (
            ("result", "preparation", "account_state", "cash"),
            "972.500",
            VerifiedSnapshotPaperCycleReportSchemaError,
        ),
        (
            ("result", "preparation", "account_state", "cash"),
            972.5,
            VerifiedSnapshotPaperCycleReportSchemaError,
        ),
    ),
)
def test_strict_parser_rejects_noncanonical_scalars(path, value, error_type) -> None:
    _, payload, _ = _evidence()

    with pytest.raises(error_type):
        parse_verified_snapshot_paper_cycle_result(
            _set_path(_tree(payload), path, value)
        )


def test_strict_parser_rejects_missing_unknown_and_noncanonical_key_order() -> None:
    _, payload, _ = _evidence()
    missing = _tree(payload)
    missing["result"].pop("status")
    unknown = _tree(payload)
    unknown["unexpected"] = 1
    retained = _tree(payload)
    reordered = (
        json.dumps(
            {
                "schema_version": retained["schema_version"],
                "result": retained["result"],
            },
            ensure_ascii=True,
            sort_keys=False,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )

    for candidate in (_bytes(missing), _bytes(unknown), reordered):
        with pytest.raises(VerifiedSnapshotPaperCycleReportSchemaError):
            parse_verified_snapshot_paper_cycle_result(candidate)


def test_strict_parse_does_not_accept_reconciled_identity_tamper() -> None:
    _, payload, _ = _evidence()
    tampered = _set_path(
        _tree(payload),
        ("result", "result_id"),
        "00000000-0000-0000-0000-000000000000",
    )

    with pytest.raises(VerifiedSnapshotPaperCycleReportReconciliationError):
        parse_verified_snapshot_paper_cycle_result(tampered)


def test_complete_offline_verification_and_replay() -> None:
    expected, report, snapshot = _evidence()

    verification = verify_verified_snapshot_paper_cycle_report(
        report,
        snapshot,
        calendar(),
        expected_report_sha256=sha256(report).hexdigest(),
        expected_report_byte_length=len(report),
    )

    assert (
        verification.status is VerifiedSnapshotPaperCycleReportVerificationStatus.PASS
    )
    assert verification.diagnostics == ()
    assert verification.result == expected
    assert replay_verified_snapshot_paper_cycle_report(verification) == expected
    with pytest.raises(FrozenInstanceError):
        verification.report_byte_length = 0  # type: ignore[misc]


def test_outer_report_hash_and_length_mismatch_are_deterministic_failures() -> None:
    _, report, snapshot = _evidence()

    verification = verify_verified_snapshot_paper_cycle_report(
        report,
        snapshot,
        calendar(),
        expected_report_sha256="0" * 64,
        expected_report_byte_length=0,
    )

    assert tuple(item.code for item in verification.diagnostics) == (
        VerifiedSnapshotPaperCycleReportVerificationCode.REPORT_BYTE_LENGTH_MISMATCH,
        VerifiedSnapshotPaperCycleReportVerificationCode.REPORT_SHA256_MISMATCH,
    )
    assert verification.result is None
    with pytest.raises(VerifiedSnapshotPaperCycleReplayError):
        replay_verified_snapshot_paper_cycle_report(verification)


def test_original_snapshot_is_required_and_linked_by_hash_length_and_id() -> None:
    _, report, snapshot = _evidence()

    verification = verify_verified_snapshot_paper_cycle_report(
        report, snapshot + b"x", calendar()
    )

    assert tuple(item.code for item in verification.diagnostics) == (
        VerifiedSnapshotPaperCycleReportVerificationCode.SNAPSHOT_LINKAGE_FAILURE,
    )
    assert verification.result is None


@pytest.mark.parametrize(
    ("path", "value", "expected_code"),
    (
        (
            ("result", "preparation", "snapshot_reference", "artifact_sha256"),
            "0" * 64,
            VerifiedSnapshotPaperCycleReportVerificationCode.SNAPSHOT_LINKAGE_FAILURE,
        ),
        (
            ("result", "preparation", "close_marks", 0, "planning_close"),
            "102.76",
            VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
        ),
        (
            ("result", "preparation", "account_state", "cash"),
            "972.51",
            VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
        ),
        (
            (
                "result",
                "preparation",
                "account_state",
                "positions",
                0,
                "quantity",
            ),
            "9",
            VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
        ),
        (
            ("result", "preparation", "target", "quantities", 0, "quantity"),
            "1",
            VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
        ),
        (
            ("result", "preparation", "target", "target_cash"),
            "984",
            VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
        ),
        (
            (
                "result",
                "preparation",
                "open_references",
                0,
                "caller_asserted_open_reference_price",
            ),
            "104",
            VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
        ),
        (
            (
                "result",
                "preparation",
                "policies",
                "fill_policy",
                "slippage_basis_points",
            ),
            "1",
            VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
        ),
        (
            ("result", "preparation", "planning_at"),
            "2025-01-06T20:02:00Z",
            VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
        ),
        (
            ("result", "preparation", "preparation_id"),
            "00000000-0000-0000-0000-000000000000",
            VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
        ),
        (
            ("result", "bootstrap_evidence", "initialization_id"),
            "00000000-0000-0000-0000-000000000000",
            VerifiedSnapshotPaperCycleReportVerificationCode.IDENTITY_STATE_RECONCILIATION_FAILURE,
        ),
        (
            (
                "result",
                "runtime_result",
                "plan",
                "trades",
                0,
                "planned_quantity",
            ),
            "9",
            VerifiedSnapshotPaperCycleReportVerificationCode.EXECUTION_REPLAY_FAILURE,
        ),
        (
            ("result", "runtime_result", "proposal_result", "result_id"),
            "00000000-0000-0000-0000-000000000000",
            VerifiedSnapshotPaperCycleReportVerificationCode.EXECUTION_REPLAY_FAILURE,
        ),
        (
            ("result", "runtime_result", "risk_result", "result_id"),
            "00000000-0000-0000-0000-000000000000",
            VerifiedSnapshotPaperCycleReportVerificationCode.EXECUTION_REPLAY_FAILURE,
        ),
        (
            ("result", "runtime_result", "order_result", "result_id"),
            "00000000-0000-0000-0000-000000000000",
            VerifiedSnapshotPaperCycleReportVerificationCode.EXECUTION_REPLAY_FAILURE,
        ),
        (
            (
                "result",
                "runtime_result",
                "fill_result",
                "evaluations",
                0,
                "fill",
                "fill_id",
            ),
            "00000000-0000-0000-0000-000000000000",
            VerifiedSnapshotPaperCycleReportVerificationCode.EXECUTION_REPLAY_FAILURE,
        ),
        (
            ("result", "runtime_result", "pre_engine_state_id"),
            "00000000-0000-0000-0000-000000000000",
            VerifiedSnapshotPaperCycleReportVerificationCode.EXECUTION_REPLAY_FAILURE,
        ),
        (
            ("result", "final_account_state", "cash"),
            "1",
            VerifiedSnapshotPaperCycleReportVerificationCode.IDENTITY_STATE_RECONCILIATION_FAILURE,
        ),
        (
            ("result", "status"),
            "NO_ACTION",
            VerifiedSnapshotPaperCycleReportVerificationCode.IDENTITY_STATE_RECONCILIATION_FAILURE,
        ),
        (
            ("result", "result_id"),
            "00000000-0000-0000-0000-000000000000",
            VerifiedSnapshotPaperCycleReportVerificationCode.IDENTITY_STATE_RECONCILIATION_FAILURE,
        ),
    ),
)
def test_independently_retained_sections_fail_exact_offline_replay(
    path, value, expected_code
) -> None:
    _, report, snapshot = _evidence()
    tampered = _set_path(_tree(report), path, value)

    verification = verify_verified_snapshot_paper_cycle_report(
        tampered, snapshot, calendar()
    )

    assert verification.result is None
    assert verification.diagnostics[-1].code is expected_code


def test_verification_invokes_execution_runtime_exactly_once(monkeypatch) -> None:
    _, report, snapshot = _evidence()
    import trading_bot.runtime.verified_snapshot_serialization as serialization

    original = serialization.execute_prepared_verified_snapshot_paper_cycle
    calls = []

    def counted(preparation):
        calls.append(preparation.preparation_id)
        return original(preparation)

    monkeypatch.setattr(
        serialization,
        "execute_prepared_verified_snapshot_paper_cycle",
        counted,
    )

    verification = verify_verified_snapshot_paper_cycle_report(
        report, snapshot, calendar()
    )

    assert verification.passed
    assert calls == [verification.result.preparation.preparation_id]


def test_verifier_never_uses_provider_network_or_filesystem(monkeypatch) -> None:
    _, report, snapshot = _evidence()

    def fail(*args, **kwargs):
        raise AssertionError("out-of-bound operation invoked")

    monkeypatch.setattr(builtins, "open", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(
        "trading_bot.market_data.AlpacaDailySnapshotProvider.fetch",
        fail,
    )

    verification = verify_verified_snapshot_paper_cycle_report(
        report, snapshot, calendar()
    )

    assert verification.passed
