# PD2D1 real-host preparation read-only diagnostic

## Scope and stage model

This temporary one-shot harness isolates the exact frozen first-cycle path
through successful active PD2B3 preparation, then stops before Architecture-67
inspection:

```text
preflight
-> genuine C1
-> genuine P2 frozen selection
-> frozen F1/F2 input construction
-> PD2B3 preparation construction
-> preparation entry (P2 revalidation, B1, P1 build/replay, intent and inputs)
-> active preparation and private binding reconciliation
-> preparation release
-> stop
```

Construction does not enter the mutex. Entry occurs once, the private binding
is read only while the preparation remains active, and release occurs once.
After successful entry, every body outcome including `KeyboardInterrupt` and
`SystemExit` releases before the original `BaseException` is re-raised. A
release failure fails closed and is never retried.

The harness never imports or calls the Architecture-67 inspector, qualification
boundary, executor, transition/receipt writers, provider capture, broker API,
scheduler, or recovery mutation. It never serializes or emits execution inputs,
the operation root, the binding, paths, handles, mutex material, credentials, or
raw authority/account/preparation objects.

## Safe results

Success is the compact schema
`pd2d1-preparation-readonly-diagnostic/v1` with result
`PREPARATION_READY`. It reports only frozen identities, prepared UUIDs, the
GENESIS terminal, `OWNED`, exact-root match, active-binding verification, and
confirmation that all three effect gates are exactly false.

Blocked stages are fixed: `PREFLIGHT_BLOCKED`, `C1_BLOCKED`, `P2_BLOCKED`,
`PREPARATION_CONSTRUCTION_BLOCKED`, `PREPARATION_ENTER_BLOCKED`,
`ACTIVE_PREPARATION_RECONCILIATION_BLOCKED`, and
`PREPARATION_RELEASE_BLOCKED`. Their exception detail is limited to a fixed
allowlisted family. `WindowsNativeError` may additionally expose only an
allowlisted operation and an exact integer-or-null error code. Exception text
and dynamic class names are never emitted.

## Future operator command — frozen, not executed

Run this only after ChatGPT/Sol exact source review, exactly once, as the
non-elevated `DESKTOP-I4DOKM7\Trading` principal:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$Python = 'F:\AITradingBot\runtime\python.exe'
$Script = 'F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\diagnose_pd2d1_preparation_readonly.py'
& $Python -B $Script
$LASTEXITCODE
```

Use no arguments, redirection, transcript, or log. Do not rerun after any
result without a new review. This command is frozen only; it was not executed
during implementation or source verification. The result cannot authorize
PD2D2 or any Paper-v2 mutation.
