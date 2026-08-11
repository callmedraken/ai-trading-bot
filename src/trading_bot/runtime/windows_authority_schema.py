"""Production v1 schema, canonical authority evidence, and validation.

This module is deliberately independent of the Architecture-77 transactional
fixture.  The fixture remains a regression contract for the existing capture
service; this module owns the packaged production artifact and its exact
read-only validation boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from trading_bot.runtime.windows_authority import (
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
)


class AuthoritySchemaError(WindowsAuthorityError, ValueError):
    """Base class for production schema and evidence failures."""


class SchemaValidationError(AuthoritySchemaError):
    """Raised when the artifact or materialized schema is not exact."""


class MetadataValidationError(AuthoritySchemaError):
    """Raised when canonical authority metadata is invalid."""


class MigrationValidationError(AuthoritySchemaError):
    """Raised when the immutable v1 initialization evidence is invalid."""


class InitializationBlockedError(AuthoritySchemaError):
    """Raised when a required reviewed release/build input is unavailable."""


PRODUCTION_SCHEMA_ID = "windows-transactional-authority-schema/v1"
PRODUCTION_SCHEMA_VERSION = 1
METADATA_ENCODING_VERSION = "authority-metadata/v1"
INITIALIZATION_POLICY_VERSION = "authority-initialization/v1"
MIGRATION_POLICY_VERSION = "migration-policy/v1"
SCHEMA_MANIFEST_VERSION = "schema-manifest/v1"
RELEASE_MANIFEST_ID = "authority-initializer-release-manifest/v1"
INITIALIZER_CONTRACT_VERSION = "authority-initializer/v1"
SQLITE_BUILD_MANIFEST_ID = "sqlite-authority/v1"
AUTHORITY_IDENTITY_NAMESPACE = UUID("7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012")

_ARTIFACT_NAME = "windows_transactional_authority_v1.sql"
_ARTIFACT_SHA256 = "aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58"
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SID = re.compile(r"^S-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*))+$")
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_UTC_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def _artifact_bytes() -> bytes:
    try:
        data = (
            resources.files("trading_bot.runtime.schema")
            .joinpath(_ARTIFACT_NAME)
            .read_bytes()
        )
    except (FileNotFoundError, ModuleNotFoundError, OSError) as error:
        raise SchemaValidationError("production SQL artifact is unavailable") from error
    if data.startswith(b"\xef\xbb\xbf"):
        raise SchemaValidationError("production SQL artifact must not contain a BOM")
    if hashlib.sha256(data).hexdigest() != _ARTIFACT_SHA256:
        raise SchemaValidationError("production SQL artifact digest is not approved")
    if b"sha256(" in data.lower():
        raise SchemaValidationError(
            "production SQL artifact contains a custom hash call"
        )
    return data


PRODUCTION_SCHEMA_ARTIFACT_BYTES = _artifact_bytes()
PRODUCTION_SCHEMA_ARTIFACT_SHA256 = _ARTIFACT_SHA256


def configure_trusted_schema_off(connection: sqlite3.Connection) -> None:
    """Establish and read back SQLite's connection-local trusted-schema fence."""

    if type(connection) is not sqlite3.Connection:
        raise SchemaValidationError("trusted-schema setup requires sqlite3.Connection")
    configured = False
    setconfig = getattr(connection, "setconfig", None)
    config_constant = getattr(sqlite3, "SQLITE_DBCONFIG_TRUSTED_SCHEMA", None)
    if callable(setconfig) and type(config_constant) is int:
        try:
            setconfig(config_constant, 0)
            configured = True
        except (sqlite3.Error, TypeError, ValueError):
            configured = False
    if not configured:
        try:
            connection.execute("PRAGMA trusted_schema = OFF")
        except (sqlite3.Error, TypeError, ValueError) as error:
            raise SchemaValidationError(
                "SQLite cannot establish trusted_schema=OFF"
            ) from error
    try:
        value = connection.execute("PRAGMA trusted_schema").fetchone()
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SchemaValidationError("SQLite trusted_schema readback failed") from error
    if value is None or type(value[0]) is not int or value[0] != 0:
        raise SchemaValidationError("SQLite trusted_schema is not OFF")


def _statement_iterator(sql: bytes | str) -> tuple[str, ...]:
    text = sql.decode("utf-8") if type(sql) is bytes else sql
    if type(text) is not str:
        raise SchemaValidationError("SQL artifact must be text")
    statements: list[str] = []
    buffer = ""
    for character in text:
        buffer += character
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                statements.append(statement)
            buffer = ""
    if buffer.strip():
        raise SchemaValidationError("SQL artifact ends with an incomplete statement")
    return tuple(statements)


def execute_schema_artifact(
    connection: sqlite3.Connection,
    *,
    commit: bool = False,
) -> None:
    """Execute the packaged artifact statement-by-statement in one transaction."""

    if type(connection) is not sqlite3.Connection:
        raise SchemaValidationError("schema execution requires sqlite3.Connection")
    configure_trusted_schema_off(connection)
    try:
        for statement in _statement_iterator(PRODUCTION_SCHEMA_ARTIFACT_BYTES):
            connection.execute(statement)
        if commit:
            connection.commit()
    except (sqlite3.Error, ValueError, TypeError) as error:
        raise SchemaValidationError(
            "production SQL artifact could not execute"
        ) from error


def _quote_pragma_identifier(value: str) -> str:
    if type(value) is not str or not value or "\x00" in value:
        raise SchemaValidationError("SQLite schema identifier is invalid")
    return '"' + value.replace('"', '""') + '"'


def _schema_rows(connection: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    try:
        rows = tuple(
            tuple(row)
            for row in connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_schema"
            ).fetchall()
        )
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SchemaValidationError("SQLite schema rows could not be read") from error
    filtered = tuple(
        row
        for row in rows
        if not (
            row[0] == "index"
            and type(row[1]) is str
            and row[1].startswith("sqlite_autoindex_")
            and row[3] is None
        )
    )
    return tuple(
        sorted(filtered, key=lambda row: (str(row[0]), str(row[1]), str(row[2])))
    )


def _pragma_rows(
    connection: sqlite3.Connection,
    pragma: str,
    table: str,
) -> tuple[tuple[object, ...], ...]:
    statement = f"PRAGMA {pragma}({_quote_pragma_identifier(table)})"
    try:
        return tuple(tuple(row) for row in connection.execute(statement).fetchall())
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SchemaValidationError(f"SQLite {pragma} could not be read") from error


def _materialized_schema_manifest(connection: sqlite3.Connection) -> bytes:
    rows = _schema_rows(connection)
    tables = [row for row in rows if row[0] == "table"]
    manifest_tables: dict[str, object] = {}
    for row in tables:
        name = str(row[1])
        columns = _pragma_rows(connection, "table_xinfo", name)
        indexes = _pragma_rows(connection, "index_list", name)
        index_items: list[dict[str, object]] = []
        for index in sorted(indexes, key=lambda item: str(item[1])):
            index_name = str(index[1])
            index_items.append(
                {
                    "columns": [
                        list(item)
                        for item in _pragma_rows(connection, "index_xinfo", index_name)
                    ],
                    "name": index_name,
                    "partial": index[4],
                    "origin": index[3],
                    "unique": index[2],
                }
            )
        manifest_tables[name] = {
            "columns": [list(item) for item in columns],
            "foreign_keys": [
                list(item)
                for item in _pragma_rows(connection, "foreign_key_list", name)
            ],
            "indexes": index_items,
            "sql": row[3],
        }
    manifest = {
        "manifest_id": SCHEMA_MANIFEST_VERSION,
        "schema_objects": [
            {
                "name": row[1],
                "sql": row[3],
                "table": row[2],
                "type": row[0],
            }
            for row in rows
        ],
        "tables": manifest_tables,
        "triggers": [
            {"name": row[1], "sql": row[3], "table": row[2]}
            for row in rows
            if row[0] == "trigger"
        ],
        "views": [
            {"name": row[1], "sql": row[3], "table": row[2]}
            for row in rows
            if row[0] == "view"
        ],
    }
    return json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _materialize_expected_manifest() -> bytes:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        execute_schema_artifact(connection)
        return _materialized_schema_manifest(connection)
    except (sqlite3.Error, AuthoritySchemaError) as error:
        if isinstance(error, AuthoritySchemaError):
            raise
        raise SchemaValidationError(
            "expected schema manifest could not be built"
        ) from error
    finally:
        connection.close()


PRODUCTION_SCHEMA_MANIFEST_BYTES = _materialize_expected_manifest()


def canonical_schema_manifest(connection: sqlite3.Connection) -> bytes:
    """Return the exact rootpage-free manifest for one database connection."""

    configure_trusted_schema_off(connection)
    return _materialized_schema_manifest(connection)


def validate_production_schema(connection: sqlite3.Connection) -> None:
    """Require the exact artifact digest and exact materialized schema."""

    configure_trusted_schema_off(connection)
    if hashlib.sha256(PRODUCTION_SCHEMA_ARTIFACT_BYTES).hexdigest() != (
        PRODUCTION_SCHEMA_ARTIFACT_SHA256
    ):
        raise SchemaValidationError("production artifact identity is inconsistent")
    if canonical_schema_manifest(connection) != PRODUCTION_SCHEMA_MANIFEST_BYTES:
        raise SchemaValidationError("materialized production schema is not exact")


def _strict_json_object(
    data: bytes, error_type: type[AuthoritySchemaError]
) -> dict[str, object]:
    if type(data) is not bytes:
        raise error_type("canonical JSON input must be bytes")
    if data.startswith(b"\xef\xbb\xbf"):
        raise error_type("canonical JSON must not contain a BOM")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise error_type("canonical JSON contains duplicate keys")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise error_type(f"canonical JSON contains invalid constant {value}")

    try:
        parsed = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except AuthoritySchemaError:
        raise
    except (UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise error_type("canonical JSON is malformed") from error
    if type(parsed) is not dict:
        raise error_type("canonical JSON root must be an object")
    return parsed


def _canonical_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _require_text(
    value: object, field: str, error_type: type[AuthoritySchemaError]
) -> str:
    if type(value) is not str or not value:
        raise error_type(f"{field} must be non-empty text")
    return value


def _require_uuid(
    value: object, field: str, error_type: type[AuthoritySchemaError]
) -> str:
    text = _require_text(value, field, error_type)
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError) as error:
        raise error_type(f"{field} must be a UUID") from error
    if str(parsed) != text:
        raise error_type(f"{field} must be lowercase canonical UUID text")
    return text


def _require_digest(
    value: object, field: str, error_type: type[AuthoritySchemaError]
) -> str:
    text = _require_text(value, field, error_type)
    if _HEX_DIGEST.fullmatch(text) is None:
        raise error_type(f"{field} must be lowercase SHA-256 text")
    return text


def _require_timestamp(
    value: object, field: str, error_type: type[AuthoritySchemaError]
) -> str:
    text = _require_text(value, field, error_type)
    if _UTC_TIMESTAMP.fullmatch(text) is None:
        raise error_type(f"{field} is not timestamp v1")
    try:
        datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise error_type(f"{field} is not a valid UTC timestamp") from error
    return text


_METADATA_FIELDS = frozenset(
    {
        "approved_account_sid",
        "authority_epoch_id",
        "authority_policy_version",
        "bootstrap_digest",
        "bootstrap_generation",
        "bootstrap_schema",
        "claim_policy_version",
        "created_at_utc",
        "database_identity_digest",
        "initialization_policy_version",
        "machine_authority_id",
        "metadata_encoding_version",
        "production_schema_digest",
        "production_schema_id",
        "production_schema_version",
        "provider_id",
        "permitted_provider_operation",
        "signing_key_id",
        "singleton_key",
    }
)


@dataclass(frozen=True, slots=True)
class AuthorityMetadataV1:
    """The exact singleton semantic object stored in authority_metadata."""

    approved_account_sid: str
    authority_epoch_id: str
    authority_policy_version: str
    bootstrap_digest: str
    bootstrap_generation: int
    bootstrap_schema: int
    claim_policy_version: str
    created_at_utc: str
    database_identity_digest: str
    initialization_policy_version: str
    machine_authority_id: str
    metadata_encoding_version: str
    production_schema_digest: str
    production_schema_id: str
    production_schema_version: int
    provider_id: str
    permitted_provider_operation: str
    signing_key_id: str
    singleton_key: int = 1

    def __post_init__(self) -> None:
        _require_uuid(
            self.authority_epoch_id, "authority_epoch_id", MetadataValidationError
        )
        _require_uuid(
            self.machine_authority_id, "machine_authority_id", MetadataValidationError
        )
        if (
            type(self.approved_account_sid) is not str
            or _SID.fullmatch(self.approved_account_sid) is None
        ):
            raise MetadataValidationError("approved_account_sid is not a SID")
        if (
            type(self.signing_key_id) is not str
            or _KEY_ID.fullmatch(self.signing_key_id) is None
        ):
            raise MetadataValidationError("signing_key_id is not canonical")
        for field in (
            "bootstrap_digest",
            "database_identity_digest",
            "production_schema_digest",
        ):
            _require_digest(getattr(self, field), field, MetadataValidationError)
        _require_timestamp(
            self.created_at_utc, "created_at_utc", MetadataValidationError
        )
        if type(self.bootstrap_schema) is not int or self.bootstrap_schema != 1:
            raise MetadataValidationError("bootstrap_schema must equal 1")
        if type(self.bootstrap_generation) is not int or self.bootstrap_generation <= 0:
            raise MetadataValidationError("bootstrap_generation must be positive")
        if self.authority_policy_version != "authority-policy/v1":
            raise MetadataValidationError("authority policy is unsupported")
        if self.claim_policy_version != "claim-policy/v1":
            raise MetadataValidationError("claim policy is unsupported")
        if self.production_schema_id != PRODUCTION_SCHEMA_ID:
            raise MetadataValidationError("production schema ID is unsupported")
        if (
            type(self.production_schema_version) is not int
            or self.production_schema_version != 1
        ):
            raise MetadataValidationError("production schema version is unsupported")
        if self.metadata_encoding_version != METADATA_ENCODING_VERSION:
            raise MetadataValidationError("metadata encoding is unsupported")
        if self.initialization_policy_version != INITIALIZATION_POLICY_VERSION:
            raise MetadataValidationError("initialization policy is unsupported")
        if type(self.provider_id) is not str or not self.provider_id:
            raise MetadataValidationError("provider_id must be text")
        if (
            type(self.permitted_provider_operation) is not str
            or not self.permitted_provider_operation
        ):
            raise MetadataValidationError("permitted_provider_operation must be text")
        if type(self.singleton_key) is not int or self.singleton_key != 1:
            raise MetadataValidationError("singleton_key must equal 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "approved_account_sid": self.approved_account_sid,
            "authority_epoch_id": self.authority_epoch_id,
            "authority_policy_version": self.authority_policy_version,
            "bootstrap_digest": self.bootstrap_digest,
            "bootstrap_generation": self.bootstrap_generation,
            "bootstrap_schema": self.bootstrap_schema,
            "claim_policy_version": self.claim_policy_version,
            "created_at_utc": self.created_at_utc,
            "database_identity_digest": self.database_identity_digest,
            "initialization_policy_version": self.initialization_policy_version,
            "machine_authority_id": self.machine_authority_id,
            "metadata_encoding_version": self.metadata_encoding_version,
            "production_schema_digest": self.production_schema_digest,
            "production_schema_id": self.production_schema_id,
            "production_schema_version": self.production_schema_version,
            "provider_id": self.provider_id,
            "permitted_provider_operation": self.permitted_provider_operation,
            "signing_key_id": self.signing_key_id,
            "singleton_key": self.singleton_key,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict())

    @property
    def digest(self) -> bytes:
        return hashlib.sha256(self.canonical_bytes()).digest()


def parse_authority_metadata_bytes(data: bytes) -> AuthorityMetadataV1:
    values = _strict_json_object(data, MetadataValidationError)
    if frozenset(values) != _METADATA_FIELDS:
        raise MetadataValidationError("authority metadata field set is not exact")
    integer_fields = {
        "bootstrap_generation",
        "bootstrap_schema",
        "production_schema_version",
        "singleton_key",
    }
    for field, value in values.items():
        if field in integer_fields:
            if type(value) is not int:
                raise MetadataValidationError(f"{field} must be an integer")
        elif type(value) is not str:
            raise MetadataValidationError(f"{field} must be a string")
    metadata = AuthorityMetadataV1(**values)
    if metadata.canonical_bytes() != data:
        raise MetadataValidationError("authority metadata bytes are not canonical")
    return metadata


def authority_metadata_from_bootstrap(
    bootstrap: WindowsAuthorityBootstrap,
    *,
    bootstrap_digest: str,
    created_at_utc: str,
) -> AuthorityMetadataV1:
    return AuthorityMetadataV1(
        approved_account_sid=bootstrap.approved_account_sid,
        authority_epoch_id=bootstrap.authority_epoch_id,
        authority_policy_version=bootstrap.authority_policy_version,
        bootstrap_digest=_require_digest(
            bootstrap_digest, "bootstrap_digest", MetadataValidationError
        ),
        bootstrap_generation=bootstrap.bootstrap_generation,
        bootstrap_schema=bootstrap.bootstrap_schema,
        claim_policy_version=bootstrap.claim_policy_version,
        created_at_utc=created_at_utc,
        database_identity_digest=bootstrap.database_identity_digest,
        initialization_policy_version=INITIALIZATION_POLICY_VERSION,
        machine_authority_id=bootstrap.machine_authority_id,
        metadata_encoding_version=METADATA_ENCODING_VERSION,
        production_schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        production_schema_id=PRODUCTION_SCHEMA_ID,
        production_schema_version=PRODUCTION_SCHEMA_VERSION,
        provider_id=bootstrap.provider_id,
        permitted_provider_operation=bootstrap.permitted_provider_operation,
        signing_key_id=bootstrap.signing_key_id,
    )


def validate_metadata_against_bootstrap(
    metadata: AuthorityMetadataV1,
    bootstrap: WindowsAuthorityBootstrap,
    *,
    bootstrap_digest: str,
) -> None:
    if bootstrap.digest != bootstrap_digest:
        raise MetadataValidationError("verified bootstrap digest is inconsistent")
    expected = authority_metadata_from_bootstrap(
        bootstrap,
        bootstrap_digest=bootstrap_digest,
        created_at_utc=metadata.created_at_utc,
    )
    if metadata != expected:
        raise MetadataValidationError("authority metadata does not match bootstrap")


def _frame(value: object) -> str:
    text = str(value)
    return f"{len(text.encode('utf-8'))}:{text}"


def migration_id_v1(authority_epoch_id: str) -> str:
    """Return the Architecture-77 framed deterministic migration identity."""

    _require_uuid(authority_epoch_id, "authority_epoch_id", MigrationValidationError)
    material = "".join(
        (
            _frame("migration_id/v1"),
            _frame(authority_epoch_id),
            _frame(PRODUCTION_SCHEMA_VERSION),
            _frame(MIGRATION_POLICY_VERSION),
        )
    )
    return str(uuid5(AUTHORITY_IDENTITY_NAMESPACE, material))


@dataclass(frozen=True, slots=True)
class ReleaseManifestEvidence:
    """An explicitly reviewed initializer release manifest."""

    manifest_bytes: bytes
    application_version: str
    manifest_id: str = RELEASE_MANIFEST_ID
    initializer_contract_version: str = INITIALIZER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if type(self.manifest_bytes) is not bytes:
            raise InitializationBlockedError("release manifest bytes must be bytes")
        if self.manifest_id != RELEASE_MANIFEST_ID:
            raise InitializationBlockedError("release manifest ID is unsupported")
        if self.initializer_contract_version != INITIALIZER_CONTRACT_VERSION:
            raise InitializationBlockedError("initializer contract is unsupported")
        if type(self.application_version) is not str or not self.application_version:
            raise InitializationBlockedError("release application version is invalid")
        values = _strict_json_object(self.manifest_bytes, InitializationBlockedError)
        expected = {
            "application_version",
            "initializer_contract_version",
            "manifest_id",
            "production_schema_digest",
            "production_schema_id",
        }
        if frozenset(values) != expected or any(
            type(value) is not str for value in values.values()
        ):
            raise InitializationBlockedError(
                "release manifest evidence is inconsistent"
            )
        if values != self.to_dict() or _canonical_bytes(values) != self.manifest_bytes:
            raise InitializationBlockedError(
                "release manifest evidence is inconsistent"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "application_version": self.application_version,
            "initializer_contract_version": self.initializer_contract_version,
            "manifest_id": self.manifest_id,
            "production_schema_digest": PRODUCTION_SCHEMA_ARTIFACT_SHA256,
            "production_schema_id": PRODUCTION_SCHEMA_ID,
        }

    @property
    def digest(self) -> bytes:
        return hashlib.sha256(self.manifest_bytes).digest()


def parse_release_manifest_bytes(data: bytes) -> ReleaseManifestEvidence:
    values = _strict_json_object(data, InitializationBlockedError)
    expected = {
        "application_version",
        "initializer_contract_version",
        "manifest_id",
        "production_schema_digest",
        "production_schema_id",
    }
    if frozenset(values) != expected:
        raise InitializationBlockedError("release manifest field set is not exact")
    if any(type(value) is not str for value in values.values()):
        raise InitializationBlockedError("release manifest values must be strings")
    if values["manifest_id"] != RELEASE_MANIFEST_ID:
        raise InitializationBlockedError("release manifest ID is unsupported")
    if values["initializer_contract_version"] != INITIALIZER_CONTRACT_VERSION:
        raise InitializationBlockedError("initializer contract is unsupported")
    if values["production_schema_id"] != PRODUCTION_SCHEMA_ID:
        raise InitializationBlockedError("release schema ID does not match")
    if values["production_schema_digest"] != PRODUCTION_SCHEMA_ARTIFACT_SHA256:
        raise InitializationBlockedError("release schema digest does not match")
    parsed = ReleaseManifestEvidence(
        manifest_bytes=data,
        application_version=values["application_version"],
        manifest_id=values["manifest_id"],
        initializer_contract_version=values["initializer_contract_version"],
    )
    if _canonical_bytes(values) != data:
        raise InitializationBlockedError("release manifest bytes are not canonical")
    return parsed


def load_approved_release_manifest() -> ReleaseManifestEvidence:
    """Fail closed until the separately reviewed production manifest is published."""

    raise InitializationBlockedError(
        "no approved production release manifest is published"
    )


@dataclass(frozen=True, slots=True)
class SqliteAuthorityBuildEvidence:
    """Sanitized evidence for an explicitly approved SQLite/VFS build."""

    manifest_bytes: bytes
    sqlite_version: str
    sqlite_source_id: str
    vfs: str
    compile_options: tuple[str, ...]
    trusted_schema_off: bool = True
    manifest_id: str = SQLITE_BUILD_MANIFEST_ID

    def __post_init__(self) -> None:
        if (
            type(self.manifest_bytes) is not bytes
            or self.manifest_id != SQLITE_BUILD_MANIFEST_ID
        ):
            raise InitializationBlockedError("SQLite build evidence is inconsistent")
        if self.trusted_schema_off is not True:
            raise InitializationBlockedError(
                "SQLite trusted-schema evidence is not true"
            )
        values = _strict_json_object(self.manifest_bytes, InitializationBlockedError)
        if values != self.to_dict() or _canonical_bytes(values) != self.manifest_bytes:
            raise InitializationBlockedError("SQLite build evidence is inconsistent")

    def to_dict(self) -> dict[str, object]:
        return {
            "compile_options": list(self.compile_options),
            "manifest_id": self.manifest_id,
            "sqlite_source_id": self.sqlite_source_id,
            "sqlite_version": self.sqlite_version,
            "trusted_schema_off": self.trusted_schema_off,
            "vfs": self.vfs,
        }

    @property
    def digest(self) -> bytes:
        return hashlib.sha256(self.manifest_bytes).digest()


def parse_sqlite_authority_build_manifest(data: bytes) -> SqliteAuthorityBuildEvidence:
    values = _strict_json_object(data, InitializationBlockedError)
    expected = {
        "compile_options",
        "manifest_id",
        "sqlite_source_id",
        "sqlite_version",
        "trusted_schema_off",
        "vfs",
    }
    if frozenset(values) != expected:
        raise InitializationBlockedError("SQLite build manifest field set is not exact")
    if values["manifest_id"] != SQLITE_BUILD_MANIFEST_ID:
        raise InitializationBlockedError("SQLite build manifest ID is unsupported")
    if type(values["compile_options"]) is not list or any(
        type(item) is not str for item in values["compile_options"]
    ):
        raise InitializationBlockedError("SQLite compile options are invalid")
    options = tuple(values["compile_options"])
    if options != tuple(sorted(set(options))):
        raise InitializationBlockedError("SQLite compile options are not canonical")
    for field in ("sqlite_version", "sqlite_source_id", "vfs"):
        if type(values[field]) is not str or not values[field]:
            raise InitializationBlockedError(f"SQLite build field {field} is invalid")
    if (
        type(values["trusted_schema_off"]) is not bool
        or not values["trusted_schema_off"]
    ):
        raise InitializationBlockedError("SQLite trusted-schema evidence is not true")
    if _canonical_bytes(values) != data:
        raise InitializationBlockedError(
            "SQLite build manifest bytes are not canonical"
        )
    return SqliteAuthorityBuildEvidence(
        manifest_bytes=data,
        sqlite_version=values["sqlite_version"],
        sqlite_source_id=values["sqlite_source_id"],
        vfs=values["vfs"],
        compile_options=options,
        trusted_schema_off=values["trusted_schema_off"],
        manifest_id=values["manifest_id"],
    )


def load_approved_sqlite_authority_build() -> SqliteAuthorityBuildEvidence:
    """Fail closed until the separately reviewed native build is published."""

    raise InitializationBlockedError(
        "no approved sqlite-authority/v1 build is published"
    )


@dataclass(frozen=True, slots=True)
class SchemaMigrationV1:
    """The immutable historical fact written by the one-time initializer."""

    migration_id: str
    authority_epoch_id: str
    schema_version: int
    migration_policy_version: str
    migration_digest: bytes
    application_release_digest: bytes
    migration_json: bytes
    applied_at_utc: str

    def __post_init__(self) -> None:
        if self.migration_id != migration_id_v1(self.authority_epoch_id):
            raise MigrationValidationError("migration ID is not deterministic v1")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise MigrationValidationError("migration schema version is unsupported")
        if self.migration_policy_version != MIGRATION_POLICY_VERSION:
            raise MigrationValidationError("migration policy is unsupported")
        if type(self.migration_digest) is not bytes or len(self.migration_digest) != 32:
            raise MigrationValidationError("migration digest must be 32 raw bytes")
        if (
            type(self.application_release_digest) is not bytes
            or len(self.application_release_digest) != 32
        ):
            raise MigrationValidationError("release digest must be 32 raw bytes")
        if type(self.migration_json) is not bytes:
            raise MigrationValidationError("migration JSON must be UTF-8 bytes")
        _require_timestamp(
            self.applied_at_utc, "applied_at_utc", MigrationValidationError
        )
        if hashlib.sha256(self.migration_json).digest() != self.migration_digest:
            raise MigrationValidationError("migration digest does not match bytes")
        parsed = _strict_json_object(self.migration_json, MigrationValidationError)
        if parsed != self.to_dict():
            raise MigrationValidationError("migration JSON does not match row")
        if _canonical_bytes(parsed) != self.migration_json:
            raise MigrationValidationError("migration JSON is not canonical")

    def to_dict(self) -> dict[str, object]:
        return {
            "application_release_digest": self.application_release_digest.hex(),
            "applied_at_utc": self.applied_at_utc,
            "authority_epoch_id": self.authority_epoch_id,
            "initialization_policy_version": INITIALIZATION_POLICY_VERSION,
            "migration_id": self.migration_id,
            "migration_policy_version": self.migration_policy_version,
            "production_schema_digest": PRODUCTION_SCHEMA_ARTIFACT_SHA256,
            "production_schema_id": PRODUCTION_SCHEMA_ID,
            "schema_version": self.schema_version,
        }


def create_schema_migration_v1(
    authority_epoch_id: str,
    *,
    release_manifest: ReleaseManifestEvidence,
    applied_at_utc: str,
) -> SchemaMigrationV1:
    migration_id = migration_id_v1(authority_epoch_id)
    provisional = {
        "application_release_digest": release_manifest.digest.hex(),
        "applied_at_utc": applied_at_utc,
        "authority_epoch_id": authority_epoch_id,
        "initialization_policy_version": INITIALIZATION_POLICY_VERSION,
        "migration_id": migration_id,
        "migration_policy_version": MIGRATION_POLICY_VERSION,
        "production_schema_digest": PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        "production_schema_id": PRODUCTION_SCHEMA_ID,
        "schema_version": PRODUCTION_SCHEMA_VERSION,
    }
    migration_json = _canonical_bytes(provisional)
    return SchemaMigrationV1(
        migration_id=migration_id,
        authority_epoch_id=authority_epoch_id,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        migration_policy_version=MIGRATION_POLICY_VERSION,
        migration_digest=hashlib.sha256(migration_json).digest(),
        application_release_digest=release_manifest.digest,
        migration_json=migration_json,
        applied_at_utc=applied_at_utc,
    )


def validate_metadata_row(
    connection: sqlite3.Connection,
    bootstrap: WindowsAuthorityBootstrap,
    *,
    bootstrap_digest: str,
) -> AuthorityMetadataV1:
    try:
        rows = connection.execute(
            "SELECT approved_account_sid, authority_epoch_id, "
            "authority_policy_version, bootstrap_digest, bootstrap_generation, "
            "bootstrap_schema, claim_policy_version, created_at_utc, "
            "database_identity_digest, initialization_policy_version, "
            "machine_authority_id, metadata_encoding_version, "
            "production_schema_digest, production_schema_id, "
            "production_schema_version, provider_id, permitted_provider_operation, "
            "signing_key_id, singleton_key, metadata_json, "
            "metadata_digest FROM authority_metadata"
        ).fetchall()
    except (sqlite3.Error, TypeError, ValueError) as error:
        raise MetadataValidationError(
            "authority metadata row could not be read"
        ) from error
    if len(rows) != 1:
        raise MetadataValidationError(
            "authority metadata must contain one singleton row"
        )
    row = rows[0]
    if type(row[19]) is not bytes or type(row[20]) is not bytes:
        raise MetadataValidationError(
            "authority metadata JSON and digest must be BLOBs"
        )
    metadata = parse_authority_metadata_bytes(row[19])
    if hashlib.sha256(row[19]).digest() != row[20]:
        raise MetadataValidationError("authority metadata digest is invalid")
    expected_columns = (
        metadata.approved_account_sid,
        metadata.authority_epoch_id,
        metadata.authority_policy_version,
        bytes.fromhex(metadata.bootstrap_digest),
        metadata.bootstrap_generation,
        metadata.bootstrap_schema,
        metadata.claim_policy_version,
        metadata.created_at_utc,
        bytes.fromhex(metadata.database_identity_digest),
        metadata.initialization_policy_version,
        metadata.machine_authority_id,
        metadata.metadata_encoding_version,
        bytes.fromhex(metadata.production_schema_digest),
        metadata.production_schema_id,
        metadata.production_schema_version,
        metadata.provider_id,
        metadata.permitted_provider_operation,
        metadata.signing_key_id,
        metadata.singleton_key,
    )
    if tuple(row[:19]) != expected_columns:
        raise MetadataValidationError("authority metadata columns do not match JSON")
    validate_metadata_against_bootstrap(
        metadata, bootstrap, bootstrap_digest=bootstrap_digest
    )
    return metadata


def validate_migration_row(
    connection: sqlite3.Connection,
    *,
    authority_epoch_id: str,
    release_manifest: ReleaseManifestEvidence,
) -> SchemaMigrationV1:
    try:
        rows = connection.execute(
            "SELECT migration_id, authority_epoch_id, schema_version, "
            "migration_policy_version, migration_digest, application_release_digest, "
            "migration_json, applied_at_utc FROM schema_migrations"
        ).fetchall()
    except (sqlite3.Error, TypeError, ValueError) as error:
        raise MigrationValidationError(
            "schema migration row could not be read"
        ) from error
    if len(rows) != 1:
        raise MigrationValidationError("schema_migrations must contain one v1 row")
    row = rows[0]
    if not all(type(row[index]) is bytes for index in (4, 5, 6)):
        raise MigrationValidationError("migration evidence fields must be BLOBs")
    migration = SchemaMigrationV1(
        migration_id=row[0],
        authority_epoch_id=row[1],
        schema_version=row[2],
        migration_policy_version=row[3],
        migration_digest=row[4],
        application_release_digest=row[5],
        migration_json=row[6],
        applied_at_utc=row[7],
    )
    expected = create_schema_migration_v1(
        authority_epoch_id,
        release_manifest=release_manifest,
        applied_at_utc=migration.applied_at_utc,
    )
    if migration != expected:
        raise MigrationValidationError("schema migration evidence is not exact")
    return migration


@dataclass(frozen=True, slots=True)
class ProductionAuthorityEvidence:
    """Sanitized evidence returned only after complete read-only validation."""

    database_path: str
    schema_id: str
    schema_version: int
    schema_digest: str
    metadata_digest: str
    migration_id: str
    release_manifest_digest: str
    sqlite_build_manifest_digest: str


def validate_production_authority_database(
    connection: sqlite3.Connection,
    *,
    database_path: str | Path,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    release_manifest: ReleaseManifestEvidence,
    sqlite_build: SqliteAuthorityBuildEvidence,
    allow_active_transaction: bool = False,
) -> ProductionAuthorityEvidence:
    """Perform the complete no-write validator for a supported database."""

    configure_trusted_schema_off(connection)
    if connection.in_transaction and not allow_active_transaction:
        raise SchemaValidationError("read-only validation began in a transaction")
    try:
        databases = tuple(
            tuple(row) for row in connection.execute("PRAGMA database_list")
        )
    except (sqlite3.Error, TypeError, ValueError) as error:
        raise SchemaValidationError("SQLite database list could not be read") from error
    if len(databases) != 1 or databases[0][1] != "main":
        raise SchemaValidationError("SQLite database contains an attachment")
    actual_path = str(databases[0][2] or "")
    if actual_path.casefold() != str(database_path).casefold():
        raise SchemaValidationError("SQLite database path is not the fixed target")
    journal_path = Path(f"{database_path}-journal")
    if not journal_path.is_file():
        raise SchemaValidationError("SQLite persistent journal is not present")
    try:
        integrity = tuple(
            tuple(row) for row in connection.execute("PRAGMA integrity_check")
        )
        foreign_keys = tuple(
            tuple(row) for row in connection.execute("PRAGMA foreign_key_check")
        )
    except (sqlite3.Error, TypeError, ValueError) as error:
        raise SchemaValidationError(
            "SQLite integrity evidence could not be read"
        ) from error
    if integrity != (("ok",),) or foreign_keys:
        raise SchemaValidationError("SQLite integrity or foreign-key check failed")
    if sqlite_build.sqlite_version != sqlite3.sqlite_version:
        raise InitializationBlockedError(
            "SQLite version does not match approved build evidence"
        )
    try:
        source_id = str(connection.execute("SELECT sqlite_source_id()").fetchone()[0])
        compile_options = tuple(
            sorted(str(row[0]) for row in connection.execute("PRAGMA compile_options"))
        )
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise InitializationBlockedError(
            "SQLite build identity could not be read"
        ) from error
    if source_id != sqlite_build.sqlite_source_id:
        raise InitializationBlockedError(
            "SQLite source ID does not match approved build evidence"
        )
    if compile_options != tuple(sorted(sqlite_build.compile_options)):
        raise InitializationBlockedError(
            "SQLite compile options do not match approved build evidence"
        )
    validate_production_schema(connection)
    metadata = validate_metadata_row(
        connection, bootstrap, bootstrap_digest=bootstrap_digest
    )
    migration = validate_migration_row(
        connection,
        authority_epoch_id=metadata.authority_epoch_id,
        release_manifest=release_manifest,
    )
    return ProductionAuthorityEvidence(
        database_path=str(database_path),
        schema_id=metadata.production_schema_id,
        schema_version=metadata.production_schema_version,
        schema_digest=metadata.production_schema_digest,
        metadata_digest=metadata.digest.hex(),
        migration_id=migration.migration_id,
        release_manifest_digest=release_manifest.digest.hex(),
        sqlite_build_manifest_digest=sqlite_build.digest.hex(),
    )


def validate_schema_state(connection: sqlite3.Connection) -> str:
    """Classify an open database without treating partial metadata as supported."""

    configure_trusted_schema_off(connection)
    objects = _schema_rows(connection)
    if not objects:
        return "PRECREATED_UNINITIALIZED"
    try:
        validate_production_schema(connection)
    except AuthoritySchemaError:
        return "INITIALIZED_UNSUPPORTED"
    try:
        metadata_count = connection.execute(
            "SELECT count(*) FROM authority_metadata"
        ).fetchone()[0]
        migration_count = connection.execute(
            "SELECT count(*) FROM schema_migrations"
        ).fetchone()[0]
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SchemaValidationError(
            "production schema state could not be read"
        ) from error
    if metadata_count != 1 or migration_count != 1:
        return "INITIALIZED_UNSUPPORTED"
    try:
        metadata_row = connection.execute(
            "SELECT metadata_json, metadata_digest FROM authority_metadata"
        ).fetchone()
        migration_row = connection.execute(
            "SELECT migration_id, authority_epoch_id, schema_version, "
            "migration_policy_version, migration_digest, "
            "application_release_digest, migration_json, applied_at_utc "
            "FROM schema_migrations"
        ).fetchone()
        if metadata_row is None or migration_row is None:
            return "INITIALIZED_UNSUPPORTED"
        parse_authority_metadata_bytes(metadata_row[0])
        if hashlib.sha256(metadata_row[0]).digest() != metadata_row[1]:
            return "INVALID_MISMATCHED"
        SchemaMigrationV1(*migration_row)
    except (AuthoritySchemaError, sqlite3.Error, TypeError, ValueError, IndexError):
        return "INVALID_MISMATCHED"
    return "INITIALIZED_SUPPORTED"


def safe_external_call_guard(callable_value: Callable[..., Any]) -> None:
    """Reject a callable accidentally supplied as a transaction-side effect."""

    if not callable(callable_value):
        raise TypeError("external call guard requires a callable")
