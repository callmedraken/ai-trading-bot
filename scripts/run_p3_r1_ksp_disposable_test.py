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
from contextlib import AbstractContextManager
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
ORDINARY_NONADMIN_SELECTION_REQUIRES_REVIEW = True

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

NTE_BAD_KEYSET = 0x80090016
NTE_PERM = 0x80090010
NTE_NOT_SUPPORTED = 0x80090029
REVIEWED_NOT_FOUND_STATUSES = frozenset({NTE_BAD_KEYSET})
REVIEWED_ACCESS_DENIED_STATUSES = frozenset({NTE_PERM})

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
_P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_P256_GX = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
_P256_GY = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5

TEST_SIGNATURE_DOMAIN = (
    b"AITradingBot/P3R1/DisposableKSPValidation/TestSignature/v1\x00"
)
TEST_SIGNATURE_MESSAGE = (
    b"TEST-ONLY;NO-BOOTSTRAP;NO-P3R1-RECOVERY-AUTHORIZATION;"
    b"NO-PRODUCTION-ORDER-OR-TRADING-AUTHORITY"
)
TEST_SIGNATURE_PREIMAGE = (
    TEST_SIGNATURE_DOMAIN
    + len(TEST_SIGNATURE_MESSAGE).to_bytes(4, "big")
    + TEST_SIGNATURE_MESSAGE
)


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


class NativeOperationUncertain(RuntimeError):
    """Raised when a future native effect may have happened but is unproved."""


class HandleReleaseError(NativeOperationUncertain):
    """Raised when an owned native resource could not be released exactly once."""


class EvidenceRetentionError(RuntimeError):
    """Base class for classified fixed-root evidence retention failures."""


class EvidenceRetentionUncertain(EvidenceRetentionError):
    """Durable evidence authority could not be proved; execution must stop."""

    def __init__(
        self,
        message: str,
        intended_evidence: HarnessEvidence | None = None,
        *,
        effect_may_have_occurred: bool = False,
    ) -> None:
        self.intended_evidence = intended_evidence
        self.effect_may_have_occurred = effect_may_have_occurred
        super().__init__(message)


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


@dataclass(frozen=True)
class TokenFacts:
    user_sid: str
    elevated: bool
    elevation_type_full: bool
    administrators_enabled: bool


class OwnedNativeHandle(AbstractContextManager[Any]):
    """Own one non-null native handle and release it at most once."""

    def __init__(
        self,
        value: Any,
        release: Callable[[Any], None],
        label: str,
    ) -> None:
        if value is None or value == 0:
            raise HarnessContractError(f"{label} returned a null handle")
        self.value = value
        self._release = release
        self._label = label
        self._owned = True

    @property
    def owned(self) -> bool:
        return self._owned

    def close(self) -> None:
        if not self._owned:
            return
        self._owned = False
        try:
            self._release(self.value)
        except Exception as error:
            raise HandleReleaseError(f"failed to release {self._label}") from error

    def __enter__(self) -> Any:
        if not self._owned:
            raise HandleReleaseError(f"{self._label} is already released")
        return self.value

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        try:
            self.close()
        except HandleReleaseError as release_error:
            if exc is not None:
                combined = BaseExceptionGroup(
                    f"{self._label} operation and release both failed",
                    [exc, release_error],
                )
                if isinstance(exc, EvidenceRetentionUncertain):
                    raise EvidenceRetentionUncertain(
                        f"{self._label} retention and release both failed",
                        exc.intended_evidence,
                        effect_may_have_occurred=exc.effect_may_have_occurred,
                    ) from combined
                raise HandleReleaseError(
                    f"{self._label} operation ended with an uncertain release"
                ) from combined
            raise
        return False


@dataclass(frozen=True)
class NativeOpenResult:
    status: int
    handle: OwnedNativeHandle | None


class NativeApi(Protocol):
    """Narrow injectable native surface used by the disabled phase bodies."""

    def current_token_facts(self) -> TokenFacts: ...

    def evidence_root_exists(self, root: PureWindowsPath) -> bool: ...

    def open_provider(self) -> OwnedNativeHandle: ...

    def get_dword(self, handle: Any, property_name: str, flags: int) -> int: ...

    def get_string(self, handle: Any, property_name: str, flags: int) -> str: ...

    def get_bytes(self, handle: Any, property_name: str, flags: int) -> bytes: ...

    def try_open_key(
        self,
        provider: Any,
        identity: KeyIdentity,
        flags: int,
    ) -> NativeOpenResult: ...

    def create_key(
        self,
        provider: Any,
        identity: KeyIdentity,
        flags: int,
    ) -> OwnedNativeHandle: ...

    def set_dword(
        self,
        handle: Any,
        property_name: str,
        value: int,
        flags: int,
    ) -> None: ...

    def set_bytes(
        self,
        handle: Any,
        property_name: str,
        value: bytes,
        flags: int,
    ) -> None: ...

    def build_exact_security_descriptor(self) -> bytes: ...

    def decode_security_descriptor(
        self, value: bytes
    ) -> SecurityDescriptorSemantic: ...

    def finalize_key(self, handle: Any, flags: int) -> None: ...

    def export_public(self, handle: Any, flags: int) -> bytes: ...

    def private_export_probe_status(
        self,
        handle: Any,
        blob_type: str,
        flags: int,
    ) -> int: ...

    def sign_hash(self, handle: Any, digest: bytes, flags: int) -> bytes: ...


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


def require_successful_effect_handle(
    operation: str,
    status: int,
    handle: int | None,
) -> int:
    """Require an effect API's success status and its promised acquired handle."""

    check_security_status(operation, status)
    if handle is None or handle == 0:
        raise NativeOperationUncertain(
            f"{operation} returned success without the required key handle"
        )
    return handle


def parse_ncrypt_dword(value: bytes, property_name: str) -> int:
    """Parse one exact little-endian NCrypt DWORD property buffer."""

    if len(value) != 4:
        raise HarnessContractError(f"{property_name} is not exactly one DWORD")
    return struct.unpack("<I", value)[0]


def parse_ncrypt_string(value: bytes, property_name: str) -> str:
    """Parse one exact null-terminated NCrypt UTF-16 property buffer."""

    if len(value) < 2 or len(value) % 2 or not value.endswith(b"\x00\x00"):
        raise HarnessContractError(f"{property_name} is malformed UTF-16")
    try:
        text = value[:-2].decode("utf-16-le")
    except UnicodeDecodeError as error:
        raise HarnessContractError(f"{property_name} is malformed UTF-16") from error
    if "\x00" in text:
        raise HarnessContractError(f"{property_name} contains embedded NUL data")
    return text


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


def _strict_object(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HarnessContractError(f"{label} must be an object")
    if frozenset(value) != fields:
        raise HarnessContractError(f"{label} has unknown or missing fields")
    return value


def _strict_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise HarnessContractError(f"{label} must be a boolean")
    return value


def _strict_int(value: Any, label: str) -> int:
    if type(value) is not int:
        raise HarnessContractError(f"{label} must be an integer")
    return value


def _strict_text(value: Any, label: str) -> str:
    if type(value) is not str:
        raise HarnessContractError(f"{label} must be text")
    return value


def _enum_value(enum_type: type[StrEnum], value: Any, label: str) -> StrEnum:
    text = _strict_text(value, label)
    try:
        return enum_type(text)
    except ValueError as error:
        raise HarnessContractError(f"{label} is not a recognized value") from error


def _parse_lifecycle(value: Any) -> LifecycleEvidence:
    item = _strict_object(
        value,
        frozenset(field.name for field in dataclass_fields(LifecycleEvidence)),
        "lifecycle",
    )
    return LifecycleEvidence(
        machine_creation_attempted=_strict_bool(
            item["machine_creation_attempted"], "machine_creation_attempted"
        ),
        machine_created=_strict_bool(item["machine_created"], "machine_created"),
        shadow_creation_attempted=_strict_bool(
            item["shadow_creation_attempted"], "shadow_creation_attempted"
        ),
        shadow_created=_strict_bool(item["shadow_created"], "shadow_created"),
        test_name_retired=_strict_bool(item["test_name_retired"], "test_name_retired"),
    )


def _parse_key_metadata(value: Any) -> KeyMetadata:
    item = _strict_object(
        value,
        frozenset(
            {
                "algorithm",
                "algorithm_group",
                "identity",
                "key_length_bits",
                "key_type",
                "public_sec1_hex",
            }
        ),
        "key metadata",
    )
    identity_item = _strict_object(
        item["identity"],
        frozenset({"container", "operator_sid", "provider", "scope"}),
        "key identity",
    )
    operator_sid = identity_item["operator_sid"]
    if operator_sid is not None:
        operator_sid = _strict_text(operator_sid, "operator_sid")
    scope = _enum_value(KeyScope, identity_item["scope"], "scope")
    if not isinstance(scope, KeyScope):  # pragma: no cover - type narrowing
        raise HarnessContractError("invalid key scope")
    identity = KeyIdentity(
        provider=_strict_text(identity_item["provider"], "provider"),
        scope=scope,
        container=_strict_text(identity_item["container"], "container"),
        operator_sid=operator_sid,
    )
    public_hex = _strict_text(item["public_sec1_hex"], "public_sec1_hex")
    try:
        public_sec1 = bytes.fromhex(public_hex)
    except ValueError as error:
        raise HarnessContractError("public_sec1_hex is malformed") from error
    if public_sec1.hex() != public_hex:
        raise HarnessContractError("public_sec1_hex is not canonical lowercase hex")
    return KeyMetadata(
        identity=identity,
        key_type=_strict_int(item["key_type"], "key_type"),
        algorithm=_strict_text(item["algorithm"], "algorithm"),
        algorithm_group=_strict_text(item["algorithm_group"], "algorithm_group"),
        key_length_bits=_strict_int(item["key_length_bits"], "key_length_bits"),
        public_sec1=public_sec1,
    )


def _parse_completion(value: Any) -> PhaseCompletion | None:
    if value is None:
        return None
    if not isinstance(value, dict) or type(value.get("kind")) is not str:
        raise HarnessContractError("completion must have an exact kind")
    kind = value["kind"]
    if kind == "read-only-preflight/v1":
        item = _strict_object(
            value,
            frozenset(
                {
                    "both_scope_absence_proved",
                    "elevated_operator_sid",
                    "future_evidence_root_absent",
                    "kind",
                    "provider_security_descriptor_support",
                }
            ),
            "preflight completion",
        )
        return ReadOnlyPreflightCompletion(
            _strict_bool(
                item["both_scope_absence_proved"], "both_scope_absence_proved"
            ),
            _strict_bool(
                item["future_evidence_root_absent"], "future_evidence_root_absent"
            ),
            _strict_bool(
                item["provider_security_descriptor_support"],
                "provider_security_descriptor_support",
            ),
            _strict_text(item["elevated_operator_sid"], "elevated_operator_sid"),
        )
    if kind == "machine-validation/v1":
        item = _strict_object(
            value,
            frozenset(
                {
                    "exact_properties_verified",
                    "independent_reopen_verified",
                    "kind",
                    "machine_metadata",
                    "security_descriptor_verified",
                }
            ),
            "machine completion",
        )
        return MachineValidationCompletion(
            _parse_key_metadata(item["machine_metadata"]),
            _strict_bool(
                item["exact_properties_verified"], "exact_properties_verified"
            ),
            _strict_bool(
                item["security_descriptor_verified"],
                "security_descriptor_verified",
            ),
            _strict_bool(
                item["independent_reopen_verified"], "independent_reopen_verified"
            ),
        )
    if kind == "shadow-scope/v1":
        item = _strict_object(
            value,
            frozenset(
                {
                    "kind",
                    "machine_metadata",
                    "scope_non_substitution_verified",
                    "shadow_metadata",
                }
            ),
            "shadow completion",
        )
        return ShadowScopeCompletion(
            _parse_key_metadata(item["machine_metadata"]),
            _parse_key_metadata(item["shadow_metadata"]),
            _strict_bool(
                item["scope_non_substitution_verified"],
                "scope_non_substitution_verified",
            ),
        )
    if kind == "elevated-effect/v1":
        item = _strict_object(
            value,
            frozenset(
                {
                    "kind",
                    "private_export_denial_matrix_verified",
                    "signature_verified_with_machine_public",
                }
            ),
            "elevated completion",
        )
        return ElevatedEffectCompletion(
            _strict_bool(
                item["signature_verified_with_machine_public"],
                "signature_verified_with_machine_public",
            ),
            _strict_bool(
                item["private_export_denial_matrix_verified"],
                "private_export_denial_matrix_verified",
            ),
        )
    if kind == "principal-denial/v1":
        item = _strict_object(
            value,
            frozenset(
                {
                    "actor_sid",
                    "downstream_private_operations_unreachable",
                    "kind",
                    "machine_open_denied",
                }
            ),
            "principal denial completion",
        )
        return PrincipalDenialCompletion(
            _strict_text(item["actor_sid"], "actor_sid"),
            _strict_bool(item["machine_open_denied"], "machine_open_denied"),
            _strict_bool(
                item["downstream_private_operations_unreachable"],
                "downstream_private_operations_unreachable",
            ),
        )
    if kind == "final-reconciliation/v1":
        item = _strict_object(
            value,
            frozenset(
                {
                    "all_phase_evidence_reconciled",
                    "both_scope_qualified_keys_retained",
                    "cleanup_performed",
                    "kind",
                }
            ),
            "final completion",
        )
        return FinalReconciliationCompletion(
            _strict_bool(
                item["all_phase_evidence_reconciled"],
                "all_phase_evidence_reconciled",
            ),
            _strict_bool(
                item["both_scope_qualified_keys_retained"],
                "both_scope_qualified_keys_retained",
            ),
            _strict_bool(item["cleanup_performed"], "cleanup_performed"),
        )
    raise HarnessContractError("unknown completion kind")


def _parse_probe_results(value: Any) -> tuple[PrivateExportProbeResult, ...]:
    if not isinstance(value, list):
        raise HarnessContractError("private_export_probe_results must be a list")
    results: list[PrivateExportProbeResult] = []
    for raw in value:
        item = _strict_object(raw, frozenset({"outcome", "probe"}), "probe result")
        probe = _enum_value(PrivateExportProbe, item["probe"], "probe")
        outcome = _enum_value(
            PrivateExportProbeOutcome, item["outcome"], "probe outcome"
        )
        if not isinstance(probe, PrivateExportProbe) or not isinstance(
            outcome, PrivateExportProbeOutcome
        ):
            raise HarnessContractError("invalid probe result")
        results.append(PrivateExportProbeResult(probe, outcome))
    return tuple(results)


def _parse_snapshot(value: Any) -> PhaseStateSnapshot:
    item = _strict_object(
        value,
        frozenset(
            {
                "completion",
                "lifecycle",
                "private_export_probe_results",
                "signature_attempt_count",
                "signature_outcome",
            }
        ),
        "phase snapshot",
    )
    signature = _enum_value(
        SignatureOutcome, item["signature_outcome"], "signature_outcome"
    )
    if not isinstance(signature, SignatureOutcome):
        raise HarnessContractError("invalid signature outcome")
    return PhaseStateSnapshot(
        lifecycle=_parse_lifecycle(item["lifecycle"]),
        completion=_parse_completion(item["completion"]),
        signature_outcome=signature,
        signature_attempt_count=_strict_int(
            item["signature_attempt_count"], "signature_attempt_count"
        ),
        private_export_probe_results=_parse_probe_results(
            item["private_export_probe_results"]
        ),
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HarnessContractError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_test_evidence(path: Path) -> HarnessEvidence:
    """Strictly load canonical v2 retained evidence and revalidate its chain."""

    raw = path.read_bytes()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise HarnessContractError("evidence must be canonical ASCII JSON") from error
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_json_keys)
    except (json.JSONDecodeError, HarnessContractError) as error:
        raise HarnessContractError("evidence JSON is malformed or ambiguous") from error
    item = _strict_object(
        payload,
        frozenset(
            {
                "future_evidence_root",
                "lifecycle",
                "phases",
                "private_export_probe_results",
                "schema",
                "signature_attempt_count",
                "signature_outcome",
                "test_container",
            }
        ),
        "evidence",
    )
    schema = _strict_text(item["schema"], "schema")
    if schema != HARNESS_SCHEMA_VERSION:
        raise HarnessContractError("only exact v2 retained evidence is accepted")
    if not isinstance(item["phases"], list):
        raise HarnessContractError("phases must be a list")
    records: list[PhaseRecord] = []
    for raw_record in item["phases"]:
        record = _strict_object(
            raw_record,
            frozenset(
                {
                    "actor_sid",
                    "outcome",
                    "phase",
                    "previous_record_sha256",
                    "record_sha256",
                    "state_snapshot",
                    "state_snapshot_sha256",
                }
            ),
            "phase record",
        )
        phase = _enum_value(Phase, record["phase"], "phase")
        outcome = _enum_value(PhaseOutcome, record["outcome"], "phase outcome")
        if not isinstance(phase, Phase) or not isinstance(outcome, PhaseOutcome):
            raise HarnessContractError("invalid phase record")
        records.append(
            PhaseRecord(
                phase=phase,
                outcome=outcome,
                actor_sid=_strict_text(record["actor_sid"], "actor_sid"),
                previous_record_sha256=_strict_text(
                    record["previous_record_sha256"], "previous_record_sha256"
                ),
                state_snapshot=_parse_snapshot(record["state_snapshot"]),
                state_snapshot_sha256=_strict_text(
                    record["state_snapshot_sha256"], "state_snapshot_sha256"
                ),
                record_sha256=_strict_text(record["record_sha256"], "record_sha256"),
            )
        )
    signature = _enum_value(
        SignatureOutcome, item["signature_outcome"], "signature_outcome"
    )
    if not isinstance(signature, SignatureOutcome):
        raise HarnessContractError("invalid signature outcome")
    evidence = HarnessEvidence(
        schema=schema,
        test_container=_strict_text(item["test_container"], "test_container"),
        future_evidence_root=_strict_text(
            item["future_evidence_root"], "future_evidence_root"
        ),
        lifecycle=_parse_lifecycle(item["lifecycle"]),
        phases=tuple(records),
        signature_outcome=signature,
        signature_attempt_count=_strict_int(
            item["signature_attempt_count"], "signature_attempt_count"
        ),
        private_export_probe_results=_parse_probe_results(
            item["private_export_probe_results"]
        ),
    )
    validate_harness_evidence(evidence)
    if canonical_evidence_bytes(evidence) != raw:
        raise HarnessContractError("evidence bytes are not exact canonical v2")
    return evidence


def _require_native_execution_authorized() -> None:
    if not _NATIVE_EFFECT_EXECUTION_AUTHORIZED:
        raise NativeExecutionDisabled(
            "native disposable KSP execution is not authorized by this checkpoint"
        )
    if _NATIVE_EFFECT_AUTHORIZATION_ID.startswith("NOT-AUTHORIZED"):
        raise NativeExecutionDisabled("native authorization identifier is disabled")


def _validate_evidence_successor(
    previous: HarnessEvidence, current: HarnessEvidence
) -> None:
    if previous == current:
        raise HarnessContractError("duplicate retained evidence snapshot")
    if (
        len(current.phases) < len(previous.phases)
        or current.phases[: len(previous.phases)] != previous.phases
    ):
        raise HarnessContractError("retained evidence phase history regressed")
    if not _lifecycle_contains(current.lifecycle, previous.lifecycle):
        raise HarnessContractError("retained evidence lifecycle regressed")
    if current.signature_attempt_count < previous.signature_attempt_count or not (
        _outcome_contains(current.signature_outcome, previous.signature_outcome)
    ):
        raise HarnessContractError("retained signature state regressed")
    for current_probe, previous_probe in zip(
        current.private_export_probe_results,
        previous.private_export_probe_results,
        strict=True,
    ):
        if not _outcome_contains(current_probe.outcome, previous_probe.outcome):
            raise HarnessContractError("retained private-export state regressed")


def _snapshot_files(root: Path) -> list[tuple[int, int, str, Path]]:
    entries: list[tuple[int, int, str, Path]] = []
    for path in root.iterdir():
        parts = path.name.split("-")
        if (
            not path.is_file()
            or len(parts) != 4
            or parts[0] != "snapshot"
            or len(parts[1]) != 4
            or len(parts[2]) != 2
            or not parts[1].isdigit()
            or not parts[2].isdigit()
            or not parts[3].endswith(".json")
        ):
            raise HarnessContractError("retained evidence root has an unknown entry")
        digest = parts[3][:-5]
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise HarnessContractError("retained evidence filename digest is malformed")
        entries.append((int(parts[1]), int(parts[2]), digest, path))
    entries.sort(key=lambda item: item[0])
    if [entry[0] for entry in entries] != list(range(1, len(entries) + 1)):
        raise HarnessContractError(
            "retained evidence sequence is missing or duplicated"
        )
    return entries


def _load_retained_evidence_from_root(root: Path) -> HarnessEvidence:
    if root == Path(str(FUTURE_EVIDENCE_ROOT)):
        _require_native_execution_authorized()
    if not root.is_dir():
        raise HarnessContractError(
            "retained evidence root is absent or not a directory"
        )
    entries = _snapshot_files(root)
    if not entries:
        raise HarnessContractError("retained evidence root contains no snapshots")
    previous: HarnessEvidence | None = None
    for _, phase_count, digest, path in entries:
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise HarnessContractError("retained evidence filename digest is wrong")
        current = load_test_evidence(path)
        if len(current.phases) != phase_count:
            raise HarnessContractError(
                "retained evidence filename phase count is wrong"
            )
        if previous is not None:
            _validate_evidence_successor(previous, current)
        previous = current
    if previous is None:  # pragma: no cover - entries is proven nonempty
        raise HarnessContractError("retained evidence is absent")
    return previous


def _publish_retained_evidence_to_root_create_new(
    evidence: HarnessEvidence, root: Path
) -> Path:
    if root == Path(str(FUTURE_EVIDENCE_ROOT)):
        _require_native_execution_authorized()
    validate_harness_evidence(evidence)
    first_publication = (
        len(evidence.phases) == 1
        and evidence.phases[0].phase is Phase.READ_ONLY_PREFLIGHT
        and evidence.phases[0].outcome is PhaseOutcome.SUCCEEDED
        and evidence.lifecycle == LifecycleEvidence()
    )
    if first_publication:
        root.mkdir(parents=False, exist_ok=False)
    elif not root.is_dir():
        raise HarnessContractError(
            "retained evidence root is absent or not a directory"
        )
    entries = _snapshot_files(root)
    if entries:
        previous = _load_retained_evidence_from_root(root)
        _validate_evidence_successor(previous, evidence)
    elif not first_publication:
        raise HarnessContractError(
            "non-preflight evidence cannot be the first snapshot"
        )
    encoded = canonical_evidence_bytes(evidence)
    digest = hashlib.sha256(encoded).hexdigest()
    sequence = len(entries) + 1
    destination = root / (
        f"snapshot-{sequence:04d}-{len(evidence.phases):02d}-{digest}.json"
    )
    with destination.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return destination


def publish_retained_evidence_create_new(evidence: HarnessEvidence) -> Path:
    """Future append-only publisher for the fixed root; disabled in source."""

    _require_native_execution_authorized()
    root = Path(str(validate_evidence_root(FUTURE_EVIDENCE_ROOT)))
    try:
        return _publish_retained_evidence_to_root_create_new(evidence, root)
    except EvidenceRetentionError:
        raise
    except Exception as error:
        raise EvidenceRetentionUncertain(
            "fixed-root evidence publication could not be proved",
            evidence,
        ) from error


def load_retained_evidence() -> HarnessEvidence:
    """Future fixed-root multi-session loader; disabled from ordinary use."""

    _require_native_execution_authorized()
    root = Path(str(validate_evidence_root(FUTURE_EVIDENCE_ROOT)))
    try:
        return _load_retained_evidence_from_root(root)
    except EvidenceRetentionError:
        raise
    except Exception as error:
        raise EvidenceRetentionUncertain(
            "fixed-root retained evidence could not be loaded and reconciled"
        ) from error


def persist_and_reload_retained_evidence(
    evidence: HarnessEvidence,
) -> HarnessEvidence:
    """Append, fsync, reload, validate, and exactly confirm fixed-root state."""

    _require_native_execution_authorized()
    try:
        publish_retained_evidence_create_new(evidence)
        confirmed = load_retained_evidence()
    except EvidenceRetentionUncertain:
        raise
    except Exception as error:  # pragma: no cover - public helpers classify first
        raise EvidenceRetentionUncertain(
            "retained evidence persistence/reload failed",
            evidence,
        ) from error
    if confirmed != evidence:
        raise EvidenceRetentionUncertain(
            "reloaded retained evidence differs from the intended state",
            evidence,
        )
    return confirmed


def _confirm_evidence_retention(
    evidence: HarnessEvidence,
    retainer: Callable[[HarnessEvidence], HarnessEvidence | None],
    *,
    require_exact_confirmation: bool,
    effect_may_have_occurred: bool,
) -> HarnessEvidence:
    try:
        confirmed = retainer(evidence)
    except EvidenceRetentionUncertain as error:
        raise EvidenceRetentionUncertain(
            str(error),
            evidence,
            effect_may_have_occurred=(
                effect_may_have_occurred or error.effect_may_have_occurred
            ),
        ) from error
    except Exception as error:
        raise EvidenceRetentionUncertain(
            "evidence publication/reload could not be proved",
            evidence,
            effect_may_have_occurred=effect_may_have_occurred,
        ) from error
    if require_exact_confirmation:
        if confirmed != evidence:
            raise EvidenceRetentionUncertain(
                "persistent retainer did not reload the exact intended evidence",
                evidence,
                effect_may_have_occurred=effect_may_have_occurred,
            )
        return confirmed
    if confirmed is not None and confirmed != evidence:
        raise EvidenceRetentionUncertain(
            "test retainer returned contradictory evidence",
            evidence,
            effect_may_have_occurred=effect_may_have_occurred,
        )
    return evidence


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


def _load_confirmed_evidence(
    loader: Callable[[], HarnessEvidence],
) -> HarnessEvidence:
    try:
        evidence = loader()
        return validate_harness_evidence(evidence)
    except EvidenceRetentionUncertain:
        raise
    except Exception as error:
        raise EvidenceRetentionUncertain(
            "retained evidence load/validation could not be proved"
        ) from error


def _derive_next_retained_phase(evidence: HarnessEvidence) -> Phase:
    validate_harness_evidence(evidence)
    if evidence.phases and evidence.phases[-1].outcome is not PhaseOutcome.SUCCEEDED:
        raise HarnessContractError("terminal predecessor blocks native dispatch")
    if len(evidence.phases) >= len(PHASE_ORDER):
        raise HarnessContractError("all phases are already complete")
    return PHASE_ORDER[len(evidence.phases)]


def _validate_phase_start_eligibility(
    phase: Phase,
    evidence: HarnessEvidence,
) -> None:
    if phase is Phase.MACHINE_CREATE_AND_VALIDATE:
        if evidence.lifecycle != LifecycleEvidence():
            raise HarnessContractError(
                "machine phase cannot restart from a retained attempt state"
            )
        return
    if phase is Phase.SHADOW_CREATE_AND_SCOPE_PROOF:
        if evidence.lifecycle != LifecycleEvidence(
            machine_creation_attempted=True,
            machine_created=True,
            test_name_retired=True,
        ):
            raise HarnessContractError(
                "shadow phase cannot restart from a retained attempt state"
            )
        return
    validate_phase_dispatch_eligibility(phase, evidence)


def _execute_next_retained_native_phase(
    requested_phase: Phase,
    *,
    evidence_root_exists: Callable[[], bool],
    load_latest: Callable[[], HarnessEvidence],
    persist_reload: Callable[[HarnessEvidence], HarnessEvidence | None],
    operations_factory: Callable[[], NativePhaseOperations],
) -> HarnessEvidence:
    """Pure-testable authority runner that never accepts caller evidence."""

    try:
        root_exists = evidence_root_exists()
    except EvidenceRetentionUncertain:
        raise
    except Exception as error:
        raise EvidenceRetentionUncertain(
            "fixed evidence-root existence could not be proved"
        ) from error

    if root_exists:
        evidence = _load_confirmed_evidence(load_latest)
    else:
        evidence = HarnessEvidence()

    next_phase = _derive_next_retained_phase(evidence)
    if requested_phase is not next_phase:
        raise HarnessContractError(
            f"requested {requested_phase.value}; retained authority requires "
            f"{next_phase.value}"
        )
    if not root_exists and next_phase is not Phase.READ_ONLY_PREFLIGHT:
        raise HarnessContractError(
            "absent evidence root permits only initial preflight"
        )
    _validate_phase_start_eligibility(next_phase, evidence)

    if next_phase is Phase.MACHINE_CREATE_AND_VALIDATE:
        intended = begin_machine_creation(evidence)
        evidence = _confirm_evidence_retention(
            intended,
            persist_reload,
            require_exact_confirmation=True,
            effect_may_have_occurred=False,
        )
    elif next_phase is Phase.SHADOW_CREATE_AND_SCOPE_PROOF:
        intended = begin_shadow_creation(evidence)
        evidence = _confirm_evidence_retention(
            intended,
            persist_reload,
            require_exact_confirmation=True,
            effect_may_have_occurred=False,
        )

    operations = operations_factory()
    result = operations.execute(next_phase, evidence)
    effect_phase = next_phase in {
        Phase.MACHINE_CREATE_AND_VALIDATE,
        Phase.SHADOW_CREATE_AND_SCOPE_PROOF,
        Phase.ELEVATED_MACHINE_EFFECT_TEST,
    }
    try:
        confirmed = _load_confirmed_evidence(load_latest)
    except EvidenceRetentionUncertain as error:
        raise EvidenceRetentionUncertain(
            "completed phase could not be reloaded from the fixed evidence root",
            result,
            effect_may_have_occurred=effect_phase or error.effect_may_have_occurred,
        ) from error
    if confirmed != result:
        raise EvidenceRetentionUncertain(
            "latest fixed-root evidence differs from completed phase state",
            result,
            effect_may_have_occurred=effect_phase,
        )
    return confirmed


def execute_next_retained_native_phase(requested_phase: Phase) -> HarnessEvidence:
    """Source-gated real runner deriving authority only from the fixed root."""

    _require_native_execution_authorized()
    root = Path(str(validate_evidence_root(FUTURE_EVIDENCE_ROOT)))

    def fixed_root_exists() -> bool:
        try:
            return root.exists()
        except OSError as error:
            raise EvidenceRetentionUncertain(
                "fixed evidence-root absence/presence is uncertain"
            ) from error

    class FixedRootDispatch:
        # Constructed only here, after the source gate. The generic public
        # operations.execute API cannot dispatch a real ctypes adapter.
        def execute(self, phase: Phase, evidence: HarnessEvidence) -> HarnessEvidence:
            operations = NativeWindowsPhaseOperations.load_for_authorized_execution()
            return operations._execute_phase(phase, evidence)

    return _execute_next_retained_native_phase(
        requested_phase,
        evidence_root_exists=fixed_root_exists,
        load_latest=load_retained_evidence,
        persist_reload=persist_and_reload_retained_evidence,
        operations_factory=FixedRootDispatch,
    )


def _p256_add(
    left: tuple[int, int] | None,
    right: tuple[int, int] | None,
) -> tuple[int, int] | None:
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % _P256_P == 0:
        return None
    if left == right:
        if y1 == 0:
            return None
        slope = ((3 * x1 * x1 + _P256_A) * pow(2 * y1, -1, _P256_P)) % _P256_P
    else:
        slope = ((y2 - y1) * pow((x2 - x1) % _P256_P, -1, _P256_P)) % _P256_P
    x3 = (slope * slope - x1 - x2) % _P256_P
    return x3, (slope * (x1 - x3) - y1) % _P256_P


def _p256_multiply(scalar: int, point: tuple[int, int]) -> tuple[int, int] | None:
    result: tuple[int, int] | None = None
    addend: tuple[int, int] | None = point
    while scalar:
        if scalar & 1:
            result = _p256_add(result, addend)
        addend = _p256_add(addend, addend)
        scalar >>= 1
    return result


def verify_test_signature_p1363(
    public_sec1: bytes,
    digest: bytes,
    signature: bytes,
) -> bool:
    """Verify the one fixed test signature without accepting DER ambiguity."""

    if len(public_sec1) != 65 or public_sec1[0] != 4 or len(digest) != 32:
        return False
    if len(signature) != 64:
        return False
    x = int.from_bytes(public_sec1[1:33], "big")
    y = int.from_bytes(public_sec1[33:], "big")
    try:
        _validate_public_point(public_sec1[1:33], public_sec1[33:])
    except HarnessContractError:
        return False
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if not (1 <= r < _P256_N and 1 <= s < _P256_N):
        return False
    inverse = pow(s, -1, _P256_N)
    z = int.from_bytes(digest, "big")
    point = _p256_add(
        _p256_multiply((z * inverse) % _P256_N, (_P256_GX, _P256_GY)),
        _p256_multiply((r * inverse) % _P256_N, (x, y)),
    )
    return point is not None and point[0] % _P256_N == r


def classify_private_export_status(status: int) -> PrivateExportProbeOutcome:
    """Classify a native probe without treating unsupported format as denial."""

    normalized = status & 0xFFFFFFFF
    if normalized in REVIEWED_ACCESS_DENIED_STATUSES:
        return PrivateExportProbeOutcome.DENIED_AS_REQUIRED
    if normalized == NTE_NOT_SUPPORTED:
        return PrivateExportProbeOutcome.UNSUPPORTED_FORMAT
    return PrivateExportProbeOutcome.FAILED


class NativeWindowsPhaseOperations:
    """Exact future phase bodies, reachable only behind the disabled source gate."""

    def __init__(
        self,
        api: NativeApi,
        evidence_retainer: (
            Callable[[HarnessEvidence], HarnessEvidence | None] | None
        ) = None,
    ) -> None:
        if getattr(api, "requires_persistent_retainer", False) and (
            evidence_retainer is None
        ):
            raise HarnessContractError(
                "native ctypes operations require append-only evidence retention"
            )
        self._api = api
        self._evidence_retainer = evidence_retainer
        self._persistent_retainer_required = bool(
            getattr(api, "requires_persistent_retainer", False)
        )
        self._retained_evidence = HarnessEvidence()
        self._effect_may_have_occurred = False

    @classmethod
    def load_for_authorized_execution(cls) -> NativeWindowsPhaseOperations:
        _require_native_execution_authorized()
        return cls(
            CtypesNativeApi.load_for_authorized_execution(),
            persist_and_reload_retained_evidence,
        )

    def _retain(self, evidence: HarnessEvidence) -> HarnessEvidence:
        confirmed = evidence
        if self._evidence_retainer is not None:
            confirmed = _confirm_evidence_retention(
                evidence,
                self._evidence_retainer,
                require_exact_confirmation=self._persistent_retainer_required,
                effect_may_have_occurred=self._effect_may_have_occurred,
            )
        self._retained_evidence = confirmed
        return confirmed

    def execute(self, phase: Phase, evidence: HarnessEvidence) -> HarnessEvidence:
        if isinstance(self._api, CtypesNativeApi):
            _require_native_execution_authorized()
            raise HarnessContractError(
                "real native phases require execute_next_retained_native_phase"
            )
        return self._execute_phase(phase, evidence)

    def _execute_phase(
        self, phase: Phase, evidence: HarnessEvidence
    ) -> HarnessEvidence:
        if isinstance(self._api, CtypesNativeApi):
            _require_native_execution_authorized()
        validate_phase_dispatch_eligibility(phase, evidence)
        self._retained_evidence = evidence
        self._effect_may_have_occurred = False
        handlers: dict[
            Phase, Callable[[HarnessEvidence], tuple[HarnessEvidence, PhaseCompletion]]
        ] = {
            Phase.READ_ONLY_PREFLIGHT: self._read_only_preflight,
            Phase.MACHINE_CREATE_AND_VALIDATE: self._machine_create_and_validate,
            Phase.SHADOW_CREATE_AND_SCOPE_PROOF: self._shadow_create_and_scope_proof,
            Phase.ELEVATED_MACHINE_EFFECT_TEST: self._elevated_machine_effect_test,
            Phase.TRADING_DENIAL: self._principal_denial,
            Phase.ORDINARY_NONADMIN_DENIAL: self._principal_denial,
            Phase.FINAL_EVIDENCE_RECONCILIATION: self._final_reconciliation,
        }
        try:
            updated, completion = handlers[phase](evidence)
        except EvidenceRetentionUncertain:
            raise
        except (HandleReleaseError, NativeOperationUncertain, SecurityStatusError):
            return self._retain(
                append_phase_result(
                    self._retained_evidence, phase, PhaseOutcome.UNCERTAIN
                )
            )
        except HarnessContractError:
            return self._retain(
                append_phase_result(self._retained_evidence, phase, PhaseOutcome.FAILED)
            )
        return self._retain(
            append_phase_result(updated, phase, PhaseOutcome.SUCCEEDED, completion)
        )

    def _require_operator_token(self) -> TokenFacts:
        facts = self._api.current_token_facts()
        if facts.user_sid != ELEVATED_TEST_OPERATOR_SID:
            raise HarnessContractError("current token is not the exact test operator")
        if not facts.elevated or not facts.elevation_type_full:
            raise HarnessContractError("test operator token is not genuinely elevated")
        if not facts.administrators_enabled:
            raise HarnessContractError("Administrators is not enabled in the token")
        return facts

    def _require_provider_name(self, provider: Any) -> None:
        if (
            self._api.get_string(
                provider, NCRYPT_NAME_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
            )
            != PROVIDER_NAME
        ):
            raise HarnessContractError("opened provider did not report the exact name")

    def _require_absent(self, provider: Any, identity: KeyIdentity, flags: int) -> None:
        result = self._api.try_open_key(provider, identity, flags)
        if result.handle is not None:
            result.handle.close()
            raise HarnessContractError(
                "TEST container already exists in a frozen scope"
            )
        if (result.status & 0xFFFFFFFF) not in REVIEWED_NOT_FOUND_STATUSES:
            raise SecurityStatusError("NCryptOpenKey absence probe", result.status)

    def _read_only_preflight(
        self, evidence: HarnessEvidence
    ) -> tuple[HarnessEvidence, PhaseCompletion]:
        if os.name != "nt" or sys.platform != "win32":
            raise HarnessContractError("native harness requires Windows")
        self._require_operator_token()
        validate_test_container(TEST_CONTAINER_TEXT)
        validate_key_identity(MACHINE_TEST_KEY)
        validate_key_identity(CURRENT_USER_SHADOW_KEY)
        validate_evidence_root(FUTURE_EVIDENCE_ROOT)
        if self._api.evidence_root_exists(FUTURE_EVIDENCE_ROOT):
            raise HarnessContractError("future evidence root already exists")
        with self._api.open_provider() as provider:
            self._require_provider_name(provider)
            if (
                self._api.get_dword(
                    provider,
                    NCRYPT_SECURITY_DESCR_SUPPORT_PROPERTY,
                    NCRYPT_PROPERTY_GET_FLAGS,
                )
                != 1
            ):
                raise HarnessContractError(
                    "provider security-descriptor support is not exactly DWORD 1"
                )
            self._require_absent(
                provider, MACHINE_TEST_KEY, NCRYPT_MACHINE_REOPEN_FLAGS
            )
            self._require_absent(
                provider, CURRENT_USER_SHADOW_KEY, NCRYPT_CURRENT_USER_REOPEN_FLAGS
            )
        return evidence, ReadOnlyPreflightCompletion(
            both_scope_absence_proved=True,
            future_evidence_root_absent=True,
            provider_security_descriptor_support=True,
            elevated_operator_sid=ELEVATED_TEST_OPERATOR_SID,
        )

    def _read_metadata(
        self,
        handle: Any,
        identity: KeyIdentity,
    ) -> KeyMetadata:
        name = self._api.get_string(
            handle, NCRYPT_NAME_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
        )
        if name != identity.container:
            raise HarnessContractError("key name readback is not exact")
        algorithm = self._api.get_string(
            handle, NCRYPT_ALGORITHM_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
        )
        group = self._api.get_string(
            handle, NCRYPT_ALGORITHM_GROUP_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
        )
        length = self._api.get_dword(
            handle, NCRYPT_LENGTH_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
        )
        key_type = self._api.get_dword(
            handle, NCRYPT_KEY_TYPE_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
        )
        public = normalize_ecc_public_blob(
            self._api.export_public(handle, NCRYPT_PUBLIC_EXPORT_FLAGS)
        )
        metadata = KeyMetadata(identity, key_type, algorithm, group, length, public)
        _validate_metadata_common(metadata)
        return metadata

    def _verify_machine_handle(
        self,
        handle: Any,
        expected_public: bytes | None = None,
        expected_unique_name: str | None = None,
    ) -> tuple[KeyMetadata, str]:
        metadata = self._read_metadata(handle, MACHINE_TEST_KEY)
        if metadata.key_type != NCRYPT_KEY_TYPE_MACHINE:
            raise HarnessContractError("machine key type is not exactly 0x20")
        if (
            self._api.get_dword(
                handle, NCRYPT_KEY_USAGE_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
            )
            != NCRYPT_ALLOW_SIGNING_FLAG
        ):
            raise HarnessContractError("machine usage is not signing-only")
        if (
            self._api.get_dword(
                handle, NCRYPT_EXPORT_POLICY_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
            )
            != NCRYPT_EXPORT_POLICY_NONE
        ):
            raise HarnessContractError("machine export policy is not zero")
        unique_name = self._api.get_string(
            handle, NCRYPT_UNIQUE_NAME_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
        )
        if not unique_name:
            raise HarnessContractError("machine unique name is empty")
        descriptor = self._api.decode_security_descriptor(
            self._api.get_bytes(
                handle,
                NCRYPT_SECURITY_DESCR_PROPERTY,
                NCRYPT_SECURITY_GET_FLAGS,
            )
        )
        verify_security_descriptor(descriptor)
        if expected_public is not None and metadata.public_sec1 != expected_public:
            raise HarnessContractError("machine public identity changed")
        if expected_unique_name is not None and unique_name != expected_unique_name:
            raise HarnessContractError("machine unique name changed")
        return metadata, unique_name

    def _open_exact(
        self, provider: Any, identity: KeyIdentity, flags: int
    ) -> OwnedNativeHandle:
        result = self._api.try_open_key(provider, identity, flags)
        check_security_status("NCryptOpenKey", result.status)
        if result.handle is None:
            raise HarnessContractError("successful open returned no owned key handle")
        return result.handle

    def _machine_create_and_validate(
        self, evidence: HarnessEvidence
    ) -> tuple[HarnessEvidence, PhaseCompletion]:
        self._require_operator_token()
        if NCRYPT_MACHINE_CREATE_FLAGS & NCRYPT_OVERWRITE_KEY_FLAG:
            raise HarnessContractError("machine create flags contain overwrite")
        with self._api.open_provider() as provider:
            self._require_provider_name(provider)
            self._effect_may_have_occurred = True
            with self._api.create_key(
                provider, MACHINE_TEST_KEY, NCRYPT_MACHINE_CREATE_FLAGS
            ) as key:
                evidence = record_machine_created(evidence)
                self._retain(evidence)
                self._api.set_dword(
                    key,
                    NCRYPT_KEY_USAGE_PROPERTY,
                    NCRYPT_ALLOW_SIGNING_FLAG,
                    NCRYPT_PROPERTY_SET_FLAGS,
                )
                if (
                    self._api.get_dword(
                        key, NCRYPT_KEY_USAGE_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
                    )
                    != NCRYPT_ALLOW_SIGNING_FLAG
                ):
                    raise HarnessContractError("pre-finalization usage readback failed")
                self._api.set_dword(
                    key,
                    NCRYPT_EXPORT_POLICY_PROPERTY,
                    NCRYPT_EXPORT_POLICY_NONE,
                    NCRYPT_PROPERTY_SET_FLAGS,
                )
                if (
                    self._api.get_dword(
                        key, NCRYPT_EXPORT_POLICY_PROPERTY, NCRYPT_PROPERTY_GET_FLAGS
                    )
                    != NCRYPT_EXPORT_POLICY_NONE
                ):
                    raise HarnessContractError(
                        "pre-finalization export-policy readback failed"
                    )
                descriptor_bytes = self._api.build_exact_security_descriptor()
                verify_security_descriptor(
                    self._api.decode_security_descriptor(descriptor_bytes)
                )
                self._api.set_bytes(
                    key,
                    NCRYPT_SECURITY_DESCR_PROPERTY,
                    descriptor_bytes,
                    NCRYPT_SECURITY_SET_FLAGS,
                )
                verify_security_descriptor(
                    self._api.decode_security_descriptor(
                        self._api.get_bytes(
                            key,
                            NCRYPT_SECURITY_DESCR_PROPERTY,
                            NCRYPT_SECURITY_GET_FLAGS,
                        )
                    )
                )
                self._api.finalize_key(key, NCRYPT_FINALIZE_FLAGS)
                machine_metadata, unique_name = self._verify_machine_handle(key)
            with self._open_exact(
                provider, MACHINE_TEST_KEY, NCRYPT_MACHINE_REOPEN_FLAGS
            ) as reopened:
                reopened_metadata, _ = self._verify_machine_handle(
                    reopened,
                    expected_public=machine_metadata.public_sec1,
                    expected_unique_name=unique_name,
                )
        if reopened_metadata != machine_metadata:
            raise HarnessContractError(
                "machine metadata changed after independent reopen"
            )
        return evidence, MachineValidationCompletion(
            machine_metadata=machine_metadata,
            exact_properties_verified=True,
            security_descriptor_verified=True,
            independent_reopen_verified=True,
        )

    def _machine_completion(
        self, evidence: HarnessEvidence
    ) -> MachineValidationCompletion:
        for record in evidence.phases:
            completion = record.state_snapshot.completion
            if isinstance(completion, MachineValidationCompletion):
                return completion
        raise HarnessContractError("retained machine completion is absent")

    def _shadow_completion(self, evidence: HarnessEvidence) -> ShadowScopeCompletion:
        for record in evidence.phases:
            completion = record.state_snapshot.completion
            if isinstance(completion, ShadowScopeCompletion):
                return completion
        raise HarnessContractError("retained shadow completion is absent")

    def _shadow_create_and_scope_proof(
        self, evidence: HarnessEvidence
    ) -> tuple[HarnessEvidence, PhaseCompletion]:
        self._require_operator_token()
        if NCRYPT_CURRENT_USER_CREATE_FLAGS & (
            NCRYPT_MACHINE_KEY_FLAG | NCRYPT_OVERWRITE_KEY_FLAG
        ):
            raise HarnessContractError(
                "shadow create flags contain forbidden scope/overwrite"
            )
        machine_expected = self._machine_completion(evidence).machine_metadata
        with self._api.open_provider() as provider:
            self._require_provider_name(provider)
            self._effect_may_have_occurred = True
            with self._api.create_key(
                provider, CURRENT_USER_SHADOW_KEY, NCRYPT_CURRENT_USER_CREATE_FLAGS
            ) as shadow_key:
                evidence = record_shadow_created(evidence)
                self._retain(evidence)
                self._api.finalize_key(shadow_key, NCRYPT_FINALIZE_FLAGS)
                shadow_frozen = self._read_metadata(shadow_key, CURRENT_USER_SHADOW_KEY)
            with self._open_exact(
                provider,
                CURRENT_USER_SHADOW_KEY,
                NCRYPT_CURRENT_USER_REOPEN_FLAGS,
            ) as shadow_reopened:
                shadow_metadata = self._read_metadata(
                    shadow_reopened, CURRENT_USER_SHADOW_KEY
                )
            if shadow_metadata != shadow_frozen:
                raise HarnessContractError("shadow identity changed after reopen")
            with self._open_exact(
                provider, MACHINE_TEST_KEY, NCRYPT_MACHINE_REOPEN_FLAGS
            ) as machine_reopened:
                machine_metadata, _ = self._verify_machine_handle(
                    machine_reopened,
                    expected_public=machine_expected.public_sec1,
                )
        verify_scope_non_substitution(machine_metadata, shadow_metadata)
        return evidence, ShadowScopeCompletion(
            machine_metadata=machine_metadata,
            shadow_metadata=shadow_metadata,
            scope_non_substitution_verified=True,
        )

    def _elevated_machine_effect_test(
        self, evidence: HarnessEvidence
    ) -> tuple[HarnessEvidence, PhaseCompletion]:
        self._require_operator_token()
        machine_public = self._shadow_completion(evidence).machine_metadata.public_sec1
        with self._api.open_provider() as provider:
            self._require_provider_name(provider)
            with self._open_exact(
                provider, MACHINE_TEST_KEY, NCRYPT_MACHINE_REOPEN_FLAGS
            ) as machine_key:
                for probe in PrivateExportProbe:
                    evidence = begin_private_export_denial_probe(
                        evidence, MACHINE_TEST_KEY, probe
                    )
                    self._retain(evidence)
                    self._effect_may_have_occurred = True
                    status = self._api.private_export_probe_status(
                        machine_key, probe.value, NCRYPT_PUBLIC_EXPORT_FLAGS
                    )
                    outcome = classify_private_export_status(status)
                    evidence = record_private_export_probe_outcome(
                        evidence, probe, outcome
                    )
                    self._retain(evidence)
                if not _all_probes_denied_as_required(
                    evidence.private_export_probe_results
                ):
                    raise HarnessContractError(
                        "private-export matrix did not produce exact policy denials"
                    )
                evidence = begin_test_signature(evidence, MACHINE_TEST_KEY)
                self._retain(evidence)
                digest = hashlib.sha256(TEST_SIGNATURE_PREIMAGE).digest()
                self._effect_may_have_occurred = True
                signature = self._api.sign_hash(machine_key, digest, NCRYPT_SILENT_FLAG)
                if not verify_test_signature_p1363(machine_public, digest, signature):
                    evidence = record_test_signature_outcome(
                        evidence, SignatureOutcome.FAILED
                    )
                    self._retain(evidence)
                    raise HarnessContractError("TEST signature verification failed")
                evidence = record_test_signature_outcome(
                    evidence, SignatureOutcome.SUCCEEDED
                )
                self._retain(evidence)
        return evidence, ElevatedEffectCompletion(
            signature_verified_with_machine_public=True,
            private_export_denial_matrix_verified=True,
        )

    def _principal_denial(
        self, evidence: HarnessEvidence
    ) -> tuple[HarnessEvidence, PhaseCompletion]:
        phase = determine_next_phase(evidence)
        actor_sid = _expected_actor(phase)
        facts = self._api.current_token_facts()
        if facts.user_sid != actor_sid:
            raise HarnessContractError("current genuine process token SID is wrong")
        if facts.elevated or facts.elevation_type_full or facts.administrators_enabled:
            raise HarnessContractError("denial phase requires a non-elevated token")
        with self._api.open_provider() as provider:
            self._require_provider_name(provider)
            result = self._api.try_open_key(
                provider, MACHINE_TEST_KEY, NCRYPT_MACHINE_REOPEN_FLAGS
            )
            if result.handle is not None:
                result.handle.close()
                raise HarnessContractError("non-admin unexpectedly opened machine key")
            if (result.status & 0xFFFFFFFF) not in REVIEWED_ACCESS_DENIED_STATUSES:
                raise SecurityStatusError("NCryptOpenKey denial proof", result.status)
        return evidence, PrincipalDenialCompletion(
            actor_sid=actor_sid,
            machine_open_denied=True,
            downstream_private_operations_unreachable=True,
        )

    def _final_reconciliation(
        self, evidence: HarnessEvidence
    ) -> tuple[HarnessEvidence, PhaseCompletion]:
        self._require_operator_token()
        validate_harness_evidence(evidence)
        if len(evidence.phases) != len(PHASE_ORDER) - 1:
            raise HarnessContractError("final reconciliation lacks the complete chain")
        if any(
            record.outcome is not PhaseOutcome.SUCCEEDED for record in evidence.phases
        ):
            raise HarnessContractError(
                "final reconciliation has a terminal predecessor"
            )
        if evidence.signature_outcome is not SignatureOutcome.SUCCEEDED or not (
            _all_probes_denied_as_required(evidence.private_export_probe_results)
        ):
            raise HarnessContractError("final reconciliation has unresolved effects")
        expected = self._shadow_completion(evidence)
        with self._api.open_provider() as provider:
            self._require_provider_name(provider)
            with self._open_exact(
                provider, MACHINE_TEST_KEY, NCRYPT_MACHINE_REOPEN_FLAGS
            ) as machine_key:
                machine, _ = self._verify_machine_handle(
                    machine_key, expected_public=expected.machine_metadata.public_sec1
                )
            with self._open_exact(
                provider,
                CURRENT_USER_SHADOW_KEY,
                NCRYPT_CURRENT_USER_REOPEN_FLAGS,
            ) as shadow_key:
                shadow = self._read_metadata(shadow_key, CURRENT_USER_SHADOW_KEY)
        if machine != expected.machine_metadata or shadow != expected.shadow_metadata:
            raise HarnessContractError("retained key identities contradict snapshots")
        verify_scope_non_substitution(machine, shadow)
        return evidence, FinalReconciliationCompletion(
            all_phase_evidence_reconciled=True,
            both_scope_qualified_keys_retained=True,
            cleanup_performed=False,
        )


class _AclSizeInformation(ctypes.Structure):
    _fields_ = [
        ("ace_count", ctypes.c_uint32),
        ("acl_bytes_in_use", ctypes.c_uint32),
        ("acl_bytes_free", ctypes.c_uint32),
    ]


class _AclHeader(ctypes.Structure):
    _fields_ = [
        ("revision", ctypes.c_ubyte),
        ("sbz1", ctypes.c_ubyte),
        ("acl_size", ctypes.c_uint16),
        ("ace_count", ctypes.c_uint16),
        ("sbz2", ctypes.c_uint16),
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


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("sid", ctypes.c_void_p), ("attributes", ctypes.c_uint32)]


class _TokenUser(ctypes.Structure):
    _fields_ = [("user", _SidAndAttributes)]


class _SecurityDescriptorAbsolute(ctypes.Structure):
    _fields_ = [
        ("revision", ctypes.c_ubyte),
        ("sbz1", ctypes.c_ubyte),
        ("control", ctypes.c_uint16),
        ("owner", ctypes.c_void_p),
        ("group", ctypes.c_void_p),
        ("sacl", ctypes.c_void_p),
        ("dacl", ctypes.c_void_p),
    ]


def _sid_binary(sid: str) -> bytes:
    parts = sid.split("-")
    if len(parts) < 4 or parts[0] != "S":
        raise HarnessContractError("SID text is malformed")
    try:
        revision = int(parts[1], 10)
        authority = int(parts[2], 10)
        subauthorities = [int(part, 10) for part in parts[3:]]
    except ValueError as error:
        raise HarnessContractError("SID text is malformed") from error
    if revision != 1 or not 0 <= authority < (1 << 48):
        raise HarnessContractError("SID revision/authority is unsupported")
    if not 1 <= len(subauthorities) <= 15 or any(
        value < 0 or value > 0xFFFFFFFF for value in subauthorities
    ):
        raise HarnessContractError("SID subauthority is invalid")
    return (
        bytes((revision, len(subauthorities)))
        + authority.to_bytes(6, "big")
        + b"".join(value.to_bytes(4, "little") for value in subauthorities)
    )


def build_exact_security_descriptor_bytes() -> bytes:
    """Build the exact self-relative owner/protected two-allow DACL."""

    owner = _sid_binary(ADMINISTRATORS_SID)
    system = _sid_binary(LOCAL_SYSTEM_SID)
    administrators = _sid_binary(ADMINISTRATORS_SID)

    def allow_ace(sid_bytes: bytes) -> bytes:
        size = 8 + len(sid_bytes)
        return (
            struct.pack(
                "<BBHI", ACCESS_ALLOWED_ACE_TYPE, 0, size, CRYPTO_KEY_FULL_CONTROL
            )
            + sid_bytes
        )

    ace_bytes = allow_ace(system) + allow_ace(administrators)
    acl_size = ctypes.sizeof(_AclHeader) + len(ace_bytes)
    acl = struct.pack("<BBHHH", ACL_REVISION, 0, acl_size, 2, 0) + ace_bytes
    owner_offset = 20
    dacl_offset = (owner_offset + len(owner) + 3) & ~3
    padding = b"\x00" * (dacl_offset - owner_offset - len(owner))
    header = struct.pack(
        "<BBHLLLL",
        1,
        0,
        SE_SELF_RELATIVE | SE_DACL_PRESENT | SE_DACL_PROTECTED,
        owner_offset,
        0,
        0,
        dacl_offset,
    )
    return header + owner + padding + acl


def _bounded_pointer(
    pointer: int | None,
    size: int,
    base: int,
    total: int,
    label: str,
) -> int:
    if pointer is None or pointer == 0 or size < 0:
        raise HarnessContractError(f"{label} pointer/size is invalid")
    if pointer < base or pointer > base + total:
        raise HarnessContractError(f"{label} pointer is outside the descriptor")
    if size > total or pointer + size > base + total:
        raise HarnessContractError(f"{label} extends outside the descriptor")
    return pointer


def _bounded_native_slice_end(
    offset: int,
    size: int,
    total: int,
    label: str,
) -> int:
    if offset < 0 or size < 0 or offset > total or size > total - offset:
        raise HarnessContractError(f"{label} extends outside the descriptor")
    return offset + size


def _bounded_native_sid_length(
    value: bytes,
    offset: int,
    range_start: int,
    range_end: int,
    label: str,
) -> int:
    if range_start < 0 or range_end > len(value) or range_start > range_end:
        raise HarnessContractError(f"{label} containing range is invalid")
    if offset < range_start or offset > range_end:
        raise HarnessContractError(f"{label} offset is outside its containing range")
    if offset > range_end - 8:
        raise HarnessContractError(f"{label} is shorter than a SID header")
    revision = value[offset]
    subauthority_count = value[offset + 1]
    if revision != 1 or subauthority_count > 15:
        raise HarnessContractError(f"{label} header is invalid")
    sid_length = 8 + 4 * subauthority_count
    if offset > range_end - sid_length:
        raise HarnessContractError(f"{label} extends outside its containing range")
    return sid_length


def decode_native_security_descriptor(
    value: bytes,
    functions: Mapping[str, Callable[..., Any]],
) -> SecurityDescriptorSemantic:
    """Decode provider bytes after pure bounds checks, then cross-check Windows."""

    if len(value) < 20:
        raise HarnessContractError("security descriptor is shorter than its header")
    (
        native_revision,
        sbz1,
        native_control,
        owner_offset,
        group_offset,
        sacl_offset,
        dacl_offset,
    ) = struct.unpack_from("<BBHLLLL", value, 0)
    if native_revision != 1 or sbz1 != 0:
        raise HarnessContractError("security descriptor header is malformed")
    if not native_control & SE_SELF_RELATIVE:
        raise HarnessContractError("security descriptor is not self-relative")
    if not native_control & SE_DACL_PRESENT:
        raise HarnessContractError("security descriptor does not declare a DACL")
    if group_offset != 0 or sacl_offset != 0:
        raise HarnessContractError("unexpected group or SACL data is present")
    if owner_offset < 20 or dacl_offset < 20:
        raise HarnessContractError(
            "owner or DACL offset overlaps the descriptor header"
        )

    if owner_offset % 4 or dacl_offset % 4:
        raise HarnessContractError("owner or DACL offset is not DWORD-aligned")
    owner_length = _bounded_native_sid_length(
        value, owner_offset, 20, len(value), "owner SID"
    )
    owner_end = _bounded_native_slice_end(
        owner_offset, owner_length, len(value), "owner SID"
    )
    dacl_header_end = _bounded_native_slice_end(
        dacl_offset, 8, len(value), "DACL header"
    )
    if owner_offset >= dacl_offset or owner_end > dacl_offset:
        raise HarnessContractError("owner SID and DACL ranges overlap or are reordered")

    acl_revision, acl_sbz1, acl_size, ace_count, acl_sbz2 = struct.unpack_from(
        "<BBHHH", value, dacl_offset
    )
    if acl_revision not in (ACL_REVISION, ACL_REVISION_DS):
        raise HarnessContractError("DACL revision is invalid")
    if acl_sbz1 != 0 or acl_sbz2 != 0:
        raise HarnessContractError("DACL reserved fields are nonzero")
    if acl_size < dacl_header_end - dacl_offset:
        raise HarnessContractError("DACL size is shorter than its header")
    dacl_end = _bounded_native_slice_end(dacl_offset, acl_size, len(value), "DACL")
    if dacl_end != len(value):
        raise HarnessContractError("DACL has trailing or detached descriptor bytes")
    if ace_count > (acl_size - 8) // 16:
        raise HarnessContractError("DACL ACE count cannot fit inside its byte length")

    manual_aces: list[tuple[int, int, int]] = []
    ace_offset = dacl_offset + 8
    for index in range(ace_count):
        _bounded_native_slice_end(ace_offset, 4, dacl_end, f"ACE {index} header")
        ace_type, _, ace_size = struct.unpack_from("<BBH", value, ace_offset)
        if ace_type != ACCESS_ALLOWED_ACE_TYPE:
            raise HarnessContractError("ACE does not have the frozen allow-ACE shape")
        if ace_size < 16:
            raise HarnessContractError("ACE is shorter than ACCESS_ALLOWED_ACE")
        ace_end = _bounded_native_slice_end(
            ace_offset, ace_size, dacl_end, f"ACE {index}"
        )
        sid_offset = ace_offset + 8
        sid_length = _bounded_native_sid_length(
            value, sid_offset, ace_offset, ace_end, f"ACE {index} SID"
        )
        if sid_offset + sid_length != ace_end:
            raise HarnessContractError("ACE contains trailing or truncated SID bytes")
        manual_aces.append((ace_offset, ace_size, sid_length))
        ace_offset = ace_end
    if ace_offset != dacl_end:
        raise HarnessContractError("DACL contains unclaimed or truncated ACE bytes")

    # No pointer-taking Windows routine is called until every native range above is
    # independently proven to be contained by the returned byte string.
    buffer = ctypes.create_string_buffer(value, len(value))
    base = ctypes.addressof(buffer)
    descriptor = ctypes.c_void_p(base)

    def require_bool(name: str, *args: Any) -> None:
        if not bool(functions[name](*args)):
            raise HarnessContractError(f"{name} rejected native security data")

    require_bool("IsValidSecurityDescriptor", descriptor)
    returned_length = int(functions["GetSecurityDescriptorLength"](descriptor))
    if returned_length != len(value):
        raise HarnessContractError("security descriptor length/trailing bytes mismatch")

    def sid_text(pointer: int, expected_length: int, label: str) -> str:
        _bounded_pointer(pointer, expected_length, base, len(value), label)
        sid_pointer = ctypes.c_void_p(pointer)
        require_bool("IsValidSid", sid_pointer)
        sid_length = int(functions["GetLengthSid"](sid_pointer))
        if sid_length != expected_length:
            raise HarnessContractError(f"{label} native and bounded lengths disagree")
        converted = ctypes.c_wchar_p()
        converted_ok = bool(
            functions["ConvertSidToStringSidW"](sid_pointer, ctypes.byref(converted))
        )
        allocation = ctypes.cast(converted, ctypes.c_void_p).value
        if not converted_ok:
            if allocation is not None:
                if functions["LocalFree"](ctypes.c_void_p(allocation)):
                    raise HandleReleaseError(
                        "LocalFree failed after SID conversion failure"
                    )
            raise HarnessContractError("ConvertSidToStringSidW rejected SID")
        if allocation is None:
            raise HarnessContractError("SID conversion returned no allocation")

        def release_local(pointer_value: int) -> None:
            if functions["LocalFree"](ctypes.c_void_p(pointer_value)):
                raise HandleReleaseError("LocalFree failed for SID string")

        with OwnedNativeHandle(allocation, release_local, "SID string allocation"):
            text = converted.value
            if text is None:
                raise HarnessContractError("SID conversion returned null text")
            return text

    owner_pointer = ctypes.c_void_p()
    owner_defaulted = ctypes.c_int()
    require_bool(
        "GetSecurityDescriptorOwner",
        descriptor,
        ctypes.byref(owner_pointer),
        ctypes.byref(owner_defaulted),
    )
    expected_owner_address = base + owner_offset
    if owner_pointer.value != expected_owner_address:
        raise HarnessContractError("native owner pointer disagrees with bounded offset")
    owner_sid = sid_text(expected_owner_address, owner_length, "owner SID")

    control = ctypes.c_uint16()
    revision = ctypes.c_uint32()
    require_bool(
        "GetSecurityDescriptorControl",
        descriptor,
        ctypes.byref(control),
        ctypes.byref(revision),
    )
    if revision.value != 1:
        raise HarnessContractError("security descriptor revision is not one")
    if control.value != native_control:
        raise HarnessContractError("native descriptor control disagrees with header")

    dacl_present = ctypes.c_int()
    dacl_pointer = ctypes.c_void_p()
    dacl_defaulted = ctypes.c_int()
    require_bool(
        "GetSecurityDescriptorDacl",
        descriptor,
        ctypes.byref(dacl_present),
        ctypes.byref(dacl_pointer),
        ctypes.byref(dacl_defaulted),
    )
    if not dacl_present.value or dacl_pointer.value is None:
        raise HarnessContractError("security descriptor DACL is missing or NULL")
    dacl_address = base + dacl_offset
    if dacl_pointer.value != dacl_address:
        raise HarnessContractError("native DACL pointer disagrees with bounded offset")
    size_info = _AclSizeInformation()
    require_bool(
        "GetAclInformation",
        dacl_pointer,
        ctypes.byref(size_info),
        ctypes.sizeof(size_info),
        2,
    )
    if size_info.acl_bytes_in_use != acl_size:
        raise HarnessContractError("DACL header and API sizes disagree")
    if size_info.ace_count != ace_count:
        raise HarnessContractError("DACL header and API ACE counts disagree")
    if size_info.acl_bytes_free != 0:
        raise HarnessContractError("DACL API reported unclaimed bytes")

    aces: list[AceSemantic] = []
    for index, (manual_offset, ace_size, sid_length) in enumerate(manual_aces):
        ace_pointer = ctypes.c_void_p()
        require_bool("GetAce", dacl_pointer, index, ctypes.byref(ace_pointer))
        ace_address = base + manual_offset
        if ace_pointer.value != ace_address:
            raise HarnessContractError(
                f"native ACE {index} pointer disagrees with bounded offset"
            )
        ace_type, ace_flags, native_ace_size = struct.unpack_from(
            "<BBH", value, manual_offset
        )
        if native_ace_size != ace_size:  # pragma: no cover - parsed together above
            raise HarnessContractError("ACE size changed during decoding")
        access_mask = struct.unpack_from("<I", value, manual_offset + 4)[0]
        sid_address = ace_address + 8
        sid = sid_text(sid_address, sid_length, f"ACE {index} SID")
        aces.append(
            AceSemantic(
                ace_type=ace_type,
                ace_flags=ace_flags,
                sid=sid,
                access_mask=access_mask,
            )
        )
    return SecurityDescriptorSemantic(
        is_valid=True,
        owner_sid=owner_sid,
        owner_defaulted=bool(owner_defaulted.value),
        dacl_present=bool(dacl_present.value),
        dacl_is_null=False,
        dacl_defaulted=bool(dacl_defaulted.value),
        control=control.value,
        acl_revision=acl_revision,
        aces=tuple(aces),
    )


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


class CtypesNativeApi:
    """ctypes implementation for a future separately authorized Windows run."""

    requires_persistent_retainer = True

    def __init__(self, bindings: WindowsNativeBindings) -> None:
        _require_native_execution_authorized()
        self._functions = bindings.functions

    @classmethod
    def load_for_authorized_execution(cls) -> CtypesNativeApi:
        return cls(WindowsNativeBindings.load_for_authorized_execution())

    def _free_object(self, handle: Any) -> None:
        check_security_status(
            "NCryptFreeObject", int(self._functions["NCryptFreeObject"](handle))
        )

    def _close_token(self, handle: Any) -> None:
        if not bool(self._functions["CloseHandle"](handle)):
            raise HandleReleaseError("CloseHandle failed for process token")

    def _local_free(self, pointer: Any) -> None:
        if self._functions["LocalFree"](pointer):
            raise HandleReleaseError("LocalFree failed")

    def _sid_to_text(self, sid: Any) -> str:
        if not bool(self._functions["IsValidSid"](sid)):
            raise HarnessContractError("native SID is invalid")
        converted = ctypes.c_wchar_p()
        converted_ok = bool(
            self._functions["ConvertSidToStringSidW"](sid, ctypes.byref(converted))
        )
        if not converted_ok:
            failed_pointer = ctypes.cast(converted, ctypes.c_void_p).value
            if failed_pointer is not None:
                OwnedNativeHandle(
                    failed_pointer,
                    self._local_free,
                    "failed SID string allocation",
                ).close()
            raise HarnessContractError("ConvertSidToStringSidW failed")
        pointer = ctypes.cast(converted, ctypes.c_void_p).value
        if pointer is None:
            raise HarnessContractError("SID conversion returned a null allocation")
        with OwnedNativeHandle(pointer, self._local_free, "SID string allocation"):
            if converted.value is None:
                raise HarnessContractError("SID conversion returned null text")
            return converted.value

    def _string_sid(self, text: str) -> OwnedNativeHandle:
        pointer = ctypes.c_void_p()
        converted_ok = bool(
            self._functions["ConvertStringSidToSidW"](text, ctypes.byref(pointer))
        )
        if not converted_ok:
            if pointer.value is not None:
                OwnedNativeHandle(
                    pointer.value,
                    self._local_free,
                    "failed binary SID allocation",
                ).close()
            raise HarnessContractError("ConvertStringSidToSidW failed")
        return OwnedNativeHandle(
            pointer.value, self._local_free, "binary SID allocation"
        )

    def _token_information(self, token: Any, information_class: int) -> Any:
        required = ctypes.c_uint32()
        self._functions["GetTokenInformation"](
            token, information_class, None, 0, ctypes.byref(required)
        )
        if required.value == 0:
            raise HarnessContractError("GetTokenInformation size query failed")
        buffer = ctypes.create_string_buffer(required.value)
        returned = ctypes.c_uint32()
        if not bool(
            self._functions["GetTokenInformation"](
                token,
                information_class,
                buffer,
                required.value,
                ctypes.byref(returned),
            )
        ):
            raise HarnessContractError("GetTokenInformation data call failed")
        if returned.value != required.value:
            raise HarnessContractError("token information size changed")
        return buffer

    def current_token_facts(self) -> TokenFacts:
        token = ctypes.c_void_p()
        process = self._functions["GetCurrentProcess"]()
        if not bool(
            self._functions["OpenProcessToken"](process, 0x0008, ctypes.byref(token))
        ):
            if token.value is not None:
                OwnedNativeHandle(
                    token.value,
                    self._close_token,
                    "failed process token acquisition",
                ).close()
            raise HarnessContractError("OpenProcessToken failed")
        with OwnedNativeHandle(
            token.value, self._close_token, "process token"
        ) as owned:
            token_user_buffer = self._token_information(owned, 1)
            token_user = _TokenUser.from_buffer(token_user_buffer)
            user_sid = self._sid_to_text(token_user.user.sid)
            elevation_buffer = self._token_information(owned, 20)
            elevation_type_buffer = self._token_information(owned, 18)
            if (
                ctypes.sizeof(elevation_buffer) != 4
                or ctypes.sizeof(elevation_type_buffer) != 4
            ):
                raise HarnessContractError("token elevation data is malformed")
            elevated = struct.unpack("<I", elevation_buffer.raw)[0]
            elevation_type = struct.unpack("<I", elevation_type_buffer.raw)[0]
            if elevated not in (0, 1) or elevation_type not in (1, 2, 3):
                raise HarnessContractError("token elevation value is unexpected")
            with self._string_sid(ADMINISTRATORS_SID) as administrators_sid:
                enabled = ctypes.c_int()
                if not bool(
                    self._functions["CheckTokenMembership"](
                        owned, administrators_sid, ctypes.byref(enabled)
                    )
                ):
                    raise HarnessContractError("CheckTokenMembership failed")
        return TokenFacts(
            user_sid=user_sid,
            elevated=bool(elevated),
            elevation_type_full=elevation_type == 2,
            administrators_enabled=bool(enabled.value),
        )

    def evidence_root_exists(self, root: PureWindowsPath) -> bool:
        validate_evidence_root(root)
        return Path(str(root)).exists()

    def open_provider(self) -> OwnedNativeHandle:
        provider = ctypes.c_void_p()
        status = int(
            self._functions["NCryptOpenStorageProvider"](
                ctypes.byref(provider), PROVIDER_NAME, 0
            )
        )
        if status != 0 and provider.value is not None:
            OwnedNativeHandle(
                provider.value,
                self._free_object,
                "failed KSP provider acquisition",
            ).close()
            raise NativeOperationUncertain(
                "provider failure returned a handle that was released"
            ) from SecurityStatusError("NCryptOpenStorageProvider", status)
        check_security_status("NCryptOpenStorageProvider", status)
        return OwnedNativeHandle(provider.value, self._free_object, "KSP provider")

    def _raw_property(self, handle: Any, property_name: str, flags: int) -> bytes:
        required = ctypes.c_uint32()
        status = int(
            self._functions["NCryptGetProperty"](
                handle,
                property_name,
                None,
                0,
                ctypes.byref(required),
                flags,
            )
        )
        check_security_status(f"NCryptGetProperty({property_name}) size", status)
        if required.value == 0:
            raise HarnessContractError(f"{property_name} returned zero bytes")
        buffer = ctypes.create_string_buffer(required.value)
        returned = ctypes.c_uint32()
        status = int(
            self._functions["NCryptGetProperty"](
                handle,
                property_name,
                buffer,
                required.value,
                ctypes.byref(returned),
                flags,
            )
        )
        check_security_status(f"NCryptGetProperty({property_name}) data", status)
        if returned.value != required.value:
            raise HarnessContractError(f"{property_name} size changed between calls")
        return bytes(buffer.raw)

    def get_dword(self, handle: Any, property_name: str, flags: int) -> int:
        return parse_ncrypt_dword(
            self._raw_property(handle, property_name, flags), property_name
        )

    def get_string(self, handle: Any, property_name: str, flags: int) -> str:
        return parse_ncrypt_string(
            self._raw_property(handle, property_name, flags), property_name
        )

    def get_bytes(self, handle: Any, property_name: str, flags: int) -> bytes:
        return self._raw_property(handle, property_name, flags)

    def _validate_scope_flags(self, identity: KeyIdentity, flags: int) -> None:
        validate_key_identity(identity)
        has_machine = bool(flags & NCRYPT_MACHINE_KEY_FLAG)
        if has_machine != (identity.scope is KeyScope.LOCAL_MACHINE):
            raise HarnessContractError("NCrypt flags do not match the frozen key scope")

    def try_open_key(
        self,
        provider: Any,
        identity: KeyIdentity,
        flags: int,
    ) -> NativeOpenResult:
        self._validate_scope_flags(identity, flags)
        key = ctypes.c_void_p()
        status = int(
            self._functions["NCryptOpenKey"](
                provider,
                ctypes.byref(key),
                identity.container,
                0,
                flags,
            )
        )
        if status != 0:
            if key.value is not None:
                OwnedNativeHandle(
                    key.value, self._free_object, "failed NCrypt key acquisition"
                ).close()
                raise NativeOperationUncertain(
                    "failed key open returned a handle that was released"
                ) from SecurityStatusError("NCryptOpenKey", status)
            return NativeOpenResult(status & 0xFFFFFFFF, None)
        return NativeOpenResult(
            0, OwnedNativeHandle(key.value, self._free_object, "NCrypt key")
        )

    def create_key(
        self,
        provider: Any,
        identity: KeyIdentity,
        flags: int,
    ) -> OwnedNativeHandle:
        self._validate_scope_flags(identity, flags)
        if flags & NCRYPT_OVERWRITE_KEY_FLAG:
            raise HarnessContractError(
                "NCryptCreatePersistedKey overwrite is forbidden"
            )
        key = ctypes.c_void_p()
        status = int(
            self._functions["NCryptCreatePersistedKey"](
                provider,
                ctypes.byref(key),
                ALGORITHM_NAME,
                identity.container,
                0,
                flags,
            )
        )
        if status != 0 and key.value is not None:
            OwnedNativeHandle(
                key.value,
                self._free_object,
                "failed created NCrypt key acquisition",
            ).close()
            raise NativeOperationUncertain(
                "failed key creation returned a handle that was released"
            ) from SecurityStatusError("NCryptCreatePersistedKey", status)
        acquired = require_successful_effect_handle(
            "NCryptCreatePersistedKey", status, key.value
        )
        return OwnedNativeHandle(acquired, self._free_object, "created NCrypt key")

    def _set_property(
        self, handle: Any, property_name: str, value: bytes, flags: int
    ) -> None:
        if not value:
            raise HarnessContractError("NCryptSetProperty value cannot be empty")
        buffer = ctypes.create_string_buffer(value, len(value))
        status = int(
            self._functions["NCryptSetProperty"](
                handle,
                property_name,
                buffer,
                len(value),
                flags,
            )
        )
        check_security_status(f"NCryptSetProperty({property_name})", status)

    def set_dword(
        self,
        handle: Any,
        property_name: str,
        value: int,
        flags: int,
    ) -> None:
        if not 0 <= value <= 0xFFFFFFFF:
            raise HarnessContractError("DWORD property value is out of range")
        self._set_property(handle, property_name, struct.pack("<I", value), flags)

    def set_bytes(
        self,
        handle: Any,
        property_name: str,
        value: bytes,
        flags: int,
    ) -> None:
        self._set_property(handle, property_name, value, flags)

    def build_exact_security_descriptor(self) -> bytes:
        with self._string_sid(ADMINISTRATORS_SID) as administrators_sid:
            with self._string_sid(LOCAL_SYSTEM_SID) as system_sid:
                administrators_length = int(
                    self._functions["GetLengthSid"](administrators_sid)
                )
                system_length = int(self._functions["GetLengthSid"](system_sid))
                if administrators_length <= 0 or system_length <= 0:
                    raise HarnessContractError(
                        "security principal SID length is invalid"
                    )
                acl_size = (
                    ctypes.sizeof(_AclHeader)
                    + 8
                    + system_length
                    + 8
                    + administrators_length
                )
                acl = ctypes.create_string_buffer(acl_size)
                if not bool(
                    self._functions["InitializeAcl"](acl, acl_size, ACL_REVISION)
                ):
                    raise HarnessContractError("InitializeAcl failed")
                for sid in (system_sid, administrators_sid):
                    if not bool(
                        self._functions["AddAccessAllowedAceEx"](
                            acl,
                            ACL_REVISION,
                            0,
                            CRYPTO_KEY_FULL_CONTROL,
                            sid,
                        )
                    ):
                        raise HarnessContractError("AddAccessAllowedAceEx failed")

                absolute = ctypes.create_string_buffer(
                    ctypes.sizeof(_SecurityDescriptorAbsolute)
                )
                if not bool(
                    self._functions["InitializeSecurityDescriptor"](absolute, 1)
                ):
                    raise HarnessContractError("InitializeSecurityDescriptor failed")
                if not bool(
                    self._functions["SetSecurityDescriptorOwner"](
                        absolute, administrators_sid, False
                    )
                ):
                    raise HarnessContractError("SetSecurityDescriptorOwner failed")
                if not bool(
                    self._functions["SetSecurityDescriptorDacl"](
                        absolute, True, acl, False
                    )
                ):
                    raise HarnessContractError("SetSecurityDescriptorDacl failed")
                if not bool(
                    self._functions["SetSecurityDescriptorControl"](
                        absolute, SE_DACL_PROTECTED, SE_DACL_PROTECTED
                    )
                ):
                    raise HarnessContractError("SetSecurityDescriptorControl failed")

                required = ctypes.c_uint32()
                ctypes.set_last_error(0)
                if bool(
                    self._functions["MakeSelfRelativeSD"](
                        absolute, None, ctypes.byref(required)
                    )
                ):
                    raise HarnessContractError(
                        "MakeSelfRelativeSD size query unexpectedly succeeded"
                    )
                if ctypes.get_last_error() != 122 or required.value < 20:
                    raise HarnessContractError(
                        "MakeSelfRelativeSD size query did not return "
                        "exact insufficiency"
                    )
                relative = ctypes.create_string_buffer(required.value)
                returned = ctypes.c_uint32(required.value)
                if not bool(
                    self._functions["MakeSelfRelativeSD"](
                        absolute, relative, ctypes.byref(returned)
                    )
                ):
                    raise HarnessContractError("MakeSelfRelativeSD data call failed")
                if returned.value != required.value:
                    raise HarnessContractError(
                        "MakeSelfRelativeSD size changed between calls"
                    )
                value = bytes(relative.raw)
        verify_security_descriptor(self.decode_security_descriptor(value))
        return value

    def decode_security_descriptor(self, value: bytes) -> SecurityDescriptorSemantic:
        return decode_native_security_descriptor(value, self._functions)

    def finalize_key(self, handle: Any, flags: int) -> None:
        check_security_status(
            "NCryptFinalizeKey",
            int(self._functions["NCryptFinalizeKey"](handle, flags)),
        )

    def _export(self, handle: Any, blob_type: str, flags: int) -> bytes:
        required = ctypes.c_uint32()
        status = int(
            self._functions["NCryptExportKey"](
                handle,
                None,
                blob_type,
                None,
                None,
                0,
                ctypes.byref(required),
                flags,
            )
        )
        check_security_status(f"NCryptExportKey({blob_type}) size", status)
        if required.value == 0:
            raise HarnessContractError("public export returned zero bytes")
        buffer = ctypes.create_string_buffer(required.value)
        returned = ctypes.c_uint32()
        status = int(
            self._functions["NCryptExportKey"](
                handle,
                None,
                blob_type,
                None,
                buffer,
                required.value,
                ctypes.byref(returned),
                flags,
            )
        )
        check_security_status(f"NCryptExportKey({blob_type}) data", status)
        if returned.value != required.value:
            raise HarnessContractError("public export size changed")
        return bytes(buffer.raw)

    def export_public(self, handle: Any, flags: int) -> bytes:
        return self._export(handle, BCRYPT_ECCPUBLIC_BLOB, flags)

    def private_export_probe_status(
        self,
        handle: Any,
        blob_type: str,
        flags: int,
    ) -> int:
        if blob_type not in {probe.value for probe in PrivateExportProbe}:
            raise HarnessContractError("private-export blob type is not in the matrix")
        required = ctypes.c_uint32()
        return (
            int(
                self._functions["NCryptExportKey"](
                    handle,
                    None,
                    blob_type,
                    None,
                    None,
                    0,
                    ctypes.byref(required),
                    flags,
                )
            )
            & 0xFFFFFFFF
        )

    def sign_hash(self, handle: Any, digest: bytes, flags: int) -> bytes:
        if len(digest) != 32:
            raise HarnessContractError("TEST signature digest must be SHA-256")
        digest_buffer = ctypes.create_string_buffer(digest, len(digest))
        required = ctypes.c_uint32()
        status = int(
            self._functions["NCryptSignHash"](
                handle,
                None,
                digest_buffer,
                len(digest),
                None,
                0,
                ctypes.byref(required),
                flags,
            )
        )
        check_security_status("NCryptSignHash size", status)
        if required.value != 64:
            raise NativeOperationUncertain(
                "successful signature size query did not return exactly 64 bytes"
            )
        signature = ctypes.create_string_buffer(required.value)
        returned = ctypes.c_uint32()
        status = int(
            self._functions["NCryptSignHash"](
                handle,
                None,
                digest_buffer,
                len(digest),
                signature,
                required.value,
                ctypes.byref(returned),
                flags,
            )
        )
        check_security_status("NCryptSignHash data", status)
        if returned.value != required.value:
            raise NativeOperationUncertain(
                "successful signature call returned an invalid output length"
            )
        return bytes(signature.raw)


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
        "ordinary_nonadmin_selection_requires_review": (
            ORDINARY_NONADMIN_SELECTION_REQUIRES_REVIEW
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
