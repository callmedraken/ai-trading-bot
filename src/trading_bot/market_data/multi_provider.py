"""Multi-symbol coordination over an existing single-symbol provider."""

from trading_bot.market_data.exceptions import (
    EmptyAlignedHistoricalDataError,
    InconsistentProviderResultError,
)
from trading_bot.market_data.models import (
    AlignedMarketFrame,
    HistoricalDataRequest,
    HistoricalDataResult,
    MissingBarPolicy,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
)
from trading_bot.market_data.provider import HistoricalDataProvider


class CoordinatingHistoricalDataProvider:
    """Load symbols sequentially and align their exact UTC timestamps."""

    def __init__(self, single_symbol_provider: HistoricalDataProvider) -> None:
        if not hasattr(single_symbol_provider, "get_bars"):
            raise TypeError("single_symbol_provider must implement get_bars")
        self._single_symbol_provider = single_symbol_provider
        provider_type = type(single_symbol_provider)
        self._provider_name = (
            f"coordinating:{provider_type.__module__}.{provider_type.__qualname__}"
        )

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def get_bars(
        self, request: MultiSymbolHistoricalDataRequest
    ) -> MultiSymbolHistoricalDataResult:
        if not isinstance(request, MultiSymbolHistoricalDataRequest):
            raise TypeError("request must be a MultiSymbolHistoricalDataRequest")
        results = []
        for symbol in request.symbols:
            child_request = HistoricalDataRequest(
                symbol,
                request.start,
                request.end,
                request.timeframe,
                request.adjustment,
            )
            result = self._single_symbol_provider.get_bars(child_request)
            if not isinstance(result, HistoricalDataResult):
                raise InconsistentProviderResultError(
                    "constituent provider must return HistoricalDataResult"
                )
            if result.request != child_request:
                raise InconsistentProviderResultError(
                    "constituent result request does not match its derived request"
                )
            results.append(result)

        timestamps_by_symbol = {
            result.request.symbol: {bar.timestamp for bar in result.bars}
            for result in results
        }
        timestamp_sets = tuple(timestamps_by_symbol.values())
        if request.missing_bar_policy is MissingBarPolicy.UNION:
            aligned_timestamps = set().union(*timestamp_sets)
        else:
            aligned_timestamps = set.intersection(*timestamp_sets)
        if not aligned_timestamps:
            raise EmptyAlignedHistoricalDataError(
                "multi-symbol alignment produced no frames"
            )

        indexed = {
            result.request.symbol: {bar.timestamp: bar for bar in result.bars}
            for result in results
        }
        frames = tuple(
            AlignedMarketFrame(
                timestamp,
                request.symbols,
                {
                    symbol: indexed[symbol][timestamp]
                    for symbol in request.symbols
                    if timestamp in indexed[symbol]
                },
            )
            for timestamp in sorted(aligned_timestamps)
        )
        return MultiSymbolHistoricalDataResult(request, frames, self._provider_name)
