"""Pure/fake tests for the inert Architecture-98 KSP harness."""

from __future__ import annotations

import dataclasses
import json
import struct
from pathlib import Path, PureWindowsPath

import pytest

from scripts import run_p3_r1_ksp_disposable_test as harness

_GX = bytes.fromhex("6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296")
_GY = bytes.fromhex("4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5")
_NEGATED_GY = (harness._P256_P - int.from_bytes(_GY, "big")).to_bytes(32, "big")
_PUBLIC_SEC1 = b"\x04" + _GX + _GY
_SHADOW_SEC1 = b"\x04" + _GX + _NEGATED_GY


def _public_blob(x: bytes = _GX, y: bytes = _GY) -> bytes:
    return struct.pack("<II", harness.BCRYPT_ECDSA_PUBLIC_P256_MAGIC, 32) + x + y


def _valid_descriptor() -> harness.SecurityDescriptorSemantic:
    return harness.SecurityDescriptorSemantic(
        is_valid=True,
        owner_sid=harness.ADMINISTRATORS_SID,
        owner_defaulted=False,
        dacl_present=True,
        dacl_is_null=False,
        dacl_defaulted=False,
        control=(
            harness.SE_DACL_PRESENT
            | harness.SE_DACL_PROTECTED
            | harness.SE_SELF_RELATIVE
        ),
        acl_revision=harness.ACL_REVISION,
        aces=(
            harness.AceSemantic(
                harness.ACCESS_ALLOWED_ACE_TYPE,
                0,
                harness.LOCAL_SYSTEM_SID,
                harness.CRYPTO_KEY_FULL_CONTROL,
            ),
            harness.AceSemantic(
                harness.ACCESS_ALLOWED_ACE_TYPE,
                0,
                harness.ADMINISTRATORS_SID,
                harness.CRYPTO_KEY_FULL_CONTROL,
            ),
        ),
    )


def _through_preflight() -> harness.HarnessEvidence:
    return harness.append_phase_result(
        harness.HarnessEvidence(),
        harness.Phase.READ_ONLY_PREFLIGHT,
        harness.PhaseOutcome.SUCCEEDED,
    )


def _through_machine() -> harness.HarnessEvidence:
    evidence = harness.begin_machine_creation(_through_preflight())
    evidence = harness.record_machine_created(evidence)
    return harness.append_phase_result(
        evidence,
        harness.Phase.MACHINE_CREATE_AND_VALIDATE,
        harness.PhaseOutcome.SUCCEEDED,
    )


def _through_shadow() -> harness.HarnessEvidence:
    evidence = harness.begin_shadow_creation(_through_machine())
    evidence = harness.record_shadow_created(evidence)
    return harness.append_phase_result(
        evidence,
        harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF,
        harness.PhaseOutcome.SUCCEEDED,
    )


def test_frozen_test_identity_and_evidence_root() -> None:
    assert harness.TEST_CONTAINER_TEXT == "AITradingBot-P3R1-KSP-TEST-800CA51-v1"
    assert harness.FUTURE_EVIDENCE_ROOT == PureWindowsPath(
        r"F:\AI\p3-r1-ksp-disposable-test-v1"
    )
    assert harness.MACHINE_TEST_KEY.scope is harness.KeyScope.LOCAL_MACHINE
    assert harness.CURRENT_USER_SHADOW_KEY.scope is harness.KeyScope.CURRENT_USER
    assert (
        harness.CURRENT_USER_SHADOW_KEY.operator_sid
        == harness.ELEVATED_TEST_OPERATOR_SID
    )
    assert (
        harness.MACHINE_TEST_KEY.container == harness.CURRENT_USER_SHADOW_KEY.container
    )


@pytest.mark.parametrize(
    "candidate",
    [
        harness.PRODUCTION_CONTAINER_TEXT,
        harness.PRODUCTION_CONTAINER_TEXT.upper(),
        "AITradingBotP3R1Recoveryv1",
        harness.PRODUCTION_CONTAINER_TEXT + "-alias",
    ],
)
def test_production_container_equivalence_is_rejected(candidate: str) -> None:
    with pytest.raises(harness.HarnessContractError):
        harness.validate_test_container(candidate)


def test_no_caller_selected_name_or_root_is_accepted() -> None:
    with pytest.raises(harness.HarnessContractError):
        harness.validate_test_container(harness.TEST_CONTAINER_TEXT + "-other")
    with pytest.raises(harness.HarnessContractError):
        harness.validate_evidence_root(PureWindowsPath(r"F:\AI\caller-selected"))
    with pytest.raises(harness.HarnessContractError):
        harness.validate_evidence_root(PureWindowsPath(r"F:\AITradingBot\Paper\x"))


def test_default_cli_is_description_only(monkeypatch, capsys) -> None:
    called = False

    def forbidden_load():
        nonlocal called
        called = True
        raise AssertionError("native binding load was reached")

    monkeypatch.setattr(
        harness.WindowsNativeBindings,
        "load_for_authorized_execution",
        forbidden_load,
    )
    assert harness.main([]) == 0
    description = json.loads(capsys.readouterr().out)
    assert description["native_effect_execution_authorized"] is False
    assert description["test_container"] == harness.TEST_CONTAINER_TEXT
    assert not called


def test_unknown_execution_cli_option_is_not_exposed() -> None:
    with pytest.raises(SystemExit):
        harness.main(["--execute-native"])


def test_native_gate_precedes_dll_load(monkeypatch) -> None:
    loaded: list[str] = []

    def forbidden_win_dll(name: str, **_kwargs):
        loaded.append(name)
        raise AssertionError("WinDLL load was reached")

    monkeypatch.setattr(harness.ctypes, "WinDLL", forbidden_win_dll)
    with pytest.raises(harness.NativeExecutionDisabled):
        harness.WindowsNativeBindings.load_for_authorized_execution()
    assert loaded == []


def test_native_phase_gate_precedes_fake_effect_call() -> None:
    class FakeOperations:
        called = False

        def execute(self, phase, evidence):
            self.called = True
            return evidence

    operations = FakeOperations()
    with pytest.raises(harness.NativeExecutionDisabled):
        harness.execute_native_phase(
            harness.Phase.READ_ONLY_PREFLIGHT,
            harness.HarnessEvidence(),
            operations,
        )
    assert not operations.called


def test_required_typed_native_surface_excludes_cleanup() -> None:
    assert harness.NCRYPT_REQUIRED_FUNCTIONS == {
        "NCryptOpenStorageProvider",
        "NCryptCreatePersistedKey",
        "NCryptOpenKey",
        "NCryptSetProperty",
        "NCryptGetProperty",
        "NCryptFinalizeKey",
        "NCryptExportKey",
        "NCryptSignHash",
        "NCryptFreeObject",
    }
    assert "NCryptDeleteKey" not in harness.NCRYPT_REQUIRED_FUNCTIONS


def test_architecture_98_numeric_and_property_contract_is_exact() -> None:
    assert harness.NCRYPT_MACHINE_CREATE_FLAGS == 0x20
    assert harness.NCRYPT_MACHINE_REOPEN_FLAGS == 0x60
    assert harness.NCRYPT_CURRENT_USER_CREATE_FLAGS == 0
    assert harness.NCRYPT_CURRENT_USER_REOPEN_FLAGS == 0x40
    assert harness.NCRYPT_PROPERTY_SET_FLAGS == 0x80000040
    assert harness.NCRYPT_PROPERTY_GET_FLAGS == 0x40
    assert harness.NCRYPT_SECURITY_SET_FLAGS == 0x80000045
    assert harness.NCRYPT_SECURITY_GET_FLAGS == 0x45
    assert harness.NCRYPT_ALLOW_SIGNING_FLAG == 0x2
    assert harness.NCRYPT_EXPORT_POLICY_NONE == 0
    assert harness.CRYPTO_KEY_FULL_CONTROL == 0x001F019B
    assert harness.NCRYPT_SECURITY_DESCR_PROPERTY == "Security Descr"
    assert harness.NCRYPT_SECURITY_DESCR_SUPPORT_PROPERTY == "Security Descr Support"


def test_every_security_status_requires_explicit_success() -> None:
    assert harness.check_security_status("NCryptOpenKey", 0) is None
    with pytest.raises(harness.SecurityStatusError, match="0x80090016"):
        harness.check_security_status("NCryptOpenKey", -2146893802)
    with pytest.raises(TypeError):
        harness.check_security_status("NCryptOpenKey", True)


def test_public_blob_normalizes_to_exact_sec1() -> None:
    assert harness.normalize_ecc_public_blob(_public_blob()) == _PUBLIC_SEC1


@pytest.mark.parametrize(
    "blob",
    [
        struct.pack("<II", 0, 32) + _GX + _GY,
        struct.pack("<II", harness.BCRYPT_ECDSA_PUBLIC_P256_MAGIC, 31) + _GX + _GY,
        _public_blob()[:-1],
        _public_blob() + b"\x00",
        struct.pack("<II", harness.BCRYPT_ECDSA_PUBLIC_P256_MAGIC, 32)
        + (b"\xff" * 32)
        + _GY,
        struct.pack("<II", harness.BCRYPT_ECDSA_PUBLIC_P256_MAGIC, 32)
        + _GX
        + (b"\x00" * 32),
    ],
)
def test_public_blob_rejects_wrong_curve_or_shape(blob: bytes) -> None:
    with pytest.raises(harness.HarnessContractError):
        harness.normalize_ecc_public_blob(blob)


def test_security_descriptor_accepts_semantic_ace_reordering() -> None:
    descriptor = _valid_descriptor()
    normal = harness.verify_security_descriptor(descriptor)
    reversed_descriptor = dataclasses.replace(
        descriptor, aces=tuple(reversed(descriptor.aces))
    )
    assert harness.verify_security_descriptor(reversed_descriptor) == normal


def _descriptor_rejections() -> list[harness.SecurityDescriptorSemantic]:
    descriptor = _valid_descriptor()
    system, administrators = descriptor.aces
    return [
        dataclasses.replace(descriptor, is_valid=False),
        dataclasses.replace(descriptor, malformed=True),
        dataclasses.replace(descriptor, trailing_bytes=True),
        dataclasses.replace(descriptor, owner_sid=harness.LOCAL_SYSTEM_SID),
        dataclasses.replace(descriptor, owner_defaulted=True),
        dataclasses.replace(descriptor, dacl_present=False),
        dataclasses.replace(descriptor, dacl_is_null=True),
        dataclasses.replace(descriptor, dacl_defaulted=True),
        dataclasses.replace(
            descriptor, control=descriptor.control & ~harness.SE_DACL_PROTECTED
        ),
        dataclasses.replace(
            descriptor, control=descriptor.control | harness.SE_DACL_AUTO_INHERITED
        ),
        dataclasses.replace(descriptor, control=descriptor.control | 0x0010),
        dataclasses.replace(descriptor, acl_revision=3),
        dataclasses.replace(descriptor, aces=()),
        dataclasses.replace(descriptor, aces=(system,)),
        dataclasses.replace(descriptor, aces=(system, administrators, system)),
        dataclasses.replace(descriptor, aces=(system, system)),
        dataclasses.replace(
            descriptor,
            aces=(dataclasses.replace(system, ace_type=1), administrators),
        ),
        dataclasses.replace(
            descriptor,
            aces=(dataclasses.replace(system, ace_flags=0x10), administrators),
        ),
        dataclasses.replace(
            descriptor,
            aces=(dataclasses.replace(system, sid=harness.TRADING_SID), administrators),
        ),
        dataclasses.replace(
            descriptor,
            aces=(
                dataclasses.replace(system, sid=harness.ELEVATED_TEST_OPERATOR_SID),
                administrators,
            ),
        ),
        dataclasses.replace(
            descriptor,
            aces=(dataclasses.replace(system, access_mask=0x10000000), administrators),
        ),
        dataclasses.replace(
            descriptor,
            aces=(
                dataclasses.replace(system, structurally_valid=False),
                administrators,
            ),
        ),
        dataclasses.replace(
            descriptor,
            aces=(dataclasses.replace(system, trailing_bytes=True), administrators),
        ),
    ]


@pytest.mark.parametrize("descriptor", _descriptor_rejections())
def test_security_descriptor_rejects_unexpected_state(
    descriptor: harness.SecurityDescriptorSemantic,
) -> None:
    with pytest.raises(harness.HarnessContractError):
        harness.verify_security_descriptor(descriptor)


def test_scope_proof_requires_distinct_scope_qualified_identities() -> None:
    machine = harness.KeyMetadata(
        harness.MACHINE_TEST_KEY,
        harness.NCRYPT_KEY_TYPE_MACHINE,
        harness.ALGORITHM_NAME,
        harness.ALGORITHM_GROUP,
        harness.KEY_LENGTH_BITS,
        _PUBLIC_SEC1,
    )
    shadow = harness.KeyMetadata(
        harness.CURRENT_USER_SHADOW_KEY,
        0,
        harness.ALGORITHM_NAME,
        harness.ALGORITHM_GROUP,
        harness.KEY_LENGTH_BITS,
        _SHADOW_SEC1,
    )
    assert harness.verify_scope_non_substitution(machine, shadow) == (
        _PUBLIC_SEC1,
        _SHADOW_SEC1,
    )
    with pytest.raises(harness.HarnessContractError):
        harness.verify_scope_non_substitution(
            machine, dataclasses.replace(shadow, public_sec1=_PUBLIC_SEC1)
        )
    with pytest.raises(harness.HarnessContractError):
        harness.verify_scope_non_substitution(
            machine,
            dataclasses.replace(shadow, key_type=harness.NCRYPT_MACHINE_KEY_FLAG),
        )


def test_machine_creation_failure_makes_shadow_unreachable_and_retires_name() -> None:
    evidence = harness.begin_machine_creation(_through_preflight())
    evidence = harness.append_phase_result(
        evidence,
        harness.Phase.MACHINE_CREATE_AND_VALIDATE,
        harness.PhaseOutcome.UNCERTAIN,
    )
    assert evidence.lifecycle.machine_creation_attempted
    assert not evidence.lifecycle.machine_created
    assert evidence.lifecycle.test_name_retired
    with pytest.raises(harness.HarnessContractError):
        harness.begin_shadow_creation(evidence)


def test_shadow_failure_retains_machine_and_is_terminal() -> None:
    evidence = harness.begin_shadow_creation(_through_machine())
    evidence = harness.append_phase_result(
        evidence,
        harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF,
        harness.PhaseOutcome.FAILED,
    )
    assert evidence.lifecycle.machine_created
    assert evidence.lifecycle.shadow_creation_attempted
    assert not evidence.lifecycle.shadow_created
    with pytest.raises(harness.HarnessContractError):
        harness.append_phase_result(
            evidence,
            harness.Phase.ELEVATED_MACHINE_EFFECT_TEST,
            harness.PhaseOutcome.SUCCEEDED,
        )


def test_successful_scope_phase_retains_both_keys_and_retires_name() -> None:
    evidence = _through_shadow()
    assert evidence.lifecycle == harness.LifecycleEvidence(
        machine_creation_attempted=True,
        machine_created=True,
        shadow_creation_attempted=True,
        shadow_created=True,
        test_name_retired=True,
    )


@pytest.mark.parametrize(
    "lifecycle",
    [
        harness.LifecycleEvidence(machine_created=True),
        harness.LifecycleEvidence(shadow_creation_attempted=True),
        harness.LifecycleEvidence(shadow_created=True),
        harness.LifecycleEvidence(machine_creation_attempted=True),
    ],
)
def test_invalid_lifecycle_combinations_fail_closed(
    lifecycle: harness.LifecycleEvidence,
) -> None:
    with pytest.raises(harness.HarnessContractError):
        harness.validate_lifecycle(lifecycle)


def test_phase_order_and_retained_digest_chain_are_mandatory() -> None:
    with pytest.raises(harness.HarnessContractError):
        harness.append_phase_result(
            harness.HarnessEvidence(),
            harness.Phase.MACHINE_CREATE_AND_VALIDATE,
            harness.PhaseOutcome.SUCCEEDED,
        )
    evidence = _through_shadow()
    first = evidence.phases[0]
    tampered = dataclasses.replace(
        evidence,
        phases=(
            dataclasses.replace(first, record_sha256="f" * 64),
            *evidence.phases[1:],
        ),
    )
    with pytest.raises(harness.HarnessContractError):
        harness.validate_harness_evidence(tampered)


def test_ordinary_nonadmin_phase_remains_fail_closed() -> None:
    assert harness.ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED is True
    assert harness.ORDINARY_NONADMIN_TEST_SID is None
    evidence = harness.append_phase_result(
        _through_shadow(),
        harness.Phase.ELEVATED_MACHINE_EFFECT_TEST,
        harness.PhaseOutcome.SUCCEEDED,
    )
    evidence = harness.append_phase_result(
        evidence,
        harness.Phase.TRADING_DENIAL,
        harness.PhaseOutcome.SUCCEEDED,
    )
    with pytest.raises(harness.HarnessContractError):
        harness.append_phase_result(
            evidence,
            harness.Phase.ORDINARY_NONADMIN_DENIAL,
            harness.PhaseOutcome.SUCCEEDED,
        )


def test_signing_requires_scope_proof_and_machine_identity() -> None:
    with pytest.raises(harness.HarnessContractError):
        harness.begin_test_signature(_through_machine(), harness.MACHINE_TEST_KEY)
    with pytest.raises(harness.HarnessContractError):
        harness.begin_test_signature(_through_shadow(), harness.CURRENT_USER_SHADOW_KEY)


def test_single_signing_attempt_is_consumed_before_outcome() -> None:
    evidence = harness.begin_test_signature(_through_shadow(), harness.MACHINE_TEST_KEY)
    assert evidence.signature_attempt_count == 1
    assert evidence.signature_outcome is harness.SignatureOutcome.ATTEMPTED_UNCERTAIN
    with pytest.raises(harness.HarnessContractError):
        harness.begin_test_signature(evidence, harness.MACHINE_TEST_KEY)
    completed = harness.record_test_signature_outcome(
        evidence, harness.SignatureOutcome.SUCCEEDED
    )
    with pytest.raises(harness.HarnessContractError):
        harness.begin_test_signature(completed, harness.MACHINE_TEST_KEY)


def test_private_export_probe_routes_only_to_machine_and_never_retries() -> None:
    evidence = _through_shadow()
    with pytest.raises(harness.HarnessContractError):
        harness.begin_private_export_denial_probe(
            evidence,
            harness.CURRENT_USER_SHADOW_KEY,
            harness.PrivateExportProbe.ECC_PRIVATE,
        )
    updated = harness.begin_private_export_denial_probe(
        evidence,
        harness.MACHINE_TEST_KEY,
        harness.PrivateExportProbe.ECC_PRIVATE,
    )
    with pytest.raises(harness.HarnessContractError):
        harness.begin_private_export_denial_probe(
            updated,
            harness.MACHINE_TEST_KEY,
            harness.PrivateExportProbe.ECC_PRIVATE,
        )


def test_production_identity_cannot_reach_sign_or_export_gate() -> None:
    production = harness.KeyIdentity(
        harness.PROVIDER_NAME,
        harness.KeyScope.LOCAL_MACHINE,
        harness.PRODUCTION_CONTAINER_TEXT,
    )
    with pytest.raises(harness.HarnessContractError):
        harness.begin_test_signature(_through_shadow(), production)
    with pytest.raises(harness.HarnessContractError):
        harness.begin_private_export_denial_probe(
            _through_shadow(), production, harness.PrivateExportProbe.PKCS8_PRIVATE
        )


def test_evidence_is_canonical_sanitized_and_create_new(tmp_path: Path) -> None:
    evidence = _through_shadow()
    encoded = harness.canonical_evidence_bytes(evidence)
    assert encoded.endswith(b"\n")
    decoded = json.loads(encoded)
    assert decoded["test_container"] == harness.TEST_CONTAINER_TEXT
    assert "handle" not in encoded.decode("ascii").casefold()
    assert "credential" not in encoded.decode("ascii").casefold()
    destination = harness.publish_test_evidence_create_new(evidence, tmp_path)
    assert destination.read_bytes() == encoded
    with pytest.raises(FileExistsError):
        harness.publish_test_evidence_create_new(evidence, tmp_path)


def test_test_publisher_rejects_future_evidence_root_without_creation() -> None:
    with pytest.raises(harness.HarnessContractError):
        harness.publish_test_evidence_create_new(
            harness.HarnessEvidence(), Path(str(harness.FUTURE_EVIDENCE_ROOT))
        )
