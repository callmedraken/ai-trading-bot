"""Run the frozen PD3 read-only recovery validation harness."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.pd3_read_only_recovery_validation import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
