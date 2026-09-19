"""Thin entry point for the read-only PD2D1 preparation diagnostic."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.pd2d1_preparation_readonly_diagnostic import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
