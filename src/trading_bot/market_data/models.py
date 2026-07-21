"""Immutable historical market-data requests and results."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from trading_bot.domain import Bar, Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.market_data.exceptions import (
    DuplicateBarTimestampError,
    DuplicateRequestedSymbolError,
    EmptyAlignedHistoricalDataError,
    InvalidHistoricalDataRequestError,
    InvalidHistoricalDataResultError,
    InvalidMultiSymbolHistoricalDataRequestError,
    InvalidMultiSymbolHistoricalDataResultError,
)


class Timeframe(StrEnum):
    DAY_1 = "1D"


class AdjustmentType(StrEnum):
    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    TOTAL_RETURN = "TOTAL_RETURN"


class MissingBarPolicy(StrEnum):
    """Exact-timestamp policy for incomplete multi-symbol observations."""

    UNION = "UNION"
    INTERSECTION = "INTERSECTION"


@dataclass(frozen=True, slots=True)
class HistoricalDataRequest:
    """A request for one symbol over a UTC half-open interval."""

    symbol: Symbol
    start: datetime
    end: datetime
    timeframe: Timeframe = Timeframe.DAY_1
    adjustment: AdjustmentType = AdjustmentType.RAW

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise InvalidHistoricalDataRequestError("symbol must be a Symbol")
        if not isinstance(self.timeframe, Timeframe):
            raise InvalidHistoricalDataRequestError("timeframe must be a Timeframe")
        if not isinstance(self.adjustment, AdjustmentType):
            raise InvalidHistoricalDataRequestError(
                "adjustment must be an AdjustmentType"
            )
        try:
            start = normalize_utc(self.start, "start")
            end = normalize_utc(self.end, "end")
        except (TypeError, ValueError) as error:
            raise InvalidHistoricalDataRequestError(str(error)) from error
        if start >= end:
            raise InvalidHistoricalDataRequestError("start must be earlier than end")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@dataclass(frozen=True, slots=True)
class HistoricalDataResult:
    """Validated immutable bars returned by a named provider."""

    request: HistoricalDataRequest
    bars: tuple[Bar, ...]
    provider_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, HistoricalDataRequest):
            raise InvalidHistoricalDataResultError(
                "request must be a HistoricalDataRequest"
            )
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise InvalidHistoricalDataResultError("provider_name must be nonblank")
        try:
            bars = tuple(self.bars)
        except TypeError as error:
            raise InvalidHistoricalDataResultError("bars must be iterable") from error
        previous_timestamp = None
        for bar in bars:
            if not isinstance(bar, Bar):
                raise InvalidHistoricalDataResultError(
                    "bars must contain only Bar values"
                )
            if bar.symbol != self.request.symbol:
                raise InvalidHistoricalDataResultError(
                    f"bar symbol {bar.symbol} does not match {self.request.symbol}"
                )
            if not self.request.start <= bar.timestamp < self.request.end:
                raise InvalidHistoricalDataResultError(
                    f"bar timestamp {bar.timestamp.isoformat()} is outside the request"
                )
            if previous_timestamp is not None:
                if bar.timestamp == previous_timestamp:
                    raise DuplicateBarTimestampError(
                        f"duplicate bar timestamp {bar.timestamp.isoformat()}"
                    )
                if bar.timestamp < previous_timestamp:
                    raise InvalidHistoricalDataResultError(
                        "bars must be ordered chronologically"
                    )
            previous_timestamp = bar.timestamp
        object.__setattr__(self, "bars", bars)


@dataclass(frozen=True, slots=True)
class MultiSymbolHistoricalDataRequest:
    """One ordered symbol universe over a shared UTC half-open interval."""

    symbols: tuple[Symbol, ...]
    start: datetime
    end: datetime
    timeframe: Timeframe = Timeframe.DAY_1
    adjustment: AdjustmentType = AdjustmentType.RAW
    missing_bar_policy: MissingBarPolicy = MissingBarPolicy.UNION

    def __post_init__(self) -> None:
        try:
            symbols = tuple(self.symbols)
        except TypeError as error:
            raise InvalidMultiSymbolHistoricalDataRequestError(
                "symbols must be iterable"
            ) from error
        if not symbols:
            raise InvalidMultiSymbolHistoricalDataRequestError(
                "symbols must not be empty"
            )
        if not all(isinstance(symbol, Symbol) for symbol in symbols):
            raise InvalidMultiSymbolHistoricalDataRequestError(
                "symbols must contain only Symbol values"
            )
        if len(set(symbols)) != len(symbols):
            raise DuplicateRequestedSymbolError(
                "symbols must not contain duplicate values"
            )
        if not isinstance(self.timeframe, Timeframe):
            raise InvalidMultiSymbolHistoricalDataRequestError(
                "timeframe must be a Timeframe"
            )
        if not isinstance(self.adjustment, AdjustmentType):
            raise InvalidMultiSymbolHistoricalDataRequestError(
                "adjustment must be an AdjustmentType"
            )
        if not isinstance(self.missing_bar_policy, MissingBarPolicy):
            raise InvalidMultiSymbolHistoricalDataRequestError(
                "missing_bar_policy must be a MissingBarPolicy"
            )
        try:
            start = normalize_utc(self.start, "start")
            end = normalize_utc(self.end, "end")
        except (TypeError, ValueError) as error:
            raise InvalidMultiSymbolHistoricalDataRequestError(str(error)) from error
        if start >= end:
            raise InvalidMultiSymbolHistoricalDataRequestError(
                "start must be earlier than end"
            )
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@dataclass(frozen=True, slots=True)
class SymbolBars:
    """One immutable symbol-first view derived from aligned frames."""

    symbol: Symbol
    bars: tuple[Bar, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        bars = tuple(self.bars)
        previous = None
        for bar in bars:
            if not isinstance(bar, Bar) or bar.symbol != self.symbol:
                raise ValueError("bars must contain matching Bar values")
            if previous is not None and bar.timestamp <= previous:
                raise ValueError("bars must have strictly increasing timestamps")
            previous = bar.timestamp
        object.__setattr__(self, "bars", bars)


@dataclass(frozen=True, slots=True)
class AlignedMarketFrame:
    """Available bars at one exact UTC timestamp for an ordered universe."""

    timestamp: datetime
    symbols: tuple[Symbol, ...]
    bars_by_symbol: Mapping[Symbol, Bar]
    missing_symbols: tuple[Symbol, ...] = field(init=False)

    def __post_init__(self) -> None:
        try:
            timestamp = normalize_utc(self.timestamp, "timestamp")
        except (TypeError, ValueError) as error:
            raise InvalidMultiSymbolHistoricalDataResultError(str(error)) from error
        symbols = tuple(self.symbols)
        if not symbols or not all(isinstance(symbol, Symbol) for symbol in symbols):
            raise InvalidMultiSymbolHistoricalDataResultError(
                "frame symbols must be a nonempty tuple of Symbol values"
            )
        if len(set(symbols)) != len(symbols):
            raise InvalidMultiSymbolHistoricalDataResultError(
                "frame symbols must not contain duplicates"
            )
        if not isinstance(self.bars_by_symbol, Mapping):
            raise InvalidMultiSymbolHistoricalDataResultError(
                "bars_by_symbol must be a mapping"
            )
        caller_copy = dict(self.bars_by_symbol)
        unexpected = set(caller_copy) - set(symbols)
        if unexpected:
            raise InvalidMultiSymbolHistoricalDataResultError(
                "bars_by_symbol contains a symbol outside the requested universe"
            )
        ordered = {}
        for symbol in symbols:
            bar = caller_copy.get(symbol)
            if bar is None:
                continue
            if not isinstance(bar, Bar) or bar.symbol != symbol:
                raise InvalidMultiSymbolHistoricalDataResultError(
                    "frame bars must match their symbol keys"
                )
            if bar.timestamp != timestamp:
                raise InvalidMultiSymbolHistoricalDataResultError(
                    "frame bars must match the exact frame timestamp"
                )
            ordered[symbol] = bar
        missing = tuple(symbol for symbol in symbols if symbol not in ordered)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "bars_by_symbol", MappingProxyType(ordered))
        object.__setattr__(self, "missing_symbols", missing)

    @property
    def is_complete(self) -> bool:
        return not self.missing_symbols


@dataclass(frozen=True, slots=True)
class MultiSymbolHistoricalDataResult:
    """Validated timestamp-first frames for one ordered symbol universe."""

    request: MultiSymbolHistoricalDataRequest
    frames: tuple[AlignedMarketFrame, ...]
    provider_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, MultiSymbolHistoricalDataRequest):
            raise InvalidMultiSymbolHistoricalDataResultError(
                "request must be a MultiSymbolHistoricalDataRequest"
            )
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise InvalidMultiSymbolHistoricalDataResultError(
                "provider_name must be nonblank"
            )
        frames = tuple(self.frames)
        if not frames:
            raise EmptyAlignedHistoricalDataError(
                "multi-symbol alignment produced no frames"
            )
        previous = None
        for frame in frames:
            if not isinstance(frame, AlignedMarketFrame):
                raise InvalidMultiSymbolHistoricalDataResultError(
                    "frames must contain AlignedMarketFrame values"
                )
            if frame.symbols != self.request.symbols:
                raise InvalidMultiSymbolHistoricalDataResultError(
                    "frame symbols must equal the requested symbol order"
                )
            if not self.request.start <= frame.timestamp < self.request.end:
                raise InvalidMultiSymbolHistoricalDataResultError(
                    "frame timestamp is outside the request interval"
                )
            if previous is not None and frame.timestamp <= previous:
                raise InvalidMultiSymbolHistoricalDataResultError(
                    "frame timestamps must be strictly increasing"
                )
            if not frame.bars_by_symbol:
                raise InvalidMultiSymbolHistoricalDataResultError(
                    "each frame must contain at least one bar"
                )
            if (
                self.request.missing_bar_policy is MissingBarPolicy.INTERSECTION
                and not frame.is_complete
            ):
                raise InvalidMultiSymbolHistoricalDataResultError(
                    "intersection frames must contain every requested symbol"
                )
            previous = frame.timestamp
        object.__setattr__(self, "frames", frames)

    @property
    def symbols(self) -> tuple[Symbol, ...]:
        return self.request.symbols

    @property
    def timestamps(self) -> tuple[datetime, ...]:
        return tuple(frame.timestamp for frame in self.frames)

    @property
    def is_complete(self) -> bool:
        return all(frame.is_complete for frame in self.frames)

    def bars_for(self, symbol: Symbol) -> SymbolBars:
        if not isinstance(symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if symbol not in self.request.symbols:
            raise ValueError("symbol is outside the requested universe")
        return SymbolBars(
            symbol,
            tuple(
                frame.bars_by_symbol[symbol]
                for frame in self.frames
                if symbol in frame.bars_by_symbol
            ),
        )

    def frame_at(self, timestamp: datetime) -> AlignedMarketFrame | None:
        normalized = normalize_utc(timestamp, "timestamp")
        for frame in self.frames:
            if frame.timestamp == normalized:
                return frame
        return None
