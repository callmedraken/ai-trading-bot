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
import struct
import sys
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
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
    AuthorityObjectError,
    AuthorityPathError,
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
    require_fixed_authority_tree_path,
    verify_bootstrap_signature,
)
from trading_bot.runtime.windows_authority_provisioning import (
    validate_bootstrap_installation,
    validate_installed_authority,
)
from trading_bot.runtime.windows_authority_security import (
    CREATE_NEW,
    DELETE,
    ERROR_ACCESS_DENIED,
    ERROR_FILE_NOT_FOUND,
    ERROR_PATH_NOT_FOUND,
    FILE_ATTRIBUTE_NORMAL,
    FILE_FLAG_BACKUP_SEMANTICS,
    FILE_FLAG_OPEN_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    FILE_READ_DATA,
    FILE_SHARE_DELETE,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    GENERIC_WRITE,
    INVALID_HANDLE_VALUE,
    OPEN_EXISTING,
    READ_CONTROL,
    WRITE_DAC,
    WRITE_OWNER,
    AuthorityObjectKind,
    SecurityPolicy,
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
ACCEPTANCE_REPARSE_ROOT = Path(r"F:\AITradingBot\AuthorityAcceptance\Reparse")
ACCEPTANCE_REPARSE_PARENT = Path(r"F:\AITradingBot\AuthorityAcceptance")


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

    def __init__(
        self,
        message: str,
        *,
        scenario_names: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.scenario_names = scenario_names


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


FSCTL_SET_REPARSE_POINT = 0x000900A4
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003


@dataclass(frozen=True, slots=True)
class _AcceptanceInspectionTarget:
    """One acceptance-only object and the rejection expected from its inspection."""

    open_path: str | Path
    expected_path: Path
    kind: AuthorityObjectKind
    expected_reason: str | None
    policy: SecurityPolicy | None = None


@dataclass(slots=True)
class _OwnedAcceptanceScenario:
    """Track only objects created by one disposable hostile substitution."""

    directory: Path
    files: list[Path]
    links: list[Path]
    directories: list[Path]

    @classmethod
    def create(cls, root: Path, name: str) -> _OwnedAcceptanceScenario:
        directory = root / name
        try:
            directory.mkdir()
        except OSError as error:
            raise AcceptanceBlockedError(
                "acceptance scenario directory could not be created"
            ) from error
        return cls(directory, [], [], [directory])

    def new_file(self, name: str, contents: bytes = b"acceptance\n") -> Path:
        path = self.directory / name
        try:
            with path.open("xb") as stream:
                self.files.append(path)
                stream.write(contents)
        except OSError as error:
            if path.exists() and path not in self.files:
                self.files.append(path)
            raise AcceptanceBlockedError(
                "acceptance scenario file could not be created"
            ) from error
        return path

    def new_directory(self, name: str) -> Path:
        path = self.directory / name
        try:
            path.mkdir()
        except OSError as error:
            raise AcceptanceBlockedError(
                "acceptance scenario directory object could not be created"
            ) from error
        self.directories.append(path)
        return path

    def cleanup(self) -> None:
        """Remove known entries without recursive deletion or repair."""

        try:
            for path in reversed(self.links):
                path.unlink()
            for path in reversed(self.files):
                path.unlink()
            for path in reversed(self.directories):
                path.rmdir()
        except OSError as error:
            raise AcceptanceBlockedError(
                "acceptance scenario cleanup failed; remove only the named "
                "scenario-owned entries after inspection"
            ) from error


@dataclass(frozen=True, slots=True)
class _ReparseScenario:
    name: str
    build: Callable[[_OwnedAcceptanceScenario], _AcceptanceInspectionTarget]


def _windows_path_is_under(path: str | PureWindowsPath, root: Path) -> bool:
    candidate = PureWindowsPath(str(path))
    base = PureWindowsPath(str(root))
    if ".." in candidate.parts:
        return False
    try:
        candidate.relative_to(base)
    except ValueError:
        return False
    return True


def _reject_production_acceptance_path(path: str | PureWindowsPath) -> None:
    candidate = PureWindowsPath(str(path))
    production = PureWindowsPath(str(PRODUCTION_AUTHORITY_PATHS.root))
    if candidate == production or production in candidate.parents:
        raise AcceptanceBlockedError(
            "acceptance-native inspection cannot target the production authority tree"
        )


def _require_acceptance_expected_path(path: str | PureWindowsPath) -> None:
    _reject_production_acceptance_path(path)
    if PureWindowsPath(str(path)) == PureWindowsPath(str(ACCEPTANCE_REPARSE_PARENT)):
        return
    if not _windows_path_is_under(path, ACCEPTANCE_REPARSE_ROOT):
        raise AcceptanceBlockedError(
            "reparse inspection expected path is outside the fixed acceptance root"
        )


def _require_acceptance_open_path(path: str | PureWindowsPath) -> None:
    _reject_production_acceptance_path(path)
    if PureWindowsPath(str(path)) == PureWindowsPath(str(ACCEPTANCE_REPARSE_PARENT)):
        return
    raw = str(path)
    folded = raw.casefold()
    if _windows_path_is_under(path, ACCEPTANCE_REPARSE_ROOT):
        return
    unc_root = (
        "\\\\localhost\\f$" + str(PureWindowsPath(str(ACCEPTANCE_REPARSE_ROOT)))[2:]
    )
    if folded.startswith(unc_root.casefold() + "\\"):
        return
    if folded == r"\\.\nul":
        return
    raise AcceptanceBlockedError(
        "reparse inspection open path is not an approved acceptance-only candidate"
    )


def _acceptance_create_file_function(kernel32: object) -> object:
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
    return create


@contextmanager
def _open_acceptance_native_object(
    path: str | PureWindowsPath,
    expected_path: str | PureWindowsPath,
    kind: AuthorityObjectKind,
) -> Iterator[int]:
    """Open one disposable candidate directly, with no production path helper."""

    if os.name != "nt":
        raise AcceptanceBlockedError("native Windows inspection is unavailable")
    if type(kind) is not AuthorityObjectKind:
        raise AcceptanceBlockedError("acceptance object kind must be explicit")
    _require_acceptance_expected_path(expected_path)
    _require_acceptance_open_path(path)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = _acceptance_create_file_function(kernel32)
    flags = FILE_FLAG_OPEN_REPARSE_POINT
    if kind is AuthorityObjectKind.DIRECTORY:
        flags |= FILE_FLAG_BACKUP_SEMANTICS
    handle = create(
        str(path),
        FILE_READ_DATA | FILE_READ_ATTRIBUTES | READ_CONTROL,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        flags,
        None,
    )
    value = _native_handle_value(handle)
    if value in (0, INVALID_HANDLE_VALUE):
        raise AcceptanceBlockedError(
            "acceptance hostile-substitution candidate could not be opened"
        )
    close = kernel32.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    try:
        yield value
    finally:
        if not close(value):
            raise AcceptanceBlockedError(
                "acceptance hostile-substitution handle could not be closed"
            )


def _inspect_acceptance_target(target: _AcceptanceInspectionTarget) -> object:
    """Inspect through the direct acceptance handle and preserve validator errors."""

    with _open_acceptance_native_object(
        target.open_path, target.expected_path, target.kind
    ) as handle:
        inspection = inspect_open_authority_object(
            handle, target.expected_path, target.kind
        )
        if target.policy is not None:
            require_security_policy(inspection, target.policy)
        return inspection


def _rejection_matches(error: WindowsAuthorityError, expected_reason: str) -> bool:
    message = str(error).casefold()
    if expected_reason == "reparse":
        return "reparse point" in message
    if expected_reason == "final-path":
        return "final path" in message
    if expected_reason == "object-kind":
        return "object type" in message or "fixed layout" in message
    if expected_reason == "security":
        return "security" in message or "owner" in message or "dacl" in message
    if expected_reason == "non-local":
        return any(
            marker in message
            for marker in ("unc", "device", "namespace", "globalroot", "volume")
        )
    return False


def _expect_acceptance_rejection(
    scenario: _ReparseScenario,
    target: _AcceptanceInspectionTarget,
) -> None:
    """Require the reviewed validator to reject for this scenario's exact reason."""

    try:
        _inspect_acceptance_target(target)
    except AcceptanceBlockedError:
        raise
    except WindowsAuthorityError as error:
        if target.expected_reason is not None and _rejection_matches(
            error, target.expected_reason
        ):
            return
        raise AcceptanceBlockedError(
            f"{scenario.name} did not reach its reviewed rejection"
        ) from error
    except OSError as error:
        raise AcceptanceBlockedError(
            f"{scenario.name} native inspection could not complete"
        ) from error
    raise AssertionError(
        f"acceptance hostile substitution unexpectedly passed: {scenario.name}"
    )


def _expect_clean_acceptance_control(
    scenario: _ReparseScenario,
    target: _AcceptanceInspectionTarget,
) -> None:
    """Confirm a clean ordinary object is not mistaken for hostile evidence."""

    try:
        _inspect_acceptance_target(target)
    except AcceptanceBlockedError:
        raise
    except WindowsAuthorityError as error:
        raise AcceptanceBlockedError(
            f"{scenario.name} clean control was unexpectedly rejected"
        ) from error
    except OSError as error:
        raise AcceptanceBlockedError(
            f"{scenario.name} clean control could not complete"
        ) from error


def _create_acceptance_symbolic_link(
    scenario: _OwnedAcceptanceScenario,
    link: Path,
    target: Path,
    *,
    target_is_directory: bool,
) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_link = kernel32.CreateSymbolicLinkW
    create_link.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong]
    create_link.restype = ctypes.c_ubyte
    flags = 1 if target_is_directory else 0
    if not create_link(str(link), str(target), flags):
        raise AcceptanceBlockedError(
            "symbolic-link construction is unavailable on this Windows host"
        )
    scenario.links.append(link)


def _create_acceptance_mount_point(
    scenario: _OwnedAcceptanceScenario,
    link: Path,
    target: Path,
) -> None:
    """Create a disposable IO_REPARSE_TAG_MOUNT_POINT directory reparse."""

    scenario.new_directory(link.name)
    substitute = ("\\??\\" + str(target)).encode("utf-16-le")
    printed = str(target).encode("utf-16-le")
    path_buffer = substitute + b"\x00\x00" + printed + b"\x00\x00"
    payload = (
        struct.pack(
            "<IHHHHHH",
            IO_REPARSE_TAG_MOUNT_POINT,
            8 + len(path_buffer),
            0,
            0,
            len(substitute),
            len(substitute) + 2,
            len(printed),
        )
        + path_buffer
    )
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = _acceptance_create_file_function(kernel32)
    handle = create(
        str(link),
        GENERIC_WRITE | READ_CONTROL,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    value = _native_handle_value(handle)
    if value in (0, INVALID_HANDLE_VALUE):
        raise AcceptanceBlockedError(
            "mount-point reparse construction is unavailable on this host"
        )
    close = kernel32.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    device_io = kernel32.DeviceIoControl
    device_io.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_void_p,
    ]
    device_io.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(payload)
    returned = ctypes.c_ulong()
    try:
        if not device_io(
            value,
            FSCTL_SET_REPARSE_POINT,
            ctypes.byref(buffer),
            len(payload),
            None,
            0,
            ctypes.byref(returned),
            None,
        ):
            raise AcceptanceBlockedError(
                "mount-point reparse construction is unavailable on this host"
            )
    finally:
        if not close(value):
            raise AcceptanceBlockedError(
                "mount-point reparse construction handle could not be closed"
            )


def _unc_acceptance_path(path: Path) -> str:
    local = str(PureWindowsPath(str(path)))
    return r"\\localhost\F$" + local[2:]


def _build_symbolic_link_scenario(
    scenario: _OwnedAcceptanceScenario,
) -> _AcceptanceInspectionTarget:
    target = scenario.new_file("symbolic-link-target.bin")
    link = scenario.directory / "symbolic-link-substitution.bin"
    _create_acceptance_symbolic_link(scenario, link, target, target_is_directory=False)
    return _AcceptanceInspectionTarget(link, link, AuthorityObjectKind.FILE, "reparse")


def _build_junction_scenario(
    scenario: _OwnedAcceptanceScenario,
) -> _AcceptanceInspectionTarget:
    target = scenario.new_directory("junction-target")
    link = scenario.directory / "junction-substitution"
    _create_acceptance_mount_point(scenario, link, target)
    return _AcceptanceInspectionTarget(
        link, link, AuthorityObjectKind.DIRECTORY, "reparse"
    )


def _build_mount_point_scenario(
    scenario: _OwnedAcceptanceScenario,
) -> _AcceptanceInspectionTarget:
    target = scenario.new_directory("mount-point-target")
    link = scenario.directory / "mount-point-substitution"
    _create_acceptance_mount_point(scenario, link, target)
    return _AcceptanceInspectionTarget(
        link, link, AuthorityObjectKind.DIRECTORY, "reparse"
    )


def _build_wrong_final_path_scenario(
    scenario: _OwnedAcceptanceScenario,
) -> _AcceptanceInspectionTarget:
    actual = scenario.new_file("wrong-final-object.bin")
    expected = scenario.directory / "reviewed-final-object.bin"
    return _AcceptanceInspectionTarget(
        actual, expected, AuthorityObjectKind.FILE, "final-path"
    )


def _build_unc_scenario(
    scenario: _OwnedAcceptanceScenario,
) -> _AcceptanceInspectionTarget:
    local = scenario.new_file("unc-substitution-target.bin")
    return _AcceptanceInspectionTarget(
        _unc_acceptance_path(local), local, AuthorityObjectKind.FILE, "non-local"
    )


def _build_device_scenario(
    scenario: _OwnedAcceptanceScenario,
) -> _AcceptanceInspectionTarget:
    expected = scenario.new_file("device-substitution-target.bin")
    return _AcceptanceInspectionTarget(
        r"\\.\NUL", expected, AuthorityObjectKind.FILE, "non-local"
    )


def _build_wrong_object_kind_scenario(
    scenario: _OwnedAcceptanceScenario,
) -> _AcceptanceInspectionTarget:
    actual = scenario.new_file("wrong-kind-object.bin")
    return _AcceptanceInspectionTarget(
        actual, actual, AuthorityObjectKind.DIRECTORY, "object-kind"
    )


def _build_security_scenario(
    scenario: _OwnedAcceptanceScenario,
) -> _AcceptanceInspectionTarget:
    actual = scenario.new_file("wrong-security-object.bin")
    return _AcceptanceInspectionTarget(
        actual,
        actual,
        AuthorityObjectKind.FILE,
        "security",
        SecurityPolicy(
            owner_sid="S-1-5-21-999-999-999-999",
            aces=(),
            dacl_protected=True,
        ),
    )


def _build_clean_control_scenario(
    scenario: _OwnedAcceptanceScenario,
) -> _AcceptanceInspectionTarget:
    actual = scenario.new_file("ordinary-clean-object.bin")
    return _AcceptanceInspectionTarget(actual, actual, AuthorityObjectKind.FILE, None)


_REPARSE_SCENARIOS = (
    _ReparseScenario("symbolic-link-substitution", _build_symbolic_link_scenario),
    _ReparseScenario(
        "directory-junction-reparse-substitution", _build_junction_scenario
    ),
    _ReparseScenario("mount-point-reparse-substitution", _build_mount_point_scenario),
    _ReparseScenario("wrong-final-path-substitution", _build_wrong_final_path_scenario),
    _ReparseScenario("unc-substitution", _build_unc_scenario),
    _ReparseScenario("device-substitution", _build_device_scenario),
    _ReparseScenario("wrong-object-kind", _build_wrong_object_kind_scenario),
    _ReparseScenario("wrong-security", _build_security_scenario),
)
_REQUIRED_REPARSE_SCENARIO_NAMES = (
    "symbolic-link-substitution",
    "directory-junction-reparse-substitution",
    "mount-point-reparse-substitution",
    "wrong-final-path-substitution",
    "unc-substitution",
    "device-substitution",
    "wrong-object-kind",
    "wrong-security",
)
_CLEAN_CONTROL_SCENARIO = _ReparseScenario(
    "ordinary-clean-non-reparse-control", _build_clean_control_scenario
)


def _create_reparse_acceptance_root() -> Path:
    """Create a new root only; never repair or recursively remove stale state."""

    root = Path(str(ACCEPTANCE_REPARSE_ROOT))
    if os.path.lexists(root):
        raise AcceptanceBlockedError(
            "reparse acceptance root already exists; inspect stale state and "
            "remove only known acceptance objects before retrying",
            scenario_names=("stale-disposable-state",),
        )
    parent = Path(str(ACCEPTANCE_REPARSE_PARENT))
    parent_target = _AcceptanceInspectionTarget(
        parent, parent, AuthorityObjectKind.DIRECTORY, None
    )
    try:
        _inspect_acceptance_target(parent_target)
    except AcceptanceBlockedError as error:
        raise AcceptanceBlockedError(
            "acceptance parent native open or inspection is blocked",
            scenario_names=("acceptance-parent-validation-blocked",),
        ) from error
    except (WindowsAuthorityError, OSError) as error:
        raise AcceptanceBlockedError(
            "acceptance parent final-path, type, reparse, volume, or filesystem "
            "validation is blocked",
            scenario_names=("acceptance-parent-prerequisite-blocked",),
        ) from error
    try:
        root.mkdir()
    except OSError as error:
        raise AcceptanceBlockedError(
            "reparse acceptance root could not be created",
            scenario_names=("acceptance-root-creation-blocked",),
        ) from error

    root_target = _AcceptanceInspectionTarget(
        root, root, AuthorityObjectKind.DIRECTORY, None
    )
    try:
        _inspect_acceptance_target(root_target)
    except AcceptanceBlockedError as error:
        raise AcceptanceBlockedError(
            "new acceptance root native open or inspection is blocked",
            scenario_names=("acceptance-root-validation-blocked",),
        ) from error
    except (WindowsAuthorityError, OSError) as error:
        raise AcceptanceBlockedError(
            "new acceptance root final-path, type, reparse, volume, or "
            "filesystem validation is blocked",
            scenario_names=("acceptance-root-prerequisite-blocked",),
        ) from error
    return root


def _cleanup_reparse_acceptance_root(root: Path) -> None:
    try:
        root.rmdir()
    except OSError as error:
        raise AcceptanceBlockedError(
            "reparse acceptance root cleanup failed; remove only the empty "
            "acceptance root after inspecting scenario-owned state"
        ) from error


def test_reparse_acceptance_root_cannot_enter_production_path_contract() -> None:
    assert str(ACCEPTANCE_REPARSE_ROOT) not in {
        str(path) for path in PRODUCTION_AUTHORITY_PATHS.protected_objects
    }
    with pytest.raises(AuthorityPathError):
        require_fixed_authority_tree_path(ACCEPTANCE_REPARSE_ROOT)
    with pytest.raises(AuthorityPathError):
        open_authority_object(ACCEPTANCE_REPARSE_ROOT, AuthorityObjectKind.DIRECTORY)
    with pytest.raises(AcceptanceBlockedError):
        _require_acceptance_expected_path(PRODUCTION_AUTHORITY_PATHS.root)
    with pytest.raises(AcceptanceBlockedError):
        _require_acceptance_open_path(PRODUCTION_AUTHORITY_PATHS.root)


def test_acceptance_native_open_uses_no_follow_reparse_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []
    closed: list[object] = []

    class FakeCreateFile:
        argtypes: object
        restype: object

        def __call__(self, *args: object) -> object:
            calls.append(args)
            return ctypes.c_void_p(123)

    class FakeCloseHandle:
        argtypes: object
        restype: object

        def __call__(self, value: object) -> bool:
            closed.append(value)
            return True

    class FakeKernel32:
        CreateFileW = FakeCreateFile()
        CloseHandle = FakeCloseHandle()

    module = sys.modules[__name__]
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda name, use_last_error: FakeKernel32(),
        raising=False,
    )
    target = Path(r"F:\AITradingBot\AuthorityAcceptance\Reparse\scenario")
    monkeypatch.setattr(
        module,
        "open_authority_object",
        lambda *args, **kwargs: pytest.fail("production open helper was used"),
    )

    with _open_acceptance_native_object(target, target, AuthorityObjectKind.DIRECTORY):
        pass

    assert calls[0][5] & FILE_FLAG_OPEN_REPARSE_POINT
    assert calls[0][5] & FILE_FLAG_BACKUP_SEMANTICS
    assert closed == [123]


@pytest.mark.parametrize(
    "rejection",
    (
        AuthorityObjectError("authority handle final path is not the fixed target"),
        AuthorityObjectError("authority object is a reparse point"),
        AuthorityObjectError("authority object type does not match the fixed layout"),
        WindowsAuthorityError(
            "authority object security does not match reviewed policy"
        ),
    ),
)
def test_acceptance_inspection_preserves_exact_validator_rejections(
    monkeypatch: pytest.MonkeyPatch,
    rejection: WindowsAuthorityError,
) -> None:
    module = sys.modules[__name__]
    monkeypatch.setattr(os, "name", "nt")

    class FakeCreateFile:
        argtypes: object
        restype: object

        def __call__(self, *args: object) -> object:
            return ctypes.c_void_p(123)

    class FakeCloseHandle:
        argtypes: object
        restype: object

        def __call__(self, value: object) -> bool:
            return True

    class FakeKernel32:
        CreateFileW = FakeCreateFile()
        CloseHandle = FakeCloseHandle()

    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda name, use_last_error: FakeKernel32(),
        raising=False,
    )

    def reject(*args: object, **kwargs: object) -> NoReturn:
        raise rejection

    monkeypatch.setattr(module, "inspect_open_authority_object", reject)
    target_path = Path(
        r"F:\AITradingBot\AuthorityAcceptance\Reparse\scenario\target.bin"
    )
    target = _AcceptanceInspectionTarget(
        target_path, target_path, AuthorityObjectKind.FILE, "reparse"
    )

    with pytest.raises(type(rejection), match=str(rejection)):
        _inspect_acceptance_target(target)


def test_unrelated_native_rejection_blocks_instead_of_passing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unrelated = WindowsNativeError("GetVolumeInformationW", 1234)
    monkeypatch.setattr(
        sys.modules[__name__],
        "_inspect_acceptance_target",
        lambda target: (_ for _ in ()).throw(unrelated),
    )
    scenario = _ReparseScenario(
        "symbolic-link-substitution", _build_symbolic_link_scenario
    )
    target = _AcceptanceInspectionTarget(
        Path(r"F:\AITradingBot\AuthorityAcceptance\Reparse\x"),
        Path(r"F:\AITradingBot\AuthorityAcceptance\Reparse\x"),
        AuthorityObjectKind.FILE,
        "reparse",
    )
    with pytest.raises(AcceptanceBlockedError, match="did not reach"):
        _expect_acceptance_rejection(scenario, target)


def test_successful_hostile_substitution_is_a_hard_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys.modules[__name__], "_inspect_acceptance_target", lambda target: object()
    )
    scenario = _ReparseScenario(
        "symbolic-link-substitution", _build_symbolic_link_scenario
    )
    target = _AcceptanceInspectionTarget(
        Path(r"F:\AITradingBot\AuthorityAcceptance\Reparse\x"),
        Path(r"F:\AITradingBot\AuthorityAcceptance\Reparse\x"),
        AuthorityObjectKind.FILE,
        "reparse",
    )
    with pytest.raises(AssertionError, match="unexpectedly passed"):
        _expect_acceptance_rejection(scenario, target)


def test_stale_reparse_acceptance_root_blocks_without_repair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "Reparse"
    root.mkdir()
    marker = root / "unexpected.txt"
    marker.write_text("leave me", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "ACCEPTANCE_REPARSE_ROOT", root)

    with pytest.raises(AcceptanceBlockedError, match="already exists"):
        _create_reparse_acceptance_root()
    assert marker.read_text(encoding="utf-8") == "leave me"


def test_reparse_acceptance_parent_reparse_blocks_before_root_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "Reparse"
    parent = root.parent
    monkeypatch.setattr(sys.modules[__name__], "ACCEPTANCE_REPARSE_ROOT", root)
    monkeypatch.setattr(sys.modules[__name__], "ACCEPTANCE_REPARSE_PARENT", parent)
    inspected: list[Path] = []

    def reject_parent(target: _AcceptanceInspectionTarget) -> object:
        inspected.append(target.expected_path)
        raise AuthorityObjectError("authority object is a reparse point")

    monkeypatch.setattr(
        sys.modules[__name__], "_inspect_acceptance_target", reject_parent
    )

    with pytest.raises(AcceptanceBlockedError, match="parent"):
        _create_reparse_acceptance_root()
    assert inspected == [parent]
    assert not root.exists()


def test_reparse_acceptance_parent_final_path_mismatch_blocks_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "Reparse"
    monkeypatch.setattr(sys.modules[__name__], "ACCEPTANCE_REPARSE_ROOT", root)
    monkeypatch.setattr(sys.modules[__name__], "ACCEPTANCE_REPARSE_PARENT", root.parent)

    def reject_parent(target: _AcceptanceInspectionTarget) -> object:
        raise AuthorityObjectError(
            "authority handle final path is not the fixed target"
        )

    monkeypatch.setattr(
        sys.modules[__name__], "_inspect_acceptance_target", reject_parent
    )

    with pytest.raises(AcceptanceBlockedError, match="parent"):
        _create_reparse_acceptance_root()
    assert not root.exists()


def test_new_reparse_root_is_reopened_before_use(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "Reparse"
    monkeypatch.setattr(sys.modules[__name__], "ACCEPTANCE_REPARSE_ROOT", root)
    monkeypatch.setattr(sys.modules[__name__], "ACCEPTANCE_REPARSE_PARENT", root.parent)
    inspected: list[Path] = []

    def record_inspection(target: _AcceptanceInspectionTarget) -> object:
        inspected.append(target.expected_path)
        return object()

    monkeypatch.setattr(
        sys.modules[__name__], "_inspect_acceptance_target", record_inspection
    )

    created = _create_reparse_acceptance_root()
    try:
        assert created == root
        assert inspected == [root.parent, root]
    finally:
        created.rmdir()


@pytest.mark.parametrize(
    "rejection",
    (
        "authority object is a reparse point",
        "authority handle final path is not the fixed target",
        "authority object type does not match the fixed layout",
        "authority is not on the approved local NTFS volume",
    ),
)
def test_new_reparse_root_rejection_blocks_before_scenarios(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rejection: str,
) -> None:
    root = tmp_path / "Reparse"
    monkeypatch.setattr(sys.modules[__name__], "ACCEPTANCE_REPARSE_ROOT", root)
    monkeypatch.setattr(sys.modules[__name__], "ACCEPTANCE_REPARSE_PARENT", root.parent)
    inspected: list[Path] = []

    def reject_root(target: _AcceptanceInspectionTarget) -> object:
        inspected.append(target.expected_path)
        if target.expected_path == root:
            raise AuthorityObjectError(rejection)
        return object()

    monkeypatch.setattr(
        sys.modules[__name__], "_inspect_acceptance_target", reject_root
    )

    with pytest.raises(AcceptanceBlockedError, match="root"):
        _create_reparse_acceptance_root()
    assert inspected == [root.parent, root]
    assert root.exists()
    root.rmdir()


def test_scenario_cleanup_is_limited_to_owned_objects(tmp_path: Path) -> None:
    root = tmp_path / "Reparse"
    root.mkdir()
    scenario = _OwnedAcceptanceScenario.create(root, "scenario")
    owned = scenario.new_file("owned.bin")
    unexpected = scenario.directory / "unexpected.bin"
    unexpected.write_bytes(b"leave me")

    with pytest.raises(AcceptanceBlockedError, match="cleanup failed"):
        scenario.cleanup()
    assert not owned.exists()
    assert unexpected.exists()
    assert scenario.directory.exists()


def test_scenario_cleanup_failure_blocks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "Reparse"
    root.mkdir()
    scenario = _OwnedAcceptanceScenario.create(root, "scenario")
    scenario.new_file("owned.bin")

    def fail_unlink(self: Path) -> None:
        raise OSError("cleanup failure")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(AcceptanceBlockedError, match="cleanup failed"):
        scenario.cleanup()


def test_clean_non_reparse_control_cannot_satisfy_hostile_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys.modules[__name__], "_inspect_acceptance_target", lambda target: object()
    )
    scenario = _ReparseScenario(
        "ordinary-clean-non-reparse-control", _build_clean_control_scenario
    )
    target = _AcceptanceInspectionTarget(
        Path(r"F:\AITradingBot\AuthorityAcceptance\Reparse\x"),
        Path(r"F:\AITradingBot\AuthorityAcceptance\Reparse\x"),
        AuthorityObjectKind.FILE,
        "reparse",
    )
    with pytest.raises(AssertionError, match="unexpectedly passed"):
        _expect_acceptance_rejection(scenario, target)


def test_reparse_phase_cannot_pass_from_clean_objects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = sys.modules[__name__]
    root = tmp_path / "Reparse"
    root.mkdir()
    monkeypatch.setattr(module, "_require_windows_acceptance", lambda: None)
    monkeypatch.setattr(module, "is_current_token_elevated", lambda: True)
    monkeypatch.setattr(module, "is_current_token_administrator", lambda: True)
    monkeypatch.setenv(ACCEPTANCE_MAINTENANCE_ENV, "1")
    monkeypatch.setattr(module, "_create_reparse_acceptance_root", lambda: root)
    monkeypatch.setattr(module, "_inspect_acceptance_target", lambda target: object())

    def clean_builder(state: _OwnedAcceptanceScenario) -> _AcceptanceInspectionTarget:
        target = state.directory / "clean-object.bin"
        return _AcceptanceInspectionTarget(
            target, target, AuthorityObjectKind.FILE, "reparse"
        )

    monkeypatch.setattr(
        module,
        "_REPARSE_SCENARIOS",
        tuple(
            _ReparseScenario(name, clean_builder)
            for name in _REQUIRED_REPARSE_SCENARIO_NAMES
        ),
    )
    monkeypatch.setattr(
        module,
        "_CLEAN_CONTROL_SCENARIO",
        _ReparseScenario("ordinary-clean-non-reparse-control", clean_builder),
    )

    with pytest.raises(AssertionError, match="unexpectedly passed"):
        _run_reparse_and_substitution_phase()
    assert not root.exists()


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


def _install_native_root_create_probe_kernel(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    *,
    handle: object,
    error_code: int,
    close_result: bool = True,
) -> tuple[list[tuple[object, ...]], list[object]]:
    create_calls: list[tuple[object, ...]] = []
    closed: list[object] = []

    class FakeCreateFile:
        argtypes: object
        restype: object

        def __call__(self, *args: object) -> object:
            create_calls.append(args)
            value = _native_handle_value(handle)
            if value not in (0, INVALID_HANDLE_VALUE):
                Path(args[0]).touch(exist_ok=False)  # type: ignore[arg-type]
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

    module = sys.modules[__name__]
    monkeypatch.setattr(
        module, "PRODUCTION_AUTHORITY_PATHS", SimpleNamespace(root=root)
    )
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
    return create_calls, closed


def test_native_root_create_probe_counts_only_access_denied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_calls, closed = _install_native_root_create_probe_kernel(
        monkeypatch,
        tmp_path,
        handle=ctypes.c_void_p(-1),
        error_code=ERROR_ACCESS_DENIED,
    )

    assert _native_root_create_probe() is False
    assert closed == []
    assert len(create_calls) == 1
    assert create_calls[0][1] == GENERIC_WRITE
    assert create_calls[0][2] == FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
    assert create_calls[0][4] == CREATE_NEW
    assert create_calls[0][5] == FILE_ATTRIBUTE_NORMAL


def test_native_root_create_probe_blocks_unrelated_native_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_native_root_create_probe_kernel(
        monkeypatch,
        tmp_path,
        handle=ctypes.c_void_p(-1),
        error_code=ERROR_FILE_NOT_FOUND,
    )

    with pytest.raises(AcceptanceBlockedError, match="unrelated Windows failure"):
        _native_root_create_probe()


def test_native_root_create_probe_success_fails_policy_after_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_calls, closed = _install_native_root_create_probe_kernel(
        monkeypatch,
        tmp_path,
        handle=ctypes.c_void_p(123),
        error_code=0,
    )

    with pytest.raises(pytest.fail.Exception, match="authority-root-arbitrary-create"):
        _expect_access_denied(
            "authority-root-arbitrary-create", _native_root_create_probe
        )

    assert closed == [123]
    assert not Path(create_calls[0][0]).exists()  # type: ignore[arg-type]


def test_native_root_create_probe_cleanup_failure_blocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    create_calls, closed = _install_native_root_create_probe_kernel(
        monkeypatch,
        tmp_path,
        handle=ctypes.c_void_p(123),
        error_code=0,
    )

    def fail_unlink(self: Path) -> None:
        raise OSError("cleanup failure")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(AcceptanceBlockedError, match="could not be cleaned"):
        _native_root_create_probe()

    assert closed == [123]
    assert Path(create_calls[0][0]).is_file()  # type: ignore[arg-type]


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


def _native_root_create_probe() -> bool:
    """Probe authority-root file creation with exact native error evidence."""

    if os.name != "nt":
        raise AcceptanceBlockedError(
            "native Windows root-create probing is unavailable"
        )
    probe = Path(str(PRODUCTION_AUTHORITY_PATHS.root)) / (
        f".windows-authority-root-probe-{os.getpid()}-{uuid.uuid4().hex}"
    )
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
    handle = create(
        str(probe),
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    value = _native_handle_value(handle)
    if value in (0, INVALID_HANDLE_VALUE):
        error_code = ctypes.get_last_error()
        if error_code == ERROR_ACCESS_DENIED:
            return False
        raise AcceptanceBlockedError(
            "native authority-root create probe returned an unrelated Windows failure"
        )

    close = kernel32.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    close_failure: AcceptanceBlockedError | None = None
    try:
        if not close(value):
            close_failure = AcceptanceBlockedError(
                "native authority-root create probe handle could not close"
            )
    except Exception as error:
        close_failure = AcceptanceBlockedError(
            "native authority-root create probe handle could not close"
        )
        close_failure.__cause__ = error

    try:
        probe.unlink()
    except OSError as error:
        raise AcceptanceBlockedError(
            "native authority-root create probe artifact could not be cleaned"
        ) from error
    if close_failure is not None:
        raise close_failure
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
    _expect_access_denied("authority-root-arbitrary-create", _native_root_create_probe)
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


def _run_reparse_and_substitution_phase() -> AcceptanceEvidence:
    _require_windows_acceptance()
    require_administrator_phase_facts(
        token_is_elevated=is_current_token_elevated(),
        token_is_administrator=is_current_token_administrator(),
    )
    if os.environ.get(ACCEPTANCE_MAINTENANCE_ENV) != "1":
        raise AcceptanceBlockedError(
            f"{ACCEPTANCE_MAINTENANCE_ENV}=1 and a disposable authority-tree "
            "maintenance window are required"
        )
    if (
        tuple(scenario.name for scenario in _REPARSE_SCENARIOS)
        != _REQUIRED_REPARSE_SCENARIO_NAMES
    ):
        raise AssertionError("reparse phase scenario coverage is incomplete")
    root = _create_reparse_acceptance_root()
    passed: list[str] = []
    blocked: list[str] = []
    try:
        for scenario in _REPARSE_SCENARIOS:
            state: _OwnedAcceptanceScenario | None = None
            try:
                state = _OwnedAcceptanceScenario.create(root, scenario.name)
                target = scenario.build(state)
                _expect_acceptance_rejection(scenario, target)
                passed.append(scenario.name)
            except AcceptanceBlockedError:
                blocked.append(f"{scenario.name}-blocked")
            finally:
                if state is not None:
                    state.cleanup()

        clean_state: _OwnedAcceptanceScenario | None = None
        try:
            clean_state = _OwnedAcceptanceScenario.create(
                root, _CLEAN_CONTROL_SCENARIO.name
            )
            clean_target = _CLEAN_CONTROL_SCENARIO.build(clean_state)
            _expect_clean_acceptance_control(_CLEAN_CONTROL_SCENARIO, clean_target)
            passed.append(_CLEAN_CONTROL_SCENARIO.name)
        except AcceptanceBlockedError:
            blocked.append(f"{_CLEAN_CONTROL_SCENARIO.name}-blocked")
        finally:
            if clean_state is not None:
                clean_state.cleanup()
    finally:
        _cleanup_reparse_acceptance_root(root)

    if blocked:
        raise AcceptanceBlockedError(
            "one or more disposable reparse scenarios were blocked by host "
            "prerequisites",
            scenario_names=tuple(blocked),
        )
    return AcceptanceEvidence(
        phase=AcceptancePhase.REPARSE_AND_SUBSTITUTION,
        status=AcceptanceEvidenceStatus.PASS,
        account_classification="elevated-administrator",
        scenario_names=tuple(passed),
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
            scenario_names=error.scenario_names or ("external-prerequisite-blocked",),
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
        module,
        "_native_root_create_probe",
        lambda: events.append("native-root-create") or False,
    )

    def record_access_denied(scenario: str, operation: Callable[[], object]) -> None:
        if scenario == "authority-root-arbitrary-create":
            assert operation() is False

    monkeypatch.setattr(module, "_expect_access_denied", record_access_denied)

    _run_trading_allow_deny_phase()

    assert events[:5] == [
        "root",
        "capture-output",
        "database",
        "journal",
        "sqlite-connect",
    ]
    assert events[5:] == [
        "sqlite-open",
        "sqlite-close",
        "capture-artifact",
        "native-root-create",
    ]


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
