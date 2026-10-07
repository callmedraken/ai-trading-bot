"""133-K isolated operator surface; source verification never runs this command."""

import sys
from pathlib import Path

if not sys.flags.isolated or not sys.dont_write_bytecode:
    print('{"reason":"RETAINED_RECOVERY_RUNTIME_REJECTED"}', file=sys.stderr)
    raise SystemExit(3)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trading_bot.arch133_acl.recovery import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
