"""Fixed F1 launcher; source import and --help are inert."""

import sys
from pathlib import Path

ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-production-paper-134f-five-session-soak")
if __name__ == "__main__":
    if Path(__file__).resolve() != (ROOT / "scripts/run_arch134_f1.py").resolve():
        raise SystemExit(2)
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    from trading_bot.review_paper.five_session_soak_host import main

    raise SystemExit(main())
