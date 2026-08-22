"""Production Windows authority substrate for architecture 77.

The module keeps the portable authority contract (fixed paths, canonical
bootstrap, identity, policy descriptions, and typed failures) import-safe on
every platform.  Native Win32 work is deliberately isolated behind functions
that check the platform before loading a DLL or opening a handle.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import PureWindowsPath
from uuid import UUID

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR

# ---------------------------------------------------------------------------
# Typed failures


class WindowsAuthorityError(Exception):
    """Base class for fail-closed authority failures."""


class UnsupportedWindowsPlatformError(WindowsAuthorityError):
    """Raised when a native Windows-only operation is requested elsewhere."""


class AuthorityPathError(WindowsAuthorityError, ValueError):
    """Raised when a path is not one of the fixed authority paths."""


class AuthorityObjectError(WindowsAuthorityError):
    """Raised when an authority object has an unsafe type or final path."""


class WindowsNativeError(WindowsAuthorityError):
    """Raised for a failed Win32 call without exposing native text to reports."""

    def __init__(self, operation: str, error_code: int | None = None) -> None:
        self.operation = operation
        self.error_code = error_code
        suffix = "" if error_code is None else f" (win32={error_code})"
        super().__init__(f"Windows operation failed: {operation}{suffix}")


class AuthorityRecoveryRequiredError(WindowsAuthorityError):
    """Raised when administrator manual recovery is required before retry."""


class BootstrapError(WindowsAuthorityError, ValueError):
    """Base class for malformed or unsupported signed bootstrap material."""


class BootstrapSyntaxError(BootstrapError):
    """Raised when bootstrap bytes are not strict canonical JSON."""


class BootstrapSchemaError(BootstrapError):
    """Raised when bootstrap fields or values violate the accepted schema."""


class UnsupportedBootstrapError(BootstrapError):
    """Raised when a validly shaped bootstrap selects unsupported policy."""


class BootstrapSignatureError(BootstrapError):
    """Raised when detached signature material is malformed or invalid."""


class BootstrapTrustAnchorError(BootstrapSignatureError):
    """Raised when the pinned production trust anchor is absent or mismatched."""


class AuthorityPrincipalError(WindowsAuthorityError):
    """Raised when the local dedicated Trading principal is not approved."""


class AuthoritySecurityError(WindowsAuthorityError):
    """Raised when an owner, DACL, inheritance, or ACE is unsafe."""


class AdministratorRequiredError(WindowsAuthorityError):
    """Raised when provisioning is attempted without an elevated token."""


class LifecycleMutexError(WindowsAuthorityError):
    """Base class for lifecycle mutex failures."""


class LifecycleMutexSecurityError(LifecycleMutexError):
    """Raised for a hostile or unexpected existing named mutex."""


class LifecycleMutexWaitError(LifecycleMutexError):
    """Raised when the named mutex cannot be acquired."""


UnsupportedPlatformError = UnsupportedWindowsPlatformError


# ---------------------------------------------------------------------------
# Fixed deployment paths


PRODUCTION_AUTHORITY_ROOT = PureWindowsPath(r"F:\AITradingBot\Authority")
PRODUCTION_AUTHORITY_ROOT_TEXT = str(PRODUCTION_AUTHORITY_ROOT)


@dataclass(frozen=True, slots=True)
class FixedAuthorityPaths:
    """The complete fixed production deployment layout."""

    root: PureWindowsPath = PRODUCTION_AUTHORITY_ROOT

    def __post_init__(self) -> None:
        if self.root != PRODUCTION_AUTHORITY_ROOT:
            raise AuthorityPathError("production authority root is code-owned")

    @property
    def bootstrap(self) -> PureWindowsPath:
        return self.root / "authority.bootstrap.json"

    @property
    def signature(self) -> PureWindowsPath:
        return self.root / "authority.bootstrap.sig"

    @property
    def database(self) -> PureWindowsPath:
        return self.root / "authority.sqlite3"

    @property
    def journal(self) -> PureWindowsPath:
        return self.root / "authority.sqlite3-journal"

    @property
    def capture_output(self) -> PureWindowsPath:
        return self.root / "capture-output"

    @property
    def backup(self) -> PureWindowsPath:
        return self.root / "backup"

    @property
    def bootstrap_temporary(self) -> PureWindowsPath:
        return self.root / ".authority.bootstrap.json.installing"

    @property
    def signature_temporary(self) -> PureWindowsPath:
        return self.root / ".authority.bootstrap.sig.installing"

    @property
    def provisioning_temporary_objects(self) -> tuple[PureWindowsPath, ...]:
        return (self.bootstrap_temporary, self.signature_temporary)

    @property
    def protected_objects(self) -> tuple[PureWindowsPath, ...]:
        return (
            self.root,
            self.bootstrap,
            self.signature,
            self.database,
            self.journal,
            self.capture_output,
            self.backup,
        )


PRODUCTION_AUTHORITY_PATHS = FixedAuthorityPaths()
PRODUCTION_AUTHORITY_DATABASE = PRODUCTION_AUTHORITY_PATHS.database
PRODUCTION_AUTHORITY_JOURNAL = PRODUCTION_AUTHORITY_PATHS.journal
PRODUCTION_AUTHORITY_BOOTSTRAP = PRODUCTION_AUTHORITY_PATHS.bootstrap
PRODUCTION_AUTHORITY_SIGNATURE = PRODUCTION_AUTHORITY_PATHS.signature
PRODUCTION_CAPTURE_OUTPUT_ROOT = PRODUCTION_AUTHORITY_PATHS.capture_output
PRODUCTION_BACKUP_ROOT = PRODUCTION_AUTHORITY_PATHS.backup
AuthorityPaths = FixedAuthorityPaths


def fixed_authority_paths() -> FixedAuthorityPaths:
    """Return the immutable production layout with no caller-selected root."""

    return PRODUCTION_AUTHORITY_PATHS


get_fixed_authority_paths = fixed_authority_paths


def require_fixed_authority_path(
    path: str | PureWindowsPath,
    expected: PureWindowsPath,
) -> PureWindowsPath:
    """Require a path string to equal the exact code-owned target."""

    if str(path) != str(expected):
        raise AuthorityPathError("path is not the exact fixed authority target")
    return expected


def require_fixed_authority_tree_path(
    path: str | PureWindowsPath,
) -> PureWindowsPath:
    """Require one of the fixed root-level authority objects."""

    for expected in PRODUCTION_AUTHORITY_PATHS.protected_objects:
        if str(path) == str(expected):
            return expected
    raise AuthorityPathError("path is outside the fixed authority deployment")


def require_fixed_authority_provisioning_temp_path(
    path: str | PureWindowsPath,
) -> PureWindowsPath:
    """Require one of the two code-owned provisioning temporary paths."""

    for expected in PRODUCTION_AUTHORITY_PATHS.provisioning_temporary_objects:
        if str(path) == str(expected):
            return expected
    raise AuthorityPathError("path is outside the fixed provisioning temporary set")


# ---------------------------------------------------------------------------
# Canonical signed bootstrap


SUPPORTED_BOOTSTRAP_SCHEMA = 1
SUPPORTED_AUTHORITY_POLICY_VERSION = "authority-policy/v1"
SUPPORTED_CLAIM_POLICY_VERSION = "claim-policy/v1"
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SID = re.compile(r"^S-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*))+$")
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_BOOTSTRAP_FIELDS = frozenset(
    {
        "approved_account_sid",
        "authority_epoch_id",
        "authority_policy_version",
        "bootstrap_generation",
        "bootstrap_schema",
        "claim_policy_version",
        "database_identity_digest",
        "database_path",
        "machine_authority_id",
        "output_root",
        "permitted_provider_operation",
        "provider_id",
        "signing_key_id",
    }
)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BootstrapSyntaxError("bootstrap contains duplicate object keys")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise BootstrapSyntaxError(f"bootstrap contains invalid numeric constant: {value}")


def _strict_json(data: bytes) -> dict[str, object]:
    if type(data) is not bytes:
        raise BootstrapSyntaxError("bootstrap input must be bytes")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise BootstrapSyntaxError("bootstrap is not UTF-8") from error
    if text.startswith("\ufeff"):
        raise BootstrapSyntaxError("bootstrap must not contain a UTF-8 BOM")
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except BootstrapSyntaxError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise BootstrapSyntaxError("bootstrap is not valid JSON") from error
    if type(parsed) is not dict:
        raise BootstrapSchemaError("bootstrap root must be an object")
    return parsed


def _text(value: object, field: str) -> str:
    if type(value) is not str or not value:
        raise BootstrapSchemaError(f"bootstrap field {field} must be non-empty text")
    return value


def _canonical_uuid(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError) as error:
        raise BootstrapSchemaError(f"bootstrap field {field} must be a UUID") from error
    if str(parsed) != text:
        raise BootstrapSchemaError(
            f"bootstrap field {field} must be lowercase UUID text"
        )
    return text


def _positive_int(value: object, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise BootstrapSchemaError(
            f"bootstrap field {field} must be a positive integer"
        )
    return value


@dataclass(frozen=True, slots=True)
class WindowsAuthorityBootstrap:
    """The exact signed authority facts accepted by this release."""

    bootstrap_schema: int
    bootstrap_generation: int
    machine_authority_id: str
    authority_epoch_id: str
    signing_key_id: str
    approved_account_sid: str
    database_path: str
    output_root: str
    provider_id: str
    permitted_provider_operation: str
    authority_policy_version: str
    claim_policy_version: str
    database_identity_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.bootstrap_schema) is not int
            or self.bootstrap_schema != SUPPORTED_BOOTSTRAP_SCHEMA
        ):
            raise UnsupportedBootstrapError("bootstrap schema is unsupported")
        if type(self.bootstrap_generation) is not int or self.bootstrap_generation <= 0:
            raise BootstrapSchemaError("bootstrap generation must be positive")
        _canonical_uuid(self.machine_authority_id, "machine_authority_id")
        _canonical_uuid(self.authority_epoch_id, "authority_epoch_id")
        if (
            type(self.signing_key_id) is not str
            or _KEY_ID.fullmatch(self.signing_key_id) is None
        ):
            raise BootstrapSchemaError("signing_key_id is not canonical")
        if (
            type(self.approved_account_sid) is not str
            or _SID.fullmatch(self.approved_account_sid) is None
        ):
            raise BootstrapSchemaError("approved_account_sid is not a SID")
        if type(self.database_path) is not str:
            raise BootstrapSchemaError("database_path must be text")
        if self.database_path != str(PRODUCTION_AUTHORITY_PATHS.database):
            raise BootstrapSchemaError("database_path is not the fixed database path")
        if type(self.output_root) is not str:
            raise BootstrapSchemaError("output_root must be text")
        if self.output_root != str(PRODUCTION_AUTHORITY_PATHS.capture_output):
            raise BootstrapSchemaError("output_root is not the fixed capture path")
        if type(self.provider_id) is not str:
            raise BootstrapSchemaError("provider_id must be text")
        if self.provider_id != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id:
            raise BootstrapSchemaError(
                "provider_id does not match the public descriptor"
            )
        if type(self.permitted_provider_operation) is not str:
            raise BootstrapSchemaError("permitted_provider_operation must be text")
        if (
            self.permitted_provider_operation
            != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
        ):
            raise BootstrapSchemaError(
                "permitted_provider_operation does not match the public descriptor"
            )
        if type(self.authority_policy_version) is not str:
            raise BootstrapSchemaError("authority_policy_version must be text")
        if self.authority_policy_version != SUPPORTED_AUTHORITY_POLICY_VERSION:
            raise UnsupportedBootstrapError("authority policy is unsupported")
        if type(self.claim_policy_version) is not str:
            raise BootstrapSchemaError("claim_policy_version must be text")
        if self.claim_policy_version != SUPPORTED_CLAIM_POLICY_VERSION:
            raise UnsupportedBootstrapError("claim policy is unsupported")
        if (
            type(self.database_identity_digest) is not str
            or _HEX_DIGEST.fullmatch(self.database_identity_digest) is None
        ):
            raise BootstrapSchemaError(
                "database_identity_digest is not lowercase SHA-256"
            )

    def to_dict(self) -> dict[str, object]:
        """Return the exact accepted JSON object."""

        return {
            "approved_account_sid": self.approved_account_sid,
            "authority_epoch_id": self.authority_epoch_id,
            "authority_policy_version": self.authority_policy_version,
            "bootstrap_generation": self.bootstrap_generation,
            "bootstrap_schema": self.bootstrap_schema,
            "claim_policy_version": self.claim_policy_version,
            "database_identity_digest": self.database_identity_digest,
            "database_path": self.database_path,
            "machine_authority_id": self.machine_authority_id,
            "output_root": self.output_root,
            "permitted_provider_operation": self.permitted_provider_operation,
            "provider_id": self.provider_id,
            "signing_key_id": self.signing_key_id,
        }

    def canonical_bytes(self) -> bytes:
        """Serialize the bootstrap using its one canonical byte representation."""

        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    canonical_json = canonical_bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> WindowsAuthorityBootstrap:
        """Parse one exact canonical bootstrap byte sequence."""

        return parse_bootstrap_bytes(data)

    @property
    def digest(self) -> str:
        """Return the SHA-256 digest of the exact canonical bootstrap bytes."""

        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def parse_bootstrap_bytes(data: bytes) -> WindowsAuthorityBootstrap:
    """Parse and require exact canonical bootstrap bytes."""

    values = _strict_json(data)
    if frozenset(values) != _BOOTSTRAP_FIELDS:
        raise BootstrapSchemaError("bootstrap field set is not exact")
    model = WindowsAuthorityBootstrap(
        bootstrap_schema=_positive_int(values["bootstrap_schema"], "bootstrap_schema"),
        bootstrap_generation=_positive_int(
            values["bootstrap_generation"], "bootstrap_generation"
        ),
        machine_authority_id=_canonical_uuid(
            values["machine_authority_id"], "machine_authority_id"
        ),
        authority_epoch_id=_canonical_uuid(
            values["authority_epoch_id"], "authority_epoch_id"
        ),
        signing_key_id=_text(values["signing_key_id"], "signing_key_id"),
        approved_account_sid=_text(
            values["approved_account_sid"], "approved_account_sid"
        ),
        database_path=_text(values["database_path"], "database_path"),
        output_root=_text(values["output_root"], "output_root"),
        provider_id=_text(values["provider_id"], "provider_id"),
        permitted_provider_operation=_text(
            values["permitted_provider_operation"], "permitted_provider_operation"
        ),
        authority_policy_version=_text(
            values["authority_policy_version"], "authority_policy_version"
        ),
        claim_policy_version=_text(
            values["claim_policy_version"], "claim_policy_version"
        ),
        database_identity_digest=_text(
            values["database_identity_digest"], "database_identity_digest"
        ),
    )
    if model.canonical_bytes() != data:
        raise BootstrapSyntaxError("bootstrap bytes are not canonical")
    return model


parse_bootstrap = parse_bootstrap_bytes


# ---------------------------------------------------------------------------
# Pinned P-256 trust-anchor registry and Windows CNG verifier


@dataclass(frozen=True, slots=True)
class PinnedBootstrapKey:
    """One approved P-256 public key in uncompressed SEC1 form."""

    key_id: str
    public_key: bytes

    def __post_init__(self) -> None:
        if type(self.key_id) is not str or _KEY_ID.fullmatch(self.key_id) is None:
            raise BootstrapTrustAnchorError("pinned key ID is not canonical")
        if type(self.public_key) is not bytes or len(self.public_key) != 65:
            raise BootstrapTrustAnchorError("pinned key is not a P-256 public key")
        if self.public_key[0] != 4:
            raise BootstrapTrustAnchorError("pinned key is not uncompressed SEC1 P-256")


@dataclass(frozen=True, slots=True)
class PinnedBootstrapKeyRegistry:
    """Immutable registry of approved bootstrap-signing public keys by exact ID."""

    keys: tuple[PinnedBootstrapKey, ...] = ()

    def __post_init__(self) -> None:
        if type(self.keys) is not tuple:
            raise BootstrapTrustAnchorError("pinned key registry must be immutable")
        ids = [item.key_id for item in self.keys]
        if len(ids) != len(set(ids)):
            raise BootstrapTrustAnchorError(
                "pinned key registry contains duplicate IDs"
            )

    def get(self, key_id: str) -> PinnedBootstrapKey:
        for key in self.keys:
            if key.key_id == key_id:
                return key
        raise BootstrapTrustAnchorError("bootstrap key ID is not pinned")


PRODUCTION_PINNED_BOOTSTRAP_KEYS = PinnedBootstrapKeyRegistry(
    (
        PinnedBootstrapKey(
            key_id="AITradingBot/Authority/Bootstrap/v1",
            public_key=bytes.fromhex(
                "04a73d90064e8b97e4a8373f48cac44718eb375ca52581233d614365294164efba"
                "40c6758f0f4cc455f6b2bf9b222696f9bc83c91ddf625fd01de46a6e7cd9c52e"
            ),
        ),
    )
)


def require_windows_platform() -> None:
    if os.name != "nt":
        raise UnsupportedWindowsPlatformError(
            "Windows authority operation requires Windows"
        )


_require_windows = require_windows_platform


def _ntstatus(operation: str, status: int) -> None:
    if status != 0:
        raise WindowsNativeError(operation, status & 0xFFFFFFFF)


def _cng_verify_p256_sha256(public_key: bytes, data: bytes, signature: bytes) -> None:
    """Verify one raw P1363 signature through BCrypt, releasing every handle."""

    _require_windows()
    if type(data) is not bytes or len(signature) != 64:
        raise BootstrapSignatureError("signature envelope is not SHA-256 P1363")
    bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)
    alg = ctypes.c_void_p()
    key = ctypes.c_void_p()
    hash_alg = ctypes.c_void_p()
    hash_handle = ctypes.c_void_p()
    hash_object: ctypes.Array[ctypes.c_char] | None = None
    key_blob: ctypes.Array[ctypes.c_ubyte] | None = None
    try:
        open_algorithm = bcrypt.BCryptOpenAlgorithmProvider
        open_algorithm.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
        ]
        open_algorithm.restype = ctypes.c_long
        _ntstatus(
            "BCryptOpenAlgorithmProvider(ECDSA)",
            open_algorithm(ctypes.byref(alg), "ECDSA_P256", None, 0),
        )

        class EccBlobHeader(ctypes.Structure):
            _fields_ = [("magic", ctypes.c_ulong), ("cb_key", ctypes.c_ulong)]

        header = EccBlobHeader(0x31534345, 32)
        key_blob = (ctypes.c_ubyte * 133)()
        ctypes.memmove(key_blob, ctypes.byref(header), ctypes.sizeof(header))
        ctypes.memmove(ctypes.addressof(key_blob) + 8, public_key[1:33], 32)
        ctypes.memmove(ctypes.addressof(key_blob) + 40, public_key[33:], 32)
        import_key = bcrypt.BCryptImportKeyPair
        import_key.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        import_key.restype = ctypes.c_long
        _ntstatus(
            "BCryptImportKeyPair",
            import_key(alg, None, "ECCPUBLICBLOB", ctypes.byref(key), key_blob, 72, 0),
        )

        _ntstatus(
            "BCryptOpenAlgorithmProvider(SHA256)",
            open_algorithm(ctypes.byref(hash_alg), "SHA256", None, 0),
        )
        get_property = bcrypt.BCryptGetProperty
        get_property.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_ulong,
        ]
        get_property.restype = ctypes.c_long
        object_length = ctypes.c_ulong()
        object_property = (ctypes.c_ubyte * 4)()
        _ntstatus(
            "BCryptGetProperty",
            get_property(
                hash_alg,
                "ObjectLength",
                object_property,
                4,
                ctypes.byref(ctypes.c_ulong()),
                0,
            ),
        )
        ctypes.memmove(ctypes.byref(object_length), object_property, 4)
        hash_object = ctypes.create_string_buffer(object_length.value)
        create_hash = bcrypt.BCryptCreateHash
        create_hash.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_char),
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        create_hash.restype = ctypes.c_long
        _ntstatus(
            "BCryptCreateHash",
            create_hash(
                hash_alg,
                ctypes.byref(hash_handle),
                hash_object,
                object_length.value,
                None,
                0,
                0,
            ),
        )
        hash_data = bcrypt.BCryptHashData
        hash_data.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        hash_data.restype = ctypes.c_long
        data_buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        _ntstatus(
            "BCryptHashData",
            hash_data(hash_handle, data_buffer, len(data), 0),
        )
        finish_hash = bcrypt.BCryptFinishHash
        finish_hash.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        finish_hash.restype = ctypes.c_long
        computed = (ctypes.c_ubyte * 32)()
        _ntstatus("BCryptFinishHash", finish_hash(hash_handle, computed, 32, 0))
        if bytes(computed) != hashlib.sha256(data).digest():
            raise BootstrapSignatureError("internal SHA-256 verification mismatch")
        verify = bcrypt.BCryptVerifySignature
        verify.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        verify.restype = ctypes.c_long
        signature_buffer = (ctypes.c_ubyte * 64).from_buffer_copy(signature)
        status = verify(key, None, computed, 32, signature_buffer, 64, 0)
        if status != 0:
            raise BootstrapSignatureError("bootstrap signature verification failed")
    finally:
        if hash_handle.value:
            destroy_hash = bcrypt.BCryptDestroyHash
            destroy_hash.argtypes = [ctypes.c_void_p]
            destroy_hash.restype = ctypes.c_long
            destroy_hash(hash_handle)
        if hash_alg.value:
            close_algorithm = bcrypt.BCryptCloseAlgorithmProvider
            close_algorithm.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            close_algorithm.restype = ctypes.c_long
            close_algorithm(hash_alg, 0)
        if key.value:
            destroy_key = bcrypt.BCryptDestroyKey
            destroy_key.argtypes = [ctypes.c_void_p]
            destroy_key.restype = ctypes.c_long
            destroy_key(key)
        if alg.value:
            close_algorithm = bcrypt.BCryptCloseAlgorithmProvider
            close_algorithm.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            close_algorithm.restype = ctypes.c_long
            close_algorithm(alg, 0)


@dataclass(frozen=True, slots=True)
class BootstrapVerification:
    """Sanitized successful verification evidence."""

    bootstrap: WindowsAuthorityBootstrap
    bootstrap_digest: str
    signing_key_id: str
    signature_length: int


def verify_bootstrap_signature(
    bootstrap_bytes: bytes,
    signature: bytes,
    *,
    key_registry: PinnedBootstrapKeyRegistry = PRODUCTION_PINNED_BOOTSTRAP_KEYS,
) -> BootstrapVerification:
    """Parse, pin, and verify detached P-256/P1363 bootstrap trust material."""

    _require_windows()
    bootstrap = parse_bootstrap_bytes(bootstrap_bytes)
    if type(signature) is not bytes or len(signature) != 64:
        raise BootstrapSignatureError("bootstrap signature must be exactly 64 bytes")
    key = key_registry.get(bootstrap.signing_key_id)
    _cng_verify_p256_sha256(
        key.public_key,
        bootstrap_bytes,
        signature,
    )
    return BootstrapVerification(
        bootstrap=bootstrap,
        bootstrap_digest=hashlib.sha256(bootstrap_bytes).hexdigest(),
        signing_key_id=key.key_id,
        signature_length=len(signature),
    )


verify_detached_bootstrap_signature = verify_bootstrap_signature
