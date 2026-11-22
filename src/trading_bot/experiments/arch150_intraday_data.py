"""Architecture 150 one-minute data contracts and deterministic custody models.

This module is transport-neutral. It defines the frozen SPY/QQQ 2016-2023
request, strict page decoding, raw-page accounting, XNYS minute-slot
qualification, and deterministic data/partition/custody identities. It never
reads credentials, opens a socket, writes files, or evaluates a strategy.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Protocol
from urllib.parse import urlencode
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.experiments.arch148_intraday import (
    HistoricalIntradaySessionAuthority,
)
from trading_bot.experiments.arch150_intraday_ai import (
    BarResolution,
    IntradayBar,
    validate_universe_minute_bars,
)
from trading_bot.experiments.historical_research_custody import (
    canonical_json_bytes,
)

ARCH150_DATA_SCHEMA = "arch150-intraday-custody-dataset/v1"
ARCH150_PARTITION_SCHEMA = "arch150-intraday-data-partition/v1"
ARCH150_CUSTODY_SCHEMA = "arch150-intraday-data-custody-evidence/v1"
ARCH150_RAW_PAGE_SCHEMA = "arch150-intraday-raw-page/v1"
ARCH150_REQUEST_SCHEMA = "arch150-intraday-provider-request/v1"
ARCH150_SESSION_SCHEMA = "arch150-intraday-xnys-session-projection/v1"
ARCH150_DATA_IDENTITY_VERSION = "arch150-intraday-data-identity/v1"
ARCH150_CUSTODY_IDENTITY_VERSION = "arch150-intraday-custody-identity/v1"
ARCH150_REQUEST_IDENTITY_VERSION = "arch150-intraday-request-identity/v1"

INITIAL_UNIVERSE: tuple[str, ...] = ("SPY", "QQQ")
TIMEFRAME = "1Min"
REQUEST_START = datetime(2016, 1, 1, tzinfo=UTC)
REQUEST_END_INCLUSIVE = datetime(2023, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
DATA_START = date(2016, 1, 1)
DATA_END_EXCLUSIVE = date(2024, 1, 1)
DISCOVERY_START = date(2016, 1, 1)
DISCOVERY_END = date(2021, 1, 1)
VALIDATION_START = date(2021, 1, 1)
VALIDATION_END = date(2024, 1, 1)
PROVIDER_NAME = "Alpaca Market Data historical stock bars"
PROVIDER_ENDPOINT = "GET /v2/stocks/bars"
ADJUSTMENT = "all"
ADJUSTMENT_SEMANTICS = "SPLIT_PRICE_VOLUME|CASH_DIVIDEND_PRICE|SPIN_OFF_PRICE"
FEED = "sip"
CURRENCY = "USD"
ASOF = "-"
SORT = "asc"
LIMIT = 10_000
PRICE_BASIS = "ALPACA_ALL_ADJUSTED_1MINUTE_PRICE_V1"
MAX_PROVIDER_PAGE_BYTES = 4 * 1024 * 1024
MAX_PAGE_TOKEN_LENGTH = 4096
MAX_PAGES_PER_SYMBOL = 4096
MAX_PROVIDER_REQUEST_ATTEMPTS = 8192
MAX_VOLUME = (1 << 63) - 1
SCHEDULE_TIMEZONE = "America/New_York"
MINUTE = timedelta(minutes=1)

_DATA_NAMESPACE = UUID("88ab16a5-a606-5e61-9e02-2cf740b546ac")
_PARTITION_NAMESPACE = UUID("65ef0473-6840-5aa9-887e-c5ba151810d3")
_CUSTODY_NAMESPACE = UUID("f1ad3b13-00a6-5e9b-97cb-8b240fd4f8d2")
_REQUEST_NAMESPACE = UUID("81ab2fb8-9e1d-5527-8f56-4d1efdd1e8dc")
_SESSION_NAMESPACE = UUID("98e4be6a-29c0-5ab5-a42d-ddebc31b5bcf")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_NEW_YORK = ZoneInfo(SCHEDULE_TIMEZONE)


class Arch150DataError(ValueError):
    """Sanitized data-contract failure with no provider-body text."""

    def __init__(self, code: str, *, malformed_bar_count: int = 0) -> None:
        self.code = code
        self.malformed_bar_count = malformed_bar_count
        super().__init__(code)


class DatasetClassification(StrEnum):
    READY = "READY_FOR_ARCH150_DATA_CUSTODY_REVIEW"
    BLOCKED = "BLOCKED"


def _timestamp_text(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _digest(value: object) -> None:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise Arch150DataError("INVALID_SHA256")


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise Arch150DataError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> None:
    raise Arch150DataError("NONFINITE_JSON_NUMBER")


def _provider_timestamp(value: object) -> datetime:
    if type(value) is not str or _TIMESTAMP.fullmatch(value) is None:
        raise Arch150DataError("MALFORMED_PROVIDER_TIMESTAMP", malformed_bar_count=1)
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00").astimezone(UTC)
    except ValueError:
        raise Arch150DataError(
            "MALFORMED_PROVIDER_TIMESTAMP", malformed_bar_count=1
        ) from None
    if not REQUEST_START <= result < datetime(2024, 1, 1, tzinfo=UTC):
        raise Arch150DataError("PROVIDER_TIMESTAMP_OUT_OF_RANGE")
    return result


def _provider_decimal(value: object) -> Decimal:
    if type(value) not in (int, Decimal) or type(value) is bool:
        raise Arch150DataError("MALFORMED_PROVIDER_PRICE", malformed_bar_count=1)
    result = Decimal(value)
    if not result.is_finite() or result <= 0:
        raise Arch150DataError("MALFORMED_PROVIDER_PRICE", malformed_bar_count=1)
    return result


@dataclass(frozen=True, slots=True)
class Arch150HistoricalRequest:
    """Exact one-symbol provider request, including a hashed cursor identity."""

    symbol: str
    page_token: str | None = None

    def __post_init__(self) -> None:
        if type(self.symbol) is not str or self.symbol not in INITIAL_UNIVERSE:
            raise Arch150DataError("UNSUPPORTED_SYMBOL")
        if self.page_token is not None and (
            type(self.page_token) is not str
            or not self.page_token
            or len(self.page_token) > MAX_PAGE_TOKEN_LENGTH
        ):
            raise Arch150DataError("INVALID_PAGE_TOKEN")

    @property
    def descriptor(self) -> dict[str, object]:
        return {
            "schema": ARCH150_REQUEST_SCHEMA,
            "provider": PROVIDER_NAME,
            "endpoint": PROVIDER_ENDPOINT,
            "symbol": self.symbol,
            "timeframe": TIMEFRAME,
            "start": "2016-01-01T00:00:00Z",
            "end_inclusive": "2023-12-31T23:59:59.999999Z",
            "adjustment": ADJUSTMENT,
            "feed": FEED,
            "currency": CURRENCY,
            "asof": ASOF,
            "sort": SORT,
            "limit": LIMIT,
            "pagination": "next_page_token_until_null",
            "page_token_sha256": (
                sha256(self.page_token.encode("utf-8")).hexdigest()
                if self.page_token is not None
                else None
            ),
        }

    @property
    def digest(self) -> str:
        return sha256(canonical_json_bytes(self.descriptor)).hexdigest()

    @property
    def identity(self) -> UUID:
        material = {
            "version": ARCH150_REQUEST_IDENTITY_VERSION,
            "descriptor": self.descriptor,
        }
        return uuid5(_REQUEST_NAMESPACE, canonical_json_bytes(material).decode("utf-8"))


def build_alpaca_request(request: Arch150HistoricalRequest):
    """Build the existing fixed-host HTTPS request without adding credentials."""

    if type(request) is not Arch150HistoricalRequest:
        raise Arch150DataError("INVALID_REQUEST_TYPE")
    from trading_bot.market_data import alpaca_http

    parameters = [
        ("symbols", request.symbol),
        ("timeframe", TIMEFRAME),
        ("start", "2016-01-01T00:00:00Z"),
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


@dataclass(frozen=True, slots=True)
class ParsedProviderPage:
    symbol: str
    bars: tuple[IntradayBar, ...]
    next_page_token: str | None
    raw_page_sha256: str
    raw_page_byte_length: int


def parse_alpaca_page(
    payload: bytes, request: Arch150HistoricalRequest
) -> ParsedProviderPage:
    """Strictly parse one response after its bytes have been preserved."""

    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > MAX_PROVIDER_PAGE_BYTES
        or payload.startswith(b"\xef\xbb\xbf")
    ):
        raise Arch150DataError("MALFORMED_PROVIDER_BODY")
    try:
        root = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_json_constant,
        )
    except Arch150DataError:
        raise
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise Arch150DataError("MALFORMED_PROVIDER_BODY") from None
    if type(root) is not dict or set(root) not in (
        {"bars", "next_page_token"},
        {"bars", "next_page_token", "currency"},
    ):
        raise Arch150DataError("MALFORMED_PROVIDER_ROOT")
    if "currency" in root and root["currency"] != CURRENCY:
        raise Arch150DataError("PROVIDER_CURRENCY_MISMATCH")
    token = root["next_page_token"]
    if token is not None and (
        type(token) is not str or not token or len(token) > MAX_PAGE_TOKEN_LENGTH
    ):
        raise Arch150DataError("INVALID_PAGE_TOKEN")
    by_symbol = root["bars"]
    if type(by_symbol) is not dict or set(by_symbol) != {request.symbol}:
        raise Arch150DataError("UNEXPECTED_PROVIDER_SYMBOL")
    raw_bars = by_symbol[request.symbol]
    if type(raw_bars) is not list or len(raw_bars) > LIMIT:
        raise Arch150DataError("PROVIDER_PAGE_LIMIT_EXCEEDED")
    bars: list[IntradayBar] = []
    previous: datetime | None = None
    for raw in raw_bars:
        if (
            type(raw) is not dict
            or not {"t", "o", "h", "l", "c", "v"} <= set(raw)
            or not set(raw) <= {"t", "o", "h", "l", "c", "v", "n", "vw"}
        ):
            raise Arch150DataError("MALFORMED_PROVIDER_BAR", malformed_bar_count=1)
        stamp = _provider_timestamp(raw["t"])
        if previous is not None and stamp < previous:
            raise Arch150DataError("PROVIDER_PAGE_ORDER_INVALID")
        previous = stamp
        volume = raw["v"]
        if type(volume) is not int or not 0 <= volume <= MAX_VOLUME:
            raise Arch150DataError("MALFORMED_PROVIDER_VOLUME", malformed_bar_count=1)
        for optional in ("n",):
            if optional in raw and (
                type(raw[optional]) is not int or not 0 <= raw[optional] <= MAX_VOLUME
            ):
                raise Arch150DataError("MALFORMED_PROVIDER_BAR", malformed_bar_count=1)
        if "vw" in raw:
            _provider_decimal(raw["vw"])
        try:
            bars.append(
                IntradayBar(
                    request.symbol,
                    stamp,
                    _provider_decimal(raw["o"]),
                    _provider_decimal(raw["h"]),
                    _provider_decimal(raw["l"]),
                    _provider_decimal(raw["c"]),
                    volume,
                    BarResolution.ONE_MINUTE,
                )
            )
        except Arch150DataError:
            raise
        except (TypeError, ValueError):
            raise Arch150DataError(
                "MALFORMED_PROVIDER_BAR", malformed_bar_count=1
            ) from None
    return ParsedProviderPage(
        request.symbol,
        tuple(bars),
        token,
        sha256(payload).hexdigest(),
        len(payload),
    )


class RawPagePersister(Protocol):
    def __call__(self, symbol: str, ordinal: int, payload: bytes) -> None: ...


@dataclass(frozen=True, slots=True)
class RawPageCommitment:
    ordinal: int
    symbol: str
    request_digest: str
    request_descriptor_json: str
    input_token_sha256: str | None
    page_sha256: str
    byte_length: int
    next_token_sha256: str | None
    terminal_state: str

    def __post_init__(self) -> None:
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise Arch150DataError("INVALID_PAGE_ORDINAL")
        if self.symbol not in INITIAL_UNIVERSE:
            raise Arch150DataError("UNSUPPORTED_SYMBOL")
        _digest(self.request_digest)
        _digest(self.page_sha256)
        if self.input_token_sha256 is not None:
            _digest(self.input_token_sha256)
        if self.next_token_sha256 is not None:
            _digest(self.next_token_sha256)
        if type(self.byte_length) is not int or self.byte_length < 0:
            raise Arch150DataError("INVALID_RAW_PAGE_LENGTH")
        try:
            descriptor = json.loads(self.request_descriptor_json)
        except (TypeError, ValueError):
            raise Arch150DataError("INVALID_REQUEST_DESCRIPTOR") from None
        if (
            type(descriptor) is not dict
            or canonical_json_bytes(descriptor).decode("utf-8")
            != self.request_descriptor_json
            or descriptor.get("symbol") != self.symbol
            or sha256(canonical_json_bytes(descriptor)).hexdigest()
            != self.request_digest
        ):
            raise Arch150DataError("INVALID_REQUEST_DESCRIPTOR")
        if self.terminal_state not in {
            "CONTINUE",
            "NULL_TOKEN_EXHAUSTED",
            "REPEATED_TOKEN",
            "PAGE_ORDER_INVALID",
            "UNPARSED_RESPONSE_PRESERVED",
        }:
            raise Arch150DataError("INVALID_PAGE_TERMINAL_STATE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": ARCH150_RAW_PAGE_SCHEMA,
            "ordinal": self.ordinal,
            "symbol": self.symbol,
            "request_digest": self.request_digest,
            "request_descriptor": json.loads(self.request_descriptor_json),
            "input_token_sha256": self.input_token_sha256,
            "page_sha256": self.page_sha256,
            "byte_length": self.byte_length,
            "next_token_sha256": self.next_token_sha256,
            "terminal_state": self.terminal_state,
        }


@dataclass(frozen=True, slots=True)
class SymbolPageCollection:
    symbol: str
    pages: tuple[RawPageCommitment, ...]
    bars: tuple[IntradayBar, ...]
    terminal_state: str
    failure_code: str | None
    parsed_page_count: int
    raw_bar_count: int | None

    @property
    def pagination_complete(self) -> bool:
        return (
            self.terminal_state == "NULL_TOKEN_EXHAUSTED" and self.failure_code is None
        )


def collect_symbol_pages(
    symbol: str,
    fetch_raw_page: Callable[[Arch150HistoricalRequest], bytes],
    persist_raw_page: RawPagePersister,
    *,
    max_pages: int = MAX_PAGES_PER_SYMBOL,
) -> SymbolPageCollection:
    """Exhaust one stream, persisting each page before parsing it.

    A short page never ends pagination. Only a parsed null next-page token is
    terminal. Failures preserve the page that exposed them and never retry.
    """

    if symbol not in INITIAL_UNIVERSE:
        raise Arch150DataError("UNSUPPORTED_SYMBOL")
    if type(max_pages) is not int or not 1 <= max_pages <= MAX_PAGES_PER_SYMBOL:
        raise Arch150DataError("INVALID_PAGE_CEILING")
    pages: list[RawPageCommitment] = []
    bars: list[IntradayBar] = []
    seen_tokens: set[str | None] = set()
    token: str | None = None
    previous: datetime | None = None
    for ordinal in range(1, max_pages + 1):
        if token in seen_tokens:
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "REPEATED_TOKEN",
                "PAGINATION_TOKEN_LOOP",
                len(pages),
                None,
            )
        seen_tokens.add(token)
        request = Arch150HistoricalRequest(symbol, token)
        try:
            payload = fetch_raw_page(request)
        except Arch150DataError as error:
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "REQUEST_FAILED",
                error.code,
                len(pages),
                None,
            )
        except Exception:
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "REQUEST_FAILED",
                "PROVIDER_REQUEST_FAILED",
                len(pages),
                None,
            )
        if type(payload) is not bytes:
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "RESPONSE_TYPE_INVALID",
                "PROVIDER_RESPONSE_TYPE_INVALID",
                len(pages),
                None,
            )
        try:
            persist_raw_page(symbol, ordinal, payload)
        except Arch150DataError as error:
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "RAW_PERSIST_FAILED",
                error.code,
                len(pages),
                None,
            )
        except Exception:
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "RAW_PERSIST_FAILED",
                "RAW_PAGE_PERSIST_FAILED",
                len(pages),
                None,
            )
        request_json = canonical_json_bytes(request.descriptor).decode("utf-8")
        input_digest = request.descriptor["page_token_sha256"]
        page_sha = (
            sha256(payload).hexdigest()
            if type(payload) is bytes
            else sha256(b"").hexdigest()
        )
        page_length = len(payload) if type(payload) is bytes else 0
        try:
            page = parse_alpaca_page(payload, request)
        except Arch150DataError as error:
            pages.append(
                RawPageCommitment(
                    ordinal,
                    symbol,
                    request.digest,
                    request_json,
                    input_digest,
                    page_sha,
                    page_length,
                    None,
                    "UNPARSED_RESPONSE_PRESERVED",
                )
            )
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "MALFORMED_PAGE",
                error.code,
                len(pages) - 1,
                None,
            )
        next_digest = (
            sha256(page.next_page_token.encode("utf-8")).hexdigest()
            if page.next_page_token is not None
            else None
        )
        terminal = (
            "NULL_TOKEN_EXHAUSTED" if page.next_page_token is None else "CONTINUE"
        )
        for bar in page.bars:
            if bar.symbol != symbol:
                return SymbolPageCollection(
                    symbol,
                    tuple(pages),
                    tuple(bars),
                    "SYMBOL_MISMATCH",
                    "UNEXPECTED_PROVIDER_SYMBOL",
                    len(pages),
                    None,
                )
            if previous is not None and bar.timestamp < previous:
                pages.append(
                    RawPageCommitment(
                        ordinal,
                        symbol,
                        request.digest,
                        request_json,
                        input_digest,
                        page.raw_page_sha256,
                        page.raw_page_byte_length,
                        next_digest,
                        "PAGE_ORDER_INVALID",
                    )
                )
                return SymbolPageCollection(
                    symbol,
                    tuple(pages),
                    tuple(bars),
                    "PAGE_ORDER_INVALID",
                    "PROVIDER_PAGE_ORDER_INVALID",
                    len(pages),
                    None,
                )
            previous = bar.timestamp
            bars.append(bar)
        if len(page.bars) > LIMIT:
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "PAGE_LIMIT_EXCEEDED",
                "PROVIDER_PAGE_LIMIT_EXCEEDED",
                len(pages),
                None,
            )
        if page.next_page_token in seen_tokens and page.next_page_token is not None:
            terminal = "REPEATED_TOKEN"
        pages.append(
            RawPageCommitment(
                ordinal,
                symbol,
                request.digest,
                request_json,
                input_digest,
                page.raw_page_sha256,
                page.raw_page_byte_length,
                next_digest,
                terminal,
            )
        )
        if page.next_page_token is None:
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "NULL_TOKEN_EXHAUSTED",
                None,
                len(pages),
                len(bars),
            )
        if page.next_page_token in seen_tokens:
            return SymbolPageCollection(
                symbol,
                tuple(pages),
                tuple(bars),
                "REPEATED_TOKEN",
                "PAGINATION_TOKEN_LOOP",
                len(pages),
                len(bars),
            )
        token = page.next_page_token
    return SymbolPageCollection(
        symbol,
        tuple(pages),
        tuple(bars),
        "PAGE_CEILING_REACHED",
        "PAGE_CEILING_REACHED",
        len(pages),
        len(bars),
    )


def published_session_authority() -> HistoricalIntradaySessionAuthority:
    """Return the accepted XNYS authority used by the Arch150 projection."""

    return HistoricalIntradaySessionAuthority()


def _schedule_rows(
    authority: HistoricalIntradaySessionAuthority,
) -> tuple[dict[str, str], ...]:
    if type(authority) is not HistoricalIntradaySessionAuthority:
        raise Arch150DataError("UNACCEPTED_SESSION_AUTHORITY")
    from trading_bot.experiments.historical_research_custody import (
        require_accepted_historical_session_authority,
    )

    try:
        require_accepted_historical_session_authority(authority.published)
    except (TypeError, ValueError):
        raise Arch150DataError("UNACCEPTED_SESSION_AUTHORITY") from None
    rows: list[dict[str, str]] = []
    for session in authority.published.sessions:
        if not DATA_START <= session < DATA_END_EXCLUSIVE:
            continue
        schedule = authority.schedule_for(session)
        if schedule is None:
            raise Arch150DataError("PUBLISHED_SESSION_SCHEDULE_MISSING")
        rows.append(
            {
                "session_date": session.isoformat(),
                "opens_at_utc": _timestamp_text(schedule.opens_at),
                "closes_at_utc": _timestamp_text(schedule.closes_at),
            }
        )
    if not rows:
        raise Arch150DataError("PUBLISHED_SESSION_RANGE_EMPTY")
    return tuple(rows)


def session_authority_commitment(
    authority: HistoricalIntradaySessionAuthority | None = None,
) -> tuple[str, str]:
    """Commit Arch150's 2016-2023 schedule projection, not Arch148 metadata."""

    authority = authority or published_session_authority()
    rows = _schedule_rows(authority)
    material = {
        "schema": ARCH150_SESSION_SCHEMA,
        "version": "arch150-intraday-session-schedule-identity/v1",
        "upstream_xnys_identity": authority.published.identity,
        "upstream_xnys_digest": authority.published.digest,
        "timezone": SCHEDULE_TIMEZONE,
        "start": DATA_START.isoformat(),
        "end_exclusive": DATA_END_EXCLUSIVE.isoformat(),
        "resolution": TIMEFRAME,
        "sessions": list(rows),
    }
    body = canonical_json_bytes(material)
    return str(uuid5(_SESSION_NAMESPACE, body.decode("utf-8"))), sha256(
        body
    ).hexdigest()


def expected_regular_minute_slots(
    start: date = DATA_START,
    end_exclusive: date = DATA_END_EXCLUSIVE,
    authority: HistoricalIntradaySessionAuthority | None = None,
) -> Iterable[datetime]:
    """Yield exact published XNYS regular-session minute starts in a subrange."""

    if (
        type(start) is not date
        or type(end_exclusive) is not date
        or not DATA_START <= start < end_exclusive <= DATA_END_EXCLUSIVE
    ):
        raise Arch150DataError("INVALID_SESSION_SLOT_RANGE")
    authority = authority or published_session_authority()
    _schedule_rows(authority)
    for session in authority.published.sessions:
        if not start <= session < end_exclusive:
            continue
        schedule = authority.schedule_for(session)
        if schedule is None:
            raise Arch150DataError("PUBLISHED_SESSION_SCHEDULE_MISSING")
        slot = schedule.opens_at
        while slot < schedule.closes_at:
            yield slot.astimezone(UTC)
            slot += MINUTE


def normalized_csv_bytes(bars: Iterable[IntradayBar]) -> bytes:
    """Serialize Arch150 bars in deterministic symbol-then-time order."""

    materialized = tuple(bars)
    if any(type(bar) is not IntradayBar for bar in materialized):
        raise Arch150DataError("INVALID_NORMALIZED_BAR_TYPE")
    ordered = tuple(
        bar
        for symbol in INITIAL_UNIVERSE
        for bar in sorted(
            (item for item in materialized if item.symbol == symbol),
            key=lambda item: item.timestamp,
        )
    )
    rows = ["timestamp,symbol,resolution,open,high,low,close,volume\n"]
    rows.extend(
        ",".join(
            (
                _timestamp_text(bar.timestamp),
                bar.symbol,
                TIMEFRAME,
                _decimal_text(bar.open),
                _decimal_text(bar.high),
                _decimal_text(bar.low),
                _decimal_text(bar.close),
                str(bar.volume),
            )
        )
        + "\n"
        for bar in ordered
    )
    return "".join(rows).encode("utf-8")


@dataclass(frozen=True, slots=True)
class SymbolDiagnostics:
    symbol: str
    raw_page_count: int
    raw_bar_count: int | None
    raw_bar_count_known: bool
    parsed_page_count: int
    observed_regular_slot_bar_count: int
    normalized_regular_bar_count: int
    off_session_excluded_count: int
    duplicate_expected_slot_count: int
    duplicate_expected_slot_sha256: str
    missing_expected_slot_count: int
    missing_expected_slot_sha256: str
    malformed_bar_count: int
    pagination_terminal_state: str
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class Arch150DataPartition:
    schema: str
    name: str
    start: date
    end_exclusive: date
    identity: UUID
    sha256: str
    row_count: int
    bars: tuple[IntradayBar, ...]


@dataclass(frozen=True, slots=True)
class Arch150CustodyDataset:
    schema: str
    classification: DatasetClassification
    failure_codes: tuple[str, ...]
    identity: UUID
    sha256: str
    start: date
    end_exclusive: date
    symbols: tuple[str, ...]
    timeframe: str
    price_basis: str
    upstream_xnys_identity: str
    upstream_xnys_digest: str
    session_schedule_identity: str
    session_schedule_digest: str
    request_descriptors: tuple[str, ...]
    raw_page_commitments: tuple[RawPageCommitment, ...]
    raw_page_sha256_by_symbol: tuple[tuple[str, tuple[str, ...]], ...]
    diagnostics_by_symbol: tuple[SymbolDiagnostics, ...]
    normalized_bytes: bytes
    normalized_sha256: str
    first_timestamp: str | None
    last_timestamp: str | None
    bars: tuple[IntradayBar, ...]
    discovery: Arch150DataPartition
    validation: Arch150DataPartition


def _partition(
    name: str,
    start: date,
    end_exclusive: date,
    bars: tuple[IntradayBar, ...],
    dataset_identity: UUID,
) -> Arch150DataPartition:
    if any(not start <= bar.session_date < end_exclusive for bar in bars):
        raise Arch150DataError("PARTITION_BOUNDARY_MISMATCH")
    body = normalized_csv_bytes(bars)
    digest = sha256(body).hexdigest()
    material = {
        "schema": ARCH150_PARTITION_SCHEMA,
        "name": name,
        "start": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "timeframe": TIMEFRAME,
        "universe": list(INITIAL_UNIVERSE),
        "complete_dataset_identity": str(dataset_identity),
        "row_count": len(bars),
        "normalized_sha256": digest,
    }
    identity = uuid5(
        _PARTITION_NAMESPACE, canonical_json_bytes(material).decode("utf-8")
    )
    return Arch150DataPartition(
        ARCH150_PARTITION_SCHEMA,
        name,
        start,
        end_exclusive,
        identity,
        digest,
        len(bars),
        bars,
    )


def dataset_identity_material(
    *,
    request_descriptors: tuple[str, ...],
    raw_page_commitments: tuple[RawPageCommitment, ...],
    raw_page_sha256_by_symbol: tuple[tuple[str, tuple[str, ...]], ...],
    diagnostics_by_symbol: tuple[SymbolDiagnostics, ...],
    normalized_sha256: str,
    normalized_bar_count: int,
    first_timestamp: str | None,
    last_timestamp: str | None,
    discovery_row_count: int,
    discovery_sha256: str,
    validation_row_count: int,
    validation_sha256: str,
    upstream_xnys_identity: str,
    upstream_xnys_digest: str,
    session_schedule_identity: str,
    session_schedule_digest: str,
    classification: DatasetClassification,
    failure_codes: tuple[str, ...],
) -> dict[str, object]:
    """Return the complete versioned Arch150 identity input."""

    _digest(normalized_sha256)
    _digest(upstream_xnys_digest)
    _digest(session_schedule_digest)
    _digest(discovery_sha256)
    _digest(validation_sha256)
    return {
        "version": ARCH150_DATA_IDENTITY_VERSION,
        "schema": ARCH150_DATA_SCHEMA,
        "classification": classification.value,
        "failure_codes": list(failure_codes),
        "universe": list(INITIAL_UNIVERSE),
        "start": DATA_START.isoformat(),
        "end_exclusive": DATA_END_EXCLUSIVE.isoformat(),
        "discovery": {
            "start": DISCOVERY_START.isoformat(),
            "end_exclusive": DISCOVERY_END.isoformat(),
            "row_count": discovery_row_count,
            "sha256": discovery_sha256,
        },
        "validation": {
            "start": VALIDATION_START.isoformat(),
            "end_exclusive": VALIDATION_END.isoformat(),
            "row_count": validation_row_count,
            "sha256": validation_sha256,
        },
        "timeframe": TIMEFRAME,
        "provider": PROVIDER_NAME,
        "endpoint": PROVIDER_ENDPOINT,
        "adjustment": ADJUSTMENT,
        "adjustment_semantics": ADJUSTMENT_SEMANTICS,
        "feed": FEED,
        "currency": CURRENCY,
        "asof": ASOF,
        "sort": SORT,
        "limit": LIMIT,
        "price_basis": PRICE_BASIS,
        "upstream_xnys_identity": upstream_xnys_identity,
        "upstream_xnys_digest": upstream_xnys_digest,
        "session_schedule_identity": session_schedule_identity,
        "session_schedule_digest": session_schedule_digest,
        "ordered_request_descriptors": [
            json.loads(item) for item in request_descriptors
        ],
        "ordered_raw_page_commitments": [
            item.to_dict() for item in raw_page_commitments
        ],
        "ordered_raw_page_sha256_by_symbol": {
            symbol: list(hashes) for symbol, hashes in raw_page_sha256_by_symbol
        },
        "symbol_diagnostics": [
            {
                "symbol": item.symbol,
                "raw_page_count": item.raw_page_count,
                "raw_bar_count": item.raw_bar_count,
                "raw_bar_count_known": item.raw_bar_count_known,
                "parsed_page_count": item.parsed_page_count,
                "observed_regular_slot_bar_count": item.observed_regular_slot_bar_count,
                "normalized_regular_bar_count": item.normalized_regular_bar_count,
                "off_session_excluded_count": item.off_session_excluded_count,
                "duplicate_expected_slot_count": item.duplicate_expected_slot_count,
                "duplicate_expected_slot_sha256": item.duplicate_expected_slot_sha256,
                "missing_expected_slot_count": item.missing_expected_slot_count,
                "missing_expected_slot_sha256": item.missing_expected_slot_sha256,
                "malformed_bar_count": item.malformed_bar_count,
                "pagination_terminal_state": item.pagination_terminal_state,
                "failure_code": item.failure_code,
            }
            for item in diagnostics_by_symbol
        ],
        "normalized_regular_session_bar_count": normalized_bar_count,
        "normalized_sha256": normalized_sha256,
        "first_normalized_timestamp": first_timestamp,
        "last_normalized_timestamp": last_timestamp,
    }


def _stream_request_descriptors(
    collections: tuple[SymbolPageCollection, ...],
) -> tuple[str, ...]:
    return tuple(
        page.request_descriptor_json
        for collection in collections
        for page in collection.pages
    )


def _qualify_symbol(
    symbol: str,
    bars: tuple[IntradayBar, ...],
    *,
    authority: HistoricalIntradaySessionAuthority,
    expected_start: date = DATA_START,
    expected_end: date = DATA_END_EXCLUSIVE,
) -> tuple[tuple[IntradayBar, ...], SymbolDiagnostics]:
    if symbol not in INITIAL_UNIVERSE:
        raise Arch150DataError("UNSUPPORTED_SYMBOL")
    expected_slots = iter(
        expected_regular_minute_slots(expected_start, expected_end, authority)
    )
    expected_slot = next(expected_slots, None)
    normalized: list[IntradayBar] = []
    missing_hash = sha256()
    duplicate_hash = sha256()
    missing_count = 0
    duplicate_count = 0
    off_session = 0
    malformed = 0
    observed = 0
    previous: datetime | None = None
    last_matched: datetime | None = None

    def record_missing(value: datetime) -> None:
        nonlocal missing_count
        missing_hash.update(_timestamp_text(value).encode("ascii"))
        missing_hash.update(b"\n")
        missing_count += 1

    for bar in bars:
        if type(bar) is not IntradayBar or bar.symbol != symbol:
            malformed += 1
            continue
        stamp = bar.timestamp.astimezone(UTC)
        if not REQUEST_START <= stamp < datetime(2024, 1, 1, tzinfo=UTC):
            malformed += 1
            continue
        if previous is not None and stamp < previous:
            malformed += 1
        previous = stamp
        local = stamp.astimezone(_NEW_YORK)
        schedule = authority.schedule_for(local.date())
        if schedule is None or not schedule.opens_at <= stamp < schedule.closes_at:
            off_session += 1
            continue
        if stamp.second != 0 or stamp.microsecond != 0:
            malformed += 1
            continue
        while expected_slot is not None and expected_slot < stamp:
            record_missing(expected_slot)
            expected_slot = next(expected_slots, None)
        if stamp == last_matched:
            duplicate_hash.update(_timestamp_text(stamp).encode("ascii"))
            duplicate_hash.update(b"\n")
            duplicate_count += 1
            observed += 1
            continue
        if stamp != expected_slot:
            malformed += 1
            continue
        observed += 1
        normalized.append(bar)
        last_matched = stamp
        expected_slot = next(expected_slots, None)
    while expected_slot is not None:
        record_missing(expected_slot)
        expected_slot = next(expected_slots, None)
    diagnostics = SymbolDiagnostics(
        symbol=symbol,
        raw_page_count=0,
        raw_bar_count=len(bars),
        raw_bar_count_known=True,
        parsed_page_count=0,
        observed_regular_slot_bar_count=observed,
        normalized_regular_bar_count=0,
        off_session_excluded_count=off_session,
        duplicate_expected_slot_count=duplicate_count,
        duplicate_expected_slot_sha256=duplicate_hash.hexdigest(),
        missing_expected_slot_count=missing_count,
        missing_expected_slot_sha256=missing_hash.hexdigest(),
        malformed_bar_count=malformed,
        pagination_terminal_state="NOT_APPLICABLE",
        failure_code=None,
    )
    return tuple(normalized), diagnostics


def _blocked_reason_codes(
    collections: tuple[SymbolPageCollection, ...],
    diagnostics: tuple[SymbolDiagnostics, ...],
) -> tuple[str, ...]:
    reasons = [
        collection.failure_code
        for collection in collections
        if collection.failure_code is not None
    ]
    for item in diagnostics:
        if item.missing_expected_slot_count:
            reasons.append("MISSING_EXPECTED_SLOT")
        if item.duplicate_expected_slot_count:
            reasons.append("DUPLICATE_EXPECTED_SLOT")
        if item.malformed_bar_count:
            reasons.append("MALFORMED_REGULAR_SESSION_BAR")
    return tuple(dict.fromkeys(reasons))


def qualify_arch150_dataset(
    collections: Iterable[SymbolPageCollection],
    *,
    authority: HistoricalIntradaySessionAuthority | None = None,
) -> Arch150CustodyDataset:
    """Build READY only for complete, unique, exact XNYS one-minute coverage."""

    materialized = tuple(collections)
    if tuple(item.symbol for item in materialized) != INITIAL_UNIVERSE:
        raise Arch150DataError("STREAM_UNIVERSE_OR_ORDER_INVALID")
    authority = authority or published_session_authority()
    _schedule_rows(authority)
    schedule_identity, schedule_digest = session_authority_commitment(authority)
    symbol_results: list[tuple[IntradayBar, ...]] = []
    diagnostics: list[SymbolDiagnostics] = []
    pages_by_symbol: list[tuple[str, tuple[str, ...]]] = []
    page_commitments: list[RawPageCommitment] = []
    for collection in materialized:
        normalized, item = _qualify_symbol(
            collection.symbol, collection.bars, authority=authority
        )
        item = SymbolDiagnostics(
            symbol=item.symbol,
            raw_page_count=len(collection.pages),
            raw_bar_count=collection.raw_bar_count,
            raw_bar_count_known=collection.raw_bar_count is not None,
            parsed_page_count=collection.parsed_page_count,
            observed_regular_slot_bar_count=item.observed_regular_slot_bar_count,
            normalized_regular_bar_count=0,
            off_session_excluded_count=item.off_session_excluded_count,
            duplicate_expected_slot_count=item.duplicate_expected_slot_count,
            duplicate_expected_slot_sha256=item.duplicate_expected_slot_sha256,
            missing_expected_slot_count=item.missing_expected_slot_count,
            missing_expected_slot_sha256=item.missing_expected_slot_sha256,
            malformed_bar_count=item.malformed_bar_count,
            pagination_terminal_state=collection.terminal_state,
            failure_code=collection.failure_code,
        )
        symbol_results.append(normalized)
        diagnostics.append(item)
        pages_by_symbol.append(
            (collection.symbol, tuple(page.page_sha256 for page in collection.pages))
        )
        page_commitments.extend(collection.pages)
    diagnostics_tuple = tuple(diagnostics)
    reasons = _blocked_reason_codes(materialized, diagnostics_tuple)
    if any(not item.pagination_complete for item in materialized):
        reasons = tuple(dict.fromkeys((*reasons, "PAGINATION_INCOMPLETE")))
    if any(item.raw_bar_count is None for item in materialized):
        reasons = tuple(dict.fromkeys((*reasons, "RAW_BAR_COUNT_INCOMPLETE")))
    candidate = tuple(bar for stream in symbol_results for bar in stream)
    if not reasons:
        try:
            # The accepted Arch150 validator proves these remain representable by
            # the frozen foundation's exact SPY/QQQ one-minute bar contracts.
            validate_universe_minute_bars(candidate)
        except (TypeError, ValueError):
            reasons = ("ARCH150_FOUNDATION_REPRESENTATION_FAILED",)
    ready = not reasons
    normalized_bars = candidate if ready else ()
    normalized_bytes = normalized_csv_bytes(normalized_bars)
    normalized_digest = sha256(normalized_bytes).hexdigest()
    discovery_bars = tuple(
        bar
        for bar in normalized_bars
        if DISCOVERY_START <= bar.session_date < DISCOVERY_END
    )
    validation_bars = tuple(
        bar
        for bar in normalized_bars
        if VALIDATION_START <= bar.session_date < VALIDATION_END
    )
    discovery_bytes = normalized_csv_bytes(discovery_bars)
    validation_bytes = normalized_csv_bytes(validation_bars)
    discovery_digest = sha256(discovery_bytes).hexdigest()
    validation_digest = sha256(validation_bytes).hexdigest()
    status = DatasetClassification.READY if ready else DatasetClassification.BLOCKED
    frozen_diagnostics = tuple(
        SymbolDiagnostics(
            symbol=item.symbol,
            raw_page_count=item.raw_page_count,
            raw_bar_count=item.raw_bar_count,
            raw_bar_count_known=item.raw_bar_count_known,
            parsed_page_count=item.parsed_page_count,
            observed_regular_slot_bar_count=item.observed_regular_slot_bar_count,
            normalized_regular_bar_count=(len(symbol_results[index]) if ready else 0),
            off_session_excluded_count=item.off_session_excluded_count,
            duplicate_expected_slot_count=item.duplicate_expected_slot_count,
            duplicate_expected_slot_sha256=item.duplicate_expected_slot_sha256,
            missing_expected_slot_count=item.missing_expected_slot_count,
            missing_expected_slot_sha256=item.missing_expected_slot_sha256,
            malformed_bar_count=item.malformed_bar_count,
            pagination_terminal_state=item.pagination_terminal_state,
            failure_code=item.failure_code,
        )
        for index, item in enumerate(diagnostics_tuple)
    )
    request_descriptors = _stream_request_descriptors(materialized)
    material = dataset_identity_material(
        request_descriptors=request_descriptors,
        raw_page_commitments=tuple(page_commitments),
        raw_page_sha256_by_symbol=tuple(pages_by_symbol),
        diagnostics_by_symbol=frozen_diagnostics,
        normalized_sha256=normalized_digest,
        normalized_bar_count=len(normalized_bars),
        first_timestamp=(
            _timestamp_text(normalized_bars[0].timestamp) if normalized_bars else None
        ),
        last_timestamp=(
            _timestamp_text(normalized_bars[-1].timestamp) if normalized_bars else None
        ),
        discovery_row_count=len(discovery_bars),
        discovery_sha256=discovery_digest,
        validation_row_count=len(validation_bars),
        validation_sha256=validation_digest,
        upstream_xnys_identity=authority.published.identity,
        upstream_xnys_digest=authority.published.digest,
        session_schedule_identity=schedule_identity,
        session_schedule_digest=schedule_digest,
        classification=status,
        failure_codes=reasons,
    )
    identity_bytes = canonical_json_bytes(material)
    dataset_sha = sha256(identity_bytes).hexdigest()
    dataset_id = uuid5(_DATA_NAMESPACE, identity_bytes.decode("utf-8"))
    discovery = _partition(
        "DISCOVERY", DISCOVERY_START, DISCOVERY_END, discovery_bars, dataset_id
    )
    validation = _partition(
        "VALIDATION", VALIDATION_START, VALIDATION_END, validation_bars, dataset_id
    )
    return Arch150CustodyDataset(
        schema=ARCH150_DATA_SCHEMA,
        classification=status,
        failure_codes=reasons,
        identity=dataset_id,
        sha256=dataset_sha,
        start=DATA_START,
        end_exclusive=DATA_END_EXCLUSIVE,
        symbols=INITIAL_UNIVERSE,
        timeframe=TIMEFRAME,
        price_basis=PRICE_BASIS,
        upstream_xnys_identity=authority.published.identity,
        upstream_xnys_digest=authority.published.digest,
        session_schedule_identity=schedule_identity,
        session_schedule_digest=schedule_digest,
        request_descriptors=request_descriptors,
        raw_page_commitments=tuple(page_commitments),
        raw_page_sha256_by_symbol=tuple(pages_by_symbol),
        diagnostics_by_symbol=frozen_diagnostics,
        normalized_bytes=normalized_bytes,
        normalized_sha256=normalized_digest,
        first_timestamp=(
            _timestamp_text(normalized_bars[0].timestamp) if normalized_bars else None
        ),
        last_timestamp=(
            _timestamp_text(normalized_bars[-1].timestamp) if normalized_bars else None
        ),
        bars=normalized_bars,
        discovery=discovery,
        validation=validation,
    )


@dataclass(frozen=True, slots=True)
class Arch150CustodyEvidence:
    schema: str
    classification: str
    failure_codes: tuple[str, ...]
    identity: UUID
    sha256: str
    source_head: str
    source_tree: str
    dataset_identity: UUID
    dataset_sha256: str
    request_descriptors: tuple[str, ...]
    raw_page_commitments: tuple[RawPageCommitment, ...]
    raw_page_sha256_by_symbol: tuple[tuple[str, tuple[str, ...]], ...]
    diagnostics_by_symbol: tuple[SymbolDiagnostics, ...]
    credential_read_attempt_count: int
    provider_request_attempt_count: int
    robinhood_calls: int = 0
    broker_calls: int = 0
    order_mutations: int = 0
    production_state_mutations: int = 0
    strategy_pnl_evaluations: int = 0
    holdout_accesses: int = 0
    extension_accesses: int = 0
    automatic_retry: str = "FORBIDDEN"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "classification": self.classification,
            "failure_codes": list(self.failure_codes),
            "identity": str(self.identity),
            "sha256": self.sha256,
            "source": {"head": self.source_head, "tree": self.source_tree},
            "dataset": {
                "identity": str(self.dataset_identity),
                "sha256": self.dataset_sha256,
            },
            "request_descriptors": [
                json.loads(item) for item in self.request_descriptors
            ],
            "raw_page_commitments": [
                item.to_dict() for item in self.raw_page_commitments
            ],
            "raw_page_sha256_by_symbol": {
                symbol: list(hashes)
                for symbol, hashes in self.raw_page_sha256_by_symbol
            },
            "diagnostics_by_symbol": [
                {
                    "symbol": item.symbol,
                    "raw_page_count": item.raw_page_count,
                    "raw_bar_count": item.raw_bar_count,
                    "raw_bar_count_known": item.raw_bar_count_known,
                    "parsed_page_count": item.parsed_page_count,
                    "observed_regular_slot_bar_count": (
                        item.observed_regular_slot_bar_count
                    ),
                    "normalized_regular_bar_count": item.normalized_regular_bar_count,
                    "off_session_excluded_count": item.off_session_excluded_count,
                    "duplicate_expected_slot_count": item.duplicate_expected_slot_count,
                    "duplicate_expected_slot_sha256": (
                        item.duplicate_expected_slot_sha256
                    ),
                    "missing_expected_slot_count": item.missing_expected_slot_count,
                    "missing_expected_slot_sha256": item.missing_expected_slot_sha256,
                    "malformed_bar_count": item.malformed_bar_count,
                    "pagination_terminal_state": item.pagination_terminal_state,
                    "failure_code": item.failure_code,
                }
                for item in self.diagnostics_by_symbol
            ],
            "effects": {
                "credential_read_attempt_count": self.credential_read_attempt_count,
                "provider_request_attempt_count": self.provider_request_attempt_count,
                "robinhood_calls": self.robinhood_calls,
                "broker_calls": self.broker_calls,
                "order_mutations": self.order_mutations,
                "production_state_mutations": self.production_state_mutations,
                "strategy_pnl_evaluations": self.strategy_pnl_evaluations,
                "holdout_accesses": self.holdout_accesses,
                "extension_accesses": self.extension_accesses,
            },
            "automatic_retry": self.automatic_retry,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


def build_custody_evidence(
    dataset: Arch150CustodyDataset,
    *,
    source_head: str,
    source_tree: str,
    credential_read_attempt_count: int,
    provider_request_attempt_count: int,
) -> Arch150CustodyEvidence:
    """Bind the review report to dataset custody without paths, clocks or OHLCV."""

    if type(dataset) is not Arch150CustodyDataset:
        raise Arch150DataError("INVALID_DATASET_TYPE")
    if not re.fullmatch(r"[0-9a-f]{40}", source_head) or not re.fullmatch(
        r"[0-9a-f]{40}", source_tree
    ):
        raise Arch150DataError("INVALID_SOURCE_IDENTITY")
    if (
        type(credential_read_attempt_count) is not int
        or credential_read_attempt_count < 0
        or type(provider_request_attempt_count) is not int
        or provider_request_attempt_count < 0
    ):
        raise Arch150DataError("INVALID_EFFECT_COUNT")
    identity_material = {
        "version": ARCH150_CUSTODY_IDENTITY_VERSION,
        "schema": ARCH150_CUSTODY_SCHEMA,
        "classification": dataset.classification.value,
        "failure_codes": list(dataset.failure_codes),
        "source_head": source_head,
        "source_tree": source_tree,
        "dataset_identity": str(dataset.identity),
        "dataset_sha256": dataset.sha256,
        "request_descriptors": [
            json.loads(item) for item in dataset.request_descriptors
        ],
        "raw_page_commitments": [
            item.to_dict() for item in dataset.raw_page_commitments
        ],
        "raw_page_sha256_by_symbol": {
            symbol: list(hashes) for symbol, hashes in dataset.raw_page_sha256_by_symbol
        },
        "diagnostics": [
            item.__dict__
            if hasattr(item, "__dict__")
            else {field: getattr(item, field) for field in item.__dataclass_fields__}
            for item in dataset.diagnostics_by_symbol
        ],
        "effects": {
            "credential_read_attempt_count": credential_read_attempt_count,
            "provider_request_attempt_count": provider_request_attempt_count,
            "robinhood_calls": 0,
            "broker_calls": 0,
            "order_mutations": 0,
            "production_state_mutations": 0,
            "strategy_pnl_evaluations": 0,
            "holdout_accesses": 0,
            "extension_accesses": 0,
        },
        "automatic_retry": "FORBIDDEN",
    }
    body = canonical_json_bytes(identity_material)
    return Arch150CustodyEvidence(
        schema=ARCH150_CUSTODY_SCHEMA,
        classification=dataset.classification.value,
        failure_codes=dataset.failure_codes,
        identity=uuid5(_CUSTODY_NAMESPACE, body.decode("utf-8")),
        sha256=sha256(body).hexdigest(),
        source_head=source_head,
        source_tree=source_tree,
        dataset_identity=dataset.identity,
        dataset_sha256=dataset.sha256,
        request_descriptors=dataset.request_descriptors,
        raw_page_commitments=dataset.raw_page_commitments,
        raw_page_sha256_by_symbol=dataset.raw_page_sha256_by_symbol,
        diagnostics_by_symbol=dataset.diagnostics_by_symbol,
        credential_read_attempt_count=credential_read_attempt_count,
        provider_request_attempt_count=provider_request_attempt_count,
    )


__all__ = [
    "ADJUSTMENT",
    "ADJUSTMENT_SEMANTICS",
    "ASOF",
    "ARCH150_CUSTODY_SCHEMA",
    "ARCH150_DATA_SCHEMA",
    "ARCH150_PARTITION_SCHEMA",
    "Arch150CustodyDataset",
    "Arch150CustodyEvidence",
    "Arch150DataError",
    "Arch150DataPartition",
    "Arch150HistoricalRequest",
    "CURRENCY",
    "DATA_END_EXCLUSIVE",
    "DATA_START",
    "DISCOVERY_END",
    "DISCOVERY_START",
    "DatasetClassification",
    "FEED",
    "INITIAL_UNIVERSE",
    "LIMIT",
    "MAX_PAGES_PER_SYMBOL",
    "MAX_PROVIDER_REQUEST_ATTEMPTS",
    "PRICE_BASIS",
    "ParsedProviderPage",
    "RawPageCommitment",
    "SORT",
    "SymbolDiagnostics",
    "SymbolPageCollection",
    "TIMEFRAME",
    "VALIDATION_END",
    "VALIDATION_START",
    "build_alpaca_request",
    "build_custody_evidence",
    "collect_symbol_pages",
    "dataset_identity_material",
    "expected_regular_minute_slots",
    "normalized_csv_bytes",
    "parse_alpaca_page",
    "published_session_authority",
    "qualify_arch150_dataset",
    "session_authority_commitment",
]
