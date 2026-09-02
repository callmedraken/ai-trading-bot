"""Inert Architecture-98 disposable Windows KSP validation harness.

This module freezes the test identities, native API contracts, evidence model,
and multi-session state machine.  Native execution is deliberately disabled in
source.  Importing it or invoking :func:`main` cannot open a provider or key.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import struct
import sys
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from dataclasses import fields as dataclass_fields
from enum import StrEnum
from pathlib import Path, PureWindowsPath
from typing import Any, Protocol

if os.name == "nt":
    from ctypes import wintypes
else:  # pragma: no cover - definitions remain inspectable off Windows
    wintypes = None  # type: ignore[assignment]


HARNESS_SCHEMA_VERSION = "p3-r1-ksp-disposable-test-evidence/v2"
PROVIDER_NAME = "Microsoft Software Key Storage Provider"
ALGORITHM_NAME = "ECDSA_P256"
ALGORITHM_GROUP = "ECDSA"
KEY_LENGTH_BITS = 256

TEST_CONTAINER_TEXT = "AITradingBot-P3R1-KSP-TEST-800CA51-v1"
PRODUCTION_CONTAINER_TEXT = "AITradingBot-P3R1-Recovery-v1"
FUTURE_EVIDENCE_ROOT = PureWindowsPath(r"F:\AI\p3-r1-ksp-disposable-test-v1")

TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"
ELEVATED_TEST_OPERATOR_SID = "S-1-5-21-1397534616-3988210162-180023805-1005"
ADMINISTRATORS_SID = "S-1-5-32-544"
LOCAL_SYSTEM_SID = "S-1-5-18"

# Read-only discovery found possible local non-admin accounts, but no distinct
# account was reviewed as suitable for this security test.  This is intentionally
# not caller-selectable and remains a fail-closed future architecture input.
ORDINARY_NONADMIN_TEST_SID: str | None = None
ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED = True

PRODUCTION_FORBIDDEN_ROOTS = (
    PureWindowsPath(r"F:\AITradingBot\Paper"),
    PureWindowsPath(r"F:\AITradingBot\.Paper.provisioning-v1"),
    PureWindowsPath(r"F:\AITradingBot\Authority"),
    PureWindowsPath(r"F:\AITradingBot\runtime"),
)

NCRYPT_MACHINE_KEY_FLAG = 0x00000020
NCRYPT_SILENT_FLAG = 0x00000040
NCRYPT_OVERWRITE_KEY_FLAG = 0x00000080
NCRYPT_PERSIST_FLAG = 0x80000000
NCRYPT_ALLOW_SIGNING_FLAG = 0x00000002
NCRYPT_MACHINE_CREATE_FLAGS = NCRYPT_MACHINE_KEY_FLAG
NCRYPT_MACHINE_REOPEN_FLAGS = NCRYPT_MACHINE_KEY_FLAG | NCRYPT_SILENT_FLAG
NCRYPT_CURRENT_USER_CREATE_FLAGS = 0
NCRYPT_CURRENT_USER_REOPEN_FLAGS = NCRYPT_SILENT_FLAG
NCRYPT_PROPERTY_SET_FLAGS = NCRYPT_PERSIST_FLAG | NCRYPT_SILENT_FLAG
NCRYPT_PROPERTY_GET_FLAGS = NCRYPT_SILENT_FLAG
NCRYPT_FINALIZE_FLAGS = NCRYPT_SILENT_FLAG
NCRYPT_PUBLIC_EXPORT_FLAGS = NCRYPT_SILENT_FLAG
NCRYPT_SECURITY_SET_FLAGS = 0x80000045
NCRYPT_SECURITY_GET_FLAGS = 0x00000045
NCRYPT_EXPORT_POLICY_NONE = 0
NCRYPT_KEY_TYPE_MACHINE = 0x00000020

NCRYPT_NAME_PROPERTY = "Name"
NCRYPT_UNIQUE_NAME_PROPERTY = "Unique Name"
NCRYPT_ALGORITHM_PROPERTY = "Algorithm Name"
NCRYPT_ALGORITHM_GROUP_PROPERTY = "Algorithm Group"
NCRYPT_LENGTH_PROPERTY = "Length"
NCRYPT_EXPORT_POLICY_PROPERTY = "Export Policy"
NCRYPT_KEY_USAGE_PROPERTY = "Key Usage"
NCRYPT_KEY_TYPE_PROPERTY = "Key Type"
NCRYPT_SECURITY_DESCR_SUPPORT_PROPERTY = "Security Descr Support"
NCRYPT_SECURITY_DESCR_PROPERTY = "Security Descr"

ACCESS_ALLOWED_ACE_TYPE = 0x00
CRYPTO_KEY_FULL_CONTROL = 0x001F019B
ACL_REVISION = 2
ACL_REVISION_DS = 4

SE_OWNER_DEFAULTED = 0x0001
SE_DACL_PRESENT = 0x0004
SE_DACL_DEFAULTED = 0x0008
SE_DACL_AUTO_INHERIT_REQ = 0x0100
SE_DACL_AUTO_INHERITED = 0x0400
SE_DACL_PROTECTED = 0x1000
SE_SELF_RELATIVE = 0x8000

BCRYPT_ECDSA_PUBLIC_P256_MAGIC = 0x31534345
BCRYPT_ECCPUBLIC_BLOB = "ECCPUBLICBLOB"
BCRYPT_ECCPRIVATE_BLOB = "ECCPRIVATEBLOB"
NCRYPT_OPAQUETRANSPORT_BLOB = "OpaqueTransport"
NCRYPT_PKCS8_PRIVATE_KEY_BLOB = "PKCS8_PRIVATEKEY"

# The only future opt-in boundary.  There is no CLI or environment override.
# A later reviewed security-effect checkpoint must replace this disabled design
# with its exact authorization before any native phase can load a Windows DLL.
_NATIVE_EFFECT_EXECUTION_AUTHORIZED = False
_NATIVE_EFFECT_AUTHORIZATION_ID = "NOT-AUTHORIZED-IN-800CA51-HARNESS"

_ZERO_SHA256 = "0" * 64
_P256_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_P256_A = _P256_P - 3
_P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B


class HarnessContractError(ValueError):
    """Raised when frozen harness or evidence semantics are violated."""


class NativeExecutionDisabled(RuntimeError):
    """Raised before any native API is loaded or called."""


class SecurityStatusError(RuntimeError):
    """Raised for every nonzero Windows CNG ``SECURITY_STATUS``."""

    def __init__(self, operation: str, status: int) -> None:
        self.operation = operation
        self.status = status & 0xFFFFFFFF
        super().__init__(f"{operation} failed with SECURITY_STATUS 0x{self.status:08X}")


class Phase(StrEnum):
    READ_ONLY_PREFLIGHT = "READ_ONLY_PREFLIGHT"
    MACHINE_CREATE_AND_VALIDATE = "MACHINE_CREATE_AND_VALIDATE"
    SHADOW_CREATE_AND_SCOPE_PROOF = "SHADOW_CREATE_AND_SCOPE_PROOF"
    ELEVATED_MACHINE_EFFECT_TEST = "ELEVATED_MACHINE_EFFECT_TEST"
    TRADING_DENIAL = "TRADING_DENIAL"
    ORDINARY_NONADMIN_DENIAL = "ORDINARY_NONADMIN_DENIAL"
    FINAL_EVIDENCE_RECONCILIATION = "FINAL_EVIDENCE_RECONCILIATION"


PHASE_ORDER = tuple(Phase)


class PhaseOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"
    BLOCKED = "BLOCKED"


class KeyScope(StrEnum):
    LOCAL_MACHINE = "local-machine"
    CURRENT_USER = "current-user"


class SignatureOutcome(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    ATTEMPTED_UNCERTAIN = "ATTEMPTED_UNCERTAIN"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class PrivateExportProbe(StrEnum):
    ECC_PRIVATE = BCRYPT_ECCPRIVATE_BLOB
    GENERIC_PRIVATE = "PRIVATEBLOB"
    OPAQUE_TRANSPORT = NCRYPT_OPAQUETRANSPORT_BLOB
    PKCS8_PRIVATE = NCRYPT_PKCS8_PRIVATE_KEY_BLOB


class PrivateExportProbeOutcome(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    ATTEMPTED_UNCERTAIN = "ATTEMPTED_UNCERTAIN"
    DENIED_AS_REQUIRED = "DENIED_AS_REQUIRED"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FAILED = "FAILED"


@dataclass(frozen=True)
class KeyIdentity:
    provider: str
    scope: KeyScope
    container: str
    operator_sid: str | None = None


MACHINE_TEST_KEY = KeyIdentity(
    provider=PROVIDER_NAME,
    scope=KeyScope.LOCAL_MACHINE,
    container=TEST_CONTAINER_TEXT,
)
CURRENT_USER_SHADOW_KEY = KeyIdentity(
    provider=PROVIDER_NAME,
    scope=KeyScope.CURRENT_USER,
    container=TEST_CONTAINER_TEXT,
    operator_sid=ELEVATED_TEST_OPERATOR_SID,
)


@dataclass(frozen=True)
class AceSemantic:
    ace_type: int
    ace_flags: int
    sid: str
    access_mask: int
    structurally_valid: bool = True
    trailing_bytes: bool = False


@dataclass(frozen=True)
class SecurityDescriptorSemantic:
    is_valid: bool
    owner_sid: str | None
    owner_defaulted: bool
    dacl_present: bool
    dacl_is_null: bool
    dacl_defaulted: bool
    control: int
    acl_revision: int
    aces: tuple[AceSemantic, ...]
    malformed: bool = False
    trailing_bytes: bool = False


@dataclass(frozen=True)
class KeyMetadata:
    identity: KeyIdentity
    key_type: int
    algorithm: str
    algorithm_group: str
    key_length_bits: int
    public_sec1: bytes


@dataclass(frozen=True)
class ReadOnlyPreflightCompletion:
    both_scope_absence_proved: bool
    future_evidence_root_absent: bool
    provider_security_descriptor_support: bool
    elevated_operator_sid: str


@dataclass(frozen=True)
class MachineValidationCompletion:
    machine_metadata: KeyMetadata
    exact_properties_verified: bool
    security_descriptor_verified: bool
    independent_reopen_verified: bool


@dataclass(frozen=True)
class ShadowScopeCompletion:
    machine_metadata: KeyMetadata
    shadow_metadata: KeyMetadata
    scope_non_substitution_verified: bool


@dataclass(frozen=True)
class ElevatedEffectCompletion:
    signature_verified_with_machine_public: bool
    private_export_denial_matrix_verified: bool


@dataclass(frozen=True)
class PrincipalDenialCompletion:
    actor_sid: str
    machine_open_denied: bool
    downstream_private_operations_unreachable: bool


@dataclass(frozen=True)
class FinalReconciliationCompletion:
    all_phase_evidence_reconciled: bool
    both_scope_qualified_keys_retained: bool
    cleanup_performed: bool


PhaseCompletion = (
    ReadOnlyPreflightCompletion
    | MachineValidationCompletion
    | ShadowScopeCompletion
    | ElevatedEffectCompletion
    | PrincipalDenialCompletion
    | FinalReconciliationCompletion
)


@dataclass(frozen=True)
class LifecycleEvidence:
    machine_creation_attempted: bool = False
    machine_created: bool = False
    shadow_creation_attempted: bool = False
    shadow_created: bool = False
    test_name_retired: bool = False


@dataclass(frozen=True)
class PrivateExportProbeResult:
    probe: PrivateExportProbe
    outcome: PrivateExportProbeOutcome = PrivateExportProbeOutcome.NOT_ATTEMPTED


INITIAL_PRIVATE_EXPORT_PROBE_RESULTS = tuple(
    PrivateExportProbeResult(probe) for probe in PrivateExportProbe
)


@dataclass(frozen=True)
class PhaseStateSnapshot:
    lifecycle: LifecycleEvidence
    completion: PhaseCompletion | None
    signature_outcome: SignatureOutcome
    signature_attempt_count: int
    private_export_probe_results: tuple[PrivateExportProbeResult, ...]


@dataclass(frozen=True)
class PhaseRecord:
    phase: Phase
    outcome: PhaseOutcome
    actor_sid: str
    previous_record_sha256: str
    state_snapshot: PhaseStateSnapshot
    state_snapshot_sha256: str
    record_sha256: str


@dataclass(frozen=True)
class HarnessEvidence:
    schema: str = HARNESS_SCHEMA_VERSION
    test_container: str = TEST_CONTAINER_TEXT
    future_evidence_root: str = str(FUTURE_EVIDENCE_ROOT)
    lifecycle: LifecycleEvidence = LifecycleEvidence()
    phases: tuple[PhaseRecord, ...] = ()
    signature_outcome: SignatureOutcome = SignatureOutcome.NOT_ATTEMPTED
    signature_attempt_count: int = 0
    private_export_probe_results: tuple[PrivateExportProbeResult, ...] = (
        INITIAL_PRIVATE_EXPORT_PROBE_RESULTS
    )


class NativePhaseOperations(Protocol):
    """Future effect implementation boundary; never invoked by this checkpoint."""

    def execute(self, phase: Phase, evidence: HarnessEvidence) -> HarnessEvidence:
        """Execute one already-authorized phase and return retained evidence."""


def _identity_alias(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold().strip()
    return "".join(character for character in normalized if character.isalnum())


def validate_test_container(text: str) -> str:
    """Require the one code-owned TEST name and reject production equivalence."""

    if text != TEST_CONTAINER_TEXT:
        raise HarnessContractError("test container is not the frozen source value")
    normalized = unicodedata.normalize("NFKC", text).casefold().strip()
    production = (
        unicodedata.normalize("NFKC", PRODUCTION_CONTAINER_TEXT).casefold().strip()
    )
    alias = _identity_alias(text)
    production_alias = _identity_alias(PRODUCTION_CONTAINER_TEXT)
    if (
        normalized == production
        or alias == production_alias
        or normalized.startswith(production)
        or alias.startswith(production_alias)
    ):
        raise HarnessContractError("test container could resolve as production")
    if "test" not in alias:
        raise HarnessContractError("test container is not visibly TEST-only")
    return text


def validate_key_identity(identity: KeyIdentity) -> KeyIdentity:
    """Validate an exact scope-qualified disposable key identity."""

    validate_test_container(identity.container)
    if identity.provider != PROVIDER_NAME:
        raise HarnessContractError("wrong KSP provider")
    if identity.scope is KeyScope.LOCAL_MACHINE:
        if identity.operator_sid is not None:
            raise HarnessContractError("machine identity must not carry a user SID")
        if identity != MACHINE_TEST_KEY:
            raise HarnessContractError("wrong machine TEST identity")
    elif identity.scope is KeyScope.CURRENT_USER:
        if identity.operator_sid != ELEVATED_TEST_OPERATOR_SID:
            raise HarnessContractError("wrong current-user operator SID")
        if identity != CURRENT_USER_SHADOW_KEY:
            raise HarnessContractError("wrong current-user shadow identity")
    else:  # pragma: no cover - enum closes this case
        raise HarnessContractError("unknown key scope")
    return identity


def validate_evidence_root(root: PureWindowsPath) -> PureWindowsPath:
    """Reject caller-selected roots and every protected production subtree."""

    if root != FUTURE_EVIDENCE_ROOT:
        raise HarnessContractError("evidence root is not the frozen future root")
    for protected in PRODUCTION_FORBIDDEN_ROOTS:
        if root == protected or root.is_relative_to(protected):
            raise HarnessContractError("evidence root intersects production")
    return root


def check_security_status(operation: str, status: int) -> None:
    """Require exact native success; no unchecked status conversion is allowed."""

    if not isinstance(status, int) or isinstance(status, bool):
        raise TypeError("SECURITY_STATUS must be converted explicitly to int")
    if status != 0:
        raise SecurityStatusError(operation, status)


def _validate_public_point(x_bytes: bytes, y_bytes: bytes) -> None:
    if len(x_bytes) != 32 or len(y_bytes) != 32:
        raise HarnessContractError("P-256 coordinates must each be 32 bytes")
    x = int.from_bytes(x_bytes, "big")
    y = int.from_bytes(y_bytes, "big")
    if x >= _P256_P or y >= _P256_P:
        raise HarnessContractError("P-256 coordinate is outside the field")
    if (pow(y, 2, _P256_P) - (pow(x, 3, _P256_P) + _P256_A * x + _P256_B)) % (_P256_P):
        raise HarnessContractError("public point is not on P-256")


def normalize_ecc_public_blob(blob: bytes) -> bytes:
    """Validate an exact P-256 BCRYPT_ECCPUBLIC_BLOB and return SEC1 bytes."""

    if len(blob) != 72:
        raise HarnessContractError("public blob must be exactly 72 bytes")
    magic, key_size = struct.unpack("<II", blob[:8])
    if magic != BCRYPT_ECDSA_PUBLIC_P256_MAGIC:
        raise HarnessContractError("wrong BCRYPT P-256 public magic")
    if key_size != 32:
        raise HarnessContractError("BCRYPT cbKey must equal 32")
    x_bytes = blob[8:40]
    y_bytes = blob[40:72]
    _validate_public_point(x_bytes, y_bytes)
    return b"\x04" + x_bytes + y_bytes


def verify_security_descriptor(
    descriptor: SecurityDescriptorSemantic,
) -> tuple[AceSemantic, AceSemantic]:
    """Verify Architecture-98 authority semantics, never raw byte equality."""

    if not descriptor.is_valid or descriptor.malformed or descriptor.trailing_bytes:
        raise HarnessContractError("invalid or malformed security descriptor")
    if descriptor.owner_sid != ADMINISTRATORS_SID or descriptor.owner_defaulted:
        raise HarnessContractError("owner must be non-defaulted Administrators")
    if not descriptor.dacl_present or descriptor.dacl_is_null:
        raise HarnessContractError("DACL must be present and non-NULL")
    if descriptor.dacl_defaulted:
        raise HarnessContractError("DACL must not be defaulted")
    required = SE_DACL_PRESENT | SE_DACL_PROTECTED
    forbidden = (
        SE_OWNER_DEFAULTED
        | SE_DACL_DEFAULTED
        | SE_DACL_AUTO_INHERIT_REQ
        | SE_DACL_AUTO_INHERITED
    )
    if descriptor.control & required != required or descriptor.control & forbidden:
        raise HarnessContractError("security descriptor control state is wrong")
    allowed_control = required | SE_SELF_RELATIVE
    if descriptor.control & ~allowed_control:
        raise HarnessContractError("unexpected security descriptor control bit")
    if descriptor.acl_revision not in (ACL_REVISION, ACL_REVISION_DS):
        raise HarnessContractError("invalid ACL revision")
    if len(descriptor.aces) != 2:
        raise HarnessContractError("DACL must contain exactly two ACEs")

    expected = (
        AceSemantic(
            ACCESS_ALLOWED_ACE_TYPE,
            0,
            LOCAL_SYSTEM_SID,
            CRYPTO_KEY_FULL_CONTROL,
        ),
        AceSemantic(
            ACCESS_ALLOWED_ACE_TYPE,
            0,
            ADMINISTRATORS_SID,
            CRYPTO_KEY_FULL_CONTROL,
        ),
    )
    observed: list[AceSemantic] = []
    for ace in descriptor.aces:
        if not ace.structurally_valid or ace.trailing_bytes:
            raise HarnessContractError("malformed ACE")
        if ace.ace_type != ACCESS_ALLOWED_ACE_TYPE:
            raise HarnessContractError("only explicit allow ACEs are accepted")
        if ace.ace_flags != 0:
            raise HarnessContractError("ACE flags must be zero")
        if ace.access_mask != CRYPTO_KEY_FULL_CONTROL:
            raise HarnessContractError("ACE mask is not the frozen concrete mask")
        if ace.sid not in (LOCAL_SYSTEM_SID, ADMINISTRATORS_SID):
            raise HarnessContractError("unexpected ACE principal")
        observed.append(ace)
    observed_tuple = tuple(
        sorted(
            observed,
            key=lambda item: (
                item.ace_type,
                item.ace_flags,
                item.sid,
                item.access_mask,
            ),
        )
    )
    if observed_tuple != expected:
        raise HarnessContractError("missing, duplicate, or unexpected ACE")
    return observed_tuple


def verify_scope_non_substitution(
    machine: KeyMetadata, shadow: KeyMetadata
) -> tuple[bytes, bytes]:
    """Prove same text in different scopes resolves two distinct key identities."""

    validate_key_identity(machine.identity)
    validate_key_identity(shadow.identity)
    if (
        machine.identity is not MACHINE_TEST_KEY
        and machine.identity != MACHINE_TEST_KEY
    ):
        raise HarnessContractError("machine metadata is not MACHINE_TEST_KEY")
    if shadow.identity is not CURRENT_USER_SHADOW_KEY and (
        shadow.identity != CURRENT_USER_SHADOW_KEY
    ):
        raise HarnessContractError("shadow metadata is not CURRENT_USER_SHADOW_KEY")
    for metadata in (machine, shadow):
        if metadata.algorithm != ALGORITHM_NAME:
            raise HarnessContractError("wrong key algorithm")
        if metadata.algorithm_group != ALGORITHM_GROUP:
            raise HarnessContractError("wrong key algorithm group")
        if metadata.key_length_bits != KEY_LENGTH_BITS:
            raise HarnessContractError("wrong key length")
        if len(metadata.public_sec1) != 65 or metadata.public_sec1[0] != 0x04:
            raise HarnessContractError("invalid SEC1 public identity")
        _validate_public_point(metadata.public_sec1[1:33], metadata.public_sec1[33:])
    if machine.key_type != NCRYPT_KEY_TYPE_MACHINE:
        raise HarnessContractError("machine key type is not exactly 0x20")
    if shadow.key_type & NCRYPT_MACHINE_KEY_FLAG:
        raise HarnessContractError("shadow key type incorrectly carries machine scope")
    if machine.public_sec1 == shadow.public_sec1:
        raise HarnessContractError("machine and shadow public identities must differ")
    return machine.public_sec1, shadow.public_sec1


def validate_lifecycle(lifecycle: LifecycleEvidence) -> LifecycleEvidence:
    """Enforce one-way two-scope creation and retirement semantics."""

    if lifecycle.machine_created and not lifecycle.machine_creation_attempted:
        raise HarnessContractError("machine created without an attempted creation")
    if lifecycle.shadow_creation_attempted and not lifecycle.machine_created:
        raise HarnessContractError("shadow attempt requires a created machine key")
    if lifecycle.shadow_created and not lifecycle.shadow_creation_attempted:
        raise HarnessContractError("shadow created without an attempted creation")
    if lifecycle.shadow_created and not lifecycle.machine_created:
        raise HarnessContractError("shadow created without a retained machine key")
    any_attempt = (
        lifecycle.machine_creation_attempted or lifecycle.shadow_creation_attempted
    )
    if lifecycle.test_name_retired != any_attempt:
        raise HarnessContractError("the name must retire at the first create attempt")
    return lifecycle


def begin_machine_creation(evidence: HarnessEvidence) -> HarnessEvidence:
    _require_last_success(evidence, Phase.READ_ONLY_PREFLIGHT)
    if evidence.lifecycle.machine_creation_attempted:
        raise HarnessContractError("machine key creation is never retried")
    lifecycle = replace(
        evidence.lifecycle,
        machine_creation_attempted=True,
        test_name_retired=True,
    )
    return replace(evidence, lifecycle=validate_lifecycle(lifecycle))


def record_machine_created(evidence: HarnessEvidence) -> HarnessEvidence:
    if not evidence.lifecycle.machine_creation_attempted:
        raise HarnessContractError("machine creation was not begun")
    if evidence.lifecycle.machine_created:
        raise HarnessContractError("machine creation was already recorded")
    lifecycle = replace(evidence.lifecycle, machine_created=True)
    return replace(evidence, lifecycle=validate_lifecycle(lifecycle))


def begin_shadow_creation(evidence: HarnessEvidence) -> HarnessEvidence:
    if not evidence.lifecycle.machine_created:
        raise HarnessContractError("shadow is unreachable without the machine key")
    _require_last_success(evidence, Phase.MACHINE_CREATE_AND_VALIDATE)
    if evidence.lifecycle.shadow_creation_attempted:
        raise HarnessContractError("shadow key creation is never retried")
    lifecycle = replace(
        evidence.lifecycle,
        shadow_creation_attempted=True,
        test_name_retired=True,
    )
    return replace(evidence, lifecycle=validate_lifecycle(lifecycle))


def record_shadow_created(evidence: HarnessEvidence) -> HarnessEvidence:
    if not evidence.lifecycle.shadow_creation_attempted:
        raise HarnessContractError("shadow creation was not begun")
    if evidence.lifecycle.shadow_created:
        raise HarnessContractError("shadow creation was already recorded")
    lifecycle = replace(evidence.lifecycle, shadow_created=True)
    return replace(evidence, lifecycle=validate_lifecycle(lifecycle))


def _expected_actor(phase: Phase) -> str:
    if phase is Phase.TRADING_DENIAL:
        return TRADING_SID
    if phase is Phase.ORDINARY_NONADMIN_DENIAL:
        if ORDINARY_NONADMIN_TEST_SID is None:
            raise HarnessContractError(
                "ordinary non-admin identity remains blocked and cannot be claimed"
            )
        return ORDINARY_NONADMIN_TEST_SID
    return ELEVATED_TEST_OPERATOR_SID


def _metadata_payload(metadata: KeyMetadata) -> dict[str, Any]:
    return {
        "algorithm": metadata.algorithm,
        "algorithm_group": metadata.algorithm_group,
        "identity": {
            "container": metadata.identity.container,
            "operator_sid": metadata.identity.operator_sid,
            "provider": metadata.identity.provider,
            "scope": metadata.identity.scope.value,
        },
        "key_length_bits": metadata.key_length_bits,
        "key_type": metadata.key_type,
        "public_sec1_hex": metadata.public_sec1.hex(),
    }


def _completion_payload(completion: PhaseCompletion | None) -> dict[str, Any] | None:
    if completion is None:
        return None
    if isinstance(completion, ReadOnlyPreflightCompletion):
        return {
            "both_scope_absence_proved": completion.both_scope_absence_proved,
            "elevated_operator_sid": completion.elevated_operator_sid,
            "future_evidence_root_absent": completion.future_evidence_root_absent,
            "kind": "read-only-preflight/v1",
            "provider_security_descriptor_support": (
                completion.provider_security_descriptor_support
            ),
        }
    if isinstance(completion, MachineValidationCompletion):
        return {
            "exact_properties_verified": completion.exact_properties_verified,
            "independent_reopen_verified": completion.independent_reopen_verified,
            "kind": "machine-validation/v1",
            "machine_metadata": _metadata_payload(completion.machine_metadata),
            "security_descriptor_verified": completion.security_descriptor_verified,
        }
    if isinstance(completion, ShadowScopeCompletion):
        return {
            "kind": "shadow-scope/v1",
            "machine_metadata": _metadata_payload(completion.machine_metadata),
            "scope_non_substitution_verified": (
                completion.scope_non_substitution_verified
            ),
            "shadow_metadata": _metadata_payload(completion.shadow_metadata),
        }
    if isinstance(completion, ElevatedEffectCompletion):
        return {
            "kind": "elevated-effect/v1",
            "private_export_denial_matrix_verified": (
                completion.private_export_denial_matrix_verified
            ),
            "signature_verified_with_machine_public": (
                completion.signature_verified_with_machine_public
            ),
        }
    if isinstance(completion, PrincipalDenialCompletion):
        return {
            "actor_sid": completion.actor_sid,
            "downstream_private_operations_unreachable": (
                completion.downstream_private_operations_unreachable
            ),
            "kind": "principal-denial/v1",
            "machine_open_denied": completion.machine_open_denied,
        }
    if isinstance(completion, FinalReconciliationCompletion):
        return {
            "all_phase_evidence_reconciled": (completion.all_phase_evidence_reconciled),
            "both_scope_qualified_keys_retained": (
                completion.both_scope_qualified_keys_retained
            ),
            "cleanup_performed": completion.cleanup_performed,
            "kind": "final-reconciliation/v1",
        }
    raise TypeError("unknown phase completion type")


def _probe_results_payload(
    results: tuple[PrivateExportProbeResult, ...],
) -> list[dict[str, str]]:
    return [
        {"outcome": result.outcome.value, "probe": result.probe.value}
        for result in results
    ]


def _snapshot_payload(snapshot: PhaseStateSnapshot) -> dict[str, Any]:
    return {
        "completion": _completion_payload(snapshot.completion),
        "lifecycle": {
            "machine_created": snapshot.lifecycle.machine_created,
            "machine_creation_attempted": (
                snapshot.lifecycle.machine_creation_attempted
            ),
            "shadow_created": snapshot.lifecycle.shadow_created,
            "shadow_creation_attempted": snapshot.lifecycle.shadow_creation_attempted,
            "test_name_retired": snapshot.lifecycle.test_name_retired,
        },
        "private_export_probe_results": _probe_results_payload(
            snapshot.private_export_probe_results
        ),
        "signature_attempt_count": snapshot.signature_attempt_count,
        "signature_outcome": snapshot.signature_outcome.value,
    }


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_digest(snapshot: PhaseStateSnapshot) -> str:
    return _canonical_digest(_snapshot_payload(snapshot))


def _record_digest(
    phase: Phase,
    outcome: PhaseOutcome,
    actor_sid: str,
    previous_record_sha256: str,
    state_snapshot_sha256: str,
) -> str:
    return _canonical_digest(
        {
            "actor_sid": actor_sid,
            "outcome": outcome.value,
            "phase": phase.value,
            "previous_record_sha256": previous_record_sha256,
            "state_snapshot_sha256": state_snapshot_sha256,
        }
    )


def _validate_signature_state(outcome: SignatureOutcome, attempt_count: int) -> None:
    if attempt_count not in (0, 1):
        raise HarnessContractError("signature attempt count must be zero or one")
    if (attempt_count == 0 and outcome is not SignatureOutcome.NOT_ATTEMPTED) or (
        attempt_count == 1 and outcome is SignatureOutcome.NOT_ATTEMPTED
    ):
        raise HarnessContractError("signature state and attempt count disagree")


def _validate_probe_results(
    results: tuple[PrivateExportProbeResult, ...],
) -> None:
    if tuple(result.probe for result in results) != tuple(PrivateExportProbe):
        raise HarnessContractError(
            "private-export probe results must contain the exact ordered matrix"
        )
    if len({result.probe for result in results}) != len(results):
        raise HarnessContractError("private-export probes cannot be duplicated")


def _all_probes_not_attempted(
    results: tuple[PrivateExportProbeResult, ...],
) -> bool:
    return all(
        result.outcome is PrivateExportProbeOutcome.NOT_ATTEMPTED for result in results
    )


def _all_probes_denied_as_required(
    results: tuple[PrivateExportProbeResult, ...],
) -> bool:
    return all(
        result.outcome is PrivateExportProbeOutcome.DENIED_AS_REQUIRED
        for result in results
    )


def _validate_metadata_common(metadata: KeyMetadata) -> None:
    validate_key_identity(metadata.identity)
    if metadata.algorithm != ALGORITHM_NAME:
        raise HarnessContractError("wrong key algorithm")
    if metadata.algorithm_group != ALGORITHM_GROUP:
        raise HarnessContractError("wrong key algorithm group")
    if metadata.key_length_bits != KEY_LENGTH_BITS:
        raise HarnessContractError("wrong key length")
    if len(metadata.public_sec1) != 65 or metadata.public_sec1[0] != 0x04:
        raise HarnessContractError("invalid SEC1 public identity")
    _validate_public_point(metadata.public_sec1[1:33], metadata.public_sec1[33:])


def _validate_phase_snapshot(
    phase: Phase,
    outcome: PhaseOutcome,
    actor_sid: str,
    snapshot: PhaseStateSnapshot,
    prior_records: tuple[PhaseRecord, ...],
) -> None:
    validate_lifecycle(snapshot.lifecycle)
    _validate_signature_state(
        snapshot.signature_outcome, snapshot.signature_attempt_count
    )
    _validate_probe_results(snapshot.private_export_probe_results)
    if any(record.outcome is not PhaseOutcome.SUCCEEDED for record in prior_records):
        raise HarnessContractError("a terminal predecessor cannot have a successor")

    completion = snapshot.completion
    if outcome is not PhaseOutcome.SUCCEEDED:
        if completion is not None:
            raise HarnessContractError(
                "terminal phase outcomes cannot claim completion"
            )
        if phase is Phase.READ_ONLY_PREFLIGHT:
            if snapshot.lifecycle != LifecycleEvidence():
                raise HarnessContractError("failed preflight cannot follow key effects")
        elif phase is Phase.MACHINE_CREATE_AND_VALIDATE:
            if (
                not snapshot.lifecycle.machine_creation_attempted
                or not snapshot.lifecycle.test_name_retired
                or snapshot.lifecycle.shadow_creation_attempted
            ):
                raise HarnessContractError("terminal machine state is incomplete")
        elif phase is Phase.SHADOW_CREATE_AND_SCOPE_PROOF:
            if (
                not snapshot.lifecycle.machine_created
                or not snapshot.lifecycle.shadow_creation_attempted
                or not snapshot.lifecycle.test_name_retired
            ):
                raise HarnessContractError("terminal shadow state is incomplete")
        elif not (
            snapshot.lifecycle.machine_created and snapshot.lifecycle.shadow_created
        ):
            raise HarnessContractError("later terminal state must retain both keys")
        return

    if phase is Phase.READ_ONLY_PREFLIGHT:
        if not isinstance(completion, ReadOnlyPreflightCompletion):
            raise HarnessContractError("preflight success lacks its completion proof")
        if snapshot.lifecycle != LifecycleEvidence():
            raise HarnessContractError("preflight success cannot contain key effects")
        if snapshot.signature_attempt_count or not _all_probes_not_attempted(
            snapshot.private_export_probe_results
        ):
            raise HarnessContractError(
                "preflight success cannot contain effect attempts"
            )
        if not (
            completion.both_scope_absence_proved
            and completion.future_evidence_root_absent
            and completion.provider_security_descriptor_support
            and completion.elevated_operator_sid == ELEVATED_TEST_OPERATOR_SID
        ):
            raise HarnessContractError("preflight completion proof is incomplete")
        return

    if phase is Phase.MACHINE_CREATE_AND_VALIDATE:
        if not isinstance(completion, MachineValidationCompletion):
            raise HarnessContractError("machine success lacks its completion proof")
        if snapshot.lifecycle != LifecycleEvidence(
            machine_creation_attempted=True,
            machine_created=True,
            test_name_retired=True,
        ):
            raise HarnessContractError("machine success lifecycle is not exact")
        _validate_metadata_common(completion.machine_metadata)
        if (
            completion.machine_metadata.identity != MACHINE_TEST_KEY
            or completion.machine_metadata.key_type != NCRYPT_KEY_TYPE_MACHINE
            or not completion.exact_properties_verified
            or not completion.security_descriptor_verified
            or not completion.independent_reopen_verified
        ):
            raise HarnessContractError("machine completion proof is incomplete")
        if snapshot.signature_attempt_count or not _all_probes_not_attempted(
            snapshot.private_export_probe_results
        ):
            raise HarnessContractError("machine phase cannot contain effect attempts")
        return

    if phase is Phase.SHADOW_CREATE_AND_SCOPE_PROOF:
        if not isinstance(completion, ShadowScopeCompletion):
            raise HarnessContractError("shadow success lacks its completion proof")
        if snapshot.lifecycle != LifecycleEvidence(
            machine_creation_attempted=True,
            machine_created=True,
            shadow_creation_attempted=True,
            shadow_created=True,
            test_name_retired=True,
        ):
            raise HarnessContractError("shadow success lifecycle is not exact")
        verify_scope_non_substitution(
            completion.machine_metadata, completion.shadow_metadata
        )
        if not completion.scope_non_substitution_verified:
            raise HarnessContractError("scope non-substitution proof is absent")
        if snapshot.signature_attempt_count or not _all_probes_not_attempted(
            snapshot.private_export_probe_results
        ):
            raise HarnessContractError("shadow phase cannot contain effect attempts")
        return

    if not (snapshot.lifecycle.machine_created and snapshot.lifecycle.shadow_created):
        raise HarnessContractError("later phase success must retain both TEST keys")

    if phase is Phase.ELEVATED_MACHINE_EFFECT_TEST:
        if not isinstance(completion, ElevatedEffectCompletion):
            raise HarnessContractError("elevated success lacks its completion proof")
        if (
            snapshot.signature_attempt_count != 1
            or snapshot.signature_outcome is not SignatureOutcome.SUCCEEDED
            or not _all_probes_denied_as_required(snapshot.private_export_probe_results)
            or not completion.signature_verified_with_machine_public
            or not completion.private_export_denial_matrix_verified
        ):
            raise HarnessContractError("elevated effect completion is not exact")
        return

    if phase in (Phase.TRADING_DENIAL, Phase.ORDINARY_NONADMIN_DENIAL):
        if not isinstance(completion, PrincipalDenialCompletion):
            raise HarnessContractError("denial success lacks its completion proof")
        if (
            completion.actor_sid != actor_sid
            or not completion.machine_open_denied
            or not completion.downstream_private_operations_unreachable
        ):
            raise HarnessContractError("principal denial completion is incomplete")
        if (
            snapshot.signature_outcome is not SignatureOutcome.SUCCEEDED
            or not _all_probes_denied_as_required(snapshot.private_export_probe_results)
        ):
            raise HarnessContractError("denial phase has unresolved elevated effects")
        return

    if phase is Phase.FINAL_EVIDENCE_RECONCILIATION:
        if not isinstance(completion, FinalReconciliationCompletion):
            raise HarnessContractError("final success lacks its completion proof")
        if len(prior_records) != len(PHASE_ORDER) - 1:
            raise HarnessContractError("final reconciliation has missing phases")
        if (
            not completion.all_phase_evidence_reconciled
            or not completion.both_scope_qualified_keys_retained
            or completion.cleanup_performed
            or snapshot.signature_outcome is not SignatureOutcome.SUCCEEDED
            or not _all_probes_denied_as_required(snapshot.private_export_probe_results)
        ):
            raise HarnessContractError("final reconciliation is incomplete")
        return
    raise HarnessContractError("unknown phase")


def _current_snapshot(
    evidence: HarnessEvidence,
    completion: PhaseCompletion | None,
) -> PhaseStateSnapshot:
    return PhaseStateSnapshot(
        lifecycle=evidence.lifecycle,
        completion=completion,
        signature_outcome=evidence.signature_outcome,
        signature_attempt_count=evidence.signature_attempt_count,
        private_export_probe_results=evidence.private_export_probe_results,
    )


def validate_phase_result_eligibility(
    evidence: HarnessEvidence,
    phase: Phase,
    outcome: PhaseOutcome,
    completion: PhaseCompletion | None,
) -> PhaseStateSnapshot:
    """Require exact retained state before recording a phase result."""

    validate_harness_evidence(evidence)
    if evidence.phases and evidence.phases[-1].outcome is not PhaseOutcome.SUCCEEDED:
        raise HarnessContractError("a failed, blocked, or uncertain phase is terminal")
    next_index = len(evidence.phases)
    if next_index >= len(PHASE_ORDER) or PHASE_ORDER[next_index] is not phase:
        raise HarnessContractError("phase is missing, duplicated, or out of order")
    actor_sid = _expected_actor(phase)
    snapshot = _current_snapshot(evidence, completion)
    _validate_phase_snapshot(phase, outcome, actor_sid, snapshot, evidence.phases)
    return snapshot


def append_phase_result(
    evidence: HarnessEvidence,
    phase: Phase,
    outcome: PhaseOutcome,
    completion: PhaseCompletion | None = None,
) -> HarnessEvidence:
    """Append one validated result and its immutable security-state snapshot."""

    snapshot = validate_phase_result_eligibility(evidence, phase, outcome, completion)
    actor_sid = _expected_actor(phase)
    previous = evidence.phases[-1].record_sha256 if evidence.phases else _ZERO_SHA256
    state_digest = _snapshot_digest(snapshot)
    digest = _record_digest(phase, outcome, actor_sid, previous, state_digest)
    record = PhaseRecord(
        phase,
        outcome,
        actor_sid,
        previous,
        snapshot,
        state_digest,
        digest,
    )
    updated = replace(evidence, phases=(*evidence.phases, record))
    return validate_harness_evidence(updated)


def _require_last_success(evidence: HarnessEvidence, phase: Phase) -> None:
    validate_harness_evidence(evidence)
    if not evidence.phases:
        raise HarnessContractError(f"{phase.value} evidence is absent")
    latest = evidence.phases[-1]
    if latest.phase is not phase or latest.outcome is not PhaseOutcome.SUCCEEDED:
        raise HarnessContractError(f"{phase.value} is not the latest retained success")


def _lifecycle_contains(
    current: LifecycleEvidence,
    committed: LifecycleEvidence,
) -> bool:
    return all(
        not getattr(committed, field.name) or getattr(current, field.name)
        for field in dataclass_fields(LifecycleEvidence)
    )


def _outcome_contains(current: StrEnum, committed: StrEnum) -> bool:
    if committed.value == "NOT_ATTEMPTED":
        return True
    if committed.value == "ATTEMPTED_UNCERTAIN":
        return current.value != "NOT_ATTEMPTED"
    return current is committed


def validate_harness_evidence(evidence: HarnessEvidence) -> HarnessEvidence:
    """Validate fixed state, immutable phase snapshots, and digest linkage."""

    if evidence.schema != HARNESS_SCHEMA_VERSION:
        raise HarnessContractError("wrong evidence schema")
    validate_test_container(evidence.test_container)
    validate_evidence_root(PureWindowsPath(evidence.future_evidence_root))
    validate_lifecycle(evidence.lifecycle)
    _validate_signature_state(
        evidence.signature_outcome, evidence.signature_attempt_count
    )
    _validate_probe_results(evidence.private_export_probe_results)

    previous = _ZERO_SHA256
    for index, record in enumerate(evidence.phases):
        if index >= len(PHASE_ORDER) or record.phase is not PHASE_ORDER[index]:
            raise HarnessContractError("evidence phase order is invalid")
        if record.actor_sid != _expected_actor(record.phase):
            raise HarnessContractError("phase actor SID is not the frozen identity")
        if record.previous_record_sha256 != previous:
            raise HarnessContractError("phase chain predecessor digest is invalid")
        expected_state_digest = _snapshot_digest(record.state_snapshot)
        if record.state_snapshot_sha256 != expected_state_digest:
            raise HarnessContractError("phase state snapshot digest is invalid")
        expected = _record_digest(
            record.phase,
            record.outcome,
            record.actor_sid,
            record.previous_record_sha256,
            record.state_snapshot_sha256,
        )
        if record.record_sha256 != expected:
            raise HarnessContractError("phase record digest is invalid")
        if index < len(evidence.phases) - 1 and (
            record.outcome is not PhaseOutcome.SUCCEEDED
        ):
            raise HarnessContractError("terminal phase has a successor")
        _validate_phase_snapshot(
            record.phase,
            record.outcome,
            record.actor_sid,
            record.state_snapshot,
            evidence.phases[:index],
        )
        if not _lifecycle_contains(evidence.lifecycle, record.state_snapshot.lifecycle):
            raise HarnessContractError(
                "current lifecycle regressed from committed state"
            )
        if (
            evidence.signature_attempt_count
            < record.state_snapshot.signature_attempt_count
        ):
            raise HarnessContractError("current signature count regressed")
        if not _outcome_contains(
            evidence.signature_outcome, record.state_snapshot.signature_outcome
        ):
            raise HarnessContractError(
                "current signature state contradicts its snapshot"
            )
        for current_probe, committed_probe in zip(
            evidence.private_export_probe_results,
            record.state_snapshot.private_export_probe_results,
            strict=True,
        ):
            if not _outcome_contains(current_probe.outcome, committed_probe.outcome):
                raise HarnessContractError(
                    "current private-export state contradicts its snapshot"
                )
        previous = record.record_sha256
    return evidence


def determine_next_phase(evidence: HarnessEvidence) -> Phase:
    """Return the one phase eligible for native dispatch from retained state."""

    validate_harness_evidence(evidence)
    if evidence.phases and evidence.phases[-1].outcome is not PhaseOutcome.SUCCEEDED:
        raise HarnessContractError("terminal predecessor blocks native dispatch")
    if len(evidence.phases) >= len(PHASE_ORDER):
        raise HarnessContractError("all phases are already complete")
    phase = PHASE_ORDER[len(evidence.phases)]
    lifecycle = evidence.lifecycle

    if phase is Phase.READ_ONLY_PREFLIGHT:
        if (
            lifecycle != LifecycleEvidence()
            or evidence.signature_attempt_count
            or not _all_probes_not_attempted(evidence.private_export_probe_results)
        ):
            raise HarnessContractError("preflight dispatch state is not pristine")
    elif phase is Phase.MACHINE_CREATE_AND_VALIDATE:
        if lifecycle != LifecycleEvidence(
            machine_creation_attempted=True,
            test_name_retired=True,
        ):
            raise HarnessContractError("machine dispatch lacks its durable attempt")
    elif phase is Phase.SHADOW_CREATE_AND_SCOPE_PROOF:
        if lifecycle != LifecycleEvidence(
            machine_creation_attempted=True,
            machine_created=True,
            shadow_creation_attempted=True,
            test_name_retired=True,
        ):
            raise HarnessContractError("shadow dispatch lacks its durable attempt")
    elif phase is Phase.ELEVATED_MACHINE_EFFECT_TEST:
        if not (lifecycle.machine_created and lifecycle.shadow_created):
            raise HarnessContractError("elevated dispatch requires both retained keys")
        if evidence.signature_attempt_count or not _all_probes_not_attempted(
            evidence.private_export_probe_results
        ):
            raise HarnessContractError("elevated effect dispatch cannot be retried")
    elif phase is Phase.TRADING_DENIAL:
        if (
            evidence.signature_outcome is not SignatureOutcome.SUCCEEDED
            or not _all_probes_denied_as_required(evidence.private_export_probe_results)
        ):
            raise HarnessContractError("trading denial has unresolved elevated effects")
    elif phase is Phase.ORDINARY_NONADMIN_DENIAL:
        _expected_actor(phase)
    elif phase is Phase.FINAL_EVIDENCE_RECONCILIATION:
        if any(
            record.outcome is not PhaseOutcome.SUCCEEDED for record in evidence.phases
        ):
            raise HarnessContractError(
                "final reconciliation has a terminal predecessor"
            )
        if (
            evidence.signature_outcome is not SignatureOutcome.SUCCEEDED
            or not _all_probes_denied_as_required(evidence.private_export_probe_results)
        ):
            raise HarnessContractError("final reconciliation has unresolved effects")
    return phase


def validate_phase_dispatch_eligibility(
    phase: Phase,
    evidence: HarnessEvidence,
) -> Phase:
    """Require the requested phase to be the exact sole legal next dispatch."""

    expected = determine_next_phase(evidence)
    if phase is not expected:
        raise HarnessContractError(
            f"requested {phase.value}; only {expected.value} is eligible"
        )
    return phase


def begin_test_signature(
    evidence: HarnessEvidence,
    identity: KeyIdentity,
) -> HarnessEvidence:
    """Consume the single machine TEST signing attempt before a native call."""

    validate_key_identity(identity)
    if identity != MACHINE_TEST_KEY:
        raise HarnessContractError("only MACHINE_TEST_KEY may sign")
    _require_last_success(evidence, Phase.SHADOW_CREATE_AND_SCOPE_PROOF)
    if evidence.signature_attempt_count != 0:
        raise HarnessContractError("the single TEST signing attempt is consumed")
    return replace(
        evidence,
        signature_outcome=SignatureOutcome.ATTEMPTED_UNCERTAIN,
        signature_attempt_count=1,
    )


def record_test_signature_outcome(
    evidence: HarnessEvidence,
    outcome: SignatureOutcome,
) -> HarnessEvidence:
    validate_harness_evidence(evidence)
    if evidence.signature_attempt_count != 1:
        raise HarnessContractError("no TEST signing attempt is retained")
    if evidence.signature_outcome is not SignatureOutcome.ATTEMPTED_UNCERTAIN:
        raise HarnessContractError("the signing outcome is already final")
    if outcome not in (SignatureOutcome.SUCCEEDED, SignatureOutcome.FAILED):
        raise HarnessContractError("uncertainty remains retained, not rewritten")
    return replace(evidence, signature_outcome=outcome)


def begin_private_export_denial_probe(
    evidence: HarnessEvidence,
    identity: KeyIdentity,
    probe: PrivateExportProbe,
) -> HarnessEvidence:
    """Route future private-export denial probes only to MACHINE_TEST_KEY."""

    validate_key_identity(identity)
    if identity != MACHINE_TEST_KEY:
        raise HarnessContractError("shadow private export is structurally forbidden")
    _require_last_success(evidence, Phase.SHADOW_CREATE_AND_SCOPE_PROOF)
    results = list(evidence.private_export_probe_results)
    index = tuple(PrivateExportProbe).index(probe)
    if results[index].outcome is not PrivateExportProbeOutcome.NOT_ATTEMPTED:
        raise HarnessContractError("private-export denial probes are never retried")
    results[index] = PrivateExportProbeResult(
        probe, PrivateExportProbeOutcome.ATTEMPTED_UNCERTAIN
    )
    return replace(evidence, private_export_probe_results=tuple(results))


def record_private_export_probe_outcome(
    evidence: HarnessEvidence,
    probe: PrivateExportProbe,
    outcome: PrivateExportProbeOutcome,
) -> HarnessEvidence:
    """Record one terminal sanitized result without permitting a retry."""

    validate_harness_evidence(evidence)
    if outcome not in (
        PrivateExportProbeOutcome.DENIED_AS_REQUIRED,
        PrivateExportProbeOutcome.UNSUPPORTED_FORMAT,
        PrivateExportProbeOutcome.FAILED,
    ):
        raise HarnessContractError("probe outcome must be terminal and explicit")
    results = list(evidence.private_export_probe_results)
    index = tuple(PrivateExportProbe).index(probe)
    if results[index].outcome is not PrivateExportProbeOutcome.ATTEMPTED_UNCERTAIN:
        raise HarnessContractError("probe was not durably marked uncertain")
    results[index] = PrivateExportProbeResult(probe, outcome)
    return replace(evidence, private_export_probe_results=tuple(results))


def _evidence_payload(evidence: HarnessEvidence) -> dict[str, Any]:
    validate_harness_evidence(evidence)
    return {
        "future_evidence_root": evidence.future_evidence_root,
        "lifecycle": asdict(evidence.lifecycle),
        "phases": [
            {
                "actor_sid": record.actor_sid,
                "outcome": record.outcome.value,
                "phase": record.phase.value,
                "previous_record_sha256": record.previous_record_sha256,
                "record_sha256": record.record_sha256,
                "state_snapshot": _snapshot_payload(record.state_snapshot),
                "state_snapshot_sha256": record.state_snapshot_sha256,
            }
            for record in evidence.phases
        ],
        "private_export_probe_results": _probe_results_payload(
            evidence.private_export_probe_results
        ),
        "schema": evidence.schema,
        "signature_attempt_count": evidence.signature_attempt_count,
        "signature_outcome": evidence.signature_outcome.value,
        "test_container": evidence.test_container,
    }


def canonical_evidence_bytes(evidence: HarnessEvidence) -> bytes:
    """Return sanitized, stable evidence bytes containing no native handles."""

    payload = _evidence_payload(evidence)
    return (
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _write_create_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=False, exist_ok=False)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def publish_test_evidence_create_new(
    evidence: HarnessEvidence,
    test_root: Path,
) -> Path:
    """Explicit test-only publisher; callers must pass pytest ``tmp_path``."""

    if test_root == Path(str(FUTURE_EVIDENCE_ROOT)):
        raise HarnessContractError("test publisher cannot create the future root")
    destination = test_root / "p3-r1-ksp-evidence" / "evidence.json"
    _write_create_new(destination, canonical_evidence_bytes(evidence))
    return destination


def _require_native_execution_authorized() -> None:
    if not _NATIVE_EFFECT_EXECUTION_AUTHORIZED:
        raise NativeExecutionDisabled(
            "native disposable KSP execution is not authorized by this checkpoint"
        )
    if _NATIVE_EFFECT_AUTHORIZATION_ID.startswith("NOT-AUTHORIZED"):
        raise NativeExecutionDisabled("native authorization identifier is disabled")


def execute_native_phase(
    phase: Phase,
    evidence: HarnessEvidence,
    operations: NativePhaseOperations,
) -> HarnessEvidence:
    """Future effect entry point, hard-disabled before touching ``operations``."""

    validate_harness_evidence(evidence)
    validate_key_identity(MACHINE_TEST_KEY)
    validate_key_identity(CURRENT_USER_SHADOW_KEY)
    validate_evidence_root(FUTURE_EVIDENCE_ROOT)
    _require_native_execution_authorized()
    validate_phase_dispatch_eligibility(phase, evidence)
    return operations.execute(phase, evidence)  # pragma: no cover - disabled


class _AclSizeInformation(ctypes.Structure):
    _fields_ = [
        ("ace_count", ctypes.c_uint32),
        ("acl_bytes_in_use", ctypes.c_uint32),
        ("acl_bytes_free", ctypes.c_uint32),
    ]


class _AceHeader(ctypes.Structure):
    _fields_ = [
        ("ace_type", ctypes.c_ubyte),
        ("ace_flags", ctypes.c_ubyte),
        ("ace_size", ctypes.c_uint16),
    ]


class _AccessAllowedAce(ctypes.Structure):
    _fields_ = [
        ("header", _AceHeader),
        ("mask", ctypes.c_uint32),
        ("sid_start", ctypes.c_uint32),
    ]


def _bind(
    library: Any,
    name: str,
    argtypes: Sequence[Any],
    restype: Any,
) -> Callable[..., Any]:
    function = getattr(library, name)
    function.argtypes = list(argtypes)
    function.restype = restype
    return function


@dataclass(frozen=True)
class WindowsNativeBindings:
    """Typed NCrypt/security/token bindings, loaded only after the fixed gate."""

    functions: Mapping[str, Callable[..., Any]]

    @classmethod
    def load_for_authorized_execution(cls) -> WindowsNativeBindings:
        _require_native_execution_authorized()
        if os.name != "nt" or wintypes is None:  # pragma: no cover - gated
            raise NativeExecutionDisabled("Windows native APIs are unavailable")

        ncrypt = ctypes.WinDLL("ncrypt", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        status = ctypes.c_int32
        handle = ctypes.c_void_p
        dword = wintypes.DWORD
        bool_type = wintypes.BOOL
        functions: dict[str, Callable[..., Any]] = {}

        functions["NCryptOpenStorageProvider"] = _bind(
            ncrypt,
            "NCryptOpenStorageProvider",
            [ctypes.POINTER(handle), ctypes.c_wchar_p, dword],
            status,
        )
        functions["NCryptCreatePersistedKey"] = _bind(
            ncrypt,
            "NCryptCreatePersistedKey",
            [
                handle,
                ctypes.POINTER(handle),
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                dword,
                dword,
            ],
            status,
        )
        functions["NCryptOpenKey"] = _bind(
            ncrypt,
            "NCryptOpenKey",
            [handle, ctypes.POINTER(handle), ctypes.c_wchar_p, dword, dword],
            status,
        )
        functions["NCryptSetProperty"] = _bind(
            ncrypt,
            "NCryptSetProperty",
            [handle, ctypes.c_wchar_p, ctypes.c_void_p, dword, dword],
            status,
        )
        functions["NCryptGetProperty"] = _bind(
            ncrypt,
            "NCryptGetProperty",
            [
                handle,
                ctypes.c_wchar_p,
                ctypes.c_void_p,
                dword,
                ctypes.POINTER(dword),
                dword,
            ],
            status,
        )
        functions["NCryptFinalizeKey"] = _bind(
            ncrypt, "NCryptFinalizeKey", [handle, dword], status
        )
        functions["NCryptExportKey"] = _bind(
            ncrypt,
            "NCryptExportKey",
            [
                handle,
                handle,
                ctypes.c_wchar_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                dword,
                ctypes.POINTER(dword),
                dword,
            ],
            status,
        )
        functions["NCryptSignHash"] = _bind(
            ncrypt,
            "NCryptSignHash",
            [
                handle,
                ctypes.c_void_p,
                ctypes.c_void_p,
                dword,
                ctypes.c_void_p,
                dword,
                ctypes.POINTER(dword),
                dword,
            ],
            status,
        )
        functions["NCryptFreeObject"] = _bind(
            ncrypt, "NCryptFreeObject", [handle], status
        )

        security_specs: tuple[tuple[str, Sequence[Any], Any], ...] = (
            ("IsValidSecurityDescriptor", [ctypes.c_void_p], bool_type),
            (
                "GetSecurityDescriptorOwner",
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(bool_type),
                ],
                bool_type,
            ),
            (
                "GetSecurityDescriptorDacl",
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(bool_type),
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(bool_type),
                ],
                bool_type,
            ),
            (
                "GetSecurityDescriptorControl",
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_uint16),
                    ctypes.POINTER(dword),
                ],
                bool_type,
            ),
            ("GetSecurityDescriptorLength", [ctypes.c_void_p], dword),
            (
                "GetAclInformation",
                [ctypes.c_void_p, ctypes.c_void_p, dword, ctypes.c_int],
                bool_type,
            ),
            (
                "GetAce",
                [ctypes.c_void_p, dword, ctypes.POINTER(ctypes.c_void_p)],
                bool_type,
            ),
            ("IsValidSid", [ctypes.c_void_p], bool_type),
            ("GetLengthSid", [ctypes.c_void_p], dword),
            (
                "ConvertSidToStringSidW",
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)],
                bool_type,
            ),
            (
                "ConvertStringSidToSidW",
                [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)],
                bool_type,
            ),
            ("InitializeSecurityDescriptor", [ctypes.c_void_p, dword], bool_type),
            (
                "SetSecurityDescriptorOwner",
                [ctypes.c_void_p, ctypes.c_void_p, bool_type],
                bool_type,
            ),
            (
                "SetSecurityDescriptorDacl",
                [ctypes.c_void_p, bool_type, ctypes.c_void_p, bool_type],
                bool_type,
            ),
            (
                "SetSecurityDescriptorControl",
                [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16],
                bool_type,
            ),
            (
                "MakeSelfRelativeSD",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(dword)],
                bool_type,
            ),
            ("InitializeAcl", [ctypes.c_void_p, dword, dword], bool_type),
            (
                "AddAccessAllowedAceEx",
                [ctypes.c_void_p, dword, dword, dword, ctypes.c_void_p],
                bool_type,
            ),
            (
                "OpenProcessToken",
                [wintypes.HANDLE, dword, ctypes.POINTER(wintypes.HANDLE)],
                bool_type,
            ),
            (
                "GetTokenInformation",
                [
                    wintypes.HANDLE,
                    ctypes.c_int,
                    ctypes.c_void_p,
                    dword,
                    ctypes.POINTER(dword),
                ],
                bool_type,
            ),
            (
                "CheckTokenMembership",
                [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(bool_type)],
                bool_type,
            ),
        )
        for name, argtypes, restype in security_specs:
            functions[name] = _bind(advapi32, name, argtypes, restype)

        functions["LocalFree"] = _bind(
            kernel32, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p
        )
        functions["GetCurrentProcess"] = _bind(
            kernel32, "GetCurrentProcess", [], wintypes.HANDLE
        )
        functions["CloseHandle"] = _bind(
            kernel32, "CloseHandle", [wintypes.HANDLE], bool_type
        )
        return cls(functions=functions)


NCRYPT_REQUIRED_FUNCTIONS = frozenset(
    {
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
)


def harness_description() -> dict[str, Any]:
    """Return the inert, non-authorizing source contract for review."""

    return {
        "evidence_root": str(FUTURE_EVIDENCE_ROOT),
        "native_effect_execution_authorized": False,
        "ordinary_nonadmin_test_identity_blocked": (
            ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED
        ),
        "phases": [phase.value for phase in PHASE_ORDER],
        "provider": PROVIDER_NAME,
        "test_container": TEST_CONTAINER_TEXT,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Describe the inert P3-R1 disposable KSP harness."
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="print the frozen non-executable harness contract",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Describe only; this checkpoint exposes no native-execution CLI."""

    _parser().parse_args(argv)
    sys.stdout.write(json.dumps(harness_description(), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
