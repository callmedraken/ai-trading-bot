"""133-N isolated zero-semantic-argument publication/state/paper diagnostic."""

import sys
from pathlib import Path

_FAILURE = "ARCH133N_RUNTIME_BLOCKED"
_SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133n")
_NO_PYCACHE = _SOURCE_ROOT / "no-pycache"

try:
    if (
        sys.argv[1:]
        or not sys.flags.isolated
        or not sys.dont_write_bytecode
        or Path(__file__).resolve().parents[1] != _SOURCE_ROOT.resolve(strict=True)
        or _NO_PYCACHE.exists()
    ):
        raise ValueError
    sys.pycache_prefix = str(_NO_PYCACHE)
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))
    from trading_bot.arch133_publication_diagnostic.operator import main
except BaseException:
    print(_FAILURE)
    raise SystemExit(3) from None

if __name__ == "__main__":
    raise SystemExit(main())
