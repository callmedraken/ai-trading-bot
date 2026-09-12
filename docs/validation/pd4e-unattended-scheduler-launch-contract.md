# PD4-E Unattended Scheduler Launch Contract

Status: **FROZEN SOURCE ONLY — NO TASK OR PAPER EFFECT AUTHORIZATION**

The Windows Task Scheduler is an untrusted wake-up source only. The source-owned
task action selected by PD4-E is:

```text
program:
F:\AITradingBot\runtime\python.exe

launcher:
F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\run_personal_desktop_unattended_paper_operation.py

launcher semantic arguments:
none
```

The launcher selects the adjacent checkout's `src` directory from its own
resolved path. Its package selection therefore does not depend on Task
Scheduler's working directory, ambient `PYTHONPATH`, a developer virtual
environment, or another installed `trading_bot` package.

The task principal is exactly `DESKTOP-I4DOKM7\Trading`, SID
`S-1-5-21-1397534616-3988210162-180023805-1009`, running non-admin and
non-elevated. No credential material or semantic trading configuration may be
placed in task action arguments or scheduler-owned environment variables.

The scheduler may not select, override, or derive the paper account, Trading
SID, authority/database/Paper-v2 paths, transition or operation identity,
caller idempotency UUID, strategy configuration, risk policy, selected
snapshot, provider or broker identity, recovery target, or effect-gate state.

Working directory, trigger time/count, next-run time, task history, previous
exit, process lifetime, and task state are diagnostics only. No final trigger
time or trading-session eligibility policy is frozen here; a later reviewed
timing/session boundary is required before real unattended execution.

Task overlap settings are defense in depth only. The existing PD2A
paper-account mutex remains the authoritative account overlap control, and
Architecture 67 remains the durable duplicate/idempotency authority.

The PD4-E launcher only validates this contract and the closed state of all six
Paper-v2 effect gates. It performs no semantic startup qualification because
Architecture 110 has not frozen a zero-argument snapshot/session acquisition
rule. It publishes no invocation bundle and performs no Paper-v2 execution,
receipt recovery, provider call, broker call, or live action.

Creating, modifying, enabling, disabling, deleting, or running the Windows
scheduled task requires a separate explicit future Windows effect checkpoint.
