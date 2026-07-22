"""Shared pure derivation of portfolio state from public paper-ledger state."""

from decimal import Decimal

from trading_bot.ledger import PaperLedger
from trading_bot.portfolio import (
    InvalidPortfolioStateError,
    PortfolioPositionState,
    PortfolioState,
)
from trading_bot.runtime import PaperPortfolioCyclePrice
from trading_bot.simulation.exceptions import (
    PaperPortfolioSimulationStateDerivationError,
)

_ZERO = Decimal("0")


def derive_portfolio_state(
    ledger: PaperLedger,
    as_of,
    prices: tuple[PaperPortfolioCyclePrice, ...],
) -> PortfolioState:  # type: ignore[no-untyped-def]
    """Value current public ledger holdings in explicit supplied price order."""
    holdings = ledger.positions
    symbols = tuple(item.symbol for item in prices)
    missing = set(holdings) - set(symbols)
    if missing:
        names = ", ".join(sorted(str(item) for item in missing))
        raise PaperPortfolioSimulationStateDerivationError(
            f"frame prices and target omit held symbols: {names}"
        )
    try:
        positions = tuple(
            PortfolioPositionState(
                price.symbol,
                holdings[price.symbol].quantity if price.symbol in holdings else _ZERO,
                holdings[price.symbol].average_cost
                if price.symbol in holdings
                else _ZERO,
                price.risk_price,
            )
            for price in prices
        )
        exposure = sum((item.market_value for item in positions), start=_ZERO)
        return PortfolioState(as_of, positions, ledger.cash, ledger.cash + exposure)
    except InvalidPortfolioStateError as caught:
        raise PaperPortfolioSimulationStateDerivationError(
            "ledger and frame prices could not produce a valid portfolio state"
        ) from caught
