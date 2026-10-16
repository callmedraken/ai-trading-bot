"""133-M isolated zero-semantic-argument credential-free stage diagnostic."""

import sys
from pathlib import Path

_FAILURE = (
    '{"acl_mutations":0,"broker_effects":0,"consumed_wake_authority":0,'
    '"credential_reads":0,"credential_writes":0,"execution_delegations":0,'
    '"paper_mutations":0,"provider_calls":0,'
    '"reason":"POST_PUBLICATION_STAGE_DIAGNOSTIC_BLOCKED",'
    '"scheduler_reads":0,"scheduler_writes":0,'
    '"schema":"arch133m-post-publication-stage-diagnostic/v1",'
    '"stage":"RUNTIME_SOURCE","state_mutations":0,"status":"BLOCKED",'
    '"wake_delegations":0}'
)
_SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133m")
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
    # An absent private cache namespace prevents stale ignored bytecode reads.
    sys.pycache_prefix = str(_NO_PYCACHE)
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))
    from trading_bot.arch133_diagnostic.operator import main
except BaseException:
    print(_FAILURE)
    raise SystemExit(3) from None

if __name__ == "__main__":
    raise SystemExit(main())
