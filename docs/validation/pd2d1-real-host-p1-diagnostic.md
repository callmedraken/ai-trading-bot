# PD2D1 real-host P1 read-only diagnostic

## Scope and stage model

This temporary one-shot harness isolates only P1 inside the genuine production
composition:

```text
preflight
-> genuine C1
-> genuine P2 frozen selection
-> genuine supervised B1 entry
-> post-lock account and GENESIS reconciliation
-> exact frozen P1 request construction
-> P1 build
-> detached P1 replay verification
-> exact binding reconciliation
-> B1 release
-> stop
```

The genuine B1 scope remains active throughout request construction, build,
replay, and reconciliation. It requires `OWNED`, the exact post-lock account,
the GENESIS prior, and the fixed operation root. After successful B1 entry,
every body outcome including `KeyboardInterrupt` and `SystemExit` releases the
scope before re-raising the original `BaseException`. A release failure
overrides an ordinary body result, fails closed, and is never retried.

The harness stops before `PaperOperationIntent`, Architecture-67 binding or
inspection, execution inputs, PD2B3 active bindings, qualification, execution,
transition/receipt writing, recovery, providers, brokers, and schedulers. It
does not emit artifact bytes, request payloads, paths, operation-root text, or
raw authority, account, plan, or preparation objects.

## Safe results

Success uses schema `pd2d1-p1-readonly-diagnostic/v1` and result `P1_READY`.
It emits only the accepted authority/account/selection/seed/GENESIS identities,
`OWNED`, plan and request UUIDs, detached artifact SHA-256 and byte length, and
confirmation that all three effect gates are false.

Blocked stages are `PREFLIGHT_BLOCKED`, `C1_BLOCKED`, `P2_BLOCKED`,
`B1_ENTER_BLOCKED`, `P1_REQUEST_BLOCKED`, `P1_BUILD_BLOCKED`,
`P1_REPLAY_BLOCKED`, `P1_RECONCILIATION_BLOCKED`, and `B1_RELEASE_BLOCKED`.
Exception detail is limited to fixed type-based families. `WindowsNativeError`
may additionally expose only an allowlisted operation and exact integer-or-null
error code. Exception text and dynamic class names are never emitted.

## Future operator command — frozen, not executed

Run this only after ChatGPT/Sol exact source review, exactly once, as the
non-elevated `DESKTOP-I4DOKM7\Trading` principal:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$Python = 'F:\AITradingBot\runtime\python.exe'
$Script = 'F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\diagnose_pd2d1_p1_readonly.py'
& $Python -B $Script
$LASTEXITCODE
```

Use no arguments, redirection, transcript, or log. Do not rerun after any
result without a new review. This command is frozen only and was not executed
during implementation or source verification. Its result cannot authorize
PD2D2 or any Paper-v2 mutation.
