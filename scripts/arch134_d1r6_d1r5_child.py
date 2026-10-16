"""Fixed D1R5 child bridge; D1R6 trading_bot modules are never loaded here."""

import sys
from pathlib import Path

ROOT = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-premarket-wake-qualification"
)
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    from trading_bot.review_paper.pre_market_wake_qualification_host import main

    raise SystemExit(main())
