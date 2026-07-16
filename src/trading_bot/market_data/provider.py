"""Source-independent historical market-data provider contract."""

from typing import Protocol

from trading_bot.market_data.models import HistoricalDataRequest, HistoricalDataResult


class HistoricalDataProvider(Protocol):
    """Structural interface implemented by historical-data sources."""

    def get_bars(self, request: HistoricalDataRequest) -> HistoricalDataResult:
        """Return validated bars for a historical-data request."""
        ...
