# PD4 D9 Settlement Source Certification

Date: 2026-09-16

## Scope

This record certifies the final Architecture-114 D8/D9 source tree for unattended
Paper-v2 settlement qualification, one separately authorized settlement effect,
and independent post-settlement reconciliation.

This is a **source certification only**. It does not authorize or record any real
D8-B settlement invocation, D7 decision publication, receipt recovery, broker
submission, or live-trading effect.

## Certified source identity

```text
branch: feature/pd4-unattended-settlement
source HEAD: 0df4ccb97a750e5727ef65dae7a365a3c7355254
source TREE: f6c27fcff1a6cec839d8f6ec395d658dbbbbe36c
```

The source checkpoint is commit:

```text
0df4ccb97a750e5727ef65dae7a365a3c7355254
Prepare D9-A read-only settlement reconciliation
```

The certified source tree includes the already accepted D8-A/R1 and D8-B/R1
boundaries plus D9-A independent read-only reconciliation.

## Accepted predecessors

```text
D8-A/R1 HEAD 170b50743458c8c973d472476b9e7abf140b6b1d
D8-A/R1 TREE b2a202faf45bf61d5e3c1043c69a6cafcb00b6e3
focused verification: 233 passed

D8-B/R1 HEAD 260d80f60db9acfd352b1bc89ff963fc2a590a38
D8-B/R1 TREE bc4fb96d2ecb30e607262de2c0b268510bd43835
focused verification: 134 passed

D9-A HEAD 0df4ccb97a750e5727ef65dae7a365a3c7355254
D9-A TREE f6c27fcff1a6cec839d8f6ec395d658dbbbbe36c
focused verification: 422 passed
```

D9-A remains structurally read-only. It independently reconstructs current
settlement truth, verifies finalized-decision/C3/open/plan/invocation/account and
Architecture-67 state, classifies `RECONCILED`, `NOT_APPLIED`,
`RECEIPT_RECOVERY_REQUIRED`, or `BLOCKED`, and does not import D8-A qualification
or D8-B execution authority as a shortcut.

## Final certification

The first monolithic D9-B repository run used the required external basetemp and
`-p no:cacheprovider`. It reached:

```text
6092 passed
17 skipped
374 failed
1 error
```

The 374 failures and one error were confined to the two legacy Architecture-77
Windows authority modules and shared the same environment failure: the fixed
repository-local arbiter namespace under
`.pytest_cache/ai-trading-bot-lifecycle-arbiters-v1` was inaccessible to the
John development principal. The parent `.pytest_cache` ACL itself was unreadable
from the non-elevated shell and the arbiter child directory did not exist.

Architecture 77 intentionally requires that fixed repository-local rendezvous
namespace for independently spawned processes. The cache was therefore **not**
deleted, ACL-reset, taken over, redirected through `TEMP`, or changed to honor
`--basetemp` merely to make the test pass.

The replacement certification reused the previously accepted Windows recovery
pattern:

1. run the broad suite on the D9 worktree while excluding only the two legacy
   Architecture-77 modules;
2. prove those two test-module blobs are byte-identical to the clean integration
   harness copies;
3. run those legacy modules from the clean integration checkout while binding
   imports to the D9 source tree through a temporary process-local `PYTHONPATH`;
4. prove the relevant `trading_bot` modules actually resolve from the D9
   worktree before executing the legacy tests;
5. re-prove the D9 HEAD, TREE, origin HEAD, and clean worktree after the runs.

Accepted replacement results:

```text
broad nonlegacy:       5709 passed
Architecture-77 legacy: 758 passed
---------------------------------
combined:              6467 passed
skipped:                 17
failed:                   0
errors:                   0
```

Additional exact-tree checks on the same source tree:

```text
Ruff check: PASS
Ruff format --check: PASS (547 files)
git diff --check: PASS
git diff --cached --check: PASS
worktree/index: clean
local HEAD == origin feature HEAD: YES
```

No source correction was required after the environment-invalid monolithic run.
The certified source identity therefore remains exactly:

```text
HEAD 0df4ccb97a750e5727ef65dae7a365a3c7355254
TREE f6c27fcff1a6cec839d8f6ec395d658dbbbbe36c
```

## Production state after certification

No production D8 or D9 invocation occurred during source certification.

```text
D8-A production qualification: NOT RUN
D8-B real settlement:          PROTECTED / NOT AUTHORIZED
D9-A production reconciliation: NOT RUN
receipt recovery:              CLOSED
broker submission:             NOT AUTHORIZED
live trading:                  NO-GO
```

All eight committed production effect gates remain false. A future real D8-B
settlement still requires the frozen protected sequence: accepted D7
publication and reconciliation, completion of its intended execution session,
exact selected C3 evidence for that execution session, fresh D8-A qualification,
explicit approval for one D8-B effect, and fresh-process D9-A durable
reconciliation.

## Documentation rule

Docs-only commits made after this record do not alter the certified source
boundary. Future status/handoff documents must distinguish the immutable
certified source HEAD/TREE above from any later docs-only branch tip.
