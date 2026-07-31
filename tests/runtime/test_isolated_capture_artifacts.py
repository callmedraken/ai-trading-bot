from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.runtime.capture_attempt_authority import (
    ProviderCallDisposition,
    SecretCleanupResult,
    SnapshotTerminalVerification,
)
from trading_bot.runtime.isolated_capture_artifacts import (
    ISOLATED_CAPTURE_CHILD_OPERATION_VERSION,
    IsolatedCaptureArtifactError,
    IsolatedCaptureArtifactSyntaxError,
    IsolatedCaptureChildClassification,
    create_isolated_capture_child_result,
    parse_isolated_capture_child_request,
    parse_isolated_capture_child_result,
    reconcile_child_request,
    serialize_isolated_capture_child_request,
    serialize_isolated_capture_child_result,
)
from trading_bot.runtime.scheduled_readiness import ArtifactEvidence

from .isolated_capture_test_support import install_child_case


def test_child_request_golden_identity_and_bytes(tmp_path) -> None:
    case = install_child_case(tmp_path)
    request = replace(
        case["request"],
        allocation_path=Path("C:/reviewed/allocation.json"),
        credential_reference_path=Path("C:/reviewed/credential.json"),
        capture_configuration_path=Path("C:/reviewed/config.json"),
        snapshot_destination_path=Path("C:/capture/snapshots"),
        child_result_path=Path("C:/capture/result.json"),
    )
    payload = serialize_isolated_capture_child_request(request)

    assert str(request.child_request_id) == "7dff0b51-1be2-570e-b227-6885fe016c24"
    assert len(payload) == 2086
    assert (
        hashlib.sha256(payload).hexdigest()
        == "04a5d93444594eff1273f0f0fba87548746cef5ae20eba65787098365e5b07f7"
    )
    assert parse_isolated_capture_child_request(payload) == request


@pytest.mark.parametrize(
    "payload_mutator",
    [
        lambda payload: b"\xef\xbb\xbf" + payload,
        lambda payload: payload.replace(b'"schema_version":1', b'"schema_version":1.0'),
        lambda payload: payload.replace(
            b'"schema_version":1',
            b'"schema_version":1,"schema_version":1',
        ),
        lambda payload: payload.replace(
            b'"schema_version":1', b'"unexpected":1,"schema_version":1'
        ),
    ],
)
def test_child_request_hostile_parsing(tmp_path, payload_mutator) -> None:
    payload = install_child_case(tmp_path)["request_payload"]
    with pytest.raises(
        (IsolatedCaptureArtifactError, IsolatedCaptureArtifactSyntaxError)
    ):
        parse_isolated_capture_child_request(payload_mutator(payload))


def test_paths_are_transport_metadata_for_request_identity(tmp_path) -> None:
    case = install_child_case(tmp_path)
    request = case["request"]
    changed = replace(
        request,
        allocation_path=tmp_path / "elsewhere-allocation.json",
        credential_reference_path=tmp_path / "elsewhere-credential.json",
        capture_configuration_path=tmp_path / "elsewhere-config.json",
        snapshot_destination_path=tmp_path / "elsewhere-snapshots",
        child_result_path=tmp_path / "elsewhere-result.json",
    )

    assert changed.child_request_id == request.child_request_id


def test_exact_allocation_credential_and_configuration_reconcile(tmp_path) -> None:
    case = install_child_case(tmp_path)
    from trading_bot.cli.daily_snapshot_config import (
        load_daily_snapshot_capture_config,
    )

    configuration = load_daily_snapshot_capture_config(
        case["request"].capture_configuration_path
    )
    reconcile_child_request(
        case["request"],
        case["allocation"],
        case["credential"],
        configuration,
    )


def test_changed_attempt_is_rejected(tmp_path) -> None:
    case = install_child_case(tmp_path)
    tree = json.loads(case["request_payload"])
    tree["attempt_ordinal"] = 1
    hostile = (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()

    with pytest.raises(IsolatedCaptureArtifactError):
        parse_isolated_capture_child_request(hostile)


def test_child_result_golden_identity_bytes_and_hostile_parsing() -> None:
    exact = ArtifactEvidence(
        UUID("11111111-1111-5111-8111-111111111111"),
        "0" * 64,
        1,
    )
    result = create_isolated_capture_child_result(
        child_request=exact,
        allocation=exact,
        attempt_id=UUID("22222222-2222-5222-8222-222222222222"),
        provider_call_disposition=ProviderCallDisposition.NOT_STARTED,
        classification=IsolatedCaptureChildClassification.INTERNAL_FAILED,
        diagnostics=("CHILD_INTERNAL_FAILED",),
        http_status=None,
        provider_code=None,
        provider_request_id=None,
        native_exit_code=8,
        snapshot=None,
        snapshot_verification=SnapshotTerminalVerification.NOT_APPLICABLE,
        secret_cleanup=SecretCleanupResult.NOT_APPLICABLE,
        child_operation_version=ISOLATED_CAPTURE_CHILD_OPERATION_VERSION,
    )
    payload = serialize_isolated_capture_child_result(result)

    assert str(result.child_result_id) == ("6938ae49-771a-5a68-894f-3d729a58e3e2")
    assert len(payload) == 810
    assert hashlib.sha256(payload).hexdigest() == (
        "2cf07bf1633d88d1d8b213e8cdb5cbe8cc9c2bbdcc976fba24c22462d9dede0b"
    )
    assert parse_isolated_capture_child_result(payload) == result
    with pytest.raises(IsolatedCaptureArtifactSyntaxError):
        parse_isolated_capture_child_result(b"\xef\xbb\xbf" + payload)
