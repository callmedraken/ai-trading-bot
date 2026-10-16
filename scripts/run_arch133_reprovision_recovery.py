"""Isolated fixed 133-W launcher; no protected effect is implied by source/CI."""

import re
import sys
from pathlib import Path

_SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133w")
_NO_PYCACHE = _SOURCE_ROOT / "no-pycache"
try:
    args = sys.argv[1:]
    valid = args == ["plan"] or (
        len(args) == 3
        and args[:2] == ["execute-once", "--reviewed-plan-sha256"]
        and re.fullmatch(r"[0-9a-f]{64}", args[2])
    )
    if (
        not valid
        or not sys.flags.isolated
        or not sys.dont_write_bytecode
        or Path(__file__).resolve().parents[1] != _SOURCE_ROOT.resolve(strict=True)
        or _NO_PYCACHE.exists()
    ):
        raise ValueError
    sys.pycache_prefix = str(_NO_PYCACHE)
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))
    from trading_bot.arch133_reprovision_recovery.operator import main
except BaseException:
    print("ARCH133W_RUNTIME_BLOCKED")
    raise SystemExit(3) from None

if __name__ == "__main__":
    raise SystemExit(main())
