# Fixed zero-argument scheduler wake signal. Source and D1R5 remain authoritative.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($args.Count -ne 0) { exit 2 }
try {
    & 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -I -B 'F:\AI\worktrees\ai-trading-bot-production-paper-overnight-wake-arming\scripts\run_arch134_d1r6.py' launch
    exit $LASTEXITCODE
} catch { exit 2 }
