"""Public API for deterministic offline historical market data."""

from trading_bot.market_data.csv_provider import CSVHistoricalDataProvider
from trading_bot.market_data.exceptions import (
    CSVRowError,
    CSVSchemaError,
    DuplicateBarTimestampError,
    DuplicateRequestedSymbolError,
    EmptyAlignedHistoricalDataError,
    HistoricalDataError,
    HistoricalDataNotFoundError,
    HistoricalDataValidationError,
    InconsistentProviderResultError,
    InvalidHistoricalDataRequestError,
    InvalidHistoricalDataResultError,
    InvalidMultiSymbolHistoricalDataRequestError,
    InvalidMultiSymbolHistoricalDataResultError,
    UnsupportedAdjustmentError,
    UnsupportedTimeframeError,
)
from trading_bot.market_data.fingerprints import (
    canonical_multi_symbol_historical_material,
)
from trading_bot.market_data.models import (
    AdjustmentType,
    AlignedMarketFrame,
    HistoricalDataRequest,
    HistoricalDataResult,
    MissingBarPolicy,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
    SymbolBars,
    Timeframe,
)
from trading_bot.market_data.multi_provider import CoordinatingHistoricalDataProvider
from trading_bot.market_data.provider import (
    HistoricalDataProvider,
    MultiSymbolHistoricalDataProvider,
)

__all__ = [
    "AdjustmentType",
    "AlignedMarketFrame",
    "CSVHistoricalDataProvider",
    "canonical_multi_symbol_historical_material",
    "CSVRowError",
    "CSVSchemaError",
    "DuplicateBarTimestampError",
    "DuplicateRequestedSymbolError",
    "EmptyAlignedHistoricalDataError",
    "HistoricalDataError",
    "HistoricalDataNotFoundError",
    "HistoricalDataProvider",
    "HistoricalDataRequest",
    "HistoricalDataResult",
    "HistoricalDataValidationError",
    "InvalidHistoricalDataRequestError",
    "InvalidHistoricalDataResultError",
    "InvalidMultiSymbolHistoricalDataRequestError",
    "InvalidMultiSymbolHistoricalDataResultError",
    "InconsistentProviderResultError",
    "MissingBarPolicy",
    "MultiSymbolHistoricalDataProvider",
    "MultiSymbolHistoricalDataRequest",
    "MultiSymbolHistoricalDataResult",
    "CoordinatingHistoricalDataProvider",
    "SymbolBars",
    "Timeframe",
    "UnsupportedAdjustmentError",
    "UnsupportedTimeframeError",
]
