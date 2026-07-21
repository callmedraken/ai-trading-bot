"""Source-independent historical market-data provider contract."""

from typing import Protocol

from trading_bot.market_data.models import (
    HistoricalDataRequest,
    HistoricalDataResult,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
)


class HistoricalDataProvider(Protocol):
    """Structural interface implemented by historical-data sources."""

    def get_bars(self, request: HistoricalDataRequest) -> HistoricalDataResult:
        """Return validated bars for a historical-data request."""
        ...


class MultiSymbolHistoricalDataProvider(Protocol):
    """Structural interface for aligned multi-symbol historical data."""

    def get_bars(
        self, request: MultiSymbolHistoricalDataRequest
    ) -> MultiSymbolHistoricalDataResult:
        """Return exact-timestamp frames for an ordered symbol universe."""
        ...
