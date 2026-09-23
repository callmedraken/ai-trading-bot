"""Run the PD4 D8-R1 read-only settlement qualifier from this checkout."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.pd4_read_only_single_deferred_settlement_qualification import (  # noqa: E402
    main,
)

if __name__ == "__main__":
    raise SystemExit(main())
