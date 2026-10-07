"""133-L isolated zero-semantic-argument post-publication verifier only."""

import sys
from pathlib import Path

_FAILURE = (
    '{"reason":"POST_PUBLICATION_VERIFIER_FAILED_CLOSED",'
    '"schema":"arch133l-post-publication-verifier/v1","status":"FAILED_CLOSED"}'
)
_SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133l")
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
    # An absent cache namespace prevents stale ignored bytecode reads.
    sys.pycache_prefix = str(_NO_PYCACHE)
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))
    from trading_bot.arch133_verifier.operator import main
except BaseException:
    print(_FAILURE)
    raise SystemExit(3) from None

if __name__ == "__main__":
    raise SystemExit(main())
