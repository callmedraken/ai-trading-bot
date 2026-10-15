"""Isolated fixed-source D1R7 launcher; no editable-install authority."""

import sys
from pathlib import Path

ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-production-paper-stale-wake-retirement")
if __name__ == "__main__":
    if Path(__file__).resolve() != (ROOT / "scripts" / "run_arch134_d1r7.py").resolve():
        raise SystemExit(2)
    sys.path.insert(0, str(ROOT / "src"))
    from trading_bot.review_paper.pre_market_wake_retirement_host import main

    raise SystemExit(main())
