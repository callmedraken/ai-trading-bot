"""Fixed D1R9 launcher; source import and --help are inert."""

import sys
from pathlib import Path

ROOT = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-arbitrary-time-supervisor"
)
if __name__ == "__main__":
    if Path(__file__).resolve() != (ROOT / "scripts/run_arch134_d1r9.py").resolve():
        raise SystemExit(2)
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    from trading_bot.review_paper.d1_session_supervisor_host import main

    raise SystemExit(main())
