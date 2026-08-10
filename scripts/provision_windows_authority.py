"""Run the explicit administrator Windows-authority command."""

from __future__ import annotations

import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPOSITORY_ROOT / "src"))

from trading_bot.cli.windows_authority import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
