"""Pure and non-destructive tests for the production authority substrate."""

from __future__ import annotations

import hashlib
import json
import os

import pytest

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    AuthorityPathError,
    BootstrapSchemaError,
    BootstrapSignatureError,
    BootstrapSyntaxError,
    BootstrapTrustAnchorError,
    PinnedBootstrapKey,
    PinnedBootstrapKeyRegistry,
    UnsupportedBootstrapError,
    UnsupportedWindowsPlatformError,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
    parse_bootstrap_bytes,
    require_fixed_authority_path,
    verify_bootstrap_signature,
)
from trading_bot.runtime.windows_authority_mutex import (
    LIFECYCLE_MUTEX_LABEL,
    LIFECYCLE_MUTEX_PREFIX,
    canonical_lifecycle_mutex_material,
    lifecycle_mutex_digest,
    lifecycle_mutex_name,
)
from trading_bot.runtime.windows_authority_security import (
    DELETE,
    FILE_READ_DATA,
    READ_CONTROL,
    WRITE_DAC,
    WRITE_OWNER,
    AuthorityObjectKind,
    AuthorityPrincipalError,
    AuthoritySecurityError,
    SecurityAce,
    SecurityInspection,
    SecurityPolicy,
    authority_parent_security_policy,
    authority_security_policy,
    sqlite_trading_file_rights,
)


def _bootstrap() -> WindowsAuthorityBootstrap:
    return WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=1,
        machine_authority_id="87654321-4321-8765-cba9-876543210987",
        authority_epoch_id="12345678-1234-5678-9abc-def012345678",
        signing_key_id="production-bootstrap-p256/v1",
        approved_account_sid="S-1-5-21-100-200-300-400",
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        output_root=str(PRODUCTION_AUTHORITY_PATHS.capture_output),
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="0" * 64,
    )


def test_fixed_paths_are_code_owned_and_environment_independent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    expected = str(PRODUCTION_AUTHORITY_PATHS.database)
    monkeypatch.setenv("TEMP", "C:\\attacker\\temp")
    monkeypatch.setenv("TMP", "C:\\attacker\\tmp")
    monkeypatch.setenv("TMPDIR", "C:\\attacker\\tmpdir")
    monkeypatch.chdir(str(tmp_path))
    assert str(PRODUCTION_AUTHORITY_PATHS.database) == expected
    assert str(PRODUCTION_AUTHORITY_PATHS.root) == "F:\\AITradingBot\\Authority"
    assert PRODUCTION_AUTHORITY_PATHS.root.drive == "F:"
    assert PRODUCTION_AUTHORITY_PATHS.root.anchor == "F:\\"
    with pytest.raises(AuthorityPathError):
        require_fixed_authority_path(
            "C:\\other\\authority.sqlite3", PRODUCTION_AUTHORITY_PATHS.database
        )


def test_fixed_path_rejects_unc_device_and_drive_relative_inputs() -> None:
    expected = PRODUCTION_AUTHORITY_PATHS.database
    for supplied in (
        "\\\\server\\share\\authority.sqlite3",
        "\\\\?\\F:\\AITradingBot\\Authority\\authority.sqlite3",
        "F:authority.sqlite3",
        "F:\\AITradingBot\\Authority\\..\\Authority\\authority.sqlite3",
    ):
        with pytest.raises(AuthorityPathError):
            require_fixed_authority_path(supplied, expected)


def test_bootstrap_canonicalization_is_exact() -> None:
    model = _bootstrap()
    encoded = model.canonical_bytes()
    assert (
        encoded
        == json.dumps(
            model.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    )
    assert parse_bootstrap_bytes(encoded) == model
    assert model.digest == hashlib.sha256(encoded).hexdigest()
    with pytest.raises(BootstrapSyntaxError):
        parse_bootstrap_bytes(b" " + encoded)
    with pytest.raises(BootstrapSyntaxError):
        parse_bootstrap_bytes(
            encoded.replace(b'"provider_id"', b'"provider_id":"x","provider_id"', 1)
        )


@pytest.mark.parametrize(
    "change, exception",
    [
        ({"bootstrap_schema": 2}, UnsupportedBootstrapError),
        (
            {"authority_policy_version": "authority-policy/v2"},
            UnsupportedBootstrapError,
        ),
        ({"claim_policy_version": "claim-policy/v2"}, UnsupportedBootstrapError),
        (
            {"approved_account_sid": "S-01-5-21-100-200-300-400"},
            BootstrapSchemaError,
        ),
        ({"provider_id": "other"}, BootstrapSchemaError),
        ({"database_path": "C:\\other.sqlite3"}, BootstrapSchemaError),
        ({"database_identity_digest": "A" * 64}, BootstrapSchemaError),
    ],
)
def test_bootstrap_rejects_unsupported_or_drifted_values(
    change: dict[str, object], exception: type[Exception]
) -> None:
    values = _bootstrap().to_dict()
    values.update(change)
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(exception):
        parse_bootstrap_bytes(encoded)


def test_bootstrap_rejects_unknown_fields_and_noncanonical_types() -> None:
    values = _bootstrap().to_dict()
    values["unexpected"] = True
    with pytest.raises(BootstrapSchemaError):
        parse_bootstrap_bytes(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
        )
    values = _bootstrap().to_dict()
    values["bootstrap_generation"] = True
    with pytest.raises(BootstrapSchemaError):
        parse_bootstrap_bytes(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
        )


def test_production_trust_anchor_is_explicitly_not_provisioned() -> None:
    assert PRODUCTION_PINNED_BOOTSTRAP_KEYS.keys == ()
    if os.name != "nt":
        with pytest.raises(UnsupportedWindowsPlatformError):
            verify_bootstrap_signature(_bootstrap().canonical_bytes(), b"x" * 64)
        return
    with pytest.raises(BootstrapTrustAnchorError):
        verify_bootstrap_signature(_bootstrap().canonical_bytes(), b"x" * 64)
    with pytest.raises(BootstrapSignatureError):
        verify_bootstrap_signature(_bootstrap().canonical_bytes(), b"x")


def test_test_only_key_registry_validates_shape_without_production_material() -> None:
    public_key = b"\x04" + b"\x01" * 32 + b"\x02" * 32
    registry = PinnedBootstrapKeyRegistry((PinnedBootstrapKey("test/v1", public_key),))
    assert registry.get("test/v1").public_key == public_key
    with pytest.raises(BootstrapTrustAnchorError):
        registry.get("other/v1")


@pytest.mark.skipif(os.name != "nt", reason="P-256 vector uses Windows CNG")
def test_test_only_p256_p1363_vector_verifies_through_cng() -> None:
    values = _bootstrap().to_dict()
    values["signing_key_id"] = "test/v1"
    bootstrap_bytes = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    public_key = bytes.fromhex(
        "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296"
        "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
    )
    signature = bytes.fromhex(
        "654c6af39b4cc4b69220d5785e90aba76d9922d785e36891f5d667ba5d52e7ea"
        "c2f3305ffd565ec3673f474d045e5447b3fd239aed7cb989498dbe0d3336ca63"
    )
    registry = PinnedBootstrapKeyRegistry((PinnedBootstrapKey("test/v1", public_key),))
    result = verify_bootstrap_signature(
        bootstrap_bytes, signature, key_registry=registry
    )
    assert result.signing_key_id == "test/v1"
    assert result.signature_length == 64
    modified_values = dict(values)
    modified_values["database_identity_digest"] = "1" * 64
    modified_bootstrap = json.dumps(
        modified_values, sort_keys=True, separators=(",", ":")
    ).encode()
    with pytest.raises(BootstrapSignatureError):
        verify_bootstrap_signature(modified_bootstrap, signature, key_registry=registry)
    with pytest.raises(BootstrapSignatureError):
        verify_bootstrap_signature(
            bootstrap_bytes,
            signature[:-1] + bytes([signature[-1] ^ 1]),
            key_registry=registry,
        )
    with pytest.raises(BootstrapSignatureError):
        verify_bootstrap_signature(bootstrap_bytes, b"x", key_registry=registry)
    wrong_key = public_key[:-1] + bytes([public_key[-1] ^ 1])
    wrong_registry = PinnedBootstrapKeyRegistry(
        (PinnedBootstrapKey("test/v1", wrong_key),)
    )
    with pytest.raises(WindowsAuthorityError):
        verify_bootstrap_signature(
            bootstrap_bytes, signature, key_registry=wrong_registry
        )
    wrong_id_values = dict(values)
    wrong_id_values["signing_key_id"] = "test/missing"
    wrong_id_bootstrap = json.dumps(
        wrong_id_values, sort_keys=True, separators=(",", ":")
    ).encode()
    with pytest.raises(BootstrapTrustAnchorError):
        verify_bootstrap_signature(wrong_id_bootstrap, signature, key_registry=registry)


def test_lifecycle_mutex_identity_and_name_are_fixed() -> None:
    machine = "87654321-4321-8765-cba9-876543210987"
    epoch = "12345678-1234-5678-9abc-def012345678"
    reservation = "51e87e09-cea2-5828-8598-14dd053be048"
    material = canonical_lifecycle_mutex_material(machine, epoch, reservation)
    assert material == (
        b'{"authority_epoch_id":"12345678-1234-5678-9abc-def012345678",'
        b'"label":"lifecycle-arbiter/v1",'
        b'"launch_reservation_id":"51e87e09-cea2-5828-8598-14dd053be048",'
        b'"machine_authority_id":"87654321-4321-8765-cba9-876543210987"}'
    )
    digest = hashlib.sha256(material).hexdigest()
    assert lifecycle_mutex_digest(machine, epoch, reservation) == digest
    assert (
        lifecycle_mutex_name(machine, epoch, reservation)
        == LIFECYCLE_MUTEX_PREFIX + digest
    )
    assert LIFECYCLE_MUTEX_LABEL not in digest
    assert "Local\\" not in lifecycle_mutex_name(machine, epoch, reservation)


def test_security_policy_is_sid_based_and_does_not_grant_dangerous_rights() -> None:
    trading = "S-1-5-21-100-200-300-400"
    database = authority_security_policy("database", trading)
    assert [ace.principal_sid for ace in database.aces] == [
        "S-1-5-32-544",
        "S-1-5-18",
        trading,
    ]
    trading_ace = database.aces[-1]
    assert trading_ace.access_mask == sqlite_trading_file_rights()
    assert not trading_ace.access_mask & DELETE
    assert not trading_ace.access_mask & WRITE_DAC
    assert not trading_ace.access_mask & WRITE_OWNER
    backup = authority_security_policy("backup", trading)
    assert trading not in {ace.principal_sid for ace in backup.aces}
    parent = authority_parent_security_policy()
    assert trading not in {ace.principal_sid for ace in parent.aces}
    mutex = authority_security_policy("lifecycle-mutex", trading)
    assert mutex.aces[-1].access_mask & READ_CONTROL
    with pytest.raises(AuthorityPrincipalError):
        authority_security_policy("database", "Trading")


def _directory_inspection(
    path: object,
    policy: SecurityPolicy,
    *,
    owner_sid: str | None = None,
    dacl_protected: bool | None = None,
    aces: tuple[SecurityAce, ...] | None = None,
) -> SecurityInspection:
    return SecurityInspection(
        expected_path=str(path),
        final_path=str(path),
        kind=AuthorityObjectKind.DIRECTORY,
        owner_sid=owner_sid if owner_sid is not None else policy.owner_sid,
        dacl_protected=(
            dacl_protected if dacl_protected is not None else policy.dacl_protected
        ),
        aces=aces if aces is not None else policy.aces,
        is_reparse_point=False,
        volume_root="F:\\",
        filesystem="NTFS",
    )


def test_fixed_parent_chain_uses_role_aware_policies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_security as security

    trading_sid = "S-1-5-21-100-200-300-400"
    parent = PRODUCTION_AUTHORITY_PATHS.root.parent
    root_policy = authority_security_policy("root", trading_sid)
    parent_policy = authority_parent_security_policy()
    inspections = {
        str(parent): _directory_inspection(parent, parent_policy),
        str(PRODUCTION_AUTHORITY_PATHS.root): _directory_inspection(
            PRODUCTION_AUTHORITY_PATHS.root, root_policy
        ),
    }
    opened: list[str] = []

    class FakeHandle:
        def __enter__(self) -> int:
            return 1

        def __exit__(
            self,
            exc_type: object,
            exc: object,
            traceback: object,
        ) -> None:
            return None

    def fake_open(path: object, kind: AuthorityObjectKind) -> FakeHandle:
        assert kind is AuthorityObjectKind.DIRECTORY
        opened.append(str(path))
        return FakeHandle()

    def fake_inspect(
        handle: int,
        expected_path: object,
        expected_kind: AuthorityObjectKind,
    ) -> SecurityInspection:
        assert handle == 1
        assert expected_kind is AuthorityObjectKind.DIRECTORY
        return inspections[str(expected_path)]

    monkeypatch.setattr(security, "open_authority_object", fake_open)
    monkeypatch.setattr(security, "inspect_open_authority_object", fake_inspect)
    for path in (
        PRODUCTION_AUTHORITY_PATHS.bootstrap,
        PRODUCTION_AUTHORITY_PATHS.database,
        PRODUCTION_AUTHORITY_PATHS.journal,
        PRODUCTION_AUTHORITY_PATHS.capture_output,
        PRODUCTION_AUTHORITY_PATHS.backup,
    ):
        opened.clear()
        security.validate_fixed_parent_chain(path, trading_sid=trading_sid)
        assert opened == [str(parent), str(PRODUCTION_AUTHORITY_PATHS.root)]


def test_outer_parent_preflight_does_not_require_trading_sid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_security as security

    parent = PRODUCTION_AUTHORITY_PATHS.root.parent
    inspection = _directory_inspection(parent, authority_parent_security_policy())

    class FakeHandle:
        def __enter__(self) -> int:
            return 1

        def __exit__(
            self,
            exc_type: object,
            exc: object,
            traceback: object,
        ) -> None:
            return None

    monkeypatch.setattr(
        security,
        "open_authority_object",
        lambda path, kind: FakeHandle(),
    )
    monkeypatch.setattr(
        security,
        "inspect_open_authority_object",
        lambda handle, expected_path, expected_kind: inspection,
    )
    security.validate_fixed_parent_chain(PRODUCTION_AUTHORITY_PATHS.root)


@pytest.mark.parametrize(
    "component, mutation",
    [
        ("outer", "trading"),
        ("root", "missing_trading"),
        ("root", "wrong_trading"),
        ("root", "extra_ace"),
        ("outer", "wrong_owner"),
        ("outer", "unprotected"),
        ("root", "wrong_owner"),
        ("root", "unprotected"),
    ],
)
def test_fixed_parent_chain_rejects_role_policy_drift(
    monkeypatch: pytest.MonkeyPatch,
    component: str,
    mutation: str,
) -> None:
    import trading_bot.runtime.windows_authority_security as security

    trading_sid = "S-1-5-21-100-200-300-400"
    parent = PRODUCTION_AUTHORITY_PATHS.root.parent
    parent_policy = authority_parent_security_policy()
    root_policy = authority_security_policy("root", trading_sid)
    outer_inspection = _directory_inspection(parent, parent_policy)
    root_inspection = _directory_inspection(
        PRODUCTION_AUTHORITY_PATHS.root, root_policy
    )
    if component == "outer":
        if mutation == "trading":
            outer_inspection = _directory_inspection(
                parent,
                parent_policy,
                aces=root_policy.aces,
            )
        elif mutation == "wrong_owner":
            outer_inspection = _directory_inspection(
                parent,
                parent_policy,
                owner_sid="S-1-5-18",
            )
        else:
            outer_inspection = _directory_inspection(
                parent,
                parent_policy,
                dacl_protected=False,
            )
    else:
        if mutation == "missing_trading":
            root_inspection = _directory_inspection(
                PRODUCTION_AUTHORITY_PATHS.root,
                root_policy,
                aces=parent_policy.aces,
            )
        elif mutation == "wrong_trading":
            root_inspection = _directory_inspection(
                PRODUCTION_AUTHORITY_PATHS.root,
                root_policy,
                aces=authority_security_policy("root", "S-1-5-21-100-200-300-401").aces,
            )
        elif mutation == "extra_ace":
            root_inspection = _directory_inspection(
                PRODUCTION_AUTHORITY_PATHS.root,
                root_policy,
                aces=root_policy.aces + (SecurityAce("S-1-5-32-545", FILE_READ_DATA),),
            )
        elif mutation == "wrong_owner":
            root_inspection = _directory_inspection(
                PRODUCTION_AUTHORITY_PATHS.root,
                root_policy,
                owner_sid="S-1-5-18",
            )
        else:
            root_inspection = _directory_inspection(
                PRODUCTION_AUTHORITY_PATHS.root,
                root_policy,
                dacl_protected=False,
            )
    inspections = {
        str(parent): outer_inspection,
        str(PRODUCTION_AUTHORITY_PATHS.root): root_inspection,
    }

    class FakeHandle:
        def __enter__(self) -> int:
            return 1

        def __exit__(
            self,
            exc_type: object,
            exc: object,
            traceback: object,
        ) -> None:
            return None

    monkeypatch.setattr(
        security,
        "open_authority_object",
        lambda path, kind: FakeHandle(),
    )
    monkeypatch.setattr(
        security,
        "inspect_open_authority_object",
        lambda handle, expected_path, expected_kind: inspections[str(expected_path)],
    )
    with pytest.raises(AuthoritySecurityError):
        security.validate_fixed_parent_chain(
            PRODUCTION_AUTHORITY_PATHS.bootstrap,
            trading_sid=trading_sid,
        )


def test_native_operation_has_a_typed_non_windows_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority as authority

    monkeypatch.setattr(authority.os, "name", "posix")
    with pytest.raises(UnsupportedWindowsPlatformError):
        authority._require_windows()
