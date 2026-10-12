"""Manually arm one Architecture-134-D1 session; no trading-semantic arguments."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
_CACHE_ROOT = Path(r"F:\AITradingBot\Arch134D1\no-pycache")
if _CACHE_ROOT.exists():
    print('{"schema":"armed-paper-host/v1","status":"BLOCKED"}', file=sys.stderr)
    raise SystemExit(3)
sys.pycache_prefix = str(_CACHE_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trading_bot.review_paper.armed_session_host import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
