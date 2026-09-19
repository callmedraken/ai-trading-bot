"""Administrator evidence and Trading-runtime authority boundaries.

Administrator provisioning remains responsible for mutation and complete
installed conformance. The dedicated Trading runtime owns the separate
read-only executable-authority acquisition path.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath

from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    AuthorityPrincipalError,
    BootstrapVerification,
    PinnedBootstrapKeyRegistry,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
    WindowsNativeError,
    verify_bootstrap_signature,
)
from trading_bot.runtime.windows_authority_mutex import (
    validate_lifecycle_mutex_security_descriptor,
)
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    ProductionAuthorityEvidence,
    ReleaseManifestEvidence,
    SqliteAuthorityBuildEvidence,
    load_approved_release_manifest,
    load_approved_sqlite_authority_build,
    validate_production_authority_database_connection,
)
from trading_bot.runtime.windows_authority_security import (
    ERROR_FILE_NOT_FOUND,
    ERROR_PATH_NOT_FOUND,
    AuthorityObjectKind,
    authority_security_policy,
    inspect_fixed_authority_object,
    inspect_open_authority_object,
    is_current_token_administrator,
    is_current_token_elevated,
    open_authority_object,
    read_open_authority_file,
    require_administrator_token,
    require_security_policy,
    require_trading_standard_account,
    resolve_current_token_sid,
    validate_fixed_parent_chain,
)
from trading_bot.runtime.windows_authority_sqlite import (
    SqliteDatabaseState,
    open_read_only_sqlite_connection,
    validate_installed_sqlite_prerequisites,
)


class _CapabilityIssuer:
    """Private process-local provenance marker for capability issuance."""


_PRODUCTION_CAPABILITY_ISSUER = _CapabilityIssuer()
_TEST_CAPABILITY_ISSUER = _CapabilityIssuer()
_CAPABILITY_FIELDS = (
    "authority_epoch_id",
    "machine_authority_id",
    "bootstrap_schema",
    "bootstrap_generation",
    "signing_key_id",
    "approved_account_sid",
    "provider_id",
    "permitted_provider_operation",
    "authority_policy_version",
    "claim_policy_version",
    "bootstrap_digest",
    "database_identity_digest",
    "database_path",
    "schema_id",
    "schema_version",
    "schema_digest",
    "metadata_digest",
    "migration_id",
    "release_manifest_digest",
    "sqlite_build_manifest_digest",
)


class ValidatedProductionAuthority:
    """Immutable, secret-free proof of one executable fixed authority.

    The constructor is intentionally issuer-token gated.  The object is
    process-local provenance, not a serialized authority or a substitute for
    future Architecture-77 one-shot capabilities.
    """

    __slots__ = (*_CAPABILITY_FIELDS, "_provenance")

    def __init__(self, *args: object, **kwargs: object) -> None:
        issuer = kwargs.pop("_issuer", None)
        if (
            issuer
            not in (
                _PRODUCTION_CAPABILITY_ISSUER,
                _TEST_CAPABILITY_ISSUER,
            )
            or args
        ):
            raise TypeError(
                "ValidatedProductionAuthority is issued by the validation module"
            )
        if set(kwargs) != set(_CAPABILITY_FIELDS):
            raise TypeError("validated authority fields are not exact")
        object.__setattr__(self, "_provenance", issuer)
        for field in _CAPABILITY_FIELDS:
            object.__setattr__(self, field, kwargs[field])

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ValidatedProductionAuthority is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("ValidatedProductionAuthority is immutable")

    def __repr__(self) -> str:
        identity = ", ".join(
            f"{field}={getattr(self, field)!r}"
            for field in (
                "authority_epoch_id",
                "machine_authority_id",
                "bootstrap_generation",
                "database_path",
                "schema_id",
                "schema_version",
            )
        )
        return f"ValidatedProductionAuthority({identity})"

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return self._provenance is other._provenance and all(
            getattr(self, field) == getattr(other, field)
            for field in _CAPABILITY_FIELDS
        )

    def __hash__(self) -> int:
        return hash(
            (
                self._provenance,
                tuple(getattr(self, field) for field in _CAPABILITY_FIELDS),
            )
        )

    def __reduce__(self) -> object:
        raise TypeError("ValidatedProductionAuthority cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("ValidatedProductionAuthority cannot be pickled")


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


@dataclass(frozen=True, slots=True)
class InstalledDatabaseValidation:
    """Administrative validation facts for the fixed database pair."""

    database_state: SqliteDatabaseState
    production_evidence: ProductionAuthorityEvidence | None

    def __iter__(self) -> Iterator[object]:
        """Retain the prior private helper's two-value unpacking shape."""

        yield self.database_state
        yield self.production_evidence


@dataclass(frozen=True, slots=True)
class InstalledAuthorityValidation:
    """Administrative installation-conformance evidence only."""

    provisioning: ProvisioningEvidence
    bootstrap_verification: BootstrapVerification
    production_evidence: ProductionAuthorityEvidence | None


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
    from trading_bot.runtime.windows_authority_security import (
        open_authority_object,
    )

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


def read_installed_authority_material(trading_sid: str) -> tuple[bytes, bytes]:
    """Read the already security-validated fixed bootstrap pair."""

    return _read_installed_material(trading_sid)


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


def _inspect_runtime_tree(
    trading_sid: str,
) -> tuple[tuple[str, ...], bool, bool, bytes, bytes]:
    """Inspect only objects granted to the dedicated Trading principal."""

    inspected: list[str] = []
    bootstrap_bytes = b""
    signature_bytes = b""
    required = (
        (PRODUCTION_AUTHORITY_PATHS.root, "root"),
        (PRODUCTION_AUTHORITY_PATHS.bootstrap, "bootstrap"),
        (PRODUCTION_AUTHORITY_PATHS.signature, "signature"),
        (PRODUCTION_AUTHORITY_PATHS.capture_output, "capture-output"),
    )
    for path, role in required:
        with open_authority_object(path, _kind_for(path)) as handle:
            inspection = inspect_open_authority_object(handle, path, _kind_for(path))
            require_security_policy(
                inspection, authority_security_policy(role, trading_sid)
            )
            if role == "bootstrap":
                bootstrap_bytes = read_open_authority_file(handle)
            elif role == "signature":
                signature_bytes = read_open_authority_file(handle)
        inspected.append(role)

    database_present = os.path.lexists(str(PRODUCTION_AUTHORITY_PATHS.database))
    journal_present = os.path.lexists(str(PRODUCTION_AUTHORITY_PATHS.journal))
    for path, role in (
        (PRODUCTION_AUTHORITY_PATHS.database, "database"),
        (PRODUCTION_AUTHORITY_PATHS.journal, "journal"),
    ):
        if os.path.lexists(str(path)):
            with open_authority_object(path, AuthorityObjectKind.FILE) as handle:
                inspection = inspect_open_authority_object(
                    handle, path, AuthorityObjectKind.FILE
                )
                require_security_policy(
                    inspection, authority_security_policy(role, trading_sid)
                )
            inspected.append(role)
    return (
        tuple(inspected),
        database_present,
        journal_present,
        bootstrap_bytes,
        signature_bytes,
    )


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


def _validate_exact_identity(
    *,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    trading_sid: str,
    production: ProductionAuthorityEvidence,
    require_fixed_database_path: bool,
    issuer: _CapabilityIssuer,
) -> ValidatedProductionAuthority:
    """Issue a capability only from exact, already-reviewed facts."""

    if issuer not in (
        _PRODUCTION_CAPABILITY_ISSUER,
        _TEST_CAPABILITY_ISSUER,
    ):
        raise WindowsAuthorityError("validated authority issuer is invalid")

    if type(bootstrap) is not WindowsAuthorityBootstrap:
        raise WindowsAuthorityError("validated authority bootstrap type is invalid")
    if type(production) is not ProductionAuthorityEvidence:
        raise WindowsAuthorityError("validated authority evidence type is invalid")
    if type(trading_sid) is not str or trading_sid != bootstrap.approved_account_sid:
        raise WindowsAuthorityError("validated authority Trading SID is inconsistent")
    if type(bootstrap_digest) is not str or bootstrap_digest != bootstrap.digest:
        raise WindowsAuthorityError("validated authority bootstrap digest is invalid")
    if (
        production.schema_id != PRODUCTION_SCHEMA_ID
        or production.schema_version != PRODUCTION_SCHEMA_VERSION
        or production.schema_digest != PRODUCTION_SCHEMA_ARTIFACT_SHA256
    ):
        raise WindowsAuthorityError("validated authority schema identity is invalid")
    if require_fixed_database_path and (
        production.database_path != str(PRODUCTION_AUTHORITY_PATHS.database)
    ):
        raise WindowsAuthorityError("validated authority database path is not fixed")
    if type(production.database_path) is not str or not production.database_path:
        raise WindowsAuthorityError("validated authority database path is invalid")
    for field in (
        "metadata_digest",
        "release_manifest_digest",
        "sqlite_build_manifest_digest",
    ):
        value = getattr(production, field)
        if (
            type(value) is not str
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise WindowsAuthorityError(f"validated authority {field} is invalid")
    if type(production.migration_id) is not str or not production.migration_id:
        raise WindowsAuthorityError("validated authority migration identity is invalid")
    return ValidatedProductionAuthority(
        _issuer=issuer,
        authority_epoch_id=bootstrap.authority_epoch_id,
        machine_authority_id=bootstrap.machine_authority_id,
        bootstrap_schema=bootstrap.bootstrap_schema,
        bootstrap_generation=bootstrap.bootstrap_generation,
        signing_key_id=bootstrap.signing_key_id,
        approved_account_sid=bootstrap.approved_account_sid,
        provider_id=bootstrap.provider_id,
        permitted_provider_operation=bootstrap.permitted_provider_operation,
        authority_policy_version=bootstrap.authority_policy_version,
        claim_policy_version=bootstrap.claim_policy_version,
        bootstrap_digest=bootstrap_digest,
        database_identity_digest=bootstrap.database_identity_digest,
        database_path=production.database_path,
        schema_id=production.schema_id,
        schema_version=production.schema_version,
        schema_digest=production.schema_digest,
        metadata_digest=production.metadata_digest,
        migration_id=production.migration_id,
        release_manifest_digest=production.release_manifest_digest,
        sqlite_build_manifest_digest=production.sqlite_build_manifest_digest,
    )


def issue_validated_production_authority_for_test(
    *,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    production_evidence: ProductionAuthorityEvidence,
    trading_sid: str | None = None,
) -> ValidatedProductionAuthority:
    """Explicit disposable/test-only capability construction boundary."""

    return _validate_exact_identity(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap_digest,
        trading_sid=(
            bootstrap.approved_account_sid if trading_sid is None else trading_sid
        ),
        production=production_evidence,
        require_fixed_database_path=False,
        issuer=_TEST_CAPABILITY_ISSUER,
    )


def validate_installed_database_complete(
    database_present: bool,
    journal_present: bool,
    *,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    release_manifest: ReleaseManifestEvidence | None,
    sqlite_build: SqliteAuthorityBuildEvidence | None,
) -> InstalledDatabaseValidation:
    """Run complete fixed-path SQLite validation and return administrative facts."""

    if not database_present and not journal_present:
        return InstalledDatabaseValidation(SqliteDatabaseState.NOT_PRESENT, None)
    if database_present != journal_present:
        raise WindowsAuthorityError(
            "pre-created authority database and persistent journal must be paired"
        )
    selected_build = sqlite_build or load_approved_sqlite_authority_build()
    connection = open_read_only_sqlite_connection(
        PRODUCTION_AUTHORITY_PATHS.database, vfs=selected_build.vfs
    )
    try:
        installed = validate_installed_sqlite_prerequisites(
            connection,
            database_path=PRODUCTION_AUTHORITY_PATHS.database,
            journal_path=PRODUCTION_AUTHORITY_PATHS.journal,
        )
        state = installed.database_state
        if state is not SqliteDatabaseState.INITIALIZED_SUPPORTED:
            return InstalledDatabaseValidation(state, None)
        selected_release = release_manifest or load_approved_release_manifest()
        production = validate_production_authority_database_connection(
            connection,
            database_path=PRODUCTION_AUTHORITY_PATHS.database,
            bootstrap=bootstrap,
            bootstrap_digest=bootstrap_digest,
            release_manifest=selected_release,
            sqlite_build=selected_build,
        )
        return InstalledDatabaseValidation(state, production)
    finally:
        connection.close()


def _validate_installed_authority(
    *,
    key_registry: PinnedBootstrapKeyRegistry,
    release_manifest: ReleaseManifestEvidence | None = None,
    sqlite_build: SqliteAuthorityBuildEvidence | None = None,
) -> InstalledAuthorityValidation:
    """Validate complete installed conformance as administrator evidence."""

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
    database = validate_installed_database_complete(
        database_present,
        journal_present,
        bootstrap=verification.bootstrap,
        bootstrap_digest=verification.bootstrap_digest,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
    )
    return InstalledAuthorityValidation(
        provisioning=ProvisioningEvidence(
            ProvisioningState.VALIDATED,
            str(PRODUCTION_AUTHORITY_PATHS.root),
            verification.bootstrap_digest,
            verification.signing_key_id,
            trading_sid,
            inspected,
            database_present,
            journal_present,
            database_state=database.database_state.value,
        ),
        bootstrap_verification=verification,
        production_evidence=database.production_evidence,
    )


def validate_installed_authority_complete() -> InstalledAuthorityValidation:
    """Prove the fixed install from Windows trust through SQLite contents."""

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
    """Explicit test boundary for disposable trust-evidence injection."""

    return _validate_installed_authority(
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

    return validate_installed_authority_complete_for_test(
        key_registry=key_registry,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
    ).provisioning


def require_initialized_supported_authority_evidence(
    validation: InstalledAuthorityValidation,
) -> ProductionAuthorityEvidence:
    """Return reconciled administrator evidence without issuing authority."""

    if type(validation) is not InstalledAuthorityValidation:
        raise WindowsAuthorityError("installed validation result type is invalid")
    if validation.provisioning.database_state != (
        SqliteDatabaseState.INITIALIZED_SUPPORTED.value
    ):
        raise WindowsAuthorityError("installed authority is not INITIALIZED_SUPPORTED")
    if (
        type(validation.provisioning) is not ProvisioningEvidence
        or type(validation.bootstrap_verification) is not BootstrapVerification
        or type(validation.bootstrap_verification.bootstrap)
        is not WindowsAuthorityBootstrap
    ):
        raise WindowsAuthorityError("installed validation evidence types are invalid")
    verification = validation.bootstrap_verification
    bootstrap = verification.bootstrap
    if (
        validation.provisioning.bootstrap_digest != verification.bootstrap_digest
        or validation.provisioning.trading_sid != bootstrap.approved_account_sid
        or bootstrap.database_path != str(PRODUCTION_AUTHORITY_PATHS.database)
    ):
        raise WindowsAuthorityError(
            "administrator evidence does not match bootstrap facts"
        )
    production = validation.production_evidence
    if type(production) is not ProductionAuthorityEvidence:
        raise WindowsAuthorityError(
            "initialized authority has no complete database evidence"
        )
    _validate_production_evidence_shape(production, require_fixed_database_path=True)
    return production


def _validate_production_evidence_shape(
    production: ProductionAuthorityEvidence,
    *,
    require_fixed_database_path: bool,
) -> None:
    if type(production) is not ProductionAuthorityEvidence:
        raise WindowsAuthorityError("validated authority evidence type is invalid")
    if require_fixed_database_path and (
        production.database_path != str(PRODUCTION_AUTHORITY_PATHS.database)
    ):
        raise WindowsAuthorityError("validated authority database path is not fixed")
    if type(production.database_path) is not str or not production.database_path:
        raise WindowsAuthorityError("validated authority database path is invalid")
    if (
        production.schema_id != PRODUCTION_SCHEMA_ID
        or production.schema_version != PRODUCTION_SCHEMA_VERSION
        or production.schema_digest != PRODUCTION_SCHEMA_ARTIFACT_SHA256
    ):
        raise WindowsAuthorityError("validated authority schema identity is invalid")
    for field in (
        "metadata_digest",
        "release_manifest_digest",
        "sqlite_build_manifest_digest",
    ):
        value = getattr(production, field)
        if (
            type(value) is not str
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise WindowsAuthorityError(f"validated authority {field} is invalid")
    if type(production.migration_id) is not str or not production.migration_id:
        raise WindowsAuthorityError("validated authority migration identity is invalid")


def _require_current_trading_token() -> str:
    """Prove the current process is the exact non-elevated Trading principal."""

    current_sid = resolve_current_token_sid()
    trading_sid = require_trading_standard_account()
    if current_sid != trading_sid:
        raise AuthorityPrincipalError(
            "current process token is not the reviewed Trading principal"
        )
    if is_current_token_elevated() or is_current_token_administrator():
        raise AuthorityPrincipalError(
            "Trading runtime authority requires a non-elevated standard token"
        )
    return current_sid


def acquire_validated_production_authority() -> ValidatedProductionAuthority:
    """Acquire executable authority inside the exact Trading process."""

    trading_sid = _require_current_trading_token()
    (
        _inspected,
        database_present,
        journal_present,
        bootstrap_bytes,
        signature_bytes,
    ) = _inspect_runtime_tree(trading_sid)
    verification = _verify_material(
        bootstrap_bytes,
        signature_bytes,
        trading_sid=trading_sid,
        key_registry=PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    )
    validate_lifecycle_mutex_security_descriptor(trading_sid)
    database = validate_installed_database_complete(
        database_present,
        journal_present,
        bootstrap=verification.bootstrap,
        bootstrap_digest=verification.bootstrap_digest,
        release_manifest=None,
        sqlite_build=None,
    )
    if database.database_state is not SqliteDatabaseState.INITIALIZED_SUPPORTED:
        raise WindowsAuthorityError(
            "runtime authority requires INITIALIZED_SUPPORTED authority state"
        )
    production = database.production_evidence
    if type(production) is not ProductionAuthorityEvidence:
        raise WindowsAuthorityError(
            "runtime authority has no complete database evidence"
        )
    capability = _validate_exact_identity(
        bootstrap=verification.bootstrap,
        bootstrap_digest=verification.bootstrap_digest,
        trading_sid=trading_sid,
        production=production,
        require_fixed_database_path=True,
        issuer=_PRODUCTION_CAPABILITY_ISSUER,
    )
    return require_validated_production_authority(capability)


def require_validated_production_authority(
    authority: ValidatedProductionAuthority,
) -> ValidatedProductionAuthority:
    """Validate the process-local production capability consumption boundary."""

    if type(authority) is not ValidatedProductionAuthority:
        raise WindowsAuthorityError("validated production authority type is invalid")
    if authority._provenance is not _PRODUCTION_CAPABILITY_ISSUER:
        raise WindowsAuthorityError(
            "validated production authority has non-production provenance"
        )
    if authority.database_path != str(PRODUCTION_AUTHORITY_PATHS.database):
        raise WindowsAuthorityError(
            "validated production authority is not fixed-path bound"
        )
    if (
        type(authority.schema_id) is not str
        or type(authority.schema_version) is not int
        or authority.schema_id != PRODUCTION_SCHEMA_ID
        or authority.schema_version != PRODUCTION_SCHEMA_VERSION
        or authority.schema_digest != PRODUCTION_SCHEMA_ARTIFACT_SHA256
    ):
        raise WindowsAuthorityError("validated production authority schema is invalid")
    for field in (
        "bootstrap_digest",
        "database_identity_digest",
        "metadata_digest",
        "release_manifest_digest",
        "sqlite_build_manifest_digest",
    ):
        value = getattr(authority, field)
        if (
            type(value) is not str
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise WindowsAuthorityError(
                f"validated production authority {field} is invalid"
            )
    for field in _CAPABILITY_FIELDS:
        value = getattr(authority, field)
        if type(value) not in (str, int) or (type(value) is str and not value):
            raise WindowsAuthorityError(
                f"validated production authority field {field} is invalid"
            )
    return authority


def require_open_connection_matches_validated_authority(
    authority: ValidatedProductionAuthority,
    connection: sqlite3.Connection,
    *,
    allow_active_transaction: bool = False,
) -> ProductionAuthorityEvidence:
    """Revalidate one retained connection against exact C1 authority."""

    require_validated_production_authority(authority)
    if type(connection) is not sqlite3.Connection:
        raise WindowsAuthorityError("production authority connection type is invalid")

    release_manifest = load_approved_release_manifest()
    sqlite_build = load_approved_sqlite_authority_build()
    if release_manifest.digest.hex() != authority.release_manifest_digest:
        raise WindowsAuthorityError(
            "approved release manifest does not match validated authority"
        )
    if sqlite_build.digest.hex() != authority.sqlite_build_manifest_digest:
        raise WindowsAuthorityError(
            "approved SQLite build does not match validated authority"
        )

    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=authority.bootstrap_schema,
        bootstrap_generation=authority.bootstrap_generation,
        machine_authority_id=authority.machine_authority_id,
        authority_epoch_id=authority.authority_epoch_id,
        signing_key_id=authority.signing_key_id,
        approved_account_sid=authority.approved_account_sid,
        database_path=authority.database_path,
        output_root=str(PRODUCTION_AUTHORITY_PATHS.capture_output),
        provider_id=authority.provider_id,
        permitted_provider_operation=authority.permitted_provider_operation,
        authority_policy_version=authority.authority_policy_version,
        claim_policy_version=authority.claim_policy_version,
        database_identity_digest=authority.database_identity_digest,
    )
    if bootstrap.digest != authority.bootstrap_digest:
        raise WindowsAuthorityError(
            "validated authority bootstrap identity is inconsistent"
        )

    observed = validate_production_authority_database_connection(
        connection,
        database_path=authority.database_path,
        bootstrap=bootstrap,
        bootstrap_digest=authority.bootstrap_digest,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
        allow_active_transaction=allow_active_transaction,
    )
    expected = ProductionAuthorityEvidence(
        database_path=authority.database_path,
        schema_id=authority.schema_id,
        schema_version=authority.schema_version,
        schema_digest=authority.schema_digest,
        metadata_digest=authority.metadata_digest,
        migration_id=authority.migration_id,
        release_manifest_digest=authority.release_manifest_digest,
        sqlite_build_manifest_digest=authority.sqlite_build_manifest_digest,
    )
    if observed != expected:
        raise WindowsAuthorityError(
            "opened production connection does not match validated authority"
        )
    return observed


def acquire_validated_production_authority_for_test(
    *,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    production_evidence: ProductionAuthorityEvidence,
    trading_sid: str | None = None,
) -> ValidatedProductionAuthority:
    """Explicit disposable/test-only capability injection boundary."""

    return issue_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap_digest,
        production_evidence=production_evidence,
        trading_sid=trading_sid,
    )
