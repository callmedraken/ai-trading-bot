"""Architecture 148-B1 intraday research contracts and fake-only backtest.

The acquisition surface is deliberately transport-neutral: this module never
opens a socket, reads credentials, or touches a research directory.  A caller
may inject a page sender for a later, separately reviewed B2 acquisition.  B1
only defines the immutable OPEN data/custody contract and the deterministic
simulator over already supplied bars.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Context, Decimal, InvalidOperation, localcontext
from hashlib import sha256
from types import MappingProxyType
from typing import Protocol
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar, OrderSide, Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.experiments.historical_research_custody import (
    HistoricalResearchCustodyError,
    HistoricalSessionAuthority,
    canonical_json_bytes,
    require_accepted_historical_session_authority,
)
from trading_bot.experiments.historical_research_sessions import (
    AUTHORITY_DIGEST,
    AUTHORITY_IDENTITY,
    published_historical_session_authority,
)
from trading_bot.live_runtime.models import (
    CompletedBar,
    MarketQuality,
    MarketRegime,
    MarketSnapshot,
    SignalAnalysis,
    TargetPosition,
)
from trading_bot.live_runtime.strategy import (
    HardStopPolicy,
    SessionDecision,
    analyze_market,
    confirmed_regime_exit,
    session_decision,
)
from trading_bot.review_paper.session_admission import ReviewPaperSessionSchedule

ARCH148_INTRADAY_DATASET_SCHEMA = "arch148-intraday-dataset/v1"
ARCH148_INTRADAY_EVIDENCE_SCHEMA = "arch148-intraday-custody-evidence/v1"
ARCH148_INTRADAY_IDENTITY_VERSION = "arch148-intraday-dataset-identity/v1"
ARCH148_INTRADAY_EVIDENCE_IDENTITY_VERSION = "arch148-intraday-custody-identity/v1"
ARCH148_INTRADAY_IDENTITY_NAMESPACE = UUID("f0f7f3e1-4ad7-5b71-9e5b-2eb8e6a13d0c")
ARCH148_INTRADAY_EVIDENCE_NAMESPACE = UUID("a33e2ad9-6c1e-5b02-88c0-2dc7c4e5e2c2")

QQQ = "QQQ"
TQQQ_SYMBOL = "TQQQ"
SQQQ_SYMBOL = "SQQQ"
INTRADAY_SYMBOLS: tuple[str, ...] = (QQQ, TQQQ_SYMBOL, SQQQ_SYMBOL)
OPEN_START = datetime(2016, 1, 1, tzinfo=UTC)
OPEN_END_EXCLUSIVE = datetime(2024, 1, 1, tzinfo=UTC)
TIMEFRAME = "5Min"
PROVIDER_NAME = "Alpaca Market Data historical stock bars"
PROVIDER_ENDPOINT = "GET /v2/stocks/bars"
ADJUSTMENT = "all"
ADJUSTMENT_SEMANTICS = "SPLIT_PRICE_VOLUME|CASH_DIVIDEND_PRICE|SPIN_OFF_PRICE"
FEED = "sip"
CURRENCY = "USD"
ASOF = "-"
SORT = "asc"
LIMIT = 10_000
PRICE_BASIS = "ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1"
MAX_PROVIDER_PAGE_BYTES = 4 * 1024 * 1024
MAX_PAGES_PER_SYMBOL = 10_000
MAX_PAGE_TOKEN_LENGTH = 4096
MAX_VOLUME = (1 << 63) - 1
_NEW_YORK = ZoneInfo("America/New_York")
_BAR_WIDTH = timedelta(minutes=5)
_DECIMAL_CONTEXT = Context(prec=50)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PROVIDER_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)

# The accepted Architecture-146 published session resource records session
# dates.  Its cited ICE/NYSE source bundle also records these historical 13:00
# regular-session closes; this additive schedule projection never changes the
# accepted date authority or reads any market data/holdout artifact.
EARLY_CLOSE_DATES = frozenset(
    {
        date(2016, 7, 1),
        date(2016, 11, 25),
        date(2016, 12, 23),
        date(2017, 7, 3),
        date(2017, 11, 24),
        date(2018, 7, 3),
        date(2018, 11, 23),
        date(2018, 12, 24),
        date(2019, 7, 3),
        date(2019, 11, 29),
        date(2019, 12, 24),
        date(2020, 11, 27),
        date(2020, 12, 24),
        date(2021, 11, 26),
        date(2022, 11, 25),
        date(2023, 7, 3),
        date(2023, 11, 24),
    }
)


class Arch148IntradayError(ValueError):
    """Malformed, incomplete, noncanonical, or unreconciled B1 material."""


class IntradaySessionCoverageError(Arch148IntradayError):
    """A symbol is missing or contains an unexpected regular-session slot."""

    def __init__(
        self,
        symbol: str,
        missing: tuple[datetime, ...],
        unexpected: tuple[datetime, ...],
    ):
        self.symbol = symbol
        self.missing = missing
        self.unexpected = unexpected
        super().__init__(
            f"{symbol} session slot coverage mismatch: "
            f"missing={len(missing)}, unexpected={len(unexpected)}"
        )


def _timestamp_text(value: datetime) -> str:
    try:
        normalized = normalize_utc(value, "timestamp")
    except (TypeError, ValueError) as error:
        raise Arch148IntradayError("aware UTC timestamp required") from error
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise Arch148IntradayError("canonical UTC timestamp required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise Arch148IntradayError("invalid UTC timestamp") from None
    if _timestamp_text(parsed) != value:
        raise Arch148IntradayError("noncanonical UTC timestamp")
    return parsed


def _canonical_decimal(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise Arch148IntradayError("OHLC must be finite positive Decimals")
    with localcontext(_DECIMAL_CONTEXT):
        rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if not rendered:
        raise Arch148IntradayError("empty canonical Decimal")
    return rendered


def _parse_decimal(value: object) -> Decimal:
    if type(value) is not str:
        raise Arch148IntradayError("canonical Decimal text required")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise Arch148IntradayError("invalid Decimal text") from None
    if _canonical_decimal(parsed) != value:
        raise Arch148IntradayError("noncanonical Decimal text")
    return parsed


def _json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise Arch148IntradayError("noncanonical JSON material") from None


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise Arch148IntradayError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise Arch148IntradayError("nonfinite JSON constant")


def _digest(value: object) -> None:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise Arch148IntradayError("lowercase SHA256 required")


def _bar_to_dict(bar: Bar) -> dict[str, object]:
    return {
        "symbol": bar.symbol.value,
        "timestamp": _timestamp_text(bar.timestamp),
        "open": _canonical_decimal(bar.open),
        "high": _canonical_decimal(bar.high),
        "low": _canonical_decimal(bar.low),
        "close": _canonical_decimal(bar.close),
        "volume": bar.volume,
    }


def _bar_from_dict(value: object) -> Bar:
    if type(value) is not dict or set(value) != {
        "symbol",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }:
        raise Arch148IntradayError("bar fields do not match the schema")
    if type(value["symbol"]) is not str or type(value["volume"]) is not int:
        raise Arch148IntradayError("bar symbol or volume type is invalid")
    if value["volume"] < 0 or value["volume"] > MAX_VOLUME:
        raise Arch148IntradayError("bar volume is outside the bounded range")
    try:
        return Bar(
            Symbol(value["symbol"]),
            _parse_timestamp(value["timestamp"]),
            _parse_decimal(value["open"]),
            _parse_decimal(value["high"]),
            _parse_decimal(value["low"]),
            _parse_decimal(value["close"]),
            value["volume"],
        )
    except (TypeError, ValueError):
        raise Arch148IntradayError("bar values are invalid") from None


def _authority() -> HistoricalSessionAuthority:
    result = published_historical_session_authority()
    try:
        require_accepted_historical_session_authority(result)
    except (HistoricalResearchCustodyError, ValueError) as error:
        raise Arch148IntradayError(
            "published XNYS authority is not accepted"
        ) from error
    return result


@dataclass(frozen=True, slots=True)
class HistoricalIntradaySessionAuthority:
    """Historical schedule projection over the accepted Architecture-146 dates."""

    published: HistoricalSessionAuthority = field(default_factory=_authority)

    def __post_init__(self) -> None:
        if type(self.published) is not HistoricalSessionAuthority:
            raise TypeError("published must be HistoricalSessionAuthority")
        try:
            require_accepted_historical_session_authority(self.published)
        except (HistoricalResearchCustodyError, ValueError) as error:
            raise Arch148IntradayError(
                "published XNYS authority is not accepted"
            ) from error

    def schedule_for(self, session_date: date) -> ReviewPaperSessionSchedule | None:
        if type(session_date) is not date:
            raise TypeError("session_date must be exactly date")
        if session_date not in self.published.sessions:
            return None
        close_hour = 13 if session_date in EARLY_CLOSE_DATES else 16
        return ReviewPaperSessionSchedule(
            session_date=session_date,
            opens_at=datetime.combine(session_date, time(9, 30), _NEW_YORK),
            closes_at=datetime.combine(session_date, time(close_hour), _NEW_YORK),
        )


def session_slots(
    session_date: date,
    authority: HistoricalIntradaySessionAuthority | None = None,
) -> tuple[datetime, ...]:
    authority = authority or HistoricalIntradaySessionAuthority()
    schedule = authority.schedule_for(session_date)
    if schedule is None:
        return ()
    count = int((schedule.closes_at - schedule.opens_at) / _BAR_WIDTH)
    return tuple(schedule.opens_at + index * _BAR_WIDTH for index in range(count))


def expected_open_slots(
    start: datetime = OPEN_START,
    end_exclusive: datetime = OPEN_END_EXCLUSIVE,
    authority: HistoricalIntradaySessionAuthority | None = None,
) -> tuple[datetime, ...]:
    start = normalize_utc(start, "start")
    end_exclusive = normalize_utc(end_exclusive, "end_exclusive")
    if (
        start >= end_exclusive
        or start < OPEN_START
        or end_exclusive > OPEN_END_EXCLUSIVE
    ):
        raise Arch148IntradayError(
            "range must be a nonempty subset of the OPEN interval"
        )
    if any(
        value.hour or value.minute or value.second or value.microsecond
        for value in (start, end_exclusive)
    ):
        raise Arch148IntradayError("research range must use UTC midnight boundaries")
    authority = authority or HistoricalIntradaySessionAuthority()
    sessions = (
        item
        for item in authority.published.sessions
        if start.date() <= item < end_exclusive.date()
    )
    return tuple(slot for item in sessions for slot in session_slots(item, authority))


def validate_intraday_session_coverage(
    symbol: str,
    bars: tuple[Bar, ...],
    *,
    start: datetime = OPEN_START,
    end_exclusive: datetime = OPEN_END_EXCLUSIVE,
    authority: HistoricalIntradaySessionAuthority | None = None,
) -> None:
    if symbol not in INTRADAY_SYMBOLS:
        raise Arch148IntradayError("symbol is outside the fixed QQQ/TQQQ/SQQQ universe")
    if type(bars) is not tuple:
        raise Arch148IntradayError("bars must be a tuple")
    expected = expected_open_slots(start, end_exclusive, authority)
    actual = tuple(bar.timestamp for bar in bars)
    if any(type(bar) is not Bar or bar.symbol.value != symbol for bar in bars):
        raise Arch148IntradayError("bars do not match their requested symbol")
    if any(not start <= stamp < end_exclusive for stamp in actual):
        raise IntradaySessionCoverageError(symbol, (), actual)
    expected_set = set(expected)
    actual_set = set(actual)
    missing = tuple(item for item in expected if item not in actual_set)
    unexpected = tuple(item for item in actual if item not in expected_set)
    if actual != tuple(sorted(actual)) or len(actual_set) != len(actual):
        raise IntradaySessionCoverageError(symbol, missing, unexpected or actual)
    if actual != expected:
        raise IntradaySessionCoverageError(symbol, missing, unexpected)


@dataclass(frozen=True, slots=True)
class HistoricalIntradayRequest:
    """Frozen provider-neutral request for one symbol's complete OPEN history."""

    symbol: str
    page_token: str | None = None
    start: datetime = OPEN_START
    end_exclusive: datetime = OPEN_END_EXCLUSIVE
    timeframe: str = TIMEFRAME
    adjustment: str = ADJUSTMENT
    feed: str = FEED
    currency: str = CURRENCY
    asof: str = ASOF
    sort: str = SORT
    limit: int = LIMIT

    def __post_init__(self) -> None:
        if self.symbol not in INTRADAY_SYMBOLS:
            raise Arch148IntradayError("request symbol is outside the fixed universe")
        if self.page_token is not None and (
            type(self.page_token) is not str
            or not self.page_token
            or len(self.page_token) > MAX_PAGE_TOKEN_LENGTH
        ):
            raise Arch148IntradayError("pagination token is invalid")
        if (self.start, self.end_exclusive) != (OPEN_START, OPEN_END_EXCLUSIVE):
            raise Arch148IntradayError("request OPEN bounds are frozen")
        if (
            self.timeframe,
            self.adjustment,
            self.feed,
            self.currency,
            self.asof,
            self.sort,
            self.limit,
        ) != (TIMEFRAME, ADJUSTMENT, FEED, CURRENCY, ASOF, SORT, LIMIT):
            raise Arch148IntradayError("request semantics are frozen")

    @property
    def descriptor(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "start": _timestamp_text(self.start),
            "end_exclusive": _timestamp_text(self.end_exclusive),
            "timeframe": self.timeframe,
            "adjustment": self.adjustment,
            "feed": self.feed,
            "currency": self.currency,
            "asof": self.asof,
            "sort": self.sort,
            "limit": self.limit,
            "pagination": "next_page_token_exhaustion",
        }

    @property
    def digest(self) -> str:
        return sha256(canonical_json_bytes(self.descriptor)).hexdigest()


def frozen_intraday_request_descriptor() -> dict[str, object]:
    return HistoricalIntradayRequest(QQQ).descriptor


def build_alpaca_intraday_request(
    request: HistoricalIntradayRequest,
) -> object:
    if type(request) is not HistoricalIntradayRequest:
        raise Arch148IntradayError("request must be HistoricalIntradayRequest")
    from urllib.parse import urlencode

    import trading_bot.market_data.alpaca_http as alpaca_http

    parameters = [
        ("symbols", request.symbol),
        ("timeframe", TIMEFRAME),
        ("start", _timestamp_text(OPEN_START)),
        ("end", "2023-12-31T23:59:59.999999Z"),
        ("limit", str(LIMIT)),
        ("adjustment", ADJUSTMENT),
        ("asof", ASOF),
        ("feed", FEED),
        ("currency", CURRENCY),
        ("sort", SORT),
    ]
    if request.page_token is not None:
        parameters.append(("page_token", request.page_token))
    return alpaca_http.AlpacaHistoricalBarsRequest(
        method="GET",
        host=alpaca_http.ALPACA_DATA_HOST,
        target=f"/v2/stocks/bars?{urlencode(parameters)}",
        public_headers=(("Accept", "application/json"),),
    )


def _provider_timestamp(value: object) -> datetime:
    if type(value) is not str or _PROVIDER_TIMESTAMP.fullmatch(value) is None:
        raise Arch148IntradayError("provider bar timestamp shape is invalid")
    try:
        timestamp = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise Arch148IntradayError("provider bar timestamp is invalid") from None
    if not OPEN_START <= timestamp < OPEN_END_EXCLUSIVE:
        raise Arch148IntradayError("provider bar is outside the OPEN interval")
    return timestamp


def _provider_price(value: object) -> Decimal:
    if type(value) is Decimal:
        price = value
    elif type(value) is int:
        price = Decimal(value)
    else:
        raise Arch148IntradayError("provider prices must be JSON numbers")
    _canonical_decimal(price)
    return price


@dataclass(frozen=True, slots=True)
class HistoricalIntradayPage:
    bars: tuple[Bar, ...]
    next_page_token: str | None
    raw_page_sha256: str
    raw_page_byte_size: int

    def __post_init__(self) -> None:
        if type(self.bars) is not tuple or any(
            type(bar) is not Bar for bar in self.bars
        ):
            raise Arch148IntradayError("provider page bars are invalid")
        if self.next_page_token is not None and (
            type(self.next_page_token) is not str
            or not self.next_page_token
            or len(self.next_page_token) > MAX_PAGE_TOKEN_LENGTH
        ):
            raise Arch148IntradayError("provider next-page token is invalid")
        _digest(self.raw_page_sha256)
        if (
            type(self.raw_page_byte_size) is not int
            or not 0 < self.raw_page_byte_size <= MAX_PROVIDER_PAGE_BYTES
        ):
            raise Arch148IntradayError("raw provider page size is invalid")


def parse_alpaca_intraday_page(
    payload: bytes, request: HistoricalIntradayRequest
) -> HistoricalIntradayPage:
    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > MAX_PROVIDER_PAGE_BYTES
    ):
        raise Arch148IntradayError("provider response size or type is invalid")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise Arch148IntradayError("provider response must not contain a UTF-8 BOM")
    try:
        root = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object_pairs,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_constant,
        )
    except Arch148IntradayError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise Arch148IntradayError("provider response is not strict JSON") from None
    if type(root) is not dict or set(root) not in (
        {"bars", "next_page_token"},
        {"bars", "next_page_token", "currency"},
    ):
        raise Arch148IntradayError("provider response fields do not match the schema")
    if "currency" in root and root["currency"] != CURRENCY:
        raise Arch148IntradayError("provider response currency is invalid")
    token = root["next_page_token"]
    if token is not None and (
        type(token) is not str or not token or len(token) > MAX_PAGE_TOKEN_LENGTH
    ):
        raise Arch148IntradayError("provider next-page token is invalid")
    bars_by_symbol = root["bars"]
    if type(bars_by_symbol) is not dict or set(bars_by_symbol) != {request.symbol}:
        raise Arch148IntradayError("provider response contains an unexpected symbol")
    raw_bars = bars_by_symbol[request.symbol]
    if type(raw_bars) is not list:
        raise Arch148IntradayError("provider bars must be an array")
    bars: list[Bar] = []
    previous: datetime | None = None
    for raw in raw_bars:
        if (
            type(raw) is not dict
            or not {"t", "o", "h", "l", "c", "v"} <= set(raw)
            or not set(raw) <= {"t", "o", "h", "l", "c", "v", "n", "vw"}
        ):
            raise Arch148IntradayError("provider bar fields do not match the schema")
        timestamp = _provider_timestamp(raw["t"])
        if previous is not None and timestamp <= previous:
            raise Arch148IntradayError(
                "provider page bars must be strictly chronological"
            )
        previous = timestamp
        volume = raw["v"]
        if type(volume) is not int or not 0 <= volume <= MAX_VOLUME:
            raise Arch148IntradayError("provider bar volume is invalid")
        for optional in ("n",):
            if optional in raw and (
                type(raw[optional]) is not int or not 0 <= raw[optional] <= MAX_VOLUME
            ):
                raise Arch148IntradayError("provider optional count is invalid")
        if "vw" in raw:
            _provider_price(raw["vw"])
        try:
            bars.append(
                Bar(
                    Symbol(request.symbol),
                    timestamp,
                    _provider_price(raw["o"]),
                    _provider_price(raw["h"]),
                    _provider_price(raw["l"]),
                    _provider_price(raw["c"]),
                    volume,
                )
            )
        except (TypeError, ValueError):
            raise Arch148IntradayError("provider OHLCV values are invalid") from None
    return HistoricalIntradayPage(
        tuple(bars), token, sha256(payload).hexdigest(), len(payload)
    )


class HistoricalIntradayTransport(Protocol):
    def fetch_page(
        self, request: HistoricalIntradayRequest
    ) -> HistoricalIntradayPage: ...


@dataclass(frozen=True, slots=True)
class AlpacaIntradayPageTransport:
    """Decode pages from a caller-supplied sender; it does no networking."""

    send: Callable[[object], bytes]

    def fetch_page(self, request: HistoricalIntradayRequest) -> HistoricalIntradayPage:
        if not callable(self.send):
            raise Arch148IntradayError("sender must be callable")
        return parse_alpaca_intraday_page(
            self.send(build_alpaca_intraday_request(request)), request
        )


@dataclass(frozen=True, slots=True)
class CollectedIntradayPages:
    symbol: str
    bars: tuple[Bar, ...]
    raw_page_sha256: tuple[str, ...]
    raw_page_byte_size: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.symbol not in INTRADAY_SYMBOLS or type(self.bars) is not tuple:
            raise Arch148IntradayError("collected page material is invalid")
        if not self.raw_page_sha256 or len(self.raw_page_sha256) != len(
            self.raw_page_byte_size
        ):
            raise Arch148IntradayError("ordered raw page evidence is required")
        for value in self.raw_page_sha256:
            _digest(value)
        if any(
            type(value) is not int or value <= 0 for value in self.raw_page_byte_size
        ):
            raise Arch148IntradayError("raw page sizes are invalid")


def collect_intraday_pages(
    transport: HistoricalIntradayTransport, symbol: str
) -> CollectedIntradayPages:
    if symbol not in INTRADAY_SYMBOLS:
        raise Arch148IntradayError("symbol is outside the fixed universe")
    fetch_page = getattr(transport, "fetch_page", None)
    if not callable(fetch_page):
        raise Arch148IntradayError("transport must expose fetch_page")
    bars: list[Bar] = []
    page_hashes: list[str] = []
    page_sizes: list[int] = []
    token: str | None = None
    seen_tokens: set[str | None] = set()
    previous: datetime | None = None
    for _ in range(MAX_PAGES_PER_SYMBOL):
        if token in seen_tokens:
            raise Arch148IntradayError("provider pagination token repeated")
        seen_tokens.add(token)
        page = fetch_page(HistoricalIntradayRequest(symbol=symbol, page_token=token))
        if type(page) is not HistoricalIntradayPage:
            raise Arch148IntradayError("transport must return HistoricalIntradayPage")
        page_hashes.append(page.raw_page_sha256)
        page_sizes.append(page.raw_page_byte_size)
        for bar in page.bars:
            if bar.symbol.value != symbol:
                raise Arch148IntradayError(
                    "provider page returned an unexpected symbol"
                )
            if not OPEN_START <= bar.timestamp < OPEN_END_EXCLUSIVE:
                raise Arch148IntradayError("provider page returned an out-of-range bar")
            if previous is not None and bar.timestamp <= previous:
                raise Arch148IntradayError(
                    "provider pages are not strictly chronological"
                )
            previous = bar.timestamp
            bars.append(bar)
        token = page.next_page_token
        if token is None:
            return CollectedIntradayPages(
                symbol, tuple(bars), tuple(page_hashes), tuple(page_sizes)
            )
    raise Arch148IntradayError("provider pagination exceeded its bound")


def _normalized_csv(bars: tuple[Bar, ...]) -> bytes:
    rows = ["timestamp,symbol,open,high,low,close,volume\n"]
    for bar in bars:
        rows.append(
            ",".join(
                (
                    _timestamp_text(bar.timestamp),
                    bar.symbol.value,
                    _canonical_decimal(bar.open),
                    _canonical_decimal(bar.high),
                    _canonical_decimal(bar.low),
                    _canonical_decimal(bar.close),
                    str(bar.volume),
                )
            )
            + "\n"
        )
    return "".join(rows).encode("utf-8")


def _range_text(value: datetime) -> str:
    return _timestamp_text(value)


@dataclass(frozen=True, slots=True)
class IntradaySymbolDataset:
    symbol: str
    bars: tuple[Bar, ...]

    def __post_init__(self) -> None:
        if (
            self.symbol not in INTRADAY_SYMBOLS
            or type(self.bars) is not tuple
            or not self.bars
        ):
            raise Arch148IntradayError("symbol dataset is invalid")
        previous: datetime | None = None
        for bar in self.bars:
            if type(bar) is not Bar or bar.symbol.value != self.symbol:
                raise Arch148IntradayError("symbol dataset contains a mismatched bar")
            if previous is not None and bar.timestamp <= previous:
                raise Arch148IntradayError("symbol bars must be strictly chronological")
            previous = bar.timestamp

    @property
    def normalized_bytes(self) -> bytes:
        return _normalized_csv(self.bars)


def _request_descriptor_json() -> str:
    return canonical_json_bytes(
        {
            "schema": "arch148-intraday-request/v1",
            "symbols": list(INTRADAY_SYMBOLS),
            "start": _timestamp_text(OPEN_START),
            "end_exclusive": _timestamp_text(OPEN_END_EXCLUSIVE),
            "timeframe": TIMEFRAME,
            "adjustment": ADJUSTMENT,
            "feed": FEED,
            "currency": CURRENCY,
            "asof": ASOF,
            "sort": SORT,
            "limit": LIMIT,
            "pagination": "next_page_token_exhaustion",
        }
    ).decode("utf-8")


@dataclass(frozen=True, slots=True)
class IntradayDataset:
    start: datetime
    end_exclusive: datetime
    datasets: tuple[IntradaySymbolDataset, ...]
    request_descriptor_json: str = field(default_factory=_request_descriptor_json)
    calendar_identity: str = AUTHORITY_IDENTITY
    calendar_digest: str = AUTHORITY_DIGEST
    price_basis: str = PRICE_BASIS
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        start = normalize_utc(self.start, "start")
        end = normalize_utc(self.end_exclusive, "end_exclusive")
        if start >= end or start < OPEN_START or end > OPEN_END_EXCLUSIVE:
            raise Arch148IntradayError("dataset range must stay inside OPEN")
        if any(
            value.hour or value.minute or value.second or value.microsecond
            for value in (start, end)
        ):
            raise Arch148IntradayError("dataset range must use UTC midnight boundaries")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end_exclusive", end)
        if (
            type(self.datasets) is not tuple
            or tuple(item.symbol for item in self.datasets) != INTRADAY_SYMBOLS
        ):
            raise Arch148IntradayError("dataset must contain QQQ, TQQQ, SQQQ in order")
        if (
            self.price_basis != PRICE_BASIS
            or self.calendar_identity != AUTHORITY_IDENTITY
            or self.calendar_digest != AUTHORITY_DIGEST
        ):
            raise Arch148IntradayError("dataset provenance is frozen")
        try:
            descriptor = json.loads(self.request_descriptor_json)
        except (TypeError, ValueError):
            raise Arch148IntradayError(
                "request descriptor must be canonical JSON"
            ) from None
        if (
            type(descriptor) is not dict
            or _json_bytes(descriptor).decode() != self.request_descriptor_json
            or descriptor != json.loads(_request_descriptor_json())
        ):
            raise Arch148IntradayError(
                "request descriptor is not the frozen OPEN contract"
            )
        authority = HistoricalIntradaySessionAuthority()
        for item in self.datasets:
            validate_intraday_session_coverage(
                item.symbol,
                item.bars,
                start=start,
                end_exclusive=end,
                authority=authority,
            )
        timestamps = tuple(
            item.bars[i].timestamp for i in range(len(self.datasets[0].bars))
        )
        if any(
            tuple(item.bars[i].timestamp for i in range(len(item.bars))) != timestamps
            for item in self.datasets[1:]
        ):
            raise Arch148IntradayError(
                "all symbols must have identical slot timestamps"
            )
        material = [
            ARCH148_INTRADAY_IDENTITY_VERSION,
            _range_text(start),
            _range_text(end),
            self.price_basis,
            self.calendar_identity,
            self.calendar_digest,
            sha256(self.request_descriptor_json.encode()).hexdigest(),
            [
                [
                    item.symbol,
                    sha256(item.normalized_bytes).hexdigest(),
                    len(item.normalized_bytes),
                    len(item.bars),
                ]
                for item in self.datasets
            ],
        ]
        object.__setattr__(
            self,
            "identity",
            str(
                uuid5(
                    ARCH148_INTRADAY_IDENTITY_NAMESPACE,
                    canonical_json_bytes(material).decode(),
                )
            ),
        )

    @property
    def symbols(self) -> tuple[str, ...]:
        return INTRADAY_SYMBOLS

    @property
    def bars_by_symbol(self) -> Mapping[str, tuple[Bar, ...]]:
        return MappingProxyType({item.symbol: item.bars for item in self.datasets})

    @property
    def request_digest(self) -> str:
        return sha256(self.request_descriptor_json.encode()).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": ARCH148_INTRADAY_DATASET_SCHEMA,
            "identity": self.identity,
            "start": _range_text(self.start),
            "end_exclusive": _range_text(self.end_exclusive),
            "price_basis": self.price_basis,
            "calendar_identity": self.calendar_identity,
            "calendar_digest": self.calendar_digest,
            "request_descriptor": json.loads(self.request_descriptor_json),
            "datasets": [
                {
                    "symbol": item.symbol,
                    "bars": [_bar_to_dict(bar) for bar in item.bars],
                }
                for item in self.datasets
            ],
        }

    def to_json(self) -> str:
        return _json_bytes(self.to_dict()).decode("utf-8")

    @classmethod
    def from_json(cls, value: str | bytes) -> IntradayDataset:
        body = value.encode() if type(value) is str else value
        if type(body) is not bytes:
            raise Arch148IntradayError("dataset JSON must be text or bytes")
        try:
            raw = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_object_pairs,
                parse_constant=_reject_constant,
            )
        except Arch148IntradayError:
            raise
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise Arch148IntradayError("malformed dataset JSON") from None
        if type(raw) is not dict or _json_bytes(raw) != body:
            raise Arch148IntradayError("canonical dataset JSON required")
        expected = {
            "schema",
            "identity",
            "start",
            "end_exclusive",
            "price_basis",
            "calendar_identity",
            "calendar_digest",
            "request_descriptor",
            "datasets",
        }
        if set(raw) != expected or raw["schema"] != ARCH148_INTRADAY_DATASET_SCHEMA:
            raise Arch148IntradayError("dataset fields do not match the schema")
        datasets = []
        for item in raw["datasets"]:
            if (
                type(item) is not dict
                or set(item) != {"symbol", "bars"}
                or type(item["bars"]) is not list
            ):
                raise Arch148IntradayError(
                    "symbol dataset fields do not match the schema"
                )
            datasets.append(
                IntradaySymbolDataset(
                    item["symbol"], tuple(_bar_from_dict(bar) for bar in item["bars"])
                )
            )
        descriptor_json = _json_bytes(raw["request_descriptor"]).decode()
        result = cls(
            _parse_timestamp(raw["start"]),
            _parse_timestamp(raw["end_exclusive"]),
            tuple(datasets),
            descriptor_json,
            raw["calendar_identity"],
            raw["calendar_digest"],
            raw["price_basis"],
        )
        if raw["identity"] != result.identity or result.to_json() != body.decode(
            "utf-8"
        ):
            raise Arch148IntradayError("dataset identity or canonical bytes mismatch")
        return result


@dataclass(frozen=True, slots=True)
class IntradayPageEvidence:
    symbol: str
    raw_page_sha256: tuple[str, ...]
    raw_page_byte_size: tuple[int, ...]

    def __post_init__(self) -> None:
        if (
            self.symbol not in INTRADAY_SYMBOLS
            or not self.raw_page_sha256
            or len(self.raw_page_sha256) != len(self.raw_page_byte_size)
        ):
            raise Arch148IntradayError("page evidence is invalid")
        for digest in self.raw_page_sha256:
            _digest(digest)
        if any(type(size) is not int or size <= 0 for size in self.raw_page_byte_size):
            raise Arch148IntradayError("page evidence sizes are invalid")


@dataclass(frozen=True, slots=True)
class IntradayNormalizedEvidence:
    symbol: str
    normalized_sha256: str
    normalized_byte_size: int
    normalized_bar_count: int

    def __post_init__(self) -> None:
        if self.symbol not in INTRADAY_SYMBOLS:
            raise Arch148IntradayError("normalized evidence symbol is invalid")
        _digest(self.normalized_sha256)
        if self.normalized_byte_size <= 0 or self.normalized_bar_count <= 0:
            raise Arch148IntradayError("normalized evidence dimensions are invalid")


@dataclass(frozen=True, slots=True)
class IntradayCustodyEvidence:
    dataset_identity: str
    request_descriptor_json: str
    request_digest: str
    pages: tuple[IntradayPageEvidence, ...]
    normalized: tuple[IntradayNormalizedEvidence, ...]
    calendar_identity: str = AUTHORITY_IDENTITY
    calendar_digest: str = AUTHORITY_DIGEST
    price_basis: str = PRICE_BASIS
    schema: str = field(default=ARCH148_INTRADAY_EVIDENCE_SCHEMA, init=False)
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.dataset_identity) is not str or not self.dataset_identity:
            raise Arch148IntradayError("dataset identity is required")
        _digest(self.request_digest)
        if (
            self.request_descriptor_json != _request_descriptor_json()
            or sha256(self.request_descriptor_json.encode()).hexdigest()
            != self.request_digest
        ):
            raise Arch148IntradayError("request descriptor/digest mismatch")
        if (
            tuple(item.symbol for item in self.pages) != INTRADAY_SYMBOLS
            or tuple(item.symbol for item in self.normalized) != INTRADAY_SYMBOLS
        ):
            raise Arch148IntradayError("evidence symbols are not fixed and ordered")
        if (self.calendar_identity, self.calendar_digest, self.price_basis) != (
            AUTHORITY_IDENTITY,
            AUTHORITY_DIGEST,
            PRICE_BASIS,
        ):
            raise Arch148IntradayError("evidence provenance is frozen")
        material = {
            "dataset_identity": self.dataset_identity,
            "request_descriptor": json.loads(self.request_descriptor_json),
            "request_digest": self.request_digest,
            "pages": [
                {
                    "symbol": item.symbol,
                    "sha256": list(item.raw_page_sha256),
                    "sizes": list(item.raw_page_byte_size),
                }
                for item in self.pages
            ],
            "normalized": [
                {
                    "symbol": item.symbol,
                    "sha256": item.normalized_sha256,
                    "size": item.normalized_byte_size,
                    "count": item.normalized_bar_count,
                }
                for item in self.normalized
            ],
            "calendar_identity": self.calendar_identity,
            "calendar_digest": self.calendar_digest,
            "price_basis": self.price_basis,
        }
        object.__setattr__(
            self,
            "evidence_id",
            str(
                uuid5(
                    ARCH148_INTRADAY_EVIDENCE_NAMESPACE,
                    canonical_json_bytes(
                        [ARCH148_INTRADAY_EVIDENCE_IDENTITY_VERSION, material]
                    ).decode(),
                )
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "evidence_id": self.evidence_id,
            "dataset_identity": self.dataset_identity,
            "request_descriptor": json.loads(self.request_descriptor_json),
            "request_digest": self.request_digest,
            "pages": [
                {
                    "symbol": item.symbol,
                    "raw_page_sha256": list(item.raw_page_sha256),
                    "raw_page_byte_size": list(item.raw_page_byte_size),
                }
                for item in self.pages
            ],
            "normalized": [
                {
                    "symbol": item.symbol,
                    "normalized_sha256": item.normalized_sha256,
                    "normalized_byte_size": item.normalized_byte_size,
                    "normalized_bar_count": item.normalized_bar_count,
                }
                for item in self.normalized
            ],
            "calendar_identity": self.calendar_identity,
            "calendar_digest": self.calendar_digest,
            "price_basis": self.price_basis,
        }

    def to_json(self) -> str:
        return _json_bytes(self.to_dict()).decode("utf-8")

    @classmethod
    def from_json(cls, value: str | bytes) -> IntradayCustodyEvidence:
        body = value.encode() if type(value) is str else value
        try:
            raw = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_object_pairs,
                parse_constant=_reject_constant,
            )
        except Arch148IntradayError:
            raise
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise Arch148IntradayError("malformed custody evidence JSON") from None
        expected = {
            "schema",
            "evidence_id",
            "dataset_identity",
            "request_descriptor",
            "request_digest",
            "pages",
            "normalized",
            "calendar_identity",
            "calendar_digest",
            "price_basis",
        }
        if (
            type(raw) is not dict
            or set(raw) != expected
            or raw["schema"] != ARCH148_INTRADAY_EVIDENCE_SCHEMA
            or _json_bytes(raw) != body
        ):
            raise Arch148IntradayError(
                "custody evidence fields or canonical bytes are invalid"
            )
        pages = tuple(
            IntradayPageEvidence(
                item["symbol"],
                tuple(item["raw_page_sha256"]),
                tuple(item["raw_page_byte_size"]),
            )
            for item in raw["pages"]
        )
        normalized = tuple(
            IntradayNormalizedEvidence(
                item["symbol"],
                item["normalized_sha256"],
                item["normalized_byte_size"],
                item["normalized_bar_count"],
            )
            for item in raw["normalized"]
        )
        result = cls(
            raw["dataset_identity"],
            _json_bytes(raw["request_descriptor"]).decode(),
            raw["request_digest"],
            pages,
            normalized,
            raw["calendar_identity"],
            raw["calendar_digest"],
            raw["price_basis"],
        )
        if raw["evidence_id"] != result.evidence_id or result.to_json() != body.decode(
            "utf-8"
        ):
            raise Arch148IntradayError("custody evidence identity mismatch")
        return result


@dataclass(frozen=True, slots=True)
class IntradayAcquisitionResult:
    dataset: IntradayDataset
    custody: IntradayCustodyEvidence


def build_intraday_custody_evidence(
    dataset: IntradayDataset, collected: tuple[CollectedIntradayPages, ...]
) -> IntradayCustodyEvidence:
    if (
        type(dataset) is not IntradayDataset
        or type(collected) is not tuple
        or any(type(item) is not CollectedIntradayPages for item in collected)
        or tuple(item.symbol for item in collected) != INTRADAY_SYMBOLS
    ):
        raise Arch148IntradayError("collected symbols are incomplete or reordered")
    if any(item.bars != dataset.bars_by_symbol[item.symbol] for item in collected):
        raise Arch148IntradayError("collected bars do not match the dataset")
    pages = tuple(
        IntradayPageEvidence(item.symbol, item.raw_page_sha256, item.raw_page_byte_size)
        for item in collected
    )
    normalized = tuple(
        IntradayNormalizedEvidence(
            item.symbol,
            sha256(_normalized_csv(item.bars)).hexdigest(),
            len(_normalized_csv(item.bars)),
            len(item.bars),
        )
        for item in dataset.datasets
    )
    return IntradayCustodyEvidence(
        dataset.identity,
        dataset.request_descriptor_json,
        dataset.request_digest,
        pages,
        normalized,
    )


def verify_intraday_custody_evidence(
    dataset: IntradayDataset, custody: IntradayCustodyEvidence
) -> None:
    if (
        type(dataset) is not IntradayDataset
        or type(custody) is not IntradayCustodyEvidence
    ):
        raise Arch148IntradayError("exact dataset and custody evidence are required")
    if (
        custody.dataset_identity != dataset.identity
        or custody.request_digest != dataset.request_digest
    ):
        raise Arch148IntradayError("custody evidence is not bound to the dataset")
    for item in dataset.datasets:
        actual = _normalized_csv(item.bars)
        evidence = next(
            value for value in custody.normalized if value.symbol == item.symbol
        )
        if (sha256(actual).hexdigest(), len(actual), len(item.bars)) != (
            evidence.normalized_sha256,
            evidence.normalized_byte_size,
            evidence.normalized_bar_count,
        ):
            raise Arch148IntradayError("normalized custody evidence mismatch")
    IntradayCustodyEvidence.from_json(custody.to_json())


def acquire_intraday_dataset(
    transport: HistoricalIntradayTransport,
) -> IntradayAcquisitionResult:
    collected = tuple(
        collect_intraday_pages(transport, symbol) for symbol in INTRADAY_SYMBOLS
    )
    dataset = IntradayDataset(
        OPEN_START,
        OPEN_END_EXCLUSIVE,
        tuple(IntradaySymbolDataset(item.symbol, item.bars) for item in collected),
    )
    custody = build_intraday_custody_evidence(dataset, collected)
    verify_intraday_custody_evidence(dataset, custody)
    return IntradayAcquisitionResult(dataset, custody)


@dataclass(frozen=True, slots=True)
class BacktestCostModel:
    """Frozen deterministic transaction/slippage assumptions."""

    name: str
    slippage_bps: Decimal
    commission_per_side: Decimal

    def __post_init__(self) -> None:
        if (
            not self.name
            or type(self.slippage_bps) is not Decimal
            or type(self.commission_per_side) is not Decimal
        ):
            raise Arch148IntradayError("cost model fields are invalid")
        if (
            not self.slippage_bps.is_finite()
            or not self.commission_per_side.is_finite()
            or self.slippage_bps < 0
            or self.commission_per_side < 0
        ):
            raise Arch148IntradayError(
                "cost model values must be finite and nonnegative"
            )


ZERO_COST = BacktestCostModel("ZERO_COST", Decimal("0"), Decimal("0"))
CONSERVATIVE_COSTS = BacktestCostModel(
    "CONSERVATIVE_10_BPS", Decimal("10"), Decimal("0")
)


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    symbol: str
    entry_at: datetime
    entry_price: Decimal
    exit_at: datetime
    exit_price: Decimal
    quantity: Decimal
    gross_pnl: Decimal
    cost_adjusted_pnl: Decimal
    return_pct: Decimal
    exit_reason: str
    holding_duration: timedelta


@dataclass(frozen=True, slots=True)
class BacktestResult:
    dataset_identity: str
    cost_model: str
    gross_strategy_return: Decimal
    cost_adjusted_strategy_return: Decimal
    qqq_buy_and_hold_return: Decimal
    cash_control_return: Decimal
    maximum_drawdown: Decimal
    trade_count: int
    stop_hit_count: int
    reversal_exits: int
    forced_flat_count: int
    turnover: Decimal
    average_holding_duration: timedelta
    win_rate: Decimal
    average_win: Decimal
    average_loss: Decimal
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[Decimal, ...]


@dataclass(slots=True)
class _OpenBacktestPosition:
    symbol: str
    quantity: Decimal
    entry_at: datetime
    entry_raw: Decimal
    entry_fill: Decimal
    stop_price: Decimal
    entry_commission: Decimal


def _execution_price(
    raw: Decimal, side: OrderSide, model: BacktestCostModel
) -> Decimal:
    with localcontext(_DECIMAL_CONTEXT):
        slippage = model.slippage_bps / Decimal("10000")
        return raw * (
            Decimal("1") + slippage
            if side is OrderSide.BUY
            else Decimal("1") - slippage
        )


def _return(value: Decimal, base: Decimal) -> Decimal:
    with localcontext(_DECIMAL_CONTEXT):
        return value / base if base else Decimal("0")


def run_backtest(
    dataset: IntradayDataset,
    *,
    cost_model: BacktestCostModel = ZERO_COST,
    initial_capital: Decimal = Decimal("10000"),
    analyzer: Callable[..., SignalAnalysis] = analyze_market,
    session_policy: Callable[[datetime], SessionDecision] | None = None,
) -> BacktestResult:
    """Replay the accepted 148-A strategy with next-bar-open execution only."""

    if (
        type(dataset) is not IntradayDataset
        or type(cost_model) is not BacktestCostModel
    ):
        raise Arch148IntradayError("exact dataset and cost model are required")
    if (
        type(initial_capital) is not Decimal
        or not initial_capital.is_finite()
        or initial_capital <= 0
    ):
        raise Arch148IntradayError("initial capital must be finite and positive")
    if not callable(analyzer):
        raise Arch148IntradayError("analyzer must be callable")
    authority = HistoricalIntradaySessionAuthority()
    session_policy = session_policy or (
        lambda as_of: session_decision(as_of, authority=authority)
    )
    by_symbol = dataset.bars_by_symbol
    qqq_bars = by_symbol[QQQ]
    by_timestamp = {
        symbol: {bar.timestamp: bar for bar in bars}
        for symbol, bars in by_symbol.items()
    }
    cash = initial_capital
    position: _OpenBacktestPosition | None = None
    trades: list[BacktestTrade] = []
    equity_curve: list[Decimal] = []
    turnover = Decimal("0")
    stop_hits = 0
    reversal_exits = 0
    forced_flat = 0
    hard_stop = HardStopPolicy()
    signal_history: list[CompletedBar] = []

    for qqq_bar in qqq_bars:
        as_of = qqq_bar.timestamp
        current_bar = (
            by_timestamp[position.symbol][as_of] if position is not None else None
        )
        acted = False
        exit_reason: str | None = None
        exit_raw: Decimal | None = None
        if position is not None and current_bar is not None:
            if current_bar.open <= position.stop_price:
                exit_reason, exit_raw = "STOP", current_bar.open
            elif current_bar.low <= position.stop_price:
                exit_reason, exit_raw = "STOP", position.stop_price
            if exit_reason is not None:
                stop_hits += 1

        completed = tuple(
            CompletedBar(
                bar.timestamp,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
            )
            for bar in signal_history
        )
        signal: SignalAnalysis | None = None
        if completed:
            market = MarketSnapshot(
                as_of,
                completed,
                (),
                {},
            )
            signal = analyzer(market, authority=authority)

        decision = session_policy(as_of)
        if position is not None and exit_reason is None:
            if decision.force_flat:
                exit_reason, exit_raw = (
                    "FORCED_FLAT",
                    current_bar.open if current_bar else None,
                )
                forced_flat += 1
            elif signal is None or signal.quality is not MarketQuality.READY:
                exit_reason, exit_raw = (
                    "SAFETY",
                    current_bar.open if current_bar else None,
                )
            elif confirmed_regime_exit(signal, TargetPosition(position.symbol)):
                exit_reason, exit_raw = (
                    "REGIME_EXIT",
                    current_bar.open if current_bar else None,
                )
                reversal_exits += int(
                    signal.entry_confirmation
                    in (MarketRegime.BULLISH, MarketRegime.BEARISH)
                )
        if position is not None and exit_reason is not None and exit_raw is not None:
            raw_entry = position.entry_raw
            fill = _execution_price(exit_raw, OrderSide.SELL, cost_model)
            commission = cost_model.commission_per_side
            proceeds = position.quantity * fill - commission
            cash += proceeds
            gross_pnl = position.quantity * (exit_raw - raw_entry)
            cost_pnl = (
                proceeds
                - position.quantity * position.entry_fill
                - position.entry_commission
            )
            base = position.quantity * raw_entry
            trades.append(
                BacktestTrade(
                    position.symbol,
                    position.entry_at,
                    raw_entry,
                    as_of,
                    exit_raw,
                    position.quantity,
                    gross_pnl,
                    cost_pnl,
                    _return(cost_pnl, base),
                    exit_reason,
                    as_of - position.entry_at,
                )
            )
            turnover += base + position.quantity * exit_raw
            position = None
            acted = True

        if (
            position is None
            and not acted
            and signal is not None
            and decision.can_enter
            and signal.entry_confirmation
            in (MarketRegime.BULLISH, MarketRegime.BEARISH)
        ):
            target = (
                TQQQ_SYMBOL
                if signal.entry_confirmation is MarketRegime.BULLISH
                else SQQQ_SYMBOL
            )
            target_bar = by_timestamp[target][as_of]
            raw_entry = target_bar.open
            fill = _execution_price(raw_entry, OrderSide.BUY, cost_model)
            commission = cost_model.commission_per_side
            quantity = (cash - commission) / fill
            if quantity > 0:
                cash = Decimal("0")
                stop_price = hard_stop.threshold(fill)
                position = _OpenBacktestPosition(
                    target, quantity, as_of, raw_entry, fill, stop_price, commission
                )
                acted = True

        signal_history.append(
            CompletedBar(
                qqq_bar.timestamp,
                qqq_bar.open,
                qqq_bar.high,
                qqq_bar.low,
                qqq_bar.close,
                qqq_bar.volume,
            )
        )
        equity = (
            cash
            if position is None
            else cash + position.quantity * qqq_bar.close
            if position.symbol == QQQ
            else cash + position.quantity * by_timestamp[position.symbol][as_of].close
        )
        equity_curve.append(equity)

    if position is not None:
        raise Arch148IntradayError("backtest ended with an open position")
    gross_pnl = sum((item.gross_pnl for item in trades), Decimal("0"))
    cost_pnl = sum((item.cost_adjusted_pnl for item in trades), Decimal("0"))
    qqq_control = _return(qqq_bars[-1].close - qqq_bars[0].open, qqq_bars[0].open)
    peak = initial_capital
    maximum_drawdown = Decimal("0")
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            maximum_drawdown = max(maximum_drawdown, _return(peak - value, peak))
    wins = [item.return_pct for item in trades if item.cost_adjusted_pnl > 0]
    losses = [item.return_pct for item in trades if item.cost_adjusted_pnl < 0]
    average_duration = (
        sum((item.holding_duration for item in trades), timedelta()) / len(trades)
        if trades
        else timedelta()
    )
    return BacktestResult(
        dataset.identity,
        cost_model.name,
        _return(gross_pnl, initial_capital),
        _return(cost_pnl, initial_capital),
        qqq_control,
        Decimal("0"),
        maximum_drawdown,
        len(trades),
        stop_hits,
        reversal_exits,
        forced_flat,
        turnover,
        average_duration,
        _return(Decimal(len(wins)), Decimal(len(trades))) if trades else Decimal("0"),
        sum(wins, Decimal("0")) / Decimal(len(wins)) if wins else Decimal("0"),
        sum(losses, Decimal("0")) / Decimal(len(losses)) if losses else Decimal("0"),
        tuple(trades),
        tuple(equity_curve),
    )


__all__ = [
    "ADJUSTMENT",
    "ADJUSTMENT_SEMANTICS",
    "ARCH148_INTRADAY_DATASET_SCHEMA",
    "ARCH148_INTRADAY_EVIDENCE_SCHEMA",
    "AlpacaIntradayPageTransport",
    "BacktestCostModel",
    "BacktestResult",
    "BacktestTrade",
    "CONSERVATIVE_COSTS",
    "CURRENCY",
    "EARLY_CLOSE_DATES",
    "FEED",
    "HistoricalIntradayPage",
    "HistoricalIntradayRequest",
    "HistoricalIntradaySessionAuthority",
    "INTRADAY_SYMBOLS",
    "IntradayAcquisitionResult",
    "IntradayCustodyEvidence",
    "IntradayDataset",
    "IntradayNormalizedEvidence",
    "IntradayPageEvidence",
    "IntradaySessionCoverageError",
    "IntradaySymbolDataset",
    "LIMIT",
    "OPEN_END_EXCLUSIVE",
    "OPEN_START",
    "PRICE_BASIS",
    "TIMEFRAME",
    "ZERO_COST",
    "acquire_intraday_dataset",
    "build_alpaca_intraday_request",
    "build_intraday_custody_evidence",
    "collect_intraday_pages",
    "expected_open_slots",
    "frozen_intraday_request_descriptor",
    "parse_alpaca_intraday_page",
    "run_backtest",
    "session_slots",
    "validate_intraday_session_coverage",
    "verify_intraday_custody_evidence",
]
