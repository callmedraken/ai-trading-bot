"""Thin entry point for one verified-snapshot paper-cycle run."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.verified_snapshot_paper_cycle import run_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_main())
