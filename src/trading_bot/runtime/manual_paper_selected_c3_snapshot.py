"""Architecture-94 P2 read-only selected-C3 snapshot authority."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import weakref
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Protocol
from uuid import UUID

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotVerificationResult,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    load_approved_sqlite_authority_build,
    validate_persisted_evidence_digests,
    validate_production_schema,
)
from trading_bot.runtime.windows_authority_sqlite import (
    open_disposable_read_only_sqlite_connection,
    open_read_only_sqlite_connection,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_open_connection_matches_validated_authority,
    require_validated_production_authority,
)
from trading_bot.runtime.windows_effectful_capture_native import (
    CtypesWindowsEffectfulCaptureNativeApi,
    NativeOpenedArtifact,
)
from trading_bot.runtime.windows_effectful_capture_service import (
    C3ArtifactIdentityEvidence,
)
from trading_bot.runtime.windows_transactional_authority import (
    CLAIM_POLICY,
    POLICY,
    RELEASE,
    SELECTION_POLICY,
    TERMINAL_POLICY,
    validate_selected_c3_lineage_for_read,
    validate_successful_c3_terminal_for_read,
)


class SelectedC3SnapshotReadError(WindowsAuthorityError):
    """The exact selected C3 snapshot could not be proven read-only."""


@dataclass(frozen=True, slots=True, weakref_slot=True)
class SelectedC3SnapshotAuditEvidence:
    """Immutable bounded nonsecret evidence produced by successful P2."""

    selection_id: UUID
    session_id: UUID
    attempt_id: UUID
    terminal_id: UUID
    snapshot_id: UUID
    artifact_sha256: str
    artifact_byte_length: int
    artifact_identity_sha256: str
    terminal_state: str
    provider_call_disposition: str
    canonical_artifact_path: str

    def __post_init__(self) -> None:
        for field_name in (
            "selection_id",
            "session_id",
            "attempt_id",
            "terminal_id",
            "snapshot_id",
        ):
            if type(getattr(self, field_name)) is not UUID:
                raise SelectedC3SnapshotReadError(
                    f"P2 audit {field_name} must be an exact UUID"
                )
        for field_name in ("artifact_sha256", "artifact_identity_sha256"):
            value = getattr(self, field_name)
            if not _is_sha256(value):
                raise SelectedC3SnapshotReadError(
                    f"P2 audit {field_name} must be canonical SHA-256"
                )
        if (
            type(self.artifact_byte_length) is not int
            or not 1 <= self.artifact_byte_length <= MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
        ):
            raise SelectedC3SnapshotReadError("P2 audit artifact length is invalid")
        if self.terminal_state != "SUCCEEDED":
            raise SelectedC3SnapshotReadError("P2 audit terminal state is invalid")
        if self.provider_call_disposition != "CONFIRMED":
            raise SelectedC3SnapshotReadError(
                "P2 audit provider-call disposition is invalid"
            )
        if (
            type(self.canonical_artifact_path) is not str
            or not self.canonical_artifact_path
        ):
            raise SelectedC3SnapshotReadError("P2 audit artifact path is invalid")


class SelectedC3SnapshotPermit:
    """Sealed process-local proof of one successful Architecture-94 P2 read."""

    __slots__ = ("_nonce", "__weakref__")

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer is not _PERMIT_ISSUER:
            raise TypeError("selected C3 snapshot permits are issued by P2")
        self._nonce = object()

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("SelectedC3SnapshotPermit cannot be subclassed")

    def __copy__(self) -> object:
        raise TypeError("selected C3 snapshot permits cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("selected C3 snapshot permits cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("selected C3 snapshot permits cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("selected C3 snapshot permits cannot be pickled")

    def __getstate__(self) -> object:
        raise TypeError("selected C3 snapshot permits cannot be serialized")

    def __repr__(self) -> str:
        return "SelectedC3SnapshotPermit(<sealed>)"


@dataclass(frozen=True, slots=True)
class SelectedC3SnapshotReadResult:
    """P2 audit evidence and retained verified data for later P4 composition."""

    audit: SelectedC3SnapshotAuditEvidence
    permit: SelectedC3SnapshotPermit
    snapshot_bytes: bytes
    verification: DailySnapshotVerificationResult
    provider_call_performed: bool = False
    database_mutation_performed: bool = False

    def __post_init__(self) -> None:
        if type(self.audit) is not SelectedC3SnapshotAuditEvidence:
            raise SelectedC3SnapshotReadError("P2 result audit evidence is invalid")
        if type(self.permit) is not SelectedC3SnapshotPermit:
            raise SelectedC3SnapshotReadError("P2 result permit is invalid")
        if type(self.snapshot_bytes) is not bytes or not self.snapshot_bytes:
            raise SelectedC3SnapshotReadError("P2 result snapshot bytes are invalid")
        if type(self.verification) is not DailySnapshotVerificationResult:
            raise SelectedC3SnapshotReadError("P2 verification result is invalid")
        if (
            self.provider_call_performed is not False
            or self.database_mutation_performed is not False
        ):
            raise SelectedC3SnapshotReadError(
                "P2 result cannot claim a mutation or effect"
            )
        if (
            not self.verification.passed
            or self.verification.diagnostics != ()
            or self.verification.snapshot is None
            or len(self.snapshot_bytes) != self.audit.artifact_byte_length
            or hashlib.sha256(self.snapshot_bytes).hexdigest()
            != self.audit.artifact_sha256
            or self.verification.sha256 != self.audit.artifact_sha256
            or self.verification.byte_length != self.audit.artifact_byte_length
            or self.verification.snapshot.snapshot_id != self.audit.snapshot_id
        ):
            raise SelectedC3SnapshotReadError("P2 result evidence is inconsistent")
        try:
            exact_snapshot_bytes = serialize_daily_snapshot(self.verification.snapshot)
        except BaseException as error:
            raise SelectedC3SnapshotReadError(
                "P2 result verified snapshot cannot be serialized"
            ) from error
        if exact_snapshot_bytes != self.snapshot_bytes:
            raise SelectedC3SnapshotReadError(
                "P2 result snapshot bytes are inconsistent"
            )


class _ArtifactReadApi(Protocol):
    def open_final_artifact(self, path: str) -> NativeOpenedArtifact: ...

    def read_artifact_file(self, handle: int, max_bytes: int) -> bytes: ...

    def close_handle(self, handle: int) -> None: ...


@dataclass(frozen=True, slots=True)
class _PermitBinding:
    audit_ref: weakref.ReferenceType[SelectedC3SnapshotAuditEvidence]
    core_ref: weakref.ReferenceType[object]
    reader_ref: weakref.ReferenceType[object]
    registration: _ReadCoreRegistration
    authority_identity: tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class _SuccessfulReadBinding:
    audit_ref: weakref.ReferenceType[SelectedC3SnapshotAuditEvidence]
    core_ref: weakref.ReferenceType[object]
    reader_ref: weakref.ReferenceType[object]
    registration: _ReadCoreRegistration
    authority_identity: tuple[str, str, str]


class _SuccessfulReadIssuance:
    """Opaque one-shot proof that one exact P2 audit completed verification."""

    __slots__ = ("__weakref__",)

    def __init__(self) -> None:
        raise TypeError("successful P2 read issuances are created by verification")


@dataclass(frozen=True, slots=True)
class _ReadCoreRegistration:
    reader_ref: weakref.ReferenceType[object]
    authority: object | None
    provenance: object


_PERMIT_ISSUER = object()
_PERMIT_REGISTRY: weakref.WeakKeyDictionary[
    SelectedC3SnapshotPermit, _PermitBinding
] = weakref.WeakKeyDictionary()
_SUCCESSFUL_READ_ISSUANCES: weakref.WeakKeyDictionary[
    _SuccessfulReadIssuance, _SuccessfulReadBinding
] = weakref.WeakKeyDictionary()
_PERMIT_REGISTRY_LOCK = threading.Lock()
_DISPOSABLE_AUTHORITY_ISSUER = object()
_PRODUCTION_READER_CONSTRUCTOR = object()
_PRODUCTION_READER_INITIALIZING = object()
_PRODUCTION_CORE_PROVENANCE = object()
_DISPOSABLE_CORE_PROVENANCE = object()
_PRODUCTION_READER_CONSTRUCTIONS: weakref.WeakKeyDictionary[object, object] = (
    weakref.WeakKeyDictionary()
)
_CORE_REGISTRY: weakref.WeakKeyDictionary[object, _ReadCoreRegistration] = (
    weakref.WeakKeyDictionary()
)


def _issue_permit(
    audit: SelectedC3SnapshotAuditEvidence,
    *,
    core: object,
    issuance: _SuccessfulReadIssuance | None = None,
) -> SelectedC3SnapshotPermit:
    with _PERMIT_REGISTRY_LOCK:
        registration = _CORE_REGISTRY.get(core)
        if not _registration_is_exact(core, registration):
            raise SelectedC3SnapshotReadError(
                "selected C3 snapshot core provenance is invalid"
            )
        reader = registration.reader_ref()
        assert reader is not None
        successful_read = (
            _SUCCESSFUL_READ_ISSUANCES.pop(issuance, None)
            if type(issuance) is _SuccessfulReadIssuance
            else None
        )
        if (
            successful_read is None
            or successful_read.audit_ref() is not audit
            or successful_read.core_ref() is not core
            or successful_read.reader_ref() is not reader
            or successful_read.registration is not registration
        ):
            raise SelectedC3SnapshotReadError(
                "selected C3 snapshot successful-read issuance is invalid"
            )
        permit = SelectedC3SnapshotPermit(_issuer=_PERMIT_ISSUER)
        binding = _PermitBinding(
            weakref.ref(audit),
            weakref.ref(core),
            weakref.ref(reader),
            registration,
            successful_read.authority_identity,
        )
        _PERMIT_REGISTRY[permit] = binding
    return permit


def _registration_is_exact(
    core: object, registration: _ReadCoreRegistration | None
) -> bool:
    if type(core) is not _SelectedC3SnapshotReadCore or registration is None:
        return False
    reader = registration.reader_ref()
    if registration.provenance is _PRODUCTION_CORE_PROVENANCE:
        return bool(
            type(reader) is WindowsSelectedC3SnapshotReadAuthority
            and reader._core is core
            and reader._authority is registration.authority
            and core._authority is registration.authority
            and core._production is True
        )
    if registration.provenance is _DISPOSABLE_CORE_PROVENANCE:
        return bool(
            type(reader) is DisposableSelectedC3SnapshotReadAuthorityForTest
            and reader._core is core
            and registration.authority is None
            and core._authority is None
            and core._production is False
        )
    return False


def _binding_is_exact(
    binding: _PermitBinding | None,
    audit: SelectedC3SnapshotAuditEvidence,
    provenance: object,
) -> bool:
    if binding is None or binding.audit_ref() is not audit:
        return False
    core = binding.core_ref()
    reader = binding.reader_ref()
    registration = binding.registration
    return bool(
        core is not None
        and reader is registration.reader_ref()
        and registration.provenance is provenance
        and _CORE_REGISTRY.get(core) is registration
        and _registration_is_exact(core, registration)
    )


def require_selected_c3_snapshot_permit(
    permit: SelectedC3SnapshotPermit,
    audit: SelectedC3SnapshotAuditEvidence,
) -> SelectedC3SnapshotPermit:
    """Require exact process-local production P2 provenance and audit binding."""

    if type(permit) is not SelectedC3SnapshotPermit:
        raise SelectedC3SnapshotReadError("selected C3 snapshot permit type is invalid")
    if type(audit) is not SelectedC3SnapshotAuditEvidence:
        raise SelectedC3SnapshotReadError("selected C3 snapshot audit type is invalid")
    with _PERMIT_REGISTRY_LOCK:
        binding = _PERMIT_REGISTRY.get(permit)
        valid = _binding_is_exact(binding, audit, _PRODUCTION_CORE_PROVENANCE)
    if not valid:
        raise SelectedC3SnapshotReadError(
            "selected C3 snapshot permit provenance is invalid"
        )
    return permit


def require_disposable_selected_c3_snapshot_permit_for_test(
    permit: SelectedC3SnapshotPermit,
    audit: SelectedC3SnapshotAuditEvidence,
) -> SelectedC3SnapshotPermit:
    """Validate only explicitly disposable P2 permit provenance in tests."""

    if type(permit) is not SelectedC3SnapshotPermit:
        raise SelectedC3SnapshotReadError("selected C3 snapshot permit type is invalid")
    with _PERMIT_REGISTRY_LOCK:
        binding = _PERMIT_REGISTRY.get(permit)
        valid = _binding_is_exact(binding, audit, _DISPOSABLE_CORE_PROVENANCE)
    if not valid:
        raise SelectedC3SnapshotReadError(
            "disposable selected C3 snapshot permit provenance is invalid"
        )
    return permit


def require_selected_c3_snapshot_matches_authority(
    permit: SelectedC3SnapshotPermit,
    audit: SelectedC3SnapshotAuditEvidence,
    authority: ValidatedProductionAuthority,
) -> None:
    """Purely reconcile a production P2 read with the consuming C1 authority."""

    require_validated_production_authority(authority)
    require_selected_c3_snapshot_permit(permit, audit)
    with _PERMIT_REGISTRY_LOCK:
        binding = _PERMIT_REGISTRY.get(permit)
        if (
            not _binding_is_exact(binding, audit, _PRODUCTION_CORE_PROVENANCE)
            or binding.registration.authority != authority
            or binding.authority_identity
            != (
                authority.machine_authority_id,
                authority.approved_account_sid,
                authority.authority_epoch_id,
            )
        ):
            raise SelectedC3SnapshotReadError("P2 read does not match C1 authority")


def require_disposable_selected_c3_snapshot_matches_identity_for_test(
    permit: SelectedC3SnapshotPermit,
    audit: SelectedC3SnapshotAuditEvidence,
    *,
    machine_authority_id: str,
    approved_trading_sid: str,
    authority_epoch_id: str,
) -> None:
    """Reconcile retained disposable database facts without production authority."""

    require_disposable_selected_c3_snapshot_permit_for_test(permit, audit)
    with _PERMIT_REGISTRY_LOCK:
        binding = _PERMIT_REGISTRY.get(permit)
        if not _binding_is_exact(
            binding, audit, _DISPOSABLE_CORE_PROVENANCE
        ) or binding.authority_identity != (
            machine_authority_id,
            approved_trading_sid,
            authority_epoch_id,
        ):
            raise SelectedC3SnapshotReadError("disposable P2 read identity mismatch")


class _SelectedC3SnapshotReadCore:
    __slots__ = (
        "_artifact_api",
        "_authority",
        "_authority_epoch_id",
        "_capture_output_root",
        "_database_path",
        "_expected_operation",
        "_expected_provider",
        "_production",
        "_sqlite_vfs",
        "__weakref__",
    )

    def __init__(
        self,
        *,
        authority: ValidatedProductionAuthority | None,
        database_path: str,
        capture_output_root: str,
        artifact_api: _ArtifactReadApi,
        production: bool,
        sqlite_vfs: str | None,
        authority_epoch_id: str,
        expected_provider: str,
        expected_operation: str,
    ) -> None:
        self._authority = authority
        self._database_path = database_path
        self._capture_output_root = capture_output_root
        self._artifact_api = artifact_api
        self._production = production
        self._sqlite_vfs = sqlite_vfs
        self._authority_epoch_id = authority_epoch_id
        self._expected_provider = expected_provider
        self._expected_operation = expected_operation

    def read_selected_snapshot(
        self,
        selection_id: str,
        *,
        artifact_path: str | Path | None = None,
    ) -> SelectedC3SnapshotReadResult:
        canonical_selection_id = _canonical_uuid_text(selection_id, "selection ID")
        durable = self._read_durable_selection(canonical_selection_id)
        snapshot_id = _canonical_uuid_text(durable.snapshot_id, "snapshot ID")
        final_name = f"daily-market-data-snapshot-{snapshot_id}.json"
        candidate_path = self._canonical_candidate_path(final_name)
        if artifact_path is not None and str(artifact_path) != candidate_path:
            raise SelectedC3SnapshotReadError(
                "artifact transport hint is not the exact canonical candidate"
            )

        opened: NativeOpenedArtifact | None = None
        close_error: BaseException | None = None
        try:
            opened = self._artifact_api.open_final_artifact(candidate_path)
            if type(opened) is not NativeOpenedArtifact:
                raise SelectedC3SnapshotReadError(
                    "safe artifact open returned invalid evidence"
                )
            payload = self._artifact_api.read_artifact_file(
                opened.handle, MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
            )
            if (
                type(payload) is not bytes
                or not payload
                or len(payload) > MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
            ):
                raise SelectedC3SnapshotReadError(
                    "selected C3 artifact is empty, oversized, or unreadable"
                )
        except SelectedC3SnapshotReadError:
            raise
        except BaseException as error:
            raise SelectedC3SnapshotReadError(
                "selected C3 artifact could not be safely reopened"
            ) from error
        finally:
            if opened is not None:
                try:
                    self._artifact_api.close_handle(opened.handle)
                except BaseException as error:
                    close_error = error
        if close_error is not None:
            raise SelectedC3SnapshotReadError(
                "selected C3 artifact handle could not be closed"
            ) from close_error

        artifact_sha256 = hashlib.sha256(payload).hexdigest()
        if (
            artifact_sha256 != durable.artifact_sha256
            or artifact_sha256 != durable.terminal_snapshot_digest.hex()
            or artifact_sha256 != durable.selection_snapshot_digest.hex()
        ):
            raise SelectedC3SnapshotReadError(
                "selected C3 artifact digest does not reconcile"
            )
        identity = C3ArtifactIdentityEvidence(
            snapshot_id=UUID(snapshot_id),
            final_canonical_filename=final_name,
            artifact_sha256=artifact_sha256,
            artifact_byte_length=len(payload),
            native_file_identity=opened.identity,
        )
        if identity.sha256 != durable.artifact_identity_sha256:
            raise SelectedC3SnapshotReadError(
                "selected C3 artifact identity evidence does not reconcile"
            )

        calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
        verification = verify_daily_snapshot(
            payload,
            calendar,
            expected_sha256=artifact_sha256,
            expected_byte_length=len(payload),
        )
        if (
            not verification.passed
            or verification.diagnostics
            or verification.snapshot is None
            or verification.snapshot.snapshot_id != UUID(snapshot_id)
            or serialize_daily_snapshot(verification.snapshot) != payload
        ):
            raise SelectedC3SnapshotReadError(
                "selected C3 artifact failed strict daily-snapshot verification"
            )

        audit = SelectedC3SnapshotAuditEvidence(
            selection_id=UUID(canonical_selection_id),
            session_id=UUID(durable.session_id),
            attempt_id=UUID(durable.attempt_id),
            terminal_id=UUID(durable.terminal_id),
            snapshot_id=UUID(snapshot_id),
            artifact_sha256=artifact_sha256,
            artifact_byte_length=len(payload),
            artifact_identity_sha256=durable.artifact_identity_sha256,
            terminal_state=durable.terminal_state,
            provider_call_disposition=durable.provider_call_disposition,
            canonical_artifact_path=candidate_path,
        )
        issuance = object.__new__(_SuccessfulReadIssuance)
        with _PERMIT_REGISTRY_LOCK:
            registration = _CORE_REGISTRY.get(self)
            if not _registration_is_exact(self, registration):
                raise SelectedC3SnapshotReadError(
                    "selected C3 snapshot core provenance is invalid"
                )
            reader = registration.reader_ref()
            assert reader is not None
            _SUCCESSFUL_READ_ISSUANCES[issuance] = _SuccessfulReadBinding(
                weakref.ref(audit),
                weakref.ref(self),
                weakref.ref(reader),
                registration,
                durable.authority_identity,
            )
        permit = _issue_permit(
            audit,
            core=self,
            issuance=issuance,
        )
        return SelectedC3SnapshotReadResult(audit, permit, payload, verification)

    def _canonical_candidate_path(self, final_name: str) -> str:
        if self._production:
            return str(PureWindowsPath(self._capture_output_root) / final_name)
        return str(Path(self._capture_output_root) / final_name)

    def _open_connection(self) -> sqlite3.Connection:
        if self._production:
            if self._sqlite_vfs is None:
                raise SelectedC3SnapshotReadError("approved SQLite VFS is unavailable")
            return open_read_only_sqlite_connection(
                self._database_path, vfs=self._sqlite_vfs
            )
        return open_disposable_read_only_sqlite_connection(self._database_path)

    def _read_durable_selection(self, selection_id: str) -> _DurableSelection:
        connection = self._open_connection()
        initial_changes = connection.total_changes
        try:
            connection.execute("PRAGMA query_only = ON")
            query_only = connection.execute("PRAGMA query_only").fetchone()
            if query_only != (1,):
                raise SelectedC3SnapshotReadError("SQLite query-only mode is absent")
            connection.execute("BEGIN")
            if self._production:
                assert self._authority is not None
                require_open_connection_matches_validated_authority(
                    self._authority,
                    connection,
                    allow_active_transaction=True,
                )
            else:
                self._validate_disposable_database(connection)
            durable = self._query_selected_lineage(connection, selection_id)
            if connection.total_changes != initial_changes:
                raise SelectedC3SnapshotReadError(
                    "P2 read-only SQLite boundary observed a mutation"
                )
            connection.rollback()
            return durable
        except SelectedC3SnapshotReadError:
            if connection.in_transaction:
                connection.rollback()
            raise
        except BaseException as error:
            if connection.in_transaction:
                connection.rollback()
            raise SelectedC3SnapshotReadError(
                "selected C3 durable evidence is invalid"
            ) from error
        finally:
            connection.close()

    def _validate_disposable_database(self, connection: sqlite3.Connection) -> None:
        validate_production_schema(connection)
        validate_persisted_evidence_digests(connection)
        rows = connection.execute(
            """
            SELECT authority_epoch_id, provider_id, permitted_provider_operation,
                   authority_policy_version, claim_policy_version,
                   production_schema_id, production_schema_version,
                   production_schema_digest, singleton_key
            FROM authority_metadata
            """
        ).fetchall()
        expected = (
            self._authority_epoch_id,
            self._expected_provider,
            self._expected_operation,
            POLICY,
            CLAIM_POLICY,
            PRODUCTION_SCHEMA_ID,
            PRODUCTION_SCHEMA_VERSION,
            bytes.fromhex(PRODUCTION_SCHEMA_ARTIFACT_SHA256),
            1,
        )
        if rows != [expected]:
            raise SelectedC3SnapshotReadError(
                "disposable authority identity is unsupported"
            )

    def _query_selected_lineage(
        self, connection: sqlite3.Connection, selection_id: str
    ) -> _DurableSelection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(_SELECTED_LINEAGE_SQL, (selection_id,)).fetchall()
        if len(rows) != 1:
            raise SelectedC3SnapshotReadError(
                "exactly one selected C3 lineage is required"
            )
        row = rows[0]
        uuid_fields = (
            "selection_id",
            "session_id",
            "attempt_id",
            "claim_id",
            "reservation_id",
            "execution_id",
            "terminal_id",
        )
        for field_name in uuid_fields:
            _canonical_uuid_text(row[field_name], field_name)
        _canonical_uuid_text(row["authority_epoch_id"], "authority epoch ID")
        if (
            row["authority_epoch_id"] != self._authority_epoch_id
            or row["session_state"] != "SUCCESS_SELECTED"
            or row["attempt_state"] != "SUCCESS_SELECTED"
            or row["claim_state"] != "COMMITTED"
            or row["reservation_state"] != "TERMINAL_RECORDED"
            or row["execution_phase"] != "TERMINAL_RECORDED"
            or row["terminal_state"] != "SUCCEEDED"
            or row["provider_call_disposition"] != "CONFIRMED"
        ):
            raise SelectedC3SnapshotReadError(
                "selected C3 durable lineage state is invalid"
            )
        if (
            row["session_schema"] != 1
            or row["attempt_schema"] != 1
            or row["claim_schema"] != 1
            or row["reservation_schema"] != 1
            or row["execution_schema"] != 1
            or row["terminal_schema"] != 1
            or row["selection_schema"] != 1
            or row["authority_policy_version"] != POLICY
            or row["claim_policy_version"] != CLAIM_POLICY
            or row["claim_policy_row"] != CLAIM_POLICY
            or row["attempt_policy_version"] != CLAIM_POLICY
            or row["reservation_authority_policy"] != POLICY
            or row["reservation_claim_policy"] != CLAIM_POLICY
            or row["execution_authority_policy"] != POLICY
            or row["application_release_version"] != RELEASE
            or row["execution_release_version"] != RELEASE
            or row["terminal_policy_version"] != TERMINAL_POLICY
            or row["selection_policy_version"] != SELECTION_POLICY
        ):
            raise SelectedC3SnapshotReadError(
                "selected C3 durable lineage schema or policy is invalid"
            )
        if (
            row["attempt_provider_id"] != self._expected_provider
            or row["claim_provider_id"] != self._expected_provider
            or row["attempt_operation"] != self._expected_operation
            or row["claim_operation"] != self._expected_operation
            or row["provider_call_budget"] != 1
            or row["claim_provider_call_budget"] != 1
        ):
            raise SelectedC3SnapshotReadError("selected C3 provider lineage is invalid")
        request_digests = tuple(
            row[field]
            for field in (
                "session_request_digest",
                "attempt_request_digest",
                "claim_request_digest",
                "reservation_request_digest",
                "terminal_request_digest",
            )
        )
        if (
            any(
                type(value) is not bytes or len(value) != 32
                for value in request_digests
            )
            or len(set(request_digests)) != 1
        ):
            raise SelectedC3SnapshotReadError(
                "selected C3 request-digest lineage is invalid"
            )
        request_payloads = tuple(
            row[field]
            for field in (
                "session_request_json",
                "attempt_request_json",
                "claim_request_json",
            )
        )
        if (
            any(type(value) is not bytes or not value for value in request_payloads)
            or len(set(request_payloads)) != 1
            or hashlib.sha256(request_payloads[0]).digest() != request_digests[0]
        ):
            raise SelectedC3SnapshotReadError(
                "selected C3 request evidence does not reconcile"
            )
        for value, digest, label in (
            (
                row["process_intent_json"],
                row["process_intent_digest"],
                "process-intent",
            ),
            (
                row["resume_intent_json"],
                row["resume_intent_digest"],
                "resume-intent",
            ),
            (row["post_resume_json"], row["post_resume_digest"], "post-resume"),
            (row["cleanup_json"], row["cleanup_digest"], "cleanup"),
        ):
            if (
                type(value) is not bytes
                or not value
                or type(digest) is not bytes
                or len(digest) != 32
                or hashlib.sha256(value).digest() != digest
            ):
                raise SelectedC3SnapshotReadError(
                    f"selected C3 {label} evidence pair is invalid"
                )
        expected_process_intent = _canonical_json(
            {
                "authority_policy_version": POLICY,
                "claim_policy_version": CLAIM_POLICY,
                "launch_reservation_id": row["reservation_id"],
                "process_operation": "CreateProcessW",
                "request_digest": request_digests[0].hex(),
                "schema": 1,
            }
        )
        expected_resume_intent = _canonical_json(
            {
                "execution_id": row["execution_id"],
                "resume_operation": "ResumeThread",
                "schema": 1,
            }
        )
        expected_post_resume = _canonical_json(
            {
                "execution_id": row["execution_id"],
                "resume_intent_digest": row["resume_intent_digest"].hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        if (
            row["process_intent_json"] != expected_process_intent
            or row["resume_intent_json"] != expected_resume_intent
            or row["post_resume_json"] != expected_post_resume
        ):
            raise SelectedC3SnapshotReadError(
                "selected C3 process/resume evidence material is invalid"
            )
        terminal_snapshot_digest = row["terminal_snapshot_digest"]
        selection_snapshot_digest = row["selection_snapshot_digest"]
        if (
            type(terminal_snapshot_digest) is not bytes
            or len(terminal_snapshot_digest) != 32
            or type(selection_snapshot_digest) is not bytes
            or len(selection_snapshot_digest) != 32
            or terminal_snapshot_digest != selection_snapshot_digest
        ):
            raise SelectedC3SnapshotReadError(
                "selection and terminal snapshot digests do not reconcile"
            )

        validate_selected_c3_lineage_for_read(
            selection_id=row["selection_id"],
            session_id=row["session_id"],
            attempt_id=row["attempt_id"],
            attempt_ordinal=row["attempt_ordinal"],
            claim_id=row["claim_id"],
            reservation_id=row["reservation_id"],
            execution_id=row["execution_id"],
            terminal_id=row["terminal_id"],
            provider_id=row["attempt_provider_id"],
            permitted_provider_operation=row["attempt_operation"],
            provider_call_budget=row["provider_call_budget"],
            attempt_policy_version=row["attempt_policy_version"],
            claim_policy_version=row["claim_policy_version"],
            application_release_version=row["application_release_version"],
            authority_policy_version=row["authority_policy_version"],
            terminal_policy_version=row["terminal_policy_version"],
            selection_policy_version=row["selection_policy_version"],
            machine_authority_id=row["machine_authority_id"],
            authority_epoch_id=row["authority_epoch_id"],
            request_json=request_payloads[0],
            request_digest=request_digests[0],
            process_intent_digest=row["process_intent_digest"],
            process_creation_json=row["process_creation_json"],
            process_creation_digest=row["process_creation_digest"],
            job_object_json=row["job_object_json"],
            job_object_digest=row["job_object_digest"],
            resume_authorization_json=row["resume_authorization_json"],
            resume_authorization_digest=row["resume_authorization_digest"],
            allocation_evidence_json=row["allocation_evidence_json"],
            allocation_evidence_digest=row["allocation_evidence_digest"],
            attempt_evidence_json=row["attempt_evidence_json"],
            attempt_evidence_digest=row["attempt_evidence_digest"],
            claim_evidence_json=row["claim_evidence_json"],
            claim_evidence_digest=row["claim_evidence_digest"],
            reservation_evidence_json=row["reservation_evidence_json"],
            reservation_evidence_digest=row["reservation_evidence_digest"],
            selection_evidence_json=row["selection_evidence_json"],
            selection_evidence_digest=row["selection_evidence_digest"],
        )
        terminal = validate_successful_c3_terminal_for_read(
            connection,
            terminal_id=row["terminal_id"],
            terminal_state=row["terminal_state"],
            provider_call_disposition=row["provider_call_disposition"],
            snapshot_digest=terminal_snapshot_digest,
            evidence_json=row["terminal_evidence_json"],
            evidence_digest=row["terminal_evidence_digest"],
            diagnostics_json=row["diagnostics_json"],
            diagnostics_digest=row["diagnostics_digest"],
            session_id=row["session_id"],
            attempt_id=row["attempt_id"],
            claim_id=row["claim_id"],
            reservation_id=row["reservation_id"],
            execution_id=row["execution_id"],
            terminal_policy_version=row["terminal_policy_version"],
        )
        if terminal.artifact_sha256 != terminal_snapshot_digest.hex():
            raise SelectedC3SnapshotReadError(
                "terminal artifact SHA-256 does not bind snapshot digest"
            )
        return _DurableSelection(
            authority_identity=(
                row["machine_authority_id"],
                row["approved_account_sid"],
                row["authority_epoch_id"],
            ),
            session_id=row["session_id"],
            attempt_id=row["attempt_id"],
            terminal_id=row["terminal_id"],
            terminal_state=row["terminal_state"],
            provider_call_disposition=row["provider_call_disposition"],
            terminal_snapshot_digest=terminal_snapshot_digest,
            selection_snapshot_digest=selection_snapshot_digest,
            snapshot_id=terminal.snapshot_id,
            artifact_sha256=terminal.artifact_sha256,
            artifact_identity_sha256=terminal.artifact_identity_sha256,
        )


@dataclass(frozen=True, slots=True)
class _DurableSelection:
    authority_identity: tuple[str, str, str]
    session_id: str
    attempt_id: str
    terminal_id: str
    terminal_state: str
    provider_call_disposition: str
    terminal_snapshot_digest: bytes
    selection_snapshot_digest: bytes
    snapshot_id: str
    artifact_sha256: str
    artifact_identity_sha256: str


class WindowsSelectedC3SnapshotReadAuthority:
    """Sealed production P2 authority created only from genuine C1 authority."""

    __slots__ = ("_authority", "_core", "__weakref__")

    def __new__(
        cls, authority: ValidatedProductionAuthority
    ) -> WindowsSelectedC3SnapshotReadAuthority:
        del authority
        if cls is not WindowsSelectedC3SnapshotReadAuthority:
            raise TypeError(
                "WindowsSelectedC3SnapshotReadAuthority cannot be subclassed"
            )
        reader = super().__new__(cls)
        with _PERMIT_REGISTRY_LOCK:
            _PRODUCTION_READER_CONSTRUCTIONS[reader] = _PRODUCTION_READER_CONSTRUCTOR
        return reader

    def __init__(self, authority: ValidatedProductionAuthority) -> None:
        with _PERMIT_REGISTRY_LOCK:
            if (
                _PRODUCTION_READER_CONSTRUCTIONS.get(self)
                is not _PRODUCTION_READER_CONSTRUCTOR
            ):
                raise SelectedC3SnapshotReadError(
                    "production P2 reader construction provenance is invalid"
                )
            _PRODUCTION_READER_CONSTRUCTIONS[self] = _PRODUCTION_READER_INITIALIZING
        try:
            authority = require_validated_production_authority(authority)
            sqlite_build = load_approved_sqlite_authority_build()
            if sqlite_build.digest.hex() != authority.sqlite_build_manifest_digest:
                raise SelectedC3SnapshotReadError(
                    "approved SQLite build does not match production authority"
                )
            self._authority = authority
            core = _SelectedC3SnapshotReadCore(
                authority=authority,
                database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
                capture_output_root=str(PRODUCTION_AUTHORITY_PATHS.capture_output),
                artifact_api=CtypesWindowsEffectfulCaptureNativeApi(),
                production=True,
                sqlite_vfs=sqlite_build.vfs,
                authority_epoch_id=authority.authority_epoch_id,
                expected_provider=authority.provider_id,
                expected_operation=authority.permitted_provider_operation,
            )
            self._core = core
            registration = _ReadCoreRegistration(
                weakref.ref(self), authority, _PRODUCTION_CORE_PROVENANCE
            )
            with _PERMIT_REGISTRY_LOCK:
                if (
                    _PRODUCTION_READER_CONSTRUCTIONS.pop(self, None)
                    is not _PRODUCTION_READER_INITIALIZING
                ):
                    raise SelectedC3SnapshotReadError(
                        "production P2 reader construction provenance changed"
                    )
                _CORE_REGISTRY[core] = registration
        except BaseException:
            with _PERMIT_REGISTRY_LOCK:
                _PRODUCTION_READER_CONSTRUCTIONS.pop(self, None)
                core = getattr(self, "_core", None)
                if core is not None:
                    _CORE_REGISTRY.pop(core, None)
            raise

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("WindowsSelectedC3SnapshotReadAuthority cannot be subclassed")

    def read_selected_snapshot(
        self,
        selection_id: str,
        *,
        artifact_path: str | Path | None = None,
    ) -> SelectedC3SnapshotReadResult:
        return self._core.read_selected_snapshot(
            selection_id, artifact_path=artifact_path
        )


class DisposableSelectedC3SnapshotReadAuthorityForTest:
    """Explicit offline disposable P2 seam that never mints production provenance."""

    __slots__ = ("_core", "__weakref__")

    def __init__(self, *, _issuer: object | None = None, core: object = None) -> None:
        if _issuer is not _DISPOSABLE_AUTHORITY_ISSUER or type(core) is not (
            _SelectedC3SnapshotReadCore
        ):
            raise TypeError("disposable P2 authority requires the reviewed test opener")
        self._core = core
        registration = _ReadCoreRegistration(
            weakref.ref(self), None, _DISPOSABLE_CORE_PROVENANCE
        )
        with _PERMIT_REGISTRY_LOCK:
            if core in _CORE_REGISTRY:
                raise TypeError("disposable P2 core is already registered")
            _CORE_REGISTRY[core] = registration

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError(
            "DisposableSelectedC3SnapshotReadAuthorityForTest cannot be subclassed"
        )

    def read_selected_snapshot(
        self,
        selection_id: str,
        *,
        artifact_path: str | Path | None = None,
    ) -> SelectedC3SnapshotReadResult:
        return self._core.read_selected_snapshot(
            selection_id, artifact_path=artifact_path
        )


def open_disposable_selected_c3_snapshot_read_authority_for_test(
    *,
    database_path: str | Path,
    capture_output_root: str | Path,
    artifact_api: _ArtifactReadApi,
    authority_epoch_id: str,
    provider_id: str,
    permitted_provider_operation: str,
) -> DisposableSelectedC3SnapshotReadAuthorityForTest:
    """Open an explicit file-backed disposable P2 authority for offline tests."""

    path = Path(database_path)
    root = Path(capture_output_root)
    if not path.is_file() or not root.is_dir():
        raise SelectedC3SnapshotReadError("disposable P2 paths are unavailable")
    required = ("open_final_artifact", "read_artifact_file", "close_handle")
    if not all(callable(getattr(artifact_api, name, None)) for name in required):
        raise TypeError("disposable P2 artifact API is invalid")
    for value, field in (
        (authority_epoch_id, "authority epoch"),
        (provider_id, "provider ID"),
        (permitted_provider_operation, "provider operation"),
    ):
        if type(value) is not str or not value:
            raise TypeError(f"disposable P2 {field} is invalid")
    core = _SelectedC3SnapshotReadCore(
        authority=None,
        database_path=str(path),
        capture_output_root=str(root),
        artifact_api=artifact_api,
        production=False,
        sqlite_vfs=None,
        authority_epoch_id=authority_epoch_id,
        expected_provider=provider_id,
        expected_operation=permitted_provider_operation,
    )
    return DisposableSelectedC3SnapshotReadAuthorityForTest(
        _issuer=_DISPOSABLE_AUTHORITY_ISSUER, core=core
    )


def _canonical_uuid_text(value: object, field: str) -> str:
    if type(value) is not str:
        raise SelectedC3SnapshotReadError(f"{field} must be canonical UUID text")
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        raise SelectedC3SnapshotReadError(
            f"{field} must be canonical UUID text"
        ) from None
    if str(parsed) != value:
        raise SelectedC3SnapshotReadError(f"{field} must be canonical UUID text")
    return value


def _is_sha256(value: object) -> bool:
    return bool(
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


_SELECTED_LINEAGE_SQL = """
SELECT
    ss.selection_id AS selection_id,
    ss.selection_schema AS selection_schema,
    ss.selection_policy_version AS selection_policy_version,
    ss.snapshot_digest AS selection_snapshot_digest,
    ss.selection_evidence_json AS selection_evidence_json,
    ss.selection_evidence_digest AS selection_evidence_digest,
    s.session_id AS session_id,
    s.authority_epoch_id AS authority_epoch_id,
    m.machine_authority_id AS machine_authority_id,
    m.approved_account_sid AS approved_account_sid,
    s.session_schema AS session_schema,
    s.authority_policy_version AS authority_policy_version,
    s.claim_policy_version AS claim_policy_version,
    s.state AS session_state,
    s.request_json AS session_request_json,
    s.request_digest AS session_request_digest,
    a.attempt_id AS attempt_id,
    a.ordinal AS attempt_ordinal,
    a.provider_id AS attempt_provider_id,
    a.permitted_provider_operation AS attempt_operation,
    a.provider_call_budget AS provider_call_budget,
    a.request_json AS attempt_request_json,
    a.request_digest AS attempt_request_digest,
    a.attempt_schema AS attempt_schema,
    a.attempt_policy_version AS attempt_policy_version,
    a.allocation_evidence_json AS allocation_evidence_json,
    a.allocation_evidence_digest AS allocation_evidence_digest,
    a.attempt_evidence_json AS attempt_evidence_json,
    a.attempt_evidence_digest AS attempt_evidence_digest,
    a.state AS attempt_state,
    c.claim_id AS claim_id,
    c.claim_schema AS claim_schema,
    c.claim_policy_version AS claim_policy_row,
    c.provider_id AS claim_provider_id,
    c.permitted_provider_operation AS claim_operation,
    c.provider_call_budget AS claim_provider_call_budget,
    c.request_json AS claim_request_json,
    c.request_digest AS claim_request_digest,
    c.claim_evidence_json AS claim_evidence_json,
    c.claim_evidence_digest AS claim_evidence_digest,
    c.state AS claim_state,
    r.launch_reservation_id AS reservation_id,
    r.launch_reservation_schema AS reservation_schema,
    r.application_release_version AS application_release_version,
    r.authority_policy_version AS reservation_authority_policy,
    r.claim_policy_version AS reservation_claim_policy,
    r.request_digest AS reservation_request_digest,
    r.reservation_evidence_json AS reservation_evidence_json,
    r.reservation_evidence_digest AS reservation_evidence_digest,
    r.process_intent_json AS process_intent_json,
    r.process_intent_digest AS process_intent_digest,
    r.reservation_state AS reservation_state,
    e.launch_execution_id AS execution_id,
    e.launch_schema AS execution_schema,
    e.application_release_version AS execution_release_version,
    e.authority_policy_version AS execution_authority_policy,
    e.phase AS execution_phase,
    e.process_creation_json AS process_creation_json,
    e.process_creation_digest AS process_creation_digest,
    e.job_object_json AS job_object_json,
    e.job_object_digest AS job_object_digest,
    e.resume_authorization_json AS resume_authorization_json,
    e.resume_authorization_digest AS resume_authorization_digest,
    e.resume_intent_json AS resume_intent_json,
    e.resume_intent_digest AS resume_intent_digest,
    e.post_resume_json AS post_resume_json,
    e.post_resume_digest AS post_resume_digest,
    e.cleanup_json AS cleanup_json,
    e.cleanup_digest AS cleanup_digest,
    t.terminal_id AS terminal_id,
    t.terminal_schema AS terminal_schema,
    t.terminal_policy_version AS terminal_policy_version,
    t.terminal_state AS terminal_state,
    t.provider_call_disposition AS provider_call_disposition,
    t.request_digest AS terminal_request_digest,
    t.evidence_json AS terminal_evidence_json,
    t.evidence_digest AS terminal_evidence_digest,
    t.snapshot_digest AS terminal_snapshot_digest,
    t.sanitized_diagnostics_json AS diagnostics_json,
    t.sanitized_diagnostics_digest AS diagnostics_digest
FROM session_selections AS ss
JOIN sessions AS s
  ON s.session_id = ss.session_id
JOIN authority_metadata AS m
  ON m.authority_epoch_id = s.authority_epoch_id
 AND m.singleton_key = 1
JOIN terminals AS t
  ON t.terminal_id = ss.terminal_id
JOIN launch_reservations AS r
  ON r.launch_reservation_id = t.launch_reservation_id
JOIN provider_call_claims AS c
  ON c.claim_id = r.claim_id
JOIN attempts AS a
  ON a.attempt_id = c.attempt_id
 AND a.session_id = s.session_id
JOIN launch_executions AS e
  ON e.launch_reservation_id = r.launch_reservation_id
WHERE ss.selection_id = ?
"""
