"""Application configuration with fail-closed safety defaults."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TradingBotConfig:
    """Configuration for the paper-only research platform."""

    starting_cash: Decimal = Decimal("10000.00")
    paper_trading: bool = True
    allow_margin: bool = False
    allow_short_selling: bool = False
    allow_options: bool = False
    allow_crypto: bool = False

    def __post_init__(self) -> None:
        """Reject unsafe or invalid settings."""
        if not isinstance(self.starting_cash, Decimal):
            raise TypeError("starting_cash must be a Decimal")
        if self.starting_cash <= Decimal("0"):
            raise ValueError("starting_cash must be greater than zero")
        if self.paper_trading is not True:
            raise ValueError("paper_trading must remain enabled")

        prohibited = {
            "allow_margin": self.allow_margin,
            "allow_short_selling": self.allow_short_selling,
            "allow_options": self.allow_options,
            "allow_crypto": self.allow_crypto,
        }
        enabled = [name for name, value in prohibited.items() if value is not False]
        if enabled:
            names = ", ".join(enabled)
            raise ValueError(f"prohibited features cannot be enabled: {names}")
