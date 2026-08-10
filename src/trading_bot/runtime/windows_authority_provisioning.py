"""Administrator-only fixed-layout validation and provisioning workflow."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PureWindowsPath

from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    AuthorityPrincipalError,
    BootstrapVerification,
    PinnedBootstrapKeyRegistry,
    WindowsAuthorityError,
    parse_bootstrap_bytes,
    verify_bootstrap_signature,
)
from trading_bot.runtime.windows_authority_mutex import (
    validate_lifecycle_mutex_security_descriptor,
)
from trading_bot.runtime.windows_authority_security import (
    AuthorityObjectKind,
    SecurityPolicy,
    authority_security_policy,
    create_authority_directory,
    create_authority_file,
    inspect_fixed_authority_object,
    inspect_open_authority_object,
    open_authority_object,
    read_open_authority_file,
    require_administrator_token,
    require_security_policy,
    require_trading_standard_account,
    validate_fixed_parent_chain,
)
from trading_bot.runtime.windows_authority_sqlite import (
    SqliteDatabaseState,
    open_read_only_sqlite_connection,
    validate_installed_sqlite_prerequisites,
)


class ProvisioningState(StrEnum):
    VALIDATED = "VALIDATED"
    PROVISIONED = "PROVISIONED"


@dataclass(frozen=True, slots=True)
class ProvisioningEvidence:
    """Secret-free, stable evidence emitted by the administrator command."""

    state: ProvisioningState
    authority_root: str
    bootstrap_digest: str
    signing_key_id: str
    trading_sid: str
    inspected_objects: tuple[str, ...]
    database_present: bool
    journal_present: bool
    database_initialization: str = "DEFERRED"
    database_state: str = SqliteDatabaseState.NOT_PRESENT.value


def _kind_for(path: PureWindowsPath) -> AuthorityObjectKind:
    return (
        AuthorityObjectKind.DIRECTORY
        if path
        in {
            PRODUCTION_AUTHORITY_PATHS.root,
            PRODUCTION_AUTHORITY_PATHS.capture_output,
            PRODUCTION_AUTHORITY_PATHS.backup,
        }
        else AuthorityObjectKind.FILE
    )


def _verify_material(
    bootstrap_bytes: bytes,
    signature_bytes: bytes,
    *,
    trading_sid: str,
    key_registry: PinnedBootstrapKeyRegistry,
) -> BootstrapVerification:
    verification = verify_bootstrap_signature(
        bootstrap_bytes,
        signature_bytes,
        key_registry=key_registry,
    )
    if verification.bootstrap.approved_account_sid != trading_sid:
        raise AuthorityPrincipalError(
            "resolved Trading SID does not match signed bootstrap"
        )
    return verification


def validate_bootstrap_installation(
    bootstrap_bytes: bytes,
    signature_bytes: bytes,
    *,
    trading_sid: str,
    key_registry: PinnedBootstrapKeyRegistry = PRODUCTION_PINNED_BOOTSTRAP_KEYS,
) -> BootstrapVerification:
    """Validate signed material and the actual resolved SID before filesystem work."""

    return _verify_material(
        bootstrap_bytes,
        signature_bytes,
        trading_sid=trading_sid,
        key_registry=key_registry,
    )


def _read_verified_installed_file(
    path: PureWindowsPath,
    role: str,
    trading_sid: str,
) -> bytes:
    policy = authority_security_policy(role, trading_sid)
    try:
        with open_authority_object(path, AuthorityObjectKind.FILE) as handle:
            inspection = inspect_open_authority_object(
                handle, path, AuthorityObjectKind.FILE
            )
            require_security_policy(inspection, policy)
            return read_open_authority_file(handle)
    except WindowsAuthorityError:
        raise
    except OSError as error:
        raise WindowsAuthorityError(
            "fixed bootstrap trust material could not be read"
        ) from error


def _read_installed_material(trading_sid: str) -> tuple[bytes, bytes]:
    validate_fixed_parent_chain(
        PRODUCTION_AUTHORITY_PATHS.bootstrap,
        trading_sid=trading_sid,
    )
    return (
        _read_verified_installed_file(
            PRODUCTION_AUTHORITY_PATHS.bootstrap,
            "bootstrap",
            trading_sid,
        ),
        _read_verified_installed_file(
            PRODUCTION_AUTHORITY_PATHS.signature,
            "signature",
            trading_sid,
        ),
    )


def _inspect_tree(trading_sid: str) -> tuple[tuple[str, ...], bool, bool]:
    inspected: list[str] = []
    required = (
        (PRODUCTION_AUTHORITY_PATHS.root, "root"),
        (PRODUCTION_AUTHORITY_PATHS.bootstrap, "bootstrap"),
        (PRODUCTION_AUTHORITY_PATHS.signature, "signature"),
        (PRODUCTION_AUTHORITY_PATHS.capture_output, "capture-output"),
        (PRODUCTION_AUTHORITY_PATHS.backup, "backup"),
    )
    for path, role in required:
        inspection = inspect_fixed_authority_object(
            str(path), _kind_for(path), trading_sid=trading_sid
        )
        require_security_policy(
            inspection, authority_security_policy(role, trading_sid)
        )
        inspected.append(role)
    database_present = os.path.lexists(str(PRODUCTION_AUTHORITY_PATHS.database))
    journal_present = os.path.lexists(str(PRODUCTION_AUTHORITY_PATHS.journal))
    for path, role in (
        (PRODUCTION_AUTHORITY_PATHS.database, "database"),
        (PRODUCTION_AUTHORITY_PATHS.journal, "journal"),
    ):
        if os.path.lexists(str(path)):
            inspection = inspect_fixed_authority_object(
                str(path), AuthorityObjectKind.FILE, trading_sid=trading_sid
            )
            require_security_policy(
                inspection, authority_security_policy(role, trading_sid)
            )
            inspected.append(role)
    return tuple(inspected), database_present, journal_present


def _existing_fixed_objects() -> dict[PureWindowsPath, bool]:
    return {
        path: os.path.lexists(str(path))
        for path in PRODUCTION_AUTHORITY_PATHS.protected_objects
    }


def _validate_existing_objects(
    trading_sid: str,
    existing: dict[PureWindowsPath, bool],
) -> None:
    """Reject any pre-existing object that is not already exactly reviewed."""

    roles = {
        PRODUCTION_AUTHORITY_PATHS.root: "root",
        PRODUCTION_AUTHORITY_PATHS.bootstrap: "bootstrap",
        PRODUCTION_AUTHORITY_PATHS.signature: "signature",
        PRODUCTION_AUTHORITY_PATHS.capture_output: "capture-output",
        PRODUCTION_AUTHORITY_PATHS.backup: "backup",
        PRODUCTION_AUTHORITY_PATHS.database: "database",
        PRODUCTION_AUTHORITY_PATHS.journal: "journal",
    }
    for path, present in existing.items():
        if not present:
            continue
        inspection = inspect_fixed_authority_object(
            str(path), _kind_for(path), trading_sid=trading_sid
        )
        require_security_policy(
            inspection, authority_security_policy(roles[path], trading_sid)
        )


def _validate_database_if_present(
    database_present: bool,
    journal_present: bool,
    *,
    verification: BootstrapVerification | None = None,
) -> SqliteDatabaseState:
    if not database_present and not journal_present:
        return SqliteDatabaseState.NOT_PRESENT
    if database_present != journal_present:
        raise WindowsAuthorityError(
            "pre-created authority database and persistent journal must be paired"
        )
    connection = open_read_only_sqlite_connection(PRODUCTION_AUTHORITY_PATHS.database)
    try:
        evidence = validate_installed_sqlite_prerequisites(
            connection,
            database_path=PRODUCTION_AUTHORITY_PATHS.database,
            journal_path=PRODUCTION_AUTHORITY_PATHS.journal,
            verification=verification,
        )
    finally:
        connection.close()
    return evidence.database_state


def validate_installed_authority(
    *,
    key_registry: PinnedBootstrapKeyRegistry = PRODUCTION_PINNED_BOOTSTRAP_KEYS,
) -> ProvisioningEvidence:
    """Validate the fixed install and existing DB/journal without mutating it."""

    require_administrator_token()
    trading_sid = require_trading_standard_account()
    bootstrap_bytes, signature_bytes = _read_installed_material(trading_sid)
    verification = _verify_material(
        bootstrap_bytes,
        signature_bytes,
        trading_sid=trading_sid,
        key_registry=key_registry,
    )
    validate_lifecycle_mutex_security_descriptor(trading_sid)
    inspected, database_present, journal_present = _inspect_tree(trading_sid)
    database_state = _validate_database_if_present(
        database_present,
        journal_present,
        verification=verification,
    )
    return ProvisioningEvidence(
        ProvisioningState.VALIDATED,
        str(PRODUCTION_AUTHORITY_PATHS.root),
        verification.bootstrap_digest,
        verification.signing_key_id,
        trading_sid,
        inspected,
        database_present,
        journal_present,
        database_state=database_state.value,
    )


def _install_exact_file(
    destination: PureWindowsPath,
    data: bytes,
    policy: SecurityPolicy,
    existing: bool,
) -> None:
    if existing:
        with open_authority_object(destination, AuthorityObjectKind.FILE) as handle:
            inspect_open_authority_object(handle, destination, AuthorityObjectKind.FILE)
            if read_open_authority_file(handle) != data:
                raise WindowsAuthorityError(
                    "existing trust material does not exactly match staging"
                )
        return
    try:
        create_authority_file(destination, data, policy)
    except WindowsAuthorityError:
        raise
    except OSError as error:
        raise WindowsAuthorityError("trust material could not be installed") from error


def provision_authority(
    *,
    bootstrap_source: Path,
    signature_source: Path,
    key_registry: PinnedBootstrapKeyRegistry = PRODUCTION_PINNED_BOOTSTRAP_KEYS,
) -> ProvisioningEvidence:
    """Provision only the fixed authority tree after all trust checks pass."""

    require_administrator_token()
    try:
        bootstrap_bytes = bootstrap_source.read_bytes()
        signature_bytes = signature_source.read_bytes()
    except OSError as error:
        raise WindowsAuthorityError(
            "staging trust material could not be read"
        ) from error
    # Parse and verify before creating or changing any final object.
    parse_bootstrap_bytes(bootstrap_bytes)
    trading_sid = require_trading_standard_account()
    verification = _verify_material(
        bootstrap_bytes,
        signature_bytes,
        trading_sid=trading_sid,
        key_registry=key_registry,
    )
    validate_lifecycle_mutex_security_descriptor(trading_sid)
    existing = _existing_fixed_objects()
    validate_fixed_parent_chain(PRODUCTION_AUTHORITY_PATHS.root)
    _validate_existing_objects(trading_sid, existing)
    # Reject a corrupt pre-created database before any trust material mutation.
    _validate_database_if_present(
        existing[PRODUCTION_AUTHORITY_PATHS.database],
        existing[PRODUCTION_AUTHORITY_PATHS.journal],
        verification=verification,
    )
    try:
        for path, role in (
            (PRODUCTION_AUTHORITY_PATHS.root, "root"),
            (PRODUCTION_AUTHORITY_PATHS.capture_output, "capture-output"),
            (PRODUCTION_AUTHORITY_PATHS.backup, "backup"),
        ):
            if not existing[path]:
                create_authority_directory(
                    path, authority_security_policy(role, trading_sid)
                )
        _install_exact_file(
            PRODUCTION_AUTHORITY_PATHS.bootstrap,
            bootstrap_bytes,
            authority_security_policy("bootstrap", trading_sid),
            existing[PRODUCTION_AUTHORITY_PATHS.bootstrap],
        )
        _install_exact_file(
            PRODUCTION_AUTHORITY_PATHS.signature,
            signature_bytes,
            authority_security_policy("signature", trading_sid),
            existing[PRODUCTION_AUTHORITY_PATHS.signature],
        )
    except WindowsAuthorityError:
        raise
    except OSError as error:
        raise WindowsAuthorityError(
            "fixed authority objects could not be established"
        ) from error

    # New objects receive the reviewed descriptor atomically at creation;
    # existing objects were validated above and are never repaired.
    inspected, database_present, journal_present = _inspect_tree(trading_sid)
    database_state = _validate_database_if_present(
        database_present,
        journal_present,
        verification=verification,
    )
    return ProvisioningEvidence(
        ProvisioningState.PROVISIONED,
        str(PRODUCTION_AUTHORITY_PATHS.root),
        verification.bootstrap_digest,
        verification.signing_key_id,
        trading_sid,
        inspected,
        database_present,
        journal_present,
        database_state=database_state.value,
    )
