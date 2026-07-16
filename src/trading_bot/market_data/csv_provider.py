"""Strict offline historical-data provider backed by local CSV files."""

import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from trading_bot.domain import Bar, Symbol
from trading_bot.market_data.exceptions import (
    CSVRowError,
    CSVSchemaError,
    DuplicateBarTimestampError,
    HistoricalDataNotFoundError,
    UnsupportedAdjustmentError,
    UnsupportedTimeframeError,
)
from trading_bot.market_data.models import (
    AdjustmentType,
    HistoricalDataRequest,
    HistoricalDataResult,
    Timeframe,
)

_HEADERS = ("timestamp", "symbol", "open", "high", "low", "close", "volume")
_VOLUME_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")


class CSVHistoricalDataProvider:
    """Read one strictly validated CSV file per normalized symbol."""

    provider_name = "local_csv"

    def __init__(self, root_directory: Path) -> None:
        if not isinstance(root_directory, Path):
            raise TypeError("root_directory must be a Path")
        self._root_directory = root_directory

    @property
    def root_directory(self) -> Path:
        return self._root_directory

    def get_bars(self, request: HistoricalDataRequest) -> HistoricalDataResult:
        """Validate, sort, deduplicate, and filter one symbol's local CSV."""
        if not isinstance(request, HistoricalDataRequest):
            raise TypeError("request must be a HistoricalDataRequest")
        if request.timeframe is not Timeframe.DAY_1:
            raise UnsupportedTimeframeError(
                f"CSV provider does not support timeframe {request.timeframe}"
            )
        if request.adjustment is not AdjustmentType.RAW:
            raise UnsupportedAdjustmentError(
                f"CSV provider supports RAW data only, not {request.adjustment.value}"
            )
        path = self._root_directory / f"{request.symbol}.csv"
        if not path.is_file():
            raise HistoricalDataNotFoundError(
                f"no historical CSV file exists for {request.symbol}: {path}"
            )

        bars = self._load_and_validate(path, request.symbol)
        bars.sort(key=lambda bar: bar.timestamp)
        self._reject_duplicate_timestamps(bars, path)
        selected = tuple(
            bar for bar in bars if request.start <= bar.timestamp < request.end
        )
        return HistoricalDataResult(request, selected, self.provider_name)

    def _load_and_validate(self, path: Path, expected_symbol: Symbol) -> list[Bar]:
        try:
            with path.open("r", encoding="utf-8", newline="") as csv_file:
                reader = csv.reader(csv_file)
                try:
                    headers = next(reader)
                except StopIteration as error:
                    raise CSVSchemaError(f"CSV file is empty: {path}") from error
                self._validate_headers(headers, path)
                indexes = {header: headers.index(header) for header in _HEADERS}
                bars = []
                for line_number, row in enumerate(reader, start=2):
                    if len(row) != len(headers):
                        raise CSVRowError(
                            f"{path}:{line_number}: expected {len(headers)} fields, "
                            f"found {len(row)}"
                        )
                    values = {name: row[indexes[name]] for name in _HEADERS}
                    bars.append(
                        self._parse_row(values, expected_symbol, path, line_number)
                    )
                return bars
        except UnicodeError as error:
            raise CSVSchemaError(f"CSV file is not valid UTF-8: {path}") from error
        except OSError as error:
            raise HistoricalDataNotFoundError(
                f"cannot read CSV file: {path}"
            ) from error

    @staticmethod
    def _validate_headers(headers: list[str], path: Path) -> None:
        if len(headers) != len(_HEADERS) or set(headers) != set(_HEADERS):
            raise CSVSchemaError(
                f"CSV headers for {path} must contain exactly: {', '.join(_HEADERS)}"
            )

    @staticmethod
    def _parse_row(
        values: dict[str, str],
        expected_symbol: Symbol,
        path: Path,
        line_number: int,
    ) -> Bar:
        try:
            for field_name, value in values.items():
                if not value or value != value.strip():
                    raise ValueError(f"{field_name} must be nonblank without padding")
            timestamp = datetime.fromisoformat(values["timestamp"])
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("timestamp must include a timezone")
            symbol = Symbol(values["symbol"])
            if symbol != expected_symbol:
                raise ValueError(
                    f"symbol {symbol} does not match expected {expected_symbol}"
                )
            prices = {
                name: Decimal(values[name]) for name in ("open", "high", "low", "close")
            }
            if any(not price.is_finite() for price in prices.values()):
                raise ValueError("prices must be finite")
            if _VOLUME_PATTERN.fullmatch(values["volume"]) is None:
                raise ValueError("volume must be a nonnegative base-10 integer")
            return Bar(
                symbol=symbol,
                timestamp=timestamp,
                open=prices["open"],
                high=prices["high"],
                low=prices["low"],
                close=prices["close"],
                volume=int(values["volume"]),
            )
        except (InvalidOperation, TypeError, ValueError) as error:
            raise CSVRowError(f"{path}:{line_number}: {error}") from error

    @staticmethod
    def _reject_duplicate_timestamps(bars: list[Bar], path: Path) -> None:
        for previous, current in zip(bars, bars[1:], strict=False):
            if previous.timestamp == current.timestamp:
                raise DuplicateBarTimestampError(
                    f"duplicate timestamp {current.timestamp.isoformat()} in {path}"
                )
