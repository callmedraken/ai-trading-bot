"""Zero-argument Architecture-133 pre-publication bootstrap launcher."""

import os
import sys
from pathlib import Path

if sys.argv[1:]:
    print(
        '{"reason":"INVALID_ARGUMENTS","schema":"arch133-host-bootstrap/v1"}',
        file=sys.stderr,
    )
    raise SystemExit(2)

# Prove the dedicated cache namespace is absent before importing trading source.
_NO_PYCACHE = Path(r"F:\AITradingBot\Arch133\no-pycache")
try:
    os.stat(_NO_PYCACHE, follow_symlinks=False)
except FileNotFoundError:
    pass
except OSError:
    print(
        '{"reason":"HOST_BOOTSTRAP_FAILED_CLOSED",'
        '"schema":"arch133-host-bootstrap/v1"}',
        file=sys.stderr,
    )
    raise SystemExit(3)
else:
    print(
        '{"reason":"HOST_BOOTSTRAP_FAILED_CLOSED",'
        '"schema":"arch133-host-bootstrap/v1"}',
        file=sys.stderr,
    )
    raise SystemExit(3)

sys.pycache_prefix = str(_NO_PYCACHE)
_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.review_paper.unattended_host_bootstrap import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
