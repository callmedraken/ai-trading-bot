"""Run the PD4 O2 operator observability snapshot from this checkout."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.pd4_operator_observability_snapshot import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
