"""Immutable Architecture-133 supervised-release launcher.

Run only as production Python -I -S -B with zero semantic arguments.
Automatic site processing remains disabled; this launcher explicitly adds the
verified release source root and the fixed protected production site-packages
root before importing project code.
"""

import sys
from pathlib import Path

_FAILURE = '{"reason":"HOST_FAILED_CLOSED","schema":"arch133-host/v1"}'

if sys.argv[1:]:
    print('{"reason":"INVALID_ARGUMENTS","schema":"arch133-host/v1"}', file=sys.stderr)
    raise SystemExit(2)

if (
    not sys.flags.isolated
    or not sys.flags.no_site
    or not sys.dont_write_bytecode
    or "site" in sys.modules
    or "sitecustomize" in sys.modules
    or "usercustomize" in sys.modules
):
    print(_FAILURE, file=sys.stderr)
    raise SystemExit(3)

_NO_PYCACHE = Path(r"F:\AITradingBot\Arch133\no-pycache")
if _NO_PYCACHE.exists():
    print(_FAILURE, file=sys.stderr)
    raise SystemExit(3)
sys.pycache_prefix = str(_NO_PYCACHE)

_FINAL = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _FINAL / "src"
_SITE_PACKAGES = Path(r"F:\AITradingBot\runtime\Lib\site-packages")

_source = str(_SOURCE_ROOT)
_site = str(_SITE_PACKAGES)
if any(path.casefold() in {_source.casefold(), _site.casefold()} for path in sys.path):
    print(_FAILURE, file=sys.stderr)
    raise SystemExit(3)
sys.path[:0] = [_source, _site]

from trading_bot.review_paper.unattended_host import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
