"""Isolated Architecture 133-S zero-effect admission diagnostic launcher."""

import hashlib
import json
import sys
from pathlib import Path

_SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133s")
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
        or sys.platform != "win32"
        or Path(sys.executable).resolve(strict=True)
        != Path(r"F:\AITradingBot\runtime\python.exe").resolve(strict=True)
        or ".".join(map(str, sys.version_info[:3])) != "3.14.3"
        or hashlib.sha256(
            Path(r"F:\AITradingBot\runtime\python.exe").read_bytes()
        ).hexdigest()
        != "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
    ):
        raise ValueError
    sys.pycache_prefix = str(_NO_PYCACHE)
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))
    from trading_bot.arch133_parent_security_diagnostic.operator import main
except BaseException:
    print(
        json.dumps(
            {
                "reason": "PARENT_SECURITY_DIAGNOSTIC_BLOCKED",
                "schema": "arch133s-parent-security-diagnostic/v1",
                "status": "BLOCKED",
                "stage": "PREDECESSOR_RUNTIME",
                "credential_reads": 0,
                "credential_writes": 0,
                "provider_calls": 0,
                "scheduler_reads": 0,
                "scheduler_writes": 0,
                "publication_writes": 0,
                "archive_writes": 0,
                "paper_mutations": 0,
                "state_mutations": 0,
                "acl_mutations": 0,
                "wake_delegations": 0,
                "execution_delegations": 0,
                "consumed_wake_authority": 0,
                "broker_effects": 0,
                "manual_task_starts": 0,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    raise SystemExit(3) from None

if __name__ == "__main__":
    raise SystemExit(main())
