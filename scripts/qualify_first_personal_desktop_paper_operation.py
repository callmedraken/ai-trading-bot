"""Thin entry point for the frozen read-only PD2D1 qualification."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.pd2d1_first_paper_qualification import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
