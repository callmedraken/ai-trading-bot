"""Isolated fixed-path Y scratch launcher; real execution needs later TTY authority."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133y")
_NO_PYCACHE = _SOURCE_ROOT / "no-pycache"
try:
    if (
        sys.argv[1:]
        or not sys.flags.isolated
        or not sys.dont_write_bytecode
        or Path(__file__).resolve().parents[1] != _SOURCE_ROOT.resolve(strict=True)
        or _NO_PYCACHE.exists()
        or _NO_PYCACHE.is_symlink()
        or _NO_PYCACHE.is_junction()
    ):
        raise ValueError
    sys.pycache_prefix = str(_NO_PYCACHE)
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))
    from trading_bot.arch133_windows_rename_qualification.operator import main
except BaseException:
    print(
        '{"schema":"arch133y-windows-rename-qualification/v1","status":"BLOCKED",'
        '"disposition":"QUALIFICATION_REJECTED","credential_reads":0,'
        '"credential_writes":0,"provider_calls":0,"scheduler_reads":0,'
        '"scheduler_writes":0,"publication_writes":0,"archive_writes":0,'
        '"paper_mutations":0,"state_mutations":0,"acl_mutations":0,'
        '"wake_delegations":0,"execution_delegations":0,"consumed_wake_authority":0,'
        '"broker_effects":0,"manual_task_starts":0,"scratch":{'
        '"topology_creation_attempts":0,"topology_creations_completed":0,'
        '"first_rename_attempts":0,"first_renames_completed":0,'
        '"second_rename_attempts":0,"second_renames_completed":0,'
        '"cleanup_attempts":0,"cleanups_completed":0}}'
    )
    raise SystemExit(3) from None

if __name__ == "__main__":
    raise SystemExit(main())
