"""Fixed-source D1R7 launcher; no D1 continuation."""

import sys
from pathlib import Path

ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-authorization")
if __name__ == "__main__":
    if Path(__file__).resolve() != (ROOT / "scripts" / "run_arch134_d1r7.py").resolve():
        raise SystemExit(2)
    sys.path.insert(0, str(ROOT / "src"))
    from trading_bot.review_paper.d1_session_authorization_host import main

    raise SystemExit(main())
