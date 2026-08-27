"""Pure C3 contracts for one production-authorized daily snapshot capture.

C3-A1 is intentionally non-effectful.  This module does not open production
SQLite, read credentials, create processes, call a provider, or publish output.
It freezes the caller-safe request shape and the exact bridge from one C2
capture_request/v2 intent to the existing daily-snapshot provider contract.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.market_calendar import (
    MarketCalendarError,
    NYSEMarketCalendar,
    TradingSession,
)
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    MAX_DAILY_SNAPSHOT_SYMBOLS,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailyProviderRequest,
    DailySnapshotCaptureRequest,
    ProviderDescriptor,
    build_daily_provider_request,
)

C3_DAILY_SNAPSHOT_REQUEST_NAMESPACE = UUID("fc8fa4ea-4286-5a50-adae-7ba30a8ebfa1")
C3_DAILY_SNAPSHOT_REQUEST_MATERIAL_VERSION = "c3-daily-snapshot-request-v1"
C3_CHILD_OPERATION_VERSION = "c3-isolated-alpaca-daily-capture/v1"
C3_CREDENTIAL_POLICY_VERSION = "windows-credential-manager-alpaca-market-data/v2"
C3_OUTPUT_POLICY_VERSION = "fixed-c1-capture-output/v1"

C2_BAR_INTERVAL = "1d"
C2_CHILD_OPERATION_VERSION = "child/v1"
C2_OUTPUT_POLICY_VERSION = "output/v1"

ALPACA_API_KEY_ID_CREDENTIAL_TARGET = "AITradingBot/MarketData/Alpaca/ApiKeyId/v2"
ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET = (
    "AITradingBot/MarketData/Alpaca/ApiSecretKey/v2"
)

_C2_REQUEST_FIELDS = frozenset(
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
_ONE_DAY = timedelta(days=1)


class WindowsEffectfulCapturePlanError(ValueError):
    """A non-effectful C3 production-capture contract is inconsistent."""


@dataclass(frozen=True, slots=True)
class ProductionCaptureRequest:
    """Caller-safe variable intent for one C3 capture.

    Provider, operation, protocol, output policy, and provider-call budget are
    deliberately not caller-selectable.  They are introduced only by
    ``to_c2_request_dict``.
    """

    ordered_universe: tuple[Symbol, ...]
    request_window_start_date: date
    request_window_end_date: date
    target_session_date: date

    def __post_init__(self) -> None:
        try:
            universe = tuple(self.ordered_universe)
        except TypeError as error:
            raise WindowsEffectfulCapturePlanError(
                "ordered_universe must be iterable"
            ) from error
        if not 1 <= len(universe) <= MAX_DAILY_SNAPSHOT_SYMBOLS:
            raise WindowsEffectfulCapturePlanError(
                "ordered_universe is empty or exceeds its bound"
            )
        if any(type(symbol) is not Symbol for symbol in universe):
            raise WindowsEffectfulCapturePlanError(
                "ordered_universe must contain exact Symbol values"
            )
        if len(set(universe)) != len(universe):
            raise WindowsEffectfulCapturePlanError(
                "ordered_universe must be duplicate-free"
            )
        for field_name in (
            "request_window_start_date",
            "request_window_end_date",
            "target_session_date",
        ):
            value = getattr(self, field_name)
            if type(value) is not date:
                raise WindowsEffectfulCapturePlanError(
                    f"{field_name} must be an exact date"
                )
        if self.request_window_start_date > self.request_window_end_date:
            raise WindowsEffectfulCapturePlanError(
                "request window start must not follow its end"
            )
        if self.request_window_end_date >= self.target_session_date:
            raise WindowsEffectfulCapturePlanError(
                "request window end must precede target_session_date"
            )
        object.__setattr__(self, "ordered_universe", universe)

    def to_c2_request_dict(self) -> dict[str, object]:
        """Return a fresh exact capture_request/v2 mapping for C2 revalidation."""

        request = {
            "bar_interval": C2_BAR_INTERVAL,
            "child_operation_version": C2_CHILD_OPERATION_VERSION,
            "ordered_universe": [str(symbol) for symbol in self.ordered_universe],
            "output_policy_version": C2_OUTPUT_POLICY_VERSION,
            "permitted_provider_operation": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
            "provider_id": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
            "request_limit": len(self.ordered_universe),
            "request_window_end_date": self.request_window_end_date.isoformat(),
            "request_window_start_date": self.request_window_start_date.isoformat(),
            "target_session_date": self.target_session_date.isoformat(),
        }
        if frozenset(request) != _C2_REQUEST_FIELDS:
            raise AssertionError("C3 C2-request construction drifted")
        return request

    def canonical_c2_request_json(self) -> bytes:
        """Serialize the exact C2 request object using its established encoding."""

        return json.dumps(
            self.to_c2_request_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ProductionCapturePlan:
    """Immutable nonsecret pre-effect plan reconciled to the current clock."""

    request: ProductionCaptureRequest
    requested_at_utc: datetime
    authorized_snapshot_session: TradingSession
    c2_request_json: bytes
    c2_request_digest: str

    def __post_init__(self) -> None:
        if type(self.request) is not ProductionCaptureRequest:
            raise WindowsEffectfulCapturePlanError(
                "capture plan requires ProductionCaptureRequest"
            )
        requested_at = _utc(self.requested_at_utc, "requested_at_utc")
        if type(self.authorized_snapshot_session) is not TradingSession:
            raise WindowsEffectfulCapturePlanError(
                "authorized snapshot session must be TradingSession"
            )
        expected_json = self.request.canonical_c2_request_json()
        if (
            type(self.c2_request_json) is not bytes
            or self.c2_request_json != expected_json
        ):
            raise WindowsEffectfulCapturePlanError(
                "capture plan C2 request bytes are inconsistent"
            )
        expected_digest = hashlib.sha256(expected_json).hexdigest()
        if self.c2_request_digest != expected_digest:
            raise WindowsEffectfulCapturePlanError(
                "capture plan C2 request digest is inconsistent"
            )
        authorized = _derive_authorized_snapshot_session(self.request)
        if self.authorized_snapshot_session != authorized:
            raise WindowsEffectfulCapturePlanError(
                "capture plan authorized session is inconsistent"
            )
        _require_clock_reconciles(requested_at, authorized)
        object.__setattr__(self, "requested_at_utc", requested_at)


@dataclass(frozen=True, slots=True)
class BoundProductionCapturePlan:
    """One plan bound to a canonical C2 launch reservation identity."""

    plan: ProductionCapturePlan
    reservation_id: str
    daily_snapshot_request: DailySnapshotCaptureRequest
    provider_request: DailyProviderRequest

    def __post_init__(self) -> None:
        if type(self.plan) is not ProductionCapturePlan:
            raise WindowsEffectfulCapturePlanError(
                "bound plan requires ProductionCapturePlan"
            )
        reservation_id = _canonical_uuid_text(self.reservation_id, "reservation_id")
        expected_request = _daily_snapshot_request(self.plan, reservation_id)
        if self.daily_snapshot_request != expected_request:
            raise WindowsEffectfulCapturePlanError(
                "bound daily-snapshot request is inconsistent"
            )
        expected_provider_request = build_daily_provider_request(
            expected_request,
            ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
            _identified_xnys_calendar(),
        )
        if self.provider_request != expected_provider_request:
            raise WindowsEffectfulCapturePlanError(
                "bound provider request is inconsistent"
            )
        if (
            self.provider_request.target_session
            != self.plan.authorized_snapshot_session
        ):
            raise WindowsEffectfulCapturePlanError(
                "provider target does not match authorized snapshot session"
            )
        object.__setattr__(self, "reservation_id", reservation_id)


@dataclass(frozen=True, slots=True)
class ProductionProviderLaunchPlan:
    """Secret-free fixed provider plan produced before process intent."""

    bound_capture: BoundProductionCapturePlan
    provider: ProviderDescriptor = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
    child_operation_version: str = C3_CHILD_OPERATION_VERSION
    credential_policy_version: str = C3_CREDENTIAL_POLICY_VERSION
    output_policy_version: str = C3_OUTPUT_POLICY_VERSION
    api_key_id_credential_target: str = ALPACA_API_KEY_ID_CREDENTIAL_TARGET
    api_secret_key_credential_target: str = ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET

    def __post_init__(self) -> None:
        if type(self.bound_capture) is not BoundProductionCapturePlan:
            raise WindowsEffectfulCapturePlanError(
                "provider launch plan requires a bound capture"
            )
        if self.provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR:
            raise WindowsEffectfulCapturePlanError(
                "provider launch plan must use the exact Alpaca descriptor"
            )
        fixed = {
            "child_operation_version": C3_CHILD_OPERATION_VERSION,
            "credential_policy_version": C3_CREDENTIAL_POLICY_VERSION,
            "output_policy_version": C3_OUTPUT_POLICY_VERSION,
            "api_key_id_credential_target": ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
            "api_secret_key_credential_target": ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
        }
        for field_name, expected in fixed.items():
            if getattr(self, field_name) != expected:
                raise WindowsEffectfulCapturePlanError(
                    f"provider launch plan {field_name} is not fixed"
                )
        if self.api_key_id_credential_target == self.api_secret_key_credential_target:
            raise WindowsEffectfulCapturePlanError(
                "provider credential targets must remain distinct"
            )

    @property
    def reservation_id(self) -> str:
        return self.bound_capture.reservation_id

    @property
    def c2_request_digest(self) -> str:
        return self.bound_capture.plan.c2_request_digest

    @property
    def authorized_snapshot_session(self) -> TradingSession:
        return self.bound_capture.plan.authorized_snapshot_session

    @property
    def provider_request(self) -> DailyProviderRequest:
        return self.bound_capture.provider_request


def prepare_production_capture_plan(
    request: ProductionCaptureRequest,
    requested_at_utc: datetime,
) -> ProductionCapturePlan:
    """Freeze one C3 request and prove clock/session reconciliation before effects."""

    if type(request) is not ProductionCaptureRequest:
        raise WindowsEffectfulCapturePlanError(
            "request must be ProductionCaptureRequest"
        )
    requested_at = _utc(requested_at_utc, "requested_at_utc")
    authorized = _derive_authorized_snapshot_session(request)
    _require_clock_reconciles(requested_at, authorized)
    request_json = request.canonical_c2_request_json()
    return ProductionCapturePlan(
        request=request,
        requested_at_utc=requested_at,
        authorized_snapshot_session=authorized,
        c2_request_json=request_json,
        c2_request_digest=hashlib.sha256(request_json).hexdigest(),
    )


def bind_production_capture_plan(
    plan: ProductionCapturePlan,
    reservation_id: str,
) -> BoundProductionCapturePlan:
    """Bind a reviewed nonsecret plan to one canonical C2 reservation UUID."""

    if type(plan) is not ProductionCapturePlan:
        raise WindowsEffectfulCapturePlanError("plan must be ProductionCapturePlan")
    canonical_reservation = _canonical_uuid_text(reservation_id, "reservation_id")
    daily_request = _daily_snapshot_request(plan, canonical_reservation)
    provider_request = build_daily_provider_request(
        daily_request,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
        _identified_xnys_calendar(),
    )
    if provider_request.target_session != plan.authorized_snapshot_session:
        raise WindowsEffectfulCapturePlanError(
            "daily snapshot target changed after C3 authorization"
        )
    return BoundProductionCapturePlan(
        plan=plan,
        reservation_id=canonical_reservation,
        daily_snapshot_request=daily_request,
        provider_request=provider_request,
    )


def build_production_provider_launch_plan(
    bound_capture: BoundProductionCapturePlan,
) -> ProductionProviderLaunchPlan:
    """Construct the exact secret-free plan represented by C2 construct_provider."""

    if type(bound_capture) is not BoundProductionCapturePlan:
        raise WindowsEffectfulCapturePlanError(
            "bound_capture must be BoundProductionCapturePlan"
        )
    return ProductionProviderLaunchPlan(bound_capture=bound_capture)


def derive_daily_snapshot_request_id(
    plan: ProductionCapturePlan,
    reservation_id: str,
) -> UUID:
    """Derive the clock-independent request UUID bound to one C2 reservation."""

    if type(plan) is not ProductionCapturePlan:
        raise WindowsEffectfulCapturePlanError("plan must be ProductionCapturePlan")
    canonical_reservation = _canonical_uuid_text(reservation_id, "reservation_id")
    values = (
        C3_DAILY_SNAPSHOT_REQUEST_MATERIAL_VERSION,
        canonical_reservation,
        plan.c2_request_digest,
        plan.authorized_snapshot_session.session_date.isoformat(),
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        C3_CHILD_OPERATION_VERSION,
        C3_CREDENTIAL_POLICY_VERSION,
        C3_OUTPUT_POLICY_VERSION,
    )
    material = "".join(_frame(value) for value in values)
    return uuid5(C3_DAILY_SNAPSHOT_REQUEST_NAMESPACE, material)


def _daily_snapshot_request(
    plan: ProductionCapturePlan,
    reservation_id: str,
) -> DailySnapshotCaptureRequest:
    request = DailySnapshotCaptureRequest(
        request_id=derive_daily_snapshot_request_id(plan, reservation_id),
        symbols=plan.request.ordered_universe,
        requested_at=plan.requested_at_utc,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
    )
    provider_request = build_daily_provider_request(
        request,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
        _identified_xnys_calendar(),
    )
    if provider_request.target_session != plan.authorized_snapshot_session:
        raise WindowsEffectfulCapturePlanError(
            "existing daily-snapshot derivation disagrees with C3 authorization"
        )
    return request


def _derive_authorized_snapshot_session(
    request: ProductionCaptureRequest,
) -> TradingSession:
    calendar = _identified_xnys_calendar()
    timezone = ZoneInfo(XNYS_CALENDAR_DESCRIPTOR.exchange_timezone)
    try:
        start = datetime.combine(
            request.request_window_start_date,
            time.min,
            tzinfo=timezone,
        )
        end_exclusive_date = request.request_window_end_date + _ONE_DAY
        end_exclusive = datetime.combine(
            end_exclusive_date,
            time.min,
            tzinfo=timezone,
        )
        sessions = calendar.sessions_between(start, end_exclusive).sessions
    except (MarketCalendarError, OverflowError, ValueError) as error:
        raise WindowsEffectfulCapturePlanError(
            "request window is outside the supported XNYS calendar"
        ) from error
    if not sessions:
        raise WindowsEffectfulCapturePlanError(
            "request window contains no modeled XNYS session"
        )
    authorized = sessions[-1]
    if authorized.session_date >= request.target_session_date:
        raise WindowsEffectfulCapturePlanError(
            "authorized snapshot session must precede target_session_date"
        )
    return authorized


def _require_clock_reconciles(
    requested_at_utc: datetime,
    authorized: TradingSession,
) -> None:
    calendar = _identified_xnys_calendar()
    try:
        observed = calendar.previous_session(requested_at_utc)
    except MarketCalendarError as error:
        raise WindowsEffectfulCapturePlanError(
            "requested_at_utc is outside the supported XNYS calendar"
        ) from error
    if observed != authorized:
        raise WindowsEffectfulCapturePlanError(
            "runtime clock does not reconcile with the C2-authorized snapshot session"
        )


def _identified_xnys_calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _utc(value: datetime, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise WindowsEffectfulCapturePlanError(
            f"{field_name} must be an exact timezone-aware datetime"
        )
    return value.astimezone(UTC)


def _canonical_uuid_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise WindowsEffectfulCapturePlanError(
            f"{field_name} must be a canonical UUID string"
        )
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise WindowsEffectfulCapturePlanError(
            f"{field_name} must be a canonical UUID string"
        ) from error
    if str(parsed) != value:
        raise WindowsEffectfulCapturePlanError(
            f"{field_name} must be a canonical UUID string"
        )
    return value


def _frame(value: str) -> str:
    if type(value) is not str:
        raise WindowsEffectfulCapturePlanError("identity material must be strings")
    encoded = value.encode("utf-8")
    return f"{len(encoded)}:{value}"
