"""Canonical runtime signal-provider surface for the desktop prototype.

The implementation lives in ``alpaca_runtime_signal_provider`` so its focused
fake tests and the historical D34 pure builders have one semantic owner.
This compatibility surface follows the current Architecture 147 module name
without introducing a second refresh or cache policy.
"""

from trading_bot.live_prototype.alpaca_runtime_signal_provider import (
    AlpacaRuntimeSignalProvider,
    RuntimeSignalReason,
    RuntimeSignalSnapshot,
)

RuntimeSignalProvider = AlpacaRuntimeSignalProvider

__all__ = [
    "AlpacaRuntimeSignalProvider",
    "RuntimeSignalProvider",
    "RuntimeSignalReason",
    "RuntimeSignalSnapshot",
]
