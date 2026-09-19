# PD2D1 Real-Host Read-Only Operator Harness

## Scope

This record freezes the future one-shot command for the exact PD2D1 real-host
read-only qualification. It does not authorize or perform that qualification,
does not authorize PD2D2, and does not authorize any Paper-v2 mutation.

The command must run as `DESKTOP-I4DOKM7\Trading` using a non-elevated token.
Run it only at the separately reviewed real-host checkpoint.

## Frozen PowerShell command

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$Python = 'F:\AITradingBot\runtime\python.exe'
$Script = 'F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\qualify_first_personal_desktop_paper_operation.py'
& $Python -B $Script
$LASTEXITCODE
```

Do not execute this command as part of source implementation or source
verification. Do not add arguments, output redirection, a transcript, or a log
file. Copy the terminal output manually for review.

## Operator stop rules

- Confirm the shell is the dedicated `DESKTOP-I4DOKM7\Trading` account and is
  non-elevated before invocation.
- Any access-denied condition is a STOP. Do not change ACLs, accounts, groups,
  or LSA rights to make the command run.
- Any exception, nonzero ambiguous result, or `NOT_READY` result is a STOP. Do
  not blindly rerun the harness.
- Do not redirect stdout or stderr and do not create a report or log file.
- `READY` is point-in-time, non-authorizing evidence only. It does not
  authorize PD2D2, enable the supervised-execution effect gate, or authorize
  the first durable Paper-v2 mutation.
- The first mutation remains protected by its separate source review,
  real-host revalidation, one-shot command review, and fresh explicit user
  authorization.

## Real-host attempt status

Attempt 1 is consumed. Do not rerun the harness from commit `564fdf8`.
The meaningful F3-R1 run from `94a7509` remained generically blocked outside
the classified typed boundaries. The full qualification is paused pending the
narrower B1 stage-isolation diagnostic documented in
`pd2d1-real-host-b1-diagnostic.md`. Do not rerun the full qualification while
that isolation is pending. Even a future `READY` result would remain
non-authorizing and would not authorize PD2D2.
