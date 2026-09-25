"""Fixed Windows CNG bootstrap and external signer for D10 key v3.

Importing this module is inert. The protected key-creation function is a
zero-argument operator boundary reserved for separately authorized P125-1.
Portable tests exercise policy through a private CNG seam.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from ctypes import wintypes
from dataclasses import dataclass
from typing import Protocol

from scripts import d10_protected_deployment as deployment

PROVIDER_NAME = "Microsoft Software Key Storage Provider"
KEY_NAME = "AITradingBot-D10-DeploymentAttestation-v3"
SIGNING_KEY_ID = "AITradingBot/D10/DeploymentAttestation/v3"
ALGORITHM_ID = "ECDSA_P256"
ALGORITHM_GROUP = "ECDSA"
CURVE_NAME = "P-256"
KEY_SIZE_BITS = 256
SIGNING_ALGORITHM = "ECDSA-P256"
SIGNING_DIGEST = "SHA-256"
SIGNATURE_ENCODING = "IEEE-P1363"

NCRYPT_MACHINE_KEY_FLAG = 0x00000020
NCRYPT_ALLOW_SIGNING_FLAG = 0x00000002
NCRYPT_EXPORT_POLICY_NONE = 0
NCRYPT_PERSIST_FLAG = 0x80000000
NCRYPT_SILENT_FLAG = 0x00000040
OWNER_SECURITY_INFORMATION = 0x00000001
GROUP_SECURITY_INFORMATION = 0x00000002
DACL_SECURITY_INFORMATION = 0x00000004
PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
SACL_SECURITY_INFORMATION = 0x00000008
SECURITY_DESCRIPTOR_INFORMATION = (
    OWNER_SECURITY_INFORMATION | GROUP_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION
)

PROPERTY_NAME = "Name"
PROPERTY_PROVIDER_HANDLE = "Provider Handle"
PROPERTY_ALGORITHM = "Algorithm Name"
PROPERTY_ALGORITHM_GROUP = "Algorithm Group"
PROPERTY_LENGTH = "Length"
PROPERTY_KEY_TYPE = "Key Type"
PROPERTY_KEY_USAGE = "Key Usage"
PROPERTY_EXPORT_POLICY = "Export Policy"
PROPERTY_SECURITY_DESCRIPTOR = "Security Descr"
PROPERTY_SECURITY_DESCRIPTOR_SUPPORT = "Security Descr Support"
PUBLIC_KEY_BLOB_TYPE = "ECCPUBLICBLOB"
PUBLIC_KEY_BLOB_MAGIC = 0x31534345
PUBLIC_KEY_BLOB_LENGTH = 72
PUBLIC_KEY_POINT_LENGTH = 65
MAX_NATIVE_PROPERTY_BYTES = 64 * 1024
MAX_ENROLLMENT_TRANSCRIPT_BYTES = 8192
SYSTEM32 = r"C:\Windows\System32"

# Owner BUILTIN\Administrators, group SYSTEM, protected DACL, and only SYSTEM
# and BUILTIN\Administrators full-control ACEs. Trading is deliberately absent.
KEY_SECURITY_DESCRIPTOR_SDDL = "O:BAG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)"
OWNER_SID = "S-1-5-32-544"
PERSISTED_GROUP_SID = "S-1-5-21-1397534616-3988210162-180023805-1005"
SYSTEM_SID = "S-1-5-18"
REQUESTED_FULL_ACCESS_MASK = 0x001F01FF
PERSISTED_ACCESS_MASK = 0xD01F01FF
PERSISTED_SECURITY_CONTROL = 0x9004
SE_DACL_PRESENT = 0x0004
SE_DACL_PROTECTED = 0x1000
SE_SELF_RELATIVE = 0x8000
ACL_REVISION = 2
ACCESS_ALLOWED_ACE_TYPE = 0

_P256_FIELD = int(
    "FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF", 16
)
_P256_B = int("5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B", 16)
_STATUS_NOT_FOUND = 0x80090011
_STATUS_BAD_KEYSET = 0x80090016
_STATUS_EXISTS = 0x8009000F


class _Blocked(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class _KeyNotFound(Exception):
    """The fixed provider positively reported that the requested key is absent."""


class _KeyAlreadyExists(Exception):
    """Create-only key creation lost a race to an existing name."""


@dataclass(frozen=True, slots=True)
class SecurityAce:
    ace_type: int
    ace_flags: int
    access_mask: int
    trustee_sid: str


@dataclass(frozen=True, slots=True)
class SecurityFacts:
    descriptor_revision: int
    owner_sid: str
    owner_defaulted: bool
    group_sid: str
    group_defaulted: bool
    control: int
    dacl_present: bool
    dacl_defaulted: bool
    acl_revision: int
    ace_count: int
    aces: tuple[SecurityAce, ...]


class _AclSizeInformation(ctypes.Structure):
    _fields_ = [
        ("ace_count", wintypes.DWORD),
        ("acl_bytes_in_use", wintypes.DWORD),
        ("acl_bytes_free", wintypes.DWORD),
    ]


class _AclHeader(ctypes.Structure):
    _fields_ = [
        ("revision", ctypes.c_ubyte),
        ("sbz1", ctypes.c_ubyte),
        ("acl_size", wintypes.WORD),
        ("ace_count", wintypes.WORD),
        ("sbz2", wintypes.WORD),
    ]


class _AceHeader(ctypes.Structure):
    _fields_ = [
        ("ace_type", ctypes.c_ubyte),
        ("ace_flags", ctypes.c_ubyte),
        ("ace_size", wintypes.WORD),
    ]


def _verify_security_facts(facts: SecurityFacts) -> None:
    expected = (
        SecurityAce(ACCESS_ALLOWED_ACE_TYPE, 0, PERSISTED_ACCESS_MASK, SYSTEM_SID),
        SecurityAce(ACCESS_ALLOWED_ACE_TYPE, 0, PERSISTED_ACCESS_MASK, OWNER_SID),
    )
    if (
        type(facts) is not SecurityFacts
        or type(facts.descriptor_revision) is not int
        or facts.descriptor_revision != 1
        or facts.owner_sid != OWNER_SID
        or facts.owner_defaulted is not False
        or facts.group_sid != PERSISTED_GROUP_SID
        or facts.group_defaulted is not False
        or type(facts.control) is not int
        or facts.control != PERSISTED_SECURITY_CONTROL
        or facts.dacl_present is not True
        or facts.dacl_defaulted is not False
        or facts.acl_revision != ACL_REVISION
        or facts.ace_count != 2
        or type(facts.aces) is not tuple
        or facts.aces != expected
    ):
        raise _Blocked("cng_security_descriptor_mismatch")


class _CngApi(Protocol):
    """Private seam: names, flags and property values come from this module."""

    def require_administrator(self) -> None: ...
    def open_provider(self, provider_name: str) -> object: ...
    def open_key(self, provider: object, key_name: str, flags: int) -> object: ...
    def create_key(
        self, provider: object, key_name: str, algorithm: str, flags: int
    ) -> object: ...
    def set_property(
        self, key: object, name: str, value: bytes, flags: int
    ) -> None: ...
    def set_security_descriptor(self, key: object, sddl: str) -> None: ...
    def get_property(self, handle: object, name: str, flags: int = 0) -> bytes: ...
    def get_provider_name(self, key: object) -> str: ...
    def get_security_facts(self, key: object) -> SecurityFacts: ...
    def finalize_key(self, key: object, flags: int) -> None: ...
    def export_public_key(self, key: object, blob_type: str) -> bytes: ...
    def sign_hash(self, key: object, digest: bytes) -> bytes: ...
    def close(self, handle: object) -> None: ...


@dataclass(frozen=True, slots=True)
class EnrollmentResult:
    """Sanitized P125-1 evidence; the only key bytes carried are public."""

    status: str
    public_key: bytes | None
    public_key_sha256: str | None
    transcript: bytes
    reason_code: str | None


class _HandleSet:
    def __init__(self, api: _CngApi) -> None:
        self.api = api
        self.providers: list[object] = []
        self.keys: list[object] = []

    def open_provider(self) -> object:
        try:
            handle = self.api.open_provider(PROVIDER_NAME)
        except Exception:
            raise _Blocked("fixed_provider_open_failed") from None
        if handle is None or handle == 0:
            raise _Blocked("fixed_provider_handle_invalid")
        self.providers.append(handle)
        return handle

    def open_key(self, provider: object, flags: int) -> object:
        try:
            handle = self.api.open_key(provider, KEY_NAME, flags)
        except _KeyNotFound:
            raise
        except Exception:
            raise _Blocked("fixed_key_open_failed") from None
        if handle is None or handle == 0:
            raise _Blocked("fixed_key_handle_invalid")
        self.keys.append(handle)
        return handle

    def create_key(self, provider: object) -> object:
        try:
            handle = self.api.create_key(
                provider, KEY_NAME, ALGORITHM_ID, NCRYPT_MACHINE_KEY_FLAG
            )
        except _KeyAlreadyExists:
            raise _Blocked("fixed_key_already_exists") from None
        except Exception:
            raise _Blocked("fixed_key_create_failed") from None
        if handle is None or handle == 0:
            raise _Blocked("fixed_key_handle_invalid")
        self.keys.append(handle)
        return handle

    def close_key(self, handle: object) -> None:
        self._close_tracked(self.keys, handle)

    def close_all(self) -> bool:
        failed = False
        for collection in (self.keys, self.providers):
            while collection:
                handle = collection.pop()
                try:
                    self.api.close(handle)
                except Exception:
                    failed = True
        return failed

    def _close_tracked(self, collection: list[object], handle: object) -> None:
        for index, tracked in enumerate(collection):
            if tracked is handle or tracked == handle:
                del collection[index]
                break
        else:
            raise _Blocked("cng_handle_lifecycle_invalid")
        try:
            self.api.close(handle)
        except Exception:
            raise _Blocked("cng_cleanup_failed") from None


def _uint32(value: int) -> bytes:
    return value.to_bytes(4, "little", signed=False)


def _read_uint32(value: bytes, code: str = "cng_key_property_mismatch") -> int:
    if type(value) is not bytes or len(value) != 4:
        raise _Blocked(code)
    return int.from_bytes(value, "little", signed=False)


def _read_wide_string(value: bytes, code: str = "cng_key_property_mismatch") -> str:
    if type(value) is not bytes or not value or len(value) % 2:
        raise _Blocked(code)
    try:
        decoded = value.decode("utf-16-le", errors="strict")
    except UnicodeError:
        raise _Blocked(code) from None
    if not decoded.endswith("\0") or "\0" in decoded[:-1]:
        raise _Blocked(code)
    return decoded[:-1]


def _get_property(api: _CngApi, handle: object, name: str) -> bytes:
    try:
        value = api.get_property(handle, name, NCRYPT_SILENT_FLAG)
    except Exception:
        raise _Blocked("cng_key_property_unavailable") from None
    if type(value) is not bytes or not value or len(value) > MAX_NATIVE_PROPERTY_BYTES:
        raise _Blocked("cng_key_property_unavailable")
    return value


def _verify_provider(api: _CngApi, provider: object) -> None:
    if _read_wide_string(_get_property(api, provider, PROPERTY_NAME)) != PROVIDER_NAME:
        raise _Blocked("cng_provider_identity_mismatch")
    if (
        _read_uint32(_get_property(api, provider, PROPERTY_SECURITY_DESCRIPTOR_SUPPORT))
        != 1
    ):
        raise _Blocked("cng_security_descriptor_unsupported")


def _verify_key(api: _CngApi, key: object) -> SecurityFacts:
    try:
        provider_name = api.get_provider_name(key)
    except Exception:
        raise _Blocked("cng_provider_identity_unavailable") from None
    if type(provider_name) is not str or provider_name != PROVIDER_NAME:
        raise _Blocked("cng_provider_identity_mismatch")

    properties = (
        (_read_wide_string(_get_property(api, key, PROPERTY_NAME)), KEY_NAME),
        (_read_wide_string(_get_property(api, key, PROPERTY_ALGORITHM)), ALGORITHM_ID),
        (
            _read_wide_string(_get_property(api, key, PROPERTY_ALGORITHM_GROUP)),
            ALGORITHM_GROUP,
        ),
        (_read_uint32(_get_property(api, key, PROPERTY_LENGTH)), KEY_SIZE_BITS),
        (
            _read_uint32(_get_property(api, key, PROPERTY_KEY_TYPE)),
            NCRYPT_MACHINE_KEY_FLAG,
        ),
        (
            _read_uint32(_get_property(api, key, PROPERTY_KEY_USAGE)),
            NCRYPT_ALLOW_SIGNING_FLAG,
        ),
        (
            _read_uint32(_get_property(api, key, PROPERTY_EXPORT_POLICY)),
            NCRYPT_EXPORT_POLICY_NONE,
        ),
    )
    if any(actual != expected for actual, expected in properties):
        raise _Blocked("cng_key_property_mismatch")
    try:
        facts = api.get_security_facts(key)
    except Exception:
        raise _Blocked("cng_security_descriptor_unavailable") from None
    _verify_security_facts(facts)
    return facts


def normalize_public_key_blob(blob: bytes) -> bytes:
    """Convert exactly one valid P-256 ECCPUBLICBLOB to uncompressed SEC1."""
    if type(blob) is not bytes or len(blob) != PUBLIC_KEY_BLOB_LENGTH:
        raise _Blocked("public_key_blob_malformed")
    magic = int.from_bytes(blob[:4], "little", signed=False)
    coordinate_bytes = int.from_bytes(blob[4:8], "little", signed=False)
    if magic != PUBLIC_KEY_BLOB_MAGIC or coordinate_bytes != 32:
        raise _Blocked("public_key_blob_malformed")
    x = int.from_bytes(blob[8:40], "big", signed=False)
    y = int.from_bytes(blob[40:72], "big", signed=False)
    if x >= _P256_FIELD or y >= _P256_FIELD:
        raise _Blocked("public_key_point_noncanonical")
    if (y * y - (pow(x, 3, _P256_FIELD) - 3 * x + _P256_B)) % _P256_FIELD:
        raise _Blocked("public_key_point_invalid")
    point = b"\x04" + blob[8:]
    if len(point) != PUBLIC_KEY_POINT_LENGTH:
        raise _Blocked("public_key_blob_malformed")
    return point


def _transcript(
    status: str,
    public_key: bytes | None,
    reason_code: str | None,
    *,
    recovery: bool = False,
    security: SecurityFacts | None = None,
) -> bytes:
    facts: dict[str, object] = {
        "algorithm": ALGORITHM_ID,
        "curve": CURVE_NAME,
        "export_policy": 0,
        "key_name": KEY_NAME,
        "key_size_bits": KEY_SIZE_BITS,
        "key_type": NCRYPT_MACHINE_KEY_FLAG,
        "key_usage": NCRYPT_ALLOW_SIGNING_FLAG,
        "provider": PROVIDER_NAME,
        "schema": (
            "personal-desktop-d10-signing-key-attempt2-read-only-qualification/v1"
            if recovery
            else "personal-desktop-d10-signing-key-enrollment/v2"
        ),
        "requested_sddl": KEY_SECURITY_DESCRIPTOR_SDDL,
        "requested_full_access_mask": REQUESTED_FULL_ACCESS_MASK,
        "signing_key_id": SIGNING_KEY_ID,
        "status": status,
        "public_key_sec1_hex": public_key.hex() if public_key is not None else None,
        "public_key_sha256": (
            hashlib.sha256(public_key).hexdigest() if public_key is not None else None
        ),
    }
    if security is not None and status == "PASS":
        facts["persisted_security"] = {
            "descriptor_revision": security.descriptor_revision,
            "owner_sid": security.owner_sid,
            "owner_defaulted": security.owner_defaulted,
            "group_sid": security.group_sid,
            "group_defaulted": security.group_defaulted,
            "control": security.control,
            "dacl_present": security.dacl_present,
            "dacl_defaulted": security.dacl_defaulted,
            "acl_revision": security.acl_revision,
            "ace_count": security.ace_count,
            "aces": [
                {
                    "type": ace.ace_type,
                    "flags": ace.ace_flags,
                    "mask": ace.access_mask,
                    "sid": ace.trustee_sid,
                }
                for ace in security.aces
            ],
        }
    if reason_code is not None:
        facts["reason_code"] = reason_code
    encoded = json.dumps(
        facts, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    if len(encoded) > MAX_ENROLLMENT_TRANSCRIPT_BYTES:
        raise _Blocked("enrollment_transcript_bound")
    return encoded


def _enrollment_result(
    status: str,
    public_key: bytes | None = None,
    reason_code: str | None = None,
    *,
    recovery: bool = False,
    security: SecurityFacts | None = None,
) -> EnrollmentResult:
    public_hash = hashlib.sha256(public_key).hexdigest() if public_key else None
    return EnrollmentResult(
        status,
        public_key,
        public_hash,
        _transcript(
            status, public_key, reason_code, recovery=recovery, security=security
        ),
        reason_code,
    )


def _prepare_with_api(api: _CngApi) -> EnrollmentResult:
    resources = _HandleSet(api)
    public_key: bytes | None = None
    security: SecurityFacts | None = None
    reason: str | None = None
    try:
        try:
            api.require_administrator()
        except Exception:
            raise _Blocked("administrator_required") from None
        provider = resources.open_provider()
        _verify_provider(api, provider)

        # Probe both the invoking operator's user namespace and fixed machine
        # namespace. Either existing name is a no-overwrite stop.
        for scope_flags in (0, NCRYPT_MACHINE_KEY_FLAG):
            try:
                existing = resources.open_key(provider, scope_flags)
            except _KeyNotFound:
                continue
            resources.close_key(existing)
            raise _Blocked("fixed_key_already_exists")

        created = resources.create_key(provider)
        # Restrict access immediately, before setting properties or finalizing.
        try:
            api.set_security_descriptor(created, KEY_SECURITY_DESCRIPTOR_SDDL)
        except Exception:
            raise _Blocked("cng_security_descriptor_set_failed") from None

        for name, value in (
            (PROPERTY_KEY_USAGE, _uint32(NCRYPT_ALLOW_SIGNING_FLAG)),
            (PROPERTY_EXPORT_POLICY, _uint32(NCRYPT_EXPORT_POLICY_NONE)),
        ):
            try:
                api.set_property(
                    created,
                    name,
                    value,
                    NCRYPT_PERSIST_FLAG | NCRYPT_SILENT_FLAG,
                )
            except Exception:
                raise _Blocked("cng_key_property_set_failed") from None
        try:
            api.finalize_key(created, NCRYPT_SILENT_FLAG)
        except Exception:
            raise _Blocked("cng_key_finalize_failed") from None
        resources.close_key(created)

        reopened = resources.open_key(provider, NCRYPT_MACHINE_KEY_FLAG)
        security = _verify_key(api, reopened)
        try:
            blob = api.export_public_key(reopened, PUBLIC_KEY_BLOB_TYPE)
        except Exception:
            raise _Blocked("public_key_export_failed") from None
        public_key = normalize_public_key_blob(blob)
    except _Blocked as error:
        reason = error.code
    except _KeyNotFound:
        reason = "fixed_key_absence_unverifiable"
    except Exception:
        reason = "native_operation_failed"
    finally:
        if resources.close_all():
            reason = "cng_cleanup_failed"

    if reason is not None:
        return _enrollment_result("BLOCKED", reason_code=reason)
    return _enrollment_result("PASS", public_key=public_key, security=security)


def prepare_d10_signing_key() -> EnrollmentResult:
    """P125-1 operator entry point; inert until explicitly called on Windows."""
    if os.name != "nt":
        return _enrollment_result("BLOCKED", reason_code="windows_cng_required")
    try:
        api = _WindowsCngApi()
    except Exception:
        return _enrollment_result("BLOCKED", reason_code="native_cng_unavailable")
    return _prepare_with_api(api)


def _qualify_existing_with_api(api: _CngApi) -> EnrollmentResult:
    """Read-only recovery for the frozen attempt-#2 persisted object."""
    resources = _HandleSet(api)
    public_key: bytes | None = None
    security: SecurityFacts | None = None
    reason: str | None = None
    try:
        try:
            api.require_administrator()
        except Exception:
            raise _Blocked("administrator_required") from None
        provider = resources.open_provider()
        _verify_provider(api, provider)
        try:
            user_key = resources.open_key(provider, 0)
        except _KeyNotFound:
            pass
        else:
            resources.close_key(user_key)
            raise _Blocked("fixed_user_key_already_exists")
        try:
            machine_key = resources.open_key(provider, NCRYPT_MACHINE_KEY_FLAG)
        except _KeyNotFound:
            raise _Blocked("fixed_machine_key_absent") from None
        security = _verify_key(api, machine_key)
        try:
            blob = api.export_public_key(machine_key, PUBLIC_KEY_BLOB_TYPE)
        except Exception:
            raise _Blocked("public_key_export_failed") from None
        public_key = normalize_public_key_blob(blob)
    except _Blocked as error:
        reason = error.code
    except Exception:
        reason = "native_operation_failed"
    finally:
        if resources.close_all():
            reason = "cng_cleanup_failed"
    if reason is not None:
        return _enrollment_result("BLOCKED", reason_code=reason, recovery=True)
    return _enrollment_result(
        "PASS", public_key=public_key, recovery=True, security=security
    )


def qualify_existing_d10_signing_key_after_attempt2() -> EnrollmentResult:
    """Explicit zero-argument read-only recovery boundary; never enrolls or signs."""
    if os.name != "nt":
        return _enrollment_result(
            "BLOCKED", reason_code="windows_cng_required", recovery=True
        )
    try:
        api = _WindowsCngApi()
    except Exception:
        return _enrollment_result(
            "BLOCKED", reason_code="native_cng_unavailable", recovery=True
        )
    return _qualify_existing_with_api(api)


def _validate_signing_request(request: object) -> deployment.SigningRequest:
    if type(request) is not deployment.SigningRequest:
        raise _Blocked("signing_request_invalid")
    if (
        request.key_id != SIGNING_KEY_ID
        or request.algorithm != SIGNING_ALGORITHM
        or request.digest_algorithm != SIGNING_DIGEST
        or request.signature_encoding != SIGNATURE_ENCODING
        or type(request.message_sha256) is not bytes
        or len(request.message_sha256) != 32
    ):
        raise _Blocked("signing_request_invalid")
    return request


def _sign_with_api(api: _CngApi, request: object) -> deployment.DetachedSignature:
    try:
        validated = _validate_signing_request(request)
    except _Blocked as error:
        raise deployment.DeploymentBlocked(error.code) from None

    resources = _HandleSet(api)
    signature: bytes | None = None
    reason: str | None = None
    try:
        try:
            api.require_administrator()
        except Exception:
            raise _Blocked("administrator_required") from None
        provider = resources.open_provider()
        key = resources.open_key(provider, NCRYPT_MACHINE_KEY_FLAG)
        _verify_provider(api, provider)
        _verify_key(api, key)
        try:
            signature = api.sign_hash(key, validated.message_sha256)
        except Exception:
            raise _Blocked("ncrypt_sign_hash_failed") from None
        try:
            deployment.require_signature(signature)
        except Exception:
            raise _Blocked("signature_scalar_noncanonical") from None
    except _Blocked as error:
        reason = error.code
    except _KeyNotFound:
        reason = "fixed_key_unavailable"
    except Exception:
        reason = "native_signing_operation_failed"
    finally:
        if resources.close_all():
            reason = "cng_cleanup_failed"

    if reason is not None or signature is None:
        raise deployment.DeploymentBlocked(reason or "ncrypt_sign_hash_failed")
    return deployment.DetachedSignature(
        SIGNING_KEY_ID,
        SIGNING_ALGORITHM,
        SIGNING_DIGEST,
        SIGNATURE_ENCODING,
        signature,
    )


class WindowsCngExternalSigner:
    """ExternalSigner backed only by the fixed persisted D10 v3 CNG key."""

    @property
    def identity(self) -> deployment.SigningIdentity:
        return deployment.SigningIdentity(
            SIGNING_KEY_ID,
            SIGNING_ALGORITHM,
            SIGNING_DIGEST,
            SIGNATURE_ENCODING,
            False,
        )

    def sign_digest(
        self, request: deployment.SigningRequest
    ) -> deployment.DetachedSignature:
        if os.name != "nt":
            raise deployment.DeploymentBlocked("windows_cng_required")
        try:
            api = _WindowsCngApi()
        except Exception:
            raise deployment.DeploymentBlocked("native_cng_unavailable") from None
        return _sign_with_api(api, request)


class _WindowsCngApi:
    """Fixed-name NCrypt adapter with no key import/delete/private-export path."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise _Blocked("windows_cng_required")
        try:
            self._ncrypt = ctypes.WinDLL(SYSTEM32 + r"\ncrypt.dll", use_last_error=True)
            self._advapi = ctypes.WinDLL(
                SYSTEM32 + r"\advapi32.dll", use_last_error=True
            )
            self._kernel = ctypes.WinDLL(
                SYSTEM32 + r"\kernel32.dll", use_last_error=True
            )
        except Exception:
            raise _Blocked("native_cng_libraries_unavailable") from None

    @staticmethod
    def _bind(library: object, name: str, args: list[object], result: object):
        function = getattr(library, name)
        function.argtypes = args
        function.restype = result
        return function

    @staticmethod
    def _status_code(status: int) -> int:
        return int(status) & 0xFFFFFFFF

    def _check_status(self, status: int, reason: str) -> None:
        if self._status_code(status) != 0:
            raise _Blocked(reason)

    def require_administrator(self) -> None:
        try:
            from scripts.d10_protected_deployment_windows import (
                WindowsDeploymentBackend,
            )

            WindowsDeploymentBackend().require_administrator()
        except Exception:
            raise _Blocked("administrator_required") from None

    def open_provider(self, provider_name: str) -> object:
        if provider_name != PROVIDER_NAME:
            raise _Blocked("fixed_provider_only")
        handle = ctypes.c_void_p()
        open_provider = self._bind(
            self._ncrypt,
            "NCryptOpenStorageProvider",
            [ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, wintypes.DWORD],
            ctypes.c_long,
        )
        status = open_provider(ctypes.byref(handle), PROVIDER_NAME, 0)
        if self._status_code(status) != 0:
            if handle.value:
                self.close(int(handle.value))
            raise _Blocked("fixed_provider_open_failed")
        if not handle.value:
            raise _Blocked("fixed_provider_handle_invalid")
        return int(handle.value)

    def open_key(self, provider: object, key_name: str, flags: int) -> object:
        if key_name != KEY_NAME or flags not in (0, NCRYPT_MACHINE_KEY_FLAG):
            raise _Blocked("fixed_key_identity_only")
        handle = ctypes.c_void_p()
        open_key = self._bind(
            self._ncrypt,
            "NCryptOpenKey",
            [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
            ],
            ctypes.c_long,
        )
        status = open_key(
            ctypes.c_void_p(int(provider)),
            ctypes.byref(handle),
            KEY_NAME,
            0,
            flags,
        )
        code = self._status_code(status)
        if code != 0:
            if handle.value:
                self.close(int(handle.value))
            if code in (_STATUS_NOT_FOUND, _STATUS_BAD_KEYSET):
                raise _KeyNotFound
            raise _Blocked("fixed_key_open_failed")
        if not handle.value:
            raise _Blocked("fixed_key_handle_invalid")
        return int(handle.value)

    def create_key(
        self, provider: object, key_name: str, algorithm: str, flags: int
    ) -> object:
        if (
            key_name != KEY_NAME
            or algorithm != ALGORITHM_ID
            or flags != NCRYPT_MACHINE_KEY_FLAG
        ):
            raise _Blocked("fixed_key_creation_contract_only")
        handle = ctypes.c_void_p()
        create_key = self._bind(
            self._ncrypt,
            "NCryptCreatePersistedKey",
            [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
            ],
            ctypes.c_long,
        )
        status = create_key(
            ctypes.c_void_p(int(provider)),
            ctypes.byref(handle),
            ALGORITHM_ID,
            KEY_NAME,
            0,
            NCRYPT_MACHINE_KEY_FLAG,
        )
        code = self._status_code(status)
        if code != 0:
            if handle.value:
                self.close(int(handle.value))
            if code == _STATUS_EXISTS:
                raise _KeyAlreadyExists
            raise _Blocked("fixed_key_create_failed")
        if not handle.value:
            raise _Blocked("fixed_key_handle_invalid")
        return int(handle.value)

    def set_property(self, key: object, name: str, value: bytes, flags: int) -> None:
        allowed = {
            (PROPERTY_KEY_USAGE, _uint32(NCRYPT_ALLOW_SIGNING_FLAG)),
            (PROPERTY_EXPORT_POLICY, _uint32(NCRYPT_EXPORT_POLICY_NONE)),
        }
        if (
            name,
            value,
        ) not in allowed or flags != NCRYPT_PERSIST_FLAG | NCRYPT_SILENT_FLAG:
            raise _Blocked("fixed_key_property_contract_only")
        buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
        set_property = self._bind(
            self._ncrypt,
            "NCryptSetProperty",
            [
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
            ],
            ctypes.c_long,
        )
        self._check_status(
            set_property(
                ctypes.c_void_p(int(key)),
                name,
                buffer,
                len(value),
                flags,
            ),
            "cng_key_property_set_failed",
        )

    def set_security_descriptor(self, key: object, sddl: str) -> None:
        if sddl != KEY_SECURITY_DESCRIPTOR_SDDL:
            raise _Blocked("fixed_security_descriptor_only")
        convert = self._bind(
            self._advapi,
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(wintypes.DWORD),
            ],
            wintypes.BOOL,
        )
        descriptor, descriptor_length = ctypes.c_void_p(), wintypes.DWORD()
        if (
            not convert(
                KEY_SECURITY_DESCRIPTOR_SDDL,
                1,
                ctypes.byref(descriptor),
                ctypes.byref(descriptor_length),
            )
            or not descriptor.value
            or not descriptor_length.value
        ):
            if descriptor.value:
                self._free_local(descriptor)
            raise _Blocked("cng_security_descriptor_build_failed")
        set_property = self._bind(
            self._ncrypt,
            "NCryptSetProperty",
            [
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
            ],
            ctypes.c_long,
        )
        try:
            for security_info in (
                OWNER_SECURITY_INFORMATION,
                GROUP_SECURITY_INFORMATION,
                DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION,
            ):
                self._check_status(
                    set_property(
                        ctypes.c_void_p(int(key)),
                        PROPERTY_SECURITY_DESCRIPTOR,
                        descriptor,
                        descriptor_length.value,
                        security_info | NCRYPT_SILENT_FLAG,
                    ),
                    "cng_security_descriptor_set_failed",
                )
        finally:
            self._free_local(descriptor)

    def _free_local(self, pointer: object) -> None:
        local_free = self._bind(
            self._kernel,
            "LocalFree",
            [ctypes.c_void_p],
            ctypes.c_void_p,
        )
        if local_free(pointer):
            raise _Blocked("cng_cleanup_failed")

    def get_property(self, handle: object, name: str, flags: int = 0) -> bytes:
        if flags != NCRYPT_SILENT_FLAG:
            raise _Blocked("fixed_property_read_flags_only")
        return self._read_property(handle, name, flags)

    def _read_property(self, handle: object, name: str, flags: int) -> bytes:
        get_property = self._bind(
            self._ncrypt,
            "NCryptGetProperty",
            [
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.DWORD,
            ],
            ctypes.c_long,
        )
        required = wintypes.DWORD()
        self._check_status(
            get_property(
                ctypes.c_void_p(int(handle)),
                name,
                None,
                0,
                ctypes.byref(required),
                flags,
            ),
            "cng_key_property_unavailable",
        )
        if not 0 < required.value <= MAX_NATIVE_PROPERTY_BYTES:
            raise _Blocked("cng_key_property_size_invalid")
        buffer = (ctypes.c_ubyte * required.value)()
        received = wintypes.DWORD()
        self._check_status(
            get_property(
                ctypes.c_void_p(int(handle)),
                name,
                buffer,
                required.value,
                ctypes.byref(received),
                flags,
            ),
            "cng_key_property_unavailable",
        )
        if received.value != required.value:
            raise _Blocked("cng_key_property_size_drift")
        return bytes(buffer)

    def get_provider_name(self, key: object) -> str:
        raw = self._read_property(key, PROPERTY_PROVIDER_HANDLE, NCRYPT_SILENT_FLAG)
        if len(raw) != ctypes.sizeof(ctypes.c_void_p):
            raise _Blocked("cng_provider_handle_invalid")
        provider_handle = ctypes.c_void_p.from_buffer_copy(raw)
        if not provider_handle.value:
            raise _Blocked("cng_provider_handle_invalid")
        try:
            provider_name = _read_wide_string(
                self._read_property(
                    int(provider_handle.value), PROPERTY_NAME, NCRYPT_SILENT_FLAG
                ),
                "cng_provider_identity_unavailable",
            )
        finally:
            self.close(int(provider_handle.value))
        return provider_name

    def _sid_string(self, pointer: ctypes.c_void_p, start: int, end: int) -> str:
        address = pointer.value
        if not address or address < start or address + 8 > end:
            raise _Blocked("cng_security_descriptor_malformed")
        prefix = ctypes.string_at(address, 8)
        sid_length = 8 + 4 * prefix[1]
        if prefix[0] != 1 or sid_length > 68 or address + sid_length > end:
            raise _Blocked("cng_security_descriptor_malformed")
        is_valid = self._bind(
            self._advapi, "IsValidSid", [ctypes.c_void_p], wintypes.BOOL
        )
        if not is_valid(pointer):
            raise _Blocked("cng_security_descriptor_malformed")
        output = ctypes.c_wchar_p()
        convert = self._bind(
            self._advapi,
            "ConvertSidToStringSidW",
            [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)],
            wintypes.BOOL,
        )
        if not convert(pointer, ctypes.byref(output)) or not output.value:
            if output.value:
                self._free_local(ctypes.cast(output, ctypes.c_void_p))
            raise _Blocked("cng_security_descriptor_malformed")
        try:
            return output.value
        finally:
            self._free_local(ctypes.cast(output, ctypes.c_void_p))

    def get_security_facts(self, key: object) -> SecurityFacts:
        raw = self._read_property(
            key,
            PROPERTY_SECURITY_DESCRIPTOR,
            NCRYPT_SILENT_FLAG | SECURITY_DESCRIPTOR_INFORMATION,
        )
        if not 20 <= len(raw) <= MAX_NATIVE_PROPERTY_BYTES:
            raise _Blocked("cng_security_descriptor_size_invalid")
        if raw[0] != 1 or not int.from_bytes(raw[2:4], "little") & SE_SELF_RELATIVE:
            raise _Blocked("cng_security_descriptor_malformed")
        for field_offset in (4, 8, 16):
            offset = int.from_bytes(raw[field_offset : field_offset + 4], "little")
            if offset < 20 or offset > len(raw) - 8:
                raise _Blocked("cng_security_descriptor_malformed")
        buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        start = ctypes.addressof(buffer)
        end = start + len(raw)
        descriptor = ctypes.c_void_p(start)
        valid_sd = self._bind(
            self._advapi,
            "IsValidSecurityDescriptor",
            [ctypes.c_void_p],
            wintypes.BOOL,
        )
        if not valid_sd(descriptor):
            raise _Blocked("cng_security_descriptor_malformed")
        control, revision = wintypes.WORD(), wintypes.DWORD()
        get_control = self._bind(
            self._advapi,
            "GetSecurityDescriptorControl",
            [
                ctypes.c_void_p,
                ctypes.POINTER(wintypes.WORD),
                ctypes.POINTER(wintypes.DWORD),
            ],
            wintypes.BOOL,
        )
        if not get_control(descriptor, ctypes.byref(control), ctypes.byref(revision)):
            raise _Blocked("cng_security_descriptor_malformed")
        if revision.value != raw[0]:
            raise _Blocked("cng_security_descriptor_malformed")
        owner, group, dacl = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
        owner_defaulted, group_defaulted = wintypes.BOOL(), wintypes.BOOL()
        for function_name, output, defaulted in (
            ("GetSecurityDescriptorOwner", owner, owner_defaulted),
            ("GetSecurityDescriptorGroup", group, group_defaulted),
        ):
            function = self._bind(
                self._advapi,
                function_name,
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(wintypes.BOOL),
                ],
                wintypes.BOOL,
            )
            if not function(descriptor, ctypes.byref(output), ctypes.byref(defaulted)):
                raise _Blocked("cng_security_descriptor_malformed")
        present, dacl_defaulted = wintypes.BOOL(), wintypes.BOOL()
        get_dacl = self._bind(
            self._advapi,
            "GetSecurityDescriptorDacl",
            [
                ctypes.c_void_p,
                ctypes.POINTER(wintypes.BOOL),
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(wintypes.BOOL),
            ],
            wintypes.BOOL,
        )
        if not get_dacl(
            descriptor,
            ctypes.byref(present),
            ctypes.byref(dacl),
            ctypes.byref(dacl_defaulted),
        ):
            raise _Blocked("cng_security_descriptor_malformed")
        if not present.value or not dacl.value or not start <= dacl.value <= end - 8:
            raise _Blocked("cng_security_descriptor_malformed")
        header = ctypes.cast(dacl, ctypes.POINTER(_AclHeader)).contents
        if (
            header.acl_size < 8
            or dacl.value + header.acl_size > end
            or header.revision != ACL_REVISION
            or header.sbz1 != 0
            or header.sbz2 != 0
        ):
            raise _Blocked("cng_security_descriptor_malformed")
        valid_acl = self._bind(
            self._advapi, "IsValidAcl", [ctypes.c_void_p], wintypes.BOOL
        )
        if not valid_acl(dacl):
            raise _Blocked("cng_security_descriptor_malformed")
        size = _AclSizeInformation()
        get_acl_info = self._bind(
            self._advapi,
            "GetAclInformation",
            [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD],
            wintypes.BOOL,
        )
        if not get_acl_info(dacl, ctypes.byref(size), ctypes.sizeof(size), 2):
            raise _Blocked("cng_security_descriptor_malformed")
        if (
            size.ace_count != header.ace_count
            or size.acl_bytes_in_use > header.acl_size
            or size.acl_bytes_in_use < 8
            or size.ace_count > 2
        ):
            raise _Blocked("cng_security_descriptor_malformed")
        get_ace = self._bind(
            self._advapi,
            "GetAce",
            [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)],
            wintypes.BOOL,
        )
        aces = []
        expected_ace_address = dacl.value + 8
        for index in range(size.ace_count):
            pointer = ctypes.c_void_p()
            if not get_ace(dacl, index, ctypes.byref(pointer)) or not pointer.value:
                raise _Blocked("cng_security_descriptor_malformed")
            if pointer.value != expected_ace_address:
                raise _Blocked("cng_security_descriptor_malformed")
            ace = ctypes.cast(pointer, ctypes.POINTER(_AceHeader)).contents
            ace_end = pointer.value + ace.ace_size
            if ace.ace_size < 16 or ace_end > dacl.value + size.acl_bytes_in_use:
                raise _Blocked("cng_security_descriptor_malformed")
            sid_prefix = ctypes.string_at(pointer.value + 8, 8)
            if ace.ace_size != 16 + 4 * sid_prefix[1]:
                raise _Blocked("cng_security_descriptor_malformed")
            if ace.ace_type != ACCESS_ALLOWED_ACE_TYPE:
                raise _Blocked("cng_security_descriptor_mismatch")
            mask = int.from_bytes(ctypes.string_at(pointer.value + 4, 4), "little")
            sid = self._sid_string(
                ctypes.c_void_p(pointer.value + 8), pointer.value + 8, ace_end
            )
            aces.append(SecurityAce(ace.ace_type, ace.ace_flags, mask, sid))
            expected_ace_address = ace_end
        if expected_ace_address != dacl.value + size.acl_bytes_in_use:
            raise _Blocked("cng_security_descriptor_malformed")
        return SecurityFacts(
            int(raw[0]),
            self._sid_string(owner, start, end),
            bool(owner_defaulted.value),
            self._sid_string(group, start, end),
            bool(group_defaulted.value),
            int(control.value),
            bool(present.value),
            bool(dacl_defaulted.value),
            int(header.revision),
            int(size.ace_count),
            tuple(aces),
        )

    def finalize_key(self, key: object, flags: int) -> None:
        if flags != NCRYPT_SILENT_FLAG:
            raise _Blocked("fixed_finalize_flags_only")
        finalize = self._bind(
            self._ncrypt,
            "NCryptFinalizeKey",
            [ctypes.c_void_p, wintypes.DWORD],
            ctypes.c_long,
        )
        self._check_status(
            finalize(ctypes.c_void_p(int(key)), flags), "cng_key_finalize_failed"
        )

    def export_public_key(self, key: object, blob_type: str) -> bytes:
        if blob_type != PUBLIC_KEY_BLOB_TYPE:
            raise _Blocked("public_blob_type_only")
        export_key = self._bind(
            self._ncrypt,
            "NCryptExportKey",
            [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.DWORD,
            ],
            ctypes.c_long,
        )
        required = wintypes.DWORD()
        self._check_status(
            export_key(
                ctypes.c_void_p(int(key)),
                None,
                PUBLIC_KEY_BLOB_TYPE,
                None,
                None,
                0,
                ctypes.byref(required),
                NCRYPT_SILENT_FLAG,
            ),
            "public_key_export_failed",
        )
        if required.value != PUBLIC_KEY_BLOB_LENGTH:
            raise _Blocked("public_key_blob_malformed")
        buffer = (ctypes.c_ubyte * required.value)()
        received = wintypes.DWORD()
        self._check_status(
            export_key(
                ctypes.c_void_p(int(key)),
                None,
                PUBLIC_KEY_BLOB_TYPE,
                None,
                buffer,
                required.value,
                ctypes.byref(received),
                NCRYPT_SILENT_FLAG,
            ),
            "public_key_export_failed",
        )
        if received.value != PUBLIC_KEY_BLOB_LENGTH:
            raise _Blocked("public_key_blob_malformed")
        return bytes(buffer)

    def sign_hash(self, key: object, digest: bytes) -> bytes:
        if type(digest) is not bytes or len(digest) != 32:
            raise _Blocked("signing_digest_invalid")
        digest_buffer = (ctypes.c_ubyte * 32).from_buffer_copy(digest)
        signature_buffer = (ctypes.c_ubyte * 64)()
        signature_length = wintypes.DWORD()
        sign = self._bind(
            self._ncrypt,
            "NCryptSignHash",
            [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.DWORD,
            ],
            ctypes.c_long,
        )
        self._check_status(
            sign(
                ctypes.c_void_p(int(key)),
                None,
                digest_buffer,
                32,
                signature_buffer,
                64,
                ctypes.byref(signature_length),
                NCRYPT_SILENT_FLAG,
            ),
            "ncrypt_sign_hash_failed",
        )
        if signature_length.value != 64:
            raise _Blocked("signature_length_invalid")
        return bytes(signature_buffer)

    def close(self, handle: object) -> None:
        if handle is None or handle == 0:
            raise _Blocked("cng_handle_lifecycle_invalid")
        free = self._bind(
            self._ncrypt,
            "NCryptFreeObject",
            [ctypes.c_void_p],
            ctypes.c_long,
        )
        self._check_status(free(ctypes.c_void_p(int(handle))), "cng_cleanup_failed")
