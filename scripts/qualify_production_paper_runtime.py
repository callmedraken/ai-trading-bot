"""D1Q runtime qualification only; real effects require separate authorization."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
_CACHE_ROOT = Path(r"F:\AITradingBot\Arch134D1\no-pycache")
if _CACHE_ROOT.exists():
    print(
        '{"schema":"production-paper-runtime-qualification/v1","status":"BLOCKED"}',
        file=sys.stderr,
    )
    raise SystemExit(3)
sys.pycache_prefix = str(_CACHE_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trading_bot.review_paper.production_paper_runtime import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
