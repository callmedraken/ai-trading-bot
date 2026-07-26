"""Offline verification and replay for canonical daily snapshots."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from zoneinfo import ZoneInfo

from trading_bot.market_calendar import MarketCalendarError
from trading_bot.market_data.daily_snapshot_identity import (
    canonical_bars_evidence,
    daily_snapshot_audit_hash,
    daily_snapshot_id,
)
from trading_bot.market_data.daily_snapshot_models import (
    DailyMarketDataSnapshot,
    DailySnapshotReplayView,
)
from trading_bot.market_data.daily_snapshot_provider import (
    IdentifiedMarketCalendar,
    derive_completed_session,
    require_matching_calendar,
)
from trading_bot.market_data.daily_snapshot_serialization import (
    parse_daily_snapshot,
    serialize_daily_snapshot,
)
from trading_bot.market_data.exceptions import (
    DailySnapshotReplayError,
    DailySnapshotSerializationError,
    DailySnapshotVerificationError,
    InvalidDailySnapshotCalendarError,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DailySnapshotVerificationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class DailySnapshotVerificationCode(StrEnum):
    BYTE_LENGTH_MISMATCH = "BYTE_LENGTH_MISMATCH"
    SHA256_MISMATCH = "SHA256_MISMATCH"
    PARSE_ERROR = "PARSE_ERROR"
    CALENDAR_MISMATCH = "CALENDAR_MISMATCH"
    TARGET_SESSION_MISMATCH = "TARGET_SESSION_MISMATCH"
    COMPLETENESS_MISMATCH = "COMPLETENESS_MISMATCH"
    SESSION_TIMESTAMP_MISMATCH = "SESSION_TIMESTAMP_MISMATCH"
    PROVIDER_AS_OF_MISMATCH = "PROVIDER_AS_OF_MISMATCH"
    CANONICAL_BARS_MISMATCH = "CANONICAL_BARS_MISMATCH"
    AUDIT_HASH_MISMATCH = "AUDIT_HASH_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    NONCANONICAL_SERIALIZATION = "NONCANONICAL_SERIALIZATION"


@dataclass(frozen=True, slots=True)
class DailySnapshotVerificationDiagnostic:
    code: DailySnapshotVerificationCode
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, DailySnapshotVerificationCode):
            raise DailySnapshotVerificationError(
                "code must be DailySnapshotVerificationCode"
            )
        if type(self.detail) is not str or not self.detail:
            raise DailySnapshotVerificationError(
                "verification diagnostic detail must be nonblank"
            )


@dataclass(frozen=True, slots=True)
class DailySnapshotVerificationResult:
    """Complete immutable result of an offline byte verification."""

    status: DailySnapshotVerificationStatus
    byte_length: int
    sha256: str
    snapshot: DailyMarketDataSnapshot | None
    diagnostics: tuple[DailySnapshotVerificationDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, DailySnapshotVerificationStatus):
            raise DailySnapshotVerificationError(
                "status must be DailySnapshotVerificationStatus"
            )
        if type(self.byte_length) is not int or self.byte_length < 0:
            raise DailySnapshotVerificationError(
                "byte_length must be a nonnegative integer"
            )
        if (
            type(self.sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.sha256) is None
        ):
            raise DailySnapshotVerificationError(
                "sha256 must be lowercase SHA-256 text"
            )
        if (
            self.snapshot is not None
            and type(self.snapshot) is not DailyMarketDataSnapshot
        ):
            raise DailySnapshotVerificationError(
                "snapshot must be DailyMarketDataSnapshot or None"
            )
        diagnostics = tuple(self.diagnostics)
        if any(
            type(item) is not DailySnapshotVerificationDiagnostic
            for item in diagnostics
        ):
            raise DailySnapshotVerificationError(
                "diagnostics must contain verification diagnostics"
            )
        if self.status is DailySnapshotVerificationStatus.PASS:
            if type(self.snapshot) is not DailyMarketDataSnapshot or diagnostics:
                raise DailySnapshotVerificationError(
                    "PASS requires a snapshot and no diagnostics"
                )
        elif not diagnostics:
            raise DailySnapshotVerificationError(
                "FAIL requires at least one diagnostic"
            )
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def passed(self) -> bool:
        return self.status is DailySnapshotVerificationStatus.PASS


def verify_daily_snapshot(
    payload: bytes,
    calendar: IdentifiedMarketCalendar,
    *,
    expected_sha256: str | None = None,
    expected_byte_length: int | None = None,
) -> DailySnapshotVerificationResult:
    """Verify canonical bytes and all retained deterministic snapshot evidence."""
    if type(payload) is not bytes:
        raise DailySnapshotVerificationError("payload must be exact bytes")
    _validate_expected_sha256(expected_sha256)
    _validate_expected_byte_length(expected_byte_length)

    actual_length = len(payload)
    actual_sha256 = sha256(payload).hexdigest()
    diagnostics: list[DailySnapshotVerificationDiagnostic] = []
    if expected_byte_length is not None and actual_length != expected_byte_length:
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.BYTE_LENGTH_MISMATCH,
                "payload byte length does not match expected evidence",
            )
        )
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.SHA256_MISMATCH,
                "payload SHA-256 does not match expected evidence",
            )
        )

    try:
        snapshot = parse_daily_snapshot(payload)
    except DailySnapshotSerializationError as error:
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.PARSE_ERROR,
                str(error),
            )
        )
        return DailySnapshotVerificationResult(
            DailySnapshotVerificationStatus.FAIL,
            actual_length,
            actual_sha256,
            None,
            tuple(diagnostics),
        )

    diagnostics.extend(_verify_snapshot_model(snapshot, payload, calendar))
    status = (
        DailySnapshotVerificationStatus.PASS
        if not diagnostics
        else DailySnapshotVerificationStatus.FAIL
    )
    return DailySnapshotVerificationResult(
        status,
        actual_length,
        actual_sha256,
        snapshot,
        tuple(diagnostics),
    )


def replay_verified_daily_snapshot(
    result: DailySnapshotVerificationResult,
) -> DailySnapshotReplayView:
    """Return exact retained bars only from a complete PASS result."""
    if type(result) is not DailySnapshotVerificationResult:
        raise DailySnapshotReplayError("result must be DailySnapshotVerificationResult")
    if not result.passed or result.snapshot is None:
        raise DailySnapshotReplayError(
            "offline replay requires a complete PASS verification result"
        )
    snapshot = result.snapshot
    return DailySnapshotReplayView(
        snapshot_id=snapshot.snapshot_id,
        target_session=snapshot.target_session,
        provider=snapshot.provider,
        symbols=snapshot.request.symbols,
        bars=snapshot.bars,
    )


def _verify_snapshot_model(
    snapshot: DailyMarketDataSnapshot,
    payload: bytes,
    calendar: IdentifiedMarketCalendar,
) -> tuple[DailySnapshotVerificationDiagnostic, ...]:
    diagnostics: list[DailySnapshotVerificationDiagnostic] = []
    try:
        require_matching_calendar(snapshot.request, calendar)
    except InvalidDailySnapshotCalendarError:
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.CALENDAR_MISMATCH,
                "supplied calendar does not match the retained descriptor",
            )
        )
    else:
        try:
            expected_target = derive_completed_session(snapshot.request, calendar)
        except MarketCalendarError:
            diagnostics.append(
                DailySnapshotVerificationDiagnostic(
                    DailySnapshotVerificationCode.TARGET_SESSION_MISMATCH,
                    "retained request is outside the modeled calendar boundary",
                )
            )
        else:
            if snapshot.target_session != expected_target:
                diagnostics.append(
                    DailySnapshotVerificationDiagnostic(
                        DailySnapshotVerificationCode.TARGET_SESSION_MISMATCH,
                        "target session is not the prior modeled XNYS session",
                    )
                )

    if (
        len(snapshot.bars) != len(snapshot.request.symbols)
        or tuple(item.bar.symbol for item in snapshot.bars) != snapshot.request.symbols
        or any(item.session != snapshot.target_session for item in snapshot.bars)
        or len(snapshot.audit.provider_response_symbols)
        != len(snapshot.request.symbols)
        or set(snapshot.audit.provider_response_symbols)
        != set(snapshot.request.symbols)
    ):
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.COMPLETENESS_MISMATCH,
                "retained bars or response order are incomplete",
            )
        )

    timezone = ZoneInfo(snapshot.request.calendar.exchange_timezone)
    if any(
        item.bar.timestamp.astimezone(timezone).date() != item.session.session_date
        for item in snapshot.bars
    ):
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.SESSION_TIMESTAMP_MISMATCH,
                "a bar timestamp does not map to its retained session",
            )
        )

    if (
        snapshot.audit.provider_as_of is not None
        and snapshot.audit.provider_as_of.astimezone(timezone).date()
        < snapshot.target_session.session_date
    ):
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.PROVIDER_AS_OF_MISMATCH,
                "provider_as_of precedes the retained target session",
            )
        )

    expected_bars = canonical_bars_evidence(snapshot.bars)
    if snapshot.canonical_bars != expected_bars:
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.CANONICAL_BARS_MISMATCH,
                "canonical accepted-bar evidence does not reconcile",
            )
        )

    expected_identity = daily_snapshot_id(
        snapshot.request,
        snapshot.target_session,
        snapshot.provider,
        snapshot.bars,
    )
    if snapshot.snapshot_id != expected_identity:
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.IDENTITY_MISMATCH,
                "snapshot UUID5 identity does not reconcile",
            )
        )

    expected_audit = daily_snapshot_audit_hash(
        snapshot_id=snapshot.snapshot_id,
        requested_at=snapshot.request.requested_at,
        captured_at=snapshot.audit.captured_at,
        provider_as_of=snapshot.audit.provider_as_of,
        provider_request_id=snapshot.audit.provider_request_id,
        provider_response_symbols=snapshot.audit.provider_response_symbols,
        source_payload=snapshot.audit.source_payload,
    )
    if snapshot.audit.audit_sha256 != expected_audit:
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.AUDIT_HASH_MISMATCH,
                "retained audit-evidence hash does not reconcile",
            )
        )

    try:
        canonical_payload = serialize_daily_snapshot(snapshot)
    except DailySnapshotSerializationError:
        canonical_payload = b""
    if payload != canonical_payload:
        diagnostics.append(
            DailySnapshotVerificationDiagnostic(
                DailySnapshotVerificationCode.NONCANONICAL_SERIALIZATION,
                "payload bytes are not the canonical snapshot serialization",
            )
        )
    return tuple(diagnostics)


def _validate_expected_sha256(value: str | None) -> None:
    if value is not None and (
        type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None
    ):
        raise DailySnapshotVerificationError(
            "expected_sha256 must be lowercase SHA-256 text or None"
        )


def _validate_expected_byte_length(value: int | None) -> None:
    if value is not None and (type(value) is not int or value < 0):
        raise DailySnapshotVerificationError(
            "expected_byte_length must be a nonnegative integer or None"
        )
