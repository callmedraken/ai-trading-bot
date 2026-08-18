"""C3-B2 isolated child provider-execution core."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    XNYS_CALENDAR_DESCRIPTOR,
    AlpacaDailySnapshotProvider,
    AlpacaHistoricalBarsTransport,
    AlpacaHttpResponse,
    AlpacaHttpStatusError,
    AlpacaResponseError,
    AlpacaTransportError,
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
from trading_bot.runtime.windows_effectful_capture_protocol import (
    ChildCleanupStatus,
    ChildResultClassification,
    IsolatedCaptureChildRequest,
    IsolatedCaptureChildResult,
    ProviderAttemptFenceState,
    WindowsEffectfulCaptureProtocolError,
    parse_isolated_capture_child_request,
    serialize_isolated_capture_child_request,
)


class WindowsEffectfulCaptureChildError(RuntimeError):
    """The one-shot C3 child core was misused before a provider effect."""


class ChildSnapshotStagingWriter(Protocol):
    """Internal child service that owns only the inherited staging write target."""

    def write(self, payload: bytes) -> None: ...

    def flush(self) -> None: ...


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
            return self._result(
                ChildResultClassification.TRANSPORT_FAILED,
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
