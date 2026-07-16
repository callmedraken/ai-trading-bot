"""Immutable historical market-data requests and results."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from trading_bot.domain import Bar, Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.market_data.exceptions import (
    DuplicateBarTimestampError,
    InvalidHistoricalDataRequestError,
    InvalidHistoricalDataResultError,
)


class Timeframe(StrEnum):
    DAY_1 = "1D"


class AdjustmentType(StrEnum):
    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    TOTAL_RETURN = "TOTAL_RETURN"


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
