"""Source-owned D1 ACL entry point; protected execution needs fresh authority."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
_CACHE_ROOT = Path(r"F:\AITradingBot\Arch134D1\no-pycache")
if _CACHE_ROOT.exists():
    print(
        '{"schema":"production-paper-runtime-acl/v1","status":"BLOCKED","result":"FAIL"}'
    )
    raise SystemExit(3)
sys.pycache_prefix = str(_CACHE_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trading_bot.review_paper.production_paper_runtime_acl import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
