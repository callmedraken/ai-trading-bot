"""Fixed D1R9-owned D1R8 adapter; imports accepted consumer modules only."""

import sys
from pathlib import Path

ROOT = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-arbitrary-time-supervisor"
)
if __name__ == "__main__":
    if (
        Path(__file__).resolve()
        != (ROOT / "scripts/arch134_d1r9_d1r8_child.py").resolve()
    ):
        raise SystemExit(2)
    sys.path.insert(0, str(ROOT))
    from scripts.arch134_d1r9_bridge import child_main

    raise SystemExit(child_main("d1r8"))
