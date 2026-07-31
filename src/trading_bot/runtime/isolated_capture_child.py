"""One-call child-side execution for an exact isolated capture allocation."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from trading_bot.cli.daily_snapshot_config import (
    load_daily_snapshot_capture_config,
)
from trading_bot.cli.daily_snapshot_output import (
    DailySnapshotArtifactResult,
    install_daily_snapshot_artifact,
    validate_daily_snapshot_destination_directory,
)
from trading_bot.cli.exceptions import (
    DailySnapshotArtifactOutputError,
    DailySnapshotCaptureRejectedError,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotAcceptanceStatus,
    InvalidDailySnapshotResponseError,
    derive_completed_session,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.market_data.alpaca_daily_snapshot import (
    create_alpaca_daily_snapshot_provider,
)
from trading_bot.market_data.alpaca_http import (
    AlpacaHistoricalBarsTransport,
    StdlibAlpacaHistoricalBarsTransport,
)
from trading_bot.market_data.daily_snapshot_provider import capture_daily_snapshot
from trading_bot.market_data.exceptions import (
    AlpacaCredentialError,
    AlpacaHttpStatusError,
    AlpacaResponseError,
    AlpacaTimeoutError,
    AlpacaTransportError,
)
from trading_bot.runtime.capture_attempt_authority import (
    SecretCleanupResult,
    SnapshotTerminalVerification,
    parse_capture_attempt_allocation,
    parse_windows_market_data_credential_reference,
)
from trading_bot.runtime.isolated_capture_artifacts import (
    IsolatedCaptureArtifactError,
    IsolatedCaptureChildClassification,
    IsolatedCaptureChildResult,
    IsolatedCaptureReconciliationError,
    ProviderCallDisposition,
    create_isolated_capture_child_result,
    evidence_for_payload,
    parse_isolated_capture_child_request,
    parse_isolated_capture_child_result,
    publish_canonical_artifact,
    reconcile_child_request,
    serialize_isolated_capture_child_request,
    serialize_isolated_capture_child_result,
    verify_payload_evidence,
)
from trading_bot.runtime.windows_credentials import (
    ScopedAlpacaSecrets,
    WindowsCredentialInvalidError,
    WindowsCredentialManagerReader,
    WindowsCredentialNotFoundError,
    WindowsCredentialReadError,
    WindowsCredentialSidMismatchError,
)


class ProviderFactory(Protocol):
    def __call__(
        self,
        *,
        transport: AlpacaHistoricalBarsTransport,
        clock: Callable[[], datetime],
        environment: dict[str, str],
    ) -> object: ...


class _CredentialReferenceInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IsolatedCaptureChildExecution:
    result: IsolatedCaptureChildResult
    result_path: Path
    snapshot_result: DailySnapshotArtifactResult | None


class OneCallProviderFence:
    """Reject a second fetch before it can reach the concrete provider."""

    __slots__ = ("_provider", "_invocations", "_maximum_candidate_count")

    def __init__(self, provider: object, maximum_candidate_count: int) -> None:
        if not callable(getattr(provider, "fetch", None)):
            raise InvalidDailySnapshotResponseError(
                "provider must implement fetch(request)"
            )
        self._provider = provider
        self._invocations = 0
        self._maximum_candidate_count = maximum_candidate_count

    @property
    def descriptor(self) -> object:
        return getattr(self._provider, "descriptor", None)

    @property
    def invocations(self) -> int:
        return self._invocations

    def fetch(self, request: object) -> object:
        if self._invocations != 0:
            raise InvalidDailySnapshotResponseError(
                "ONE_CALL_FENCE_SECOND_INVOCATION_BLOCKED"
            )
        self._invocations = 1
        response = self._provider.fetch(request)  # type: ignore[attr-defined]
        candidates = getattr(response, "candidates", None)
        if candidates is None or len(candidates) > self._maximum_candidate_count:
            raise InvalidDailySnapshotResponseError(
                "provider response candidate count exceeds approved limit"
            )
        return response


def execute_isolated_capture_child(
    request_path: Path,
    *,
    credential_reader: WindowsCredentialManagerReader | None = None,
    transport: AlpacaHistoricalBarsTransport | None = None,
    provider_factory: ProviderFactory = create_alpaca_daily_snapshot_provider,
    clock: Callable[[], datetime] | None = None,
) -> IsolatedCaptureChildExecution:
    """Strictly verify, retrieve child-only secrets, call once, and publish fact."""
    request_payload = _read_bounded(request_path)
    request = parse_isolated_capture_child_request(request_payload)
    request_evidence = evidence_for_payload(
        request.child_request_id,
        serialize_isolated_capture_child_request(request),
    )
    allocation_payload = _read_bounded(request.allocation_path)
    verify_payload_evidence(allocation_payload, request.allocation)
    allocation = parse_capture_attempt_allocation(allocation_payload)

    disposition = ProviderCallDisposition.NOT_STARTED
    classification = IsolatedCaptureChildClassification.INTERNAL_FAILED
    diagnostics: tuple[str, ...] = ("CHILD_INTERNAL_FAILED",)
    native_exit_code = 8
    http_status: int | None = None
    provider_code: int | None = None
    provider_request_id: str | None = None
    snapshot_evidence = None
    snapshot_verification = SnapshotTerminalVerification.NOT_APPLICABLE
    secret_cleanup = SecretCleanupResult.NOT_APPLICABLE
    snapshot_result: DailySnapshotArtifactResult | None = None
    scope: ScopedAlpacaSecrets | None = None
    provider_mapping: dict[str, str] | None = None
    provider: object | None = None
    fence: OneCallProviderFence | None = None

    try:
        try:
            credential_payload = _read_bounded(request.credential_reference_path)
            verify_payload_evidence(credential_payload, request.credential_reference)
            credential_reference = parse_windows_market_data_credential_reference(
                credential_payload
            )
            if (
                request.credential_reference != allocation.credential_reference
                or request.credential_reference.artifact_id
                != credential_reference.credential_reference_id
                or credential_reference.credential_version
                != allocation.credential_reference_version
            ):
                raise _CredentialReferenceInputError
        except Exception:
            raise _CredentialReferenceInputError from None
        configuration_payload = _read_bounded(request.capture_configuration_path)
        verify_payload_evidence(configuration_payload, request.capture_configuration)
        configuration = load_daily_snapshot_capture_config(
            request.capture_configuration_path
        )
        reconcile_child_request(
            request,
            allocation,
            credential_reference,
            configuration,
        )
        destination = validate_daily_snapshot_destination_directory(
            request.snapshot_destination_path
        )
        calendar = BoundMarketCalendar(
            XNYS_CALENDAR_DESCRIPTOR,
            NYSEMarketCalendar(),
        )
        capture_request = configuration.capture_request(request.request_timestamp_utc)
        if (
            derive_completed_session(capture_request, calendar)
            != request.target_session
        ):
            raise IsolatedCaptureReconciliationError(
                "target session does not match explicit request timestamp"
            )
        reader = (
            WindowsCredentialManagerReader()
            if credential_reader is None
            else credential_reader
        )
        verified_sid = reader.verify_current_sid(credential_reference)
        scope = reader.read_after_sid_verification(
            credential_reference,
            verified_sid,
        )
        provider_mapping = scope.as_provider_mapping()
        provider_transport = (
            StdlibAlpacaHistoricalBarsTransport() if transport is None else transport
        )
        capture_clock = _utc_now if clock is None else clock
        provider = provider_factory(
            transport=provider_transport,
            clock=capture_clock,
            environment=provider_mapping,
        )
        fence = OneCallProviderFence(provider, request.maximum_candidate_count)
        disposition = ProviderCallDisposition.MAY_HAVE_STARTED
        acceptance = capture_daily_snapshot(capture_request, fence, calendar)
        if fence.invocations != 1:
            raise InvalidDailySnapshotResponseError(
                "provider invocation count is invalid"
            )
        disposition = ProviderCallDisposition.RESPONSE_CONFIRMED
        if (
            acceptance.status is not DailySnapshotAcceptanceStatus.ACCEPTED
            or acceptance.snapshot is None
        ):
            raise DailySnapshotCaptureRejectedError(acceptance)
        snapshot = acceptance.snapshot
        provider_request_id = snapshot.audit.provider_request_id
        if snapshot.target_session != request.target_session:
            raise InvalidDailySnapshotResponseError(
                "snapshot target session does not reconcile"
            )
        payload = serialize_daily_snapshot(snapshot)
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        in_memory = verify_daily_snapshot(
            payload,
            calendar,
            expected_sha256=payload_sha256,
            expected_byte_length=len(payload),
        )
        if (
            not in_memory.passed
            or in_memory.snapshot != snapshot
            or in_memory.snapshot is None
        ):
            raise DailySnapshotArtifactOutputError(
                "in-memory snapshot verification failed"
            )
        snapshot_result = install_daily_snapshot_artifact(
            destination=destination,
            snapshot=snapshot,
            payload=payload,
            in_memory_verification=in_memory,
            calendar=calendar,
        )
        finalized = _read_bounded(snapshot_result.artifact_path)
        independent = verify_daily_snapshot(
            finalized,
            calendar,
            expected_sha256=snapshot_result.artifact_sha256,
            expected_byte_length=snapshot_result.artifact_byte_length,
        )
        if (
            not independent.passed
            or independent.snapshot != snapshot
            or independent.snapshot is None
        ):
            raise DailySnapshotArtifactOutputError(
                "independent finalized snapshot verification failed"
            )
        snapshot_evidence = evidence_for_payload(snapshot.snapshot_id, finalized)
        snapshot_verification = SnapshotTerminalVerification.PASS
        classification = IsolatedCaptureChildClassification.SUCCEEDED
        diagnostics = ("CAPTURE_SUCCEEDED",)
        native_exit_code = 0
    except WindowsCredentialSidMismatchError:
        classification = IsolatedCaptureChildClassification.SID_MISMATCH
        diagnostics = ("SID_MISMATCH",)
        native_exit_code = 4
    except WindowsCredentialNotFoundError:
        classification = IsolatedCaptureChildClassification.CREDENTIAL_NOT_FOUND
        diagnostics = ("CREDENTIAL_NOT_FOUND",)
        native_exit_code = 5
    except WindowsCredentialInvalidError:
        classification = IsolatedCaptureChildClassification.CREDENTIAL_INVALID
        diagnostics = ("CREDENTIAL_INVALID",)
        native_exit_code = 5
    except WindowsCredentialReadError:
        classification = IsolatedCaptureChildClassification.CREDENTIAL_REFERENCE_INVALID
        diagnostics = ("CREDENTIAL_REFERENCE_INVALID",)
        native_exit_code = 4
    except _CredentialReferenceInputError:
        classification = IsolatedCaptureChildClassification.CREDENTIAL_REFERENCE_INVALID
        diagnostics = ("CREDENTIAL_REFERENCE_INVALID",)
        native_exit_code = 4
    except AlpacaHttpStatusError as error:
        disposition = ProviderCallDisposition.RESPONSE_CONFIRMED
        http_status = error.status
        provider_code = error.provider_code
        provider_request_id = error.request_id
        if error.status in {401, 403}:
            classification = IsolatedCaptureChildClassification.AUTHENTICATION_FAILED
            diagnostics = ("AUTHENTICATION_FAILED",)
        else:
            classification = IsolatedCaptureChildClassification.PROVIDER_REJECTED
            diagnostics = ("PROVIDER_REJECTED",)
        native_exit_code = 6
    except (TimeoutError, AlpacaTimeoutError):
        disposition = (
            ProviderCallDisposition.MAY_HAVE_STARTED
            if fence is not None and fence.invocations == 1
            else disposition
        )
        classification = IsolatedCaptureChildClassification.TIMEOUT
        diagnostics = ("PROVIDER_TIMEOUT",)
        native_exit_code = 9
    except AlpacaCredentialError:
        classification = IsolatedCaptureChildClassification.CREDENTIAL_INVALID
        diagnostics = ("CREDENTIAL_INVALID",)
        native_exit_code = 5
    except AlpacaTransportError:
        disposition = (
            ProviderCallDisposition.MAY_HAVE_STARTED
            if fence is not None and fence.invocations == 1
            else disposition
        )
        classification = IsolatedCaptureChildClassification.NETWORK_FAILED
        diagnostics = ("NETWORK_FAILED",)
        native_exit_code = 6
    except (AlpacaResponseError, InvalidDailySnapshotResponseError):
        disposition = (
            ProviderCallDisposition.MAY_HAVE_STARTED
            if fence is not None and fence.invocations == 1
            else disposition
        )
        classification = IsolatedCaptureChildClassification.INCOMPLETE_RESPONSE
        diagnostics = ("INCOMPLETE_RESPONSE",)
        native_exit_code = 6
    except DailySnapshotCaptureRejectedError:
        classification = IsolatedCaptureChildClassification.INCOMPLETE_RESPONSE
        diagnostics = ("INCOMPLETE_RESPONSE",)
        native_exit_code = 6
    except DailySnapshotArtifactOutputError:
        classification = IsolatedCaptureChildClassification.SNAPSHOT_OUTPUT_FAILED
        diagnostics = ("SNAPSHOT_OUTPUT_FAILED",)
        native_exit_code = 7
    except (
        IsolatedCaptureArtifactError,
        IsolatedCaptureReconciliationError,
        OSError,
        ValueError,
    ):
        classification = IsolatedCaptureChildClassification.INTERNAL_FAILED
        diagnostics = ("CHILD_INPUT_INVALID",)
        native_exit_code = 3
    except Exception:
        classification = IsolatedCaptureChildClassification.INTERNAL_FAILED
        diagnostics = ("CHILD_INTERNAL_FAILED",)
        native_exit_code = 8
    finally:
        provider = None
        fence = None
        if provider_mapping is not None:
            provider_mapping.clear()
            provider_mapping = None
        if scope is not None:
            try:
                scope.close()
                secret_cleanup = SecretCleanupResult.PASS
            except Exception:
                secret_cleanup = SecretCleanupResult.FAIL
            scope = None

    if (
        classification is IsolatedCaptureChildClassification.SUCCEEDED
        and secret_cleanup is not SecretCleanupResult.PASS
    ):
        classification = IsolatedCaptureChildClassification.INTERNAL_FAILED
        diagnostics = ("SECRET_CLEANUP_FAILED",)
        native_exit_code = 8
        snapshot_verification = SnapshotTerminalVerification.NOT_APPLICABLE
        snapshot_evidence = None
    result = create_isolated_capture_child_result(
        child_request=request_evidence,
        allocation=request.allocation,
        attempt_id=request.attempt_id,
        provider_call_disposition=disposition,
        classification=classification,
        diagnostics=diagnostics,
        http_status=http_status,
        provider_code=provider_code,
        provider_request_id=provider_request_id,
        native_exit_code=native_exit_code,
        snapshot=snapshot_evidence,
        snapshot_verification=snapshot_verification,
        secret_cleanup=secret_cleanup,
        child_operation_version=request.child_operation_version,
    )
    result_payload = serialize_isolated_capture_child_result(result)
    publish_canonical_artifact(
        request.child_result_path,
        result_payload,
        parse_isolated_capture_child_result,
    )
    return IsolatedCaptureChildExecution(
        result=result,
        result_path=request.child_result_path,
        snapshot_result=snapshot_result,
    )


def _read_bounded(path: Path) -> bytes:
    if not isinstance(path, Path) or not path.is_absolute():
        raise IsolatedCaptureArtifactError("artifact path must be absolute")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise IsolatedCaptureArtifactError("artifact cannot be read") from error
    if len(payload) > 512 * 1024:
        raise IsolatedCaptureArtifactError("artifact exceeds bounded read")
    return payload


def _utc_now() -> datetime:
    return datetime.now(UTC)
