"""Fixed Architecture-133 launcher; Python -I -B, zero semantic arguments."""

import sys
from pathlib import Path

# Reject secret-bearing input without importing the trading package or reading
# publication. This agrees with the host's independently enforced CLI contract.
if sys.argv[1:]:
    print('{"reason":"INVALID_ARGUMENTS","schema":"arch133-host/v1"}', file=sys.stderr)
    raise SystemExit(2)

# -B prevents writes, not reads of existing ignored bytecode. Select an absent
# dedicated cache namespace before importing source; never create or repair it.
_NO_PYCACHE = Path(r"F:\AITradingBot\Arch133\no-pycache")
if _NO_PYCACHE.exists():
    print('{"reason":"HOST_FAILED_CLOSED","schema":"arch133-host/v1"}', file=sys.stderr)
    raise SystemExit(3)
sys.pycache_prefix = str(_NO_PYCACHE)

_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.review_paper.unattended_host import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
