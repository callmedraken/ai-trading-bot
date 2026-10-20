# Architecture 134 — future production operator lifecycle: reboot means stop

Status: **PRODUCT REQUIREMENT FROZEN; future source design/implementation required.**
This requirement does not modify the active Architecture 134-F1 five-session soak.

## Intent

For the eventual operator-facing production deployment, an intentional Windows
shutdown or reboot is an operator stop action. Turning the computer back on or
logging in must not itself resume trading.

The desired lifecycle is:

```text
RUNNING
-> operator shuts down/restarts Windows
-> STOPPED across boot/login
-> optional read-only state/status reconciliation
-> explicit operator start
-> fresh source/runtime/admission checks
-> RUNNING
```

## Required production semantics

Future production scheduler/launcher/runtime design must enforce all of the
following:

- no startup/logon trigger may automatically enter an effectful trading loop;
- a Windows reboot or shutdown terminates the current running process and leaves
  the bot stopped after boot;
- durable session/effect evidence is preserved across reboot and is never deleted,
  rewritten or treated as fresh authority;
- boot/login may perform only explicitly designed inert/read-only observation if
  a later architecture chooses to add it;
- trading resumes only after a fresh explicit operator start action;
- the start path must reconcile durable state and fail closed on ambiguity before
  any new provider/paper/broker effect;
- reboot must not manufacture a retry for an already-consumed or ambiguous
  provider/paper/broker intent;
- no scheduler restart policy may silently convert an intentional OS reboot into
  automatic trading resumption.

The exact UX/CLI/GUI surface for explicit start/stop remains a future design
decision. This requirement freezes the semantics, not a specific interface.

## F1 soak exception

Architecture 134-F1 intentionally differs. Its fixed five-session soak task uses
one current-user logon trigger and a `--resume` action so the soak can test
durable restart/idempotency behavior across five published sessions. The F1 task
has `WakeToRun=false` and `StartWhenAvailable=false`; after an actual reboot it
may resume only when the user logs in and only after exact durable reconciliation.

That F1 behavior is test plumbing. It must not be copied forward as the default
production lifecycle.

If F1 is offline long enough to miss a frozen target session, the series halts;
there is no replacement session, backfill or automatic retry.

## Scope and safety

This requirement grants no provider, credential, paper, broker, D2, promotion or
real-money authority. Real-money trading remains **NO-GO**.

Before a future production deployment milestone is accepted, its source tests and
operator validation must explicitly prove reboot=stopped and manual explicit
restart semantics.
