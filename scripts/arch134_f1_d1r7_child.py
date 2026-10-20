"""Fixed F1-owned D1R7 adapter; imports accepted producer modules only."""

import sys
from pathlib import Path

ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-production-paper-134f-five-session-soak")
if __name__ == "__main__":
    if (
        Path(__file__).resolve()
        != (ROOT / "scripts/arch134_f1_d1r7_child.py").resolve()
    ):
        raise SystemExit(2)
    sys.path.insert(0, str(ROOT))
    from scripts.arch134_f1_bridge import child_main

    raise SystemExit(child_main("d1r7"))
