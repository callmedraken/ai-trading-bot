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
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

import pytest

from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    BootstrapError,
    WindowsAuthorityError,
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
    path: object,
    role: str,
    trading_sid: str,
) -> bytes:
    """Read trust material only from the handle whose path/security was checked."""

    validate_fixed_parent_chain(path, trading_sid=trading_sid)  # type: ignore[arg-type]
    policy = authority_security_policy(role, trading_sid)
    with open_authority_object(path, AuthorityObjectKind.FILE) as handle:  # type: ignore[arg-type]
        inspection = inspect_open_authority_object(
            handle, path, AuthorityObjectKind.FILE
        )
        require_security_policy(inspection, policy)
        return read_open_authority_file(handle)


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
) -> str:
    try:
        operation()
    except (BootstrapError, WindowsAuthorityError, ValueError):
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
        )
    )
    wrong_sid_base, wrong_sid_number = trading_sid.rsplit("-", 1)
    scenarios.append(
        _require_bootstrap_rejection(
            "wrong-trading-sid",
            lambda: validate_bootstrap_installation(
                _bootstrap_variant(
                    bootstrap,
                    approved_account_sid=(
                        f"{wrong_sid_base}-{int(wrong_sid_number) + 1}"
                    ),
                ),
                signature,
                trading_sid=trading_sid,
            ),
        )
    )
    scenarios.append(
        _require_bootstrap_rejection(
            "wrong-fixed-path",
            lambda: validate_bootstrap_installation(
                _bootstrap_variant(
                    bootstrap,
                    database_path=str(PRODUCTION_AUTHORITY_PATHS.database) + ".wrong",
                ),
                signature,
                trading_sid=trading_sid,
            ),
        )
    )
    scenarios.append(
        _require_bootstrap_rejection(
            "wrong-provider-operation",
            lambda: validate_bootstrap_installation(
                _bootstrap_variant(
                    bootstrap,
                    provider_id="unapproved-provider",
                    permitted_provider_operation="unapproved-operation",
                ),
                signature,
                trading_sid=trading_sid,
            ),
        )
    )
    scenarios.append(
        _require_bootstrap_rejection(
            "unsupported-policy",
            lambda: validate_bootstrap_installation(
                _bootstrap_variant(
                    bootstrap,
                    authority_policy_version="authority-policy/v999",
                ),
                signature,
                trading_sid=trading_sid,
            ),
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
    bootstrap_bytes = _read_verified_fixed_file(
        PRODUCTION_AUTHORITY_PATHS.bootstrap,
        "bootstrap",
        resolve_current_token_sid(),
    )
    signature_bytes = _read_verified_fixed_file(
        PRODUCTION_AUTHORITY_PATHS.signature,
        "signature",
        resolve_current_token_sid(),
    )
    verification = verify_bootstrap_signature(
        bootstrap_bytes,
        signature_bytes,
        key_registry=PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    )
    current_sid = resolve_current_token_sid()
    require_trading_phase_facts(
        current_sid=current_sid,
        expected_sid=verification.bootstrap.approved_account_sid,
        token_is_elevated=is_current_token_elevated(),
        token_is_administrator=is_current_token_administrator(),
    )
    return verification, current_sid


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
    value = int(getattr(handle, "value", handle) or 0)
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
    database = Path(str(PRODUCTION_AUTHORITY_PATHS.database))
    journal = Path(str(PRODUCTION_AUTHORITY_PATHS.journal))
    if not database.is_file() or not journal.is_file():
        raise AcceptanceBlockedError(
            "Trading acceptance requires the disposable administrator-"
            "provisioned DB/journal pair"
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
    database = Path(str(PRODUCTION_AUTHORITY_PATHS.database))
    journal = Path(str(PRODUCTION_AUTHORITY_PATHS.journal))
    if os.environ.get(ACCEPTANCE_MAINTENANCE_ENV) != "1":
        raise AcceptanceBlockedError(
            f"{ACCEPTANCE_MAINTENANCE_ENV}=1 is required for disposable "
            "SQLite write/lock acceptance"
        )
    if not database.is_file() or not journal.is_file():
        raise AcceptanceBlockedError("disposable acceptance DB/journal pair is absent")
    first = sqlite3.connect(str(database), timeout=0.25)
    second: sqlite3.Connection | None = None
    reopened: sqlite3.Connection | None = None
    try:
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
        first.execute("BEGIN IMMEDIATE")
        second = sqlite3.connect(str(database), timeout=0.0)
        second.execute("PRAGMA busy_timeout = 0")
        with pytest.raises(sqlite3.OperationalError) as locked:
            second.execute("BEGIN IMMEDIATE")
        if "locked" not in str(locked.value).lower():
            raise AssertionError(
                "second SQLite connection did not observe real locking"
            )
        first.rollback()
        second.execute("BEGIN IMMEDIATE")
        second.rollback()
        reopened = sqlite3.connect(str(database), timeout=0.25)
        reopened.execute("SELECT name FROM sqlite_schema").fetchall()
        if not journal.is_file():
            raise AssertionError(
                "persistent SQLite journal disappeared during acceptance"
            )
    finally:
        if reopened is not None:
            reopened.close()
        if second is not None:
            if second.in_transaction:
                second.rollback()
            second.close()
        if first.in_transaction:
            first.rollback()
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
            "begin-immediate-succeeds",
            "second-connection-observes-real-locking",
            "rollback-release-and-reacquire-succeed",
            "reopen-succeeds",
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
