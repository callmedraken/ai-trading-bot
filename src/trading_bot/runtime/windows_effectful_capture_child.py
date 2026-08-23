"""C3-B2 provider core and C3-C3A contained-child bootstrap."""

from __future__ import annotations

import hashlib
import struct
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Protocol

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    XNYS_CALENDAR_DESCRIPTOR,
    AlpacaDailySnapshotProvider,
    AlpacaHistoricalBarsTransport,
    AlpacaHttpResponse,
    AlpacaHttpStatusError,
    AlpacaResponseError,
    AlpacaTransportError,
    AlpacaTransportFailureStage,
    BoundMarketCalendar,
    DailyMarketDataSnapshot,
    DailyProviderRequest,
    DailySnapshotAcceptanceResult,
    DailySnapshotAcceptanceStatus,
    DailySnapshotCaptureRequest,
    DailySnapshotError,
    DailySnapshotSerializationError,
    InvalidDailySnapshotResponseError,
    StdlibAlpacaHistoricalBarsTransport,
    accept_daily_provider_response,
    build_daily_provider_request,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.market_data.alpaca_daily_snapshot import _AlpacaCredentials
from trading_bot.runtime.windows_effectful_capture_credentials import (
    ScopedAlpacaSecrets,
    WindowsAlpacaCredentialManagerReader,
    WindowsCredentialReadError,
    WindowsCredentialSidMismatchError,
)
from trading_bot.runtime.windows_effectful_capture_native import (
    C3_REQUEST_HANDLE_ARGUMENT,
    C3_RESULT_HANDLE_ARGUMENT,
    C3_STAGING_HANDLE_ARGUMENT,
    CtypesWindowsEffectfulCaptureChildIoApi,
    WindowsEffectfulCaptureChildIoApi,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    MAX_C3_CHILD_REQUEST_BYTES,
    MAX_C3_CHILD_RESULT_BYTES,
    ChildCleanupStatus,
    ChildResultClassification,
    IsolatedCaptureChildRequest,
    IsolatedCaptureChildResult,
    ProviderAttemptFenceState,
    WindowsEffectfulCaptureProtocolError,
    parse_isolated_capture_child_request,
    serialize_isolated_capture_child_request,
    serialize_isolated_capture_child_result,
)

C3_CHILD_BOOTSTRAP_EXIT_SUCCESS = 0
C3_CHILD_BOOTSTRAP_EXIT_FAILED = 1
_C3_CHILD_READ_CHUNK_BYTES = 4096
_MAX_UINT_PTR = (1 << (struct.calcsize("P") * 8)) - 1


class WindowsEffectfulCaptureChildError(RuntimeError):
    """The one-shot C3 child core was misused before a provider effect."""


class ChildSnapshotStagingWriter(Protocol):
    """Internal child service that owns only the inherited staging write target."""

    def write(self, payload: bytes) -> None: ...

    def flush(self) -> None: ...


class _ChildAttempt(Protocol):
    def run(self) -> IsolatedCaptureChildResult: ...


class _ChildBootstrapHandles:
    __slots__ = ("request_read", "result_write", "staging_write")

    def __init__(
        self, request_read: int, result_write: int, staging_write: int
    ) -> None:
        handles = (request_read, result_write, staging_write)
        if any(type(handle) is not int or handle <= 0 for handle in handles):
            raise WindowsEffectfulCaptureChildError("child bootstrap handle is invalid")
        if len(set(handles)) != 3:
            raise WindowsEffectfulCaptureChildError(
                "child bootstrap handles must be distinct"
            )
        self.request_read = request_read
        self.result_write = result_write
        self.staging_write = staging_write


class _ChildHandleOwner:
    __slots__ = ("_handles", "_native_io")

    def __init__(
        self,
        handles: _ChildBootstrapHandles,
        native_io: WindowsEffectfulCaptureChildIoApi,
    ) -> None:
        self._handles = [
            handles.request_read,
            handles.result_write,
            handles.staging_write,
        ]
        self._native_io = native_io

    def close_owned(self, handle: int) -> None:
        try:
            index = self._handles.index(handle)
        except ValueError:
            raise WindowsEffectfulCaptureChildError(
                "child handle cleanup was already attempted"
            ) from None
        # An uncertain CloseHandle outcome must not permit a second close attempt.
        self._handles.pop(index)
        self._native_io.close_handle(handle)

    def cleanup_remaining(self) -> bool:
        failed = False
        for handle in tuple(self._handles):
            try:
                self.close_owned(handle)
            except BaseException:
                failed = True
        return not failed


class _InheritedHandleSnapshotStagingWriter:
    """Bounded B2 writer over only the inherited staging HANDLE."""

    __slots__ = (
        "_flush_attempted",
        "_handle",
        "_native_io",
        "_write_attempted",
        "_write_complete",
    )

    def __init__(
        self, handle: int, native_io: WindowsEffectfulCaptureChildIoApi
    ) -> None:
        if type(handle) is not int or handle <= 0:
            raise WindowsEffectfulCaptureChildError("staging handle is invalid")
        self._handle = handle
        self._native_io = native_io
        self._write_attempted = False
        self._write_complete = False
        self._flush_attempted = False

    def write(self, payload: bytes) -> None:
        if self._write_attempted:
            raise WindowsEffectfulCaptureChildError(
                "staging payload write was already attempted"
            )
        self._write_attempted = True
        _complete_bounded_write(
            self._native_io,
            self._handle,
            payload,
            MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
            "staging payload",
        )
        self._write_complete = True

    def flush(self) -> None:
        if not self._write_complete or self._flush_attempted:
            raise WindowsEffectfulCaptureChildError("staging flush ordering is invalid")
        self._flush_attempted = True
        self._native_io.flush_file_buffers(self._handle)


class _ObservedSingleAttemptTransport:
    """Delegate at most one underlying Alpaca transport operation."""

    __slots__ = ("_called", "_inner", "_lock", "response")

    def __init__(self, inner: AlpacaHistoricalBarsTransport) -> None:
        if not callable(getattr(inner, "execute", None)):
            raise TypeError("child transport must implement execute")
        self._inner = inner
        self._lock = threading.Lock()
        self._called = False
        self.response: AlpacaHttpResponse | None = None

    @property
    def call_count(self) -> int:
        with self._lock:
            return int(self._called)

    def execute(
        self,
        request,
        *,
        api_key_id: str,
        api_secret_key: str,
    ):
        with self._lock:
            if self._called:
                raise WindowsEffectfulCaptureChildError(
                    "a second child transport operation is prohibited"
                )
            self._called = True
        response = self._inner.execute(
            request,
            api_key_id=api_key_id,
            api_secret_key=api_secret_key,
        )
        if type(response) is AlpacaHttpResponse:
            self.response = response
        return response


class IsolatedCaptureChildAttempt:
    """One retained canonical child request that can cross its fence once."""

    __slots__ = (
        "_clock",
        "_consumed",
        "_credential_reader",
        "_execution_id",
        "_lock",
        "_request_bytes",
        "_request_sha256",
        "_reservation_id",
        "_staging_writer",
        "_transport",
    )

    def __init__(
        self,
        *,
        request_bytes: bytes,
        credential_reader: WindowsAlpacaCredentialManagerReader,
        transport: AlpacaHistoricalBarsTransport,
        clock: Callable[[], datetime],
        staging_writer: ChildSnapshotStagingWriter,
        _issuer: object,
    ) -> None:
        if _issuer not in (_TEST_ATTEMPT_ISSUER, _PRODUCTION_ATTEMPT_ISSUER):
            raise TypeError("child attempts must be issued by the reviewed B2 boundary")
        request = parse_isolated_capture_child_request(request_bytes)
        if type(credential_reader) is not WindowsAlpacaCredentialManagerReader:
            raise TypeError("child credential reader must be the exact B1 reader")
        if not callable(getattr(transport, "execute", None)):
            raise TypeError("child transport must implement execute")
        if not callable(clock):
            raise TypeError("child clock must be callable")
        if not callable(getattr(staging_writer, "write", None)) or not callable(
            getattr(staging_writer, "flush", None)
        ):
            raise TypeError("child staging writer is invalid")
        self._request_bytes = bytes(request_bytes)
        self._request_sha256 = hashlib.sha256(self._request_bytes).hexdigest()
        self._reservation_id = request.reservation_id
        self._execution_id = request.execution_id
        self._credential_reader = credential_reader
        self._transport = transport
        self._clock = clock
        self._staging_writer = staging_writer
        self._lock = threading.Lock()
        self._consumed = False

    def __repr__(self) -> str:
        return "IsolatedCaptureChildAttempt(<bound canonical request>)"

    def run(self) -> IsolatedCaptureChildResult:
        with self._lock:
            if self._consumed:
                raise WindowsEffectfulCaptureChildError(
                    "isolated child attempt has already been consumed"
                )
            self._consumed = True

        # The admitted canonical request is consumed before any runtime effect.
        # Crossing this line is the C3_PROVIDER_ATTEMPT_ENTERED logical fence.
        try:
            request = parse_isolated_capture_child_request(self._request_bytes)
        except WindowsEffectfulCaptureProtocolError:
            return self._result(
                ChildResultClassification.REQUEST_INVALID,
                cleanup_status=ChildCleanupStatus.COMPLETE,
            )
        except Exception:
            return self._result(
                ChildResultClassification.INTERNAL_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
            )

        try:
            daily_request, provider_request, calendar = _reconcile_runtime_request(
                request
            )
        except (WindowsEffectfulCaptureProtocolError, DailySnapshotError):
            return self._result(
                ChildResultClassification.REQUEST_INVALID,
                cleanup_status=ChildCleanupStatus.COMPLETE,
            )
        except Exception:
            return self._result(
                ChildResultClassification.INTERNAL_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
            )

        try:
            scope = self._credential_reader.read(request.approved_account_sid)
        except WindowsCredentialSidMismatchError:
            return self._result(
                ChildResultClassification.SID_REJECTED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
            )
        except WindowsCredentialReadError:
            return self._result(
                ChildResultClassification.CREDENTIAL_FAILED,
                cleanup_status=ChildCleanupStatus.FAILED,
            )
        except Exception:
            return self._result(
                ChildResultClassification.CREDENTIAL_FAILED,
                cleanup_status=ChildCleanupStatus.FAILED,
            )

        if type(scope) is not ScopedAlpacaSecrets:
            try:
                close = getattr(scope, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass
            return self._result(
                ChildResultClassification.CREDENTIAL_FAILED,
                cleanup_status=ChildCleanupStatus.FAILED,
            )

        observed_transport = _ObservedSingleAttemptTransport(self._transport)
        acceptance: DailySnapshotAcceptanceResult | None = None
        provider_error: Exception | None = None
        cleanup_failed = False
        try:
            try:
                acceptance = scope.use(
                    lambda key, secret: _fetch_and_accept(
                        provider_request=provider_request,
                        calendar=calendar,
                        transport=observed_transport,
                        clock=self._clock,
                        api_key_id=key,
                        api_secret_key=secret,
                    )
                )
            except Exception as error:
                provider_error = error
        finally:
            try:
                scope.close()
            except Exception:
                cleanup_failed = True

        if cleanup_failed:
            return self._result(
                ChildResultClassification.INTERNAL_FAILED,
                cleanup_status=ChildCleanupStatus.FAILED,
                observed_transport=observed_transport,
            )

        if provider_error is not None:
            return self._provider_failure_result(provider_error, observed_transport)

        if type(acceptance) is not DailySnapshotAcceptanceResult:
            return self._result(
                ChildResultClassification.INTERNAL_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                observed_transport=observed_transport,
            )
        if acceptance.status is DailySnapshotAcceptanceStatus.REJECTED:
            return self._result(
                ChildResultClassification.SNAPSHOT_REJECTED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                observed_transport=observed_transport,
            )
        snapshot = acceptance.snapshot
        if type(snapshot) is not DailyMarketDataSnapshot:
            return self._result(
                ChildResultClassification.INTERNAL_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                observed_transport=observed_transport,
            )

        try:
            payload = serialize_daily_snapshot(snapshot)
        except DailySnapshotSerializationError:
            return self._result(
                ChildResultClassification.SERIALIZATION_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                observed_transport=observed_transport,
            )
        except Exception:
            return self._result(
                ChildResultClassification.SERIALIZATION_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                observed_transport=observed_transport,
            )

        payload_sha256 = hashlib.sha256(payload).hexdigest()
        try:
            verification = verify_daily_snapshot(
                payload,
                calendar,
                expected_sha256=payload_sha256,
                expected_byte_length=len(payload),
            )
        except Exception:
            return self._result(
                ChildResultClassification.SERIALIZATION_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                observed_transport=observed_transport,
            )
        if (
            not verification.passed
            or verification.snapshot is None
            or verification.snapshot.snapshot_id != snapshot.snapshot_id
            or verification.snapshot.request != daily_request
            or verification.snapshot.target_session
            != request.authorized_snapshot_session
            or verification.snapshot.provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
        ):
            return self._result(
                ChildResultClassification.SERIALIZATION_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                observed_transport=observed_transport,
            )

        try:
            self._staging_writer.write(payload)
            self._staging_writer.flush()
        except Exception:
            return self._result(
                ChildResultClassification.STAGING_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                observed_transport=observed_transport,
            )

        return self._result(
            ChildResultClassification.SUCCEEDED,
            cleanup_status=ChildCleanupStatus.COMPLETE,
            observed_transport=observed_transport,
            snapshot=snapshot,
            artifact_sha256=payload_sha256,
            artifact_byte_length=len(payload),
        )

    def _provider_failure_result(
        self,
        error: Exception,
        observed_transport: _ObservedSingleAttemptTransport,
    ) -> IsolatedCaptureChildResult:
        if isinstance(error, AlpacaHttpStatusError):
            status = _safe_failure_http_status(error.status)
            if status is None:
                return self._result(
                    ChildResultClassification.TRANSPORT_FAILED,
                    cleanup_status=ChildCleanupStatus.COMPLETE,
                )
            return self._result(
                ChildResultClassification.HTTP_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                http_status=status,
                provider_request_id=_safe_provider_request_id(error.request_id),
            )
        if isinstance(error, AlpacaTransportError):
            classification = {
                AlpacaTransportFailureStage.REQUEST: (
                    ChildResultClassification.TRANSPORT_REQUEST_FAILED
                ),
                AlpacaTransportFailureStage.RESPONSE_START: (
                    ChildResultClassification.TRANSPORT_RESPONSE_START_FAILED
                ),
                AlpacaTransportFailureStage.RESPONSE_METADATA: (
                    ChildResultClassification.TRANSPORT_RESPONSE_METADATA_FAILED
                ),
                AlpacaTransportFailureStage.RESPONSE_BODY: (
                    ChildResultClassification.TRANSPORT_RESPONSE_BODY_FAILED
                ),
                AlpacaTransportFailureStage.UNKNOWN: (
                    ChildResultClassification.TRANSPORT_FAILED
                ),
            }[error.stage]
            return self._result(
                classification,
                cleanup_status=ChildCleanupStatus.COMPLETE,
            )
        if isinstance(error, (AlpacaResponseError, InvalidDailySnapshotResponseError)):
            if observed_transport.response is not None:
                return self._result(
                    ChildResultClassification.PROVIDER_RESPONSE_INVALID,
                    cleanup_status=ChildCleanupStatus.COMPLETE,
                    observed_transport=observed_transport,
                )
            if observed_transport.call_count:
                return self._result(
                    ChildResultClassification.TRANSPORT_FAILED,
                    cleanup_status=ChildCleanupStatus.COMPLETE,
                )
            return self._result(
                ChildResultClassification.INTERNAL_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
            )
        if isinstance(error, DailySnapshotError):
            return self._result(
                ChildResultClassification.INTERNAL_FAILED,
                cleanup_status=ChildCleanupStatus.COMPLETE,
                observed_transport=observed_transport,
            )
        return self._result(
            ChildResultClassification.INTERNAL_FAILED,
            cleanup_status=ChildCleanupStatus.COMPLETE,
            observed_transport=observed_transport,
        )

    def _result(
        self,
        classification: ChildResultClassification,
        *,
        cleanup_status: ChildCleanupStatus,
        observed_transport: _ObservedSingleAttemptTransport | None = None,
        http_status: int | None = None,
        provider_request_id: str | None = None,
        snapshot: DailyMarketDataSnapshot | None = None,
        artifact_sha256: str | None = None,
        artifact_byte_length: int | None = None,
    ) -> IsolatedCaptureChildResult:
        if observed_transport is not None and observed_transport.response is not None:
            http_status = 200
            provider_request_id = _safe_provider_request_id(
                observed_transport.response.request_id
            )
        return IsolatedCaptureChildResult(
            reservation_id=self._reservation_id,
            execution_id=self._execution_id,
            child_request_sha256=self._request_sha256,
            fence_state=ProviderAttemptFenceState.ENTERED,
            classification=classification,
            cleanup_status=cleanup_status,
            snapshot_id=None if snapshot is None else snapshot.snapshot_id,
            artifact_sha256=artifact_sha256,
            artifact_byte_length=artifact_byte_length,
            http_status=http_status,
            provider_request_id=provider_request_id,
        )


_TEST_ATTEMPT_ISSUER = object()
_PRODUCTION_ATTEMPT_ISSUER = object()


def build_isolated_capture_child_attempt_for_test(
    request: IsolatedCaptureChildRequest,
    *,
    credential_reader: WindowsAlpacaCredentialManagerReader,
    transport: AlpacaHistoricalBarsTransport,
    clock: Callable[[], datetime],
    staging_writer: ChildSnapshotStagingWriter,
) -> IsolatedCaptureChildAttempt:
    """Explicit injected B2 seam; it never reads real credentials by itself."""

    if type(request) is not IsolatedCaptureChildRequest:
        raise TypeError("test child attempt requires IsolatedCaptureChildRequest")
    return IsolatedCaptureChildAttempt(
        request_bytes=serialize_isolated_capture_child_request(request),
        credential_reader=credential_reader,
        transport=transport,
        clock=clock,
        staging_writer=staging_writer,
        _issuer=_TEST_ATTEMPT_ISSUER,
    )


def _build_production_isolated_capture_child_attempt(
    request_bytes: bytes,
    *,
    staging_writer: ChildSnapshotStagingWriter,
) -> IsolatedCaptureChildAttempt:
    """Future C3-C internal factory for the real contained Windows child."""

    return IsolatedCaptureChildAttempt(
        request_bytes=request_bytes,
        credential_reader=WindowsAlpacaCredentialManagerReader(),
        transport=StdlibAlpacaHistoricalBarsTransport(),
        clock=lambda: datetime.now(UTC),
        staging_writer=staging_writer,
        _issuer=_PRODUCTION_ATTEMPT_ISSUER,
    )


def _parse_child_bootstrap_handles(
    arguments: Sequence[str],
) -> _ChildBootstrapHandles:
    if isinstance(arguments, (str, bytes)) or not isinstance(arguments, Sequence):
        raise WindowsEffectfulCaptureChildError("child bootstrap arguments are invalid")
    values = tuple(arguments)
    if len(values) != 6 or any(type(value) is not str for value in values):
        raise WindowsEffectfulCaptureChildError("child bootstrap arguments are invalid")
    supported = {
        C3_REQUEST_HANDLE_ARGUMENT: "request_read",
        C3_RESULT_HANDLE_ARGUMENT: "result_write",
        C3_STAGING_HANDLE_ARGUMENT: "staging_write",
    }
    parsed: dict[str, int] = {}
    for index in range(0, len(values), 2):
        flag = values[index]
        text = values[index + 1]
        field = supported.get(flag)
        if field is None or field in parsed:
            raise WindowsEffectfulCaptureChildError(
                "child bootstrap arguments are invalid"
            )
        if not text or not text.isascii() or not text.isdecimal() or text[0] == "0":
            raise WindowsEffectfulCaptureChildError(
                "child bootstrap handle text is invalid"
            )
        value = int(text)
        if value > _MAX_UINT_PTR:
            raise WindowsEffectfulCaptureChildError(
                "child bootstrap handle text is invalid"
            )
        parsed[field] = value
    if set(parsed) != set(supported.values()):
        raise WindowsEffectfulCaptureChildError("child bootstrap arguments are invalid")
    return _ChildBootstrapHandles(
        parsed["request_read"], parsed["result_write"], parsed["staging_write"]
    )


def run_isolated_capture_child_bootstrap_for_test(
    arguments: Sequence[str],
    *,
    native_io: WindowsEffectfulCaptureChildIoApi,
    attempt_factory: Callable[..., _ChildAttempt],
) -> int:
    """Explicit C3-C3A test seam with no production composition authority."""

    try:
        handles = _parse_child_bootstrap_handles(arguments)
        return _run_isolated_capture_child_bootstrap(
            handles,
            native_io=native_io,
            attempt_factory=attempt_factory,
        )
    except BaseException:
        return C3_CHILD_BOOTSTRAP_EXIT_FAILED


def main(argv: Sequence[str] | None = None) -> int:
    """Run only the reviewed real contained-child bindings without diagnostics."""

    try:
        arguments = tuple(sys.argv[1:] if argv is None else argv)
        handles = _parse_child_bootstrap_handles(arguments)
        native_io = CtypesWindowsEffectfulCaptureChildIoApi()
        return _run_isolated_capture_child_bootstrap(
            handles,
            native_io=native_io,
            attempt_factory=_build_production_isolated_capture_child_attempt,
        )
    except BaseException:
        return C3_CHILD_BOOTSTRAP_EXIT_FAILED


def _run_isolated_capture_child_bootstrap(
    handles: _ChildBootstrapHandles,
    *,
    native_io: WindowsEffectfulCaptureChildIoApi,
    attempt_factory: Callable[..., _ChildAttempt],
) -> int:
    owner = _ChildHandleOwner(handles, native_io)
    exit_code = C3_CHILD_BOOTSTRAP_EXIT_FAILED
    try:
        request_bytes = _read_canonical_child_request(native_io, handles.request_read)
        owner.close_owned(handles.request_read)
        staging_writer = _InheritedHandleSnapshotStagingWriter(
            handles.staging_write, native_io
        )
        attempt = attempt_factory(request_bytes, staging_writer=staging_writer)
        result = attempt.run()
        result_bytes = serialize_isolated_capture_child_result(result)
        _complete_bounded_write(
            native_io,
            handles.result_write,
            result_bytes,
            MAX_C3_CHILD_RESULT_BYTES,
            "child result",
        )
        exit_code = C3_CHILD_BOOTSTRAP_EXIT_SUCCESS
    except BaseException:
        exit_code = C3_CHILD_BOOTSTRAP_EXIT_FAILED
    if not owner.cleanup_remaining():
        exit_code = C3_CHILD_BOOTSTRAP_EXIT_FAILED
    return exit_code


def _read_canonical_child_request(
    native_io: WindowsEffectfulCaptureChildIoApi, request_handle: int
) -> bytes:
    payload = bytearray()
    while True:
        read_bound = min(
            _C3_CHILD_READ_CHUNK_BYTES,
            MAX_C3_CHILD_REQUEST_BYTES + 1 - len(payload),
        )
        chunk = native_io.read_file(request_handle, read_bound)
        if type(chunk) is not bytes or len(chunk) > read_bound:
            raise WindowsEffectfulCaptureChildError(
                "child request read result is invalid"
            )
        if not chunk:
            break
        payload.extend(chunk)
        if len(payload) > MAX_C3_CHILD_REQUEST_BYTES:
            raise WindowsEffectfulCaptureChildError(
                "child request exceeds its byte bound"
            )
    request_bytes = bytes(payload)
    if not request_bytes:
        raise WindowsEffectfulCaptureChildError("child request is empty")
    parse_isolated_capture_child_request(request_bytes)
    return request_bytes


def _complete_bounded_write(
    native_io: WindowsEffectfulCaptureChildIoApi,
    handle: int,
    payload: bytes,
    byte_bound: int,
    label: str,
) -> None:
    if type(payload) is not bytes or not payload or len(payload) > byte_bound:
        raise WindowsEffectfulCaptureChildError(f"{label} byte length is invalid")
    offset = 0
    while offset < len(payload):
        written = native_io.write_file(handle, payload[offset:])
        if type(written) is not int or written <= 0 or written > len(payload) - offset:
            raise WindowsEffectfulCaptureChildError(f"{label} write result is invalid")
        offset += written


def _reconcile_runtime_request(
    request: IsolatedCaptureChildRequest,
) -> tuple[DailySnapshotCaptureRequest, DailyProviderRequest, BoundMarketCalendar]:
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    daily_request = DailySnapshotCaptureRequest(
        request_id=request.daily_snapshot_request_id,
        symbols=request.capture_request.ordered_universe,
        requested_at=request.requested_at_utc,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
    )
    provider_request = build_daily_provider_request(
        daily_request,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
        calendar,
    )
    if provider_request.target_session != request.authorized_snapshot_session:
        raise WindowsEffectfulCaptureProtocolError(
            "child runtime target session disagrees with authorized session"
        )
    if provider_request.capture_request.request_id != request.daily_snapshot_request_id:
        raise WindowsEffectfulCaptureProtocolError(
            "child runtime daily snapshot request identity changed"
        )
    return daily_request, provider_request, calendar


def _fetch_and_accept(
    *,
    provider_request: DailyProviderRequest,
    calendar: BoundMarketCalendar,
    transport: _ObservedSingleAttemptTransport,
    clock: Callable[[], datetime],
    api_key_id: str,
    api_secret_key: str,
) -> DailySnapshotAcceptanceResult:
    provider = AlpacaDailySnapshotProvider(
        transport,
        _AlpacaCredentials(api_key_id, api_secret_key),
        clock,
    )
    response = provider.fetch(provider_request)
    return accept_daily_provider_response(provider_request, response, calendar)


def _safe_failure_http_status(value: object) -> int | None:
    if type(value) is not int or value == 200 or not 100 <= value <= 599:
        return None
    return value


def _safe_provider_request_id(value: object) -> str | None:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 128
        or any(ord(character) < 33 or ord(character) > 126 for character in value)
    ):
        return None
    return value


if __name__ == "__main__":
    raise SystemExit(main())
