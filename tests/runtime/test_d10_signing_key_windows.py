from __future__ import annotations

import ast
import ctypes
import hashlib
import json
import os
from ctypes import wintypes
from pathlib import Path

import pytest

from scripts import d10_protected_deployment as deployment
from scripts import d10_signing_key_windows as cng


def _u32(value: int) -> bytes:
    return value.to_bytes(4, "little")


def _wide(value: str) -> bytes:
    return (value + "\0").encode("utf-16-le")


def _public_blob() -> bytes:
    x = bytes.fromhex(
        "6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296"
    )
    y = bytes.fromhex(
        "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
    )
    return (
        cng.PUBLIC_KEY_BLOB_MAGIC.to_bytes(4, "little")
        + (32).to_bytes(4, "little")
        + x
        + y
    )


def _signature(r: int = 1, s: int = 1) -> bytes:
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def _security(
    *,
    owner: str = cng.OWNER_SID,
    group: str = cng.PERSISTED_GROUP_SID,
    control: int = (cng.SE_DACL_PRESENT | cng.SE_DACL_PROTECTED | cng.SE_SELF_RELATIVE),
    present: bool = True,
    defaulted: bool = False,
    revision: int = cng.ACL_REVISION,
    aces: tuple[cng.SecurityAce, ...] | None = None,
) -> cng.SecurityFacts:
    frozen_aces = (
        aces
        if aces is not None
        else (
            cng.SecurityAce(0, 0, cng.PERSISTED_ACCESS_MASK, cng.SYSTEM_SID),
            cng.SecurityAce(0, 0, cng.PERSISTED_ACCESS_MASK, cng.OWNER_SID),
        )
    )
    return cng.SecurityFacts(
        owner,
        group,
        control,
        present,
        defaulted,
        revision,
        len(frozen_aces),
        frozen_aces,
    )


class FakeCng:
    def __init__(
        self,
        *,
        existing_scopes: tuple[int, ...] = (),
        persisted: bool = False,
        overrides: dict[str, bytes] | None = None,
        security: cng.SecurityFacts | None = None,
        provider_name: str | None = None,
        public_blob: bytes | None = None,
        signature: bytes | None = None,
        admin: bool = True,
    ):
        self.existing_scopes = set(existing_scopes)
        self.persisted = persisted
        self.overrides = overrides or {}
        self.security = security or _security()
        self.security_after_set: cng.SecurityFacts | None = None
        self.provider_name = provider_name or cng.PROVIDER_NAME
        self.key_provider_name = self.provider_name
        self.fail_security_read = False
        self.public_blob = _public_blob() if public_blob is None else public_blob
        self.signature = _signature() if signature is None else signature
        self.admin = admin
        self.created = False
        self.finalized = False
        self.finalize_count = 0
        self.calls: list[tuple] = []
        self.closed: list[object] = []
        self.fail_close: set[object] = set()
        self.fail_sign = False
        self.property_reads: list[tuple[object, str]] = []
        self.sign_digests: list[bytes] = []
        self.key_properties = {
            cng.PROPERTY_NAME: _wide(cng.KEY_NAME),
            cng.PROPERTY_ALGORITHM: _wide(cng.ALGORITHM_ID),
            cng.PROPERTY_ALGORITHM_GROUP: _wide(cng.ALGORITHM_GROUP),
            cng.PROPERTY_LENGTH: _u32(cng.KEY_SIZE_BITS),
            cng.PROPERTY_KEY_TYPE: _u32(cng.NCRYPT_MACHINE_KEY_FLAG),
            cng.PROPERTY_KEY_USAGE: _u32(cng.NCRYPT_ALLOW_SIGNING_FLAG),
            cng.PROPERTY_EXPORT_POLICY: _u32(cng.NCRYPT_EXPORT_POLICY_NONE),
        }

    def require_administrator(self) -> None:
        self.calls.append(("administrator",))
        if not self.admin:
            raise OSError("not elevated")

    def open_provider(self, provider_name: str) -> object:
        self.calls.append(("open_provider", provider_name))
        assert provider_name == cng.PROVIDER_NAME
        return "provider"

    def open_key(self, provider: object, key_name: str, flags: int) -> object:
        self.calls.append(("open_key", provider, key_name, flags))
        assert provider == "provider"
        assert key_name == cng.KEY_NAME
        if flags in self.existing_scopes:
            return "existing_user" if flags == 0 else "existing_machine"
        if flags == cng.NCRYPT_MACHINE_KEY_FLAG and (
            self.persisted or (self.created and self.finalized)
        ):
            return "persisted_key" if self.persisted else "reopened_key"
        raise cng._KeyNotFound

    def create_key(
        self, provider: object, key_name: str, algorithm: str, flags: int
    ) -> object:
        self.calls.append(("create_key", provider, key_name, algorithm, flags))
        assert provider == "provider"
        assert key_name == cng.KEY_NAME
        assert algorithm == cng.ALGORITHM_ID
        assert flags == cng.NCRYPT_MACHINE_KEY_FLAG
        assert not self.created
        self.created = True
        return "created_key"

    def set_property(self, key: object, name: str, value: bytes, flags: int) -> None:
        self.calls.append(("set_property", key, name, value, flags))
        assert key == "created_key"
        self.key_properties[name] = value

    def set_security_descriptor(self, key: object, sddl: str) -> None:
        self.calls.append(("set_security", key, sddl))
        assert key == "created_key"
        assert sddl == cng.KEY_SECURITY_DESCRIPTOR_SDDL
        self.security = self.security_after_set or _security()

    def get_property(self, handle: object, name: str, flags: int = 0) -> bytes:
        self.calls.append(("get_property", handle, name, flags))
        self.property_reads.append((handle, name))
        if handle == "provider":
            if name == cng.PROPERTY_NAME:
                return _wide(self.provider_name)
            if name == cng.PROPERTY_SECURITY_DESCRIPTOR_SUPPORT:
                return _u32(1)
            raise AssertionError(f"unexpected provider property {name}")
        if name in self.overrides:
            return self.overrides[name]
        return self.key_properties[name]

    def get_provider_name(self, key: object) -> str:
        self.calls.append(("get_provider_name", key))
        assert key in {"reopened_key", "persisted_key"}
        return self.key_provider_name

    def get_security_facts(self, key: object) -> cng.SecurityFacts:
        self.calls.append(("get_security", key))
        assert key in {"reopened_key", "persisted_key"}
        if key == "reopened_key":
            assert self.finalized
        if self.fail_security_read:
            raise OSError("security read failed")
        return self.security

    def finalize_key(self, key: object, flags: int) -> None:
        self.calls.append(("finalize", key, flags))
        assert key == "created_key"
        assert flags == cng.NCRYPT_SILENT_FLAG
        self.finalize_count += 1
        self.finalized = True

    def export_public_key(self, key: object, blob_type: str) -> bytes:
        self.calls.append(("export_public", key, blob_type))
        assert key in {"reopened_key", "persisted_key"}
        assert blob_type == cng.PUBLIC_KEY_BLOB_TYPE
        return self.public_blob

    def sign_hash(self, key: object, digest: bytes) -> bytes:
        self.calls.append(("sign_hash", key, digest))
        self.sign_digests.append(digest)
        if self.fail_sign:
            raise OSError("sign failed")
        return self.signature

    def close(self, handle: object) -> None:
        self.calls.append(("close", handle))
        if handle in self.closed:
            raise AssertionError("handle closed more than once")
        self.closed.append(handle)
        if handle in self.fail_close:
            raise OSError("close failed")


def _request(digest: bytes = bytes(range(32))) -> deployment.SigningRequest:
    return deployment.SigningRequest(
        cng.SIGNING_KEY_ID,
        cng.SIGNING_ALGORITHM,
        cng.SIGNING_DIGEST,
        cng.SIGNATURE_ENCODING,
        digest,
    )


def test_enrollment_uses_fixed_machine_p256_sign_only_nonexportable_key() -> None:
    api = FakeCng()
    result = cng._prepare_with_api(api)

    assert result.status == "PASS"
    assert result.public_key == b"\x04" + _public_blob()[8:]
    assert result.public_key_sha256 == hashlib.sha256(result.public_key).hexdigest()
    assert api.calls[0] == ("administrator",)
    assert api.calls[1] == ("open_provider", cng.PROVIDER_NAME)
    assert [
        (call[2], call[3], call[4]) for call in api.calls if call[0] == "create_key"
    ] == [(cng.KEY_NAME, cng.ALGORITHM_ID, cng.NCRYPT_MACHINE_KEY_FLAG)]
    assert [call[3] for call in api.calls if call[0] == "open_key"] == [
        0,
        cng.NCRYPT_MACHINE_KEY_FLAG,
        cng.NCRYPT_MACHINE_KEY_FLAG,
    ]
    set_props = [call[1:] for call in api.calls if call[0] == "set_property"]
    assert set_props == [
        (
            "created_key",
            cng.PROPERTY_KEY_USAGE,
            _u32(cng.NCRYPT_ALLOW_SIGNING_FLAG),
            cng.NCRYPT_PERSIST_FLAG | cng.NCRYPT_SILENT_FLAG,
        ),
        (
            "created_key",
            cng.PROPERTY_EXPORT_POLICY,
            _u32(0),
            cng.NCRYPT_PERSIST_FLAG | cng.NCRYPT_SILENT_FLAG,
        ),
    ]
    assert api.finalize_count == 1
    set_security = api.calls.index(
        ("set_security", "created_key", cng.KEY_SECURITY_DESCRIPTOR_SDDL)
    )
    finalize = api.calls.index(("finalize", "created_key", cng.NCRYPT_SILENT_FLAG))
    close_created = api.calls.index(("close", "created_key"))
    reopen = api.calls.index(
        ("open_key", "provider", cng.KEY_NAME, cng.NCRYPT_MACHINE_KEY_FLAG),
        finalize,
    )
    verify_provider = api.calls.index(("get_provider_name", "reopened_key"))
    verify_security = api.calls.index(("get_security", "reopened_key"))
    export = api.calls.index(
        ("export_public", "reopened_key", cng.PUBLIC_KEY_BLOB_TYPE)
    )
    assert set_security < finalize < close_created < reopen < verify_provider
    assert all(
        api.calls.index(("set_property", *prop)) < finalize for prop in set_props
    )
    assert not any(call == ("get_security", "created_key") for call in api.calls)
    assert {handle for handle, _ in api.property_reads if handle != "provider"} == {
        "reopened_key"
    }
    assert ("get_provider_name", "created_key") not in api.calls
    assert {
        name for handle, name in api.property_reads if handle == "reopened_key"
    } == {
        cng.PROPERTY_NAME,
        cng.PROPERTY_ALGORITHM,
        cng.PROPERTY_ALGORITHM_GROUP,
        cng.PROPERTY_LENGTH,
        cng.PROPERTY_KEY_TYPE,
        cng.PROPERTY_KEY_USAGE,
        cng.PROPERTY_EXPORT_POLICY,
    }
    assert all(
        api.calls.index(("get_property", "reopened_key", name, cng.NCRYPT_SILENT_FLAG))
        < verify_security
        for name in api.key_properties
    )
    assert verify_security < export
    assert len(api.closed) == len(set(api.closed)) == 3


@pytest.mark.parametrize("scope", [0, cng.NCRYPT_MACHINE_KEY_FLAG])
def test_existing_user_or_machine_key_blocks_without_overwrite(scope: int) -> None:
    api = FakeCng(existing_scopes=(scope,))

    result = cng._prepare_with_api(api)

    assert result.status == "BLOCKED"
    assert result.public_key is None
    assert result.reason_code == "fixed_key_already_exists"
    assert not any(call[0] == "create_key" for call in api.calls)
    assert api.finalize_count == 0


def test_elevation_is_required_before_provider_or_key_access() -> None:
    api = FakeCng(admin=False)

    result = cng._prepare_with_api(api)

    assert result.status == "BLOCKED"
    assert result.reason_code == "administrator_required"
    assert [call[0] for call in api.calls] == ["administrator"]


def test_security_descriptor_is_protected_admin_system_only() -> None:
    result = cng._prepare_with_api(FakeCng())

    assert result.status == "PASS"
    transcript = json.loads(result.transcript)
    security = transcript["persisted_security"]
    assert security["owner_sid"] == cng.OWNER_SID
    assert security["group_sid"] == cng.PERSISTED_GROUP_SID
    assert security["control"] & cng.SE_DACL_PROTECTED
    assert security["aces"] == [
        {"type": 0, "flags": 0, "mask": 0xD01F01FF, "sid": cng.SYSTEM_SID},
        {"type": 0, "flags": 0, "mask": 0xD01F01FF, "sid": cng.OWNER_SID},
    ]
    assert deployment.TRADING_SID not in result.transcript.decode()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        (cng.PROPERTY_NAME, _wide("other-key")),
        (cng.PROPERTY_ALGORITHM, _wide("ECDSA_P384")),
        (cng.PROPERTY_ALGORITHM_GROUP, _wide("ECDH")),
        (cng.PROPERTY_LENGTH, _u32(384)),
        (cng.PROPERTY_KEY_TYPE, _u32(0)),
        (cng.PROPERTY_KEY_USAGE, _u32(0)),
        (cng.PROPERTY_KEY_USAGE, _u32(3)),
        (cng.PROPERTY_EXPORT_POLICY, _u32(1)),
        (cng.PROPERTY_EXPORT_POLICY, _u32(4)),
    ],
)
def test_reopened_property_mismatch_blocks(name: str, value: bytes) -> None:
    api = FakeCng(overrides={name: value})

    result = cng._prepare_with_api(api)

    assert result.status == "BLOCKED"
    assert result.public_key is None
    assert api.finalize_count == 1
    assert not any(call[0] == "export_public" for call in api.calls)


def test_wrong_provider_identity_blocks_enrollment() -> None:
    api = FakeCng(provider_name="Another Key Storage Provider")

    result = cng._prepare_with_api(api)

    assert result.status == "BLOCKED"
    assert result.reason_code == "cng_provider_identity_mismatch"
    assert not any(call[0] == "create_key" for call in api.calls)


def test_reopened_provider_mismatch_blocks_public_export() -> None:
    api = FakeCng()
    api.key_provider_name = "Another Key Storage Provider"

    result = cng._prepare_with_api(api)

    assert result.status == "BLOCKED"
    assert result.reason_code == "cng_provider_identity_mismatch"
    assert api.finalize_count == 1
    assert ("get_provider_name", "reopened_key") in api.calls
    assert not any(call[0] == "export_public" for call in api.calls)
    assert len([call for call in api.calls if call[0] == "create_key"]) == 1


def test_reopened_security_read_failure_blocks_without_retry_or_delete() -> None:
    api = FakeCng()
    api.fail_security_read = True

    result = cng._prepare_with_api(api)

    assert result.status == "BLOCKED"
    assert result.reason_code == "cng_security_descriptor_unavailable"
    assert api.finalize_count == 1
    assert ("get_security", "reopened_key") in api.calls
    assert not any(call[0] in {"export_public", "delete_key"} for call in api.calls)
    assert len([call for call in api.calls if call[0] == "create_key"]) == 1
    assert len([call for call in api.calls if call[0] == "open_key"]) == 3


def test_security_descriptor_drift_blocks_after_reopen() -> None:
    api = FakeCng()
    api.security_after_set = _security(owner=cng.SYSTEM_SID)

    result = cng._prepare_with_api(api)

    assert result.status == "BLOCKED"
    assert result.reason_code == "cng_security_descriptor_mismatch"
    assert api.finalize_count == 1
    assert api.calls.index(("close", "created_key")) < api.calls.index(
        ("get_security", "reopened_key")
    )
    assert not any(call[0] in {"export_public", "delete_key"} for call in api.calls)
    assert len([call for call in api.calls if call[0] == "create_key"]) == 1


def test_public_ecc_blob_normalizes_to_canonical_sec1_point() -> None:
    blob = _public_blob()
    point = cng.normalize_public_key_blob(blob)

    assert point == b"\x04" + blob[8:]
    assert len(point) == 65


@pytest.mark.parametrize(
    "blob",
    [
        b"short",
        (0).to_bytes(4, "little") + (32).to_bytes(4, "little") + bytes(64),
        cng.PUBLIC_KEY_BLOB_MAGIC.to_bytes(4, "little")
        + (31).to_bytes(4, "little")
        + bytes(64),
        cng.PUBLIC_KEY_BLOB_MAGIC.to_bytes(4, "little")
        + (32).to_bytes(4, "little")
        + bytes(64),
    ],
)
def test_malformed_public_blob_blocks(blob: bytes) -> None:
    with pytest.raises(cng._Blocked):
        cng.normalize_public_key_blob(blob)


def test_enrollment_transcript_is_deterministic_bounded_and_public_only() -> None:
    first = cng._prepare_with_api(FakeCng())
    second = cng._prepare_with_api(FakeCng())

    assert first.transcript == second.transcript
    assert len(first.transcript) <= cng.MAX_ENROLLMENT_TRANSCRIPT_BYTES
    facts = json.loads(first.transcript)
    assert facts["status"] == "PASS"
    assert facts["public_key_sec1_hex"] == first.public_key.hex()
    assert facts["public_key_sha256"] == first.public_key_sha256
    assert "private_key" not in facts
    assert "key_material" not in facts


def test_enrollment_blocked_transcript_is_bounded_and_has_no_public_material() -> None:
    result = cng._prepare_with_api(FakeCng(existing_scopes=(32,)))

    assert result.status == "BLOCKED"
    assert len(result.transcript) <= cng.MAX_ENROLLMENT_TRANSCRIPT_BYTES
    facts = json.loads(result.transcript)
    assert facts["status"] == "BLOCKED"
    assert facts["public_key_sec1_hex"] is None
    assert facts["public_key_sha256"] is None


def test_transcript_contains_no_private_output_path_or_native_private_export_api() -> (
    None
):
    source = Path(cng.__file__).read_text(encoding="utf-8")
    native_methods = set(vars(cng._WindowsCngApi))
    result = cng._prepare_with_api(FakeCng())

    assert result.public_key is not None
    assert not hasattr(result, "private_key")
    assert not any("private" in name.casefold() for name in native_methods)
    assert "NCRYPT_ECCPRIVATEBLOB" not in source
    assert "BCRYPT_ECCPRIVATEBLOB" not in source
    assert "NCryptDeleteKey" not in source
    assert "NCryptImportKey" not in source


def test_signer_identity_is_future_v3_and_frozen_protocol() -> None:
    identity = cng.WindowsCngExternalSigner().identity

    assert type(identity) is deployment.SigningIdentity
    assert identity.key_id == "AITradingBot/D10/DeploymentAttestation/v3"
    assert identity.algorithm == "ECDSA-P256"
    assert identity.digest_algorithm == "SHA-256"
    assert identity.signature_encoding == "IEEE-P1363"
    assert identity.private_key_exportable is False
    assert cng.SIGNING_KEY_ID != deployment.D10_SIGNING_KEY_ID


def test_signer_opens_only_fixed_machine_key_revalidates_and_signs_one_digest() -> None:
    api = FakeCng(persisted=True)
    request = _request()

    signed = cng._sign_with_api(api, request)

    assert type(signed) is deployment.DetachedSignature
    assert signed.key_id == cng.SIGNING_KEY_ID
    assert signed.algorithm == cng.SIGNING_ALGORITHM
    assert signed.digest_algorithm == cng.SIGNING_DIGEST
    assert signed.signature_encoding == cng.SIGNATURE_ENCODING
    assert signed.signature == _signature()
    assert api.sign_digests == [request.message_sha256]
    assert [call[3] for call in api.calls if call[0] == "open_key"] == [
        cng.NCRYPT_MACHINE_KEY_FLAG
    ]
    assert len(api.closed) == len(set(api.closed)) == 2


def test_signer_revalidates_key_properties_for_each_signature() -> None:
    api = FakeCng(persisted=True)
    request = _request()
    cng._sign_with_api(api, request)
    reads_before_second = len(api.property_reads)
    api.overrides[cng.PROPERTY_EXPORT_POLICY] = _u32(1)

    with pytest.raises(deployment.DeploymentBlocked):
        cng._sign_with_api(api, request)

    assert len(api.property_reads) > reads_before_second
    assert api.sign_digests == [request.message_sha256]


@pytest.mark.parametrize(
    "signing_request",
    [
        b"raw message bytes",
        deployment.SigningRequest(
            "wrong/key",
            cng.SIGNING_ALGORITHM,
            cng.SIGNING_DIGEST,
            cng.SIGNATURE_ENCODING,
            bytes(32),
        ),
        deployment.SigningRequest(
            cng.SIGNING_KEY_ID,
            "RSA",
            cng.SIGNING_DIGEST,
            cng.SIGNATURE_ENCODING,
            bytes(32),
        ),
        deployment.SigningRequest(
            cng.SIGNING_KEY_ID,
            cng.SIGNING_ALGORITHM,
            cng.SIGNING_DIGEST,
            cng.SIGNATURE_ENCODING,
            bytes(31),
        ),
    ],
)
def test_signer_rejects_non_digest_or_wrong_protocol_before_open(
    signing_request: object,
) -> None:
    api = FakeCng(persisted=True)

    with pytest.raises(deployment.DeploymentBlocked):
        cng._sign_with_api(api, signing_request)

    assert not any(
        call[0] in {"open_provider", "open_key", "sign_hash"} for call in api.calls
    )


@pytest.mark.parametrize(
    "signature",
    [
        bytes(63),
        bytes(65),
        _signature(r=0, s=1),
        _signature(r=1, s=0),
        _signature(r=deployment.P256_ORDER, s=1),
        _signature(r=1, s=deployment.P256_ORDER),
    ],
)
def test_signer_blocks_short_long_or_noncanonical_signature(signature: bytes) -> None:
    api = FakeCng(persisted=True, signature=signature)

    with pytest.raises(deployment.DeploymentBlocked):
        cng._sign_with_api(api, _request())

    assert api.sign_digests == [bytes(range(32))]


def test_ncrypt_sign_hash_failure_blocks() -> None:
    api = FakeCng(persisted=True)
    api.fail_sign = True

    with pytest.raises(deployment.DeploymentBlocked):
        cng._sign_with_api(api, _request())

    assert api.sign_digests == [bytes(range(32))]


def test_enrollment_and_signer_cleanup_failures_block() -> None:
    enrollment = FakeCng()
    enrollment.fail_close.add("reopened_key")
    result = cng._prepare_with_api(enrollment)
    assert result.status == "BLOCKED"
    assert result.reason_code == "cng_cleanup_failed"

    creation_close = FakeCng()
    creation_close.fail_close.add("created_key")
    result = cng._prepare_with_api(creation_close)
    assert result.status == "BLOCKED"
    assert result.reason_code == "cng_cleanup_failed"
    assert creation_close.finalize_count == 1
    assert len([call for call in creation_close.calls if call[0] == "open_key"]) == 2
    assert not any(
        call[0] in {"export_public", "delete_key"} for call in creation_close.calls
    )

    signer = FakeCng(persisted=True)
    signer.fail_close.add("persisted_key")
    with pytest.raises(deployment.DeploymentBlocked, match="cleanup"):
        cng._sign_with_api(signer, _request())


def test_fixed_source_has_no_trust_publication_or_trading_effect_imports() -> None:
    tree = ast.parse(Path(cng.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    source = Path(cng.__file__).read_text(encoding="utf-8")

    assert not imported & {
        "p1242_provision_d10",
        "p1243_publish_d10_trust",
        "personal_desktop_d10_activation_lease",
        "personal_desktop_d10_launch_guard",
    }
    for forbidden in (
        "p1242_provision_d10",
        "p1243_publish_d10_trust",
        "personal_desktop_d10_activation_lease",
        "personal_desktop_d10_launch_guard",
        "broker",
        "settlement",
        "scheduler",
        "D10_ROOT",
        "D10_ACTIVATION_LEASE",
    ):
        assert forbidden not in source


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (cng._STATUS_NOT_FOUND, cng._KeyNotFound),
        (cng._STATUS_BAD_KEYSET, cng._KeyNotFound),
        (0x80090005, cng._Blocked),
    ],
)
def test_native_open_key_classifies_only_exact_absence_and_closes_error_handle(
    status: int, expected: type[Exception]
) -> None:
    api = cng._WindowsCngApi.__new__(cng._WindowsCngApi)
    api._ncrypt = object()
    closed: list[int] = []

    def open_key(provider, output, name, legacy_spec, flags):
        assert provider.value == 1
        assert name == cng.KEY_NAME
        assert legacy_spec == 0
        assert flags == cng.NCRYPT_MACHINE_KEY_FLAG
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = 41
        return status

    api._bind = lambda library, name, args, result: open_key
    api.close = closed.append

    with pytest.raises(expected):
        api.open_key(1, cng.KEY_NAME, cng.NCRYPT_MACHINE_KEY_FLAG)

    assert closed == [41]


@pytest.mark.parametrize(
    ("user_status", "machine_status"),
    [
        (cng._STATUS_NOT_FOUND, cng._STATUS_NOT_FOUND),
        (cng._STATUS_NOT_FOUND, cng._STATUS_BAD_KEYSET),
        (cng._STATUS_BAD_KEYSET, cng._STATUS_NOT_FOUND),
        (cng._STATUS_BAD_KEYSET, cng._STATUS_BAD_KEYSET),
    ],
)
def test_enrollment_creates_only_after_native_absence_in_both_scopes(
    user_status: int, machine_status: int
) -> None:
    native = cng._WindowsCngApi.__new__(cng._WindowsCngApi)
    native._ncrypt = object()
    statuses = {0: user_status, cng.NCRYPT_MACHINE_KEY_FLAG: machine_status}

    def open_key(provider, output, name, legacy_spec, flags):
        assert provider.value == 1
        assert name == cng.KEY_NAME
        assert legacy_spec == 0
        assert not ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0]
        return statuses[flags]

    native._bind = lambda library, name, args, result: open_key

    class NativeProbeCng(FakeCng):
        def open_key(self, provider: object, key_name: str, flags: int) -> object:
            if self.created:
                return super().open_key(provider, key_name, flags)
            self.calls.append(("open_key", provider, key_name, flags))
            return native.open_key(1, key_name, flags)

    api = NativeProbeCng()
    result = cng._prepare_with_api(api)

    assert result.status == "PASS"
    assert [call[3] for call in api.calls if call[0] == "open_key"] == [
        0,
        cng.NCRYPT_MACHINE_KEY_FLAG,
        cng.NCRYPT_MACHINE_KEY_FLAG,
    ]
    assert len([call for call in api.calls if call[0] == "create_key"]) == 1
    assert api.finalize_count == 1


@pytest.mark.parametrize(
    "facts",
    [
        _security(owner=cng.SYSTEM_SID),
        _security(group=cng.SYSTEM_SID),
        _security(group=deployment.TRADING_SID),
        _security(control=cng.SE_DACL_PRESENT | cng.SE_SELF_RELATIVE),
        _security(present=False),
        _security(defaulted=True),
        _security(revision=4),
        _security(aces=()),
        _security(aces=(cng.SecurityAce(0, 0, 0xD01F01FF, cng.SYSTEM_SID),)),
        _security(
            aces=(
                cng.SecurityAce(0, 0, 0xD01F01FF, cng.OWNER_SID),
                cng.SecurityAce(0, 0, 0xD01F01FF, cng.SYSTEM_SID),
            )
        ),
        _security(
            aces=(
                cng.SecurityAce(1, 0, 0xD01F01FF, cng.SYSTEM_SID),
                cng.SecurityAce(0, 0, 0xD01F01FF, cng.OWNER_SID),
            )
        ),
        _security(
            aces=(
                cng.SecurityAce(0, 0x10, 0xD01F01FF, cng.SYSTEM_SID),
                cng.SecurityAce(0, 0, 0xD01F01FF, cng.OWNER_SID),
            )
        ),
        _security(
            aces=(
                cng.SecurityAce(0, 0, 0x001F01FF, cng.SYSTEM_SID),
                cng.SecurityAce(0, 0, 0xD01F01FF, cng.OWNER_SID),
            )
        ),
        _security(
            aces=(
                cng.SecurityAce(0, 0, 0xF01F01FF, cng.SYSTEM_SID),
                cng.SecurityAce(0, 0, 0xD01F01FF, cng.OWNER_SID),
            )
        ),
        _security(
            aces=(
                cng.SecurityAce(0, 0, 0xD01F01FF, cng.SYSTEM_SID),
                cng.SecurityAce(0, 0, 0xD01F01FF, deployment.TRADING_SID),
            )
        ),
        _security(
            aces=(
                cng.SecurityAce(0, 0, 0xD01F01FF, cng.SYSTEM_SID),
                cng.SecurityAce(0, 0, 0xD01F01FF, cng.OWNER_SID),
                cng.SecurityAce(0, 0, 0xD01F01FF, "S-1-5-32-545"),
            )
        ),
    ],
)
def test_frozen_structural_security_drift_blocks_export_and_sign(
    facts: cng.SecurityFacts,
) -> None:
    api = FakeCng(persisted=True, security=facts)
    result = cng._qualify_existing_with_api(api)
    assert result.status == "BLOCKED"
    assert result.public_key is None
    assert not any(call[0] == "export_public" for call in api.calls)
    with pytest.raises(deployment.DeploymentBlocked):
        cng._sign_with_api(FakeCng(persisted=True, security=facts), _request())


def test_frozen_structural_security_exact_mask_passes() -> None:
    result = cng._qualify_existing_with_api(FakeCng(persisted=True))
    assert result.status == "PASS"
    assert result.public_key == b"\x04" + _public_blob()[8:]


@pytest.mark.parametrize(
    ("existing_scopes", "persisted", "reason"),
    [
        ((0,), True, "fixed_user_key_already_exists"),
        ((), False, "fixed_machine_key_absent"),
    ],
)
def test_recovery_requires_absent_user_and_present_machine_key(
    existing_scopes: tuple[int, ...], persisted: bool, reason: str
) -> None:
    api = FakeCng(existing_scopes=existing_scopes, persisted=persisted)
    result = cng._qualify_existing_with_api(api)
    assert result.reason_code == reason
    assert not any(
        call[0]
        in {
            "create_key",
            "set_property",
            "set_security",
            "finalize",
            "sign_hash",
            "export_public",
        }
        for call in api.calls
    )


def test_recovery_is_read_only_and_exports_after_full_verification() -> None:
    api = FakeCng(persisted=True)
    result = cng._qualify_existing_with_api(api)
    assert result.status == "PASS"
    assert result.public_key == b"\x04" + _public_blob()[8:]
    assert not any(
        call[0]
        in {"create_key", "set_property", "set_security", "finalize", "sign_hash"}
        for call in api.calls
    )
    security_read = api.calls.index(("get_security", "persisted_key"))
    export = api.calls.index(
        ("export_public", "persisted_key", cng.PUBLIC_KEY_BLOB_TYPE)
    )
    assert security_read < export
    facts = json.loads(result.transcript)
    assert facts["schema"].endswith("attempt2-read-only-qualification/v1")
    assert facts["persisted_security"]["aces"][0]["mask"] == 0xD01F01FF
    assert len(result.transcript) <= cng.MAX_ENROLLMENT_TRANSCRIPT_BYTES
    assert (
        result.transcript
        == cng._qualify_existing_with_api(FakeCng(persisted=True)).transcript
    )


def test_recovery_property_and_cleanup_failures_block() -> None:
    for name, value in (
        (cng.PROPERTY_NAME, _wide("other")),
        (cng.PROPERTY_ALGORITHM, _wide("ECDSA_P384")),
        (cng.PROPERTY_ALGORITHM_GROUP, _wide("ECDH")),
        (cng.PROPERTY_LENGTH, _u32(384)),
        (cng.PROPERTY_KEY_TYPE, _u32(0)),
        (cng.PROPERTY_KEY_USAGE, _u32(3)),
        (cng.PROPERTY_EXPORT_POLICY, _u32(1)),
    ):
        api = FakeCng(persisted=True, overrides={name: value})
        assert cng._qualify_existing_with_api(api).status == "BLOCKED"
        assert not any(call[0] == "export_public" for call in api.calls)
    api = FakeCng(persisted=True)
    api.fail_close.add("persisted_key")
    assert cng._qualify_existing_with_api(api).reason_code == "cng_cleanup_failed"


def test_recovery_entry_point_does_not_reference_mutating_methods() -> None:
    source = Path(cng.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for name in (
        "_qualify_existing_with_api",
        "qualify_existing_d10_signing_key_after_attempt2",
    ):
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        calls = {
            node.func.attr
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert calls.isdisjoint(
            {
                "create_key",
                "set_property",
                "set_security_descriptor",
                "finalize_key",
                "sign_hash",
            }
        )
    assert "NCryptDeleteKey" not in source
    assert "NCryptImportKey" not in source


@pytest.mark.skipif(os.name != "nt", reason="synthetic native Windows descriptor")
def test_native_binary_descriptor_parsing_and_cleanup_failure() -> None:
    sddl = (
        "O:BAG:S-1-5-21-1397534616-3988210162-180023805-1005"
        "D:P(A;;0xD01F01FF;;;SY)(A;;0xD01F01FF;;;BA)"
    )
    advapi = ctypes.WinDLL(r"C:\Windows\System32\advapi32.dll", use_last_error=True)
    kernel = ctypes.WinDLL(r"C:\Windows\System32\kernel32.dll", use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [
        ctypes.c_wchar_p,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.DWORD),
    ]
    convert.restype = wintypes.BOOL
    descriptor, length = ctypes.c_void_p(), wintypes.DWORD()
    assert convert(sddl, 1, ctypes.byref(descriptor), ctypes.byref(length))
    try:
        raw = ctypes.string_at(descriptor, length.value)
    finally:
        local_free = kernel.LocalFree
        local_free.argtypes = [ctypes.c_void_p]
        local_free.restype = ctypes.c_void_p
        assert not local_free(descriptor)

    api = cng._WindowsCngApi.__new__(cng._WindowsCngApi)
    api._advapi = advapi
    api._kernel = kernel
    flags_seen: list[int] = []

    def read_property(key: object, name: str, flags: int) -> bytes:
        assert key == 17
        assert name == cng.PROPERTY_SECURITY_DESCRIPTOR
        flags_seen.append(flags)
        return raw

    api._read_property = read_property
    facts = api.get_security_facts(17)
    cng._verify_security_facts(facts)
    assert facts.owner_sid == cng.OWNER_SID
    assert facts.group_sid == cng.PERSISTED_GROUP_SID
    assert facts.acl_revision == 2
    assert facts.aces[0].access_mask == 0xD01F01FF
    assert flags_seen == [cng.NCRYPT_SILENT_FLAG | cng.SECURITY_DESCRIPTOR_INFORMATION]
    assert cng.SECURITY_DESCRIPTOR_INFORMATION & cng.SACL_SECURITY_INFORMATION == 0

    acl_offset = int.from_bytes(raw[16:20], "little")
    first_ace = acl_offset + 8
    for offset, replacement in (
        (0, bytes([2])),  # descriptor revision
        (16, bytes(4)),  # NULL DACL
        (16, (0xFFFFFFFF).to_bytes(4, "little")),  # out-of-buffer ACL
        (2, bytes([0, 0])),  # descriptor control
        (acl_offset, bytes([0])),  # ACL revision
        (acl_offset + 4, bytes([3, 0])),  # wrong ACE inventory
        (first_ace, bytes([1])),  # deny ACE
        (first_ace + 1, bytes([0x10])),  # inherited ACE
        (first_ace + 2, bytes([4, 0])),  # truncated ACE
        (first_ace + 4, (0x001F01FF).to_bytes(4, "little")),
        (first_ace + 8, bytes([2])),  # invalid SID revision
    ):
        malformed = bytearray(raw)
        malformed[offset : offset + len(replacement)] = replacement
        api._read_property = lambda key, name, flags, data=bytes(malformed): data
        with pytest.raises(cng._Blocked):
            cng._verify_security_facts(api.get_security_facts(17))

    api._read_property = lambda key, name, flags: bytes(len(raw))
    with pytest.raises(cng._Blocked, match="malformed"):
        api.get_security_facts(17)

    api._read_property = read_property
    api._free_local = lambda pointer: (_ for _ in ()).throw(
        cng._Blocked("cng_cleanup_failed")
    )
    with pytest.raises(cng._Blocked, match="cleanup"):
        api.get_security_facts(17)


def test_signer_rechecks_native_security_for_every_digest() -> None:
    api = FakeCng(persisted=True)
    cng._sign_with_api(api, _request())
    api.closed.clear()  # Fake handles are names reused across separate opens.
    api.security = _security(group=deployment.TRADING_SID)
    with pytest.raises(
        deployment.DeploymentBlocked, match="security_descriptor_mismatch"
    ):
        cng._sign_with_api(api, _request())
    assert len(api.sign_digests) == 1
    assert [
        call for call in api.calls if call == ("get_security", "persisted_key")
    ] == [
        ("get_security", "persisted_key"),
        ("get_security", "persisted_key"),
    ]
