from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from tests.runtime.isolated_capture_test_support import evidence
from tests.runtime.test_isolated_capture_process_and_launcher import _launcher_case

from trading_bot.runtime.capture_attempt_authority import (
    create_windows_market_data_credential_reference,
)
from trading_bot.runtime.isolated_capture_artifacts import evidence_for_payload
from trading_bot.runtime.windows_credentials import (
    CtypesWindowsCredentialNativeApi,
    WindowsCredentialManagerReader,
)
from trading_bot.runtime.windows_isolated_capture_launcher import (
    launch_isolated_capture_child,
)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="requires Windows")


@pytest.mark.skipif(
    os.environ.get("RUN_WINDOWS_ISOLATED_PROCESS_TESTS") != "1",
    reason="opt-in real CreateProcessW and Job Object test",
)
def test_real_suspended_process_job_assignment_and_exit(tmp_path: Path) -> None:
    _, base = _launcher_case(tmp_path)
    python_path = (Path(sys.base_prefix) / "python.exe").resolve()
    script_path = tmp_path / "real-child.py"
    script_path.write_text("raise SystemExit(8)\n", encoding="utf-8")
    config = replace(
        base,
        approved_python_executable=python_path,
        approved_python_executable_evidence=evidence_for_payload(
            evidence("real-python").artifact_id,
            python_path.read_bytes(),
        ),
        approved_child_script=script_path,
        approved_child_script_evidence=evidence_for_payload(
            evidence("real-child-script").artifact_id,
            script_path.read_bytes(),
        ),
    )

    execution = launch_isolated_capture_child(
        config,
        parent_environment={
            "SystemRoot": os.environ["SystemRoot"],
            "WINDIR": os.environ["WINDIR"],
        },
    )

    assert execution.native_exit_code == 8
    assert execution.resume_record is not None
    assert execution.termination_record.native_exit_code == 8


@pytest.mark.skipif(
    os.environ.get("RUN_WINDOWS_CREDENTIAL_MANAGER_TESTS") != "1",
    reason="opt-in read-only test requiring dedicated test credentials",
)
def test_real_credential_manager_reads_only_dedicated_test_targets() -> None:
    native = CtypesWindowsCredentialNativeApi()
    sid = native.current_process_sid()
    reference = create_windows_market_data_credential_reference(
        owner_account_sid=sid,
        api_key_id_target_name=(
            "AITradingBot/AlpacaMarketData/v1/integration-test/KeyId/1"
        ),
        api_secret_key_target_name=(
            "AITradingBot/AlpacaMarketData/v1/integration-test/SecretKey/1"
        ),
        credential_version="v1",
        permission_profile="test-only-no-provider-use",
        permission_attestation_evidence=evidence("integration-test-permission"),
        rotation_generation=0,
        reference_policy_version="credential-reference-v1",
    )

    with WindowsCredentialManagerReader(native).read(reference) as secrets:
        mapping = secrets.as_provider_mapping()
        assert set(mapping) == {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY"}
        assert all(mapping.values())
