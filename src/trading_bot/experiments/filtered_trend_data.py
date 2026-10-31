"""Source-only multi-asset research data contract for filtered-trend work.

The price basis records Alpaca's ``adjustment=all`` price-series semantics:
split price/volume, cash-dividend price, and spin-off price adjustments. It does
not claim reinvested total return. Acquisition is possible only through an
injected transport; this module contains no network client or credential path.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Context, Decimal, InvalidOperation, localcontext
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlencode
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)

if TYPE_CHECKING:
    from trading_bot.market_data.alpaca_http import AlpacaHistoricalBarsRequest

SCHEMA = "filtered-trend-multi-asset-dataset/v1"
IDENTITY_NAMESPACE = UUID("5d23cbb5-0e98-52f2-b3df-967a34a27941")
IDENTITY_VERSION = "filtered-trend-multi-asset-data-identity/v1"
PRICE_BASIS = "ALPACA_ALL_ADJUSTED_PRICE_V1"
PROVIDER_NAME = "Alpaca Market Data historical stock bars"
PROVIDER_ENDPOINT = "GET /v2/stocks/bars"
ADJUSTMENT = "all"
ADJUSTMENT_SEMANTICS = "SPLIT_PRICE_VOLUME|CASH_DIVIDEND_PRICE|SPIN_OFF_PRICE"
TIMEFRAME = "1Day"
FEED = "sip"
CURRENCY = "USD"
ASOF = "-"
SORT = "asc"
UNIVERSE: tuple[str, ...] = ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "PDBC")
DATA_START = datetime(2016, 1, 1, tzinfo=UTC)
DATA_END_EXCLUSIVE = datetime(2024, 1, 1, tzinfo=UTC)
ALPACA_END_INCLUSIVE = datetime(2023, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
MAX_DATASET_BYTES = 20_000_000
MAX_PROVIDER_PAGE_BYTES = 4 * 1024 * 1024
MAX_PAGES_PER_SYMBOL = 10_000
MAX_PAGE_TOKEN_LENGTH = 4096
MAX_DECIMAL_TEXT_LENGTH = 100
MAX_VOLUME = (1 << 63) - 1

_NEW_YORK = ZoneInfo("America/New_York")
_DATA_START_DATE = date(2016, 1, 1)
_DATA_END_DATE = date(2024, 1, 1)
_MINIMUM_PRE_2019_BARS = 253
_FIXED_DECIMAL_CONTEXT = Context(prec=50)
_PROVIDER_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_ALPACA_PUBLIC_HEADERS = (("Accept", "application/json"),)
_DATASET_FIELDS = frozenset({"schema", "identity", "price_basis", "datasets"})
_SYMBOL_DATASET_FIELDS = frozenset({"symbol", "bars", "provider_provenance"})
_BAR_FIELDS = frozenset(
    {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
)
_PROVENANCE_FIELDS = frozenset(
    {
        "provider",
        "endpoint",
        "timeframe",
        "feed",
        "currency",
        "asof",
        "sort",
        "adjustment",
        "adjustment_semantics",
        "request_start",
        "request_end_exclusive",
    }
)


class FilteredTrendDataError(ValueError):
    """Invalid, incomplete, or noncanonical filtered-trend data."""


@lru_cache(maxsize=1)
def _expected_session_dates() -> tuple[date, ...]:
    authority = published_historical_session_authority()
    sessions = tuple(
        session
        for session in authority.sessions
        if _DATA_START_DATE <= session < _DATA_END_DATE
    )
    pre_2019 = sum(session < date(2019, 1, 1) for session in sessions)
    if pre_2019 < _MINIMUM_PRE_2019_BARS:
        raise FilteredTrendDataError(
            "published session authority lacks required pre-2019 warmup"
        )
    return sessions


def _canonical_decimal(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise FilteredTrendDataError("bar prices must be finite positive Decimals")
    decimal_value = value.as_tuple()
    if (
        len(decimal_value.digits) > MAX_DECIMAL_TEXT_LENGTH
        or abs(decimal_value.exponent) > MAX_DECIMAL_TEXT_LENGTH
    ):
        raise FilteredTrendDataError("bar price exceeds canonical text bound")
    with localcontext(_FIXED_DECIMAL_CONTEXT):
        rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if len(rendered) > MAX_DECIMAL_TEXT_LENGTH:
        raise FilteredTrendDataError("bar price exceeds canonical text bound")
    return rendered


def _parse_decimal(value: object) -> Decimal:
    if type(value) is not str or len(value) > MAX_DECIMAL_TEXT_LENGTH:
        raise FilteredTrendDataError("canonical decimal text required")
    try:
        parsed = Decimal(value)
        if _canonical_decimal(parsed) != value:
            raise FilteredTrendDataError("noncanonical bar price")
        return parsed
    except (InvalidOperation, ArithmeticError):
        raise FilteredTrendDataError("invalid bar price") from None


def _timestamp_text(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None:
        raise FilteredTrendDataError("aware bar timestamp required")
    normalized = value.astimezone(UTC)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise FilteredTrendDataError("UTC Z timestamp required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise FilteredTrendDataError("invalid bar timestamp") from None
    if _timestamp_text(parsed) != value:
        raise FilteredTrendDataError("noncanonical bar timestamp")
    return parsed


def _json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise FilteredTrendDataError("dataset is not canonical JSON data") from None


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FilteredTrendDataError("duplicate JSON field")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> None:
    raise FilteredTrendDataError("non-finite JSON number rejected")


def _require_fields(value: object, expected: frozenset[str], label: str) -> Mapping:
    if type(value) is not dict or set(value) != expected:
        raise FilteredTrendDataError(f"{label} fields do not match the schema")
    return value


def _identity_material(dataset_rows: tuple[SymbolDataset, ...]) -> list[object]:
    material: list[object] = [IDENTITY_VERSION, PRICE_BASIS]
    for item in dataset_rows:
        provenance = item.provider_provenance.to_dict()
        material.append(
            [
                item.symbol,
                [[key, provenance[key]] for key in sorted(provenance)],
                [
                    [
                        bar.symbol.value,
                        _timestamp_text(bar.timestamp),
                        _canonical_decimal(bar.open),
                        _canonical_decimal(bar.high),
                        _canonical_decimal(bar.low),
                        _canonical_decimal(bar.close),
                        bar.volume,
                    ]
                    for bar in item.bars
                ],
            ]
        )
    return material


def _derive_identity(dataset_rows: tuple[SymbolDataset, ...]) -> str:
    material = _flatten_identity(_identity_material(dataset_rows))
    name = "".join(f"{len(part.encode('utf-8'))}:{part}" for part in material)
    return str(uuid5(IDENTITY_NAMESPACE, name))


def _flatten_identity(value: object) -> tuple[str, ...]:
    if type(value) is list:
        return (
            "sequence",
            str(len(value)),
            *(part for item in value for part in _flatten_identity(item)),
        )
    if type(value) is str:
        return ("string", value)
    if type(value) is int:
        return ("integer", str(value))
    raise FilteredTrendDataError("unsupported semantic identity value")


@dataclass(frozen=True, slots=True)
class ProviderProvenance:
    """Fixed source request and documented price-adjustment semantics."""

    provider: str = PROVIDER_NAME
    endpoint: str = PROVIDER_ENDPOINT
    timeframe: str = TIMEFRAME
    feed: str = FEED
    currency: str = CURRENCY
    asof: str = ASOF
    sort: str = SORT
    adjustment: str = ADJUSTMENT
    adjustment_semantics: str = ADJUSTMENT_SEMANTICS
    request_start: str = "2016-01-01T00:00:00Z"
    request_end_exclusive: str = "2024-01-01T00:00:00Z"

    def __post_init__(self) -> None:
        if self.to_dict() != {
            "provider": PROVIDER_NAME,
            "endpoint": PROVIDER_ENDPOINT,
            "timeframe": TIMEFRAME,
            "feed": FEED,
            "currency": CURRENCY,
            "asof": ASOF,
            "sort": SORT,
            "adjustment": ADJUSTMENT,
            "adjustment_semantics": ADJUSTMENT_SEMANTICS,
            "request_start": "2016-01-01T00:00:00Z",
            "request_end_exclusive": "2024-01-01T00:00:00Z",
        }:
            raise FilteredTrendDataError("provider price-basis provenance is frozen")

    def to_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "timeframe": self.timeframe,
            "feed": self.feed,
            "currency": self.currency,
            "asof": self.asof,
            "sort": self.sort,
            "adjustment": self.adjustment,
            "adjustment_semantics": self.adjustment_semantics,
            "request_start": self.request_start,
            "request_end_exclusive": self.request_end_exclusive,
        }

    @classmethod
    def from_dict(cls, value: object) -> ProviderProvenance:
        root = _require_fields(value, _PROVENANCE_FIELDS, "provider provenance")
        if any(type(item) is not str for item in root.values()):
            raise FilteredTrendDataError("provider provenance values must be strings")
        return cls(**root)


def _validate_symbol_bars(symbol: str, bars: tuple[Bar, ...]) -> None:
    if type(symbol) is not str or symbol not in UNIVERSE:
        raise FilteredTrendDataError("symbol is outside the fixed research universe")
    if not bars:
        raise FilteredTrendDataError(f"{symbol} history is empty")
    expected_sessions = _expected_session_dates()
    expected_set = set(expected_sessions)
    observed_dates: list[date] = []
    previous_timestamp: datetime | None = None
    symbol_value = Symbol(symbol)
    for bar in bars:
        if type(bar) is not Bar or bar.symbol != symbol_value:
            raise FilteredTrendDataError("bars must match their symbol dataset")
        if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
            raise FilteredTrendDataError(
                "bar timestamps must be strictly increasing and unique"
            )
        previous_timestamp = bar.timestamp
        local_timestamp = bar.timestamp.astimezone(_NEW_YORK)
        if local_timestamp.timetz().replace(tzinfo=None) != time.min:
            raise FilteredTrendDataError(
                "daily bars must be timestamped at New York local midnight"
            )
        session_date = local_timestamp.date()
        if not _DATA_START_DATE <= session_date < _DATA_END_DATE:
            raise FilteredTrendDataError("bar date is outside [2016-01-01, 2024-01-01)")
        if session_date not in expected_set:
            raise FilteredTrendDataError(
                "bar date is absent from published NYSE sessions"
            )
        observed_dates.append(session_date)
        for price in (bar.open, bar.high, bar.low, bar.close):
            _canonical_decimal(price)
        if type(bar.volume) is not int or not 0 <= bar.volume <= MAX_VOLUME:
            raise FilteredTrendDataError("bar volume is outside the supported range")
    if tuple(observed_dates) != expected_sessions:
        raise FilteredTrendDataError(
            f"{symbol} history does not exactly cover the published 2016-2023 sessions"
        )
    if sum(session < date(2019, 1, 1) for session in observed_dates) < (
        _MINIMUM_PRE_2019_BARS
    ):
        raise FilteredTrendDataError(f"{symbol} lacks required pre-2019 warmup")


@dataclass(frozen=True, slots=True)
class SymbolDataset:
    """One ordered symbol series and its fixed provider provenance."""

    symbol: str
    bars: tuple[Bar, ...]
    provider_provenance: ProviderProvenance = field(default_factory=ProviderProvenance)

    def __post_init__(self) -> None:
        if type(self.bars) is not tuple:
            try:
                object.__setattr__(self, "bars", tuple(self.bars))
            except TypeError:
                raise FilteredTrendDataError("bars must be iterable") from None
        if type(self.provider_provenance) is not ProviderProvenance:
            raise FilteredTrendDataError("provider provenance has the wrong type")
        _validate_symbol_bars(self.symbol, self.bars)

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "bars": [_bar_to_dict(bar) for bar in self.bars],
            "provider_provenance": self.provider_provenance.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class MultiAssetDataset:
    """Immutable fixed-universe 2016-2023 adjusted-price data."""

    datasets: tuple[SymbolDataset, ...]
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.datasets) is not tuple:
            try:
                object.__setattr__(self, "datasets", tuple(self.datasets))
            except TypeError:
                raise FilteredTrendDataError("datasets must be iterable") from None
        if (
            len(self.datasets) != len(UNIVERSE)
            or tuple(
                item.symbol if type(item) is SymbolDataset else None
                for item in self.datasets
            )
            != UNIVERSE
        ):
            raise FilteredTrendDataError(
                "datasets must contain the exact fixed universe in declared order"
            )
        provenance = tuple(item.provider_provenance for item in self.datasets)
        if any(item != provenance[0] for item in provenance[1:]):
            raise FilteredTrendDataError("all symbols must use identical provenance")
        object.__setattr__(self, "identity", _derive_identity(self.datasets))

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(item.symbol for item in self.datasets)

    @property
    def bars_by_symbol(self) -> Mapping[str, tuple[Bar, ...]]:
        from types import MappingProxyType

        return MappingProxyType({item.symbol: item.bars for item in self.datasets})

    @property
    def price_basis(self) -> str:
        return PRICE_BASIS

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "identity": self.identity,
            "price_basis": PRICE_BASIS,
            "datasets": [item.to_dict() for item in self.datasets],
        }

    def to_json(self) -> str:
        return _json_bytes(self.to_dict()).decode("utf-8")

    @classmethod
    def from_dict(cls, value: object) -> MultiAssetDataset:
        root = _require_fields(value, _DATASET_FIELDS, "dataset")
        if root["schema"] != SCHEMA or root["price_basis"] != PRICE_BASIS:
            raise FilteredTrendDataError("dataset schema or price basis is unsupported")
        raw_datasets = root["datasets"]
        if type(raw_datasets) is not list:
            raise FilteredTrendDataError("datasets must be a JSON array")
        datasets = tuple(_symbol_dataset_from_dict(item) for item in raw_datasets)
        dataset = cls(datasets)
        if type(root["identity"]) is not str or root["identity"] != dataset.identity:
            raise FilteredTrendDataError("dataset identity is inconsistent")
        return dataset

    @classmethod
    def from_json(cls, value: str | bytes) -> MultiAssetDataset:
        if type(value) is str:
            body = value.encode("utf-8")
        elif type(value) is bytes:
            body = value
        else:
            raise FilteredTrendDataError("dataset JSON must be text or bytes")
        if not body or len(body) > MAX_DATASET_BYTES:
            raise FilteredTrendDataError("dataset JSON size is invalid")
        try:
            parsed = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_object_pairs,
                parse_constant=_reject_json_constant,
            )
        except FilteredTrendDataError:
            raise
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise FilteredTrendDataError("malformed dataset JSON") from None
        if type(parsed) is not dict or _json_bytes(parsed) != body:
            raise FilteredTrendDataError("canonical dataset JSON is required")
        return cls.from_dict(parsed)


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


def _symbol_dataset_from_dict(value: object) -> SymbolDataset:
    root = _require_fields(value, _SYMBOL_DATASET_FIELDS, "symbol dataset")
    symbol = root["symbol"]
    raw_bars = root["bars"]
    if type(symbol) is not str or type(raw_bars) is not list:
        raise FilteredTrendDataError("symbol or bars field has the wrong type")
    provenance = ProviderProvenance.from_dict(root["provider_provenance"])
    bars: list[Bar] = []
    for raw_bar in raw_bars:
        item = _require_fields(raw_bar, _BAR_FIELDS, "bar")
        if type(item["symbol"]) is not str or type(item["volume"]) is not int:
            raise FilteredTrendDataError("bar symbol or volume has the wrong type")
        try:
            bar = Bar(
                Symbol(item["symbol"]),
                _parse_timestamp(item["timestamp"]),
                _parse_decimal(item["open"]),
                _parse_decimal(item["high"]),
                _parse_decimal(item["low"]),
                _parse_decimal(item["close"]),
                item["volume"],
            )
        except (TypeError, ValueError):
            raise FilteredTrendDataError("bar fields are invalid") from None
        bars.append(bar)
    return SymbolDataset(symbol, tuple(bars), provenance)


@dataclass(frozen=True, slots=True)
class HistoricalBarsRequest:
    """Fixed provider-neutral request; ``end_exclusive`` remains half-open."""

    symbol: str
    page_token: str | None = None
    start: datetime = DATA_START
    end_exclusive: datetime = DATA_END_EXCLUSIVE
    timeframe: str = TIMEFRAME
    adjustment: str = ADJUSTMENT
    feed: str = FEED
    currency: str = CURRENCY
    asof: str = ASOF
    sort: str = SORT

    def __post_init__(self) -> None:
        if type(self.symbol) is not str or self.symbol not in UNIVERSE:
            raise FilteredTrendDataError("request symbol is outside the fixed universe")
        if self.page_token is not None and (
            type(self.page_token) is not str
            or not self.page_token
            or len(self.page_token) > MAX_PAGE_TOKEN_LENGTH
        ):
            raise FilteredTrendDataError("pagination token is invalid")
        if (self.start, self.end_exclusive) != (DATA_START, DATA_END_EXCLUSIVE):
            raise FilteredTrendDataError("request bounds are frozen")
        if (
            self.timeframe,
            self.adjustment,
            self.feed,
            self.currency,
            self.asof,
            self.sort,
        ) != (
            TIMEFRAME,
            ADJUSTMENT,
            FEED,
            CURRENCY,
            ASOF,
            SORT,
        ):
            raise FilteredTrendDataError("request semantics are frozen")


def _request_timestamp(value: datetime) -> str:
    normalized = value.astimezone(UTC)
    return normalized.isoformat(timespec="auto").replace("+00:00", "Z")


def build_alpaca_request(
    request: HistoricalBarsRequest,
) -> AlpacaHistoricalBarsRequest:
    """Build the exact unauthenticated public request for one symbol page."""

    if type(request) is not HistoricalBarsRequest:
        raise FilteredTrendDataError("request must be a HistoricalBarsRequest")
    import trading_bot.market_data.alpaca_http as alpaca_http

    parameters = [
        ("symbols", request.symbol),
        ("timeframe", TIMEFRAME),
        ("start", _request_timestamp(DATA_START)),
        ("end", _request_timestamp(ALPACA_END_INCLUSIVE)),
        ("limit", "10000"),
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
        public_headers=_ALPACA_PUBLIC_HEADERS,
    )


def _provider_timestamp(value: object) -> datetime:
    if type(value) is not str or _PROVIDER_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise FilteredTrendDataError("provider bar timestamp shape is invalid")
    try:
        timestamp = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise FilteredTrendDataError("provider bar timestamp is invalid") from None
    if timestamp.astimezone(_NEW_YORK).time() != time.min:
        raise FilteredTrendDataError("provider daily bar is not at New York midnight")
    if not DATA_START <= timestamp < DATA_END_EXCLUSIVE:
        raise FilteredTrendDataError("provider bar is outside the requested interval")
    return timestamp


def _provider_price(value: object) -> Decimal:
    if type(value) is Decimal:
        price = value
    elif type(value) is int:
        price = Decimal(value)
    else:
        raise FilteredTrendDataError("provider prices must be JSON numbers")
    _canonical_decimal(price)
    return price


def parse_alpaca_page(
    payload: bytes, request: HistoricalBarsRequest
) -> HistoricalBarsPage:
    """Strictly parse one official multi-symbol historical-bars JSON page."""

    if type(request) is not HistoricalBarsRequest:
        raise FilteredTrendDataError("request must be a HistoricalBarsRequest")
    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > MAX_PROVIDER_PAGE_BYTES
    ):
        raise FilteredTrendDataError("provider response size or type is invalid")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise FilteredTrendDataError("provider response must not contain a UTF-8 BOM")
    try:
        root = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object_pairs,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_json_constant,
        )
    except FilteredTrendDataError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise FilteredTrendDataError("provider response is not strict JSON") from None
    if type(root) is not dict or set(root) != {"bars", "next_page_token"}:
        raise FilteredTrendDataError("provider response fields do not match the schema")
    token = root["next_page_token"]
    if token is not None and (
        type(token) is not str or not token or len(token) > MAX_PAGE_TOKEN_LENGTH
    ):
        raise FilteredTrendDataError("provider next-page token is invalid")
    raw_bars_by_symbol = root["bars"]
    if (
        type(raw_bars_by_symbol) is not dict
        or set(raw_bars_by_symbol) != {request.symbol}
        or type(raw_bars_by_symbol[request.symbol]) is not list
    ):
        raise FilteredTrendDataError("provider response contains an unexpected symbol")

    bars: list[Bar] = []
    previous_timestamp: datetime | None = None
    required = frozenset({"t", "o", "h", "l", "c", "v"})
    allowed = required | {"n", "vw"}
    for raw_bar in raw_bars_by_symbol[request.symbol]:
        if (
            type(raw_bar) is not dict
            or not required <= set(raw_bar)
            or not set(raw_bar) <= allowed
        ):
            raise FilteredTrendDataError("provider bar fields do not match the schema")
        timestamp = _provider_timestamp(raw_bar["t"])
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise FilteredTrendDataError(
                "provider page bars must be strictly chronological"
            )
        previous_timestamp = timestamp
        volume = raw_bar["v"]
        if type(volume) is not int or not 0 <= volume <= MAX_VOLUME:
            raise FilteredTrendDataError("provider bar volume is invalid")
        if "n" in raw_bar and (
            type(raw_bar["n"]) is not int or not 0 <= raw_bar["n"] <= MAX_VOLUME
        ):
            raise FilteredTrendDataError("provider trade count is invalid")
        if "vw" in raw_bar:
            _provider_price(raw_bar["vw"])
        try:
            bars.append(
                Bar(
                    Symbol(request.symbol),
                    timestamp,
                    _provider_price(raw_bar["o"]),
                    _provider_price(raw_bar["h"]),
                    _provider_price(raw_bar["l"]),
                    _provider_price(raw_bar["c"]),
                    volume,
                )
            )
        except (TypeError, ValueError):
            raise FilteredTrendDataError("provider OHLCV values are invalid") from None
    return HistoricalBarsPage(tuple(bars), token)


@dataclass(frozen=True, slots=True)
class HistoricalBarsPage:
    """One already decoded page returned by an injected transport."""

    bars: tuple[Bar, ...]
    next_page_token: str | None = None

    def __post_init__(self) -> None:
        if type(self.bars) is not tuple:
            try:
                object.__setattr__(self, "bars", tuple(self.bars))
            except TypeError:
                raise FilteredTrendDataError("page bars must be iterable") from None
        if any(type(bar) is not Bar for bar in self.bars):
            raise FilteredTrendDataError("provider page contains a non-Bar value")
        token = self.next_page_token
        if token is not None and (
            type(token) is not str or not token or len(token) > MAX_PAGE_TOKEN_LENGTH
        ):
            raise FilteredTrendDataError("next page token is invalid")


class HistoricalBarsTransport(Protocol):
    """Injected source only; no default implementation or credential access."""

    def fetch_page(self, request: HistoricalBarsRequest) -> HistoricalBarsPage: ...


@dataclass(frozen=True, slots=True)
class AlpacaPageTransport:
    """Decode Alpaca pages from a caller-supplied sender, without networking."""

    send: Callable[[AlpacaHistoricalBarsRequest], bytes]

    def __post_init__(self) -> None:
        if not callable(self.send):
            raise FilteredTrendDataError("sender must be callable")

    def fetch_page(self, request: HistoricalBarsRequest) -> HistoricalBarsPage:
        if type(request) is not HistoricalBarsRequest:
            raise FilteredTrendDataError("request must be a HistoricalBarsRequest")
        return parse_alpaca_page(self.send(build_alpaca_request(request)), request)


def acquire_dataset(transport: HistoricalBarsTransport) -> MultiAssetDataset:
    """Acquire fixed-range pages through a caller-supplied transport.

    The Alpaca request builder maps the contract to an inclusive API end that
    remains strictly before ``2024-01-01``; the response parser rejects any
    returned bar outside the half-open interval. No network call is made by
    this module itself.
    """

    fetch_page = getattr(transport, "fetch_page", None)
    if not callable(fetch_page):
        raise FilteredTrendDataError("injected transport must expose fetch_page")
    provenance = ProviderProvenance()
    datasets: list[SymbolDataset] = []
    for symbol in UNIVERSE:
        symbol_bars: list[Bar] = []
        token: str | None = None
        seen_tokens: set[str | None] = set()
        page_count = 0
        last_timestamp: datetime | None = None
        while True:
            if token in seen_tokens:
                raise FilteredTrendDataError("provider pagination token repeated")
            seen_tokens.add(token)
            page_count += 1
            if page_count > MAX_PAGES_PER_SYMBOL:
                raise FilteredTrendDataError("provider pagination exceeded its bound")
            page = fetch_page(HistoricalBarsRequest(symbol=symbol, page_token=token))
            if type(page) is not HistoricalBarsPage:
                raise FilteredTrendDataError("transport must return HistoricalBarsPage")
            for bar in page.bars:
                if bar.symbol.value != symbol:
                    raise FilteredTrendDataError(
                        "provider page returned an unexpected symbol"
                    )
                if not DATA_START <= bar.timestamp < DATA_END_EXCLUSIVE:
                    raise FilteredTrendDataError(
                        "provider page returned an out-of-range bar"
                    )
                if last_timestamp is not None and bar.timestamp <= last_timestamp:
                    raise FilteredTrendDataError(
                        "provider pages are not strictly chronological"
                    )
                last_timestamp = bar.timestamp
                symbol_bars.append(bar)
            token = page.next_page_token
            if token is None:
                break
        datasets.append(SymbolDataset(symbol, tuple(symbol_bars), provenance))
    return MultiAssetDataset(tuple(datasets))


def write_dataset(path: Path, dataset: MultiAssetDataset) -> None:
    """Write a canonical dataset once to a caller-chosen external path."""

    if not isinstance(path, Path) or type(dataset) is not MultiAssetDataset:
        raise FilteredTrendDataError("Path and MultiAssetDataset values are required")
    if not path.parent.is_dir():
        raise FilteredTrendDataError("dataset parent directory must already exist")
    if path.exists() or path.is_symlink():
        raise FilteredTrendDataError("dataset destination already exists")
    body = dataset.to_json().encode("utf-8")
    if len(body) > MAX_DATASET_BYTES:
        raise FilteredTrendDataError("dataset exceeds the bounded artifact size")
    try:
        with path.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise FilteredTrendDataError("dataset destination already exists") from None
    with path.open("rb") as handle:
        readback = handle.read(MAX_DATASET_BYTES + 1)
    if readback != body:
        raise FilteredTrendDataError("dataset readback mismatch")


def read_dataset(path: Path) -> MultiAssetDataset:
    """Read one bounded, canonical, strictly validated dataset artifact."""

    if not isinstance(path, Path):
        raise FilteredTrendDataError("Path value is required")
    try:
        with path.open("rb") as handle:
            body = handle.read(MAX_DATASET_BYTES + 1)
    except OSError:
        raise FilteredTrendDataError("dataset file could not be read") from None
    if len(body) > MAX_DATASET_BYTES:
        raise FilteredTrendDataError("dataset exceeds the bounded artifact size")
    return MultiAssetDataset.from_json(body)
