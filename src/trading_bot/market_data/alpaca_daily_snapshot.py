"""Concrete one-attempt Alpaca adapter for provider-neutral daily snapshots."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data.alpaca_http import (
    ALPACA_DATA_HOST,
    AlpacaHistoricalBarsRequest,
    AlpacaHistoricalBarsTransport,
    AlpacaHttpResponse,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.market_data.daily_snapshot_models import (
    DailyBarCandidate,
    DailyProviderRequest,
    DailyProviderResponse,
    ProviderDescriptor,
    SourcePayloadEvidence,
)
from trading_bot.market_data.exceptions import (
    AlpacaCredentialError,
    AlpacaResponseError,
)

ALPACA_API_KEY_ID_ENVIRONMENT_VARIABLE = "APCA_API_KEY_ID"
ALPACA_API_SECRET_KEY_ENVIRONMENT_VARIABLE = "APCA_API_SECRET_KEY"

ALPACA_DAILY_SNAPSHOT_DESCRIPTOR = ProviderDescriptor(
    provider_id="alpaca-market-data",
    adapter_version=1,
    operation="historical-stock-bars-v2-raw-usd-no-asof",
    feed="sip",
)

_PUBLIC_HEADERS = (
    ("Accept", "application/json"),
    ("Accept-Encoding", "identity"),
    ("User-Agent", "ai-trading-bot-daily-snapshot/1"),
)
_ROOT_FIELDS = frozenset({"bars", "currency", "next_page_token"})
_REQUIRED_ROOT_FIELDS = frozenset({"bars", "next_page_token"})
_BAR_FIELDS = frozenset({"c", "h", "l", "n", "o", "t", "v", "vw", "x"})
_REQUIRED_BAR_FIELDS = frozenset({"c", "h", "l", "o", "t", "v"})
_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
_SAFE_EXCHANGE_PATTERN = re.compile(r"^[!-~]{1,16}$")


class _AlpacaCredentials:
    __slots__ = ("api_key_id", "api_secret_key")

    def __init__(self, api_key_id: str, api_secret_key: str) -> None:
        self.api_key_id = _credential(
            api_key_id, ALPACA_API_KEY_ID_ENVIRONMENT_VARIABLE
        )
        self.api_secret_key = _credential(
            api_secret_key,
            ALPACA_API_SECRET_KEY_ENVIRONMENT_VARIABLE,
        )

    def __repr__(self) -> str:
        return "_AlpacaCredentials(api_key_id=<redacted>, api_secret_key=<redacted>)"


class AlpacaDailySnapshotProvider:
    """Map one fixed Alpaca response into one provider-neutral envelope."""

    __slots__ = ("_clock", "_credentials", "_transport")

    def __init__(
        self,
        transport: AlpacaHistoricalBarsTransport,
        credentials: _AlpacaCredentials,
        clock: Callable[[], datetime],
    ) -> None:
        if not callable(getattr(transport, "execute", None)):
            raise AlpacaResponseError("transport must implement execute")
        if type(credentials) is not _AlpacaCredentials:
            raise AlpacaCredentialError("Alpaca credentials are invalid")
        if not callable(clock):
            raise AlpacaResponseError("clock must be callable")
        self._transport = transport
        self._credentials = credentials
        self._clock = clock

    def __repr__(self) -> str:
        return (
            "AlpacaDailySnapshotProvider("
            f"descriptor={ALPACA_DAILY_SNAPSHOT_DESCRIPTOR!r}, "
            "credentials=<redacted>)"
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ALPACA_DAILY_SNAPSHOT_DESCRIPTOR

    def fetch(self, request: DailyProviderRequest) -> DailyProviderResponse:
        if type(request) is not DailyProviderRequest:
            raise AlpacaResponseError("request must be a DailyProviderRequest")
        if request.provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR:
            raise AlpacaResponseError(
                "provider request does not match the fixed Alpaca descriptor"
            )
        http_request = build_alpaca_historical_bars_request(request)
        response = self._transport.execute(
            http_request,
            api_key_id=self._credentials.api_key_id,
            api_secret_key=self._credentials.api_secret_key,
        )
        if type(response) is not AlpacaHttpResponse:
            raise AlpacaResponseError("transport returned an invalid response")
        captured_at = self._clock()
        candidates, pagination_complete = parse_alpaca_historical_bars_response(
            response.body
        )
        return DailyProviderResponse(
            request=request,
            candidates=candidates,
            captured_at=captured_at,
            provider_as_of=None,
            provider_request_id=response.request_id,
            source_payload=SourcePayloadEvidence(
                sha256=response.body_sha256,
                byte_length=response.body_byte_length,
                media_type=response.media_type,
            ),
            pagination_complete=pagination_complete,
        )


def create_alpaca_daily_snapshot_provider(
    *,
    transport: AlpacaHistoricalBarsTransport,
    clock: Callable[[], datetime],
    environment: Mapping[str, str],
) -> AlpacaDailySnapshotProvider:
    """Load runtime credentials and create the fixed concrete provider."""
    if not isinstance(environment, Mapping):
        raise AlpacaCredentialError("credential environment must be a mapping")
    key = environment.get(ALPACA_API_KEY_ID_ENVIRONMENT_VARIABLE)
    secret = environment.get(ALPACA_API_SECRET_KEY_ENVIRONMENT_VARIABLE)
    if key is None:
        raise AlpacaCredentialError(f"missing {ALPACA_API_KEY_ID_ENVIRONMENT_VARIABLE}")
    if secret is None:
        raise AlpacaCredentialError(
            f"missing {ALPACA_API_SECRET_KEY_ENVIRONMENT_VARIABLE}"
        )
    return AlpacaDailySnapshotProvider(
        transport,
        _AlpacaCredentials(key, secret),
        clock,
    )


def build_alpaca_historical_bars_request(
    request: DailyProviderRequest,
) -> AlpacaHistoricalBarsRequest:
    """Build the exact nonsecret request target for one frozen session."""
    if type(request) is not DailyProviderRequest:
        raise AlpacaResponseError("request must be a DailyProviderRequest")
    if request.provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR:
        raise AlpacaResponseError(
            "provider request does not match the fixed Alpaca descriptor"
        )
    target_date = request.target_session.session_date
    start_utc, end_utc = alpaca_target_interval_utc(target_date)
    parameters = (
        (
            "symbols",
            ",".join(str(symbol) for symbol in request.capture_request.symbols),
        ),
        ("timeframe", "1Day"),
        ("start", canonical_timestamp(start_utc)),
        ("end", canonical_timestamp(end_utc)),
        ("limit", str(len(request.capture_request.symbols))),
        ("adjustment", "raw"),
        ("asof", "-"),
        ("feed", "sip"),
        ("currency", "USD"),
        ("sort", "asc"),
    )
    return AlpacaHistoricalBarsRequest(
        method="GET",
        host=ALPACA_DATA_HOST,
        target=f"/v2/stocks/bars?{urlencode(parameters)}",
        public_headers=_PUBLIC_HEADERS,
    )


def parse_alpaca_historical_bars_response(
    payload: bytes,
) -> tuple[tuple[DailyBarCandidate, ...], bool]:
    """Strictly map one bounded Alpaca JSON entity into untrusted candidates."""
    if type(payload) is not bytes:
        raise AlpacaResponseError("Alpaca response payload must be exact bytes")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise AlpacaResponseError("Alpaca response must not contain a UTF-8 BOM")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AlpacaResponseError("Alpaca response is not valid UTF-8") from error
    try:
        root = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_nonstandard_constant,
        )
    except (json.JSONDecodeError, AlpacaResponseError) as error:
        raise AlpacaResponseError("Alpaca response is not valid strict JSON") from error
    if type(root) is not dict:
        raise AlpacaResponseError("Alpaca response root must be an object")
    fields = frozenset(root)
    if not _REQUIRED_ROOT_FIELDS <= fields or not fields <= _ROOT_FIELDS:
        raise AlpacaResponseError("Alpaca response root fields are unsupported")
    if "currency" in root and root["currency"] != "USD":
        raise AlpacaResponseError("Alpaca response currency must be USD")
    bars = root["bars"]
    if type(bars) is not dict:
        raise AlpacaResponseError("Alpaca bars must be an object keyed by symbol")
    token = root["next_page_token"]
    if token is not None and (type(token) is not str or not token):
        raise AlpacaResponseError("Alpaca next_page_token must be null or nonblank")

    candidates: list[DailyBarCandidate] = []
    for raw_symbol, raw_bars in bars.items():
        symbol = _canonical_symbol(raw_symbol)
        if type(raw_bars) is not list:
            raise AlpacaResponseError("each Alpaca symbol must map to a bar array")
        for raw_bar in raw_bars:
            candidates.append(
                _candidate(
                    raw_bar,
                    symbol=symbol,
                    ordinal=len(candidates),
                )
            )
    return tuple(candidates), token is None


def _candidate(
    value: object,
    *,
    symbol: Symbol,
    ordinal: int,
) -> DailyBarCandidate:
    if type(value) is not dict:
        raise AlpacaResponseError("each Alpaca bar must be an object")
    fields = frozenset(value)
    if not _REQUIRED_BAR_FIELDS <= fields or not fields <= _BAR_FIELDS:
        raise AlpacaResponseError("Alpaca bar fields are unsupported")
    timestamp = _timestamp(value["t"])
    open_price = _positive_decimal(value["o"], "o")
    high = _positive_decimal(value["h"], "h")
    low = _positive_decimal(value["l"], "l")
    close = _positive_decimal(value["c"], "c")
    volume = _nonnegative_int(value["v"], "v")
    if "n" in value:
        _nonnegative_int(value["n"], "n")
    if "vw" in value:
        _positive_decimal(value["vw"], "vw")
    if "x" in value and (
        type(value["x"]) is not str
        or _SAFE_EXCHANGE_PATTERN.fullmatch(value["x"]) is None
    ):
        raise AlpacaResponseError("Alpaca bar x must be printable ASCII")
    exchange_date = timestamp.astimezone(ZoneInfo("America/New_York")).date()
    return DailyBarCandidate(
        response_ordinal=ordinal,
        symbol=symbol,
        session=TradingSession(exchange_date),
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _canonical_symbol(value: object) -> Symbol:
    if type(value) is not str:
        raise AlpacaResponseError("Alpaca bar symbol key must be a string")
    try:
        symbol = Symbol(value)
    except (TypeError, ValueError) as error:
        raise AlpacaResponseError("Alpaca bar symbol key is invalid") from error
    if str(symbol) != value:
        raise AlpacaResponseError("Alpaca bar symbol key is not canonical")
    return symbol


def _timestamp(value: object) -> datetime:
    if type(value) is not str or _TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise AlpacaResponseError("Alpaca bar timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AlpacaResponseError("Alpaca bar timestamp is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AlpacaResponseError("Alpaca bar timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _positive_decimal(value: object, field_name: str) -> Decimal:
    if type(value) is int:
        parsed = Decimal(value)
    elif type(value) is Decimal:
        parsed = value
    else:
        raise AlpacaResponseError(
            f"Alpaca bar {field_name} must be an exact JSON number"
        )
    if not parsed.is_finite() or parsed <= 0:
        raise AlpacaResponseError(
            f"Alpaca bar {field_name} must be finite and positive"
        )
    return parsed


def _nonnegative_int(value: object, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise AlpacaResponseError(
            f"Alpaca bar {field_name} must be a nonnegative integer"
        )
    return value


def _credential(value: object, variable_name: str) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(character in value for character in ("\r", "\n", "\0"))
    ):
        raise AlpacaCredentialError(f"{variable_name} is invalid")
    return value


def _reject_duplicate_keys(pairs):  # type: ignore[no-untyped-def]
    result = {}
    for key, value in pairs:
        if key in result:
            raise AlpacaResponseError("Alpaca response contains a duplicate key")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise AlpacaResponseError(f"Alpaca response contains unsupported constant {value}")


def alpaca_target_interval_utc(
    target_date: date,
) -> tuple[datetime, datetime]:
    """Return independently converted New York bounds for validation tests."""
    if type(target_date) is not date:
        raise AlpacaResponseError("target_date must be an exact date")
    timezone = ZoneInfo("America/New_York")
    start = datetime.combine(target_date, time.min, tzinfo=timezone).astimezone(UTC)
    end = (
        datetime.combine(
            target_date + timedelta(days=1),
            time.min,
            tzinfo=timezone,
        )
        - timedelta(microseconds=1)
    ).astimezone(UTC)
    return start, end
