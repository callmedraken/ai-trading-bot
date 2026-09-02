"""Pure/fake tests for the inert Architecture-98 KSP harness."""

from __future__ import annotations

import dataclasses
import inspect
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


def _machine_metadata() -> harness.KeyMetadata:
    return harness.KeyMetadata(
        harness.MACHINE_TEST_KEY,
        harness.NCRYPT_KEY_TYPE_MACHINE,
        harness.ALGORITHM_NAME,
        harness.ALGORITHM_GROUP,
        harness.KEY_LENGTH_BITS,
        _PUBLIC_SEC1,
    )


def _shadow_metadata() -> harness.KeyMetadata:
    return harness.KeyMetadata(
        harness.CURRENT_USER_SHADOW_KEY,
        0,
        harness.ALGORITHM_NAME,
        harness.ALGORITHM_GROUP,
        harness.KEY_LENGTH_BITS,
        _SHADOW_SEC1,
    )


def _preflight_completion() -> harness.ReadOnlyPreflightCompletion:
    return harness.ReadOnlyPreflightCompletion(
        both_scope_absence_proved=True,
        future_evidence_root_absent=True,
        provider_security_descriptor_support=True,
        elevated_operator_sid=harness.ELEVATED_TEST_OPERATOR_SID,
    )


def _machine_completion() -> harness.MachineValidationCompletion:
    return harness.MachineValidationCompletion(
        machine_metadata=_machine_metadata(),
        exact_properties_verified=True,
        security_descriptor_verified=True,
        independent_reopen_verified=True,
    )


def _shadow_completion() -> harness.ShadowScopeCompletion:
    return harness.ShadowScopeCompletion(
        machine_metadata=_machine_metadata(),
        shadow_metadata=_shadow_metadata(),
        scope_non_substitution_verified=True,
    )


def _elevated_completion() -> harness.ElevatedEffectCompletion:
    return harness.ElevatedEffectCompletion(
        signature_verified_with_machine_public=True,
        private_export_denial_matrix_verified=True,
    )


def _through_preflight() -> harness.HarnessEvidence:
    return harness.append_phase_result(
        harness.HarnessEvidence(),
        harness.Phase.READ_ONLY_PREFLIGHT,
        harness.PhaseOutcome.SUCCEEDED,
        _preflight_completion(),
    )


def _through_machine() -> harness.HarnessEvidence:
    evidence = harness.begin_machine_creation(_through_preflight())
    evidence = harness.record_machine_created(evidence)
    return harness.append_phase_result(
        evidence,
        harness.Phase.MACHINE_CREATE_AND_VALIDATE,
        harness.PhaseOutcome.SUCCEEDED,
        _machine_completion(),
    )


def _through_shadow() -> harness.HarnessEvidence:
    evidence = harness.begin_shadow_creation(_through_machine())
    evidence = harness.record_shadow_created(evidence)
    return harness.append_phase_result(
        evidence,
        harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF,
        harness.PhaseOutcome.SUCCEEDED,
        _shadow_completion(),
    )


def _through_elevated() -> harness.HarnessEvidence:
    evidence = harness.begin_test_signature(_through_shadow(), harness.MACHINE_TEST_KEY)
    evidence = harness.record_test_signature_outcome(
        evidence, harness.SignatureOutcome.SUCCEEDED
    )
    for probe in harness.PrivateExportProbe:
        evidence = harness.begin_private_export_denial_probe(
            evidence, harness.MACHINE_TEST_KEY, probe
        )
        evidence = harness.record_private_export_probe_outcome(
            evidence,
            probe,
            harness.PrivateExportProbeOutcome.DENIED_AS_REQUIRED,
        )
    return harness.append_phase_result(
        evidence,
        harness.Phase.ELEVATED_MACHINE_EFFECT_TEST,
        harness.PhaseOutcome.SUCCEEDED,
        _elevated_completion(),
    )


def _through_trading() -> harness.HarnessEvidence:
    return harness.append_phase_result(
        _through_elevated(),
        harness.Phase.TRADING_DENIAL,
        harness.PhaseOutcome.SUCCEEDED,
        harness.PrincipalDenialCompletion(
            actor_sid=harness.TRADING_SID,
            machine_open_denied=True,
            downstream_private_operations_unreachable=True,
        ),
    )


def test_frozen_test_identity_and_evidence_root() -> None:
    assert harness.HARNESS_SCHEMA_VERSION == "p3-r1-ksp-disposable-test-evidence/v2"
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


class _FakeOperations:
    def __init__(self) -> None:
        self.calls: list[harness.Phase] = []

    def execute(
        self,
        phase: harness.Phase,
        evidence: harness.HarnessEvidence,
    ) -> harness.HarnessEvidence:
        self.calls.append(phase)
        return evidence


def _authorize_pure_fake_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(harness, "_NATIVE_EFFECT_EXECUTION_AUTHORIZED", True)
    monkeypatch.setattr(
        harness,
        "_NATIVE_EFFECT_AUTHORIZATION_ID",
        "TEST-ONLY-PURE-FAKE-DISPATCH",
    )
    monkeypatch.setattr(
        harness.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: pytest.fail("Windows DLL load was attempted"),
    )


@pytest.mark.parametrize(
    ("evidence_factory", "requested_phase"),
    [
        (lambda: harness.HarnessEvidence(), harness.Phase.MACHINE_CREATE_AND_VALIDATE),
        (
            lambda: harness.HarnessEvidence(),
            harness.Phase.FINAL_EVIDENCE_RECONCILIATION,
        ),
        (
            lambda: harness.begin_machine_creation(_through_preflight()),
            harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF,
        ),
        (lambda: _through_preflight(), harness.Phase.READ_ONLY_PREFLIGHT),
    ],
)
def test_authorized_fake_dispatch_rejects_wrong_or_skipped_phase(
    monkeypatch,
    evidence_factory,
    requested_phase: harness.Phase,
) -> None:
    _authorize_pure_fake_dispatch(monkeypatch)
    operations = _FakeOperations()
    with pytest.raises(harness.HarnessContractError):
        harness.execute_native_phase(
            requested_phase,
            evidence_factory(),
            operations,
        )
    assert operations.calls == []


@pytest.mark.parametrize(
    "terminal_outcome",
    [
        harness.PhaseOutcome.FAILED,
        harness.PhaseOutcome.UNCERTAIN,
        harness.PhaseOutcome.BLOCKED,
    ],
)
def test_authorized_fake_dispatch_rejects_terminal_predecessor(
    monkeypatch,
    terminal_outcome: harness.PhaseOutcome,
) -> None:
    _authorize_pure_fake_dispatch(monkeypatch)
    evidence = harness.append_phase_result(
        harness.HarnessEvidence(),
        harness.Phase.READ_ONLY_PREFLIGHT,
        terminal_outcome,
    )
    operations = _FakeOperations()
    with pytest.raises(harness.HarnessContractError):
        harness.execute_native_phase(
            harness.Phase.MACHINE_CREATE_AND_VALIDATE,
            evidence,
            operations,
        )
    assert operations.calls == []


def test_authorized_fake_dispatch_rejects_blocked_ordinary_identity(
    monkeypatch,
) -> None:
    _authorize_pure_fake_dispatch(monkeypatch)
    operations = _FakeOperations()
    with pytest.raises(harness.HarnessContractError):
        harness.execute_native_phase(
            harness.Phase.ORDINARY_NONADMIN_DENIAL,
            _through_trading(),
            operations,
        )
    assert operations.calls == []


def test_exact_eligible_phase_reaches_fake_operations_once(monkeypatch) -> None:
    _authorize_pure_fake_dispatch(monkeypatch)
    operations = _FakeOperations()
    evidence = harness.HarnessEvidence()
    assert (
        harness.execute_native_phase(
            harness.Phase.READ_ONLY_PREFLIGHT,
            evidence,
            operations,
        )
        is evidence
    )
    assert operations.calls == [harness.Phase.READ_ONLY_PREFLIGHT]


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


def test_native_property_buffers_require_exact_dword_and_utf16_shapes() -> None:
    assert harness.parse_ncrypt_dword(b"\x01\x00\x00\x00", "support") == 1
    assert harness.parse_ncrypt_string(
        "ECDSA".encode("utf-16-le") + b"\x00\x00", "alg"
    ) == ("ECDSA")
    with pytest.raises(harness.HarnessContractError):
        harness.parse_ncrypt_dword(b"\x01\x00", "support")
    with pytest.raises(harness.HarnessContractError):
        harness.parse_ncrypt_string(b"E\x00", "alg")
    with pytest.raises(harness.HarnessContractError):
        harness.parse_ncrypt_string(b"E\x00\x00\x00X\x00\x00\x00", "alg")


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


def test_modifying_committed_phase_snapshot_is_detected() -> None:
    evidence = _through_machine()
    record = evidence.phases[-1]
    completion = record.state_snapshot.completion
    assert isinstance(completion, harness.MachineValidationCompletion)
    altered_snapshot = dataclasses.replace(
        record.state_snapshot,
        completion=dataclasses.replace(completion, security_descriptor_verified=False),
    )
    altered_record = dataclasses.replace(record, state_snapshot=altered_snapshot)
    tampered = dataclasses.replace(
        evidence, phases=(*evidence.phases[:-1], altered_record)
    )
    with pytest.raises(harness.HarnessContractError, match="snapshot digest"):
        harness.validate_harness_evidence(tampered)


def test_current_lifecycle_cannot_regress_from_committed_phase() -> None:
    evidence = _through_machine()
    tampered = dataclasses.replace(
        evidence,
        lifecycle=dataclasses.replace(evidence.lifecycle, machine_created=False),
    )
    with pytest.raises(harness.HarnessContractError, match="lifecycle regressed"):
        harness.validate_harness_evidence(tampered)


def test_current_signature_cannot_contradict_committed_effect_phase() -> None:
    evidence = _through_elevated()
    tampered = dataclasses.replace(
        evidence, signature_outcome=harness.SignatureOutcome.FAILED
    )
    with pytest.raises(harness.HarnessContractError, match="signature state"):
        harness.validate_harness_evidence(tampered)


def test_current_probe_result_cannot_contradict_committed_effect_phase() -> None:
    evidence = _through_elevated()
    results = list(evidence.private_export_probe_results)
    results[0] = dataclasses.replace(
        results[0], outcome=harness.PrivateExportProbeOutcome.FAILED
    )
    tampered = dataclasses.replace(
        evidence, private_export_probe_results=tuple(results)
    )
    with pytest.raises(harness.HarnessContractError, match="private-export state"):
        harness.validate_harness_evidence(tampered)


def test_ordinary_nonadmin_phase_remains_fail_closed() -> None:
    assert harness.ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED is True
    assert harness.ORDINARY_NONADMIN_TEST_SID is None
    assert harness.ORDINARY_NONADMIN_SELECTION_REQUIRES_REVIEW is True
    evidence = _through_trading()
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


def _complete_export_probes(
    evidence: harness.HarnessEvidence,
    first_outcome: harness.PrivateExportProbeOutcome = (
        harness.PrivateExportProbeOutcome.DENIED_AS_REQUIRED
    ),
) -> harness.HarnessEvidence:
    for index, probe in enumerate(harness.PrivateExportProbe):
        evidence = harness.begin_private_export_denial_probe(
            evidence, harness.MACHINE_TEST_KEY, probe
        )
        outcome = (
            first_outcome
            if index == 0
            else harness.PrivateExportProbeOutcome.DENIED_AS_REQUIRED
        )
        if outcome is not harness.PrivateExportProbeOutcome.ATTEMPTED_UNCERTAIN:
            evidence = harness.record_private_export_probe_outcome(
                evidence, probe, outcome
            )
    return evidence


def test_elevated_success_rejects_absent_signature() -> None:
    evidence = _complete_export_probes(_through_shadow())
    with pytest.raises(harness.HarnessContractError):
        harness.append_phase_result(
            evidence,
            harness.Phase.ELEVATED_MACHINE_EFFECT_TEST,
            harness.PhaseOutcome.SUCCEEDED,
            _elevated_completion(),
        )


@pytest.mark.parametrize(
    "signature_outcome",
    [
        harness.SignatureOutcome.ATTEMPTED_UNCERTAIN,
        harness.SignatureOutcome.FAILED,
    ],
)
def test_elevated_success_rejects_uncertain_or_failed_signature(
    signature_outcome: harness.SignatureOutcome,
) -> None:
    evidence = harness.begin_test_signature(_through_shadow(), harness.MACHINE_TEST_KEY)
    if signature_outcome is harness.SignatureOutcome.FAILED:
        evidence = harness.record_test_signature_outcome(evidence, signature_outcome)
    evidence = _complete_export_probes(evidence)
    with pytest.raises(harness.HarnessContractError):
        harness.append_phase_result(
            evidence,
            harness.Phase.ELEVATED_MACHINE_EFFECT_TEST,
            harness.PhaseOutcome.SUCCEEDED,
            _elevated_completion(),
        )


def test_elevated_success_rejects_missing_export_probe() -> None:
    evidence = harness.begin_test_signature(_through_shadow(), harness.MACHINE_TEST_KEY)
    evidence = harness.record_test_signature_outcome(
        evidence, harness.SignatureOutcome.SUCCEEDED
    )
    for probe in tuple(harness.PrivateExportProbe)[:-1]:
        evidence = harness.begin_private_export_denial_probe(
            evidence, harness.MACHINE_TEST_KEY, probe
        )
        evidence = harness.record_private_export_probe_outcome(
            evidence,
            probe,
            harness.PrivateExportProbeOutcome.DENIED_AS_REQUIRED,
        )
    with pytest.raises(harness.HarnessContractError):
        harness.append_phase_result(
            evidence,
            harness.Phase.ELEVATED_MACHINE_EFFECT_TEST,
            harness.PhaseOutcome.SUCCEEDED,
            _elevated_completion(),
        )


@pytest.mark.parametrize(
    "probe_outcome",
    [
        harness.PrivateExportProbeOutcome.ATTEMPTED_UNCERTAIN,
        harness.PrivateExportProbeOutcome.FAILED,
        harness.PrivateExportProbeOutcome.UNSUPPORTED_FORMAT,
    ],
)
def test_elevated_success_rejects_non_denial_probe_result(
    probe_outcome: harness.PrivateExportProbeOutcome,
) -> None:
    evidence = harness.begin_test_signature(_through_shadow(), harness.MACHINE_TEST_KEY)
    evidence = harness.record_test_signature_outcome(
        evidence, harness.SignatureOutcome.SUCCEEDED
    )
    evidence = _complete_export_probes(evidence, probe_outcome)
    with pytest.raises(harness.HarnessContractError):
        harness.append_phase_result(
            evidence,
            harness.Phase.ELEVATED_MACHINE_EFFECT_TEST,
            harness.PhaseOutcome.SUCCEEDED,
            _elevated_completion(),
        )


def test_trading_success_requires_dedicated_completion_result() -> None:
    with pytest.raises(harness.HarnessContractError):
        harness.append_phase_result(
            _through_elevated(),
            harness.Phase.TRADING_DENIAL,
            harness.PhaseOutcome.SUCCEEDED,
        )


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
    assert (
        updated.private_export_probe_results[0].outcome
        is harness.PrivateExportProbeOutcome.ATTEMPTED_UNCERTAIN
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


def test_strict_v2_loader_round_trips_canonical_evidence(tmp_path: Path) -> None:
    evidence = _through_shadow()
    path = tmp_path / "evidence.json"
    path.write_bytes(harness.canonical_evidence_bytes(evidence))
    assert harness.load_test_evidence(path) == evidence


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__(
            "schema", "p3-r1-ksp-disposable-test-evidence/v1"
        ),
        lambda payload: payload.__setitem__("unknown", True),
        lambda payload: payload.pop("test_container"),
        lambda payload: payload.__setitem__("signature_attempt_count", True),
    ],
)
def test_strict_v2_loader_rejects_wrong_schema_shape_and_types(
    tmp_path: Path, mutate
) -> None:
    payload = json.loads(harness.canonical_evidence_bytes(_through_shadow()))
    mutate(payload)
    path = tmp_path / "evidence.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n",
        encoding="ascii",
    )
    with pytest.raises(harness.HarnessContractError):
        harness.load_test_evidence(path)


def test_strict_v2_loader_rejects_duplicate_and_noncanonical_json(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.json"
    path.write_text('{"schema":"x","schema":"y"}\n', encoding="ascii")
    with pytest.raises(harness.HarnessContractError):
        harness.load_test_evidence(path)
    path.write_bytes(harness.canonical_evidence_bytes(_through_shadow()).rstrip())
    with pytest.raises(harness.HarnessContractError, match="canonical"):
        harness.load_test_evidence(path)


def test_append_only_retained_loader_selects_validated_latest_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "retained"
    preflight = _through_preflight()
    first = harness._publish_retained_evidence_to_root_create_new(preflight, root)
    assert first.name.startswith("snapshot-0001-01-")
    attempted = harness.begin_machine_creation(preflight)
    second = harness._publish_retained_evidence_to_root_create_new(attempted, root)
    assert second.name.startswith("snapshot-0002-01-")
    assert harness._load_retained_evidence_from_root(root) == attempted
    with pytest.raises(harness.HarnessContractError, match="duplicate"):
        harness._publish_retained_evidence_to_root_create_new(attempted, root)


def test_retained_loader_rejects_unknown_gap_and_digest_tamper(tmp_path: Path) -> None:
    root = tmp_path / "retained"
    first = harness._publish_retained_evidence_to_root_create_new(
        _through_preflight(), root
    )
    first.write_bytes(first.read_bytes() + b" ")
    with pytest.raises(harness.HarnessContractError, match="digest"):
        harness._load_retained_evidence_from_root(root)

    other_root = tmp_path / "other-retained"
    published = harness._publish_retained_evidence_to_root_create_new(
        _through_preflight(), other_root
    )
    published.rename(published.with_name(published.name.replace("0001", "0002", 1)))
    with pytest.raises(harness.HarnessContractError, match="sequence"):
        harness._load_retained_evidence_from_root(other_root)


def test_retained_root_is_created_only_for_successful_first_preflight(
    tmp_path: Path,
) -> None:
    failed = harness.NativeWindowsPhaseOperations(
        _FakeNativeApi(provider_name="Wrong Provider")
    ).execute(harness.Phase.READ_ONLY_PREFLIGHT, harness.HarnessEvidence())
    root = tmp_path / "retained"
    with pytest.raises(harness.HarnessContractError):
        harness._publish_retained_evidence_to_root_create_new(failed, root)
    assert not root.exists()


def _deterministic_test_signature(digest: bytes) -> bytes:
    private_scalar = 1
    nonce = 7
    point = harness._p256_multiply(nonce, (harness._P256_GX, harness._P256_GY))
    assert point is not None
    r = point[0] % harness._P256_N
    z = int.from_bytes(digest, "big")
    s = (pow(nonce, -1, harness._P256_N) * (z + r * private_scalar)) % (harness._P256_N)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


class _FakeNativeApi:
    def __init__(
        self,
        *,
        machine_exists: bool = False,
        shadow_exists: bool = False,
        token: harness.TokenFacts | None = None,
        deny_machine: bool = False,
        provider_name: str = harness.PROVIDER_NAME,
    ) -> None:
        self.machine_exists = machine_exists
        self.shadow_exists = shadow_exists
        self.deny_machine = deny_machine
        self.provider_name = provider_name
        self.token = token or harness.TokenFacts(
            harness.ELEVATED_TEST_OPERATOR_SID, True, True, True
        )
        self.events: list[str] = []
        self.dwords = {
            "machine": {
                harness.NCRYPT_KEY_USAGE_PROPERTY: harness.NCRYPT_ALLOW_SIGNING_FLAG,
                harness.NCRYPT_EXPORT_POLICY_PROPERTY: 0,
            }
        }

    def _handle(self, value: str) -> harness.OwnedNativeHandle:
        self.events.append(f"acquire:{value}")

        def release(released: str) -> None:
            self.events.append(f"close:{released}")

        return harness.OwnedNativeHandle(value, release, value)

    def current_token_facts(self) -> harness.TokenFacts:
        self.events.append("token")
        return self.token

    def evidence_root_exists(self, root: PureWindowsPath) -> bool:
        assert root == harness.FUTURE_EVIDENCE_ROOT
        self.events.append("evidence-root-absent")
        return False

    def open_provider(self) -> harness.OwnedNativeHandle:
        return self._handle("provider")

    def get_dword(self, handle, property_name: str, flags: int) -> int:
        self.events.append(f"get-dword:{handle}:{property_name}:{flags:#x}")
        if handle == "provider":
            assert property_name == harness.NCRYPT_SECURITY_DESCR_SUPPORT_PROPERTY
            return 1
        if property_name == harness.NCRYPT_KEY_TYPE_PROPERTY:
            return harness.NCRYPT_KEY_TYPE_MACHINE if handle == "machine" else 0
        if property_name == harness.NCRYPT_LENGTH_PROPERTY:
            return harness.KEY_LENGTH_BITS
        return self.dwords[handle][property_name]

    def get_string(self, handle, property_name: str, flags: int) -> str:
        self.events.append(f"get-string:{handle}:{property_name}:{flags:#x}")
        if handle == "provider":
            if property_name != harness.NCRYPT_NAME_PROPERTY:
                raise harness.HarnessContractError("wrong provider identity property")
            return self.provider_name
        values = {
            harness.NCRYPT_NAME_PROPERTY: harness.TEST_CONTAINER_TEXT,
            harness.NCRYPT_UNIQUE_NAME_PROPERTY: "machine-unique-name",
            harness.NCRYPT_ALGORITHM_PROPERTY: harness.ALGORITHM_NAME,
            harness.NCRYPT_ALGORITHM_GROUP_PROPERTY: harness.ALGORITHM_GROUP,
        }
        return values[property_name]

    def get_bytes(self, handle, property_name: str, flags: int) -> bytes:
        self.events.append(f"get-bytes:{handle}:{property_name}:{flags:#x}")
        assert handle == "machine"
        assert property_name == harness.NCRYPT_SECURITY_DESCR_PROPERTY
        return harness.build_exact_security_descriptor_bytes()

    def try_open_key(
        self, provider, identity: harness.KeyIdentity, flags: int
    ) -> harness.NativeOpenResult:
        assert provider == "provider"
        self.events.append(
            f"open:{identity.scope.value}:{identity.container}:{flags:#x}"
        )
        exists = (
            self.machine_exists
            if identity.scope is harness.KeyScope.LOCAL_MACHINE
            else self.shadow_exists
        )
        if identity.scope is harness.KeyScope.LOCAL_MACHINE and self.deny_machine:
            return harness.NativeOpenResult(harness.NTE_PERM, None)
        if not exists:
            return harness.NativeOpenResult(harness.NTE_BAD_KEYSET, None)
        value = (
            "machine" if identity.scope is harness.KeyScope.LOCAL_MACHINE else "shadow"
        )
        return harness.NativeOpenResult(0, self._handle(value))

    def create_key(
        self, provider, identity: harness.KeyIdentity, flags: int
    ) -> harness.OwnedNativeHandle:
        assert provider == "provider"
        self.events.append(f"create:{identity.scope.value}:{flags:#x}")
        if identity.scope is harness.KeyScope.LOCAL_MACHINE:
            assert not self.machine_exists
            self.machine_exists = True
            return self._handle("machine")
        assert not self.shadow_exists
        self.shadow_exists = True
        return self._handle("shadow")

    def set_dword(self, handle, property_name: str, value: int, flags: int) -> None:
        self.events.append(f"set-dword:{handle}:{property_name}:{value:#x}:{flags:#x}")
        self.dwords.setdefault(handle, {})[property_name] = value

    def set_bytes(self, handle, property_name: str, value: bytes, flags: int) -> None:
        self.events.append(f"set-bytes:{handle}:{property_name}:{flags:#x}")
        assert value == harness.build_exact_security_descriptor_bytes()

    def build_exact_security_descriptor(self) -> bytes:
        self.events.append("build-security-descriptor")
        return harness.build_exact_security_descriptor_bytes()

    def decode_security_descriptor(
        self, value: bytes
    ) -> harness.SecurityDescriptorSemantic:
        self.events.append("decode-security-descriptor")
        assert value == harness.build_exact_security_descriptor_bytes()
        return _valid_descriptor()

    def finalize_key(self, handle, flags: int) -> None:
        self.events.append(f"finalize:{handle}:{flags:#x}")

    def export_public(self, handle, flags: int) -> bytes:
        self.events.append(f"public-export:{handle}:{flags:#x}")
        return _public_blob() if handle == "machine" else _public_blob(_GX, _NEGATED_GY)

    def private_export_probe_status(self, handle, blob_type: str, flags: int) -> int:
        self.events.append(f"private-probe:{handle}:{blob_type}:{flags:#x}")
        return harness.NTE_PERM

    def sign_hash(self, handle, digest: bytes, flags: int) -> bytes:
        self.events.append(f"sign:{handle}:{flags:#x}")
        return _deterministic_test_signature(digest)


class _FakeRetainedStore:
    def __init__(self, initial: harness.HarnessEvidence | None = None) -> None:
        self.latest = initial
        self.events: list[str] = []

    def root_exists(self) -> bool:
        self.events.append("root-exists")
        return self.latest is not None

    def load(self) -> harness.HarnessEvidence:
        self.events.append("load")
        if self.latest is None:
            raise AssertionError("no retained evidence")
        return self.latest

    def persist(self, evidence: harness.HarnessEvidence) -> harness.HarnessEvidence:
        harness.validate_harness_evidence(evidence)
        self.events.append(
            "persist:"
            f"{evidence.lifecycle.machine_creation_attempted}:"
            f"{evidence.lifecycle.shadow_creation_attempted}:"
            f"{len(evidence.phases)}"
        )
        self.latest = evidence
        return evidence


def test_read_only_preflight_uses_exact_provider_and_both_scope_absence() -> None:
    api = _FakeNativeApi()
    result = harness.NativeWindowsPhaseOperations(api).execute(
        harness.Phase.READ_ONLY_PREFLIGHT, harness.HarnessEvidence()
    )
    assert result.phases[-1].outcome is harness.PhaseOutcome.SUCCEEDED
    opens = [event for event in api.events if event.startswith("open:")]
    assert opens == [
        f"open:local-machine:{harness.TEST_CONTAINER_TEXT}:0x60",
        f"open:current-user:{harness.TEST_CONTAINER_TEXT}:0x40",
    ]
    assert all(harness.PRODUCTION_CONTAINER_TEXT not in event for event in api.events)
    assert f"get-string:provider:Name:{harness.NCRYPT_PROPERTY_GET_FLAGS:#x}" in (
        api.events
    )
    assert not hasattr(harness, "NCRYPT_PROVIDER_NAME_PROPERTY")
    assert "Provider Name" not in inspect.getsource(
        harness.NativeWindowsPhaseOperations._require_provider_name
    )


def test_provider_name_readback_mismatch_fails_closed() -> None:
    api = _FakeNativeApi(provider_name="Unexpected Provider")
    result = harness.NativeWindowsPhaseOperations(api).execute(
        harness.Phase.READ_ONLY_PREFLIGHT, harness.HarnessEvidence()
    )
    assert result.phases[-1].outcome is harness.PhaseOutcome.FAILED
    assert not any(event.startswith("open:") for event in api.events)


def test_fixed_root_runner_accepts_no_caller_evidence_path_or_environment(
    monkeypatch,
) -> None:
    assert tuple(
        inspect.signature(harness.execute_next_retained_native_phase).parameters
    ) == ("requested_phase",)
    reached = False

    def forbidden_factory():
        nonlocal reached
        reached = True
        raise AssertionError("source gate was bypassed")

    monkeypatch.setattr(
        harness.NativeWindowsPhaseOperations,
        "load_for_authorized_execution",
        forbidden_factory,
    )
    with pytest.raises(harness.NativeExecutionDisabled):
        harness.execute_next_retained_native_phase(harness.Phase.READ_ONLY_PREFLIGHT)
    assert reached is False


def test_retained_runner_first_preflight_starts_empty_and_publishes_result() -> None:
    store = _FakeRetainedStore()
    api = _FakeNativeApi()
    api.requires_persistent_retainer = True

    result = harness._execute_next_retained_native_phase(
        harness.Phase.READ_ONLY_PREFLIGHT,
        evidence_root_exists=store.root_exists,
        load_latest=store.load,
        persist_reload=store.persist,
        operations_factory=lambda: harness.NativeWindowsPhaseOperations(
            api, store.persist
        ),
    )

    assert result == _through_preflight()
    assert store.latest == result
    assert store.events[0] == "root-exists"
    assert store.events[-1] == "load"


@pytest.mark.parametrize(
    ("phase", "initial", "machine_exists", "attempt_event", "create_event"),
    [
        (
            harness.Phase.MACHINE_CREATE_AND_VALIDATE,
            _through_preflight(),
            False,
            "persist:True:False:1",
            "create:local-machine:0x20",
        ),
        (
            harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF,
            _through_machine(),
            True,
            "persist:True:True:2",
            "create:current-user:0x0",
        ),
    ],
)
def test_retained_runner_durably_confirms_create_attempt_before_dispatch(
    phase: harness.Phase,
    initial: harness.HarnessEvidence,
    machine_exists: bool,
    attempt_event: str,
    create_event: str,
) -> None:
    store = _FakeRetainedStore(initial)
    api = _FakeNativeApi(machine_exists=machine_exists)
    api.requires_persistent_retainer = True
    ordering: list[str] = []
    original_persist = store.persist
    original_create = api.create_key

    def persist(evidence: harness.HarnessEvidence) -> harness.HarnessEvidence:
        result = original_persist(evidence)
        ordering.append(store.events[-1])
        return result

    def create(*args, **kwargs):
        ordering.append(create_event)
        return original_create(*args, **kwargs)

    api.create_key = create

    def factory() -> harness.NativeWindowsPhaseOperations:
        ordering.append("factory")
        return harness.NativeWindowsPhaseOperations(api, persist)

    result = harness._execute_next_retained_native_phase(
        phase,
        evidence_root_exists=store.root_exists,
        load_latest=store.load,
        persist_reload=persist,
        operations_factory=factory,
    )

    assert result.phases[-1].phase is phase
    assert result.phases[-1].outcome is harness.PhaseOutcome.SUCCEEDED
    assert ordering.index(attempt_event) < ordering.index("factory")
    assert ordering.index("factory") < ordering.index(create_event)


@pytest.mark.parametrize(
    ("phase", "initial"),
    [
        (harness.Phase.MACHINE_CREATE_AND_VALIDATE, _through_preflight()),
        (harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF, _through_machine()),
    ],
)
def test_retained_runner_stops_before_create_when_attempt_retention_fails(
    phase: harness.Phase,
    initial: harness.HarnessEvidence,
) -> None:
    store = _FakeRetainedStore(initial)
    factory_reached = False

    def fail_persist(evidence: harness.HarnessEvidence):
        raise OSError(evidence.lifecycle)

    def forbidden_factory():
        nonlocal factory_reached
        factory_reached = True
        raise AssertionError("native factory reached after retention failure")

    with pytest.raises(harness.EvidenceRetentionUncertain) as raised:
        harness._execute_next_retained_native_phase(
            phase,
            evidence_root_exists=store.root_exists,
            load_latest=store.load,
            persist_reload=fail_persist,
            operations_factory=forbidden_factory,
        )
    assert raised.value.effect_may_have_occurred is False
    assert factory_reached is False


def test_retained_runner_rejects_requested_phase_mismatch_before_factory() -> None:
    store = _FakeRetainedStore(_through_preflight())
    reached = False

    def forbidden_factory():
        nonlocal reached
        reached = True

    with pytest.raises(harness.HarnessContractError, match="retained authority"):
        harness._execute_next_retained_native_phase(
            harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF,
            evidence_root_exists=store.root_exists,
            load_latest=store.load,
            persist_reload=store.persist,
            operations_factory=forbidden_factory,
        )
    assert reached is False


def test_retained_runner_fsyncs_and_reloads_tmp_snapshots_before_each_create(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "retained"
    ordering: list[str] = []
    real_fsync = harness.os.fsync

    def fsync(descriptor: int) -> None:
        real_fsync(descriptor)
        ordering.append("fsync")

    monkeypatch.setattr(harness.os, "fsync", fsync)

    def load() -> harness.HarnessEvidence:
        result = harness._load_retained_evidence_from_root(root)
        ordering.append("reload")
        return result

    def persist(evidence: harness.HarnessEvidence) -> harness.HarnessEvidence:
        harness._publish_retained_evidence_to_root_create_new(evidence, root)
        return load()

    api = _FakeNativeApi()
    api.requires_persistent_retainer = True
    original_create = api.create_key

    def create(*args, **kwargs):
        assert ordering[-2:] == ["fsync", "reload"]
        ordering.append("create")
        return original_create(*args, **kwargs)

    api.create_key = create
    for phase in (
        harness.Phase.READ_ONLY_PREFLIGHT,
        harness.Phase.MACHINE_CREATE_AND_VALIDATE,
        harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF,
    ):
        result = harness._execute_next_retained_native_phase(
            phase,
            evidence_root_exists=root.exists,
            load_latest=load,
            persist_reload=persist,
            operations_factory=lambda: harness.NativeWindowsPhaseOperations(
                api, persist
            ),
        )
        assert result.phases[-1].outcome is harness.PhaseOutcome.SUCCEEDED
    assert ordering.count("create") == 2


@pytest.mark.parametrize(
    ("phase", "initial"),
    [
        (harness.Phase.MACHINE_CREATE_AND_VALIDATE, _through_preflight()),
        (harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF, _through_machine()),
    ],
)
def test_retained_runner_rejects_mismatched_reload_and_previously_retained_attempt(
    phase: harness.Phase,
    initial: harness.HarnessEvidence,
) -> None:
    store = _FakeRetainedStore(initial)

    def forbidden_factory():
        raise AssertionError("unconfirmed or previously attempted create dispatched")

    with pytest.raises(harness.EvidenceRetentionUncertain):
        harness._execute_next_retained_native_phase(
            phase,
            evidence_root_exists=store.root_exists,
            load_latest=store.load,
            persist_reload=lambda intended: initial,
            operations_factory=forbidden_factory,
        )

    store.latest = (
        harness.begin_machine_creation(initial)
        if phase is harness.Phase.MACHINE_CREATE_AND_VALIDATE
        else harness.begin_shadow_creation(initial)
    )
    with pytest.raises(harness.HarnessContractError, match="cannot restart"):
        harness._execute_next_retained_native_phase(
            phase,
            evidence_root_exists=store.root_exists,
            load_latest=store.load,
            persist_reload=store.persist,
            operations_factory=forbidden_factory,
        )


def test_machine_phase_exact_prefinalization_finalize_reopen_order() -> None:
    api = _FakeNativeApi()
    evidence = harness.begin_machine_creation(_through_preflight())
    result = harness.NativeWindowsPhaseOperations(api).execute(
        harness.Phase.MACHINE_CREATE_AND_VALIDATE, evidence
    )
    assert result.phases[-1].outcome is harness.PhaseOutcome.SUCCEEDED
    create = api.events.index("create:local-machine:0x20")
    set_usage = next(
        i
        for i, event in enumerate(api.events)
        if event.startswith("set-dword:machine:Key Usage")
    )
    get_usage = next(
        i
        for i, event in enumerate(api.events)
        if event.startswith("get-dword:machine:Key Usage")
    )
    set_export = next(
        i
        for i, event in enumerate(api.events)
        if event.startswith("set-dword:machine:Export Policy")
    )
    set_security = next(
        i
        for i, event in enumerate(api.events)
        if event.startswith("set-bytes:machine:Security Descr")
    )
    finalize = api.events.index("finalize:machine:0x40")
    close_original = api.events.index("close:machine")
    reopen = api.events.index(f"open:local-machine:{harness.TEST_CONTAINER_TEXT}:0x60")
    assert create < set_usage < get_usage < set_export < set_security < finalize
    assert finalize < close_original < reopen
    assert harness.NCRYPT_OVERWRITE_KEY_FLAG & harness.NCRYPT_MACHINE_CREATE_FLAGS == 0


def test_shadow_phase_uses_current_user_no_overwrite_and_reproves_machine() -> None:
    api = _FakeNativeApi(machine_exists=True)
    evidence = harness.begin_shadow_creation(_through_machine())
    result = harness.NativeWindowsPhaseOperations(api).execute(
        harness.Phase.SHADOW_CREATE_AND_SCOPE_PROOF, evidence
    )
    assert result.phases[-1].outcome is harness.PhaseOutcome.SUCCEEDED
    assert "create:current-user:0x0" in api.events
    assert api.events.index("finalize:shadow:0x40") < api.events.index("close:shadow")
    shadow_open = api.events.index(
        f"open:current-user:{harness.TEST_CONTAINER_TEXT}:0x40"
    )
    machine_open = api.events.index(
        f"open:local-machine:{harness.TEST_CONTAINER_TEXT}:0x60"
    )
    assert shadow_open < machine_open


def test_elevated_effect_marks_each_attempt_before_call_and_signs_last(
    monkeypatch,
) -> None:
    api = _FakeNativeApi(machine_exists=True, shadow_exists=True)
    ordering: list[str] = []
    real_begin_probe = harness.begin_private_export_denial_probe
    real_begin_signature = harness.begin_test_signature

    def begin_probe(*args, **kwargs):
        ordering.append("begin-probe")
        return real_begin_probe(*args, **kwargs)

    def begin_signature(*args, **kwargs):
        ordering.append("begin-signature")
        return real_begin_signature(*args, **kwargs)

    monkeypatch.setattr(harness, "begin_private_export_denial_probe", begin_probe)
    monkeypatch.setattr(harness, "begin_test_signature", begin_signature)
    original_probe = api.private_export_probe_status
    original_sign = api.sign_hash

    def probe(*args, **kwargs):
        ordering.append("native-probe")
        return original_probe(*args, **kwargs)

    def sign(*args, **kwargs):
        ordering.append("native-sign")
        return original_sign(*args, **kwargs)

    api.private_export_probe_status = probe
    api.sign_hash = sign
    result = harness.NativeWindowsPhaseOperations(api).execute(
        harness.Phase.ELEVATED_MACHINE_EFFECT_TEST, _through_shadow()
    )
    assert result.phases[-1].outcome is harness.PhaseOutcome.SUCCEEDED
    assert ordering == [
        "begin-probe",
        "native-probe",
        "begin-probe",
        "native-probe",
        "begin-probe",
        "native-probe",
        "begin-probe",
        "native-probe",
        "begin-signature",
        "native-sign",
    ]
    assert result.signature_attempt_count == 1
    assert "sign:machine:0x40" in api.events


def test_test_signature_preimage_is_fixed_and_unmistakably_nonproduction() -> None:
    assert harness.TEST_SIGNATURE_PREIMAGE.startswith(harness.TEST_SIGNATURE_DOMAIN)
    assert b"TEST-ONLY" in harness.TEST_SIGNATURE_PREIMAGE
    assert b"NO-BOOTSTRAP" in harness.TEST_SIGNATURE_PREIMAGE
    assert b"NO-P3R1-RECOVERY-AUTHORIZATION" in harness.TEST_SIGNATURE_PREIMAGE
    assert b"NO-PRODUCTION-ORDER-OR-TRADING-AUTHORITY" in (
        harness.TEST_SIGNATURE_PREIMAGE
    )


def test_private_export_status_classification_is_explicit() -> None:
    assert (
        harness.classify_private_export_status(harness.NTE_PERM)
        is harness.PrivateExportProbeOutcome.DENIED_AS_REQUIRED
    )
    assert (
        harness.classify_private_export_status(harness.NTE_NOT_SUPPORTED)
        is harness.PrivateExportProbeOutcome.UNSUPPORTED_FORMAT
    )
    assert (
        harness.classify_private_export_status(0)
        is harness.PrivateExportProbeOutcome.FAILED
    )


def test_denial_phase_requires_exact_genuine_non_elevated_actor() -> None:
    wrong = _FakeNativeApi(machine_exists=True, deny_machine=True)
    wrong_result = harness.NativeWindowsPhaseOperations(wrong).execute(
        harness.Phase.TRADING_DENIAL, _through_elevated()
    )
    assert wrong_result.phases[-1].outcome is harness.PhaseOutcome.FAILED
    exact = _FakeNativeApi(
        machine_exists=True,
        deny_machine=True,
        token=harness.TokenFacts(harness.TRADING_SID, False, False, False),
    )
    result = harness.NativeWindowsPhaseOperations(exact).execute(
        harness.Phase.TRADING_DENIAL, _through_elevated()
    )
    assert result.phases[-1].outcome is harness.PhaseOutcome.SUCCEEDED
    assert not any(event.startswith("private-probe") for event in exact.events)
    assert not any(event.startswith("sign:") for event in exact.events)


def test_owned_handle_releases_once_and_reports_release_failure() -> None:
    releases: list[int] = []
    handle = harness.OwnedNativeHandle(7, releases.append, "test")
    handle.close()
    handle.close()
    assert releases == [7]

    def fail_release(value: int) -> None:
        raise RuntimeError(value)

    with pytest.raises(harness.HandleReleaseError):
        with harness.OwnedNativeHandle(8, fail_release, "test"):
            pass


def test_phase_release_failure_is_retained_as_uncertain() -> None:
    api = _FakeNativeApi()

    def open_provider() -> harness.OwnedNativeHandle:
        def fail_release(value: str) -> None:
            raise RuntimeError(value)

        return harness.OwnedNativeHandle("provider", fail_release, "provider")

    api.open_provider = open_provider
    result = harness.NativeWindowsPhaseOperations(api).execute(
        harness.Phase.READ_ONLY_PREFLIGHT, harness.HarnessEvidence()
    )
    assert result.phases[-1].outcome is harness.PhaseOutcome.UNCERTAIN


def test_effect_attempt_state_is_retained_before_each_native_call() -> None:
    api = _FakeNativeApi(machine_exists=True, shadow_exists=True)
    retained: list[harness.HarnessEvidence] = []
    original_probe = api.private_export_probe_status
    original_sign = api.sign_hash

    def probe(*args, **kwargs):
        assert (
            retained[-1]
            .private_export_probe_results[
                sum(
                    result.outcome
                    is not harness.PrivateExportProbeOutcome.NOT_ATTEMPTED
                    for result in retained[-1].private_export_probe_results
                )
                - 1
            ]
            .outcome
            is harness.PrivateExportProbeOutcome.ATTEMPTED_UNCERTAIN
        )
        return original_probe(*args, **kwargs)

    def sign(*args, **kwargs):
        assert (
            retained[-1].signature_outcome
            is harness.SignatureOutcome.ATTEMPTED_UNCERTAIN
        )
        assert retained[-1].signature_attempt_count == 1
        return original_sign(*args, **kwargs)

    api.private_export_probe_status = probe
    api.sign_hash = sign
    result = harness.NativeWindowsPhaseOperations(api, retained.append).execute(
        harness.Phase.ELEVATED_MACHINE_EFFECT_TEST, _through_shadow()
    )
    assert result.phases[-1].outcome is harness.PhaseOutcome.SUCCEEDED


def test_probe_attempt_retention_failure_prevents_native_probe() -> None:
    api = _FakeNativeApi(machine_exists=True, shadow_exists=True)
    api.requires_persistent_retainer = True
    operations = harness.NativeWindowsPhaseOperations(
        api,
        lambda evidence: (_ for _ in ()).throw(OSError(evidence)),
    )
    prior = _through_shadow()

    with pytest.raises(harness.EvidenceRetentionUncertain) as raised:
        operations.execute(harness.Phase.ELEVATED_MACHINE_EFFECT_TEST, prior)

    assert raised.value.effect_may_have_occurred is False
    assert operations._retained_evidence == prior
    assert not any(event.startswith("private-probe:") for event in api.events)


@pytest.mark.parametrize("release_fails", [False, True])
def test_post_probe_retention_failure_stops_without_retry_or_recursive_record(
    release_fails: bool,
) -> None:
    api = _FakeNativeApi(machine_exists=True, shadow_exists=True)
    api.requires_persistent_retainer = True
    retained: list[harness.HarnessEvidence] = []
    retention_calls = 0
    if release_fails:
        original_handle = api._handle

        def handle(value: str) -> harness.OwnedNativeHandle:
            if value != "machine":
                return original_handle(value)

            def fail_release(released: str) -> None:
                raise OSError("release failed")

            return harness.OwnedNativeHandle(value, fail_release, value)

        api._handle = handle

    def fail_second(evidence: harness.HarnessEvidence) -> harness.HarnessEvidence:
        nonlocal retention_calls
        retention_calls += 1
        if len(retained) == 1:
            raise OSError("terminal probe result could not be retained")
        retained.append(evidence)
        return evidence

    operations = harness.NativeWindowsPhaseOperations(api, fail_second)
    with pytest.raises(harness.EvidenceRetentionUncertain) as raised:
        operations.execute(
            harness.Phase.ELEVATED_MACHINE_EFFECT_TEST, _through_shadow()
        )

    assert raised.value.effect_may_have_occurred is True
    assert (
        len([event for event in api.events if event.startswith("private-probe:")]) == 1
    )
    assert not any(event.startswith("sign:") for event in api.events)
    assert (
        operations._retained_evidence.private_export_probe_results[0].outcome
        is harness.PrivateExportProbeOutcome.ATTEMPTED_UNCERTAIN
    )
    assert len(retained) == 1
    assert retention_calls == 2


def test_signature_attempt_retention_failure_prevents_native_signature() -> None:
    api = _FakeNativeApi(machine_exists=True, shadow_exists=True)
    api.requires_persistent_retainer = True
    retain_count = 0

    def fail_signature_marker(
        evidence: harness.HarnessEvidence,
    ) -> harness.HarnessEvidence:
        nonlocal retain_count
        retain_count += 1
        if retain_count == len(harness.PrivateExportProbe) * 2 + 1:
            raise OSError("signature marker could not be retained")
        return evidence

    with pytest.raises(harness.EvidenceRetentionUncertain) as raised:
        harness.NativeWindowsPhaseOperations(api, fail_signature_marker).execute(
            harness.Phase.ELEVATED_MACHINE_EFFECT_TEST, _through_shadow()
        )

    assert raised.value.effect_may_have_occurred is True
    assert len(
        [event for event in api.events if event.startswith("private-probe:")]
    ) == len(harness.PrivateExportProbe)
    assert not any(event.startswith("sign:") for event in api.events)


def test_real_native_operations_are_unreachable_while_source_gate_disabled(
    monkeypatch,
) -> None:
    reached = False

    def forbidden(self, phase, evidence):
        nonlocal reached
        reached = True
        return evidence

    monkeypatch.setattr(harness.NativeWindowsPhaseOperations, "execute", forbidden)
    operations = harness.NativeWindowsPhaseOperations(_FakeNativeApi())
    with pytest.raises(harness.NativeExecutionDisabled):
        harness.execute_native_phase(
            harness.Phase.READ_ONLY_PREFLIGHT,
            harness.HarnessEvidence(),
            operations,
        )
    assert reached is False


def test_ctypes_adapter_and_future_evidence_publisher_are_source_gated(
    monkeypatch,
) -> None:
    with pytest.raises(harness.NativeExecutionDisabled):
        harness.CtypesNativeApi(harness.WindowsNativeBindings({}))

    touched = False

    def forbidden_mkdir(*args, **kwargs):
        nonlocal touched
        touched = True

    monkeypatch.setattr(Path, "mkdir", forbidden_mkdir)
    with pytest.raises(harness.NativeExecutionDisabled):
        harness.publish_retained_evidence_create_new(_through_preflight())
    assert touched is False


def test_create_success_without_handle_is_classified_uncertain() -> None:
    api = object.__new__(harness.CtypesNativeApi)

    def success_without_handle(
        provider, output, algorithm, container, legacy_spec, flags
    ) -> int:
        return 0

    api._functions = {"NCryptCreatePersistedKey": success_without_handle}
    with pytest.raises(harness.NativeOperationUncertain, match="without.*handle"):
        api.create_key(
            "provider", harness.MACHINE_TEST_KEY, harness.NCRYPT_MACHINE_CREATE_FLAGS
        )


def test_generic_operations_cannot_dispatch_ctypes_with_caller_evidence() -> None:
    api = object.__new__(harness.CtypesNativeApi)
    api._functions = {}
    operations = harness.NativeWindowsPhaseOperations(api, lambda evidence: evidence)
    with pytest.raises(harness.NativeExecutionDisabled):
        operations.execute(harness.Phase.READ_ONLY_PREFLIGHT, harness.HarnessEvidence())


@pytest.mark.parametrize("bad_size_query", [False, True])
def test_signature_success_with_invalid_output_length_is_uncertain(
    bad_size_query: bool,
) -> None:
    api = object.__new__(harness.CtypesNativeApi)
    calls = 0

    def sign(handle, padding, digest, digest_size, output, size, returned, flags):
        nonlocal calls
        calls += 1
        harness.ctypes.cast(returned, harness.ctypes.POINTER(harness.ctypes.c_uint32))[
            0
        ] = 0 if bad_size_query or output is not None else 64
        return 0

    api._functions = {"NCryptSignHash": sign}
    with pytest.raises(harness.NativeOperationUncertain):
        api.sign_hash(1, bytes(32), harness.NCRYPT_SILENT_FLAG)
    assert calls == (1 if bad_size_query else 2)


def _sid_text_from_pointer(pointer: int) -> str:
    revision = harness.ctypes.c_ubyte.from_address(pointer).value
    count = harness.ctypes.c_ubyte.from_address(pointer + 1).value
    authority = int.from_bytes(harness.ctypes.string_at(pointer + 2, 6), "big")
    subs = [
        int.from_bytes(harness.ctypes.string_at(pointer + 8 + index * 4, 4), "little")
        for index in range(count)
    ]
    return "S-" + "-".join([str(revision), str(authority), *(str(x) for x in subs)])


def _fake_security_functions(total_length: int):
    retained_strings: list[object] = []

    def address(value) -> int:
        return harness.ctypes.cast(value, harness.ctypes.c_void_p).value

    def is_valid(descriptor) -> int:
        return 1

    def length(descriptor) -> int:
        return total_length

    def owner(descriptor, output, defaulted) -> int:
        base = address(descriptor)
        owner_offset = struct.unpack("<I", harness.ctypes.string_at(base + 4, 4))[0]
        harness.ctypes.cast(output, harness.ctypes.POINTER(harness.ctypes.c_void_p))[
            0
        ] = base + owner_offset
        harness.ctypes.cast(defaulted, harness.ctypes.POINTER(harness.ctypes.c_int))[
            0
        ] = 0
        return 1

    def control(descriptor, output, revision) -> int:
        base = address(descriptor)
        value = struct.unpack("<H", harness.ctypes.string_at(base + 2, 2))[0]
        harness.ctypes.cast(output, harness.ctypes.POINTER(harness.ctypes.c_uint16))[
            0
        ] = value
        harness.ctypes.cast(revision, harness.ctypes.POINTER(harness.ctypes.c_uint32))[
            0
        ] = 1
        return 1

    def dacl(descriptor, present, output, defaulted) -> int:
        base = address(descriptor)
        offset = struct.unpack("<I", harness.ctypes.string_at(base + 16, 4))[0]
        harness.ctypes.cast(present, harness.ctypes.POINTER(harness.ctypes.c_int))[
            0
        ] = 1
        harness.ctypes.cast(output, harness.ctypes.POINTER(harness.ctypes.c_void_p))[
            0
        ] = base + offset
        harness.ctypes.cast(defaulted, harness.ctypes.POINTER(harness.ctypes.c_int))[
            0
        ] = 0
        return 1

    def acl_information(acl, output, size, info_class) -> int:
        assert size == harness.ctypes.sizeof(harness._AclSizeInformation)
        assert info_class == 2
        base = address(acl)
        _, _, acl_size, ace_count, _ = struct.unpack(
            "<BBHHH", harness.ctypes.string_at(base, 8)
        )
        info = harness.ctypes.cast(
            output, harness.ctypes.POINTER(harness._AclSizeInformation)
        )[0]
        info.ace_count = ace_count
        info.acl_bytes_in_use = acl_size
        info.acl_bytes_free = 0
        return 1

    def get_ace(acl, index, output) -> int:
        pointer = address(acl) + 8
        for _ in range(index):
            pointer += struct.unpack("<H", harness.ctypes.string_at(pointer + 2, 2))[0]
        harness.ctypes.cast(output, harness.ctypes.POINTER(harness.ctypes.c_void_p))[
            0
        ] = pointer
        return 1

    def valid_sid(sid) -> int:
        pointer = address(sid)
        return int(
            harness.ctypes.c_ubyte.from_address(pointer).value == 1
            and 1 <= harness.ctypes.c_ubyte.from_address(pointer + 1).value <= 15
        )

    def sid_length(sid) -> int:
        return 8 + 4 * harness.ctypes.c_ubyte.from_address(address(sid) + 1).value

    def sid_to_string(sid, output) -> int:
        buffer = harness.ctypes.create_unicode_buffer(
            _sid_text_from_pointer(address(sid))
        )
        retained_strings.append(buffer)
        harness.ctypes.cast(output, harness.ctypes.POINTER(harness.ctypes.c_wchar_p))[
            0
        ] = harness.ctypes.cast(buffer, harness.ctypes.c_wchar_p)
        return 1

    return {
        "IsValidSecurityDescriptor": is_valid,
        "GetSecurityDescriptorLength": length,
        "GetSecurityDescriptorOwner": owner,
        "GetSecurityDescriptorControl": control,
        "GetSecurityDescriptorDacl": dacl,
        "GetAclInformation": acl_information,
        "GetAce": get_ace,
        "IsValidSid": valid_sid,
        "GetLengthSid": sid_length,
        "ConvertSidToStringSidW": sid_to_string,
        "LocalFree": lambda pointer: None,
    }


def test_native_security_decoder_accepts_exact_bounded_descriptor() -> None:
    value = harness.build_exact_security_descriptor_bytes()
    descriptor = harness.decode_native_security_descriptor(
        value, _fake_security_functions(len(value))
    )
    assert harness.verify_security_descriptor(descriptor) == tuple(
        sorted(
            _valid_descriptor().aces,
            key=lambda ace: (ace.ace_type, ace.ace_flags, ace.sid, ace.access_mask),
        )
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "owner-out-of-bounds",
        "dacl-out-of-bounds",
        "acl-size-out-of-bounds",
        "ace-size-out-of-bounds",
        "ace-size-short",
        "owner-sid-truncated",
        "ace-sid-truncated",
    ],
)
def test_native_security_decoder_rejects_bounds_before_pointer_callbacks(
    mutation: str,
) -> None:
    value = bytearray(harness.build_exact_security_descriptor_bytes())
    dacl_offset = struct.unpack_from("<I", value, 16)[0]
    if mutation == "owner-out-of-bounds":
        struct.pack_into("<I", value, 4, 0xFFFFFFFC)
    elif mutation == "dacl-out-of-bounds":
        struct.pack_into("<I", value, 16, len(value) + 4)
    elif mutation == "acl-size-out-of-bounds":
        struct.pack_into("<H", value, dacl_offset + 2, len(value))
    elif mutation == "ace-size-short":
        struct.pack_into("<H", value, dacl_offset + 8 + 2, 7)
    elif mutation == "ace-size-out-of-bounds":
        struct.pack_into("<H", value, dacl_offset + 8 + 2, 0xFFFC)
    elif mutation == "owner-sid-truncated":
        owner_offset = struct.unpack_from("<I", value, 4)[0]
        value[owner_offset + 1] = 15
    else:
        value[dacl_offset + 8 + 8 + 1] = 15

    callbacks: list[str] = []

    def forbidden(*args, **kwargs):
        callbacks.append("unsafe")
        raise AssertionError("pointer-taking callback reached malformed data")

    functions = {
        name: forbidden
        for name in (
            "IsValidSecurityDescriptor",
            "GetSecurityDescriptorLength",
            "GetSecurityDescriptorOwner",
            "GetSecurityDescriptorControl",
            "GetSecurityDescriptorDacl",
            "GetAclInformation",
            "GetAce",
            "IsValidSid",
            "GetLengthSid",
            "ConvertSidToStringSidW",
            "LocalFree",
        )
    }
    with pytest.raises(harness.HarnessContractError):
        harness.decode_native_security_descriptor(bytes(value), functions)
    assert callbacks == []
