"""Thin entry point for the secret-free Windows isolated-child launcher."""

# ruff: noqa: I001

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.isolated_capture_launcher import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
