"""Isolated Architecture 133-R zero-effect admission diagnostic launcher."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133r")
_NO_PYCACHE = _SOURCE_ROOT / "no-pycache"
try:
    args = sys.argv[1:]
    if (
        len(args) != 2
        or args[0] != "--material-file"
        or not Path(args[1]).is_absolute()
        or not sys.flags.isolated
        or not sys.dont_write_bytecode
        or Path(__file__).resolve().parents[1] != _SOURCE_ROOT.resolve(strict=True)
        or _NO_PYCACHE.exists()
    ):
        raise ValueError
    sys.pycache_prefix = str(_NO_PYCACHE)
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))
    from trading_bot.arch133_reprovision_diagnostic.operator import main
except BaseException:
    print(
        '{"reason":"ARCH133R_RUNTIME_BLOCKED","schema":"arch133r-reprovision-admission-diagnostic/v1","status":"BLOCKED"}'
    )
    raise SystemExit(3) from None

if __name__ == "__main__":
    raise SystemExit(main())
