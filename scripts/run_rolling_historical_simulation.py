"""Thin entry point for the offline rolling historical simulation CLI."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.rolling_historical import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
