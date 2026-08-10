"""Pure and non-destructive tests for the production authority substrate."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import threading
import uuid
from ctypes import wintypes

import pytest

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    AuthorityObjectError,
    AuthorityPathError,
    BootstrapSchemaError,
    BootstrapSignatureError,
    BootstrapSyntaxError,
    BootstrapTrustAnchorError,
    LifecycleMutexSecurityError,
    PinnedBootstrapKey,
    PinnedBootstrapKeyRegistry,
    UnsupportedBootstrapError,
    UnsupportedWindowsPlatformError,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
    WindowsNativeError,
    parse_bootstrap_bytes,
    require_fixed_authority_path,
    verify_bootstrap_signature,
)
from trading_bot.runtime.windows_authority_mutex import (
    ADMINISTRATORS_SID,
    LIFECYCLE_MUTEX_LABEL,
    LIFECYCLE_MUTEX_PREFIX,
    SYSTEM_SID,
    GlobalLifecycleMutex,
    canonical_lifecycle_mutex_material,
    lifecycle_mutex_digest,
    lifecycle_mutex_name,
    reviewed_lifecycle_mutex_security_policy,
    select_lifecycle_mutex_owner_sid,
)
from trading_bot.runtime.windows_authority_security import (
    DELETE,
    FILE_APPEND_DATA,
    FILE_READ_ATTRIBUTES,
    FILE_READ_DATA,
    FILE_READ_EA,
    FILE_WRITE_ATTRIBUTES,
    FILE_WRITE_DATA,
    FILE_WRITE_EA,
    MUTEX_ALL_ACCESS,
    READ_CONTROL,
    SE_FILE_OBJECT,
    SE_KERNEL_OBJECT,
    SYNCHRONIZE,
    WRITE_DAC,
    WRITE_OWNER,
    AuthorityObjectKind,
    AuthorityPrincipalError,
    AuthoritySecurityError,
    SecurityAce,
    SecurityInspection,
    SecurityObjectType,
    SecurityPolicy,
    authority_parent_security_policy,
    authority_security_policy,
    resolve_current_token_sid,
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


def test_native_object_open_is_fixed_path_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_security as security

    monkeypatch.setattr(security, "require_windows_platform", lambda: None)
    with pytest.raises(AuthorityPathError):
        security.open_authority_object(
            r"F:\AITradingBot\Authority\other.sqlite3",
            AuthorityObjectKind.FILE,
        )


@pytest.mark.parametrize(
    "supplied, expected",
    [
        (
            r"\\?\F:\AITradingBot\Authority",
            r"F:\AITradingBot\Authority",
        ),
        (
            r"\\?\F:\AITradingBot\Authority\authority.sqlite3",
            r"F:\AITradingBot\Authority\authority.sqlite3",
        ),
    ],
)
def test_normalize_final_authority_path_accepts_local_dos_paths(
    supplied: str, expected: str
) -> None:
    import trading_bot.runtime.windows_authority_security as security

    assert security._normalize_final_authority_path(supplied) == expected


@pytest.mark.parametrize(
    "supplied",
    [
        r"\\?\UNC\server\share\Authority",
        r"\\server\share\Authority",
        r"\\.\F:\AITradingBot\Authority",
        r"\\?\GLOBALROOT\Device\HarddiskVolume1\Authority",
        r"\\?\Volume{12345678-1234-1234-1234-123456789abc}\Authority",
        r"\\?\F:relative\Authority",
        r"\\?\not-a-drive\Authority",
        "\\\\?\\",
    ],
)
def test_normalize_final_authority_path_rejects_unapproved_namespaces(
    supplied: str,
) -> None:
    import trading_bot.runtime.windows_authority_security as security

    with pytest.raises(AuthorityObjectError):
        security._normalize_final_authority_path(supplied)


def test_final_path_normalizes_local_dos_prefix_from_native_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_security as security

    native_value = r"\\?\F:\AITradingBot\Authority\authority.sqlite3"

    class FakeGetFinalPathNameByHandleW:
        argtypes: object
        restype: object

        def __call__(
            self,
            handle: int,
            buffer: ctypes.Array[ctypes.c_wchar],
            size: int,
            flags: int,
        ) -> int:
            assert handle == 123
            assert size == len(buffer)
            assert flags == 0
            buffer.value = native_value
            return len(native_value)

    class FakeKernel32:
        GetFinalPathNameByHandleW = FakeGetFinalPathNameByHandleW()

    monkeypatch.setattr(security, "wintypes", wintypes)
    monkeypatch.setattr(security, "_kernel32", lambda: FakeKernel32())

    assert security._final_path(123) == r"F:\AITradingBot\Authority\authority.sqlite3"


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
    generic_read_write = (
        FILE_READ_DATA
        | FILE_READ_EA
        | FILE_READ_ATTRIBUTES
        | FILE_WRITE_DATA
        | FILE_APPEND_DATA
        | FILE_WRITE_EA
        | FILE_WRITE_ATTRIBUTES
        | READ_CONTROL
        | SYNCHRONIZE
    )
    assert trading_ace.access_mask & generic_read_write == generic_read_write
    assert not trading_ace.access_mask & DELETE
    assert not trading_ace.access_mask & WRITE_DAC
    assert not trading_ace.access_mask & WRITE_OWNER
    for role in ("root", "bootstrap", "signature", "backup"):
        policy = authority_security_policy(role, trading)
        assert all(
            not ace.access_mask & FILE_WRITE_EA
            for ace in policy.aces
            if ace.principal_sid == trading
        )
    for role in ("database", "journal"):
        policy = authority_security_policy(role, trading)
        assert policy.aces[-1].access_mask == sqlite_trading_file_rights()
    assert trading not in {
        ace.principal_sid for ace in authority_security_policy("backup", trading).aces
    }
    parent = authority_parent_security_policy()
    assert trading not in {ace.principal_sid for ace in parent.aces}
    mutex = authority_security_policy("lifecycle-mutex", trading)
    assert mutex.aces[-1].access_mask & READ_CONTROL
    with pytest.raises(AuthorityPrincipalError):
        authority_security_policy("database", "Trading")


def test_security_inspection_passes_explicit_object_type_to_get_security_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_security as security

    requested_types: list[int] = []

    class FakeFunction:
        argtypes: object
        restype: object

        def __call__(self, handle: int, object_type: int, *args: object) -> int:
            assert handle == 123
            requested_types.append(object_type)
            return 5

    class FakeAdvapi32:
        GetSecurityInfo = FakeFunction()

    monkeypatch.setattr(security, "wintypes", wintypes)
    monkeypatch.setattr(security.os, "name", "nt")
    monkeypatch.setattr(security, "_advapi32", lambda: FakeAdvapi32())
    for object_type in (SecurityObjectType.FILE, SecurityObjectType.KERNEL):
        with pytest.raises(WindowsNativeError):
            security.inspect_handle_security(123, object_type)
    assert requested_types == [SE_FILE_OBJECT, SE_KERNEL_OBJECT]


def test_authority_file_and_mutex_inspection_select_their_native_object_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_security as security

    observed: list[SecurityObjectType] = []
    policy = authority_security_policy("bootstrap", "S-1-5-21-100-200-300-400")

    def fake_security(
        handle: int,
        object_type: SecurityObjectType,
    ) -> tuple[str, bool, tuple[SecurityAce, ...]]:
        observed.append(object_type)
        return policy.owner_sid, True, policy.aces

    monkeypatch.setattr(security, "require_windows_platform", lambda: None)
    monkeypatch.setattr(security, "_security", fake_security)
    monkeypatch.setattr(
        security,
        "_final_path",
        lambda handle: str(PRODUCTION_AUTHORITY_PATHS.bootstrap),
    )
    monkeypatch.setattr(security, "_attributes", lambda handle: (0, 0))
    monkeypatch.setattr(security, "_volume", lambda path: ("F:\\", "NTFS"))
    security.inspect_open_authority_object(
        123,
        PRODUCTION_AUTHORITY_PATHS.bootstrap,
        AuthorityObjectKind.FILE,
    )
    security.inspect_handle_security(123, SecurityObjectType.KERNEL)
    assert observed == [SecurityObjectType.FILE, SecurityObjectType.KERNEL]


@pytest.mark.parametrize(
    "current_sid, elevated, administrator, expected",
    [
        (
            "S-1-5-21-100-200-300-400",
            False,
            False,
            "S-1-5-21-100-200-300-400",
        ),
        ("S-1-5-18", False, False, SYSTEM_SID),
        ("S-1-5-21-100-200-300-401", True, True, ADMINISTRATORS_SID),
    ],
)
def test_lifecycle_mutex_owner_selection_uses_approved_token_facts(
    current_sid: str,
    elevated: bool,
    administrator: bool,
    expected: str,
) -> None:
    assert (
        select_lifecycle_mutex_owner_sid(
            "S-1-5-21-100-200-300-400",
            current_sid,
            token_is_elevated=elevated,
            token_is_administrator=administrator,
        )
        == expected
    )


def test_lifecycle_mutex_owner_selection_rejects_unapproved_token() -> None:
    with pytest.raises(LifecycleMutexSecurityError):
        select_lifecycle_mutex_owner_sid(
            "S-1-5-21-100-200-300-400",
            "S-1-5-21-100-200-300-401",
            token_is_elevated=False,
            token_is_administrator=False,
        )


def test_lifecycle_mutex_policy_allows_only_reviewed_owner_sids() -> None:
    trading = "S-1-5-21-100-200-300-400"
    base = authority_security_policy("lifecycle-mutex", trading)
    for owner in (ADMINISTRATORS_SID, SYSTEM_SID, trading):
        policy = reviewed_lifecycle_mutex_security_policy(trading, owner_sid=owner)
        assert policy.owner_sid == owner
        assert policy.aces == base.aces
    with pytest.raises(LifecycleMutexSecurityError):
        reviewed_lifecycle_mutex_security_policy(
            trading, owner_sid="S-1-5-21-100-200-300-401"
        )
    assert (
        authority_security_policy("database", trading).owner_sid == ADMINISTRATORS_SID
    )


@pytest.mark.parametrize(
    "owner_sid, aces, protected, accepted",
    [
        (ADMINISTRATORS_SID, "exact", True, True),
        (SYSTEM_SID, "exact", True, True),
        ("S-1-5-21-100-200-300-400", "exact", True, True),
        ("S-1-5-21-100-200-300-401", "exact", True, False),
        (ADMINISTRATORS_SID, "expanded", True, False),
        (ADMINISTRATORS_SID, "exact", False, False),
    ],
)
def test_existing_lifecycle_mutex_requires_approved_owner_and_exact_dacl(
    monkeypatch: pytest.MonkeyPatch,
    owner_sid: str,
    aces: str,
    protected: bool,
    accepted: bool,
) -> None:
    import trading_bot.runtime.windows_authority_mutex as mutex

    trading = "S-1-5-21-100-200-300-400"
    policy = authority_security_policy("lifecycle-mutex", trading)
    actual_aces = (
        policy.aces
        if aces == "exact"
        else policy.aces + (SecurityAce("S-1-5-32-545", FILE_READ_DATA),)
    )
    monkeypatch.setattr(
        mutex,
        "inspect_handle_security",
        lambda handle, object_type: (owner_sid, protected, actual_aces),
    )
    if accepted:
        assert mutex._validate_mutex_policy(123, trading).owner_sid == owner_sid
    else:
        with pytest.raises(LifecycleMutexSecurityError):
            mutex._validate_mutex_policy(123, trading)


def test_trading_can_create_a_new_mutex_with_exact_rights_and_kernel_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_mutex as mutex

    trading = "S-1-5-21-100-200-300-400"
    calls: list[tuple[str, tuple[object, ...]]] = []
    policy = reviewed_lifecycle_mutex_security_policy(trading, owner_sid=trading)

    class FakeFunction:
        argtypes: object
        restype: object

        def __init__(self, name: str, result: object) -> None:
            self.name = name
            self.result = result

        def __call__(self, *args: object) -> object:
            calls.append((self.name, args))
            return self.result

    class FakeKernel32:
        CreateMutexExW = FakeFunction("CreateMutexExW", ctypes.c_void_p(123))
        WaitForSingleObject = FakeFunction("WaitForSingleObject", mutex.WAIT_OBJECT_0)
        ReleaseMutex = FakeFunction("ReleaseMutex", True)
        CloseHandle = FakeFunction("CloseHandle", True)

    class FakeAttributes:
        attributes = ctypes.c_int()

        def __enter__(self) -> FakeAttributes:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

    monkeypatch.setattr(mutex, "require_windows_platform", lambda: None)
    monkeypatch.setattr(
        mutex,
        "resolve_current_lifecycle_mutex_owner_sid",
        lambda sid: sid,
    )
    monkeypatch.setattr(
        mutex, "build_security_attributes", lambda value: FakeAttributes()
    )
    monkeypatch.setattr(
        mutex,
        "inspect_handle_security",
        lambda handle, object_type: (
            calls.append(("inspect", (handle, object_type)))
            or (trading, True, policy.aces)
        ),
    )
    monkeypatch.setattr(
        mutex.ctypes,
        "WinDLL",
        lambda name, use_last_error: FakeKernel32(),
        raising=False,
    )

    scope = GlobalLifecycleMutex("machine", "epoch", "reservation", trading_sid=trading)
    acquisition = scope.acquire()
    assert acquisition.state.value == "OWNED"
    create_calls = [args for name, args in calls if name == "CreateMutexExW"]
    assert len(create_calls) == 1
    assert create_calls[0][1] == scope.name
    assert create_calls[0][2] == 0
    assert (
        create_calls[0][3]
        == mutex.MUTEX_MODIFY_STATE | mutex.READ_CONTROL | mutex.SYNCHRONIZE
    )
    assert (123, SecurityObjectType.KERNEL) in [
        args for name, args in calls if name == "inspect"
    ]
    scope.release()


@pytest.mark.skipif(
    os.name != "nt" or os.environ.get("AI_TRADING_BOT_RUN_WINDOWS_NATIVE_TESTS") != "1",
    reason="opt-in disposable native Windows mutex integration test",
)
def test_native_global_lifecycle_mutex_create_release_and_reacquire() -> None:
    """Exercise a temporary Global mutex without touching production authority state."""

    trading_sid = resolve_current_token_sid()
    reservation = f"native-contract-test-{os.getpid()}-{uuid.uuid4().hex}"
    first = GlobalLifecycleMutex(
        "native-contract-test-machine",
        "native-contract-test-epoch",
        reservation,
        trading_sid=trading_sid,
    )
    first_acquisition = first.acquire()
    contender_started = threading.Event()
    contender_acquired = threading.Event()
    contender_errors: list[BaseException] = []

    def contend() -> None:
        contender = GlobalLifecycleMutex(
            "native-contract-test-machine",
            "native-contract-test-epoch",
            reservation,
            trading_sid=trading_sid,
        )
        contender_started.set()
        try:
            contender.acquire()
            contender_acquired.set()
        except BaseException as error:
            contender_errors.append(error)
        finally:
            contender.release()

    thread = threading.Thread(target=contend)
    thread.start()
    try:
        assert first_acquisition.was_abandoned is False
        assert contender_started.wait(5) is True
        assert contender_acquired.wait(0.1) is False
    finally:
        first.release()
    thread.join(5)
    assert thread.is_alive() is False
    assert contender_errors == []
    assert contender_acquired.is_set() is True

    second = GlobalLifecycleMutex(
        "native-contract-test-machine",
        "native-contract-test-epoch",
        reservation,
        trading_sid=trading_sid,
    )
    second_acquisition = second.acquire()
    try:
        assert second_acquisition.was_abandoned is False
    finally:
        second.release()

    abandoned_holder: list[GlobalLifecycleMutex] = []
    abandoned_errors: list[BaseException] = []

    def abandon() -> None:
        holder = GlobalLifecycleMutex(
            "native-contract-test-machine",
            "native-contract-test-epoch",
            reservation,
            trading_sid=trading_sid,
        )
        try:
            holder.acquire()
            abandoned_holder.append(holder)
        except BaseException as error:
            abandoned_errors.append(error)

    abandoned_thread = threading.Thread(target=abandon)
    abandoned_thread.start()
    abandoned_thread.join(5)
    assert abandoned_thread.is_alive() is False
    assert abandoned_errors == []
    assert len(abandoned_holder) == 1

    recovery = GlobalLifecycleMutex(
        "native-contract-test-machine",
        "native-contract-test-epoch",
        reservation,
        trading_sid=trading_sid,
    )
    recovery_acquisition = recovery.acquire()
    try:
        assert recovery_acquisition.was_abandoned is True
    finally:
        recovery.release()
        abandoned_holder[0].close()


@pytest.mark.skipif(
    os.name != "nt" or os.environ.get("AI_TRADING_BOT_RUN_WINDOWS_NATIVE_TESTS") != "1",
    reason="opt-in disposable native Windows mutex security test",
)
def test_native_global_lifecycle_mutex_rejects_unreviewed_security() -> None:
    """Reject a disposable pre-existing Global mutex with the wrong security."""

    import trading_bot.runtime.windows_authority_mutex as mutex

    trading_sid = resolve_current_token_sid()
    reservation = f"native-hostile-test-{os.getpid()}-{uuid.uuid4().hex}"
    name = mutex.lifecycle_mutex_name(
        "native-hostile-test-machine", "native-hostile-test-epoch", reservation
    )
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateMutexExW
    create.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    create.restype = ctypes.c_void_p
    handle = create(None, name, 0, MUTEX_ALL_ACCESS)
    assert handle
    native_handle = int(getattr(handle, "value", handle))
    close = kernel32.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = wintypes.BOOL
    try:
        with pytest.raises(LifecycleMutexSecurityError):
            GlobalLifecycleMutex(
                "native-hostile-test-machine",
                "native-hostile-test-epoch",
                reservation,
                trading_sid=trading_sid,
            ).acquire()
    finally:
        assert close(native_handle)


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
