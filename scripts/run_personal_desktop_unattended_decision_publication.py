"""Run the Architecture-113 D6 decision-only launcher from this checkout."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.cli.personal_desktop_unattended_decision_publication_launcher import (  # noqa: E402
    main,
)

if __name__ == "__main__":
    raise SystemExit(main())
