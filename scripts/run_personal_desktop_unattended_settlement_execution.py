"""Run the D8-B settlement launcher from this source checkout under python -I."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.pd4_unattended_settlement_execution import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
