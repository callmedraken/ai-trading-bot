"""Explicit, phase-scoped Windows authority acceptance boundaries.

The opt-in tests in this module are deliberately not a single production
acceptance test.  Each selected phase emits only its own sanitized evidence;
the production GO decision remains an external checklist over all required
phase evidence.
"""

from __future__ import annotations

import ctypes
import json
import os
import sqlite3
import sys
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from typing import NoReturn

import pytest

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    AuthorityPrincipalError,
    BootstrapError,
    BootstrapSchemaError,
    BootstrapSignatureError,
    BootstrapTrustAnchorError,
    PinnedBootstrapKey,
    PinnedBootstrapKeyRegistry,
    UnsupportedBootstrapError,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
    WindowsNativeError,
    parse_bootstrap_bytes,
    verify_bootstrap_signature,
)
from trading_bot.runtime.windows_authority_provisioning import (
    validate_bootstrap_installation,
    validate_installed_authority,
)
from trading_bot.runtime.windows_authority_security import (
    DELETE,
    ERROR_ACCESS_DENIED,
    ERROR_FILE_NOT_FOUND,
    ERROR_PATH_NOT_FOUND,
    FILE_FLAG_BACKUP_SEMANTICS,
    FILE_FLAG_OPEN_REPARSE_POINT,
    FILE_SHARE_DELETE,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    INVALID_HANDLE_VALUE,
    OPEN_EXISTING,
    WRITE_DAC,
    WRITE_OWNER,
    AuthorityObjectKind,
    authority_security_policy,
    inspect_open_authority_object,
    is_current_token_administrator,
    is_current_token_elevated,
    open_authority_object,
    read_open_authority_file,
    require_security_policy,
    resolve_current_token_sid,
    validate_fixed_parent_chain,
)
from trading_bot.runtime.windows_authority_sqlite import (
    configure_and_validate_authority_sqlite_connection,
)

ACCEPTANCE_OPT_IN_ENV = "AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE"
ACCEPTANCE_PHASE_ENV = "AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_PHASE"
ACCEPTANCE_MAINTENANCE_ENV = "AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_MAINTENANCE"
ACCEPTANCE_SQLITE_VFS_ROOT = Path(r"F:\AITradingBot\AuthorityAcceptance\SQLiteVfs")
ACCEPTANCE_SQLITE_VFS_DATABASE = ACCEPTANCE_SQLITE_VFS_ROOT / "authority-vfs.sqlite3"
ACCEPTANCE_SQLITE_VFS_JOURNAL = (
    ACCEPTANCE_SQLITE_VFS_ROOT / "authority-vfs.sqlite3-journal"
)
ACCEPTANCE_SQLITE_VFS_TABLE = "windows_authority_acceptance_probe"
ACCEPTANCE_SQLITE_VFS_PROBE_ID = 1
ACCEPTANCE_SQLITE_VFS_MARKER = "milestone-a-rollback-probe"


class AcceptancePhase(StrEnum):
    """One independently retained class of Windows acceptance evidence."""

    ADMINISTRATOR_FIXED_ROOT = "administrator"
    TRADING_ALLOW_DENY = "trading"
    SQLITE_WINDOWS_VFS = "sqlite-vfs"
    REPARSE_AND_SUBSTITUTION = "reparse"
    CROSS_SESSION_GLOBAL_MUTEX = "cross-session-mutex"


class AcceptanceEvidenceStatus(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"


REQUIRED_ACCEPTANCE_PHASES = tuple(AcceptancePhase)
_ACCEPTANCE_COMMAND = (
    ".venv\\Scripts\\python.exe -m pytest "
    "tests/acceptance/test_windows_authority_provisioning_acceptance.py -q"
)


class AcceptanceConfigurationError(RuntimeError):
    """Raised when the explicit acceptance phase selection is unsafe."""


class AcceptanceBlockedError(RuntimeError):
    """Raised when an external Windows acceptance prerequisite is unavailable."""


@dataclass(frozen=True, slots=True)
class AcceptanceEvidence:
    """Safe evidence for exactly one phase, never for Milestone A as a whole."""

    phase: AcceptancePhase
    status: AcceptanceEvidenceStatus
    account_classification: str
    scenario_names: tuple[str, ...]
    bootstrap_digest: str | None = None
    database_state: str | None = None
    trading_sid: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the only facts this acceptance boundary may retain."""

        return {
            "account_classification": self.account_classification,
            "bootstrap_digest": self.bootstrap_digest,
            "command": _ACCEPTANCE_COMMAND,
            "database_state": self.database_state,
            "phase_id": self.phase.name,
            "scenario_names": list(self.scenario_names),
            "status": self.status.value,
            "trading_sid": self.trading_sid,
        }


def select_acceptance_phase(
    environ: Mapping[str, str] | None = None,
) -> AcceptancePhase:
    """Require the global opt-in and one known, independently named phase."""

    values = os.environ if environ is None else environ
    if values.get(ACCEPTANCE_OPT_IN_ENV) != "1":
        raise AcceptanceConfigurationError(
            f"{ACCEPTANCE_OPT_IN_ENV}=1 is required for Windows acceptance"
        )
    raw_phase = values.get(ACCEPTANCE_PHASE_ENV)
    if raw_phase is None:
        raise AcceptanceConfigurationError(
            f"{ACCEPTANCE_PHASE_ENV} must select one acceptance phase"
        )
    try:
        return AcceptancePhase(raw_phase)
    except ValueError as error:
        allowed = ", ".join(phase.value for phase in REQUIRED_ACCEPTANCE_PHASES)
        raise AcceptanceConfigurationError(
            f"unknown Windows acceptance phase {raw_phase!r}; allowed values: {allowed}"
        ) from error


def missing_required_phase_ids(
    evidence: Iterable[AcceptanceEvidence],
) -> tuple[AcceptancePhase, ...]:
    """Return phase IDs without separate PASS evidence for the external checklist."""

    passed = {
        item.phase for item in evidence if item.status is AcceptanceEvidenceStatus.PASS
    }
    return tuple(phase for phase in REQUIRED_ACCEPTANCE_PHASES if phase not in passed)


def require_administrator_phase_facts(
    *,
    token_is_elevated: bool,
    token_is_administrator: bool,
) -> None:
    """Reject an administrator phase that is not actually administrator-run."""

    if not token_is_elevated or not token_is_administrator:
        raise AcceptanceBlockedError(
            "administrator phase requires an elevated administrator token"
        )


def require_trading_phase_facts(
    *,
    current_sid: str,
    expected_sid: str,
    token_is_elevated: bool,
    token_is_administrator: bool,
) -> None:
    """Reject a Trading phase that is not actually running as standard Trading."""

    if current_sid != expected_sid:
        raise AcceptanceBlockedError(
            "Trading phase must run under the signed Trading SID"
        )
    if token_is_elevated or token_is_administrator:
        raise AcceptanceBlockedError(
            "Trading phase rejects administrator or elevated tokens"
        )


def _selected_phase_or_skip(expected: AcceptancePhase) -> AcceptancePhase:
    if os.environ.get(ACCEPTANCE_OPT_IN_ENV) != "1":
        pytest.skip(
            "Windows authority acceptance requires explicit opt-in and phase selection"
        )
    try:
        selected = select_acceptance_phase()
    except AcceptanceConfigurationError as error:
        pytest.fail(str(error))
    if selected is not expected:
        pytest.skip(f"phase {selected.name} selected; {expected.name} not selected")
    return selected


def _require_windows_acceptance() -> None:
    if os.name != "nt":
        raise AcceptanceBlockedError("Windows is required for this acceptance phase")


def _read_verified_fixed_file(
    path: str | PureWindowsPath,
    role: str,
    trading_sid: str,
) -> bytes:
    """Read administrator-validated trust material from its inspected handle."""

    validate_fixed_parent_chain(path, trading_sid=trading_sid)
    return _read_inspected_fixed_file(path, role, trading_sid)


def _read_trading_verified_fixed_file(
    path: str | PureWindowsPath,
    role: str,
    trading_sid: str,
) -> bytes:
    """Read a Trading-visible trust file without opening its protected parent."""

    return _read_inspected_fixed_file(path, role, trading_sid)


def _read_inspected_fixed_file(
    path: str | PureWindowsPath,
    role: str,
    trading_sid: str,
) -> bytes:
    """Read bytes only from the no-follow handle whose fixed target was inspected."""

    policy = authority_security_policy(role, trading_sid)
    with open_authority_object(path, AuthorityObjectKind.FILE) as handle:
        inspection = inspect_open_authority_object(
            handle, path, AuthorityObjectKind.FILE
        )
        require_security_policy(inspection, policy)
        return read_open_authority_file(handle)


def _validate_fixed_object_for_capability(
    path: str | PureWindowsPath,
    role: str,
    kind: AuthorityObjectKind,
    trading_sid: str,
) -> None:
    """Validate one Trading-visible target before an acceptance capability probe."""

    try:
        policy = authority_security_policy(role, trading_sid)
        with open_authority_object(path, kind) as handle:
            inspection = inspect_open_authority_object(handle, path, kind)
            require_security_policy(inspection, policy)
    except WindowsNativeError as error:
        if error.error_code in {ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND}:
            raise AcceptanceBlockedError(
                f"required production {role} object is absent"
            ) from error
        raise


def _bootstrap_variant(bootstrap: object, **changes: object) -> bytes:
    values = dict(bootstrap.to_dict())  # type: ignore[union-attr]
    values.update(changes)
    return json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _require_bootstrap_rejection(
    scenario: str,
    operation: Callable[[], object],
    *,
    expected_exception: type[BaseException]
    | tuple[type[BaseException], ...]
    | None = None,
) -> str:
    try:
        operation()
    except (BootstrapError, WindowsAuthorityError, ValueError) as error:
        if expected_exception is not None and not isinstance(error, expected_exception):
            raise AssertionError(
                f"acceptance negative scenario {scenario} reached "
                f"{type(error).__name__}; expected {expected_exception}"
            ) from error
        return scenario
    raise AssertionError(
        f"acceptance negative scenario unexpectedly passed: {scenario}"
    )


def _administrator_negative_matrix(
    bootstrap: object,
    signature: bytes,
    trading_sid: str,
) -> tuple[str, ...]:
    scenarios: list[str] = []
    scenarios.append(
        _require_bootstrap_rejection(
            "bad-signature",
            lambda: validate_bootstrap_installation(
                bootstrap.canonical_bytes(),  # type: ignore[union-attr]
                bytes([signature[0] ^ 1]) + signature[1:],
                trading_sid=trading_sid,
            ),
            expected_exception=BootstrapSignatureError,
        )
    )
    scenarios.append(
        _require_bootstrap_rejection(
            "unsupported-signing-key-id",
            lambda: validate_bootstrap_installation(
                _bootstrap_variant(bootstrap, signing_key_id="unsupported/v1"),
                signature,
                trading_sid=trading_sid,
            ),
            expected_exception=BootstrapTrustAnchorError,
        )
    )
    wrong_sid_base, wrong_sid_number = trading_sid.rsplit("-", 1)
    scenarios.append(
        _require_bootstrap_rejection(
            "wrong-trading-sid",
            lambda: validate_bootstrap_installation(
                bootstrap.canonical_bytes(),  # type: ignore[union-attr]
                signature,
                trading_sid=f"{wrong_sid_base}-{int(wrong_sid_number) + 1}",
            ),
            expected_exception=AuthorityPrincipalError,
        )
    )
    scenarios.append(
        _require_bootstrap_rejection(
            "wrong-fixed-path",
            lambda: parse_bootstrap_bytes(
                _bootstrap_variant(
                    bootstrap,
                    database_path=str(PRODUCTION_AUTHORITY_PATHS.database) + ".wrong",
                ),
            ),
            expected_exception=BootstrapSchemaError,
        )
    )
    scenarios.append(
        _require_bootstrap_rejection(
            "wrong-provider-operation",
            lambda: parse_bootstrap_bytes(
                _bootstrap_variant(
                    bootstrap,
                    provider_id="unapproved-provider",
                    permitted_provider_operation="unapproved-operation",
                ),
            ),
            expected_exception=BootstrapSchemaError,
        )
    )
    scenarios.append(
        _require_bootstrap_rejection(
            "unsupported-policy",
            lambda: parse_bootstrap_bytes(
                _bootstrap_variant(
                    bootstrap,
                    authority_policy_version="authority-policy/v999",
                ),
            ),
            expected_exception=UnsupportedBootstrapError,
        )
    )
    return tuple(scenarios)


def _run_administrator_fixed_root_phase() -> AcceptanceEvidence:
    _require_windows_acceptance()
    require_administrator_phase_facts(
        token_is_elevated=is_current_token_elevated(),
        token_is_administrator=is_current_token_administrator(),
    )
    from trading_bot.runtime.windows_authority_security import (
        require_trading_standard_account,
    )

    trading_sid = require_trading_standard_account()
    evidence = validate_installed_authority()
    expected_roles = {
        "root",
        "bootstrap",
        "signature",
        "capture-output",
        "backup",
        "database",
        "journal",
    }
    if evidence.authority_root != str(PRODUCTION_AUTHORITY_PATHS.root):
        raise AcceptanceBlockedError("installed authority root is not the fixed path")
    if set(evidence.inspected_objects) != expected_roles:
        raise AcceptanceBlockedError(
            "installed authority evidence does not cover the complete fixed tree"
        )
    if evidence.database_present is not True or evidence.journal_present is not True:
        raise AcceptanceBlockedError(
            "administrator acceptance requires the paired database and journal"
        )
    bootstrap_bytes = _read_verified_fixed_file(
        PRODUCTION_AUTHORITY_PATHS.bootstrap,
        "bootstrap",
        trading_sid,
    )
    signature_bytes = _read_verified_fixed_file(
        PRODUCTION_AUTHORITY_PATHS.signature,
        "signature",
        trading_sid,
    )
    bootstrap = parse_bootstrap_bytes(bootstrap_bytes)
    if len(signature_bytes) != 64 or bootstrap.approved_account_sid != trading_sid:
        raise AcceptanceBlockedError("installed signed material facts are inconsistent")
    repeated = validate_installed_authority()
    if repeated != evidence:
        raise AssertionError("repeated administrator validation was not idempotent")
    negative_scenarios = _administrator_negative_matrix(
        bootstrap,
        signature_bytes,
        trading_sid,
    )
    return AcceptanceEvidence(
        phase=AcceptancePhase.ADMINISTRATOR_FIXED_ROOT,
        status=AcceptanceEvidenceStatus.PASS,
        account_classification="elevated-administrator",
        scenario_names=(
            "elevated-administrator-token",
            "fixed-root-owner-protected-dacl-final-local-ntfs-no-reparse",
            "same-handle-bootstrap-signature-read-and-verified-install",
            "installed-database-lifecycle-state-reported",
            "repeated-validation-read-only-idempotent",
            *negative_scenarios,
        ),
        bootstrap_digest=evidence.bootstrap_digest,
        database_state=evidence.database_state,
        trading_sid=trading_sid,
    )


def _require_trading_context() -> tuple[object, str]:
    _require_windows_acceptance()
    current_sid = resolve_current_token_sid()
    bootstrap_bytes = _read_trading_verified_fixed_file(
        PRODUCTION_AUTHORITY_PATHS.bootstrap,
        "bootstrap",
        current_sid,
    )
    signature_bytes = _read_trading_verified_fixed_file(
        PRODUCTION_AUTHORITY_PATHS.signature,
        "signature",
        current_sid,
    )
    verification = verify_bootstrap_signature(
        bootstrap_bytes,
        signature_bytes,
        key_registry=PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    )
    require_trading_phase_facts(
        current_sid=current_sid,
        expected_sid=verification.bootstrap.approved_account_sid,
        token_is_elevated=is_current_token_elevated(),
        token_is_administrator=is_current_token_administrator(),
    )
    return verification, current_sid


def test_administrator_trust_read_still_validates_parent_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, object]] = []
    module = sys.modules[__name__]

    class FakeHandle:
        def __enter__(self) -> FakeHandle:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    handle = FakeHandle()
    monkeypatch.setattr(
        module,
        "validate_fixed_parent_chain",
        lambda path, *, trading_sid: events.append(("parent", path)),
    )
    monkeypatch.setattr(
        module,
        "authority_security_policy",
        lambda role, trading_sid: (role, trading_sid),
    )
    monkeypatch.setattr(
        module,
        "open_authority_object",
        lambda path, kind: events.append(("open", handle)) or handle,
    )
    monkeypatch.setattr(
        module,
        "inspect_open_authority_object",
        lambda inspected, path, kind: events.append(("inspect", inspected)) or object(),
    )
    monkeypatch.setattr(
        module,
        "require_security_policy",
        lambda inspection, policy: events.append(("policy", inspection)),
    )
    monkeypatch.setattr(
        module,
        "read_open_authority_file",
        lambda inspected: events.append(("read", inspected)) or b"bootstrap",
    )

    assert (
        _read_verified_fixed_file(
            PRODUCTION_AUTHORITY_PATHS.bootstrap,
            "bootstrap",
            "S-1-5-21-100-200-300-400",
        )
        == b"bootstrap"
    )
    assert [name for name, _value in events] == [
        "parent",
        "open",
        "inspect",
        "policy",
        "read",
    ]
    assert events[1][1] is handle
    assert events[2][1] is handle
    assert events[4][1] is handle


def test_trading_context_reads_inspected_handles_without_parent_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = sys.modules[__name__]
    trading_sid = "S-1-5-21-100-200-300-400"
    events: list[tuple[str, object]] = []

    class FakeHandle:
        def __init__(self, label: str) -> None:
            self.label = label

        def __enter__(self) -> FakeHandle:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    handles: dict[str, FakeHandle] = {}

    def fake_open(path: str | PureWindowsPath, kind: AuthorityObjectKind) -> FakeHandle:
        handle = FakeHandle(str(path))
        handles[str(path)] = handle
        events.append(("open", handle))
        return handle

    def reject_parent(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("Trading acceptance must not open the sealed parent")

    monkeypatch.setattr(module, "_require_windows_acceptance", lambda: None)
    monkeypatch.setattr(module, "resolve_current_token_sid", lambda: trading_sid)
    monkeypatch.setattr(module, "validate_fixed_parent_chain", reject_parent)
    monkeypatch.setattr(
        module,
        "authority_security_policy",
        lambda role, sid: (role, sid),
    )
    monkeypatch.setattr(module, "open_authority_object", fake_open)
    monkeypatch.setattr(
        module,
        "inspect_open_authority_object",
        lambda handle, path, kind: events.append(("inspect", handle)) or object(),
    )
    monkeypatch.setattr(
        module,
        "require_security_policy",
        lambda inspection, policy: events.append(("policy", inspection)),
    )
    monkeypatch.setattr(
        module,
        "read_open_authority_file",
        lambda handle: events.append(("read", handle)) or handle.label.encode(),
    )
    monkeypatch.setattr(
        module,
        "verify_bootstrap_signature",
        lambda bootstrap_bytes, signature_bytes, *, key_registry: SimpleNamespace(
            bootstrap=SimpleNamespace(approved_account_sid=trading_sid),
            bootstrap_digest="digest",
        ),
    )
    monkeypatch.setattr(module, "is_current_token_elevated", lambda: False)
    monkeypatch.setattr(module, "is_current_token_administrator", lambda: False)

    verification, current_sid = _require_trading_context()

    assert current_sid == trading_sid
    assert verification.bootstrap_digest == "digest"
    assert handles[str(PRODUCTION_AUTHORITY_PATHS.bootstrap)] is not None
    assert handles[str(PRODUCTION_AUTHORITY_PATHS.signature)] is not None
    for name, value in events:
        if name == "read":
            assert any(
                other_name == "inspect" and other_value is value
                for other_name, other_value in events
            )


def test_trading_fixed_object_validation_does_not_open_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = sys.modules[__name__]
    trading_sid = "S-1-5-21-100-200-300-400"
    events: list[str] = []

    class FakeHandle:
        def __enter__(self) -> FakeHandle:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def reject_parent(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("Trading acceptance must not open the sealed parent")

    monkeypatch.setattr(module, "validate_fixed_parent_chain", reject_parent)
    monkeypatch.setattr(
        module,
        "authority_security_policy",
        lambda role, sid: events.append("policy-build") or (role, sid),
    )
    monkeypatch.setattr(
        module,
        "open_authority_object",
        lambda path, kind: events.append("open") or FakeHandle(),
    )
    monkeypatch.setattr(
        module,
        "inspect_open_authority_object",
        lambda handle, path, kind: events.append("inspect") or object(),
    )
    monkeypatch.setattr(
        module,
        "require_security_policy",
        lambda inspection, policy: events.append("policy-check"),
    )

    _validate_fixed_object_for_capability(
        PRODUCTION_AUTHORITY_PATHS.root,
        "root",
        AuthorityObjectKind.DIRECTORY,
        trading_sid,
    )

    assert events == ["policy-build", "open", "inspect", "policy-check"]


def test_trading_fixed_object_validation_propagates_target_and_policy_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = sys.modules[__name__]
    trading_sid = "S-1-5-21-100-200-300-400"

    class FakeHandle:
        def __enter__(self) -> FakeHandle:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        module,
        "authority_security_policy",
        lambda role, sid: (role, sid),
    )
    monkeypatch.setattr(
        module,
        "open_authority_object",
        lambda path, kind: FakeHandle(),
    )
    target_failure = WindowsAuthorityError("inspected target rejected")

    def fail_inspection(*args: object, **kwargs: object) -> NoReturn:
        raise target_failure

    monkeypatch.setattr(module, "inspect_open_authority_object", fail_inspection)
    with pytest.raises(WindowsAuthorityError, match="inspected target rejected"):
        _validate_fixed_object_for_capability(
            PRODUCTION_AUTHORITY_PATHS.root,
            "root",
            AuthorityObjectKind.DIRECTORY,
            trading_sid,
        )

    monkeypatch.setattr(
        module,
        "inspect_open_authority_object",
        lambda handle, path, kind: object(),
    )
    security_failure = WindowsAuthorityError("security policy rejected")

    def fail_policy(*args: object, **kwargs: object) -> NoReturn:
        raise security_failure

    monkeypatch.setattr(module, "require_security_policy", fail_policy)
    with pytest.raises(WindowsAuthorityError, match="security policy rejected"):
        _validate_fixed_object_for_capability(
            PRODUCTION_AUTHORITY_PATHS.root,
            "root",
            AuthorityObjectKind.DIRECTORY,
            trading_sid,
        )


def _expect_access_denied(scenario: str, operation: Callable[[], object]) -> None:
    try:
        result = operation()
    except AcceptanceBlockedError:
        raise
    except WindowsAuthorityError as error:
        if getattr(error, "error_code", None) == ERROR_ACCESS_DENIED:
            return
        raise AcceptanceBlockedError(
            f"{scenario} returned an unrelated Windows failure"
        ) from error
    except OSError as error:
        if getattr(error, "winerror", None) == ERROR_ACCESS_DENIED:
            return
        raise AcceptanceBlockedError(
            f"{scenario} returned an unrelated operating-system failure"
        ) from error
    if result is False:
        return
    pytest.fail(f"Trading allow/deny policy allowed {scenario}")


_POINTER_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def _native_handle_value(handle: object) -> int:
    """Normalize acceptance-probe handles without importing runtime internals."""

    value = getattr(handle, "value", handle)
    if value is None:
        return 0
    normalized = int(value)
    if normalized in (INVALID_HANDLE_VALUE, _POINTER_INVALID_HANDLE_VALUE):
        return INVALID_HANDLE_VALUE
    return normalized


def _native_access_probe(
    path: object, desired_access: int, kind: AuthorityObjectKind
) -> bool:
    """Probe a capability without deleting, renaming, or replacing the target."""

    if os.name != "nt":
        raise AcceptanceBlockedError("native Windows access probing is unavailable")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    create.restype = ctypes.c_void_p
    flags = FILE_FLAG_OPEN_REPARSE_POINT
    if kind is AuthorityObjectKind.DIRECTORY:
        flags |= FILE_FLAG_BACKUP_SEMANTICS
    handle = create(
        str(path),
        desired_access,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        flags,
        None,
    )
    value = _native_handle_value(handle)
    if value in (0, INVALID_HANDLE_VALUE):
        error_code = ctypes.get_last_error()
        if error_code == ERROR_ACCESS_DENIED:
            return False
        raise AcceptanceBlockedError("native access probe could not execute")
    close = kernel32.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    if not close(value):
        raise AcceptanceBlockedError("native access probe handle could not close")
    return True


def _install_native_access_probe_kernel(
    monkeypatch: pytest.MonkeyPatch,
    *,
    handle: object,
    error_code: int,
    close_result: bool = True,
) -> list[object]:
    closed: list[object] = []

    class FakeCreateFile:
        argtypes: object
        restype: object

        def __call__(self, *args: object) -> object:
            return handle

    class FakeCloseHandle:
        argtypes: object
        restype: object

        def __call__(self, value: object) -> bool:
            closed.append(value)
            return close_result

    class FakeKernel32:
        CreateFileW = FakeCreateFile()
        CloseHandle = FakeCloseHandle()

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda name, use_last_error: FakeKernel32(),
        raising=False,
    )
    monkeypatch.setattr(
        ctypes,
        "get_last_error",
        lambda: error_code,
        raising=False,
    )
    return closed


def test_native_access_probe_normalizes_pointer_width_invalid_handles() -> None:
    pointer_bits = ctypes.sizeof(ctypes.c_void_p) * 8
    pointer_invalid = ctypes.c_void_p(-1).value
    assert pointer_invalid == (1 << pointer_bits) - 1
    assert _native_handle_value(None) == 0
    assert _native_handle_value(ctypes.c_void_p()) == 0
    assert _native_handle_value(0) == 0
    assert _native_handle_value(123) == 123
    assert _native_handle_value(-1) == INVALID_HANDLE_VALUE
    assert _native_handle_value(ctypes.c_void_p(-1)) == INVALID_HANDLE_VALUE
    assert _native_handle_value(pointer_invalid) == INVALID_HANDLE_VALUE


@pytest.mark.parametrize("desired_access", [DELETE, WRITE_DAC, WRITE_OWNER])
def test_native_trading_denial_probe_counts_access_denied(
    monkeypatch: pytest.MonkeyPatch,
    desired_access: int,
) -> None:
    pointer_invalid = ctypes.c_void_p(-1).value
    closed = _install_native_access_probe_kernel(
        monkeypatch,
        handle=pointer_invalid,
        error_code=ERROR_ACCESS_DENIED,
    )

    assert (
        _native_access_probe(
            PRODUCTION_AUTHORITY_PATHS.bootstrap,
            desired_access,
            AuthorityObjectKind.FILE,
        )
        is False
    )
    assert closed == []


def test_native_access_probe_blocks_unrelated_invalid_handle_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pointer_invalid = ctypes.c_void_p(-1).value
    closed = _install_native_access_probe_kernel(
        monkeypatch,
        handle=pointer_invalid,
        error_code=ERROR_FILE_NOT_FOUND,
    )

    with pytest.raises(AcceptanceBlockedError):
        _native_access_probe(
            PRODUCTION_AUTHORITY_PATHS.bootstrap,
            DELETE,
            AuthorityObjectKind.FILE,
        )
    assert closed == []


def test_native_access_probe_closes_valid_handle_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = _install_native_access_probe_kernel(
        monkeypatch,
        handle=ctypes.c_void_p(123),
        error_code=0,
    )

    assert (
        _native_access_probe(
            PRODUCTION_AUTHORITY_PATHS.bootstrap,
            DELETE,
            AuthorityObjectKind.FILE,
        )
        is True
    )
    assert closed == [123]


def test_native_access_probe_blocks_valid_handle_close_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = _install_native_access_probe_kernel(
        monkeypatch,
        handle=ctypes.c_void_p(123),
        error_code=0,
        close_result=False,
    )

    with pytest.raises(AcceptanceBlockedError):
        _native_access_probe(
            PRODUCTION_AUTHORITY_PATHS.bootstrap,
            DELETE,
            AuthorityObjectKind.FILE,
        )
    assert closed == [123]


def _create_capture_artifact(capture_root: Path) -> None:
    artifact = capture_root / (
        f".windows-authority-acceptance-{os.getpid()}-{uuid.uuid4().hex}.bin"
    )
    try:
        with artifact.open("xb") as stream:
            stream.write(b"windows-authority-acceptance\n")
    finally:
        if artifact.exists():
            try:
                artifact.unlink()
            except OSError as error:
                raise AcceptanceBlockedError(
                    "acceptance capture artifact could not be cleaned up"
                ) from error


def _create_root_probe() -> bool:
    probe = Path(str(PRODUCTION_AUTHORITY_PATHS.root)) / (
        f".windows-authority-root-probe-{os.getpid()}-{uuid.uuid4().hex}"
    )
    try:
        with probe.open("xb"):
            pass
    finally:
        if probe.exists():
            try:
                probe.unlink()
            except OSError as error:
                raise AcceptanceBlockedError(
                    "root capability probe created an artifact that could not "
                    "be cleaned"
                ) from error
    return True


def _run_trading_allow_deny_phase() -> AcceptanceEvidence:
    verification, trading_sid = _require_trading_context()
    database = PRODUCTION_AUTHORITY_PATHS.database
    journal = PRODUCTION_AUTHORITY_PATHS.journal
    _validate_fixed_object_for_capability(
        PRODUCTION_AUTHORITY_PATHS.root,
        "root",
        AuthorityObjectKind.DIRECTORY,
        trading_sid,
    )
    _validate_fixed_object_for_capability(
        PRODUCTION_AUTHORITY_PATHS.capture_output,
        "capture-output",
        AuthorityObjectKind.DIRECTORY,
        trading_sid,
    )
    _validate_fixed_object_for_capability(
        database,
        "database",
        AuthorityObjectKind.FILE,
        trading_sid,
    )
    _validate_fixed_object_for_capability(
        journal,
        "journal",
        AuthorityObjectKind.FILE,
        trading_sid,
    )
    connection = sqlite3.connect(str(database), timeout=0.0)
    try:
        connection.execute("SELECT name FROM sqlite_schema").fetchall()
    finally:
        connection.close()
    _create_capture_artifact(Path(str(PRODUCTION_AUTHORITY_PATHS.capture_output)))

    _expect_access_denied(
        "backup-inaccessible",
        lambda: (
            open_authority_object(
                PRODUCTION_AUTHORITY_PATHS.backup,
                AuthorityObjectKind.DIRECTORY,
            ).close()
            or True
        ),
    )
    _expect_access_denied("authority-root-arbitrary-create", _create_root_probe)
    for path, label in (
        (PRODUCTION_AUTHORITY_PATHS.bootstrap, "bootstrap"),
        (PRODUCTION_AUTHORITY_PATHS.signature, "signature"),
    ):
        _expect_access_denied(
            f"{label}-replace-inaccessible",
            lambda path=path: _native_access_probe(
                path, DELETE, AuthorityObjectKind.FILE
            ),
        )
    for path, label in (
        (PRODUCTION_AUTHORITY_PATHS.database, "database"),
        (PRODUCTION_AUTHORITY_PATHS.journal, "journal"),
    ):
        _expect_access_denied(
            f"{label}-delete-inaccessible",
            lambda path=path: _native_access_probe(
                path, DELETE, AuthorityObjectKind.FILE
            ),
        )
        _expect_access_denied(
            f"{label}-rename-replace-inaccessible",
            lambda path=path: _native_access_probe(
                path, DELETE, AuthorityObjectKind.FILE
            ),
        )
    for path, label in (
        (PRODUCTION_AUTHORITY_PATHS.bootstrap, "bootstrap"),
        (PRODUCTION_AUTHORITY_PATHS.signature, "signature"),
        (PRODUCTION_AUTHORITY_PATHS.database, "database"),
        (PRODUCTION_AUTHORITY_PATHS.journal, "journal"),
    ):
        _expect_access_denied(
            f"{label}-write-dac",
            lambda path=path: _native_access_probe(
                path, WRITE_DAC, AuthorityObjectKind.FILE
            ),
        )
        _expect_access_denied(
            f"{label}-write-owner",
            lambda path=path: _native_access_probe(
                path, WRITE_OWNER, AuthorityObjectKind.FILE
            ),
        )
    return AcceptanceEvidence(
        phase=AcceptancePhase.TRADING_ALLOW_DENY,
        status=AcceptanceEvidenceStatus.PASS,
        account_classification="standard-trading-non-admin",
        scenario_names=(
            "signed-trading-sid-matches-current-token",
            "token-not-administrator-and-not-elevated",
            "bootstrap-readable",
            "signature-readable",
            "database-readable",
            "journal-present-for-standard-vfs",
            "capture-output-reviewed-artifact-created-and-cleaned",
            "reviewed-denials-distinguished-as-access-denied",
            "backup-inaccessible",
            "authority-root-arbitrary-create-denied",
            "bootstrap-replace-denied",
            "signature-replace-denied",
            "database-delete-and-rename-replace-denied",
            "journal-delete-and-rename-replace-denied",
            "write-dac-denied",
            "write-owner-denied",
        ),
        bootstrap_digest=verification.bootstrap_digest,
        trading_sid=trading_sid,
    )


def _run_sqlite_windows_vfs_phase() -> AcceptanceEvidence:
    verification, trading_sid = _require_trading_context()
    database = ACCEPTANCE_SQLITE_VFS_DATABASE
    journal = ACCEPTANCE_SQLITE_VFS_JOURNAL
    if os.environ.get(ACCEPTANCE_MAINTENANCE_ENV) != "1":
        raise AcceptanceBlockedError(
            f"{ACCEPTANCE_MAINTENANCE_ENV}=1 is required for disposable "
            "SQLite write/lock acceptance"
        )
    if not database.is_file() or not journal.is_file():
        raise AcceptanceBlockedError(
            "administrator-prepared disposable SQLite VFS DB/journal pair is absent"
        )
    first: sqlite3.Connection | None = None
    second: sqlite3.Connection | None = None
    reopened: sqlite3.Connection | None = None
    try:
        first = sqlite3.connect(str(database), timeout=0.25)
        durability = configure_and_validate_authority_sqlite_connection(
            first,
            database_path=database,
            journal_path=journal,
        )
        if (
            durability.foreign_keys is not True
            or durability.journal_mode != "persist"
            or durability.synchronous != 2
        ):
            raise AssertionError(
                "SQLite durability evidence did not match the contract"
            )
        schema = tuple(
            tuple(row)
            for row in first.execute(
                f"PRAGMA table_info({ACCEPTANCE_SQLITE_VFS_TABLE})"
            ).fetchall()
        )
        if schema != (
            (0, "probe_id", "INTEGER", 0, None, 1),
            (1, "marker", "TEXT", 1, None, 0),
        ):
            raise AcceptanceBlockedError(
                "administrator-prepared disposable probe table is absent or has "
                "an unapproved schema"
            )
        if (
            first.execute(
                f"SELECT COUNT(*) FROM {ACCEPTANCE_SQLITE_VFS_TABLE}"
            ).fetchone()[0]
            != 0
        ):
            raise AcceptanceBlockedError(
                "administrator-prepared disposable probe table is not empty"
            )
        journal_before = journal.stat().st_size
        if journal_before != 0:
            raise AcceptanceBlockedError(
                "administrator-prepared disposable journal is not empty before "
                "the rollback probe"
            )
        first.execute("BEGIN IMMEDIATE")
        first.execute(
            f"INSERT INTO {ACCEPTANCE_SQLITE_VFS_TABLE} (probe_id, marker) "
            "VALUES (?, ?)",
            (ACCEPTANCE_SQLITE_VFS_PROBE_ID, ACCEPTANCE_SQLITE_VFS_MARKER),
        )
        if first.execute(
            f"SELECT marker FROM {ACCEPTANCE_SQLITE_VFS_TABLE} WHERE probe_id = ?",
            (ACCEPTANCE_SQLITE_VFS_PROBE_ID,),
        ).fetchone() != (ACCEPTANCE_SQLITE_VFS_MARKER,):
            raise AssertionError(
                "SQLite rollback marker was not visible in-transaction"
            )
        journal_during = journal.stat().st_size
        if journal_during <= journal_before:
            raise AssertionError(
                "SQLite transaction did not write the persistent journal"
            )
        second = sqlite3.connect(str(database), timeout=0.0)
        second.execute("PRAGMA busy_timeout = 0")
        with pytest.raises(sqlite3.OperationalError) as locked:
            second.execute("BEGIN IMMEDIATE")
        if "locked" not in str(locked.value).lower():
            raise AssertionError(
                "second SQLite connection did not observe real locking"
            )
        first.rollback()
        if (
            first.execute(
                f"SELECT COUNT(*) FROM {ACCEPTANCE_SQLITE_VFS_TABLE} "
                "WHERE probe_id = ?",
                (ACCEPTANCE_SQLITE_VFS_PROBE_ID,),
            ).fetchone()[0]
            != 0
        ):
            raise AssertionError("SQLite rollback left a committed probe marker")
        second.execute("BEGIN IMMEDIATE")
        second.execute(
            f"INSERT INTO {ACCEPTANCE_SQLITE_VFS_TABLE} (probe_id, marker) "
            "VALUES (?, ?)",
            (ACCEPTANCE_SQLITE_VFS_PROBE_ID, ACCEPTANCE_SQLITE_VFS_MARKER),
        )
        if second.execute(
            f"SELECT marker FROM {ACCEPTANCE_SQLITE_VFS_TABLE} WHERE probe_id = ?",
            (ACCEPTANCE_SQLITE_VFS_PROBE_ID,),
        ).fetchone() != (ACCEPTANCE_SQLITE_VFS_MARKER,):
            raise AssertionError(
                "SQLite reacquired write was not visible in-transaction"
            )
        second.rollback()
        if (
            second.execute(
                f"SELECT COUNT(*) FROM {ACCEPTANCE_SQLITE_VFS_TABLE} "
                "WHERE probe_id = ?",
                (ACCEPTANCE_SQLITE_VFS_PROBE_ID,),
            ).fetchone()[0]
            != 0
        ):
            raise AssertionError("SQLite reacquired rollback left a committed marker")
        reopened = sqlite3.connect(str(database), timeout=0.25)
        reopened.execute("SELECT name FROM sqlite_schema").fetchall()
        if (
            reopened.execute(
                f"SELECT COUNT(*) FROM {ACCEPTANCE_SQLITE_VFS_TABLE} "
                "WHERE probe_id = ?",
                (ACCEPTANCE_SQLITE_VFS_PROBE_ID,),
            ).fetchone()[0]
            != 0
        ):
            raise AssertionError("SQLite reopen observed a committed probe marker")
        if not journal.is_file():
            raise AssertionError(
                "persistent SQLite journal disappeared during acceptance"
            )
    except sqlite3.Error as error:
        raise AcceptanceBlockedError(
            "disposable SQLite VFS probe could not complete under the Trading account"
        ) from error
    except OSError as error:
        raise AcceptanceBlockedError(
            "disposable SQLite VFS probe files could not be inspected"
        ) from error
    finally:
        if reopened is not None:
            reopened.close()
        if second is not None:
            if second.in_transaction:
                second.rollback()
            second.close()
        if first is not None and first.in_transaction:
            first.rollback()
        if first is not None:
            first.close()
    return AcceptanceEvidence(
        phase=AcceptancePhase.SQLITE_WINDOWS_VFS,
        status=AcceptanceEvidenceStatus.PASS,
        account_classification="standard-trading-non-admin",
        scenario_names=(
            "ordinary-python-sqlite3-read-write-open",
            "configure-helper-succeeds",
            "foreign-keys-on",
            "journal-mode-persist",
            "synchronous-full",
            "administrator-precreated-probe-table",
            "real-main-database-insert-visible-in-transaction",
            "persistent-journal-written-during-transaction",
            "second-connection-observes-real-locking",
            "rollback-removes-probe-marker",
            "reacquire-write-and-rollback-succeed",
            "reopen-proves-no-committed-probe-marker",
            "persistent-journal-remains-present",
        ),
        bootstrap_digest=verification.bootstrap_digest,
        trading_sid=trading_sid,
    )


def _run_reparse_and_substitution_phase() -> NoReturn:
    _require_windows_acceptance()
    if not is_current_token_elevated() or not is_current_token_administrator():
        raise AcceptanceBlockedError(
            "reparse acceptance requires an elevated administrator maintenance session"
        )
    if os.environ.get(ACCEPTANCE_MAINTENANCE_ENV) != "1":
        raise AcceptanceBlockedError(
            f"{ACCEPTANCE_MAINTENANCE_ENV}=1 and a disposable authority-tree "
            "maintenance window are required"
        )
    raise AcceptanceBlockedError(
        "reparse phase requires the documented disposable maintenance "
        "procedure; pytest does not mutate the fixed authority tree"
    )


def _run_cross_session_global_mutex_phase() -> NoReturn:
    raise AcceptanceBlockedError(
        "cross-session mutex evidence requires two independently launched "
        "Windows sessions and is never generated by this pytest process"
    )


def run_acceptance_phase(phase: AcceptancePhase) -> AcceptanceEvidence:
    """Run one phase only; manual phases can return BLOCKED but never fake PASS."""

    runners: dict[AcceptancePhase, Callable[[], AcceptanceEvidence]] = {
        AcceptancePhase.ADMINISTRATOR_FIXED_ROOT: _run_administrator_fixed_root_phase,
        AcceptancePhase.TRADING_ALLOW_DENY: _run_trading_allow_deny_phase,
        AcceptancePhase.SQLITE_WINDOWS_VFS: _run_sqlite_windows_vfs_phase,
        AcceptancePhase.REPARSE_AND_SUBSTITUTION: _run_reparse_and_substitution_phase,
        AcceptancePhase.CROSS_SESSION_GLOBAL_MUTEX: (
            _run_cross_session_global_mutex_phase
        ),
    }
    return runners[phase]()


def _execute_selected_phase(expected: AcceptancePhase) -> None:
    _selected_phase_or_skip(expected)
    try:
        evidence = run_acceptance_phase(expected)
    except AcceptanceBlockedError as error:
        blocked = AcceptanceEvidence(
            phase=expected,
            status=AcceptanceEvidenceStatus.BLOCKED,
            account_classification="unverified",
            scenario_names=("external-prerequisite-blocked",),
        )
        print(json.dumps(blocked.to_dict(), sort_keys=True))
        pytest.skip(f"BLOCKED prerequisite: {error}")
    except WindowsAuthorityError as error:
        pytest.fail(f"{expected.name} phase failed: {type(error).__name__}")
    print(json.dumps(evidence.to_dict(), sort_keys=True))


def test_acceptance_administrator_fixed_root_phase() -> None:
    _execute_selected_phase(AcceptancePhase.ADMINISTRATOR_FIXED_ROOT)


def test_acceptance_trading_allow_deny_phase() -> None:
    _execute_selected_phase(AcceptancePhase.TRADING_ALLOW_DENY)


def test_acceptance_sqlite_windows_vfs_phase() -> None:
    _execute_selected_phase(AcceptancePhase.SQLITE_WINDOWS_VFS)


def test_acceptance_reparse_and_substitution_phase() -> None:
    _execute_selected_phase(AcceptancePhase.REPARSE_AND_SUBSTITUTION)


def test_acceptance_cross_session_global_mutex_phase() -> None:
    _execute_selected_phase(AcceptancePhase.CROSS_SESSION_GLOBAL_MUTEX)


def test_acceptance_phase_tests_skip_without_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ACCEPTANCE_OPT_IN_ENV, raising=False)
    monkeypatch.delenv(ACCEPTANCE_PHASE_ENV, raising=False)
    with pytest.raises(pytest.skip.Exception):
        _selected_phase_or_skip(AcceptancePhase.ADMINISTRATOR_FIXED_ROOT)


def test_acceptance_opt_in_without_phase_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ACCEPTANCE_OPT_IN_ENV, "1")
    monkeypatch.delenv(ACCEPTANCE_PHASE_ENV, raising=False)
    with pytest.raises(AcceptanceConfigurationError, match="must select"):
        select_acceptance_phase()


def test_acceptance_unknown_phase_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ACCEPTANCE_OPT_IN_ENV, "1")
    monkeypatch.setenv(ACCEPTANCE_PHASE_ENV, "not-a-phase")
    with pytest.raises(AcceptanceConfigurationError, match="unknown"):
        select_acceptance_phase()


def test_administrator_phase_cannot_satisfy_trading_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ACCEPTANCE_OPT_IN_ENV, "1")
    monkeypatch.setenv(
        ACCEPTANCE_PHASE_ENV,
        AcceptancePhase.ADMINISTRATOR_FIXED_ROOT.value,
    )
    assert select_acceptance_phase() is AcceptancePhase.ADMINISTRATOR_FIXED_ROOT
    with pytest.raises(pytest.skip.Exception):
        _selected_phase_or_skip(AcceptancePhase.TRADING_ALLOW_DENY)


def test_trading_phase_rejects_administrator_token() -> None:
    with pytest.raises(AcceptanceBlockedError, match="rejects administrator"):
        require_trading_phase_facts(
            current_sid="S-1-5-21-100-200-300-400",
            expected_sid="S-1-5-21-100-200-300-400",
            token_is_elevated=True,
            token_is_administrator=True,
        )


def test_administrator_phase_rejects_non_admin_token() -> None:
    with pytest.raises(AcceptanceBlockedError, match="elevated administrator"):
        require_administrator_phase_facts(
            token_is_elevated=False,
            token_is_administrator=False,
        )


def test_wrong_trading_sid_reaches_signed_sid_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The negative matrix keeps signed bytes intact through signature verification."""

    import trading_bot.runtime.windows_authority as authority

    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=1,
        machine_authority_id="87654321-4321-8765-cba9-876543210987",
        authority_epoch_id="12345678-1234-5678-9abc-def012345678",
        signing_key_id="test/v1",
        approved_account_sid="S-1-5-21-100-200-300-400",
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        output_root=str(PRODUCTION_AUTHORITY_PATHS.capture_output),
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="0" * 64,
    )
    public_key = b"\x04" + b"\x01" * 32 + b"\x02" * 32
    registry = PinnedBootstrapKeyRegistry((PinnedBootstrapKey("test/v1", public_key),))
    signature = b"s" * 64
    verified_inputs: list[tuple[bytes, bytes, bytes]] = []
    monkeypatch.setattr(authority, "_require_windows", lambda: None)
    monkeypatch.setattr(
        authority,
        "_cng_verify_p256_sha256",
        lambda key, data, signed: verified_inputs.append((key, data, signed)),
    )

    with pytest.raises(AuthorityPrincipalError):
        validate_bootstrap_installation(
            bootstrap.canonical_bytes(),
            signature,
            trading_sid="S-1-5-21-100-200-300-401",
            key_registry=registry,
        )

    assert verified_inputs == [
        (public_key, bootstrap.canonical_bytes(), signature),
    ]


def test_trading_phase_validates_fixed_objects_before_capability_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    module = sys.modules[__name__]

    class FakeConnection:
        def execute(self, statement: str) -> FakeConnection:
            assert statement == "SELECT name FROM sqlite_schema"
            events.append("sqlite-open")
            return self

        def fetchall(self) -> list[object]:
            return []

        def close(self) -> None:
            events.append("sqlite-close")

    monkeypatch.setattr(
        module,
        "_require_trading_context",
        lambda: (
            SimpleNamespace(bootstrap_digest="digest"),
            "S-1-5-21-100-200-300-400",
        ),
    )

    def record_validation(
        path: str | PureWindowsPath,
        role: str,
        kind: AuthorityObjectKind,
        trading_sid: str,
    ) -> None:
        del path, kind, trading_sid
        events.append(role)

    monkeypatch.setattr(
        module, "_validate_fixed_object_for_capability", record_validation
    )
    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda _path, timeout: events.append("sqlite-connect") or FakeConnection(),
    )
    monkeypatch.setattr(
        module,
        "_create_capture_artifact",
        lambda _path: events.append("capture-artifact"),
    )
    monkeypatch.setattr(
        module, "_expect_access_denied", lambda _scenario, _operation: None
    )

    _run_trading_allow_deny_phase()

    assert events[:5] == [
        "root",
        "capture-output",
        "database",
        "journal",
        "sqlite-connect",
    ]
    assert events[5:] == ["sqlite-open", "sqlite-close", "capture-artifact"]


def test_phase_evidence_identifies_exact_phase() -> None:
    evidence = AcceptanceEvidence(
        phase=AcceptancePhase.TRADING_ALLOW_DENY,
        status=AcceptanceEvidenceStatus.PASS,
        account_classification="standard-trading-non-admin",
        scenario_names=("bootstrap-readable",),
    )
    rendered = evidence.to_dict()
    assert rendered["phase_id"] == "TRADING_ALLOW_DENY"
    assert rendered["status"] == "PASS"


def test_evidence_cannot_represent_complete_milestone_acceptance() -> None:
    evidence = AcceptanceEvidence(
        phase=AcceptancePhase.ADMINISTRATOR_FIXED_ROOT,
        status=AcceptanceEvidenceStatus.PASS,
        account_classification="elevated-administrator",
        scenario_names=("fixed-root",),
    )
    rendered = evidence.to_dict()
    assert "milestone_a_accepted" not in rendered
    assert "complete_acceptance" not in rendered
    assert "all_phases_passed" not in rendered


def test_cross_session_evidence_cannot_be_generated_by_this_process() -> None:
    with pytest.raises(AcceptanceBlockedError, match="two independently launched"):
        run_acceptance_phase(AcceptancePhase.CROSS_SESSION_GLOBAL_MUTEX)


def test_one_phase_does_not_clear_external_acceptance_gates() -> None:
    evidence = AcceptanceEvidence(
        phase=AcceptancePhase.ADMINISTRATOR_FIXED_ROOT,
        status=AcceptanceEvidenceStatus.PASS,
        account_classification="elevated-administrator",
        scenario_names=("fixed-root",),
    )
    missing = missing_required_phase_ids((evidence,))
    assert missing == (
        AcceptancePhase.TRADING_ALLOW_DENY,
        AcceptancePhase.SQLITE_WINDOWS_VFS,
        AcceptancePhase.REPARSE_AND_SUBSTITUTION,
        AcceptancePhase.CROSS_SESSION_GLOBAL_MUTEX,
    )
