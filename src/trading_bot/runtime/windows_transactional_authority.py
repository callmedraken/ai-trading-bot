"""Reviewed Windows transactional authority service.

This module owns the Architecture-77 durable state machine and its narrow
external-effect boundary.  It is intentionally inert in C2: no provider,
credential, process, scheduling, or brokerage adapter is supplied for
production.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import sqlite3
import threading
import uuid
import weakref
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from functools import wraps
from pathlib import Path
from typing import Any, Protocol, Self

from trading_bot.domain import Symbol
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    MAX_DAILY_SNAPSHOT_SYMBOLS,
)
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_mutex import GlobalLifecycleMutex
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    SchemaValidationError,
    configure_trusted_schema_off,
    require_evidence_digest,
)
from trading_bot.runtime.windows_authority_sqlite import (
    configure_and_validate_authority_sqlite_connection,
    open_writable_authority_sqlite_connection,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_open_connection_matches_validated_authority,
    require_validated_production_authority,
)

NAMESPACE = uuid.UUID("7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012")
PROVIDER = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id
OPERATION = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
POLICY = "authority-policy/v1"
CLAIM_POLICY = "claim-policy/v1"
RELEASE = "release/v1"
TERMINAL_POLICY = "terminal-policy/v1"
SELECTION_POLICY = "selection-policy/v1"
RECOVERY_POLICY = "recovery-policy/v1"
TIMESTAMP = "2026-01-01T00:00:00Z"
PROCESS_INTENT_TIMESTAMP = "2026-01-01T00:00:30Z"
PROCESS_CREATED_TIMESTAMP = "2026-01-01T00:01:00Z"
RESUME_INTENT_TIMESTAMP = "2026-01-01T00:01:30Z"
PROCESS_FAILURE_TIMESTAMP = "2026-01-01T00:02:00Z"
MANUAL_REVIEW_TIMESTAMP = "2026-01-01T00:03:00Z"
TERMINAL_TIMESTAMP = "2026-01-01T00:04:00Z"
SELECTION_TIMESTAMP = "2026-01-01T00:05:00Z"
CLOSE_TIMESTAMP = "2026-01-01T00:06:00Z"
CAPTURE_REQUEST_FIELDS = frozenset(
    {
        "bar_interval",
        "child_operation_version",
        "ordered_universe",
        "output_policy_version",
        "permitted_provider_operation",
        "provider_id",
        "request_limit",
        "request_window_end_date",
        "request_window_start_date",
        "target_session_date",
    }
)


class ExternalAuthorityBoundaryUnavailable(WindowsAuthorityError):
    """C2 has no production provider/process side-effect adapter."""


class TransactionalAuthorityLifecycle:
    """Shared admission/quiescence state for one disposable test lifecycle."""

    __slots__ = (
        "_active_operations",
        "_close_error",
        "_close_complete",
        "_quiescing_operations",
        "_state",
        "_state_lock",
        "_drained",
    )

    def __init__(self) -> None:
        self._state_lock = threading.Lock()
        self._state = "OPEN"
        self._active_operations = 0
        self._quiescing_operations = 0
        self._drained = threading.Event()
        self._drained.set()
        self._close_complete = threading.Event()
        self._close_error: BaseException | None = None

    def _closed_error(self) -> BaseException:
        return self._close_error or ExternalAuthorityBoundaryUnavailable(
            "transactional authority lifecycle is closed"
        )

    def require_open(self) -> None:
        with self._state_lock:
            if self._state != "OPEN":
                raise self._closed_error()

    @contextmanager
    def admit(self, *, wait_for_close: bool = True) -> Iterator[None]:
        with self._state_lock:
            if self._state != "OPEN":
                raise self._closed_error()
            self._active_operations += 1
            if wait_for_close:
                if self._quiescing_operations == 0:
                    self._drained.clear()
                self._quiescing_operations += 1
        try:
            yield
        finally:
            with self._state_lock:
                self._active_operations -= 1
                if wait_for_close:
                    self._quiescing_operations -= 1
                    if self._quiescing_operations == 0:
                        self._drained.set()

    def close(self, error: BaseException | None = None) -> None:
        """Stop admission, drain ordinary operations, and become terminal."""

        with self._state_lock:
            if self._state == "CLOSED":
                return
            if self._state == "CLOSING":
                wait_for_close = True
            else:
                self._state = "CLOSING"
                self._close_error = error
                wait_for_close = False
        if wait_for_close:
            self._close_complete.wait()
            return
        self._drained.wait()
        with self._state_lock:
            self._state = "CLOSED"
            self._close_complete.set()


class _ConnectionOperationCoordinator:
    """Serialize complete logical transactions for one exact connection."""

    __slots__ = ("lock",)

    def __init__(self) -> None:
        self.lock = threading.RLock()


_CONNECTION_COORDINATORS_LOCK = threading.Lock()
_CONNECTION_COORDINATORS: dict[
    int, tuple[sqlite3.Connection, _ConnectionOperationCoordinator]
] = {}


def _connection_operation_coordinator(
    connection: sqlite3.Connection,
) -> _ConnectionOperationCoordinator:
    if type(connection) is not sqlite3.Connection:
        raise TypeError("connection operation requires an exact sqlite3.Connection")
    identity = id(connection)
    with _CONNECTION_COORDINATORS_LOCK:
        entry = _CONNECTION_COORDINATORS.get(identity)
        if entry is None or entry[0] is not connection:
            coordinator = _ConnectionOperationCoordinator()
            _CONNECTION_COORDINATORS[identity] = (connection, coordinator)
            return coordinator
        return entry[1]


@contextmanager
def _connection_operation(connection: sqlite3.Connection) -> Iterator[None]:
    coordinator = _connection_operation_coordinator(connection)
    with coordinator.lock:
        yield


def _serialized_connection_operation(
    function: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap one complete SQL state-machine transition in connection ownership."""

    @wraps(function)
    def wrapped(connection: sqlite3.Connection, *args: Any, **kwargs: Any) -> Any:
        with _connection_operation(connection):
            return function(connection, *args, **kwargs)

    return wrapped


class TransactionalAuthorityAdapter(Protocol):
    """Narrow future side-effect adapter; C2 supplies no production instance."""

    def construct_provider(
        self, capability: ProviderConstructionPermit, *, fail: bool = False
    ) -> ConstructedProvider: ...
    def create_process(
        self, process_intent: ProcessIntent, *, fail: bool = False
    ) -> ProcessCreationReceipt | ProcessCreationFailure: ...
    def resume_thread(
        self, resume_intent: ResumeIntent, *, fail: bool = False
    ) -> ResumeReceipt: ...
    def deliver_c3_child_request(
        self, execution_id: str, reservation_id: str, payload: bytes
    ) -> None: ...
    def validate_c3_post_resume_evidence(
        self,
        evidence: object,
        *,
        execution_id: str,
        reservation_id: str,
        resume_receipt: ResumeReceipt,
    ) -> tuple[bytes, bytes]: ...
    def consume_c3_post_resume_evidence(
        self,
        evidence: object,
        *,
        execution_id: str,
        reservation_id: str,
        resume_receipt: ResumeReceipt,
    ) -> None: ...
    def prepare_c3_terminal(
        self,
        lineage: tuple[str, str, str, str, str],
        verified_snapshot: object | None,
    ) -> object: ...
    def validate_c3_terminal(
        self,
        authorization: object,
        lineage: tuple[str, str, str, str, str],
    ) -> tuple[str, str, bytes | None, bytes, bytes, bytes, bytes]: ...
    def consume_c3_terminal(
        self,
        authorization: object,
        lineage: tuple[str, str, str, str, str],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class _ServiceContext:
    authority: ValidatedProductionAuthority | None
    lifecycle_arbiter_factory: Callable[[str], AbstractContextManager[object]]
    timestamp_provider: Callable[[str], str]
    capture_request_provider: Callable[[object], ValidatedCaptureRequest]
    test_only: bool
    lifecycle: TransactionalAuthorityLifecycle | None = None
    external_adapter: TransactionalAuthorityAdapter | None = None
    test_database: DisposableAuthorityDatabaseForTest | None = None
    test_service_token: object | None = None


@dataclass(frozen=True, slots=True)
class _ProviderConstructionLineage:
    request_digest: bytes
    authority_policy_version: str
    claim_policy_version: str


@dataclass(frozen=True, slots=True)
class _ProcessCreationLineage:
    application_release_version: str
    authority_policy_version: str
    process_intent_json: bytes
    process_intent_digest: bytes


@dataclass(frozen=True, slots=True)
class _ResumeThreadLineage:
    resume_intent_json: bytes
    resume_intent_digest: bytes


_DISPOSABLE_DATABASE_CONSTRUCTOR = object()


@dataclass(frozen=True, slots=True)
class _DisposableDatabaseIdentity:
    database_list: tuple[tuple[int, str, str], ...]


def _inspect_disposable_database_identity(
    connection: sqlite3.Connection,
) -> _DisposableDatabaseIdentity:
    if type(connection) is not sqlite3.Connection:
        raise TypeError("disposable database requires exact sqlite3.Connection")
    with _connection_operation(connection):
        rows = connection.execute("PRAGMA database_list").fetchall()
    identity = _DisposableDatabaseIdentity(
        tuple(
            (int(sequence), str(name), "" if filename is None else str(filename))
            for sequence, name, filename in rows
        )
    )
    if len(identity.database_list) != 1 or identity.database_list[0][1] != "main":
        raise ExternalAuthorityBoundaryUnavailable(
            "disposable test database must have exactly one main database"
        )
    filename = identity.database_list[0][2]
    if filename:
        raise ExternalAuthorityBoundaryUnavailable(
            "disposable test database must be anonymous in-memory SQLite"
        )
    return identity


class DisposableAuthorityDatabaseForTest:
    """Opaque database opened and identity-checked by the disposable test seam."""

    __slots__ = ("_connection", "_identity", "_claim_lock", "_claimed", "__weakref__")

    def __new__(
        cls,
        constructor: object,
        connection: sqlite3.Connection,
        identity: _DisposableDatabaseIdentity,
    ) -> Self:
        if constructor is not _DISPOSABLE_DATABASE_CONSTRUCTOR:
            raise TypeError("disposable test databases must use the reviewed opener")
        instance = super().__new__(cls)
        instance._connection = connection
        instance._identity = identity
        instance._claim_lock = threading.Lock()
        instance._claimed = False
        return instance

    def __init__(
        self,
        constructor: object,
        connection: sqlite3.Connection,
        identity: _DisposableDatabaseIdentity,
    ) -> None:
        del constructor, connection, identity

    @property
    def database_identity(self) -> tuple[tuple[int, str, str], ...]:
        return self._identity.database_list

    def validate_identity(self) -> None:
        if _inspect_disposable_database_identity(self._connection) != self._identity:
            raise ExternalAuthorityBoundaryUnavailable(
                "disposable test database identity changed after opening"
            )

    def _claim_test_service(self) -> None:
        with self._claim_lock:
            if self._claimed:
                raise ExternalAuthorityBoundaryUnavailable(
                    "disposable test database already has a service owner"
                )
            self.validate_identity()
            self._claimed = True

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        del args
        self.close()

    def __reduce__(self) -> object:
        raise TypeError("disposable test databases cannot be serialized")


def open_disposable_authority_database_for_test(
    database: object = ":memory:",
) -> DisposableAuthorityDatabaseForTest:
    """Open and identity-check an anonymous database for the explicit test seam."""

    if database != ":memory:":
        raise ExternalAuthorityBoundaryUnavailable(
            "disposable test database requires anonymous in-memory SQLite"
        )
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            ":memory:",
            timeout=5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        configure_trusted_schema_off(connection)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        identity = _inspect_disposable_database_identity(connection)
        return DisposableAuthorityDatabaseForTest(
            _DISPOSABLE_DATABASE_CONSTRUCTOR,
            connection,
            identity,
        )
    except BaseException:
        if connection is not None:
            connection.close()
        raise


_CURRENT_SERVICE_CONTEXT: contextvars.ContextVar[_ServiceContext | None] = (
    contextvars.ContextVar(
        "windows_transactional_authority_service_context", default=None
    )
)


def _lifecycle_arbiter(reservation_id: str) -> AbstractContextManager[object]:
    context = _CURRENT_SERVICE_CONTEXT.get()
    if context is None:
        raise ExternalAuthorityBoundaryUnavailable(
            "transactional authority lifecycle boundary has no service context"
        )
    return context.lifecycle_arbiter_factory(str(reservation_id))


def _require_service_context() -> _ServiceContext:
    context = _CURRENT_SERVICE_CONTEXT.get()
    if context is None:
        raise ExternalAuthorityBoundaryUnavailable(
            "transactional authority operation requires a bound service"
        )
    return context


def _service_issuer(production_issuer: object, test_issuer: object) -> object:
    return test_issuer if _require_service_context().test_only else production_issuer


def _active_test_service_token() -> object | None:
    context = _CURRENT_SERVICE_CONTEXT.get()
    if context is None or not context.test_only:
        return None
    return context.test_service_token


def _require_service_provenance(
    capability: object,
    *,
    production_issuer: object,
    test_issuer: object,
    label: str,
    test_only: bool | None = None,
    service_token: object | None = None,
) -> None:
    if test_only is None:
        context = _require_service_context()
        test_only = context.test_only
        service_token = context.test_service_token
    expected_issuer = test_issuer if test_only else production_issuer
    if getattr(capability, "_issuer", None) is not expected_issuer:
        if test_only:
            raise TypeError(f"{label} has invalid test service provenance issuer")
        raise ExternalAuthorityBoundaryUnavailable(
            f"{label} has invalid production service provenance"
        )
    if test_only and getattr(capability, "_service_token", None) is not service_token:
        raise TypeError(f"{label} has invalid test service provenance service")


def _production_timestamp(fallback: str) -> str:
    del fallback
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp(fallback: str) -> str:
    context = _CURRENT_SERVICE_CONTEXT.get()
    return fallback if context is None else context.timestamp_provider(fallback)


def _production_lifecycle_arbiter_factory(
    authority: ValidatedProductionAuthority,
) -> Callable[[str], AbstractContextManager[object]]:
    def create(reservation_id: str) -> AbstractContextManager[object]:
        return GlobalLifecycleMutex(
            authority.machine_authority_id,
            authority.authority_epoch_id,
            str(reservation_id),
            trading_sid=authority.approved_account_sid,
        )

    return create


_RESUME_INTENT_ISSUER = object()
_PROCESS_INTENT_ISSUER = object()
_PROCESS_RESULT_ISSUER = object()
_RESUME_RESULT_ISSUER = object()
_PROVIDER_CONSTRUCTION_ISSUER = object()
_CONSTRUCTED_PROVIDER_ISSUER = object()
_TEST_RESUME_INTENT_ISSUER = object()
_TEST_PROCESS_INTENT_ISSUER = object()
_TEST_PROCESS_RESULT_ISSUER = object()
_TEST_RESUME_RESULT_ISSUER = object()
_TEST_PROVIDER_CONSTRUCTION_ISSUER = object()
_TEST_CONSTRUCTED_PROVIDER_ISSUER = object()
_ISSUED_RESUME_PERMITS_LOCK = threading.Lock()
_ISSUED_PROCESS_PERMITS_LOCK = threading.Lock()
_ISSUED_PROCESS_RESULTS_LOCK = threading.Lock()
_ISSUED_RESUME_RESULTS_LOCK = threading.Lock()
_ISSUED_PROVIDER_CONSTRUCTION_PERMITS_LOCK = threading.Lock()
_ISSUED_CONSTRUCTED_PROVIDERS_LOCK = threading.Lock()


class _ProcessLocalCapability:
    """Marker that prevents durable or cross-process capability transfer."""

    def __reduce__(self) -> object:
        raise TypeError("transactional authority capabilities cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("transactional authority capabilities cannot be pickled")


class _TestServiceToken:
    """Weak-referenceable identity token for one test service lifecycle."""

    __slots__ = ("__weakref__",)


@dataclass(eq=False)
class _ProcessPermit:
    lock: threading.Lock = field(default_factory=threading.Lock)
    consumed: bool = False


@dataclass(eq=False)
class _ProcessResultPermit:
    lock: threading.Lock = field(default_factory=threading.Lock)
    consumed: bool = False


@dataclass(eq=False)
class _ResumePermit:
    lock: threading.Lock = field(default_factory=threading.Lock)
    consumed: bool = False


@dataclass(eq=False)
class _ResumeResultPermit:
    lock: threading.Lock = field(default_factory=threading.Lock)
    consumed: bool = False


@dataclass(eq=False)
class _ProviderConstructionOneShot:
    lock: threading.Lock = field(default_factory=threading.Lock)
    consumed: bool = False


@dataclass(eq=False)
class _ConstructedProviderOneShot:
    lock: threading.Lock = field(default_factory=threading.Lock)
    consumed: bool = False


@dataclass(frozen=True, slots=True, eq=False)
class ProviderConstructionPermit(_ProcessLocalCapability):
    """Reservation identity plus opaque one-shot provider-construction authority."""

    reservation_id: str
    _issuer: object = field(repr=False, compare=False)
    _permit: _ProviderConstructionOneShot = field(repr=False, compare=False)
    _service_token: object | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._issuer not in (
            _PROVIDER_CONSTRUCTION_ISSUER,
            _TEST_PROVIDER_CONSTRUCTION_ISSUER,
        ):
            raise TypeError(
                "fake provider construction permits require reservation commit"
            )

    def __str__(self) -> str:
        return self.reservation_id


@dataclass(frozen=True, slots=True)
class ConstructedProvider(_ProcessLocalCapability):
    """Opaque one-shot handoff from provider construction to process intent."""

    reservation_id: str
    _issuer: object = field(repr=False, compare=False)
    _permit: _ConstructedProviderOneShot = field(repr=False, compare=False)
    _service_token: object | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._issuer not in (
            _CONSTRUCTED_PROVIDER_ISSUER,
            _TEST_CONSTRUCTED_PROVIDER_ISSUER,
        ):
            raise TypeError("fake constructed providers can only come from the adapter")


@dataclass(frozen=True, slots=True)
class ProcessIntent(_ProcessLocalCapability):
    """Opaque one-shot authority returned only by the intent transaction."""

    reservation_id: str
    intent_json: bytes
    intent_digest: bytes
    _issuer: object = field(repr=False, compare=False)
    _permit: _ProcessPermit = field(repr=False, compare=False)
    _service_token: object | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._issuer not in (
            _PROCESS_INTENT_ISSUER,
            _TEST_PROCESS_INTENT_ISSUER,
        ):
            raise TypeError("fake process intents can only be issued after commit")


@dataclass(frozen=True, slots=True)
class ProcessCreationReceipt(_ProcessLocalCapability):
    """Canonical successful CreateProcessW and Job Object result."""

    reservation_id: str
    process_intent_digest: bytes
    process_json: bytes
    process_digest: bytes
    job_json: bytes
    job_digest: bytes
    resume_authorization_json: bytes
    resume_authorization_digest: bytes
    _issuer: object = field(repr=False, compare=False)
    _permit: _ProcessResultPermit = field(repr=False, compare=False)
    _service_token: object | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._issuer not in (
            _PROCESS_RESULT_ISSUER,
            _TEST_PROCESS_RESULT_ISSUER,
        ):
            raise TypeError("fake process receipts can only come from the adapter")


@dataclass(frozen=True, slots=True)
class ProcessCreationFailure(_ProcessLocalCapability):
    """Canonical definitive CreateProcessW not-created result."""

    reservation_id: str
    process_intent_digest: bytes
    result_json: bytes
    result_digest: bytes
    _issuer: object = field(repr=False, compare=False)
    _permit: _ProcessResultPermit = field(repr=False, compare=False)
    _service_token: object | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._issuer not in (
            _PROCESS_RESULT_ISSUER,
            _TEST_PROCESS_RESULT_ISSUER,
        ):
            raise TypeError("fake process failures can only come from the adapter")


@dataclass(frozen=True, slots=True)
class ResumeIntent(_ProcessLocalCapability):
    """Opaque one-shot authority returned only by the intent transaction."""

    execution_id: str
    reservation_id: str
    intent_json: bytes
    intent_digest: bytes
    _issuer: object = field(repr=False, compare=False)
    _permit: _ResumePermit = field(repr=False, compare=False)
    _service_token: object | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._issuer not in (
            _RESUME_INTENT_ISSUER,
            _TEST_RESUME_INTENT_ISSUER,
        ):
            raise TypeError("fake resume intents can only be issued after commit")


@dataclass(frozen=True, slots=True)
class ResumeReceipt(_ProcessLocalCapability):
    """Canonical result returned by the fake external ResumeThread boundary."""

    execution_id: str
    reservation_id: str
    resume_intent_digest: bytes
    result_json: bytes
    result_digest: bytes
    _issuer: object = field(repr=False, compare=False)
    _permit: _ResumeResultPermit = field(repr=False, compare=False)
    _service_token: object | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self._issuer not in (
            _RESUME_RESULT_ISSUER,
            _TEST_RESUME_RESULT_ISSUER,
        ):
            raise TypeError("fake resume receipts can only come from the adapter")


# Preserve direct test-query convenience after removing ``str`` inheritance.
# Capability boundaries never use this adapter to select authoritative lineage.
sqlite3.register_adapter(ProviderConstructionPermit, str)


@dataclass(frozen=True, slots=True)
class _ProviderConstructionIssuance:
    capability: weakref.ReferenceType[ProviderConstructionPermit]
    reservation_id: str
    issuer: object
    permit: weakref.ReferenceType[_ProviderConstructionOneShot]
    service_token: weakref.ReferenceType[object] | None


@dataclass(frozen=True, slots=True)
class _ConstructedProviderIssuance:
    provider: weakref.ReferenceType[ConstructedProvider]
    reservation_id: str
    issuer: object
    permit: weakref.ReferenceType[_ConstructedProviderOneShot]
    service_token: weakref.ReferenceType[object] | None


@dataclass(frozen=True, slots=True)
class _ProcessIntentIssuance:
    intent: weakref.ReferenceType[ProcessIntent]
    reservation_id: str
    intent_json: bytes
    intent_digest: bytes
    issuer: object
    permit: weakref.ReferenceType[_ProcessPermit]
    service_token: weakref.ReferenceType[object] | None


@dataclass(frozen=True, slots=True)
class _ProcessResultIssuance:
    result: weakref.ReferenceType[ProcessCreationReceipt | ProcessCreationFailure]
    reservation_id: str
    process_intent_digest: bytes
    evidence: tuple[bytes, ...]
    digests: tuple[bytes, ...]
    issuer: object
    permit: weakref.ReferenceType[_ProcessResultPermit]
    service_token: weakref.ReferenceType[object] | None


@dataclass(frozen=True, slots=True)
class _ResumeIntentIssuance:
    intent: weakref.ReferenceType[ResumeIntent]
    execution_id: str
    reservation_id: str
    intent_json: bytes
    intent_digest: bytes
    issuer: object
    permit: weakref.ReferenceType[_ResumePermit]
    service_token: weakref.ReferenceType[object] | None


@dataclass(frozen=True, slots=True)
class _ResumeResultIssuance:
    result: weakref.ReferenceType[ResumeReceipt]
    execution_id: str
    reservation_id: str
    resume_intent_digest: bytes
    result_json: bytes
    result_digest: bytes
    issuer: object
    permit: weakref.ReferenceType[_ResumeResultPermit]
    service_token: weakref.ReferenceType[object] | None


class _WeakIssuanceRegistry:
    """Weakly own one-shot issuance records without retaining their objects."""

    def __init__(self, lock: threading.Lock) -> None:
        self._lock = lock
        self._entries: dict[weakref.ReferenceType[Any], Any] = {}

    def _remove(self, reference: weakref.ReferenceType[Any]) -> None:
        with self._lock:
            self._entries.pop(reference, None)

    def __setitem__(self, permit: object, issuance: object) -> None:
        reference = weakref.ref(permit, self._remove)
        self._entries[reference] = issuance

    def get(self, permit: object, default: object = None) -> object:
        return self._entries.get(weakref.ref(permit), default)

    def __delitem__(self, permit: object) -> None:
        del self._entries[weakref.ref(permit)]

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


_ISSUED_PROVIDER_CONSTRUCTION_PERMITS: _WeakIssuanceRegistry
_ISSUED_CONSTRUCTED_PROVIDERS: _WeakIssuanceRegistry
_ISSUED_PROCESS_PERMITS: _WeakIssuanceRegistry
_ISSUED_PROCESS_RESULTS: _WeakIssuanceRegistry
_ISSUED_RESUME_PERMITS: _WeakIssuanceRegistry
_ISSUED_RESUME_RESULTS: _WeakIssuanceRegistry


_ISSUED_PROVIDER_CONSTRUCTION_PERMITS = _WeakIssuanceRegistry(
    _ISSUED_PROVIDER_CONSTRUCTION_PERMITS_LOCK
)
_ISSUED_CONSTRUCTED_PROVIDERS = _WeakIssuanceRegistry(
    _ISSUED_CONSTRUCTED_PROVIDERS_LOCK
)
_ISSUED_PROCESS_PERMITS = _WeakIssuanceRegistry(_ISSUED_PROCESS_PERMITS_LOCK)
_ISSUED_PROCESS_RESULTS = _WeakIssuanceRegistry(_ISSUED_PROCESS_RESULTS_LOCK)
_ISSUED_RESUME_PERMITS = _WeakIssuanceRegistry(_ISSUED_RESUME_PERMITS_LOCK)
_ISSUED_RESUME_RESULTS = _WeakIssuanceRegistry(_ISSUED_RESUME_RESULTS_LOCK)

_PRODUCTION_C3_RESULT_ISSUER_CONSTRUCTOR = object()


class _ProductionC3ResultIssuer:
    """Exact production C2 issuer privately retained by one bound C3 adapter."""

    __slots__ = ("_active", "_adapter", "_lock")

    def __init__(self, constructor: object, adapter: object) -> None:
        if constructor is not _PRODUCTION_C3_RESULT_ISSUER_CONSTRUCTOR:
            raise TypeError("production C3 result issuers are composition-owned")
        self._adapter: object | None = adapter
        self._active = True
        self._lock = threading.Lock()

    def _require_active_adapter(self) -> object:
        with self._lock:
            adapter = self._adapter
            if not self._active or adapter is None:
                raise ExternalAuthorityBoundaryUnavailable(
                    "production C3 result issuer is revoked"
                )
        context = _require_service_context()
        if context.test_only or context.external_adapter is not adapter:
            raise ExternalAuthorityBoundaryUnavailable(
                "production C3 result issuance is outside its exact service binding"
            )
        return adapter

    def issue_constructed_provider(self, reservation_id: str) -> ConstructedProvider:
        self._require_active_adapter()
        return _issue_constructed_provider(
            reservation_id,
            issuer=_CONSTRUCTED_PROVIDER_ISSUER,
            service_token=None,
        )

    def issue_process_creation_receipt(
        self,
        reservation_id: str,
        process_intent_digest: bytes,
        *,
        application_name: str,
        child_base_arguments: tuple[str, ...],
    ) -> ProcessCreationReceipt:
        self._require_active_adapter()
        process_json, job_json, resume_json = _production_process_success_evidence(
            reservation_id,
            process_intent_digest,
            application_name=application_name,
            child_base_arguments=child_base_arguments,
        )
        return _issue_process_creation_receipt(
            reservation_id,
            process_intent_digest,
            process_json,
            _digest(process_json),
            job_json,
            _digest(job_json),
            resume_json,
            _digest(resume_json),
            issuer=_PROCESS_RESULT_ISSUER,
            service_token=None,
        )

    def issue_process_creation_failure(
        self, reservation_id: str, process_intent_digest: bytes
    ) -> ProcessCreationFailure:
        self._require_active_adapter()
        result_json = _process_failure_json(reservation_id, process_intent_digest)
        return _issue_process_creation_failure(
            reservation_id,
            process_intent_digest,
            result_json,
            _digest(result_json),
            issuer=_PROCESS_RESULT_ISSUER,
            service_token=None,
        )

    def issue_resume_receipt(
        self,
        execution_id: str,
        reservation_id: str,
        resume_intent_digest: bytes,
    ) -> ResumeReceipt:
        self._require_active_adapter()
        result_json = _json(
            {
                "execution_id": execution_id,
                "resume_intent_digest": resume_intent_digest.hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        return _issue_resume_receipt(
            execution_id,
            reservation_id,
            resume_intent_digest,
            result_json,
            _digest(result_json),
            issuer=_RESUME_RESULT_ISSUER,
            service_token=None,
        )

    def close(self) -> None:
        with self._lock:
            self._active = False
            self._adapter = None

    def __copy__(self) -> object:
        raise TypeError("production C3 result issuers cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("production C3 result issuers cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("production C3 result issuers cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("production C3 result issuers cannot be pickled")


def _weak_reference(value: object, label: str) -> weakref.ReferenceType[Any]:
    try:
        return weakref.ref(value)
    except TypeError as error:
        raise TypeError(f"{label} must be weak-referenceable") from error


def _optional_weak_reference(
    value: object | None, label: str
) -> weakref.ReferenceType[object] | None:
    return None if value is None else _weak_reference(value, label)


def _resolve_weak_reference(
    reference: weakref.ReferenceType[Any] | None,
) -> Any:
    return None if reference is None else reference()


def _frame(value: str) -> str:
    value = str(value)
    encoded = value.encode("utf-8")
    return f"{len(encoded)}:" + value


def _ordered_list(values: tuple[str, ...]) -> str:
    return _frame(str(len(values))) + "".join(_frame(value) for value in values)


def _identity(label: str, *values: str) -> str:
    material = _frame(label) + "".join(_frame(value) for value in values)
    return str(uuid.uuid5(NAMESPACE, material))


def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _require_evidence_pair(
    evidence: bytes, digest: bytes, *, field: str = "evidence digest"
) -> None:
    require_evidence_digest(evidence, digest, field=field)


def _require_terminal_snapshot_digest(
    state: str, snapshot_digest: bytes | None
) -> None:
    if state == "SUCCEEDED":
        if type(snapshot_digest) is not bytes or len(snapshot_digest) != 32:
            raise SchemaValidationError(
                "successful terminal requires an exact 32-byte snapshot digest"
            )
    elif snapshot_digest is not None:
        raise SchemaValidationError("non-success terminal snapshot digest must be NULL")


def _json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


_MAX_C3_CLEANUP_EVIDENCE_BYTES = 1024
_MAX_C3_TERMINAL_EVIDENCE_BYTES = 2048
_MAX_C3_TERMINAL_DIAGNOSTICS_BYTES = 512
_C3_TERMINAL_EVIDENCE_FIELDS = frozenset(
    {
        "artifact_identity_sha256",
        "artifact_sha256",
        "artifact_verification",
        "attempt_id",
        "child_fence_state",
        "child_request_sha256",
        "child_result_classification",
        "child_result_sha256",
        "claim_id",
        "execution_id",
        "parent_cleanup",
        "process_outcome",
        "provider_call_disposition",
        "reservation_id",
        "result_transport",
        "schema",
        "session_id",
        "snapshot_id",
        "staging_cleanup",
        "terminal_state",
    }
)
_C3_CHILD_CLASSIFICATIONS = frozenset(
    {
        "SUCCEEDED",
        "REQUEST_INVALID",
        "SID_REJECTED",
        "CREDENTIAL_FAILED",
        "TRANSPORT_FAILED",
        "HTTP_FAILED",
        "PROVIDER_RESPONSE_INVALID",
        "SNAPSHOT_REJECTED",
        "SERIALIZATION_FAILED",
        "STAGING_FAILED",
        "INTERNAL_FAILED",
    }
)
_C3_ARTIFACT_FAILURES = frozenset(
    {
        "INELIGIBLE_CHILD_RESULT",
        "STAGING_IDENTITY_MISMATCH",
        "STAGING_BYTES_INVALID",
        "CHILD_CLAIM_MISMATCH",
        "OFFLINE_VERIFICATION_FAILED",
        "REQUEST_RECONCILIATION_FAILED",
        "PUBLICATION_FAILED",
        "FINAL_REVERIFICATION_FAILED",
        "STAGING_CLEANUP_FAILED",
    }
)


def _reject_duplicate_evidence_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("C3 cleanup evidence contains a duplicate JSON key")
        result[key] = value
    return result


def _reject_nonstandard_evidence_constant(value: str) -> None:
    raise ValueError(f"C3 cleanup evidence contains unsupported constant {value!r}")


def _require_canonical_c3_cleanup_evidence(
    cleanup_json: object, cleanup_digest: object
) -> tuple[bytes, bytes]:
    """Validate only the generic canonical pair; C3 semantics stay adapter-owned."""

    if (
        type(cleanup_json) is not bytes
        or not cleanup_json
        or len(cleanup_json) > _MAX_C3_CLEANUP_EVIDENCE_BYTES
    ):
        raise ValueError("C3 cleanup evidence bytes are invalid")
    if type(cleanup_digest) is not bytes or len(cleanup_digest) != 32:
        raise ValueError("C3 cleanup evidence digest must be exact SHA-256 bytes")
    if _digest(cleanup_json) != cleanup_digest:
        raise ValueError("C3 cleanup evidence digest is invalid")
    if cleanup_json.startswith(b"\xef\xbb\xbf"):
        raise ValueError("C3 cleanup evidence must not contain a UTF-8 BOM")
    try:
        text = cleanup_json.decode("utf-8")
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_evidence_keys,
            parse_constant=_reject_nonstandard_evidence_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("C3 cleanup evidence must be strict UTF-8 JSON") from error
    if type(parsed) is not dict or _json(parsed) != cleanup_json:
        raise ValueError("C3 cleanup evidence must be one canonical JSON object")
    return cleanup_json, cleanup_digest


def _require_canonical_c3_json_pair(
    value: object,
    digest: object,
    *,
    field: str,
    byte_limit: int,
) -> tuple[bytes, bytes, dict[str, Any]]:
    if type(value) is not bytes or not value or len(value) > byte_limit:
        raise ValueError(f"{field} bytes are invalid")
    if type(digest) is not bytes or len(digest) != 32 or _digest(value) != digest:
        raise ValueError(f"{field} digest is invalid")
    if value.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{field} must not contain a UTF-8 BOM")
    try:
        parsed = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_evidence_keys,
            parse_constant=_reject_nonstandard_evidence_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{field} must be strict UTF-8 JSON") from error
    if type(parsed) is not dict or _json(parsed) != value:
        raise ValueError(f"{field} must be one canonical JSON object")
    return value, digest, parsed


def _is_canonical_sha256(value: object) -> bool:
    return bool(
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_c3_terminal_material(
    material: object,
    lineage: tuple[str, str, str, str, str],
) -> tuple[str, str, bytes | None, bytes, bytes, bytes, bytes]:
    if type(material) is not tuple or len(material) != 7:
        raise ValueError("C3 terminal adapter returned invalid material")
    (
        state,
        disposition,
        snapshot_digest,
        evidence_json,
        evidence_digest,
        diagnostics_json,
        diagnostics_digest,
    ) = material
    if type(state) is not str or type(disposition) is not str:
        raise ValueError("C3 terminal state material is invalid")
    _require_terminal_snapshot_digest(state, snapshot_digest)
    evidence_json, evidence_digest, evidence = _require_canonical_c3_json_pair(
        evidence_json,
        evidence_digest,
        field="C3 terminal evidence",
        byte_limit=_MAX_C3_TERMINAL_EVIDENCE_BYTES,
    )
    diagnostics_json, diagnostics_digest, diagnostics = _require_canonical_c3_json_pair(
        diagnostics_json,
        diagnostics_digest,
        field="C3 terminal diagnostics",
        byte_limit=_MAX_C3_TERMINAL_DIAGNOSTICS_BYTES,
    )
    if set(evidence) != _C3_TERMINAL_EVIDENCE_FIELDS or evidence["schema"] != 1:
        raise ValueError("C3 terminal evidence schema is invalid")
    if (
        set(diagnostics)
        != {
            "artifact_verification",
            "parent_cleanup",
            "reason",
            "result_transport",
            "schema",
            "staging_cleanup",
        }
        or diagnostics["schema"] != 1
    ):
        raise ValueError("C3 terminal diagnostics schema is invalid")
    if (
        tuple(
            evidence[field]
            for field in (
                "session_id",
                "attempt_id",
                "claim_id",
                "reservation_id",
                "execution_id",
            )
        )
        != lineage
    ):
        raise ValueError("C3 terminal evidence lineage is mismatched")
    if (
        evidence["terminal_state"] != state
        or evidence["provider_call_disposition"] != disposition
        or not _is_canonical_sha256(evidence["child_request_sha256"])
    ):
        raise ValueError("C3 terminal evidence outcome binding is invalid")
    if evidence["result_transport"] not in {
        "COMPLETE",
        "EMPTY",
        "OVERSIZED",
        "READ_FAILED",
    } or evidence["process_outcome"] not in {
        "EXITED_ZERO",
        "EXITED_NONZERO",
        "TIMED_OUT_TERMINATED",
        "WAIT_FAILED_TERMINATED",
        "OBSERVATION_FAILED_TERMINATED",
        "TERMINATION_UNCONFIRMED",
    }:
        raise ValueError("C3 terminal process classification is invalid")
    if evidence["parent_cleanup"] not in {"COMPLETE", "FAILED"}:
        raise ValueError("C3 terminal parent cleanup is invalid")
    if evidence["staging_cleanup"] not in {
        "COMPLETE",
        "FAILED",
        "IDENTITY_MISMATCH",
        "ALREADY_RELEASED",
    }:
        raise ValueError("C3 terminal staging cleanup is invalid")
    fence = evidence["child_fence_state"]
    classification = evidence["child_result_classification"]
    child_result_sha256 = evidence["child_result_sha256"]
    child_result_absent = (
        fence is None and classification is None and child_result_sha256 is None
    )
    child_result_present = (
        fence in {"ENTERED", "NOT_ENTERED"}
        and classification in _C3_CHILD_CLASSIFICATIONS
        and _is_canonical_sha256(child_result_sha256)
        and evidence["result_transport"] == "COMPLETE"
    )
    if not (child_result_absent or child_result_present):
        raise ValueError("C3 terminal child result classification is invalid")
    artifact_verification = evidence["artifact_verification"]
    if artifact_verification not in {
        "VERIFIED",
        "NOT_ATTEMPTED",
        *_C3_ARTIFACT_FAILURES,
    }:
        raise ValueError("C3 terminal artifact classification is invalid")
    artifact_fields = (
        evidence["snapshot_id"],
        evidence["artifact_sha256"],
        evidence["artifact_identity_sha256"],
    )
    reason = diagnostics["reason"]
    if state == "SUCCEEDED":
        if (
            disposition != "CONFIRMED"
            or fence != "ENTERED"
            or classification != "SUCCEEDED"
            or artifact_verification != "VERIFIED"
            or type(evidence["snapshot_id"]) is not str
            or not _is_canonical_sha256(evidence["artifact_sha256"])
            or not _is_canonical_sha256(evidence["artifact_identity_sha256"])
            or bytes.fromhex(evidence["artifact_sha256"]) != snapshot_digest
            or reason != "VERIFIED_SNAPSHOT"
            or evidence["staging_cleanup"] != "COMPLETE"
        ):
            raise ValueError("C3 successful terminal material is invalid")
        try:
            if str(uuid.UUID(evidence["snapshot_id"])) != evidence["snapshot_id"]:
                raise ValueError
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("C3 terminal snapshot identity is invalid") from error
    elif state == "FAILED":
        if (
            disposition != "CONFIRMED"
            or any(value is not None for value in artifact_fields)
            or artifact_verification == "VERIFIED"
        ):
            raise ValueError("C3 failed terminal material is invalid")
        child_failure = (
            fence == "ENTERED"
            and classification in _C3_CHILD_CLASSIFICATIONS - {"SUCCEEDED"}
            and reason == "POST_FENCE_CHILD_FAILURE"
        )
        parent_failure = (
            fence == "ENTERED"
            and classification == "SUCCEEDED"
            and artifact_verification in _C3_ARTIFACT_FAILURES
            and reason == "PARENT_ARTIFACT_VERIFICATION_FAILED"
        )
        if not (child_failure or parent_failure):
            raise ValueError("C3 failed terminal mapping is invalid")
    elif state == "AMBIGUOUS":
        if (
            disposition != "MAY_HAVE_OCCURRED"
            or any(value is not None for value in artifact_fields)
            or artifact_verification == "VERIFIED"
            or reason != "POST_RESUME_OUTCOME_AMBIGUOUS"
            or not (child_result_absent or fence == "NOT_ENTERED")
        ):
            raise ValueError("C3 ambiguous terminal mapping is invalid")
    else:
        raise ValueError("C3 post-resume terminal state is unsupported")
    for diagnostic_field in (
        "artifact_verification",
        "parent_cleanup",
        "result_transport",
        "staging_cleanup",
    ):
        if diagnostics[diagnostic_field] != evidence[diagnostic_field]:
            raise ValueError("C3 terminal diagnostics binding is invalid")
    return (
        state,
        disposition,
        snapshot_digest,
        evidence_json,
        evidence_digest,
        diagnostics_json,
        diagnostics_digest,
    )


def _require_c3_terminal_matches_durable_cleanup(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
    evidence_json: bytes,
) -> None:
    row = connection.execute(
        "SELECT cleanup_json, cleanup_digest FROM launch_executions "
        "WHERE launch_execution_id = ? AND launch_reservation_id = ?",
        (execution_id, reservation_id),
    ).fetchone()
    if row is None:
        raise ValueError("C3 terminal durable cleanup lineage is unavailable")
    cleanup_json, _cleanup_digest = _require_canonical_c3_cleanup_evidence(*row)
    cleanup = json.loads(cleanup_json)
    evidence = json.loads(evidence_json)
    fields = (
        "child_fence_state",
        "child_request_sha256",
        "child_result_classification",
        "child_result_sha256",
        "execution_id",
        "parent_cleanup",
        "process_outcome",
        "provider_call_disposition",
        "reservation_id",
        "result_transport",
        "schema",
    )
    if set(cleanup) != set(fields) or any(
        cleanup[field] != evidence[field] for field in fields
    ):
        raise ValueError("C3 terminal evidence differs from durable cleanup evidence")


def _evidence(label: str) -> tuple[bytes, bytes]:
    value = _json({"evidence": label, "schema": 1})
    return value, _digest(value)


@dataclass(frozen=True, slots=True)
class ValidatedCaptureRequest:
    bar_interval: str
    child_operation_version: str
    ordered_universe: tuple[str, ...]
    output_policy_version: str
    permitted_provider_operation: str
    provider_id: str
    request_limit: int
    request_window_end_date: str
    request_window_start_date: str
    target_session_date: str

    def canonical_json(self) -> bytes:
        return _json(
            {
                "bar_interval": self.bar_interval,
                "child_operation_version": self.child_operation_version,
                "ordered_universe": list(self.ordered_universe),
                "output_policy_version": self.output_policy_version,
                "permitted_provider_operation": self.permitted_provider_operation,
                "provider_id": self.provider_id,
                "request_limit": self.request_limit,
                "request_window_end_date": self.request_window_end_date,
                "request_window_start_date": self.request_window_start_date,
                "target_session_date": self.target_session_date,
            }
        )


def _snapshot_capture_request(request: object) -> ValidatedCaptureRequest:
    if type(request) is not dict:
        raise ValueError("capture_request/v2 must be an exact object")
    captured = request.copy()
    if set(captured) != CAPTURE_REQUEST_FIELDS:
        raise ValueError("capture_request/v2 has a missing or unknown field")

    string_fields = CAPTURE_REQUEST_FIELDS - {"ordered_universe", "request_limit"}
    if any(type(captured[field]) is not str for field in string_fields):
        raise ValueError("capture_request/v2 string fields require exact strings")
    if type(captured["ordered_universe"]) is not list:
        raise ValueError("ordered_universe must be an exact list")
    captured_universe = tuple(captured["ordered_universe"])
    if not 1 <= len(captured_universe) <= MAX_DAILY_SNAPSHOT_SYMBOLS:
        raise ValueError("ordered_universe is empty or exceeds its bound")
    canonical_universe: list[str] = []
    for entry in captured_universe:
        if type(entry) is not str:
            raise ValueError("ordered_universe members must be exact strings")
        try:
            canonical_text = str(Symbol(entry))
        except (TypeError, ValueError) as error:
            raise ValueError("ordered_universe member is not a valid Symbol") from error
        canonical_universe.append(canonical_text)
    if len(set(canonical_universe)) != len(canonical_universe):
        raise ValueError("ordered_universe must be duplicate-free")
    if any(
        entry != canonical_text
        for entry, canonical_text in zip(
            captured_universe, canonical_universe, strict=True
        )
    ):
        raise ValueError("ordered_universe members must already be canonical Symbols")
    request_limit = captured["request_limit"]
    if type(request_limit) is not int or request_limit <= 0:
        raise ValueError("request_limit must be an exact positive integer")
    if (
        request_limit != len(canonical_universe)
        or request_limit > MAX_DAILY_SNAPSHOT_SYMBOLS
    ):
        raise ValueError("request_limit must equal the bounded universe size")

    for field_name in (
        "request_window_start_date",
        "request_window_end_date",
        "target_session_date",
    ):
        value = captured[field_name]
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{field_name} is not a canonical date") from error
        if parsed.isoformat() != value:
            raise ValueError(f"{field_name} is not a canonical date")
    window_start = date.fromisoformat(captured["request_window_start_date"])
    window_end = date.fromisoformat(captured["request_window_end_date"])
    target_session = date.fromisoformat(captured["target_session_date"])
    if not window_start <= window_end < target_session:
        raise ValueError("capture request dates are not causally ordered")

    fixed_values = {
        "bar_interval": "1d",
        "child_operation_version": "child/v1",
        "output_policy_version": "output/v1",
        "provider_id": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        "permitted_provider_operation": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
    }
    if any(captured[field] != value for field, value in fixed_values.items()):
        raise ValueError("capture_request/v2 fixed semantics are invalid")
    return ValidatedCaptureRequest(
        bar_interval=captured["bar_interval"],
        child_operation_version=captured["child_operation_version"],
        ordered_universe=tuple(canonical_universe),
        output_policy_version=captured["output_policy_version"],
        permitted_provider_operation=captured["permitted_provider_operation"],
        provider_id=captured["provider_id"],
        request_limit=request_limit,
        request_window_end_date=captured["request_window_end_date"],
        request_window_start_date=captured["request_window_start_date"],
        target_session_date=captured["target_session_date"],
    )


def _session_id(
    request: ValidatedCaptureRequest,
    *,
    machine_authority_id: str,
    authority_epoch_id: str,
    authority_policy_version: str,
    claim_policy_version: str,
) -> str:
    return _identity(
        "session_id/v2",
        machine_authority_id,
        authority_epoch_id,
        "1",
        authority_policy_version,
        claim_policy_version,
        "capture_request/v2",
        request.target_session_date,
        request.provider_id,
        request.permitted_provider_operation,
        _ordered_list(request.ordered_universe),
        request.bar_interval,
        request.request_window_start_date,
        request.request_window_end_date,
        str(request.request_limit),
        request.child_operation_version,
        request.output_policy_version,
    )


def _canonical_ordinal(value: object, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be an exact non-negative int")
    return value


def _attempt_id(
    session_id: str,
    ordinal: int,
    provider_id: str,
    permitted_provider_operation: str,
    attempt_policy_version: str,
) -> str:
    ordinal = _canonical_ordinal(ordinal, "attempt ordinal")
    return _identity(
        "attempt_id/v2",
        session_id,
        str(ordinal),
        provider_id,
        permitted_provider_operation,
        "1",
        attempt_policy_version,
    )


def _claim_id(
    attempt_id: str,
    claim_policy_version: str,
    provider_id: str,
    permitted_provider_operation: str,
    provider_call_budget: int,
) -> str:
    return _identity(
        "claim_id/v2",
        attempt_id,
        "1",
        claim_policy_version,
        provider_id,
        permitted_provider_operation,
        str(provider_call_budget),
    )


def _reservation_id(
    claim_id: str,
    application_release_version: str,
    authority_policy_version: str,
    claim_policy_version: str,
) -> str:
    return _identity(
        "launch_reservation_id/v2",
        claim_id,
        "1",
        application_release_version,
        authority_policy_version,
        claim_policy_version,
    )


def _execution_id(
    reservation_id: str,
    application_release_version: str,
    authority_policy_version: str,
) -> str:
    return _identity(
        "launch_execution_id/v2",
        reservation_id,
        "1",
        application_release_version,
        authority_policy_version,
    )


def _terminal_id(reservation_id: str, terminal_policy_version: str) -> str:
    return _identity("terminal_id/v2", reservation_id, "1", terminal_policy_version)


def _selection_id(
    session_id: str, terminal_id: str, selection_policy_version: str
) -> str:
    return _identity(
        "selection_id/v2",
        session_id,
        terminal_id,
        "1",
        selection_policy_version,
    )


def _recovery_id(
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    predecessor_state: str,
    resulting_state: str,
    ordinal: int,
    recovery_policy_version: str,
) -> str:
    ordinal = _canonical_ordinal(ordinal, "recovery ordinal")
    return _identity(
        "recovery_id/v2",
        session_id,
        target_kind,
        target_id,
        action,
        predecessor_state,
        resulting_state,
        "1",
        recovery_policy_version,
        str(ordinal),
    )


def _require_no_active_transaction(connection: sqlite3.Connection) -> None:
    if type(connection) is not sqlite3.Connection:
        raise TypeError("lifecycle boundary requires an exact sqlite3.Connection")
    with _connection_operation(connection):
        if connection.in_transaction:
            raise ValueError("lifecycle boundary requires no active SQLite transaction")
        context = _require_service_context()
        if context.test_only:
            test_database = context.test_database
            if test_database is not None:
                test_database.validate_identity()


def _begin(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")


def _finish(connection: sqlite3.Connection, commit: bool) -> None:
    (connection.commit if commit else connection.rollback)()


@_serialized_connection_operation
def _core_create_session(
    connection: sqlite3.Connection,
    request: dict[str, Any] | None = None,
    *,
    created_at_utc: str = TIMESTAMP,
) -> str:
    _require_service_context()
    if request is None:
        raise ValueError("capture request is required at the production boundary")
    snapshot = _require_service_context().capture_request_provider(request)
    _begin(connection)
    try:
        metadata = connection.execute(
            """
            SELECT authority_epoch_id, machine_authority_id, provider_id,
                   permitted_provider_operation, authority_policy_version,
                   claim_policy_version
            FROM authority_metadata
            WHERE singleton_key = 1
            """
        ).fetchone()
        if metadata is None:
            raise ValueError("authority metadata is missing")
        (
            authority_epoch_id,
            machine_authority_id,
            metadata_provider_id,
            metadata_operation,
            authority_policy_version,
            claim_policy_version,
        ) = metadata
        if authority_policy_version != POLICY:
            raise ValueError("authority policy is unsupported by this release")
        if claim_policy_version != CLAIM_POLICY:
            raise ValueError("claim policy is unsupported by this release")
        if (
            metadata_provider_id != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id
            or metadata_operation != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
        ):
            raise ValueError("authority metadata does not match the Alpaca descriptor")
        request_provider_id = snapshot.provider_id
        request_operation = snapshot.permitted_provider_operation
        if request_provider_id != metadata_provider_id:
            raise ValueError("request provider_id does not match authority metadata")
        if request_operation != metadata_operation:
            raise ValueError(
                "request permitted_provider_operation does not match authority metadata"
            )
        request_bytes = snapshot.canonical_json()
        request_digest = _digest(request_bytes)
        _require_evidence_pair(
            request_bytes, request_digest, field="session request digest"
        )
        session_id = _session_id(
            snapshot,
            machine_authority_id=machine_authority_id,
            authority_epoch_id=authority_epoch_id,
            authority_policy_version=authority_policy_version,
            claim_policy_version=claim_policy_version,
        )
        connection.execute(
            """
            INSERT INTO sessions (
                session_id, authority_epoch_id, session_schema,
                authority_policy_version, claim_policy_version,
                target_session_date, state, next_attempt_ordinal,
                next_recovery_ordinal, request_json, request_digest,
                created_at_utc, closed_at_utc, close_reason
            ) VALUES (?, ?, 1, ?, ?, ?, 'OPEN', 0, 0, ?, ?, ?, NULL, NULL)
            """,
            (
                session_id,
                authority_epoch_id,
                authority_policy_version,
                claim_policy_version,
                snapshot.target_session_date,
                request_bytes,
                request_digest,
                created_at_utc,
            ),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return session_id


@_serialized_connection_operation
def _core_allocate_attempt(
    connection: sqlite3.Connection,
    session_id: str,
    ordinal: int | None = None,
    *,
    created_at_utc: str = TIMESTAMP,
) -> str:
    _require_service_context()
    requested_ordinal = (
        None if ordinal is None else _canonical_ordinal(ordinal, "attempt ordinal")
    )
    _begin(connection)
    try:
        row = connection.execute(
            """
            SELECT s.next_attempt_ordinal, s.request_json, s.request_digest,
                   m.provider_id, m.permitted_provider_operation,
                   s.authority_policy_version, s.claim_policy_version,
                   m.authority_policy_version, m.claim_policy_version
            FROM sessions s
            JOIN authority_metadata m
              ON m.authority_epoch_id = s.authority_epoch_id
            WHERE s.session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown session")
        (
            current_ordinal,
            request_bytes,
            request_digest,
            provider_id,
            operation,
            authority_policy_version,
            claim_policy_version,
            metadata_authority_policy,
            metadata_claim_policy,
        ) = row
        if (
            authority_policy_version != metadata_authority_policy
            or claim_policy_version != metadata_claim_policy
        ):
            raise ValueError("session policy lineage does not match metadata")
        current_ordinal = _canonical_ordinal(current_ordinal, "attempt ordinal")
        allocated_ordinal = (
            current_ordinal if requested_ordinal is None else requested_ordinal
        )
        attempt_id = _attempt_id(
            session_id,
            allocated_ordinal,
            provider_id,
            operation,
            claim_policy_version,
        )
        allocation_evidence, allocation_digest = _evidence(
            f"allocation:{allocated_ordinal}"
        )
        attempt_evidence, attempt_digest = _evidence(f"attempt:{allocated_ordinal}")
        _require_evidence_pair(
            request_bytes, request_digest, field="attempt request digest"
        )
        _require_evidence_pair(
            allocation_evidence, allocation_digest, field="attempt allocation digest"
        )
        _require_evidence_pair(
            attempt_evidence, attempt_digest, field="attempt evidence digest"
        )
        connection.execute(
            """
            INSERT INTO attempts (
                attempt_id, session_id, ordinal, provider_id,
                permitted_provider_operation, provider_call_budget,
                request_json, request_digest, attempt_schema,
                attempt_policy_version, allocation_evidence_json,
                allocation_evidence_digest, attempt_evidence_json,
                attempt_evidence_digest, state, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, 1, ?, ?, ?, ?, ?, 'ALLOCATED', ?)
            """,
            (
                attempt_id,
                session_id,
                allocated_ordinal,
                provider_id,
                operation,
                request_bytes,
                request_digest,
                claim_policy_version,
                allocation_evidence,
                allocation_digest,
                attempt_evidence,
                attempt_digest,
                created_at_utc,
            ),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return attempt_id


def _validate_claim_admission_evidence(
    connection: sqlite3.Connection, session_id: str
) -> None:
    """Validate retry-safe prior outcomes before admitting a new claim."""

    rows = connection.execute(
        """
        SELECT safe_reservation.process_creation_failure_json,
               safe_reservation.process_creation_failure_digest,
               safe_reservation.process_intent_json,
               safe_reservation.process_intent_digest
        FROM provider_call_claims prior_claim
        JOIN attempts prior_attempt
          ON prior_attempt.attempt_id = prior_claim.attempt_id
        JOIN launch_reservations safe_reservation
          ON safe_reservation.claim_id = prior_claim.claim_id
        JOIN terminals safe_terminal
          ON safe_terminal.launch_reservation_id =
             safe_reservation.launch_reservation_id
        WHERE prior_attempt.session_id = ?
          AND prior_attempt.state = 'TERMINAL_RECORDED'
          AND safe_reservation.reservation_state = 'TERMINAL_RECORDED'
          AND safe_reservation.process_creation_failure_json IS NOT NULL
          AND safe_reservation.process_creation_failure_digest IS NOT NULL
          AND safe_terminal.terminal_state = 'FAILED'
          AND safe_terminal.provider_call_disposition = 'NOT_STARTED'
          AND safe_terminal.snapshot_digest IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM launch_executions prior_execution
              WHERE prior_execution.launch_reservation_id =
                    safe_reservation.launch_reservation_id
          )
        """,
        (session_id,),
    ).fetchall()
    for (
        process_failure,
        process_failure_digest,
        process_intent,
        process_intent_digest,
    ) in rows:
        _require_evidence_pair(
            process_failure,
            process_failure_digest,
            field="retry-safe process failure digest",
        )
        _require_evidence_pair(
            process_intent,
            process_intent_digest,
            field="retry-safe process intent digest",
        )


@_serialized_connection_operation
def _core_commit_claim(
    connection: sqlite3.Connection,
    attempt_id: str,
    *,
    committed_at_utc: str = TIMESTAMP,
) -> str:
    _require_service_context()
    evidence, evidence_digest = _evidence(f"claim:{attempt_id}")
    _begin(connection)
    try:
        attempt = connection.execute(
            """
            SELECT a.session_id, a.request_json, a.request_digest, a.provider_id,
                   a.permitted_provider_operation, a.provider_call_budget,
                   a.attempt_policy_version
            FROM attempts a WHERE attempt_id = ?
            """,
            (attempt_id,),
        ).fetchone()
        if attempt is None:
            raise ValueError("unknown attempt")
        (
            session_id,
            request_bytes,
            request_digest,
            provider_id,
            operation,
            budget,
            claim_policy_version,
        ) = attempt
        _require_evidence_pair(
            request_bytes, request_digest, field="claim request digest"
        )
        _validate_claim_admission_evidence(connection, session_id)
        _require_evidence_pair(evidence, evidence_digest, field="claim evidence digest")
        claim_id = _claim_id(
            attempt_id,
            claim_policy_version,
            provider_id,
            operation,
            budget,
        )
        connection.execute(
            """
            INSERT INTO provider_call_claims (
                claim_id, attempt_id, claim_schema, claim_policy_version,
                provider_id, permitted_provider_operation, provider_call_budget,
                request_json, request_digest, claim_evidence_json,
                claim_evidence_digest, state, committed_at_utc
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 'COMMITTED', ?)
            """,
            (
                claim_id,
                attempt_id,
                claim_policy_version,
                provider_id,
                operation,
                budget,
                request_bytes,
                request_digest,
                evidence,
                evidence_digest,
                committed_at_utc,
            ),
        )
        connection.execute(
            "UPDATE attempts SET state = 'CLAIM_COMMITTED' WHERE attempt_id = ?",
            (attempt_id,),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return claim_id


@_serialized_connection_operation
def _core_reserve_launch(
    connection: sqlite3.Connection,
    claim_id: str,
    *,
    committed_at_utc: str = TIMESTAMP,
) -> ProviderConstructionPermit:
    _require_service_context()
    evidence, evidence_digest = _evidence(f"reservation:{claim_id}")
    _begin(connection)
    try:
        claim = connection.execute(
            """
            SELECT c.attempt_id, c.request_digest, c.claim_policy_version,
                   s.authority_policy_version, a.request_json
            FROM provider_call_claims c
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE c.claim_id = ?
            """,
            (claim_id,),
        ).fetchone()
        if claim is None:
            raise ValueError("unknown claim")
        (
            attempt_id,
            request_digest,
            claim_policy_version,
            authority_policy_version,
            request_bytes,
        ) = claim
        _require_evidence_pair(
            request_bytes, request_digest, field="reservation request digest"
        )
        _require_evidence_pair(
            evidence, evidence_digest, field="reservation evidence digest"
        )
        reservation_id = _reservation_id(
            claim_id,
            RELEASE,
            authority_policy_version,
            claim_policy_version,
        )
        connection.execute(
            """
            INSERT INTO launch_reservations (
                launch_reservation_id, claim_id, launch_reservation_schema,
                application_release_version, authority_policy_version,
                claim_policy_version, request_digest, reservation_evidence_json,
                reservation_evidence_digest, reservation_state,
                process_creation_failure_json, process_creation_failure_digest,
                committed_at_utc, outcome_recorded_at_utc
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, 'COMMITTED', NULL, NULL, ?, NULL)
            """,
            (
                reservation_id,
                claim_id,
                RELEASE,
                authority_policy_version,
                claim_policy_version,
                request_digest,
                evidence,
                evidence_digest,
                committed_at_utc,
            ),
        )
        connection.execute(
            "UPDATE attempts SET state = 'LAUNCH_RESERVED' WHERE attempt_id = ?",
            (attempt_id,),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    one_shot = _ProviderConstructionOneShot()
    issuer = _service_issuer(
        _PROVIDER_CONSTRUCTION_ISSUER,
        _TEST_PROVIDER_CONSTRUCTION_ISSUER,
    )
    capability = ProviderConstructionPermit(
        reservation_id,
        _issuer=issuer,
        _permit=one_shot,
        _service_token=_active_test_service_token(),
    )
    with _ISSUED_PROVIDER_CONSTRUCTION_PERMITS_LOCK:
        _ISSUED_PROVIDER_CONSTRUCTION_PERMITS[one_shot] = _ProviderConstructionIssuance(
            capability=_weak_reference(capability, "provider capability"),
            reservation_id=reservation_id,
            issuer=issuer,
            permit=_weak_reference(one_shot, "provider permit"),
            service_token=_optional_weak_reference(
                capability._service_token, "provider service token"
            ),
        )
    return capability


def _process_intent_json(
    reservation_id: str,
    request_digest: bytes,
    authority_policy_version: str,
    claim_policy_version: str,
) -> bytes:
    reservation_id = str(reservation_id)
    return _json(
        {
            "authority_policy_version": authority_policy_version,
            "claim_policy_version": claim_policy_version,
            "launch_reservation_id": reservation_id,
            "process_operation": "CreateProcessW",
            "request_digest": request_digest.hex(),
            "schema": 1,
        }
    )


def _registered_provider_reservation_id(
    capability: ProviderConstructionPermit,
) -> str:
    if type(capability) is not ProviderConstructionPermit:
        raise TypeError("provider construction requires a reservation-issued permit")
    if capability._issuer not in (
        _PROVIDER_CONSTRUCTION_ISSUER,
        _TEST_PROVIDER_CONSTRUCTION_ISSUER,
    ):
        raise TypeError("provider construction permit issuer is invalid")
    permit = capability._permit
    if type(permit) is not _ProviderConstructionOneShot:
        raise ValueError("provider construction permit registry binding mismatch")
    with permit.lock:
        with _ISSUED_PROVIDER_CONSTRUCTION_PERMITS_LOCK:
            issuance = _ISSUED_PROVIDER_CONSTRUCTION_PERMITS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError(
                    "provider construction permit was consumed or not issued"
                )
            if (
                _resolve_weak_reference(issuance.capability) is not capability
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not capability._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not capability._service_token
                or issuance.reservation_id != capability.reservation_id
            ):
                raise ValueError(
                    "provider construction permit registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            return issuance.reservation_id


def _consume_provider_construction_permit(
    capability: ProviderConstructionPermit, reservation_id: str
) -> None:
    permit = capability._permit
    if type(permit) is not _ProviderConstructionOneShot:
        raise ValueError("provider construction permit registry binding mismatch")
    with permit.lock:
        with _ISSUED_PROVIDER_CONSTRUCTION_PERMITS_LOCK:
            issuance = _ISSUED_PROVIDER_CONSTRUCTION_PERMITS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError(
                    "provider construction permit was consumed or not issued"
                )
            if (
                _resolve_weak_reference(issuance.capability) is not capability
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not capability._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not capability._service_token
                or issuance.reservation_id != capability.reservation_id
                or issuance.reservation_id != reservation_id
            ):
                raise ValueError(
                    "provider construction permit registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            del _ISSUED_PROVIDER_CONSTRUCTION_PERMITS[permit]
        permit.consumed = True


def _registered_constructed_provider_reservation_id(
    provider: ConstructedProvider,
) -> str:
    if type(provider) is not ConstructedProvider:
        raise TypeError("process intent requires an opaque constructed provider")
    if provider._issuer not in (
        _CONSTRUCTED_PROVIDER_ISSUER,
        _TEST_CONSTRUCTED_PROVIDER_ISSUER,
    ):
        raise TypeError("constructed provider issuer is invalid")
    permit = provider._permit
    if type(permit) is not _ConstructedProviderOneShot:
        raise ValueError("constructed provider registry binding mismatch")
    with permit.lock:
        with _ISSUED_CONSTRUCTED_PROVIDERS_LOCK:
            issuance = _ISSUED_CONSTRUCTED_PROVIDERS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError(
                    "constructed provider was already consumed or not issued"
                )
            if (
                _resolve_weak_reference(issuance.provider) is not provider
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not provider._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not provider._service_token
                or issuance.reservation_id != provider.reservation_id
            ):
                raise ValueError(
                    "constructed provider registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            return issuance.reservation_id


def _consume_constructed_provider(
    provider: ConstructedProvider, reservation_id: str
) -> None:
    permit = provider._permit
    if type(permit) is not _ConstructedProviderOneShot:
        raise ValueError("constructed provider registry binding mismatch")
    with permit.lock:
        with _ISSUED_CONSTRUCTED_PROVIDERS_LOCK:
            issuance = _ISSUED_CONSTRUCTED_PROVIDERS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError(
                    "constructed provider was already consumed or not issued"
                )
            if (
                _resolve_weak_reference(issuance.provider) is not provider
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not provider._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not provider._service_token
                or issuance.reservation_id != provider.reservation_id
                or issuance.reservation_id != reservation_id
            ):
                raise ValueError(
                    "constructed provider registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            del _ISSUED_CONSTRUCTED_PROVIDERS[permit]
        permit.consumed = True


def _require_provider_construction_lineage(
    connection: sqlite3.Connection, reservation_id: str
) -> _ProviderConstructionLineage:
    row = connection.execute(
        """
        SELECT r.reservation_state, r.request_digest,
               r.authority_policy_version, r.claim_policy_version,
               r.process_intent_json, r.process_intent_digest,
               r.reservation_evidence_json, r.reservation_evidence_digest,
               c.state, c.request_json, c.request_digest,
               c.claim_policy_version, c.claim_evidence_json,
               c.claim_evidence_digest,
               a.state, a.request_json, a.request_digest,
               a.attempt_policy_version, a.provider_id,
               a.permitted_provider_operation, a.provider_call_budget,
               s.state, s.request_json, s.request_digest,
               s.authority_policy_version, s.claim_policy_version,
               m.provider_id, m.permitted_provider_operation,
               m.authority_policy_version, m.claim_policy_version
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        JOIN authority_metadata m ON m.singleton_key = 1
        WHERE r.launch_reservation_id = ?
          AND r.reservation_state = 'COMMITTED'
          AND r.process_intent_json IS NULL
          AND r.process_intent_digest IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM launch_executions e
              WHERE e.launch_reservation_id = r.launch_reservation_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM terminals t
              WHERE t.launch_reservation_id = r.launch_reservation_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM session_selections ss
              WHERE ss.session_id = s.session_id
          )
        """,
        (str(reservation_id),),
    ).fetchone()
    if row is None:
        durable_status = connection.execute(
            """
            SELECT r.reservation_state, r.process_intent_json,
                   EXISTS (
                       SELECT 1 FROM launch_executions e
                       WHERE e.launch_reservation_id = r.launch_reservation_id
                   ),
                   EXISTS (
                       SELECT 1 FROM terminals t
                       WHERE t.launch_reservation_id = r.launch_reservation_id
                   ),
                   EXISTS (
                       SELECT 1 FROM session_selections ss
                       JOIN attempts a ON a.session_id = ss.session_id
                       JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
                       JOIN launch_reservations lr ON lr.claim_id = c.claim_id
                       WHERE lr.launch_reservation_id = r.launch_reservation_id
                   )
            FROM launch_reservations r
            WHERE r.launch_reservation_id = ?
            """,
            (str(reservation_id),),
        ).fetchone()
        if durable_status is not None:
            (
                durable_reservation_state,
                durable_process_intent_json,
                has_execution,
                has_terminal,
                has_selection,
            ) = durable_status
            if (
                durable_reservation_state != "COMMITTED"
                or durable_process_intent_json is not None
                or has_execution
                or has_terminal
                or has_selection
            ):
                raise ValueError("provider construction active lineage is revoked")
        raise ValueError("provider construction active lineage is unavailable")
    (
        reservation_state,
        request_digest,
        authority_policy_version,
        claim_policy_version,
        process_intent_json,
        process_intent_digest,
        reservation_evidence,
        reservation_evidence_digest,
        claim_state,
        claim_request,
        claim_request_digest,
        claim_policy,
        claim_evidence,
        claim_evidence_digest,
        attempt_state,
        attempt_request,
        attempt_request_digest,
        attempt_policy,
        attempt_provider,
        attempt_operation,
        attempt_budget,
        session_state,
        session_request,
        session_request_digest,
        session_authority_policy,
        session_claim_policy,
        metadata_provider,
        metadata_operation,
        metadata_authority_policy,
        metadata_claim_policy,
    ) = row
    if reservation_state != "COMMITTED" or process_intent_json is not None:
        raise ValueError("provider construction requires COMMITTED")
    if process_intent_digest is not None:
        raise ValueError("provider construction intent lineage is invalid")
    if (
        _digest(reservation_evidence) != reservation_evidence_digest
        or _digest(claim_evidence) != claim_evidence_digest
        or _digest(claim_request) != claim_request_digest
        or claim_request != attempt_request
        or claim_request != session_request
        or request_digest != claim_request_digest
        or request_digest != attempt_request_digest
        or request_digest != session_request_digest
    ):
        raise ValueError("provider construction request or evidence binding is invalid")
    if (
        claim_state != "COMMITTED"
        or attempt_state != "LAUNCH_RESERVED"
        or session_state != "OPEN"
        or claim_policy_version != claim_policy
        or claim_policy != attempt_policy
        or claim_policy != session_claim_policy
        or claim_policy != metadata_claim_policy
        or authority_policy_version != session_authority_policy
        or authority_policy_version != metadata_authority_policy
        or attempt_provider != metadata_provider
        or attempt_provider != PROVIDER
        or attempt_operation != metadata_operation
        or attempt_operation != OPERATION
        or attempt_budget != 1
    ):
        raise ValueError("provider construction policy or claim binding is invalid")
    return _ProviderConstructionLineage(
        request_digest=request_digest,
        authority_policy_version=authority_policy_version,
        claim_policy_version=claim_policy_version,
    )


def _core_commit_process_intent(
    connection: sqlite3.Connection,
    reservation_id: str,
    provider: ConstructedProvider | None = None,
) -> ProcessIntent:
    _require_service_context()
    _require_no_active_transaction(connection)
    if type(provider) is not ConstructedProvider:
        raise TypeError("process intent requires an opaque constructed provider")
    _require_service_provenance(
        provider,
        production_issuer=_CONSTRUCTED_PROVIDER_ISSUER,
        test_issuer=_TEST_CONSTRUCTED_PROVIDER_ISSUER,
        label="constructed provider",
    )
    registered_reservation_id = _registered_constructed_provider_reservation_id(
        provider
    )
    if registered_reservation_id != str(reservation_id):
        raise ValueError("constructed provider belongs to another reservation")
    with _lifecycle_arbiter(registered_reservation_id):
        return _commit_process_intent_locked(
            connection, registered_reservation_id, provider
        )


@_serialized_connection_operation
def _commit_process_intent_locked(
    connection: sqlite3.Connection,
    reservation_id: str,
    provider: ConstructedProvider,
) -> ProcessIntent:
    reservation_id = str(reservation_id)
    if _registered_constructed_provider_reservation_id(provider) != reservation_id:
        raise ValueError("constructed provider registry binding mismatch")
    lineage = _require_provider_construction_lineage(connection, reservation_id)
    request_digest = lineage.request_digest
    authority_policy_version = lineage.authority_policy_version
    claim_policy_version = lineage.claim_policy_version
    _begin(connection)
    try:
        intent_json = _process_intent_json(
            reservation_id,
            request_digest,
            authority_policy_version,
            claim_policy_version,
        )
        intent_digest = _digest(intent_json)
        cursor = connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'PROCESS_INTENT_COMMITTED',
                process_intent_json = ?, process_intent_digest = ?,
                process_intent_committed_at_utc = ?
            WHERE launch_reservation_id = ? AND reservation_state = 'COMMITTED'
            """,
            (
                intent_json,
                intent_digest,
                _timestamp(PROCESS_INTENT_TIMESTAMP),
                reservation_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("process intent ownership was not acquired")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    _consume_constructed_provider(provider, reservation_id)
    permit = _ProcessPermit()
    issuer = _service_issuer(_PROCESS_INTENT_ISSUER, _TEST_PROCESS_INTENT_ISSUER)
    intent = ProcessIntent(
        reservation_id=reservation_id,
        intent_json=intent_json,
        intent_digest=intent_digest,
        _issuer=issuer,
        _permit=permit,
        _service_token=_active_test_service_token(),
    )
    with _ISSUED_PROCESS_PERMITS_LOCK:
        _ISSUED_PROCESS_PERMITS[permit] = _ProcessIntentIssuance(
            intent=_weak_reference(intent, "process intent"),
            reservation_id=reservation_id,
            intent_json=intent_json,
            intent_digest=intent_digest,
            issuer=issuer,
            permit=_weak_reference(permit, "process intent permit"),
            service_token=_optional_weak_reference(
                intent._service_token, "process intent service token"
            ),
        )
    return intent


def _process_success_evidence(
    reservation_id: str, process_intent_digest: bytes
) -> tuple[bytes, bytes, bytes]:
    reservation_id = str(reservation_id)
    common = {
        "process_intent_digest": process_intent_digest.hex(),
        "reservation_id": reservation_id,
        "schema": 1,
    }
    return (
        _json({**common, "creation_result": "SUSPENDED_CHILD_CREATED"}),
        _json({**common, "job_object_result": "ASSIGNED"}),
        _json({**common, "resume_authorization": "SUSPENDED_THREAD_OWNED"}),
    )


def _production_process_success_evidence(
    reservation_id: str,
    process_intent_digest: bytes,
    *,
    application_name: str,
    child_base_arguments: tuple[str, ...],
) -> tuple[bytes, bytes, bytes]:
    """Canonical sanitized evidence issued only after real native creation."""

    reservation_id = str(reservation_id)
    if type(application_name) is not str or not application_name:
        raise TypeError("production process evidence application is invalid")
    if (
        type(child_base_arguments) is not tuple
        or len(child_base_arguments) != 2
        or not all(type(value) is str and value for value in child_base_arguments)
    ):
        raise TypeError("production child base arguments are invalid")
    common = {
        "process_intent_digest": process_intent_digest.hex(),
        "reservation_id": reservation_id,
        "schema": 1,
    }
    return (
        _json(
            {
                **common,
                "application_name": application_name,
                "child_base_arguments": list(child_base_arguments),
                "creation_flags_policy": "C3_EXACT_SUSPENDED_NO_WINDOW_V1",
                "creation_result": "SUSPENDED_CHILD_CREATED",
                "environment_policy": "C3_EXACT_FIVE_ENTRY_V1",
                "handle_list_count": 3,
                "handle_list_policy": "C3_EXACT_REQUEST_RESULT_STAGING_V1",
                "shell_or_path_resolution": False,
            }
        ),
        _json(
            {
                **common,
                "active_process_limit": 1,
                "breakaway_allowed": False,
                "job_assignment": "AT_PROCESS_CREATION",
                "job_object_result": "ASSIGNED",
                "kill_on_job_close": True,
            }
        ),
        _json(
            {
                **common,
                "previous_suspend_count_required": 1,
                "resume_authorization": "EXACT_PRIMARY_THREAD_RETAINED",
            }
        ),
    )


def _require_production_process_success_evidence(
    receipt: ProcessCreationReceipt,
) -> tuple[bytes, bytes, bytes]:
    common = {
        "process_intent_digest": receipt.process_intent_digest.hex(),
        "reservation_id": receipt.reservation_id,
        "schema": 1,
    }
    try:
        process = json.loads(receipt.process_json)
        job = json.loads(receipt.job_json)
        resume = json.loads(receipt.resume_authorization_json)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        raise ValueError("production process evidence is not canonical JSON") from None
    if (
        type(process) is not dict
        or set(process)
        != {
            *common,
            "application_name",
            "child_base_arguments",
            "creation_flags_policy",
            "creation_result",
            "environment_policy",
            "handle_list_count",
            "handle_list_policy",
            "shell_or_path_resolution",
        }
        or any(process.get(key) != value for key, value in common.items())
        or type(process.get("application_name")) is not str
        or not process["application_name"]
        or type(process.get("child_base_arguments")) is not list
        or len(process["child_base_arguments"]) != 2
        or not all(
            type(value) is str and value for value in process["child_base_arguments"]
        )
        or process.get("creation_flags_policy") != "C3_EXACT_SUSPENDED_NO_WINDOW_V1"
        or process.get("creation_result") != "SUSPENDED_CHILD_CREATED"
        or process.get("environment_policy") != "C3_EXACT_FIVE_ENTRY_V1"
        or process.get("handle_list_count") != 3
        or process.get("handle_list_policy") != "C3_EXACT_REQUEST_RESULT_STAGING_V1"
        or process.get("shell_or_path_resolution") is not False
    ):
        raise ValueError("production process evidence is invalid")
    if type(job) is not dict or job != {
        **common,
        "active_process_limit": 1,
        "breakaway_allowed": False,
        "job_assignment": "AT_PROCESS_CREATION",
        "job_object_result": "ASSIGNED",
        "kill_on_job_close": True,
    }:
        raise ValueError("production Job Object evidence is invalid")
    if type(resume) is not dict or resume != {
        **common,
        "previous_suspend_count_required": 1,
        "resume_authorization": "EXACT_PRIMARY_THREAD_RETAINED",
    }:
        raise ValueError("production resume authorization evidence is invalid")
    expected = (_json(process), _json(job), _json(resume))
    if expected != (
        receipt.process_json,
        receipt.job_json,
        receipt.resume_authorization_json,
    ):
        raise ValueError("production process evidence is not canonical")
    if (
        receipt.process_digest != _digest(expected[0])
        or receipt.job_digest != _digest(expected[1])
        or receipt.resume_authorization_digest != _digest(expected[2])
    ):
        raise ValueError("production process evidence digest is invalid")
    return expected


def _process_failure_json(reservation_id: str, process_intent_digest: bytes) -> bytes:
    reservation_id = str(reservation_id)
    return _json(
        {
            "creation_result": "NOT_CREATED",
            "process_intent_digest": process_intent_digest.hex(),
            "reservation_id": reservation_id,
            "schema": 1,
        }
    )


def _registered_process_intent_reservation_id(intent: ProcessIntent) -> str:
    if type(intent) is not ProcessIntent:
        raise TypeError("CreateProcessW requires an opaque fake process intent")
    if intent._issuer not in (_PROCESS_INTENT_ISSUER, _TEST_PROCESS_INTENT_ISSUER):
        raise TypeError("CreateProcessW process intent issuer is invalid")
    permit = intent._permit
    if type(permit) is not _ProcessPermit:
        raise ValueError("CreateProcessW process intent registry binding mismatch")
    with permit.lock:
        with _ISSUED_PROCESS_PERMITS_LOCK:
            issuance = _ISSUED_PROCESS_PERMITS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError(
                    "CreateProcessW process intent was already consumed or not issued"
                )
            if (
                _resolve_weak_reference(issuance.intent) is not intent
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not intent._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not intent._service_token
                or issuance.reservation_id != intent.reservation_id
                or issuance.intent_json != intent.intent_json
                or issuance.intent_digest != intent.intent_digest
            ):
                raise ValueError(
                    "CreateProcessW process intent registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            return issuance.reservation_id


def _consume_process_intent(intent: ProcessIntent, reservation_id: str) -> None:
    permit = intent._permit
    if type(permit) is not _ProcessPermit:
        raise ValueError("CreateProcessW process intent registry binding mismatch")
    with permit.lock:
        with _ISSUED_PROCESS_PERMITS_LOCK:
            issuance = _ISSUED_PROCESS_PERMITS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError(
                    "CreateProcessW process intent was already consumed or not issued"
                )
            if (
                _resolve_weak_reference(issuance.intent) is not intent
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not intent._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not intent._service_token
                or issuance.reservation_id != intent.reservation_id
                or issuance.reservation_id != reservation_id
                or issuance.intent_json != intent.intent_json
                or issuance.intent_digest != intent.intent_digest
            ):
                raise ValueError(
                    "CreateProcessW process intent registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            del _ISSUED_PROCESS_PERMITS[permit]
        permit.consumed = True


def _process_result_visible_evidence(
    result: ProcessCreationReceipt | ProcessCreationFailure,
) -> tuple[tuple[bytes, ...], tuple[bytes, ...]]:
    if type(result) is ProcessCreationReceipt:
        return (
            (
                result.process_json,
                result.job_json,
                result.resume_authorization_json,
            ),
            (
                result.process_digest,
                result.job_digest,
                result.resume_authorization_digest,
            ),
        )
    if type(result) is ProcessCreationFailure:
        return (result.result_json,), (result.result_digest,)
    raise TypeError("process result type is invalid")


def _registered_process_result_reservation_id(
    result: ProcessCreationReceipt | ProcessCreationFailure,
) -> str:
    if type(result) not in {ProcessCreationReceipt, ProcessCreationFailure}:
        raise TypeError("process result type is invalid")
    if result._issuer not in (_PROCESS_RESULT_ISSUER, _TEST_PROCESS_RESULT_ISSUER):
        raise TypeError("process result issuer is invalid")
    permit = result._permit
    if type(permit) is not _ProcessResultPermit:
        raise ValueError("process result registry binding mismatch")
    with permit.lock:
        with _ISSUED_PROCESS_RESULTS_LOCK:
            issuance = _ISSUED_PROCESS_RESULTS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError("process result was already consumed or not issued")
            evidence, digests = _process_result_visible_evidence(result)
            if (
                _resolve_weak_reference(issuance.result) is not result
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not result._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not result._service_token
                or issuance.reservation_id != result.reservation_id
                or issuance.process_intent_digest != result.process_intent_digest
                or issuance.evidence != evidence
                or issuance.digests != digests
            ):
                raise ValueError(
                    "process result registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            return issuance.reservation_id


def _consume_process_result(
    result: ProcessCreationReceipt | ProcessCreationFailure,
    reservation_id: str,
) -> None:
    permit = result._permit
    if type(permit) is not _ProcessResultPermit:
        raise ValueError("process result registry binding mismatch")
    with permit.lock:
        with _ISSUED_PROCESS_RESULTS_LOCK:
            issuance = _ISSUED_PROCESS_RESULTS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError("process result was already consumed or not issued")
            evidence, digests = _process_result_visible_evidence(result)
            if (
                _resolve_weak_reference(issuance.result) is not result
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not result._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not result._service_token
                or issuance.reservation_id != result.reservation_id
                or issuance.reservation_id != reservation_id
                or issuance.process_intent_digest != result.process_intent_digest
                or issuance.evidence != evidence
                or issuance.digests != digests
            ):
                raise ValueError(
                    "process result registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            del _ISSUED_PROCESS_RESULTS[permit]
        permit.consumed = True


def _registered_resume_intent_binding(intent: ResumeIntent) -> tuple[str, str]:
    if type(intent) is not ResumeIntent:
        raise TypeError("ResumeThread requires an opaque fake resume intent")
    if intent._issuer not in (_RESUME_INTENT_ISSUER, _TEST_RESUME_INTENT_ISSUER):
        raise TypeError("ResumeThread intent issuer is invalid")
    permit = intent._permit
    if type(permit) is not _ResumePermit:
        raise ValueError("ResumeThread intent registry binding mismatch")
    with permit.lock:
        with _ISSUED_RESUME_PERMITS_LOCK:
            issuance = _ISSUED_RESUME_PERMITS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError(
                    "ResumeThread intent was already consumed or not issued"
                )
            if (
                _resolve_weak_reference(issuance.intent) is not intent
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not intent._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not intent._service_token
                or issuance.execution_id != intent.execution_id
                or issuance.reservation_id != intent.reservation_id
                or issuance.intent_json != intent.intent_json
                or issuance.intent_digest != intent.intent_digest
            ):
                raise ValueError(
                    "ResumeThread intent registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            return issuance.execution_id, issuance.reservation_id


def _consume_resume_intent(
    intent: ResumeIntent, execution_id: str, reservation_id: str
) -> None:
    permit = intent._permit
    if type(permit) is not _ResumePermit:
        raise ValueError("ResumeThread intent registry binding mismatch")
    with permit.lock:
        with _ISSUED_RESUME_PERMITS_LOCK:
            issuance = _ISSUED_RESUME_PERMITS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError(
                    "ResumeThread intent was already consumed or not issued"
                )
            if (
                _resolve_weak_reference(issuance.intent) is not intent
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not intent._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not intent._service_token
                or issuance.execution_id != intent.execution_id
                or issuance.execution_id != execution_id
                or issuance.reservation_id != intent.reservation_id
                or issuance.reservation_id != reservation_id
                or issuance.intent_json != intent.intent_json
                or issuance.intent_digest != intent.intent_digest
            ):
                raise ValueError(
                    "ResumeThread intent registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            del _ISSUED_RESUME_PERMITS[permit]
        permit.consumed = True


def _registered_resume_result_binding(result: ResumeReceipt) -> tuple[str, str]:
    if type(result) is not ResumeReceipt:
        raise TypeError("post-resume evidence requires a fake resume receipt")
    if result._issuer not in (_RESUME_RESULT_ISSUER, _TEST_RESUME_RESULT_ISSUER):
        raise TypeError("resume result issuer is invalid")
    permit = result._permit
    if type(permit) is not _ResumeResultPermit:
        raise ValueError("resume result registry binding mismatch")
    with permit.lock:
        with _ISSUED_RESUME_RESULTS_LOCK:
            issuance = _ISSUED_RESUME_RESULTS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError("resume result was already consumed or not issued")
            if (
                _resolve_weak_reference(issuance.result) is not result
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not result._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not result._service_token
                or issuance.execution_id != result.execution_id
                or issuance.reservation_id != result.reservation_id
                or issuance.resume_intent_digest != result.resume_intent_digest
                or issuance.result_json != result.result_json
                or issuance.result_digest != result.result_digest
            ):
                raise ValueError(
                    "resume result registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            return issuance.execution_id, issuance.reservation_id


def _consume_resume_result(
    result: ResumeReceipt, execution_id: str, reservation_id: str
) -> None:
    permit = result._permit
    if type(permit) is not _ResumeResultPermit:
        raise ValueError("resume result registry binding mismatch")
    with permit.lock:
        with _ISSUED_RESUME_RESULTS_LOCK:
            issuance = _ISSUED_RESUME_RESULTS.get(permit)
            if permit.consumed or issuance is None:
                raise ValueError("resume result was already consumed or not issued")
            if (
                _resolve_weak_reference(issuance.result) is not result
                or _resolve_weak_reference(issuance.permit) is not permit
                or issuance.issuer is not result._issuer
                or _resolve_weak_reference(issuance.service_token)
                is not result._service_token
                or issuance.execution_id != result.execution_id
                or issuance.execution_id != execution_id
                or issuance.reservation_id != result.reservation_id
                or issuance.reservation_id != reservation_id
                or issuance.resume_intent_digest != result.resume_intent_digest
                or issuance.result_json != result.result_json
                or issuance.result_digest != result.result_digest
            ):
                raise ValueError(
                    "resume result registry binding mismatch: "
                    "exact object or fields were not issued"
                )
            del _ISSUED_RESUME_RESULTS[permit]
        permit.consumed = True


def _require_process_creation_lineage(
    connection: sqlite3.Connection,
    reservation_id: str,
    process_intent_digest: bytes,
    process_intent_json: bytes | None = None,
) -> _ProcessCreationLineage:
    row = connection.execute(
        """
        SELECT r.application_release_version, r.authority_policy_version,
               r.reservation_state, r.process_intent_json,
               r.process_intent_digest, c.state, a.state, s.state
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE r.launch_reservation_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM terminals t
              WHERE t.launch_reservation_id = r.launch_reservation_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM session_selections ss
              WHERE ss.session_id = s.session_id
          )
        """,
        (str(reservation_id),),
    ).fetchone()
    if row is None:
        raise ValueError("process creation active lineage is unavailable")
    (
        application_release_version,
        authority_policy_version,
        reservation_state,
        committed_intent_json,
        committed_intent_digest,
        claim_state,
        attempt_state,
        session_state,
    ) = row
    if reservation_state != "PROCESS_INTENT_COMMITTED":
        raise ValueError("process creation requires PROCESS_INTENT_COMMITTED")
    if (
        claim_state != "COMMITTED"
        or attempt_state != "LAUNCH_RESERVED"
        or session_state != "OPEN"
    ):
        raise ValueError("process creation active parent lineage is revoked")
    if (
        committed_intent_json is None
        or _digest(committed_intent_json) != committed_intent_digest
        or process_intent_digest != committed_intent_digest
        or (
            process_intent_json is not None
            and process_intent_json != committed_intent_json
        )
    ):
        raise ValueError("process creation intent binding is invalid")
    return _ProcessCreationLineage(
        application_release_version=application_release_version,
        authority_policy_version=authority_policy_version,
        process_intent_json=committed_intent_json,
        process_intent_digest=committed_intent_digest,
    )


def _core_record_execution(
    connection: sqlite3.Connection,
    reservation_id: str,
    receipt: ProcessCreationReceipt,
) -> str:
    _require_service_context()
    _require_no_active_transaction(connection)
    if type(receipt) is not ProcessCreationReceipt:
        raise TypeError("record_execution requires a fake process creation receipt")
    _require_service_provenance(
        receipt,
        production_issuer=_PROCESS_RESULT_ISSUER,
        test_issuer=_TEST_PROCESS_RESULT_ISSUER,
        label="process creation receipt",
    )
    registered_reservation_id = _registered_process_result_reservation_id(receipt)
    if registered_reservation_id != str(reservation_id):
        raise ValueError("process creation receipt belongs to another reservation")
    with _lifecycle_arbiter(registered_reservation_id):
        return _record_execution_locked(connection, registered_reservation_id, receipt)


@_serialized_connection_operation
def _record_execution_locked(
    connection: sqlite3.Connection,
    reservation_id: str,
    receipt: ProcessCreationReceipt,
) -> str:
    reservation_id = str(reservation_id)
    if _registered_process_result_reservation_id(receipt) != reservation_id:
        raise ValueError("process result registry binding mismatch")
    if receipt._issuer is _PROCESS_RESULT_ISSUER:
        process, job, resume = _require_production_process_success_evidence(receipt)
    else:
        process, job, resume = _process_success_evidence(
            reservation_id, receipt.process_intent_digest
        )
    if (
        receipt.process_json != process
        or receipt.process_digest != _digest(process)
        or receipt.job_json != job
        or receipt.job_digest != _digest(job)
        or receipt.resume_authorization_json != resume
        or receipt.resume_authorization_digest != _digest(resume)
    ):
        raise ValueError("process creation receipt is not exact canonical evidence")
    lineage = _require_process_creation_lineage(
        connection, reservation_id, receipt.process_intent_digest
    )
    application_release_version = lineage.application_release_version
    authority_policy_version = lineage.authority_policy_version
    intent_digest = lineage.process_intent_digest
    _begin(connection)
    try:
        execution_id = _execution_id(
            reservation_id,
            application_release_version,
            authority_policy_version,
        )
        connection.execute(
            """
            INSERT INTO launch_executions (
                launch_execution_id, launch_reservation_id, launch_schema,
                application_release_version, authority_policy_version, phase,
                process_creation_json, process_creation_digest, job_object_json,
                job_object_digest, resume_authorization_json,
                resume_authorization_digest, resume_intent_json,
                resume_intent_digest, resume_intent_committed_at_utc,
                post_resume_json, post_resume_digest, cleanup_json,
                cleanup_digest, created_at_utc
            ) VALUES (?, ?, 1, ?, ?, 'PRE_RESUME_READY', ?, ?, ?, ?, ?, ?,
                      NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)
            """,
            (
                execution_id,
                reservation_id,
                application_release_version,
                authority_policy_version,
                process,
                receipt.process_digest,
                job,
                receipt.job_digest,
                resume,
                receipt.resume_authorization_digest,
                _timestamp(PROCESS_CREATED_TIMESTAMP),
            ),
        )
        cursor = connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'PROCESS_CREATED', outcome_recorded_at_utc = ?
            WHERE launch_reservation_id = ?
              AND reservation_state = 'PROCESS_INTENT_COMMITTED'
              AND process_intent_digest IS ?
              AND EXISTS (
                  SELECT 1
                  FROM provider_call_claims c
                  JOIN attempts a ON a.attempt_id = c.attempt_id
                  JOIN sessions s ON s.session_id = a.session_id
                  WHERE c.claim_id = launch_reservations.claim_id
                    AND c.state = 'COMMITTED'
                    AND a.state = 'LAUNCH_RESERVED'
                    AND s.state = 'OPEN'
                    AND NOT EXISTS (
                        SELECT 1 FROM terminals t
                        WHERE t.launch_reservation_id =
                              launch_reservations.launch_reservation_id
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM session_selections ss
                        WHERE ss.session_id = s.session_id
                    )
              )
            """,
            (_timestamp(PROCESS_CREATED_TIMESTAMP), reservation_id, intent_digest),
        )
        if cursor.rowcount != 1:
            raise ValueError("execution active parent lineage changed")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    _consume_process_result(receipt, reservation_id)
    return execution_id


def _core_commit_resume_intent(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
) -> ResumeIntent:
    _require_service_context()
    _require_no_active_transaction(connection)
    reservation_id = str(reservation_id)
    with _lifecycle_arbiter(reservation_id):
        return _commit_resume_intent_locked(connection, execution_id, reservation_id)


def _require_pre_resume_ready_lineage(
    connection: sqlite3.Connection, execution_id: str, reservation_id: str
) -> None:
    row = connection.execute(
        """
        SELECT e.phase, e.process_creation_json, e.process_creation_digest,
               e.job_object_json, e.job_object_digest,
               e.resume_authorization_json, e.resume_authorization_digest,
               r.reservation_state, s.state, e.launch_reservation_id
        FROM launch_executions e
        JOIN launch_reservations r
          ON r.launch_reservation_id = e.launch_reservation_id
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE e.launch_execution_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM terminals t
              WHERE t.launch_reservation_id = r.launch_reservation_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM session_selections ss
              WHERE ss.session_id = s.session_id
          )
        """,
        (execution_id,),
    ).fetchone()
    if row is None:
        raise ValueError(
            "unknown execution or resume intent active lineage is unavailable"
        )
    if row[9] != reservation_id:
        raise ValueError("resume execution belongs to another reservation")
    if row[0] != "PRE_RESUME_READY":
        raise ValueError("resume intent requires PRE_RESUME_READY")
    if row[7] != "PROCESS_CREATED" or row[8] != "OPEN":
        raise ValueError("resume intent active parent lineage is revoked")
    for evidence_json, evidence_digest in (
        (row[1], row[2]),
        (row[3], row[4]),
        (row[5], row[6]),
    ):
        if evidence_json is None or _digest(evidence_json) != evidence_digest:
            raise ValueError("resume intent requires exact pre-resume evidence")


@_serialized_connection_operation
def _commit_resume_intent_locked(
    connection: sqlite3.Connection, execution_id: str, reservation_id: str
) -> ResumeIntent:
    reservation_id = str(reservation_id)
    intent_json = _json(
        {
            "execution_id": execution_id,
            "resume_operation": "ResumeThread",
            "schema": 1,
        }
    )
    intent_digest = _digest(intent_json)
    _begin(connection)
    try:
        _require_pre_resume_ready_lineage(connection, execution_id, reservation_id)
        cursor = connection.execute(
            """
            UPDATE launch_executions
            SET phase = 'RESUME_INTENT_COMMITTED', resume_intent_json = ?,
                resume_intent_digest = ?, resume_intent_committed_at_utc = ?
            WHERE launch_execution_id = ?
              AND phase = 'PRE_RESUME_READY'
              AND EXISTS (
                  SELECT 1
                  FROM launch_reservations r
                  JOIN provider_call_claims c ON c.claim_id = r.claim_id
                  JOIN attempts a ON a.attempt_id = c.attempt_id
                  JOIN sessions s ON s.session_id = a.session_id
                  WHERE r.launch_reservation_id =
                        launch_executions.launch_reservation_id
                    AND r.reservation_state = 'PROCESS_CREATED'
                    AND s.state = 'OPEN'
                    AND NOT EXISTS (
                        SELECT 1 FROM terminals t
                        WHERE t.launch_reservation_id = r.launch_reservation_id
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM session_selections ss
                        WHERE ss.session_id = s.session_id
                    )
              )
            """,
            (
                intent_json,
                intent_digest,
                _timestamp(RESUME_INTENT_TIMESTAMP),
                execution_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("resume intent ownership was not acquired")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    permit = _ResumePermit()
    issuer = _service_issuer(_RESUME_INTENT_ISSUER, _TEST_RESUME_INTENT_ISSUER)
    intent = ResumeIntent(
        execution_id=execution_id,
        reservation_id=reservation_id,
        intent_json=intent_json,
        intent_digest=intent_digest,
        _issuer=issuer,
        _permit=permit,
        _service_token=_active_test_service_token(),
    )
    with _ISSUED_RESUME_PERMITS_LOCK:
        _ISSUED_RESUME_PERMITS[permit] = _ResumeIntentIssuance(
            intent=_weak_reference(intent, "resume intent"),
            execution_id=execution_id,
            reservation_id=reservation_id,
            intent_json=intent_json,
            intent_digest=intent_digest,
            issuer=issuer,
            permit=_weak_reference(permit, "resume intent permit"),
            service_token=_optional_weak_reference(
                intent._service_token, "resume intent service token"
            ),
        )
    return intent


def _core_record_process_creation_failure(
    connection: sqlite3.Connection,
    reservation_id: str,
    failure: ProcessCreationFailure,
) -> None:
    _require_service_context()
    _require_no_active_transaction(connection)
    if type(failure) is not ProcessCreationFailure:
        raise TypeError(
            "record_process_creation_failure requires a fake process creation failure"
        )
    _require_service_provenance(
        failure,
        production_issuer=_PROCESS_RESULT_ISSUER,
        test_issuer=_TEST_PROCESS_RESULT_ISSUER,
        label="process creation failure",
    )
    registered_reservation_id = _registered_process_result_reservation_id(failure)
    if registered_reservation_id != str(reservation_id):
        raise ValueError("process creation failure belongs to another reservation")
    with _lifecycle_arbiter(registered_reservation_id):
        _record_process_creation_failure_locked(
            connection, registered_reservation_id, failure
        )


@_serialized_connection_operation
def _record_process_creation_failure_locked(
    connection: sqlite3.Connection,
    reservation_id: str,
    failure: ProcessCreationFailure,
) -> None:
    reservation_id = str(reservation_id)
    if _registered_process_result_reservation_id(failure) != reservation_id:
        raise ValueError("process result registry binding mismatch")
    expected = _process_failure_json(reservation_id, failure.process_intent_digest)
    if failure.result_json != expected or failure.result_digest != _digest(expected):
        raise ValueError("process creation failure is not exact canonical evidence")
    _begin(connection)
    try:
        row = connection.execute(
            """
            SELECT r.reservation_state, r.process_intent_json,
                   r.process_intent_digest, c.state, a.state, s.state
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE r.launch_reservation_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
            """,
            (str(reservation_id),),
        ).fetchone()
        if row is None:
            raise ValueError("unknown reservation")
        if (
            row[0] != "PROCESS_INTENT_COMMITTED"
            or row[1] is None
            or _digest(row[1]) != row[2]
            or failure.process_intent_digest != row[2]
            or row[3] != "COMMITTED"
            or row[4] != "LAUNCH_RESERVED"
            or row[5] != "OPEN"
        ):
            raise ValueError("process creation failure intent binding is invalid")
        cursor = connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'PROCESS_CREATION_FAILED',
                process_creation_failure_json = ?,
                process_creation_failure_digest = ?,
                outcome_recorded_at_utc = ?
            WHERE launch_reservation_id = ?
              AND reservation_state = 'PROCESS_INTENT_COMMITTED'
              AND process_intent_digest IS ?
              AND EXISTS (
                  SELECT 1
                  FROM provider_call_claims c
                  JOIN attempts a ON a.attempt_id = c.attempt_id
                  JOIN sessions s ON s.session_id = a.session_id
                  WHERE c.claim_id = launch_reservations.claim_id
                    AND c.state = 'COMMITTED'
                    AND a.state = 'LAUNCH_RESERVED'
                    AND s.state = 'OPEN'
                    AND NOT EXISTS (
                        SELECT 1 FROM terminals t
                        WHERE t.launch_reservation_id =
                              launch_reservations.launch_reservation_id
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM session_selections ss
                        WHERE ss.session_id = s.session_id
                    )
              )
            """,
            (
                failure.result_json,
                failure.result_digest,
                _timestamp(PROCESS_FAILURE_TIMESTAMP),
                reservation_id,
                row[2],
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("process failure active parent lineage changed")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    _consume_process_result(failure, reservation_id)


def _require_resume_thread_lineage(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
    resume_intent_digest: bytes,
    resume_intent_json: bytes | None = None,
) -> _ResumeThreadLineage:
    row = connection.execute(
        """
        SELECT e.phase, e.process_creation_json, e.process_creation_digest,
               e.job_object_json, e.job_object_digest,
               e.resume_authorization_json, e.resume_authorization_digest,
               e.resume_intent_json, e.resume_intent_digest,
               r.reservation_state, s.state, e.launch_reservation_id
        FROM launch_executions e
        JOIN launch_reservations r
          ON r.launch_reservation_id = e.launch_reservation_id
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE e.launch_execution_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM terminals t
              WHERE t.launch_reservation_id = r.launch_reservation_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM session_selections ss
              WHERE ss.session_id = s.session_id
          )
        """,
        (str(execution_id),),
    ).fetchone()
    if row is None:
        raise ValueError("resume active lineage is unavailable")
    (
        phase,
        process_json,
        process_digest,
        job_json,
        job_digest,
        resume_authorization_json,
        resume_authorization_digest,
        committed_intent_json,
        committed_intent_digest,
        reservation_state,
        session_state,
        committed_reservation_id,
    ) = row
    if committed_reservation_id != str(reservation_id):
        raise ValueError("resume execution belongs to another reservation")
    if phase != "RESUME_INTENT_COMMITTED":
        raise ValueError("resume requires RESUME_INTENT_COMMITTED")
    if reservation_state != "PROCESS_CREATED" or session_state != "OPEN":
        raise ValueError("resume active parent lineage is revoked")
    for evidence_json, evidence_digest in (
        (process_json, process_digest),
        (job_json, job_digest),
        (resume_authorization_json, resume_authorization_digest),
    ):
        if evidence_json is None or _digest(evidence_json) != evidence_digest:
            raise ValueError("resume requires exact pre-resume evidence")
    expected_intent_json = _json(
        {
            "execution_id": str(execution_id),
            "resume_operation": "ResumeThread",
            "schema": 1,
        }
    )
    if (
        committed_intent_json is None
        or _digest(committed_intent_json) != committed_intent_digest
        or committed_intent_json != expected_intent_json
        or resume_intent_digest != committed_intent_digest
        or (
            resume_intent_json is not None
            and resume_intent_json != committed_intent_json
        )
    ):
        raise ValueError("resume intent binding is invalid")
    return _ResumeThreadLineage(
        resume_intent_json=committed_intent_json,
        resume_intent_digest=committed_intent_digest,
    )


def _core_record_post_resume_evidence(
    connection: sqlite3.Connection,
    execution_id: str,
    resume_receipt: ResumeReceipt,
) -> None:
    context = _require_service_context()
    _require_no_active_transaction(connection)
    adapter = context.external_adapter
    if adapter is not None and (
        callable(getattr(adapter, "validate_c3_post_resume_evidence", None))
        or callable(getattr(adapter, "consume_c3_post_resume_evidence", None))
    ):
        raise ExternalAuthorityBoundaryUnavailable(
            "C3 composition requires the C3 post-resume evidence operation"
        )
    if type(resume_receipt) is not ResumeReceipt:
        raise TypeError("post-resume evidence requires a fake resume receipt")
    _require_service_provenance(
        resume_receipt,
        production_issuer=_RESUME_RESULT_ISSUER,
        test_issuer=_TEST_RESUME_RESULT_ISSUER,
        label="resume receipt",
    )
    registered_execution_id, registered_reservation_id = (
        _registered_resume_result_binding(resume_receipt)
    )
    if registered_execution_id != execution_id:
        raise ValueError("fake resume receipt belongs to another execution")
    with _lifecycle_arbiter(registered_reservation_id):
        _record_post_resume_evidence_locked(
            connection,
            registered_execution_id,
            resume_receipt,
        )


@_serialized_connection_operation
def _record_post_resume_evidence_locked(
    connection: sqlite3.Connection,
    execution_id: str,
    resume_receipt: ResumeReceipt,
) -> None:
    if type(resume_receipt) is not ResumeReceipt:
        raise TypeError("post-resume evidence requires a fake resume receipt")
    registered_execution_id, reservation_id = _registered_resume_result_binding(
        resume_receipt
    )
    if registered_execution_id != execution_id:
        raise ValueError("resume result registry binding mismatch")
    cleanup, cleanup_digest = _evidence(f"cleanup:{execution_id}")
    if _digest(cleanup) != cleanup_digest:
        raise ValueError("cleanup evidence digest is invalid")
    lineage = _require_resume_thread_lineage(
        connection,
        execution_id,
        reservation_id,
        resume_receipt.resume_intent_digest,
    )
    resume_intent_digest = lineage.resume_intent_digest
    _begin(connection)
    try:
        expected_result = _json(
            {
                "execution_id": execution_id,
                "resume_intent_digest": resume_intent_digest.hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        if resume_receipt.result_json != expected_result:
            raise ValueError("fake resume receipt is not the exact canonical success")
        if resume_receipt.result_digest != _digest(expected_result):
            raise ValueError("fake resume receipt digest is invalid")
        cursor = connection.execute(
            """
            UPDATE launch_executions
            SET phase = 'RESUME_RECORDED', post_resume_json = ?,
                post_resume_digest = ?, cleanup_json = ?, cleanup_digest = ?
            WHERE launch_execution_id = ?
              AND phase = 'RESUME_INTENT_COMMITTED'
              AND resume_intent_digest IS ?
              AND EXISTS (
                  SELECT 1
                  FROM launch_reservations r
                  JOIN provider_call_claims c ON c.claim_id = r.claim_id
                  JOIN attempts a ON a.attempt_id = c.attempt_id
                  JOIN sessions s ON s.session_id = a.session_id
                  WHERE r.launch_reservation_id =
                        launch_executions.launch_reservation_id
                    AND r.reservation_state = 'PROCESS_CREATED'
                    AND s.state = 'OPEN'
                    AND NOT EXISTS (
                        SELECT 1 FROM terminals t
                        WHERE t.launch_reservation_id = r.launch_reservation_id
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM session_selections ss
                        WHERE ss.session_id = s.session_id
                    )
              )
            """,
            (
                expected_result,
                resume_receipt.result_digest,
                cleanup,
                cleanup_digest,
                execution_id,
                resume_intent_digest,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("post-resume active lineage changed before persistence")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    _consume_resume_result(resume_receipt, execution_id, reservation_id)


def _require_c3_post_resume_lineage(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
    resume_intent_digest: bytes,
) -> _ResumeThreadLineage:
    lineage = _require_resume_thread_lineage(
        connection,
        execution_id,
        reservation_id,
        resume_intent_digest,
    )
    row = connection.execute(
        """
        SELECT c.state, a.state
        FROM launch_executions e
        JOIN launch_reservations r
          ON r.launch_reservation_id = e.launch_reservation_id
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        WHERE e.launch_execution_id = ?
          AND e.launch_reservation_id = ?
        """,
        (str(execution_id), str(reservation_id)),
    ).fetchone()
    if row != ("COMMITTED", "LAUNCH_RESERVED"):
        raise ValueError("C3 post-resume complete active lineage is unavailable")
    return lineage


def _core_record_c3_post_resume_evidence(
    connection: sqlite3.Connection,
    execution_id: str,
    resume_receipt: ResumeReceipt,
    evidence: object,
) -> None:
    context = _require_service_context()
    _require_no_active_transaction(connection)
    if type(resume_receipt) is not ResumeReceipt:
        raise TypeError("C3 post-resume evidence requires a resume receipt")
    _require_service_provenance(
        resume_receipt,
        production_issuer=_RESUME_RESULT_ISSUER,
        test_issuer=_TEST_RESUME_RESULT_ISSUER,
        label="resume receipt",
    )
    registered_execution_id, registered_reservation_id = (
        _registered_resume_result_binding(resume_receipt)
    )
    if registered_execution_id != str(execution_id):
        raise ValueError("resume receipt belongs to another execution")
    adapter = context.external_adapter
    validate = getattr(adapter, "validate_c3_post_resume_evidence", None)
    consume = getattr(adapter, "consume_c3_post_resume_evidence", None)
    if adapter is None or not callable(validate) or not callable(consume):
        raise ExternalAuthorityBoundaryUnavailable(
            "transactional authority has no reviewed C3 evidence adapter"
        )
    with _lifecycle_arbiter(registered_reservation_id):
        _record_c3_post_resume_evidence_locked(
            connection,
            registered_execution_id,
            registered_reservation_id,
            resume_receipt,
            evidence,
            validate=validate,
            consume=consume,
        )


@_serialized_connection_operation
def _record_c3_post_resume_evidence_locked(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
    resume_receipt: ResumeReceipt,
    evidence: object,
    *,
    validate: Callable[..., object],
    consume: Callable[..., object],
) -> None:
    lineage = _require_c3_post_resume_lineage(
        connection,
        execution_id,
        reservation_id,
        resume_receipt.resume_intent_digest,
    )
    registered_execution_id, registered_reservation_id = (
        _registered_resume_result_binding(resume_receipt)
    )
    if (
        registered_execution_id != execution_id
        or registered_reservation_id != reservation_id
    ):
        raise ValueError("resume receipt registry binding changed")
    pair = validate(
        evidence,
        execution_id=execution_id,
        reservation_id=reservation_id,
        resume_receipt=resume_receipt,
    )
    if type(pair) is not tuple or len(pair) != 2:
        raise ValueError("C3 evidence adapter returned an invalid evidence pair")
    cleanup_json, cleanup_digest = _require_canonical_c3_cleanup_evidence(*pair)
    expected_result = _json(
        {
            "execution_id": execution_id,
            "resume_intent_digest": lineage.resume_intent_digest.hex(),
            "resume_result": "RESUMED",
            "schema": 1,
        }
    )
    if resume_receipt.result_json != expected_result:
        raise ValueError("resume receipt is not the exact canonical success")
    if resume_receipt.result_digest != _digest(expected_result):
        raise ValueError("resume receipt digest is invalid")

    _begin(connection)
    try:
        cursor = connection.execute(
            """
            UPDATE launch_executions
            SET phase = 'RESUME_RECORDED', post_resume_json = ?,
                post_resume_digest = ?, cleanup_json = ?, cleanup_digest = ?
            WHERE launch_execution_id = ?
              AND launch_reservation_id = ?
              AND phase = 'RESUME_INTENT_COMMITTED'
              AND resume_intent_digest IS ?
              AND EXISTS (
                  SELECT 1
                  FROM launch_reservations r
                  JOIN provider_call_claims c ON c.claim_id = r.claim_id
                  JOIN attempts a ON a.attempt_id = c.attempt_id
                  JOIN sessions s ON s.session_id = a.session_id
                  WHERE r.launch_reservation_id =
                        launch_executions.launch_reservation_id
                    AND r.reservation_state = 'PROCESS_CREATED'
                    AND c.state = 'COMMITTED'
                    AND a.state = 'LAUNCH_RESERVED'
                    AND s.state = 'OPEN'
                    AND NOT EXISTS (
                        SELECT 1 FROM terminals t
                        WHERE t.launch_reservation_id = r.launch_reservation_id
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM session_selections ss
                        WHERE ss.session_id = s.session_id
                    )
              )
            """,
            (
                resume_receipt.result_json,
                resume_receipt.result_digest,
                cleanup_json,
                cleanup_digest,
                execution_id,
                reservation_id,
                lineage.resume_intent_digest,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("C3 post-resume active lineage changed before persistence")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise

    _consume_resume_result(resume_receipt, execution_id, reservation_id)
    consume(
        evidence,
        execution_id=execution_id,
        reservation_id=reservation_id,
        resume_receipt=resume_receipt,
    )


def _require_c3_artifact_verification_lineage(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
) -> tuple[str, str, str, str, str]:
    row = connection.execute(
        """
        SELECT s.session_id, a.attempt_id, c.claim_id,
               r.launch_reservation_id, e.launch_execution_id,
               e.post_resume_json, e.post_resume_digest,
               e.cleanup_json, e.cleanup_digest
        FROM launch_executions e
        JOIN launch_reservations r
          ON r.launch_reservation_id = e.launch_reservation_id
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE e.launch_execution_id = ?
          AND e.launch_reservation_id = ?
          AND e.phase = 'RESUME_RECORDED'
          AND r.reservation_state = 'PROCESS_CREATED'
          AND c.state = 'COMMITTED'
          AND a.state = 'LAUNCH_RESERVED'
          AND s.state = 'OPEN'
          AND NOT EXISTS (
              SELECT 1 FROM terminals t
              WHERE t.launch_reservation_id = r.launch_reservation_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM session_selections ss
              WHERE ss.session_id = s.session_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM manual_recoveries mr
              WHERE mr.session_id = s.session_id
          )
        """,
        (str(execution_id), str(reservation_id)),
    ).fetchone()
    if row is None:
        raise ValueError("C3 artifact verification active lineage is unavailable")
    if any(value is None for value in row[5:]):
        raise ValueError("C3 artifact verification evidence is incomplete")
    if _digest(row[5]) != row[6] or _digest(row[7]) != row[8]:
        raise ValueError("C3 artifact verification evidence digest is invalid")
    return (row[0], row[1], row[2], row[3], row[4])


def _core_verify_c3_captured_snapshot(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
) -> object:
    context = _require_service_context()
    _require_no_active_transaction(connection)
    adapter = context.external_adapter
    verify = getattr(adapter, "verify_c3_captured_snapshot", None)
    if adapter is None or not callable(verify):
        raise ExternalAuthorityBoundaryUnavailable(
            "transactional authority has no reviewed C3 artifact verifier"
        )
    reservation_id = str(reservation_id)
    execution_id = str(execution_id)
    with _lifecycle_arbiter(reservation_id):
        with _connection_operation(connection):
            lineage = _require_c3_artifact_verification_lineage(
                connection, execution_id, reservation_id
            )
        return verify(lineage)


def _core_validate_c3_verified_snapshot(
    connection: sqlite3.Connection, capability: object
) -> None:
    context = _require_service_context()
    _require_no_active_transaction(connection)
    adapter = context.external_adapter
    binding = getattr(adapter, "c3_verified_snapshot_lineage", None)
    validate = getattr(adapter, "validate_c3_verified_snapshot", None)
    if adapter is None or not callable(binding) or not callable(validate):
        raise ExternalAuthorityBoundaryUnavailable(
            "transactional authority has no reviewed C3 snapshot validator"
        )
    lineage = binding(capability)
    if type(lineage) is not tuple or len(lineage) != 5:
        raise ValueError("C3 verified snapshot lineage is invalid")
    reservation_id = lineage[3]
    execution_id = lineage[4]
    with _lifecycle_arbiter(reservation_id):
        with _connection_operation(connection):
            current = _require_c3_artifact_verification_lineage(
                connection, execution_id, reservation_id
            )
        if current != lineage:
            raise ValueError("C3 verified snapshot durable lineage changed")
        validate(capability, current)


def _c3_terminal_adapter_methods(
    adapter: object,
) -> tuple[Callable[..., object], Callable[..., object], Callable[..., object]]:
    prepare = getattr(adapter, "prepare_c3_terminal", None)
    validate = getattr(adapter, "validate_c3_terminal", None)
    consume = getattr(adapter, "consume_c3_terminal", None)
    if not all(callable(method) for method in (prepare, validate, consume)):
        raise ExternalAuthorityBoundaryUnavailable(
            "transactional authority has no reviewed C3 terminal adapter"
        )
    return prepare, validate, consume


def _adapter_exposes_c3_terminal_interface(adapter: object | None) -> bool:
    if adapter is None:
        return False
    return any(
        callable(getattr(adapter, name, None))
        for name in (
            "prepare_c3_terminal",
            "validate_c3_terminal",
            "consume_c3_terminal",
        )
    )


def _core_record_c3_terminal(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
    verified_snapshot: object | None,
) -> str:
    context = _require_service_context()
    _require_no_active_transaction(connection)
    adapter = context.external_adapter
    if adapter is None:
        raise ExternalAuthorityBoundaryUnavailable(
            "transactional authority has no reviewed C3 terminal adapter"
        )
    prepare, validate, consume = _c3_terminal_adapter_methods(adapter)
    execution_id = str(execution_id)
    reservation_id = str(reservation_id)
    with _lifecycle_arbiter(reservation_id):
        with _connection_operation(connection):
            lineage = _require_c3_artifact_verification_lineage(
                connection, execution_id, reservation_id
            )
        authorization = prepare(lineage, verified_snapshot)
        material = _require_c3_terminal_material(
            validate(authorization, lineage), lineage
        )
        with _connection_operation(connection):
            _require_c3_terminal_matches_durable_cleanup(
                connection, execution_id, reservation_id, material[3]
            )
        terminal_id = _record_c3_terminal_locked(
            connection,
            execution_id,
            reservation_id,
            lineage,
            material,
        )
        consume(authorization, lineage)
        return terminal_id


@_serialized_connection_operation
def _record_c3_terminal_locked(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
    lineage: tuple[str, str, str, str, str],
    material: tuple[str, str, bytes | None, bytes, bytes, bytes, bytes],
) -> str:
    (
        state,
        disposition,
        snapshot_digest,
        evidence,
        evidence_digest,
        diagnostics,
        diagnostics_digest,
    ) = _require_c3_terminal_material(material, lineage)
    terminal_id = _terminal_id(reservation_id, TERMINAL_POLICY)
    _begin(connection)
    try:
        current = _require_c3_artifact_verification_lineage(
            connection, execution_id, reservation_id
        )
        if current != lineage:
            raise ValueError("C3 terminal active lineage changed before persistence")
        _require_c3_terminal_matches_durable_cleanup(
            connection, execution_id, reservation_id, evidence
        )
        request_digest = connection.execute(
            "SELECT request_digest FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO terminals (
                terminal_id, launch_reservation_id, terminal_schema,
                terminal_policy_version, terminal_state,
                provider_call_disposition, request_digest, evidence_json,
                evidence_digest, snapshot_digest, sanitized_diagnostics_json,
                sanitized_diagnostics_digest, recorded_at_utc
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                terminal_id,
                reservation_id,
                TERMINAL_POLICY,
                state,
                disposition,
                request_digest,
                evidence,
                evidence_digest,
                snapshot_digest,
                diagnostics,
                diagnostics_digest,
                _timestamp(TERMINAL_TIMESTAMP),
            ),
        )
        execution_update = connection.execute(
            "UPDATE launch_executions SET phase = 'TERMINAL_RECORDED' "
            "WHERE launch_execution_id = ? AND launch_reservation_id = ? "
            "AND phase = 'RESUME_RECORDED'",
            (execution_id, reservation_id),
        )
        reservation_update = connection.execute(
            "UPDATE launch_reservations SET reservation_state = 'TERMINAL_RECORDED' "
            "WHERE launch_reservation_id = ? AND reservation_state = 'PROCESS_CREATED'",
            (reservation_id,),
        )
        attempt_update = connection.execute(
            "UPDATE attempts SET state = 'TERMINAL_RECORDED' "
            "WHERE attempt_id = ? AND state = 'LAUNCH_RESERVED'",
            (lineage[1],),
        )
        if (
            execution_update.rowcount != 1
            or reservation_update.rowcount != 1
            or attempt_update.rowcount != 1
        ):
            raise ValueError("C3 terminal active lineage changed during persistence")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return terminal_id


def _core_record_terminal(
    connection: sqlite3.Connection,
    reservation_id: str,
    state: str = "SUCCEEDED",
    disposition: str = "CONFIRMED",
    *,
    snapshot_digest: bytes | None,
) -> str:
    context = _require_service_context()
    _require_no_active_transaction(connection)
    if _adapter_exposes_c3_terminal_interface(context.external_adapter):
        raise ExternalAuthorityBoundaryUnavailable(
            "legacy terminal recording is unavailable under C3 composition"
        )
    _require_terminal_snapshot_digest(state, snapshot_digest)
    reservation_id = str(reservation_id)
    with _lifecycle_arbiter(reservation_id):
        return _record_terminal_locked(
            connection,
            reservation_id,
            state,
            disposition,
            snapshot_digest=snapshot_digest,
        )


@_serialized_connection_operation
def _record_terminal_locked(
    connection: sqlite3.Connection,
    reservation_id: str,
    state: str,
    disposition: str,
    *,
    snapshot_digest: bytes | None,
) -> str:
    _require_terminal_snapshot_digest(state, snapshot_digest)
    reservation_id = str(reservation_id)
    terminal_policy_version = TERMINAL_POLICY
    terminal_id = _terminal_id(reservation_id, terminal_policy_version)
    evidence, evidence_digest = _evidence(f"terminal:{reservation_id}")
    diagnostics, diagnostics_digest = _evidence("sanitized-diagnostics")
    _require_evidence_pair(evidence, evidence_digest, field="terminal evidence digest")
    _require_evidence_pair(
        diagnostics, diagnostics_digest, field="terminal diagnostics digest"
    )
    _begin(connection)
    try:
        reservation = connection.execute(
            """
            SELECT claim_id, request_digest, reservation_state,
                   process_creation_failure_json, process_creation_failure_digest,
                   process_intent_json, process_intent_digest
            FROM launch_reservations WHERE launch_reservation_id = ?
            """,
            (str(reservation_id),),
        ).fetchone()
        if reservation is None:
            raise ValueError("unknown reservation")
        if (
            state == "FAILED"
            and disposition == "NOT_STARTED"
            and reservation[2] == "PROCESS_CREATION_FAILED"
        ):
            _require_evidence_pair(
                reservation[5],
                reservation[6],
                field="terminal parent process intent digest",
            )
        connection.execute(
            """
            INSERT INTO terminals (
                terminal_id, launch_reservation_id, terminal_schema,
                terminal_policy_version, terminal_state,
                provider_call_disposition, request_digest, evidence_json,
                evidence_digest, snapshot_digest, sanitized_diagnostics_json,
                sanitized_diagnostics_digest, recorded_at_utc
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                terminal_id,
                reservation_id,
                terminal_policy_version,
                state,
                disposition,
                reservation[1],
                evidence,
                evidence_digest,
                snapshot_digest,
                diagnostics,
                diagnostics_digest,
                _timestamp(TERMINAL_TIMESTAMP),
            ),
        )
        if reservation[2] != "MANUAL_REVIEW":
            connection.execute(
                """
                UPDATE launch_executions
                SET phase = 'TERMINAL_RECORDED'
                WHERE launch_reservation_id = ?
                """,
                (str(reservation_id),),
            )
        connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'TERMINAL_RECORDED'
            WHERE launch_reservation_id = ?
            """,
            (str(reservation_id),),
        )
        attempt_id = connection.execute(
            """
            SELECT c.attempt_id FROM provider_call_claims c
            JOIN launch_reservations r ON r.claim_id = c.claim_id
            WHERE r.launch_reservation_id = ?
            """,
            (str(reservation_id),),
        ).fetchone()[0]
        connection.execute(
            "UPDATE attempts SET state = 'TERMINAL_RECORDED' WHERE attempt_id = ?",
            (attempt_id,),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return terminal_id


def _insert_selection_in_transaction(
    connection: sqlite3.Connection, session_id: str, terminal_id: str
) -> str:
    snapshot = connection.execute(
        "SELECT snapshot_digest FROM terminals WHERE terminal_id = ?", (terminal_id,)
    ).fetchone()
    if snapshot is None or snapshot[0] is None:
        raise ValueError("terminal has no snapshot")
    selection_policy_version = SELECTION_POLICY
    selection_id = _selection_id(session_id, terminal_id, selection_policy_version)
    evidence, evidence_digest = _evidence(f"selection:{terminal_id}")
    _require_evidence_pair(evidence, evidence_digest, field="selection evidence digest")
    connection.execute(
        """
        INSERT INTO session_selections (
            selection_id, session_id, terminal_id, selection_schema,
            selection_policy_version, snapshot_digest,
            selection_evidence_json, selection_evidence_digest,
            selected_at_utc
        ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
        """,
        (
            selection_id,
            session_id,
            terminal_id,
            selection_policy_version,
            snapshot[0],
            evidence,
            evidence_digest,
            _timestamp(SELECTION_TIMESTAMP),
        ),
    )
    attempt_id = connection.execute(
        """
        SELECT a.attempt_id
        FROM attempts a
        JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
        JOIN launch_reservations r ON r.claim_id = c.claim_id
        JOIN terminals t ON t.launch_reservation_id = r.launch_reservation_id
        WHERE t.terminal_id = ?
        """,
        (terminal_id,),
    ).fetchone()[0]
    connection.execute(
        "UPDATE attempts SET state = 'SUCCESS_SELECTED' WHERE attempt_id = ?",
        (attempt_id,),
    )
    connection.execute(
        "UPDATE sessions SET state = 'SUCCESS_SELECTED' WHERE session_id = ?",
        (session_id,),
    )
    return selection_id


@_serialized_connection_operation
def _core_select_terminal(
    connection: sqlite3.Connection, session_id: str, terminal_id: str
) -> str:
    _require_service_context()
    _begin(connection)
    try:
        selection_id = _insert_selection_in_transaction(
            connection, session_id, terminal_id
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return selection_id


def _require_c3_success_selection_session(
    connection: sqlite3.Connection, terminal_id: str
) -> str:
    row = connection.execute(
        """
        SELECT s.session_id, a.attempt_id, c.claim_id,
               r.launch_reservation_id, e.launch_execution_id,
               t.terminal_policy_version, t.snapshot_digest
        FROM terminals t
        JOIN launch_reservations r
          ON r.launch_reservation_id = t.launch_reservation_id
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        JOIN launch_executions e
          ON e.launch_reservation_id = r.launch_reservation_id
        WHERE t.terminal_id = ?
          AND t.terminal_schema = 1
          AND t.terminal_policy_version = ?
          AND t.terminal_state = 'SUCCEEDED'
          AND t.provider_call_disposition = 'CONFIRMED'
          AND typeof(t.snapshot_digest) = 'blob'
          AND length(t.snapshot_digest) = 32
          AND r.reservation_state = 'TERMINAL_RECORDED'
          AND c.state = 'COMMITTED'
          AND a.state = 'TERMINAL_RECORDED'
          AND s.state = 'OPEN'
          AND e.phase = 'TERMINAL_RECORDED'
          AND NOT EXISTS (
              SELECT 1 FROM session_selections ss
              WHERE ss.session_id = s.session_id
                 OR ss.terminal_id = t.terminal_id
          )
        """,
        (str(terminal_id), TERMINAL_POLICY),
    ).fetchone()
    if row is None:
        raise ValueError("C3 successful terminal is unavailable for selection")
    reservation_id = row[3]
    if _terminal_id(reservation_id, row[5]) != str(terminal_id):
        raise ValueError("C3 terminal identity is not canonical")
    if type(row[6]) is not bytes or len(row[6]) != 32:
        raise ValueError("C3 successful terminal snapshot digest is invalid")
    return row[0]


@_serialized_connection_operation
def _core_select_c3_terminal(connection: sqlite3.Connection, terminal_id: str) -> str:
    _require_service_context()
    _require_no_active_transaction(connection)
    terminal_id = str(terminal_id)
    _begin(connection)
    try:
        session_id = _require_c3_success_selection_session(connection, terminal_id)
        selection_id = _insert_selection_in_transaction(
            connection, session_id, terminal_id
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return selection_id


def _target_state(
    connection: sqlite3.Connection, target_kind: str, target_id: str
) -> str:
    table, identity_column = {
        "SESSION": ("sessions", "session_id"),
        "ATTEMPT": ("attempts", "attempt_id"),
        "CLAIM": ("provider_call_claims", "claim_id"),
        "LAUNCH_RESERVATION": ("launch_reservations", "launch_reservation_id"),
        "TERMINAL": ("terminals", "terminal_id"),
    }[target_kind]
    state_column = {
        "SESSION": "state",
        "ATTEMPT": "state",
        "CLAIM": "state",
        "LAUNCH_RESERVATION": "reservation_state",
        "TERMINAL": "terminal_state",
    }[target_kind]
    row = connection.execute(
        f"SELECT {state_column} FROM {table} WHERE {identity_column} = ?", (target_id,)
    ).fetchone()
    if row is None:
        raise ValueError("unknown recovery target")
    return row[0]


_RECOVERY_ACTIONS: dict[str, tuple[str, str, str]] = {
    "RECORD_ATTEMPT_AMBIGUITY": (
        "ATTEMPT",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
    ),
    "RECORD_CLAIM_AMBIGUITY": (
        "CLAIM",
        "COMMITTED",
        "AMBIGUITY_RECORDED",
    ),
    "CLASSIFY_LAUNCH_RESERVATION": (
        "LAUNCH_RESERVATION",
        "COMMITTED",
        "MANUAL_REVIEW",
    ),
    "CLASSIFY_PROCESS_OUTCOME_UNKNOWN": (
        "LAUNCH_RESERVATION",
        "PROCESS_INTENT_COMMITTED",
        "MANUAL_REVIEW",
    ),
    "CLASSIFY_PRE_RESUME_READY": (
        "LAUNCH_RESERVATION",
        "PROCESS_CREATED",
        "MANUAL_REVIEW",
    ),
    "CLASSIFY_RESUME_OUTCOME_UNKNOWN": (
        "LAUNCH_RESERVATION",
        "PROCESS_CREATED",
        "MANUAL_REVIEW",
    ),
    "SELECT_COMMITTED_SUCCESS": (
        "TERMINAL",
        "SUCCEEDED",
        "SUCCESS_SELECTED",
    ),
    "CLOSE_SESSION": ("SESSION", "OPEN", "CLOSED"),
    "ACKNOWLEDGE_RESTORE": (
        "SESSION",
        "OPEN",
        "RESTORE_ACKNOWLEDGED",
    ),
}


_RECOVERY_TARGET_EVIDENCE_PAIRS: dict[str, tuple[str, ...]] = {
    "RECORD_ATTEMPT_AMBIGUITY": (
        "launch_executions.post_resume",
        "launch_executions.cleanup",
    ),
    "RECORD_CLAIM_AMBIGUITY": (
        "launch_executions.post_resume",
        "launch_executions.cleanup",
    ),
    "CLASSIFY_LAUNCH_RESERVATION": (),
    "CLASSIFY_PROCESS_OUTCOME_UNKNOWN": ("launch_reservations.process_intent",),
    "CLASSIFY_PRE_RESUME_READY": (
        "launch_executions.process_creation",
        "launch_executions.job_object",
        "launch_executions.resume_authorization",
    ),
    "CLASSIFY_RESUME_OUTCOME_UNKNOWN": (
        "launch_executions.process_creation",
        "launch_executions.job_object",
        "launch_executions.resume_authorization",
        "launch_executions.resume_intent",
    ),
    "SELECT_COMMITTED_SUCCESS": (),
    "CLOSE_SESSION": (),
    "ACKNOWLEDGE_RESTORE": (),
}


def _validate_recovery_target_evidence(
    connection: sqlite3.Connection,
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
) -> None:
    """Validate only the stored cryptographic pairs required by one recovery."""

    required_pairs = _RECOVERY_TARGET_EVIDENCE_PAIRS[action]
    if not required_pairs:
        return

    if action in {"RECORD_ATTEMPT_AMBIGUITY", "RECORD_CLAIM_AMBIGUITY"}:
        target_column = "a.attempt_id" if target_kind == "ATTEMPT" else "c.claim_id"
        row = connection.execute(
            f"""
            SELECT e.post_resume_json, e.post_resume_digest,
                   e.cleanup_json, e.cleanup_digest, e.phase
            FROM launch_executions e
            JOIN launch_reservations r
              ON r.launch_reservation_id = e.launch_reservation_id
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            WHERE {target_column} = ? AND a.session_id = ?
            """,
            (target_id, session_id),
        ).fetchone()
        if row is None or row[4] != "RESUME_RECORDED":
            return
        pair_values = {
            "launch_executions.post_resume": (row[0], row[1]) if row else None,
            "launch_executions.cleanup": (row[2], row[3]) if row else None,
        }
    elif action == "CLASSIFY_PROCESS_OUTCOME_UNKNOWN":
        row = connection.execute(
            """
            SELECT r.process_intent_json, r.process_intent_digest,
                   r.reservation_state
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            WHERE r.launch_reservation_id = ? AND a.session_id = ?
            """,
            (target_id, session_id),
        ).fetchone()
        if row is None or row[2] != "PROCESS_INTENT_COMMITTED":
            return
        pair_values = {
            "launch_reservations.process_intent": ((row[0], row[1]) if row else None),
        }
    else:
        row = connection.execute(
            """
            SELECT e.process_creation_json, e.process_creation_digest,
                   e.job_object_json, e.job_object_digest,
                   e.resume_authorization_json, e.resume_authorization_digest,
                   e.resume_intent_json, e.resume_intent_digest, e.phase
            FROM launch_executions e
            JOIN launch_reservations r
              ON r.launch_reservation_id = e.launch_reservation_id
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            WHERE r.launch_reservation_id = ? AND a.session_id = ?
            """,
            (target_id, session_id),
        ).fetchone()
        expected_phase = (
            "PRE_RESUME_READY"
            if action == "CLASSIFY_PRE_RESUME_READY"
            else "RESUME_INTENT_COMMITTED"
        )
        if row is None or row[8] != expected_phase:
            return
        pair_values = {
            "launch_executions.process_creation": ((row[0], row[1]) if row else None),
            "launch_executions.job_object": (row[2], row[3]) if row else None,
            "launch_executions.resume_authorization": (
                (row[4], row[5]) if row else None
            ),
            "launch_executions.resume_intent": ((row[6], row[7]) if row else None),
        }

    for pair in required_pairs:
        values = pair_values[pair]
        if values is None:
            raise ValueError(f"recovery target evidence is unavailable: {pair}")
        _require_evidence_pair(values[0], values[1], field=f"{pair} digest")


def _preflight_recovery_request(
    target_kind: str,
    action: str,
    ordinal: object,
    *,
    operator_evidence_json: bytes,
    operator_evidence_digest: bytes,
) -> int | None:
    if action not in _RECOVERY_ACTIONS:
        raise ValueError("unknown recovery action")
    expected_kind, _, _ = _RECOVERY_ACTIONS[action]
    if target_kind != expected_kind:
        raise ValueError("recovery action target kind is invalid")
    _require_evidence_pair(
        operator_evidence_json,
        operator_evidence_digest,
        field="operator evidence digest",
    )
    return None if ordinal is None else _canonical_ordinal(ordinal, "recovery ordinal")


def _core_record_recovery(
    connection: sqlite3.Connection,
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    ordinal: int | None = None,
    *,
    operator_evidence_json: bytes,
    operator_evidence_digest: bytes,
) -> str:
    _require_service_context()
    requested_ordinal = _preflight_recovery_request(
        target_kind,
        action,
        ordinal,
        operator_evidence_json=operator_evidence_json,
        operator_evidence_digest=operator_evidence_digest,
    )
    _require_no_active_transaction(connection)
    target_id = str(target_id)
    if target_kind == "LAUNCH_RESERVATION" and action.startswith("CLASSIFY_"):
        with _lifecycle_arbiter(target_id):
            return _record_recovery_locked(
                connection,
                session_id,
                target_kind,
                target_id,
                action,
                requested_ordinal,
                operator_evidence_json=operator_evidence_json,
                operator_evidence_digest=operator_evidence_digest,
            )
    return _record_recovery_locked(
        connection,
        session_id,
        target_kind,
        target_id,
        action,
        requested_ordinal,
        operator_evidence_json=operator_evidence_json,
        operator_evidence_digest=operator_evidence_digest,
    )


@_serialized_connection_operation
def _record_recovery_locked(
    connection: sqlite3.Connection,
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    ordinal: int | None,
    *,
    operator_evidence_json: bytes,
    operator_evidence_digest: bytes,
) -> str:
    target_id = str(target_id)
    requested_ordinal = _preflight_recovery_request(
        target_kind,
        action,
        ordinal,
        operator_evidence_json=operator_evidence_json,
        operator_evidence_digest=operator_evidence_digest,
    )
    _require_no_active_transaction(connection)
    _begin(connection)
    try:
        expected_kind, _, resulting = _RECOVERY_ACTIONS[action]
        if target_kind != expected_kind:
            raise ValueError("recovery action target kind is invalid")
        row = connection.execute(
            "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown recovery session")
        current_ordinal = _canonical_ordinal(row[0], "recovery ordinal")
        recovery_ordinal = (
            current_ordinal if requested_ordinal is None else requested_ordinal
        )
        predecessor = _target_state(connection, target_kind, target_id)
        _validate_recovery_target_evidence(
            connection,
            session_id,
            target_kind,
            target_id,
            action,
        )
        recovery_id = _recovery_id(
            session_id,
            target_kind,
            target_id,
            action,
            predecessor,
            resulting,
            recovery_ordinal,
            RECOVERY_POLICY,
        )
        recovery_timestamp = {
            "SELECT_COMMITTED_SUCCESS": _timestamp(SELECTION_TIMESTAMP),
            "CLOSE_SESSION": _timestamp(CLOSE_TIMESTAMP),
        }.get(action, _timestamp(MANUAL_REVIEW_TIMESTAMP))
        connection.execute(
            """
            INSERT INTO manual_recoveries (
                recovery_id, session_id, recovery_ordinal, target_kind,
                target_id, action, predecessor_state, resulting_state,
                recovery_schema, recovery_policy_version,
                operator_evidence_json, operator_evidence_digest,
                created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                recovery_id,
                session_id,
                recovery_ordinal,
                target_kind,
                target_id,
                action,
                predecessor,
                resulting,
                RECOVERY_POLICY,
                operator_evidence_json,
                operator_evidence_digest,
                recovery_timestamp,
            ),
        )
        if action in (
            "CLASSIFY_LAUNCH_RESERVATION",
            "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        ):
            connection.execute(
                """
                UPDATE launch_reservations
                SET reservation_state = 'MANUAL_REVIEW', outcome_recorded_at_utc = ?
                WHERE launch_reservation_id = ?
                """,
                (_timestamp(MANUAL_REVIEW_TIMESTAMP), target_id),
            )
        elif action in (
            "CLASSIFY_PRE_RESUME_READY",
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        ):
            connection.execute(
                """
                UPDATE launch_reservations
                SET reservation_state = 'MANUAL_REVIEW'
                WHERE launch_reservation_id = ?
                """,
                (target_id,),
            )
        elif action == "SELECT_COMMITTED_SUCCESS":
            _insert_selection_in_transaction(connection, session_id, target_id)
        elif action == "CLOSE_SESSION":
            connection.execute(
                """
                UPDATE sessions
                SET state = 'CLOSED', closed_at_utc = ?, close_reason = ?
                WHERE session_id = ?
                """,
                (_timestamp(CLOSE_TIMESTAMP), "recovery-approved-close", session_id),
            )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return recovery_id


def snapshot_capture_request_for_test(request: object) -> ValidatedCaptureRequest:
    """Explicit disposable boundary for behavioral capture-request vectors."""

    return _snapshot_capture_request(request)


class _TransactionalLeaseWitness:
    """Process-local proof supplied by the reviewed test lease adapter."""

    __slots__ = ("core", "service_token", "reservation_id", "active")

    def __init__(
        self,
        core: TransactionalAuthorityCore,
        service_token: object,
        reservation_id: str,
    ) -> None:
        self.core = core
        self.service_token = service_token
        self.reservation_id = reservation_id
        self.active = True


class _TransactionalLease:
    """Encapsulate one held arbiter and its invalidated-on-exit witness."""

    __slots__ = (
        "_arbiter",
        "_binding",
        "_lifecycle_error",
        "_operation_count",
        "_operations_drained",
        "_release_complete",
        "_release_exception",
        "_state",
        "_witness",
        "active",
    )

    def __init__(
        self,
        binding: TransactionalAuthorityCoreBinding,
        arbiter: AbstractContextManager[object],
        witness: _TransactionalLeaseWitness,
    ) -> None:
        self._arbiter = arbiter
        self._binding = binding
        self._lifecycle_error: BaseException | None = None
        self._operation_count = 0
        self._operations_drained = threading.Event()
        self._operations_drained.set()
        self._release_complete = threading.Event()
        self._release_exception: BaseException | None = None
        self._state = "ACTIVE"
        self._witness = witness
        self.active = True

    def _require_active_witness(self) -> _TransactionalLeaseWitness:
        if not self.active:
            if self._lifecycle_error is not None:
                raise self._lifecycle_error
            raise ExternalAuthorityBoundaryUnavailable(
                "transactional lifecycle lease is closed"
            )
        return self._witness

    @contextmanager
    def admit_operation(
        self,
        core: TransactionalAuthorityCore,
        service_token: object | None,
        reservation_id: str | None = None,
    ) -> Iterator[_TransactionalLeaseWitness]:
        """Pin this lease and its arbiter for one complete while-held operation."""

        with self._binding._lifecycle_state_lock:
            if self._state != "ACTIVE" or not self.active or not self._witness.active:
                if self._release_exception is not None:
                    raise self._release_exception
                if self._lifecycle_error is not None:
                    raise self._lifecycle_error
                raise ExternalAuthorityBoundaryUnavailable(
                    "transactional lifecycle lease is closed"
                )
            witness = self._witness
            if (
                witness.core is not core
                or witness.service_token is not service_token
                or (
                    reservation_id is not None
                    and witness.reservation_id != str(reservation_id)
                )
            ):
                raise ValueError("lifecycle lease witness is invalid or mismatched")
            self._operation_count += 1
            if self._operation_count == 1:
                self._operations_drained.clear()
        try:
            yield witness
        finally:
            with self._binding._lifecycle_state_lock:
                self._operation_count -= 1
                if self._operation_count == 0:
                    self._operations_drained.set()

    def __enter__(self) -> Self:
        self._require_active_witness()
        return self

    def __exit__(self, *args: object) -> None:
        with self._binding._lifecycle_state_lock:
            if self._state in {"RELEASED", "RELEASE_FAILED"}:
                if self._release_exception is not None:
                    raise self._release_exception
                if self._lifecycle_error is not None:
                    raise self._lifecycle_error
                raise ExternalAuthorityBoundaryUnavailable(
                    "transactional lifecycle lease was already released"
                )
            if self._state == "RELEASING":
                wait_for_release = True
            else:
                self._state = "RELEASING"
                self.active = False
                self._witness.active = False
                wait_for_release = False
        if wait_for_release:
            self._release_complete.wait()
            with self._binding._lifecycle_state_lock:
                if self._release_exception is not None:
                    raise self._release_exception
                if self._lifecycle_error is not None:
                    raise self._lifecycle_error
            raise ExternalAuthorityBoundaryUnavailable(
                "transactional lifecycle lease was already released"
            )
        self._operations_drained.wait()
        self._release_arbiter(*args)

    def invalidate_for_harness_close(self, error: BaseException) -> None:
        with self._binding._lifecycle_state_lock:
            if self._state in {"RELEASED", "RELEASE_FAILED"}:
                return
            self._lifecycle_error = error
            if self._state == "RELEASING":
                return
            self._state = "RELEASING"
            self.active = False
            self._witness.active = False
        self._operations_drained.wait()
        self._release_arbiter(None, None, None)

    def _release_arbiter(self, *args: object) -> None:
        try:
            self._arbiter.__exit__(*args)
        except BaseException as exc:
            with self._binding._lifecycle_state_lock:
                self._release_exception = exc
                self._state = "RELEASE_FAILED"
                self._binding._release_failures.append(exc)
            raise
        finally:
            with self._binding._lifecycle_state_lock:
                if self._state != "RELEASE_FAILED":
                    self._state = "RELEASED"
                self.active = False
                self._witness.active = False
                self._binding._active_leases.discard(self)
                self._release_complete.set()

    def __reduce__(self) -> object:
        raise TypeError("transactional lifecycle leases cannot be serialized")


_CORE_BINDING_CONSTRUCTOR = object()
_HARNESS_BINDING_ISSUER_CONSTRUCTOR = object()


class _HarnessCoreBindingIssuer:
    """Non-subclassable, one-shot issuer owned by one harness lifetime."""

    __slots__ = ("_consumed", "_harness", "_provenance")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("harness core binding issuers cannot be subclassed")

    def __new__(cls, *args: object) -> Self:
        if args or cls is not _HarnessCoreBindingIssuer:
            raise TypeError("harness core binding issuer requires its factory")
        return super().__new__(cls)

    def __init__(self, *args: object) -> None:
        del args
        raise TypeError("harness core binding issuer requires its factory")

    @classmethod
    def _create(cls, harness: object) -> Self:
        issuer = object.__new__(cls)
        issuer._consumed = False
        issuer._harness = harness
        issuer._provenance = _HARNESS_BINDING_ISSUER_CONSTRUCTOR
        return issuer

    def _components(self) -> tuple[object, ...]:
        if (
            self._provenance is not _HARNESS_BINDING_ISSUER_CONSTRUCTOR
            or self._consumed
        ):
            raise TypeError("harness core binding issuer is unavailable")
        issuer = getattr(self._harness, "_issue_transactional_core_binding", None)
        if not callable(issuer):
            raise TypeError("harness core binding issuer requires its lifecycle")
        components = issuer(self)
        self._consumed = True
        return components

    def __reduce__(self) -> object:
        raise TypeError("harness core binding issuers cannot be serialized")


class TransactionalAuthorityCoreBinding:
    """Exact, issuer-gated binding for the reviewed file-backed test harness.

    This is a supported implementation value, not production authority.  It
    deliberately has no subclass contract: the core reads only fields on this
    exact runtime type after the reviewed harness issuer has validated them.
    """

    __slots__ = (
        "_active",
        "_capture_request_factory",
        "_connection",
        "_external_adapter",
        "_active_leases",
        "_release_failures",
        "_lifecycle",
        "_lifecycle_state_lock",
        "_lifecycle_arbiter_factory",
        "_lifecycle_error",
        "_issuance_provenance",
        "_service_token",
        "__weakref__",
    )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("transactional authority core bindings cannot be subclassed")

    def __new__(cls, *args: object) -> Self:
        if args:
            raise TypeError("transactional authority core binding requires its issuer")
        if cls is not TransactionalAuthorityCoreBinding:
            raise TypeError(
                "transactional authority core bindings cannot be subclassed"
            )
        instance = super().__new__(cls)
        return instance

    def __init__(self, *args: object) -> None:
        del args
        raise TypeError("transactional authority core binding requires its issuer")

    @classmethod
    def create_harness_issuer(cls, harness: object) -> object:
        if cls is not TransactionalAuthorityCoreBinding:
            raise TypeError(
                "transactional authority core bindings cannot be subclassed"
            )
        return _HarnessCoreBindingIssuer._create(harness)

    @classmethod
    def issue_for_harness(cls, issuer: object) -> Self:
        """Issue one binding from a validated Architecture-77 harness issuer.

        Only the exact one-shot issuer created for one harness lifecycle can
        reach the lifecycle component provider. The storage contract is
        checked again before the binding becomes runnable.
        """

        if (
            type(issuer) is not _HarnessCoreBindingIssuer
            or issuer._provenance is not _HARNESS_BINDING_ISSUER_CONSTRUCTOR
        ):
            raise TypeError("transactional core binding requires the reviewed issuer")
        components = issuer._components()
        if type(components) is not tuple or len(components) != 6:
            raise TypeError(
                "transactional core binding issuer returned invalid material"
            )
        (
            connection,
            lifecycle_arbiter_factory,
            capture_request_factory,
            external_adapter,
            service_token,
            lifecycle,
        ) = components
        if type(connection) is not sqlite3.Connection:
            raise TypeError(
                "transactional core binding requires an exact sqlite3.Connection"
            )
        if not callable(lifecycle_arbiter_factory):
            raise TypeError("transactional core binding requires a lifecycle arbiter")
        if capture_request_factory is not None and not callable(
            capture_request_factory
        ):
            raise TypeError(
                "transactional core binding requires a named capture adapter"
            )
        if service_token is None:
            raise TypeError("transactional core binding requires harness provenance")
        if type(lifecycle) is not TransactionalAuthorityLifecycle:
            raise TypeError("transactional core binding requires lifecycle state")
        _weak_reference(service_token, "transactional core binding service token")
        try:
            with _connection_operation(connection):
                database_list = connection.execute("PRAGMA database_list").fetchall()
                schema = connection.execute(
                    "SELECT production_schema_id, production_schema_version, "
                    "production_schema_digest FROM authority_metadata "
                    "WHERE singleton_key = 1"
                ).fetchone()
        except sqlite3.Error as exc:
            raise TypeError(
                "transactional core binding storage is not reviewed"
            ) from exc
        if len(database_list) != 1 or database_list[0][1] != "main":
            raise TypeError("transactional core binding requires one main database")
        database_path = str(database_list[0][2] or "")
        if not database_path:
            raise TypeError(
                "transactional core binding requires file-backed harness storage"
            )
        if (
            Path(database_path).resolve()
            == Path(PRODUCTION_AUTHORITY_PATHS.database).resolve()
        ):
            raise TypeError(
                "transactional core binding cannot target production storage"
            )
        if schema != (
            PRODUCTION_SCHEMA_ID,
            PRODUCTION_SCHEMA_VERSION,
            bytes.fromhex(PRODUCTION_SCHEMA_ARTIFACT_SHA256),
        ):
            raise TypeError(
                "transactional core binding schema identity is not reviewed"
            )
        if cls is not TransactionalAuthorityCoreBinding:
            raise TypeError(
                "transactional authority core bindings cannot be subclassed"
            )
        binding = object.__new__(cls)
        binding._active = True
        binding._active_leases = set()
        binding._release_failures = []
        binding._lifecycle = lifecycle
        binding._lifecycle_state_lock = threading.RLock()
        binding._connection = connection
        binding._lifecycle_arbiter_factory = lifecycle_arbiter_factory
        binding._capture_request_factory = capture_request_factory
        binding._external_adapter = external_adapter
        binding._lifecycle_error = None
        binding._issuance_provenance = _CORE_BINDING_CONSTRUCTOR
        binding._service_token = service_token
        return binding

    def _require_active(self) -> None:
        with self._lifecycle_state_lock:
            if not self._active:
                if self._lifecycle_error is not None:
                    raise self._lifecycle_error
                raise ExternalAuthorityBoundaryUnavailable(
                    "transactional core binding lifecycle is closed"
                )

    def _components(
        self,
    ) -> tuple[
        sqlite3.Connection,
        Callable[[str], AbstractContextManager[object]],
        Callable[[object], ValidatedCaptureRequest] | None,
        TransactionalAuthorityAdapter | None,
        object,
        TransactionalAuthorityLifecycle,
    ]:
        self._require_active()
        return (
            self._connection,
            self._lifecycle_arbiter_factory,
            self._capture_request_factory,
            self._external_adapter,
            self._service_token,
            self._lifecycle,
        )

    def acquire_lifecycle_lease(
        self,
        core: TransactionalAuthorityCore,
        reservation_id: str,
    ) -> _TransactionalLease:
        """Acquire the reviewed arbiter before issuing a lease witness."""

        self._require_active()
        if (
            type(core) is not TransactionalAuthorityCore
            or core._harness_binding is not self
        ):
            raise TypeError(
                "lifecycle lease witness requires its reviewed core binding"
            )
        with core._bound_context():
            _require_no_active_transaction(self._connection)
            arbiter = self._lifecycle_arbiter_factory(str(reservation_id))
            arbiter.__enter__()
            try:
                self._lifecycle.require_open()
                with self._lifecycle_state_lock:
                    if not self._active:
                        if self._lifecycle_error is not None:
                            raise self._lifecycle_error
                        raise ExternalAuthorityBoundaryUnavailable(
                            "transactional core binding lifecycle is closed"
                        )
                    witness = _TransactionalLeaseWitness(
                        core, self._service_token, str(reservation_id)
                    )
                    lease = _TransactionalLease(self, arbiter, witness)
                    self._active_leases.add(lease)
                    return lease
            except BaseException:
                arbiter.__exit__(None, None, None)
                raise

    def release_lifecycle_lease(self, lease: object, *args: object) -> None:
        if type(lease) is not _TransactionalLease or lease._binding is not self:
            raise TypeError("lifecycle lease does not belong to this core binding")
        lease.__exit__(*args)

    def invalidate_for_harness_close(self, error: BaseException | None = None) -> None:
        close_error = (
            error
            if error is not None
            else ExternalAuthorityBoundaryUnavailable(
                "transactional core binding lifecycle is closed"
            )
        )
        with self._lifecycle_state_lock:
            self._active = False
            self._lifecycle_error = close_error
            leases = tuple(self._active_leases)
            release_error: BaseException | None = (
                self._release_failures[0] if self._release_failures else None
            )
        for lease in leases:
            try:
                lease.invalidate_for_harness_close(close_error)
            except BaseException as exc:
                if release_error is None:
                    release_error = exc
        for lease in leases:
            lease._release_complete.wait()
            if release_error is None and lease._release_exception is not None:
                release_error = lease._release_exception
        if release_error is not None:
            raise release_error

    def __reduce__(self) -> object:
        raise TypeError("transactional core bindings cannot be serialized")


_CORE_CONSTRUCTOR = object()


@dataclass(frozen=True, slots=True)
class _CoreConstruction:
    connection: sqlite3.Connection
    context: _ServiceContext
    harness_binding: TransactionalAuthorityCoreBinding | None
    constructor: object


class TransactionalAuthorityCore:
    """Supported shared transactional state-machine implementation."""

    def __init__(self, construction: _CoreConstruction) -> None:
        if (
            type(construction) is not _CoreConstruction
            or construction.constructor is not _CORE_CONSTRUCTOR
        ):
            raise TypeError("transactional core requires a reviewed storage binding")
        self._connection = construction.connection
        self._context = construction.context
        self._harness_binding = construction.harness_binding

    @classmethod
    def from_harness_binding(
        cls,
        binding: TransactionalAuthorityCoreBinding,
    ) -> Self:
        if (
            type(binding) is not TransactionalAuthorityCoreBinding
            or binding._issuance_provenance is not _CORE_BINDING_CONSTRUCTOR
        ):
            raise TypeError("transactional core requires a reviewed harness binding")
        (
            connection,
            lifecycle_arbiter_factory,
            capture_request_factory,
            external_adapter,
            service_token,
            lifecycle,
        ) = binding._components()
        if type(connection) is not sqlite3.Connection:
            raise TypeError("transactional core requires an exact sqlite3.Connection")
        if service_token is None:
            raise TypeError("transactional core requires harness provenance")
        return cls(
            _CoreConstruction(
                connection=connection,
                context=_ServiceContext(
                    authority=None,
                    lifecycle_arbiter_factory=lifecycle_arbiter_factory,
                    timestamp_provider=lambda fallback: fallback,
                    capture_request_provider=(
                        _snapshot_capture_request
                        if capture_request_factory is None
                        else capture_request_factory
                    ),
                    test_only=True,
                    lifecycle=lifecycle,
                    external_adapter=external_adapter,
                    test_service_token=service_token,
                ),
                harness_binding=binding,
                constructor=_CORE_CONSTRUCTOR,
            ),
        )

    @classmethod
    def _from_context(
        cls, connection: sqlite3.Connection, context: _ServiceContext
    ) -> Self:
        if type(connection) is not sqlite3.Connection:
            raise TypeError("transactional core requires an exact sqlite3.Connection")
        return cls(
            _CoreConstruction(
                connection=connection,
                context=context,
                harness_binding=None,
                constructor=_CORE_CONSTRUCTOR,
            )
        )

    def _require_binding_active(self) -> None:
        if self._harness_binding is not None:
            self._harness_binding._require_active()

    @contextmanager
    def _held_lifecycle_operation(
        self, lease: object, reservation_id: str | None = None
    ) -> Iterator[_TransactionalLeaseWitness]:
        """Admit one operation while its exact lifecycle lease remains held."""

        with self._bound_context():
            if type(lease) is not _TransactionalLease:
                raise TypeError(
                    "already-held operation requires a reviewed lifecycle lease"
                )
            if (
                self._harness_binding is None
                or lease._binding is not self._harness_binding
            ):
                raise ValueError("lifecycle lease witness is invalid or mismatched")
            with lease.admit_operation(
                self, self._context.test_service_token, reservation_id
            ) as witness:
                yield witness

    def require_execution_binding_while_held(
        self,
        execution_id: str,
        reservation_id: str,
        *,
        lease_witness: object,
    ) -> None:
        """Require durable execution lineage to match the held reservation."""

        with self._held_lifecycle_operation(lease_witness, reservation_id):
            with _connection_operation(self._connection):
                _require_no_active_transaction(self._connection)
                row = self._connection.execute(
                    "SELECT launch_reservation_id FROM launch_executions "
                    "WHERE launch_execution_id = ?",
                    (str(execution_id),),
                ).fetchone()
            if row is None or row[0] != str(reservation_id):
                raise ValueError("execution does not belong to the held reservation")

    @contextmanager
    def bind_external_effects(self) -> Iterator[None]:
        """Bind the reviewed service provenance while an adapter runs."""

        with self._bound_context():
            yield

    def _dispatch_c3_child_request(
        self, execution_id: str, reservation_id: str, payload: bytes
    ) -> None:
        """Deliver one C3 request only while exact PRE_RESUME_READY is active."""

        with self._bound_context():
            _require_no_active_transaction(self._connection)
            adapter = self._context.external_adapter
            deliver = getattr(adapter, "deliver_c3_child_request", None)
            if adapter is None or not callable(deliver):
                raise ExternalAuthorityBoundaryUnavailable(
                    "C2 production has no C3 child-request adapter"
                )
            if type(payload) is not bytes or not payload:
                raise TypeError("C3 child request requires nonempty bytes")
            reservation_id = str(reservation_id)
            execution_id = str(execution_id)
            with _lifecycle_arbiter(reservation_id):
                with _connection_operation(self._connection):
                    _require_pre_resume_ready_lineage(
                        self._connection, execution_id, reservation_id
                    )
                deliver(execution_id, reservation_id, payload)

    def _dispatch_external_effect(
        self,
        operation: str,
        capability: object,
        *,
        fail: bool = False,
    ) -> (
        ConstructedProvider
        | ProcessCreationReceipt
        | ProcessCreationFailure
        | ResumeReceipt
    ):
        """Run one complete arbiter-bound external-effect authority boundary."""

        with self._bound_context():
            _require_no_active_transaction(self._connection)
            adapter = self._context.external_adapter
            if adapter is None:
                raise ExternalAuthorityBoundaryUnavailable(
                    "C2 production has no external-effect adapter"
                )
            if operation == "provider":
                if type(capability) is not ProviderConstructionPermit:
                    raise TypeError(
                        "provider construction requires a reservation-issued permit"
                    )
                _require_service_provenance(
                    capability,
                    production_issuer=_PROVIDER_CONSTRUCTION_ISSUER,
                    test_issuer=_TEST_PROVIDER_CONSTRUCTION_ISSUER,
                    label="provider construction permit",
                )
                reservation_id = _registered_provider_reservation_id(capability)
                with _lifecycle_arbiter(reservation_id):
                    with _connection_operation(self._connection):
                        _require_provider_construction_lineage(
                            self._connection, reservation_id
                        )
                    _consume_provider_construction_permit(capability, reservation_id)
                    result = adapter.construct_provider(capability, fail=fail)
                    if type(result) is not ConstructedProvider:
                        raise TypeError(
                            "provider construction adapter returned an invalid result"
                        )
                    _require_service_provenance(
                        result,
                        production_issuer=_CONSTRUCTED_PROVIDER_ISSUER,
                        test_issuer=_TEST_CONSTRUCTED_PROVIDER_ISSUER,
                        label="constructed provider",
                    )
                    if _registered_constructed_provider_reservation_id(result) != (
                        reservation_id
                    ):
                        raise ValueError(
                            "constructed provider belongs to another reservation"
                        )
                    return result
            if operation == "process":
                if type(capability) is not ProcessIntent:
                    raise TypeError(
                        "CreateProcessW requires an opaque fake process intent"
                    )
                _require_service_provenance(
                    capability,
                    production_issuer=_PROCESS_INTENT_ISSUER,
                    test_issuer=_TEST_PROCESS_INTENT_ISSUER,
                    label="process intent",
                )
                reservation_id = _registered_process_intent_reservation_id(capability)
                with _lifecycle_arbiter(reservation_id):
                    with _connection_operation(self._connection):
                        _require_process_creation_lineage(
                            self._connection,
                            reservation_id,
                            capability.intent_digest,
                            capability.intent_json,
                        )
                    _consume_process_intent(capability, reservation_id)
                    result = adapter.create_process(capability, fail=fail)
                    if type(result) not in {
                        ProcessCreationReceipt,
                        ProcessCreationFailure,
                    }:
                        raise TypeError(
                            "process creation adapter returned an invalid result"
                        )
                    _require_service_provenance(
                        result,
                        production_issuer=_PROCESS_RESULT_ISSUER,
                        test_issuer=_TEST_PROCESS_RESULT_ISSUER,
                        label="process creation result",
                    )
                    if (
                        _registered_process_result_reservation_id(result)
                        != reservation_id
                        or result.process_intent_digest != capability.intent_digest
                    ):
                        raise ValueError(
                            "process creation result does not match process intent"
                        )
                    return result
            if operation == "resume":
                if type(capability) is not ResumeIntent:
                    raise TypeError(
                        "ResumeThread requires an opaque fake resume intent"
                    )
                _require_service_provenance(
                    capability,
                    production_issuer=_RESUME_INTENT_ISSUER,
                    test_issuer=_TEST_RESUME_INTENT_ISSUER,
                    label="resume intent",
                )
                execution_id, reservation_id = _registered_resume_intent_binding(
                    capability
                )
                with _lifecycle_arbiter(reservation_id):
                    with _connection_operation(self._connection):
                        _require_resume_thread_lineage(
                            self._connection,
                            execution_id,
                            reservation_id,
                            capability.intent_digest,
                            capability.intent_json,
                        )
                    _consume_resume_intent(capability, execution_id, reservation_id)
                    result = adapter.resume_thread(capability, fail=fail)
                    if type(result) is not ResumeReceipt:
                        raise TypeError("resume adapter returned an invalid result")
                    _require_service_provenance(
                        result,
                        production_issuer=_RESUME_RESULT_ISSUER,
                        test_issuer=_TEST_RESUME_RESULT_ISSUER,
                        label="resume receipt",
                    )
                    result_execution_id, result_reservation_id = (
                        _registered_resume_result_binding(result)
                    )
                    if (
                        result_execution_id != execution_id
                        or result_reservation_id != reservation_id
                        or result.resume_intent_digest != capability.intent_digest
                    ):
                        raise ValueError("resume receipt does not match resume intent")
                    return result
            raise ValueError("unsupported external-effect operation")

    @contextmanager
    def _bound_context(self, *, wait_for_close: bool = True) -> Iterator[None]:
        self._require_binding_active()
        lifecycle = self._context.lifecycle
        if lifecycle is None:
            token = _CURRENT_SERVICE_CONTEXT.set(self._context)
            try:
                yield
            finally:
                _CURRENT_SERVICE_CONTEXT.reset(token)
            return
        with lifecycle.admit(wait_for_close=wait_for_close):
            self._require_binding_active()
            token = _CURRENT_SERVICE_CONTEXT.set(self._context)
            try:
                yield
            finally:
                _CURRENT_SERVICE_CONTEXT.reset(token)

    def require_test_capability(self, capability: object) -> None:
        with self._bound_context():
            if type(capability) is ProviderConstructionPermit:
                _require_service_provenance(
                    capability,
                    production_issuer=_PROVIDER_CONSTRUCTION_ISSUER,
                    test_issuer=_TEST_PROVIDER_CONSTRUCTION_ISSUER,
                    label="provider construction permit",
                )
            elif type(capability) is ConstructedProvider:
                _require_service_provenance(
                    capability,
                    production_issuer=_CONSTRUCTED_PROVIDER_ISSUER,
                    test_issuer=_TEST_CONSTRUCTED_PROVIDER_ISSUER,
                    label="constructed provider",
                )
            elif type(capability) is ProcessIntent:
                _require_service_provenance(
                    capability,
                    production_issuer=_PROCESS_INTENT_ISSUER,
                    test_issuer=_TEST_PROCESS_INTENT_ISSUER,
                    label="process intent",
                )
            elif type(capability) in {ProcessCreationReceipt, ProcessCreationFailure}:
                _require_service_provenance(
                    capability,
                    production_issuer=_PROCESS_RESULT_ISSUER,
                    test_issuer=_TEST_PROCESS_RESULT_ISSUER,
                    label="process creation result",
                )
            elif type(capability) is ResumeIntent:
                _require_service_provenance(
                    capability,
                    production_issuer=_RESUME_INTENT_ISSUER,
                    test_issuer=_TEST_RESUME_INTENT_ISSUER,
                    label="resume intent",
                )
            elif type(capability) is ResumeReceipt:
                _require_service_provenance(
                    capability,
                    production_issuer=_RESUME_RESULT_ISSUER,
                    test_issuer=_TEST_RESUME_RESULT_ISSUER,
                    label="resume receipt",
                )
            else:
                raise TypeError("unsupported transactional capability")

    def create_session(
        self, request: dict[str, Any], *, created_at_utc: str = TIMESTAMP
    ) -> str:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_create_session(
                self._connection, request, created_at_utc=created_at_utc
            )

    def allocate_attempt(
        self,
        session_id: str,
        *,
        ordinal: int | None = None,
        created_at_utc: str = TIMESTAMP,
    ) -> str:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_allocate_attempt(
                self._connection,
                session_id,
                ordinal,
                created_at_utc=created_at_utc,
            )

    def commit_claim(
        self, attempt_id: str, *, committed_at_utc: str = TIMESTAMP
    ) -> str:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_commit_claim(
                self._connection, attempt_id, committed_at_utc=committed_at_utc
            )

    def reserve_launch(
        self, claim_id: str, *, committed_at_utc: str = TIMESTAMP
    ) -> ProviderConstructionPermit:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_reserve_launch(
                self._connection, claim_id, committed_at_utc=committed_at_utc
            )

    def commit_process_intent(
        self, reservation_id: str, provider: ConstructedProvider
    ) -> ProcessIntent:
        with self._bound_context():
            if type(provider) is not ConstructedProvider:
                raise TypeError(
                    "commit_process_intent requires an opaque constructed provider"
                )
            _require_service_provenance(
                provider,
                production_issuer=_CONSTRUCTED_PROVIDER_ISSUER,
                test_issuer=_TEST_CONSTRUCTED_PROVIDER_ISSUER,
                label="constructed provider",
            )
            _require_no_active_transaction(self._connection)
            return _core_commit_process_intent(
                self._connection, reservation_id, provider
            )

    def record_execution(
        self, reservation_id: str, receipt: ProcessCreationReceipt
    ) -> str:
        with self._bound_context():
            if type(receipt) is not ProcessCreationReceipt:
                raise TypeError(
                    "record_execution requires a fake process creation receipt"
                )
            _require_service_provenance(
                receipt,
                production_issuer=_PROCESS_RESULT_ISSUER,
                test_issuer=_TEST_PROCESS_RESULT_ISSUER,
                label="process creation receipt",
            )
            _require_no_active_transaction(self._connection)
            return _core_record_execution(self._connection, reservation_id, receipt)

    def commit_resume_intent(
        self, execution_id: str, reservation_id: str
    ) -> ResumeIntent:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_commit_resume_intent(
                self._connection, execution_id, reservation_id
            )

    def record_process_creation_failure(
        self, reservation_id: str, failure: ProcessCreationFailure
    ) -> None:
        with self._bound_context():
            _require_service_provenance(
                failure,
                production_issuer=_PROCESS_RESULT_ISSUER,
                test_issuer=_TEST_PROCESS_RESULT_ISSUER,
                label="process creation failure",
            )
            _require_no_active_transaction(self._connection)
            return _core_record_process_creation_failure(
                self._connection, reservation_id, failure
            )

    def record_post_resume_evidence(
        self, execution_id: str, receipt: ResumeReceipt
    ) -> None:
        with self._bound_context():
            if type(receipt) is not ResumeReceipt:
                raise TypeError("post-resume evidence requires a fake resume receipt")
            _require_service_provenance(
                receipt,
                production_issuer=_RESUME_RESULT_ISSUER,
                test_issuer=_TEST_RESUME_RESULT_ISSUER,
                label="resume receipt",
            )
            _require_no_active_transaction(self._connection)
            return _core_record_post_resume_evidence(
                self._connection, execution_id, receipt
            )

    def record_c3_post_resume_evidence(
        self, execution_id: str, receipt: ResumeReceipt, evidence: object
    ) -> None:
        with self._bound_context():
            if type(receipt) is not ResumeReceipt:
                raise TypeError("C3 post-resume evidence requires a resume receipt")
            _require_service_provenance(
                receipt,
                production_issuer=_RESUME_RESULT_ISSUER,
                test_issuer=_TEST_RESUME_RESULT_ISSUER,
                label="resume receipt",
            )
            _require_no_active_transaction(self._connection)
            return _core_record_c3_post_resume_evidence(
                self._connection, execution_id, receipt, evidence
            )

    def verify_c3_captured_snapshot(
        self, execution_id: str, reservation_id: str
    ) -> object:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_verify_c3_captured_snapshot(
                self._connection, execution_id, reservation_id
            )

    def validate_c3_verified_snapshot(self, capability: object) -> None:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_validate_c3_verified_snapshot(self._connection, capability)

    def record_c3_terminal(
        self,
        execution_id: str,
        reservation_id: str,
        verified_snapshot: object | None = None,
    ) -> str:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_record_c3_terminal(
                self._connection,
                execution_id,
                reservation_id,
                verified_snapshot,
            )

    def record_terminal(
        self,
        reservation_id: str,
        state: str = "SUCCEEDED",
        disposition: str = "CONFIRMED",
        *,
        snapshot_digest: bytes | None,
    ) -> str:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_record_terminal(
                self._connection,
                reservation_id,
                state,
                disposition,
                snapshot_digest=snapshot_digest,
            )

    def select_terminal(self, session_id: str, terminal_id: str) -> str:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_select_terminal(self._connection, session_id, terminal_id)

    def select_c3_terminal(self, terminal_id: str) -> str:
        with self._bound_context():
            _require_no_active_transaction(self._connection)
            return _core_select_c3_terminal(self._connection, terminal_id)

    def record_recovery(
        self,
        session_id: str,
        target_kind: str,
        target_id: str,
        action: str,
        ordinal: int | None = None,
        *,
        operator_evidence_json: bytes,
        operator_evidence_digest: bytes,
    ) -> str:
        with self._bound_context():
            if ordinal is not None:
                _canonical_ordinal(ordinal, "recovery ordinal")
            _require_no_active_transaction(self._connection)
            return _core_record_recovery(
                self._connection,
                session_id,
                target_kind,
                target_id,
                action,
                ordinal,
                operator_evidence_json=operator_evidence_json,
                operator_evidence_digest=operator_evidence_digest,
            )

    def commit_process_intent_while_held(
        self,
        reservation_id: str,
        provider: ConstructedProvider,
        *,
        lease_witness: object,
    ) -> ProcessIntent:
        with self._held_lifecycle_operation(lease_witness, reservation_id):
            _require_no_active_transaction(self._connection)
            if type(provider) is not ConstructedProvider:
                raise TypeError(
                    "commit_process_intent requires an opaque constructed provider"
                )
            _require_service_provenance(
                provider,
                production_issuer=_CONSTRUCTED_PROVIDER_ISSUER,
                test_issuer=_TEST_CONSTRUCTED_PROVIDER_ISSUER,
                label="constructed provider",
            )
            return _commit_process_intent_locked(
                self._connection, reservation_id, provider
            )

    def record_execution_while_held(
        self,
        reservation_id: str,
        receipt: ProcessCreationReceipt,
        *,
        lease_witness: object,
    ) -> str:
        with self._held_lifecycle_operation(lease_witness, reservation_id):
            _require_no_active_transaction(self._connection)
            if type(receipt) is not ProcessCreationReceipt:
                raise TypeError(
                    "record_execution requires a fake process creation receipt"
                )
            _require_service_provenance(
                receipt,
                production_issuer=_PROCESS_RESULT_ISSUER,
                test_issuer=_TEST_PROCESS_RESULT_ISSUER,
                label="process creation receipt",
            )
            return _record_execution_locked(self._connection, reservation_id, receipt)

    def commit_resume_intent_while_held(
        self,
        execution_id: str,
        reservation_id: str,
        *,
        lease_witness: object,
    ) -> ResumeIntent:
        with self._held_lifecycle_operation(lease_witness, reservation_id):
            _require_no_active_transaction(self._connection)
            return _commit_resume_intent_locked(
                self._connection, execution_id, reservation_id
            )

    def record_process_creation_failure_while_held(
        self,
        reservation_id: str,
        failure: ProcessCreationFailure,
        *,
        lease_witness: object,
    ) -> None:
        with self._held_lifecycle_operation(lease_witness, reservation_id):
            _require_no_active_transaction(self._connection)
            _require_service_provenance(
                failure,
                production_issuer=_PROCESS_RESULT_ISSUER,
                test_issuer=_TEST_PROCESS_RESULT_ISSUER,
                label="process creation failure",
            )
            return _record_process_creation_failure_locked(
                self._connection, reservation_id, failure
            )

    def record_post_resume_evidence_while_held(
        self,
        execution_id: str,
        receipt: ResumeReceipt,
        *,
        lease_witness: object,
    ) -> None:
        with self._held_lifecycle_operation(lease_witness) as witness:
            _require_no_active_transaction(self._connection)
            if type(receipt) is not ResumeReceipt:
                raise TypeError("post-resume evidence requires a fake resume receipt")
            _require_service_provenance(
                receipt,
                production_issuer=_RESUME_RESULT_ISSUER,
                test_issuer=_TEST_RESUME_RESULT_ISSUER,
                label="resume receipt",
            )
            registered_execution_id, registered_reservation_id = (
                _registered_resume_result_binding(receipt)
            )
            if registered_execution_id != str(execution_id):
                raise ValueError("fake resume receipt belongs to another execution")
            if registered_reservation_id != witness.reservation_id:
                raise ValueError("resume receipt belongs to the held reservation")
            return _record_post_resume_evidence_locked(
                self._connection, execution_id, receipt
            )

    def record_terminal_while_held(
        self,
        reservation_id: str,
        state: str = "SUCCEEDED",
        disposition: str = "CONFIRMED",
        *,
        snapshot_digest: bytes | None,
        lease_witness: object,
    ) -> str:
        with self._held_lifecycle_operation(lease_witness, reservation_id):
            _require_no_active_transaction(self._connection)
            context = _require_service_context()
            if _adapter_exposes_c3_terminal_interface(context.external_adapter):
                raise ExternalAuthorityBoundaryUnavailable(
                    "legacy terminal recording is unavailable under C3 composition"
                )
            return _record_terminal_locked(
                self._connection,
                reservation_id,
                state,
                disposition,
                snapshot_digest=snapshot_digest,
            )

    def record_recovery_while_held(
        self,
        session_id: str,
        target_kind: str,
        target_id: str,
        action: str,
        ordinal: int | None = None,
        *,
        operator_evidence_json: bytes,
        operator_evidence_digest: bytes,
        lease_witness: object,
    ) -> str:
        with self._held_lifecycle_operation(lease_witness) as witness:
            _require_no_active_transaction(self._connection)
            requested_ordinal = _preflight_recovery_request(
                target_kind,
                action,
                ordinal,
                operator_evidence_json=operator_evidence_json,
                operator_evidence_digest=operator_evidence_digest,
            )
            with _connection_operation(self._connection):
                _require_no_active_transaction(self._connection)
                self._require_recovery_target_reservation(
                    session_id,
                    target_kind,
                    target_id,
                    witness.reservation_id,
                )
                return _record_recovery_locked(
                    self._connection,
                    session_id,
                    target_kind,
                    target_id,
                    action,
                    requested_ordinal,
                    operator_evidence_json=operator_evidence_json,
                    operator_evidence_digest=operator_evidence_digest,
                )

    def _require_recovery_target_reservation(
        self,
        session_id: str,
        target_kind: str,
        target_id: str,
        reservation_id: str,
    ) -> None:
        target_id = str(target_id)
        reservation_id = str(reservation_id)
        queries = {
            "SESSION": (
                """
                SELECT r.launch_reservation_id
                FROM sessions s
                JOIN attempts a ON a.session_id = s.session_id
                JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
                JOIN launch_reservations r ON r.claim_id = c.claim_id
                WHERE s.session_id = ? AND s.session_id = ?
                  AND r.launch_reservation_id = ?
                """,
                (target_id, str(session_id), reservation_id),
            ),
            "ATTEMPT": (
                """
                SELECT r.launch_reservation_id
                FROM attempts a
                JOIN sessions s ON s.session_id = a.session_id
                JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
                JOIN launch_reservations r ON r.claim_id = c.claim_id
                WHERE a.attempt_id = ? AND s.session_id = ?
                  AND r.launch_reservation_id = ?
                """,
                (target_id, str(session_id), reservation_id),
            ),
            "CLAIM": (
                """
                SELECT r.launch_reservation_id
                FROM provider_call_claims c
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN sessions s ON s.session_id = a.session_id
                JOIN launch_reservations r ON r.claim_id = c.claim_id
                WHERE c.claim_id = ? AND s.session_id = ?
                  AND r.launch_reservation_id = ?
                """,
                (target_id, str(session_id), reservation_id),
            ),
            "LAUNCH_RESERVATION": (
                """
                SELECT r.launch_reservation_id
                FROM launch_reservations r
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN sessions s ON s.session_id = a.session_id
                WHERE r.launch_reservation_id = ? AND s.session_id = ?
                  AND r.launch_reservation_id = ?
                """,
                (target_id, str(session_id), reservation_id),
            ),
            "TERMINAL": (
                """
                SELECT r.launch_reservation_id
                FROM terminals t
                JOIN launch_reservations r
                  ON r.launch_reservation_id = t.launch_reservation_id
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN sessions s ON s.session_id = a.session_id
                WHERE t.terminal_id = ? AND s.session_id = ?
                  AND r.launch_reservation_id = ?
                """,
                (target_id, str(session_id), reservation_id),
            ),
        }
        query = queries.get(target_kind)
        if query is None:
            raise ValueError(
                "recovery target kind cannot be bound to the held reservation"
            )
        row = self._connection.execute(*query).fetchone()
        if row is None:
            raise ValueError("recovery target is outside the held reservation")

    def target_state(self, target_kind: str, target_id: str) -> str:
        with self._bound_context():
            with _connection_operation(self._connection):
                return _target_state(self._connection, target_kind, target_id)

    def validate_recovery_target_evidence(
        self,
        session_id: str,
        target_kind: str,
        target_id: str,
        action: str,
    ) -> None:
        with self._bound_context():
            with _connection_operation(self._connection):
                return _validate_recovery_target_evidence(
                    self._connection, session_id, target_kind, target_id, action
                )


class WindowsTransactionalAuthority:
    """Production owner of the reviewed durable transactional authority.

    Production construction accepts only the genuine C1 capability.  It never
    accepts a path, SQLite connection, schema identity, or public side-effect
    adapter.  The private C3 composition factory and disposable `for_test`
    factory are the only adapter-binding seams.
    """

    def __init__(self, authority: ValidatedProductionAuthority) -> None:
        self._authority = require_validated_production_authority(authority)
        self._connection: sqlite3.Connection | None = None
        self._core: TransactionalAuthorityCore | None = None
        self._test_database: DisposableAuthorityDatabaseForTest | None = None
        self._production_c3_issuer: _ProductionC3ResultIssuer | None = None
        self._context = _ServiceContext(
            authority=self._authority,
            lifecycle_arbiter_factory=_production_lifecycle_arbiter_factory(
                self._authority
            ),
            timestamp_provider=_production_timestamp,
            capture_request_provider=_snapshot_capture_request,
            test_only=False,
        )

    @classmethod
    def _for_production_c3(
        cls,
        authority: ValidatedProductionAuthority,
        adapter: TransactionalAuthorityAdapter,
    ) -> Self:
        """Privately bind one reviewed production C3 adapter to production C2."""

        bind_issuer = getattr(adapter, "_bind_production_c2_issuer", None)
        if not callable(bind_issuer):
            raise TypeError("production C3 adapter binding is invalid")
        instance = cls(authority)
        issuer = _ProductionC3ResultIssuer(
            _PRODUCTION_C3_RESULT_ISSUER_CONSTRUCTOR, adapter
        )
        instance._context = _ServiceContext(
            authority=instance._authority,
            lifecycle_arbiter_factory=_production_lifecycle_arbiter_factory(
                instance._authority
            ),
            timestamp_provider=_production_timestamp,
            capture_request_provider=_snapshot_capture_request,
            test_only=False,
            external_adapter=adapter,
        )
        instance._production_c3_issuer = issuer
        try:
            bind_issuer(issuer)
        except BaseException:
            issuer.close()
            instance._production_c3_issuer = None
            instance.close()
            raise
        return instance

    @classmethod
    def for_test(
        cls,
        *,
        database: DisposableAuthorityDatabaseForTest,
        lifecycle_arbiter_factory: Callable[[str], AbstractContextManager[object]],
        capture_request_factory: Callable[[object], ValidatedCaptureRequest]
        | None = None,
        external_adapter: TransactionalAuthorityAdapter | None = None,
    ) -> Self:
        """Create a disposable service with explicitly injected test seams."""

        if type(database) is not DisposableAuthorityDatabaseForTest:
            raise TypeError(
                "test authority service requires a reviewed disposable database"
            )
        database._claim_test_service()
        instance = cls.__new__(cls)
        instance._authority = None
        instance._connection = database._connection
        instance._core = None
        instance._test_database = database
        instance._production_c3_issuer = None
        lifecycle = TransactionalAuthorityLifecycle()
        instance._context = _ServiceContext(
            authority=None,
            lifecycle_arbiter_factory=lifecycle_arbiter_factory,
            timestamp_provider=lambda fallback: fallback,
            capture_request_provider=(
                _snapshot_capture_request
                if capture_request_factory is None
                else capture_request_factory
            ),
            test_only=True,
            lifecycle=lifecycle,
            external_adapter=external_adapter,
            test_database=database,
            test_service_token=_TestServiceToken(),
        )
        return instance

    @property
    def authority(self) -> ValidatedProductionAuthority | None:
        return self._authority

    @property
    def database_path(self) -> str:
        if self._authority is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "test authority service has no production database binding"
            )
        return self._authority.database_path

    def _open_production_connection(self) -> sqlite3.Connection:
        if self._connection is not None:
            return self._connection
        build = _approved_sqlite_build_for_authority(self._authority)
        connection = open_writable_authority_sqlite_connection(
            self._authority.database_path, vfs=build.vfs
        )
        try:
            configure_and_validate_authority_sqlite_connection(
                connection,
                database_path=self._authority.database_path,
                journal_path=f"{self._authority.database_path}-journal",
            )
            require_open_connection_matches_validated_authority(
                self._authority, connection
            )
        except BaseException:
            try:
                connection.close()
            except BaseException:
                pass
            raise
        self._connection = connection
        return connection

    def _service_timestamp(self, fallback: str) -> str:
        return self._context.timestamp_provider(fallback)

    def _require_service_open(self) -> None:
        lifecycle = self._context.lifecycle
        if lifecycle is not None:
            lifecycle.require_open()

    def close(self) -> None:
        production_c3_issuer = self._production_c3_issuer
        self._production_c3_issuer = None
        if production_c3_issuer is not None:
            production_c3_issuer.close()
        lifecycle = self._context.lifecycle
        if lifecycle is not None:
            lifecycle.close(
                ExternalAuthorityBoundaryUnavailable(
                    "test authority service lifecycle is closed"
                )
            )
        connection = self._connection
        self._connection = None
        self._core = None
        self._test_database = None
        if connection is not None:
            connection.close()

    def _core_for_operation(self) -> TransactionalAuthorityCore:
        if self._context.test_only:
            lifecycle = self._context.lifecycle
            if lifecycle is None:
                raise ExternalAuthorityBoundaryUnavailable(
                    "test service has no lifecycle state"
                )
            lifecycle.require_open()
            if self._test_database is None or self._connection is None:
                raise ExternalAuthorityBoundaryUnavailable(
                    "test service has no reviewed disposable database"
                )
        else:
            self._open_production_connection()
        if self._connection is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "transactional authority has no database connection"
            )
        if self._core is None:
            self._core = TransactionalAuthorityCore._from_context(
                self._connection,
                self._context,
            )
        return self._core

    def create_session(self, request: dict[str, Any]) -> str:
        return self._core_for_operation().create_session(
            request, created_at_utc=self._service_timestamp(TIMESTAMP)
        )

    def allocate_attempt(self, session_id: str, *, ordinal: int | None = None) -> str:
        return self._core_for_operation().allocate_attempt(
            session_id,
            ordinal=ordinal,
            created_at_utc=self._service_timestamp(TIMESTAMP),
        )

    def commit_claim(self, attempt_id: str) -> str:
        return self._core_for_operation().commit_claim(
            attempt_id, committed_at_utc=self._service_timestamp(TIMESTAMP)
        )

    def reserve_launch(self, claim_id: str) -> ProviderConstructionPermit:
        return self._core_for_operation().reserve_launch(
            claim_id, committed_at_utc=self._service_timestamp(TIMESTAMP)
        )

    def commit_process_intent(
        self, reservation_id: str, provider: ConstructedProvider
    ) -> ProcessIntent:
        self._require_service_open()
        _require_service_provenance(
            provider,
            production_issuer=_CONSTRUCTED_PROVIDER_ISSUER,
            test_issuer=_TEST_CONSTRUCTED_PROVIDER_ISSUER,
            label="constructed provider",
            test_only=self._context.test_only,
            service_token=self._context.test_service_token,
        )
        return self._core_for_operation().commit_process_intent(
            reservation_id, provider
        )

    def record_execution(
        self, reservation_id: str, receipt: ProcessCreationReceipt
    ) -> str:
        self._require_service_open()
        _require_service_provenance(
            receipt,
            production_issuer=_PROCESS_RESULT_ISSUER,
            test_issuer=_TEST_PROCESS_RESULT_ISSUER,
            label="process creation receipt",
            test_only=self._context.test_only,
            service_token=self._context.test_service_token,
        )
        return self._core_for_operation().record_execution(reservation_id, receipt)

    def commit_resume_intent(
        self, execution_id: str, reservation_id: str
    ) -> ResumeIntent:
        return self._core_for_operation().commit_resume_intent(
            execution_id, reservation_id
        )

    def record_process_creation_failure(
        self, reservation_id: str, failure: ProcessCreationFailure
    ) -> None:
        self._require_service_open()
        _require_service_provenance(
            failure,
            production_issuer=_PROCESS_RESULT_ISSUER,
            test_issuer=_TEST_PROCESS_RESULT_ISSUER,
            label="process creation failure",
            test_only=self._context.test_only,
            service_token=self._context.test_service_token,
        )
        return self._core_for_operation().record_process_creation_failure(
            reservation_id, failure
        )

    def record_post_resume_evidence(
        self, execution_id: str, receipt: ResumeReceipt
    ) -> None:
        self._require_service_open()
        _require_service_provenance(
            receipt,
            production_issuer=_RESUME_RESULT_ISSUER,
            test_issuer=_TEST_RESUME_RESULT_ISSUER,
            label="resume receipt",
            test_only=self._context.test_only,
            service_token=self._context.test_service_token,
        )
        return self._core_for_operation().record_post_resume_evidence(
            execution_id, receipt
        )

    def record_c3_post_resume_evidence(
        self, execution_id: str, receipt: ResumeReceipt, evidence: object
    ) -> None:
        self._require_service_open()
        _require_service_provenance(
            receipt,
            production_issuer=_RESUME_RESULT_ISSUER,
            test_issuer=_TEST_RESUME_RESULT_ISSUER,
            label="resume receipt",
            test_only=self._context.test_only,
            service_token=self._context.test_service_token,
        )
        if self._context.external_adapter is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "transactional authority has no reviewed C3 evidence adapter"
            )
        return self._core_for_operation().record_c3_post_resume_evidence(
            execution_id, receipt, evidence
        )

    def verify_c3_captured_snapshot(
        self, execution_id: str, reservation_id: str
    ) -> object:
        self._require_service_open()
        if self._context.external_adapter is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "transactional authority has no reviewed C3 artifact adapter"
            )
        return self._core_for_operation().verify_c3_captured_snapshot(
            execution_id, reservation_id
        )

    def validate_c3_verified_snapshot(self, capability: object) -> None:
        self._require_service_open()
        if self._context.external_adapter is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "transactional authority has no reviewed C3 artifact adapter"
            )
        return self._core_for_operation().validate_c3_verified_snapshot(capability)

    def record_c3_terminal(
        self,
        execution_id: str,
        reservation_id: str,
        verified_snapshot: object | None = None,
    ) -> str:
        self._require_service_open()
        if self._context.external_adapter is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "transactional authority has no reviewed C3 terminal adapter"
            )
        return self._core_for_operation().record_c3_terminal(
            execution_id,
            reservation_id,
            verified_snapshot,
        )

    def record_terminal(
        self,
        reservation_id: str,
        state: str = "SUCCEEDED",
        disposition: str = "CONFIRMED",
        *,
        snapshot_digest: bytes | None,
    ) -> str:
        return self._core_for_operation().record_terminal(
            reservation_id,
            state,
            disposition,
            snapshot_digest=snapshot_digest,
        )

    def select_terminal(self, session_id: str, terminal_id: str) -> str:
        return self._core_for_operation().select_terminal(session_id, terminal_id)

    def select_c3_terminal(self, terminal_id: str) -> str:
        self._require_service_open()
        return self._core_for_operation().select_c3_terminal(terminal_id)

    def record_recovery(
        self,
        session_id: str,
        target_kind: str,
        target_id: str,
        action: str,
        ordinal: int | None = None,
        *,
        operator_evidence_json: bytes,
        operator_evidence_digest: bytes,
    ) -> str:
        if ordinal is not None:
            _canonical_ordinal(ordinal, "recovery ordinal")
        return self._core_for_operation().record_recovery(
            session_id,
            target_kind,
            target_id,
            action,
            ordinal,
            operator_evidence_json=operator_evidence_json,
            operator_evidence_digest=operator_evidence_digest,
        )

    def construct_provider(
        self, capability: ProviderConstructionPermit, *, fail: bool = False
    ) -> ConstructedProvider:
        self._require_service_open()
        if self._context.external_adapter is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "C2 production has no provider construction adapter"
            )
        return self._core_for_operation()._dispatch_external_effect(
            "provider", capability, fail=fail
        )  # type: ignore[return-value]

    def create_process(
        self, process_intent: ProcessIntent, *, fail: bool = False
    ) -> ProcessCreationReceipt | ProcessCreationFailure:
        self._require_service_open()
        if self._context.external_adapter is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "C2 production has no process creation adapter"
            )
        return self._core_for_operation()._dispatch_external_effect(
            "process", process_intent, fail=fail
        )  # type: ignore[return-value]

    def deliver_c3_child_request(
        self, execution_id: str, reservation_id: str, payload: bytes
    ) -> None:
        """C3-only request delivery; a bare production authority stays inert."""

        self._require_service_open()
        if self._context.external_adapter is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "C2 production has no C3 child-request adapter"
            )
        return self._core_for_operation()._dispatch_c3_child_request(
            execution_id, reservation_id, payload
        )

    def resume_thread(
        self, resume_intent: ResumeIntent, *, fail: bool = False
    ) -> ResumeReceipt:
        self._require_service_open()
        if self._context.external_adapter is None:
            raise ExternalAuthorityBoundaryUnavailable(
                "C2 production has no resume adapter"
            )
        return self._core_for_operation()._dispatch_external_effect(
            "resume", resume_intent, fail=fail
        )  # type: ignore[return-value]


def _approved_sqlite_build_for_authority(
    authority: ValidatedProductionAuthority | None,
) -> Any:
    if type(authority) is not ValidatedProductionAuthority:
        raise ExternalAuthorityBoundaryUnavailable(
            "production SQLite binding requires validated production authority"
        )
    from trading_bot.runtime.windows_authority_schema import (
        load_approved_sqlite_authority_build,
    )

    build = load_approved_sqlite_authority_build()
    if build.digest.hex() != authority.sqlite_build_manifest_digest:
        raise ExternalAuthorityBoundaryUnavailable(
            "approved SQLite build does not match validated authority"
        )
    return build


def registered_provider_reservation_id_for_test(
    capability: ProviderConstructionPermit,
) -> str:
    return _registered_provider_reservation_id(capability)


def _require_test_consumer_core(
    core: TransactionalAuthorityCore, capability: object
) -> None:
    if type(core) is not TransactionalAuthorityCore or not core._context.test_only:
        raise ExternalAuthorityBoundaryUnavailable(
            "test capability consumer requires an explicit test service"
        )
    core.require_test_capability(capability)


def consume_provider_construction_permit_for_test(
    capability: ProviderConstructionPermit,
    reservation_id: str,
    *,
    core: TransactionalAuthorityCore,
) -> None:
    _require_test_consumer_core(core, capability)
    return _consume_provider_construction_permit(capability, reservation_id)


def registered_constructed_provider_reservation_id_for_test(
    provider: ConstructedProvider,
) -> str:
    return _registered_constructed_provider_reservation_id(provider)


def consume_constructed_provider_for_test(
    provider: ConstructedProvider,
    reservation_id: str,
    *,
    core: TransactionalAuthorityCore,
) -> None:
    _require_test_consumer_core(core, provider)
    return _consume_constructed_provider(provider, reservation_id)


def registered_process_intent_reservation_id_for_test(intent: ProcessIntent) -> str:
    return _registered_process_intent_reservation_id(intent)


def consume_process_intent_for_test(
    intent: ProcessIntent,
    reservation_id: str,
    *,
    core: TransactionalAuthorityCore,
) -> None:
    _require_test_consumer_core(core, intent)
    return _consume_process_intent(intent, reservation_id)


def registered_process_result_reservation_id_for_test(
    result: ProcessCreationReceipt | ProcessCreationFailure,
) -> str:
    return _registered_process_result_reservation_id(result)


def consume_process_result_for_test(
    result: ProcessCreationReceipt | ProcessCreationFailure,
    reservation_id: str,
    *,
    core: TransactionalAuthorityCore,
) -> None:
    _require_test_consumer_core(core, result)
    return _consume_process_result(result, reservation_id)


def registered_resume_intent_binding_for_test(intent: ResumeIntent) -> tuple[str, str]:
    return _registered_resume_intent_binding(intent)


def consume_resume_intent_for_test(
    intent: ResumeIntent,
    execution_id: str,
    reservation_id: str,
    *,
    core: TransactionalAuthorityCore,
) -> None:
    _require_test_consumer_core(core, intent)
    return _consume_resume_intent(intent, execution_id, reservation_id)


def registered_resume_result_binding_for_test(
    result: ResumeReceipt,
) -> tuple[str, str]:
    return _registered_resume_result_binding(result)


def consume_resume_result_for_test(
    result: ResumeReceipt,
    execution_id: str,
    reservation_id: str,
    *,
    core: TransactionalAuthorityCore,
) -> None:
    _require_test_consumer_core(core, result)
    return _consume_resume_result(result, execution_id, reservation_id)


def process_intent_json_for_test(
    reservation_id: str,
    request_digest: bytes,
    authority_policy_version: str,
    claim_policy_version: str,
) -> bytes:
    return _process_intent_json(
        reservation_id, request_digest, authority_policy_version, claim_policy_version
    )


def process_success_evidence_for_test(
    reservation_id: str, process_intent_digest: bytes
) -> tuple[bytes, bytes, bytes]:
    return _process_success_evidence(reservation_id, process_intent_digest)


def process_failure_json_for_test(
    reservation_id: str, process_intent_digest: bytes
) -> bytes:
    return _process_failure_json(reservation_id, process_intent_digest)


def process_result_visible_evidence_for_test(
    result: ProcessCreationReceipt | ProcessCreationFailure,
) -> tuple[tuple[bytes, ...], tuple[bytes, ...]]:
    return _process_result_visible_evidence(result)


def _issue_constructed_provider(
    reservation_id: str, *, issuer: object, service_token: object | None
) -> ConstructedProvider:
    permit = _ConstructedProviderOneShot()
    provider = ConstructedProvider(
        reservation_id,
        _issuer=issuer,
        _permit=permit,
        _service_token=service_token,
    )
    with _ISSUED_CONSTRUCTED_PROVIDERS_LOCK:
        _ISSUED_CONSTRUCTED_PROVIDERS[permit] = _ConstructedProviderIssuance(
            provider=_weak_reference(provider, "constructed provider"),
            reservation_id=reservation_id,
            issuer=issuer,
            permit=_weak_reference(permit, "constructed provider permit"),
            service_token=_optional_weak_reference(
                provider._service_token, "constructed provider service token"
            ),
        )
    return provider


def _issue_process_creation_receipt(
    reservation_id: str,
    process_intent_digest: bytes,
    process_json: bytes,
    process_digest: bytes,
    job_json: bytes,
    job_digest: bytes,
    resume_authorization_json: bytes,
    resume_authorization_digest: bytes,
    *,
    issuer: object,
    service_token: object | None,
) -> ProcessCreationReceipt:
    permit = _ProcessResultPermit()
    result = ProcessCreationReceipt(
        reservation_id=reservation_id,
        process_intent_digest=process_intent_digest,
        process_json=process_json,
        process_digest=process_digest,
        job_json=job_json,
        job_digest=job_digest,
        resume_authorization_json=resume_authorization_json,
        resume_authorization_digest=resume_authorization_digest,
        _issuer=issuer,
        _permit=permit,
        _service_token=service_token,
    )
    evidence, digests = _process_result_visible_evidence(result)
    with _ISSUED_PROCESS_RESULTS_LOCK:
        _ISSUED_PROCESS_RESULTS[permit] = _ProcessResultIssuance(
            result=_weak_reference(result, "process result"),
            reservation_id=reservation_id,
            process_intent_digest=process_intent_digest,
            evidence=evidence,
            digests=digests,
            issuer=issuer,
            permit=_weak_reference(permit, "process result permit"),
            service_token=_optional_weak_reference(
                result._service_token, "process result service token"
            ),
        )
    return result


def _issue_process_creation_failure(
    reservation_id: str,
    process_intent_digest: bytes,
    result_json: bytes,
    result_digest: bytes,
    *,
    issuer: object,
    service_token: object | None,
) -> ProcessCreationFailure:
    permit = _ProcessResultPermit()
    result = ProcessCreationFailure(
        reservation_id=reservation_id,
        process_intent_digest=process_intent_digest,
        result_json=result_json,
        result_digest=result_digest,
        _issuer=issuer,
        _permit=permit,
        _service_token=service_token,
    )
    evidence, digests = _process_result_visible_evidence(result)
    with _ISSUED_PROCESS_RESULTS_LOCK:
        _ISSUED_PROCESS_RESULTS[permit] = _ProcessResultIssuance(
            result=_weak_reference(result, "process failure"),
            reservation_id=reservation_id,
            process_intent_digest=process_intent_digest,
            evidence=evidence,
            digests=digests,
            issuer=issuer,
            permit=_weak_reference(permit, "process failure permit"),
            service_token=_optional_weak_reference(
                result._service_token, "process failure service token"
            ),
        )
    return result


def _issue_resume_receipt(
    execution_id: str,
    reservation_id: str,
    resume_intent_digest: bytes,
    result_json: bytes,
    result_digest: bytes,
    *,
    issuer: object,
    service_token: object | None,
) -> ResumeReceipt:
    permit = _ResumeResultPermit()
    result = ResumeReceipt(
        execution_id=execution_id,
        reservation_id=reservation_id,
        resume_intent_digest=resume_intent_digest,
        result_json=result_json,
        result_digest=result_digest,
        _issuer=issuer,
        _permit=permit,
        _service_token=service_token,
    )
    with _ISSUED_RESUME_RESULTS_LOCK:
        _ISSUED_RESUME_RESULTS[permit] = _ResumeResultIssuance(
            result=_weak_reference(result, "resume result"),
            execution_id=execution_id,
            reservation_id=reservation_id,
            resume_intent_digest=resume_intent_digest,
            result_json=result_json,
            result_digest=result_digest,
            issuer=issuer,
            permit=_weak_reference(permit, "resume result permit"),
            service_token=_optional_weak_reference(
                result._service_token, "resume result service token"
            ),
        )
    return result


def issue_constructed_provider_for_test(reservation_id: str) -> ConstructedProvider:
    return _issue_constructed_provider(
        reservation_id,
        issuer=_TEST_CONSTRUCTED_PROVIDER_ISSUER,
        service_token=_active_test_service_token(),
    )


def issue_process_creation_receipt_for_test(
    reservation_id: str,
    process_intent_digest: bytes,
    process_json: bytes,
    process_digest: bytes,
    job_json: bytes,
    job_digest: bytes,
    resume_authorization_json: bytes,
    resume_authorization_digest: bytes,
) -> ProcessCreationReceipt:
    return _issue_process_creation_receipt(
        reservation_id,
        process_intent_digest,
        process_json,
        process_digest,
        job_json,
        job_digest,
        resume_authorization_json,
        resume_authorization_digest,
        issuer=_TEST_PROCESS_RESULT_ISSUER,
        service_token=_active_test_service_token(),
    )


def issue_process_creation_failure_for_test(
    reservation_id: str,
    process_intent_digest: bytes,
    result_json: bytes,
    result_digest: bytes,
) -> ProcessCreationFailure:
    return _issue_process_creation_failure(
        reservation_id,
        process_intent_digest,
        result_json,
        result_digest,
        issuer=_TEST_PROCESS_RESULT_ISSUER,
        service_token=_active_test_service_token(),
    )


def issue_resume_receipt_for_test(
    execution_id: str,
    reservation_id: str,
    resume_intent_digest: bytes,
    result_json: bytes,
    result_digest: bytes,
) -> ResumeReceipt:
    return _issue_resume_receipt(
        execution_id,
        reservation_id,
        resume_intent_digest,
        result_json,
        result_digest,
        issuer=_TEST_RESUME_RESULT_ISSUER,
        service_token=_active_test_service_token(),
    )
