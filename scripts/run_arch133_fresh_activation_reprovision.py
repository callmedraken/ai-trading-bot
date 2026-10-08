"""Isolated fixed 133-Q launcher; no protected effect is implied by source/CI."""

import re
import sys
from pathlib import Path

_SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133q")
_NO_PYCACHE = _SOURCE_ROOT / "no-pycache"
try:
    args = sys.argv[1:]
    valid = (len(args) == 3 and args[0] == "plan" and args[1] == "--material-file") or (
        len(args) == 5
        and args[0] == "execute-once"
        and args[1] == "--material-file"
        and args[3] == "--reviewed-plan-sha256"
        and re.fullmatch(r"[0-9a-f]{64}", args[4])
    )
    if (
        not valid
        or not Path(args[2]).is_absolute()
        or not sys.flags.isolated
        or not sys.dont_write_bytecode
        or Path(__file__).resolve().parents[1] != _SOURCE_ROOT.resolve(strict=True)
        or _NO_PYCACHE.exists()
    ):
        raise ValueError
    sys.pycache_prefix = str(_NO_PYCACHE)
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))
    from trading_bot.arch133_reprovision.operator import main
except BaseException:
    print("ARCH133Q_RUNTIME_BLOCKED")
    raise SystemExit(3) from None

if __name__ == "__main__":
    raise SystemExit(main())
