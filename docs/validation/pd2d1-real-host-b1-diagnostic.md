# PD2D1 real-host B1 read-only diagnostic

## Scope and stage model

This temporary one-shot harness isolates only the genuine PD2B1 boundary:

```text
C1
-> pre-lock Paper-v2 account read and exact GENESIS reconciliation
-> PD2A admission construction
-> exact source-owned mutex acquisition
-> post-lock Paper-v2 account read and exact GENESIS reconciliation
-> mutex release
```

It stops after release. It does not read P2 or selected C3, load the F2 seed,
plan a strategy, prepare a verified cycle, construct an operation intent or
execution inputs, inspect or execute Architecture 67, create a transition or
receipt, recover, schedule, call a provider or broker, enable an effect gate,
or authorize PD2D2. It performs no persistent filesystem mutation.

The explicit result stages and exit codes are:

```text
INVALID_ARGUMENTS                         2
PREFLIGHT_BLOCKED                         3
C1_BLOCKED                                4
PRE_LOCK_ACCOUNT_READ_BLOCKED             5
MUTEX_ADMISSION_CONSTRUCTION_BLOCKED      6
MUTEX_ACQUIRE_BLOCKED                     7
MUTEX_ACQUIRE_RECONCILIATION_BLOCKED      7
ABANDONED_OWNER_RECONCILIATION_REQUIRED   7
POST_LOCK_ACCOUNT_READ_BLOCKED            8
POST_LOCK_ACCOUNT_RECONCILIATION_BLOCKED  8
MUTEX_RELEASE_BLOCKED                     9
B1_READY                                  0
```

An acquired admission is released exactly once, including after abandoned or
unexpected acquisition state and after post-lock failure. A release failure
overrides an earlier post-lock result and fails closed. There is no retry.

## Frozen evidence and safe diagnostics

The harness requires exact production machine/epoch/Trading SID identity, the
accepted publication freeze, account `9415cd7b-bf36-5fba-bd58-a0f99119dc21`,
GENESIS terminal `1832a2b5-8b63-501a-8f7d-f1722c32307b`, no successors,
reports, snapshots, or receipts, no historical configuration dependencies, and
the exact source-owned operation root. It never prints the root, mutex name,
digest, handle, or raw authority/account object.

Blocked results may contain only a fixed allowlisted `exception_family`.
`WindowsNativeError` may additionally expose an exact integer-or-`null` error
code and a source-allowlisted operation. Exception messages, dynamic class
names, native formatted messages, paths, handles, tokens, and arbitrary text
are never emitted.

## Future operator command — frozen, not executed

Run this only after ChatGPT/Sol source review, exactly once, as the non-elevated
`DESKTOP-I4DOKM7\Trading` principal:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$Python = 'F:\AITradingBot\runtime\python.exe'
$Script = 'F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\diagnose_pd2d1_b1_readonly.py'
& $Python -B $Script
$LASTEXITCODE
```

Use no arguments, redirection, transcript, or log. Do not change an ACL,
account, group, or LSA right, and do not rerun after any result without a new
review. This command is recorded only; it was not executed during source
implementation or verification.
