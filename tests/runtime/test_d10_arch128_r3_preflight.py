from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import d10_arch128_r3_preflight as r3
from scripts import d10_protected_replacement as replacement


def test_frozen_current_s5r10_identity_matches_accepted_lineage() -> None:
    identity = replacement.NEW_IDENTITY
    assert identity.deployment_id == r3.CURRENT_DEPLOYMENT_ID
    assert identity.unsigned_attestation_sha256 == r3.CURRENT_ATTESTATION_SHA256
    assert identity.certified_source_head == r3.CURRENT_SOURCE_HEAD
    assert identity.certified_source_tree == r3.CURRENT_SOURCE_TREE
    assert identity.manifest_sha256 == r3.CURRENT_MANIFEST_SHA256
    assert identity.executable_file_count == r3.CURRENT_EXECUTABLE_FILE_COUNT
    assert identity.executable_total_bytes == r3.CURRENT_EXECUTABLE_TOTAL_BYTES
    assert identity.guard_sha256 == r3.CURRENT_GUARD_SHA256
    assert identity.guard_byte_length == r3.CURRENT_GUARD_BYTE_LENGTH


def test_r3_future_namespace_paths_are_fixed_and_distinct() -> None:
    assert r3.HISTORICAL_S5R8_RETIRED == (
        r"F:\AITradingBot\D10.retired-2fd79986-fb50-5fe4-800a-2d4aa5e7307c"
    )
    assert r3.NEW_S5R10_RETIRED == (
        r"F:\AITradingBot\D10.retired-9f3d111b-25bb-5ee4-9abf-f5215a32b826"
    )
    assert r3.NEW_STAGING == (
        r"F:\AITradingBot\D10.replacement-d2071f25-5a7c-5293-a28f-5b722c9917a2.installing"
    )
    assert len(
        {
            r3.HISTORICAL_S5R8_RETIRED.casefold(),
            r3.NEW_S5R10_RETIRED.casefold(),
            r3.NEW_STAGING.casefold(),
        }
    ) == 3


def test_reader_allowlist_extends_only_exact_arch128_absence_roots() -> None:
    for path in (
        r3.HISTORICAL_S5R8_RETIRED,
        r3.NEW_S5R10_RETIRED,
        r3.NEW_STAGING,
    ):
        assert r3.R3Reader._allowed(path, directory=None)
        assert r3.R3Reader._allowed(path, directory=True)
        assert not r3.R3Reader._allowed(path + r"\child", directory=None)
        assert not r3.R3Reader._allowed(path, directory=False)
    assert not r3.R3Reader._allowed(
        r"F:\AITradingBot\D10.replacement-attacker.installing",
        directory=None,
    )


def test_expected_scheduler_is_exact_disabled_nonrunning_halted_contract() -> None:
    expected = r3._expected_scheduler()
    assert expected["enabled"] is False
    assert expected["task_state"] == 1
    assert expected["trigger_enabled"] is True
    assert expected["trigger_start_boundary"] == "2026-09-29T01:30:00-07:00"
    assert expected["trigger_end_boundary"] == "2026-10-05T17:45:22-07:00"
    assert expected["action_path"] == r"F:\AITradingBot\runtime\python.exe"
    assert expected["action_working_directory"] == r"F:\AITradingBot\D10"
    assert expected["allow_demand_start"] is True
    assert expected["wake_to_run"] is True


def test_old_incident_lease_facts_are_frozen() -> None:
    assert r3.OLD_LEASE_SHA256 == (
        "91106d61129dc9c11e017a7ea613ba0fd82c87fd9debfc346b265c03c49a1e84"
    )
    assert r3.OLD_ACTIVATION == "2026-09-29T00:45:22.000000Z"
    assert r3.OLD_END == "2026-10-06T00:45:22.000000Z"
    assert r3.OLD_SOAK_ID == "48f14b13-aa18-5ce8-a0e0-402c867b17b6"


def test_require_signed_identity_accepts_only_current_s5r10(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = type("Observed", (), {"leases_present": (True, False, False)})()
    r3._require_signed_identity(observed)

    monkeypatch.setattr(
        replacement,
        "NEW_IDENTITY",
        replace(replacement.NEW_IDENTITY, guard_byte_length=1),
    )
    with pytest.raises(r3.R3Blocked, match="signed_s5r10_identity_drift"):
        r3._require_signed_identity(observed)


@pytest.mark.parametrize(
    "leases",
    [
        (False, False, False),
        (True, True, False),
        (True, False, True),
        (False, True, False),
    ],
)
def test_require_signed_identity_rejects_wrong_lease_namespace(leases: tuple[bool, bool, bool]) -> None:
    observed = type("Observed", (), {"leases_present": leases})()
    with pytest.raises(r3.R3Blocked, match="signed_s5r10_identity_drift"):
        r3._require_signed_identity(observed)


def test_scheduler_helper_source_is_read_only_and_fixed() -> None:
    source = r3.SCHEDULER_HELPER.read_text(encoding="utf-8")
    assert "Schedule.Service" in source
    assert "Read-FixedTask" in source
    assert "task_state" in source
    for forbidden in (
        ".Enabled =",
        "RegisterTask",
        "DeleteTask",
        "Run(",
        "Start-ScheduledTask",
        "Set-ScheduledTask",
        "Disable-ScheduledTask",
        "Enable-ScheduledTask",
    ):
        assert forbidden not in source


def test_r3_python_source_has_no_mutation_or_effect_surface() -> None:
    source = Path(r3.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "WindowsActivationLeaseBackend",
        "WindowsDeploymentBackend",
        "publish_create_only",
        "create_file(",
        "create_directory(",
        "SetFileInformationByHandle",
        "NtSetInformationFile",
        "getpass",
        "Trading password",
        "subprocess.Popen",
    ):
        assert forbidden not in source
    assert "source_launch" in source
    assert '"NOT_RUN"' in source


def test_scheduler_xml_digest_is_frozen_to_accepted_post_halt() -> None:
    assert r3.EXPECTED_SCHEDULER_XML_SHA256 == (
        "8d592a71258529fa88cd85866b0be1e91cf407d91e9acf5891a1bd82c0bf09b0"
    )
    assert len(bytes.fromhex(r3.EXPECTED_SCHEDULER_XML_SHA256)) == hashlib.sha256().digest_size
