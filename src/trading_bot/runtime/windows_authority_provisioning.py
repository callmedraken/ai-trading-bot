"""Administrator-only fixed-layout validation and provisioning workflow."""

from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath

from trading_bot.runtime import windows_authority_validation as authority_validation
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    AuthorityRecoveryRequiredError,
    BootstrapVerification,
    PinnedBootstrapKeyRegistry,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
    WindowsNativeError,
    parse_bootstrap_bytes,
)
from trading_bot.runtime.windows_authority_mutex import (
    validate_lifecycle_mutex_security_descriptor,
)
from trading_bot.runtime.windows_authority_schema import (
    ReleaseManifestEvidence,
    SqliteAuthorityBuildEvidence,
    load_approved_release_manifest,
    load_approved_sqlite_authority_build,
)
from trading_bot.runtime.windows_authority_security import (
    ERROR_FILE_NOT_FOUND,
    ERROR_PATH_NOT_FOUND,
    AuthorityObjectKind,
    SecurityPolicy,
    authority_security_policy,
    create_authority_directory,
    create_unpublished_authority_file,
    inspect_fixed_authority_object,
    inspect_open_authority_object,
    inspect_open_authority_provisioning_temp_file,
    open_authority_object,
    publish_unpublished_authority_file,
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
from trading_bot.runtime.windows_authority_validation import (
    InstalledAuthorityValidation,
    ProvisioningEvidence,
    ProvisioningState,
    validate_bootstrap_installation,
    validate_installed_database_complete,
)


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
    return validate_bootstrap_installation(
        bootstrap_bytes,
        signature_bytes,
        trading_sid=trading_sid,
        key_registry=key_registry,
    )


def _read_installed_material(trading_sid: str) -> tuple[bytes, bytes]:
    """Retain the low-level administrator helper for existing diagnostics/tests."""

    validate_fixed_parent_chain(
        PRODUCTION_AUTHORITY_PATHS.bootstrap,
        trading_sid=trading_sid,
    )

    def read_verified(path: PureWindowsPath, role: str) -> bytes:
        policy = authority_security_policy(role, trading_sid)
        with open_authority_object(path, AuthorityObjectKind.FILE) as handle:
            inspection = inspect_open_authority_object(
                handle, path, AuthorityObjectKind.FILE
            )
            require_security_policy(inspection, policy)
            return read_open_authority_file(handle)

    return (
        read_verified(PRODUCTION_AUTHORITY_PATHS.bootstrap, "bootstrap"),
        read_verified(PRODUCTION_AUTHORITY_PATHS.signature, "signature"),
    )


def read_installed_authority_material(trading_sid: str) -> tuple[bytes, bytes]:
    """Read installed material through the dedicated validation module."""

    return authority_validation.read_installed_authority_material(trading_sid)


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


def _validate_existing_authority_root(trading_sid: str) -> bool:
    """Validate the parent and existing root before probing any child path."""

    root = PRODUCTION_AUTHORITY_PATHS.root
    validate_fixed_parent_chain(root, trading_sid=trading_sid)
    try:
        root_handle = open_authority_object(root, AuthorityObjectKind.DIRECTORY)
    except WindowsNativeError as error:
        if error.error_code in {ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND}:
            return False
        raise
    with root_handle as handle:
        inspection = inspect_open_authority_object(
            handle, root, AuthorityObjectKind.DIRECTORY
        )
        require_security_policy(
            inspection, authority_security_policy("root", trading_sid)
        )
    return True


def _existing_fixed_objects(trading_sid: str) -> dict[PureWindowsPath, bool]:
    """Discover children only after the fixed parent and root are trusted."""

    root_present = _validate_existing_authority_root(trading_sid)
    existing: dict[PureWindowsPath, bool] = {
        PRODUCTION_AUTHORITY_PATHS.root: root_present
    }
    for path in PRODUCTION_AUTHORITY_PATHS.protected_objects[1:]:
        existing[path] = root_present and os.path.lexists(str(path))
    return existing


def _validate_existing_objects(
    trading_sid: str,
    existing: dict[PureWindowsPath, bool],
) -> None:
    """Reject any pre-existing object that is not already exactly reviewed."""

    roles = {
        PRODUCTION_AUTHORITY_PATHS.bootstrap: "bootstrap",
        PRODUCTION_AUTHORITY_PATHS.signature: "signature",
        PRODUCTION_AUTHORITY_PATHS.capture_output: "capture-output",
        PRODUCTION_AUTHORITY_PATHS.backup: "backup",
        PRODUCTION_AUTHORITY_PATHS.database: "database",
        PRODUCTION_AUTHORITY_PATHS.journal: "journal",
    }
    for path, present in existing.items():
        if path == PRODUCTION_AUTHORITY_PATHS.root or not present:
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
    vfs: str | None = None,
) -> SqliteDatabaseState:
    if not database_present and not journal_present:
        return SqliteDatabaseState.NOT_PRESENT
    if database_present != journal_present:
        raise WindowsAuthorityError(
            "pre-created authority database and persistent journal must be paired"
        )
    if vfs is None:
        raise WindowsAuthorityError(
            "approved SQLite VFS evidence is required before opening "
            "the authority database"
        )
    connection = open_read_only_sqlite_connection(
        PRODUCTION_AUTHORITY_PATHS.database, vfs=vfs
    )
    try:
        evidence = validate_installed_sqlite_prerequisites(
            connection,
            database_path=PRODUCTION_AUTHORITY_PATHS.database,
            journal_path=PRODUCTION_AUTHORITY_PATHS.journal,
        )
    finally:
        connection.close()
    return evidence.database_state


def _validate_installed_database_complete(
    database_present: bool,
    journal_present: bool,
    *,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    release_manifest: ReleaseManifestEvidence | None,
    sqlite_build: SqliteAuthorityBuildEvidence | None,
) -> authority_validation.InstalledDatabaseValidation:
    """Compatibility wrapper over the centralized complete validator."""

    return validate_installed_database_complete(
        database_present,
        journal_present,
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap_digest,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
    )


def _require_reserved_temporary_objects_absent() -> None:
    """Fail closed when either reserved install name needs manual recovery."""

    for path in PRODUCTION_AUTHORITY_PATHS.provisioning_temporary_objects:
        try:
            handle = open_authority_object(path, AuthorityObjectKind.FILE)
        except WindowsNativeError as error:
            if error.error_code in {ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND}:
                continue
            raise AuthorityRecoveryRequiredError(
                "reserved authority trust-material temporary requires manual recovery"
            ) from error
        else:
            handle.close()
            raise AuthorityRecoveryRequiredError(
                "reserved authority trust-material temporary requires manual recovery"
            )


def _validate_exact_file(
    path: PureWindowsPath,
    data: bytes,
    policy: SecurityPolicy,
) -> None:
    with open_authority_object(path, AuthorityObjectKind.FILE) as handle:
        inspection = inspect_open_authority_object(
            handle, path, AuthorityObjectKind.FILE
        )
        require_security_policy(inspection, policy)
        if read_open_authority_file(handle) != data:
            raise WindowsAuthorityError(
                "existing trust material does not exactly match staging"
            )


def _validate_installed_authority(
    *,
    key_registry: PinnedBootstrapKeyRegistry,
    release_manifest: ReleaseManifestEvidence | None = None,
    sqlite_build: SqliteAuthorityBuildEvidence | None = None,
) -> InstalledAuthorityValidation:
    """Compatibility wrapper over the centralized installed validator."""

    if (
        key_registry is PRODUCTION_PINNED_BOOTSTRAP_KEYS
        and release_manifest is None
        and sqlite_build is None
    ):
        return authority_validation.validate_installed_authority_complete()
    return authority_validation.validate_installed_authority_complete_for_test(
        key_registry=key_registry,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
    )


def validate_installed_authority_complete() -> InstalledAuthorityValidation:
    """Prove installed authority through the centralized validation boundary."""

    return _validate_installed_authority(
        key_registry=PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    )


def validate_installed_authority() -> ProvisioningEvidence:
    """Validate the fixed install while preserving the CLI evidence contract."""

    return validate_installed_authority_complete().provisioning


def validate_installed_authority_complete_for_test(
    *,
    key_registry: PinnedBootstrapKeyRegistry,
    release_manifest: ReleaseManifestEvidence | None = None,
    sqlite_build: SqliteAuthorityBuildEvidence | None = None,
) -> InstalledAuthorityValidation:
    """Explicit test boundary for complete installed validation injection."""

    return authority_validation.validate_installed_authority_complete_for_test(
        key_registry=key_registry,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
    )


def validate_installed_authority_for_test(
    *,
    key_registry: PinnedBootstrapKeyRegistry,
    release_manifest: ReleaseManifestEvidence | None = None,
    sqlite_build: SqliteAuthorityBuildEvidence | None = None,
) -> ProvisioningEvidence:
    """Explicit test-only boundary for disposable trust-evidence injection."""

    return authority_validation.validate_installed_authority_complete_for_test(
        key_registry=key_registry,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
    ).provisioning


def _install_exact_file(
    destination: PureWindowsPath,
    data: bytes,
    policy: SecurityPolicy,
    existing: bool,
) -> None:
    if existing:
        _validate_exact_file(destination, data, policy)
        return
    temporary_by_destination = {
        PRODUCTION_AUTHORITY_PATHS.bootstrap: (
            PRODUCTION_AUTHORITY_PATHS.bootstrap_temporary
        ),
        PRODUCTION_AUTHORITY_PATHS.signature: (
            PRODUCTION_AUTHORITY_PATHS.signature_temporary
        ),
    }
    try:
        temporary = temporary_by_destination[destination]
    except KeyError as error:
        raise WindowsAuthorityError(
            "only fixed bootstrap and signature files can be published"
        ) from error
    try:
        with create_unpublished_authority_file(temporary, data, policy) as handle:
            inspection = inspect_open_authority_provisioning_temp_file(
                handle, temporary
            )
            require_security_policy(inspection, policy)
            if read_open_authority_file(handle) != data:
                raise WindowsAuthorityError(
                    "unpublished trust material does not exactly match staging"
                )
            publish_unpublished_authority_file(handle, destination)
        _validate_exact_file(destination, data, policy)
    except WindowsAuthorityError:
        raise
    except OSError as error:
        raise WindowsAuthorityError("trust material could not be installed") from error


def _provision_authority(
    *,
    bootstrap_source: Path,
    signature_source: Path,
    key_registry: PinnedBootstrapKeyRegistry,
    release_manifest: ReleaseManifestEvidence | None = None,
    sqlite_build: SqliteAuthorityBuildEvidence | None = None,
) -> ProvisioningEvidence:
    """Provision the fixed authority tree with explicitly selected trust inputs."""

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
    existing = _existing_fixed_objects(trading_sid)
    _validate_existing_objects(trading_sid, existing)
    # Reject a corrupt pre-created database before any trust material mutation.
    selected_build = sqlite_build
    if (
        existing[PRODUCTION_AUTHORITY_PATHS.database]
        or existing[PRODUCTION_AUTHORITY_PATHS.journal]
    ):
        selected_build = selected_build or load_approved_sqlite_authority_build()
        database_state = _validate_database_if_present(
            existing[PRODUCTION_AUTHORITY_PATHS.database],
            existing[PRODUCTION_AUTHORITY_PATHS.journal],
            vfs=selected_build.vfs,
        )
    else:
        database_state = _validate_database_if_present(
            existing[PRODUCTION_AUTHORITY_PATHS.database],
            existing[PRODUCTION_AUTHORITY_PATHS.journal],
        )
    if database_state is SqliteDatabaseState.INITIALIZED_SUPPORTED:
        selected_release = release_manifest or load_approved_release_manifest()
        if selected_build is None:
            raise WindowsAuthorityError(
                "approved SQLite VFS evidence is required for initialized authority"
            )
        complete = _validate_installed_database_complete(
            True,
            True,
            bootstrap=verification.bootstrap,
            bootstrap_digest=verification.bootstrap_digest,
            release_manifest=selected_release,
            sqlite_build=selected_build,
        )
        if (
            complete.database_state is not SqliteDatabaseState.INITIALIZED_SUPPORTED
            or complete.production_evidence is None
        ):
            raise WindowsAuthorityError(
                "initialized authority was not completely reconciled"
            )
    try:
        if existing[PRODUCTION_AUTHORITY_PATHS.root]:
            _require_reserved_temporary_objects_absent()
        for path, role in (
            (PRODUCTION_AUTHORITY_PATHS.root, "root"),
            (PRODUCTION_AUTHORITY_PATHS.capture_output, "capture-output"),
            (PRODUCTION_AUTHORITY_PATHS.backup, "backup"),
        ):
            if not existing[path]:
                create_authority_directory(
                    path, authority_security_policy(role, trading_sid)
                )
            if path == PRODUCTION_AUTHORITY_PATHS.root and not existing[path]:
                _validate_existing_authority_root(trading_sid)
                _require_reserved_temporary_objects_absent()
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

    # Existing objects were validated above and are never repaired. Absent
    # trust files were published only after complete temporary-file validation.
    inspected, database_present, journal_present = _inspect_tree(trading_sid)
    if database_present or journal_present:
        selected_build = selected_build or load_approved_sqlite_authority_build()
        complete = _validate_installed_database_complete(
            database_present,
            journal_present,
            bootstrap=verification.bootstrap,
            bootstrap_digest=verification.bootstrap_digest,
            release_manifest=release_manifest,
            sqlite_build=selected_build,
        )
        database_state = complete.database_state
        production_evidence = complete.production_evidence
        if database_state is SqliteDatabaseState.INITIALIZED_SUPPORTED and (
            production_evidence is None
        ):
            raise WindowsAuthorityError(
                "initialized authority was not completely reconciled"
            )
    else:
        database_state = _validate_database_if_present(
            database_present,
            journal_present,
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


def provision_authority(
    *,
    bootstrap_source: Path,
    signature_source: Path,
) -> ProvisioningEvidence:
    """Provision the fixed authority tree with production-pinned trust evidence."""

    return _provision_authority(
        bootstrap_source=bootstrap_source,
        signature_source=signature_source,
        key_registry=PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    )


def provision_authority_for_test(
    *,
    bootstrap_source: Path,
    signature_source: Path,
    key_registry: PinnedBootstrapKeyRegistry,
    release_manifest: ReleaseManifestEvidence | None = None,
    sqlite_build: SqliteAuthorityBuildEvidence | None = None,
) -> ProvisioningEvidence:
    """Explicit test-only boundary for disposable trust-evidence injection."""

    return _provision_authority(
        bootstrap_source=bootstrap_source,
        signature_source=signature_source,
        key_registry=key_registry,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
    )
