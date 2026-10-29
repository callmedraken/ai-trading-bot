"""Source-bound launcher for separately reviewed B2 read-only host observation."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT != Path(r"F:\AI\worktrees\ai-trading-bot-146b-pre-b2-readiness-current"):
    raise SystemExit("STOP: exact reviewed F: worktree required")
sys.path.insert(0, str(ROOT / "src"))

from trading_bot.experiments.historical_research_b2_preflight import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
