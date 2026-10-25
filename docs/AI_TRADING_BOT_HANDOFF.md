# AI Trading Bot — Current Handoff

## Current source boundary

Architecture 134-F1R1-D1S4-R1 recovery/reconciliation is accepted and complete;
its durable recovery attempt is permanently CONSUMED. Incident release material
remains preserved and untrusted.

Architecture 134-F1R1-D1S4 Fresh Successor Source is SOURCE ACCEPTED and
integrated into `develop` at:

    HEAD b18c6e32606828beeebc540a93c9f05e3e024323
    TREE b082c15bc697bf289fc7997b3d7bf87050082dc3
    DIRECT PARENT 47370fcb24baa0359ac741ee3ba2a14da6438f8d

Accepted source branch:
`feature/robinhood-production-paper-134f1r1-d1s4-fresh-successor-source-current`.

Feature publication CI #714 / 40167976672 attempt 1 is terminal SUCCESS.
Canonical ROBINHOOD artifact 12589725766 covered 112 modules / 11,222 cases:
11,216 passed, 6 skipped, 0 failed/errors; artifact SHA256
5edc36760e543cd2db525742a78952f0f5a5cd104a8e91f94eb776c1c485eec2.

ChatGPT fast-forwarded `develop` to that exact accepted commit. Develop
integration CI #715 / 40169150780 attempt 1 is terminal SUCCESS: source-static,
full-tests (0..3) and source-gates passed; active-tests and certification-tests
were correctly skipped on the broad fallback integration route.

The fresh source implementation remains source-only. It admits exact clean
source/worktree/branch/origin/remote identity, reconstructs the current immutable
release manifest/inventory and derives prospective release/final/attempt
identities. It excludes all three preserved incident release IDs. The dispatcher
has preflight=None and execute=None; no old D1S4/R1 latch can grant fresh
authority. Runtime binding, successor-soak and execute eligibility remain false.

Frozen incident objects remain:

- `F:\AITradingBot\releases\release-18d5d329c1d458558e98d7effe523c3b`
- `F:\AITradingBot\releases\release-cb94451fc3295a97afffe9fac5d09ff3.installing`
- `F:\AITradingBot\releases\release-03c42597246752319956ab96e01ed61c.installing`

Do not repair, delete, rename, reuse, bind, promote or derive fresh authority
from any of them.

## Weekend operating boundary

Do **not** freeze a production deployment generation yet.

Normal project development may continue on `develop` through the weekend,
including bounded source-only/offline research work that does not require
market-open evidence or a fixed deployment candidate. If `develop` advances,
the future deployment release identity must be regenerated from that later exact
HEAD/TREE.

Architecture 145-B is still deferred until the fresh F1 successor soak is
complete and accepted. Research Results GUI follows 145-B, then large strategy
campaigns. Do not reorder that accepted macro path.

No real-host successor preflight, installation execute, latch creation,
production materialization, scheduler/runtime mutation, provider/broker effect or
live effect is authorized during this weekend development window. Live remains
NO-GO.

## Sunday-night handoff

Immediately before preparing for the next market-open session:

1. resolve the then-current remote `develop` HEAD/TREE and require terminal
   green CI for that exact tip;
2. freeze only that exact tip as the deployment candidate;
3. create the fresh deployment-admission source checkpoint that emits/pins the
   concrete deterministic release ID, immutable final path and fresh
   release-derived attempt path;
4. publish once, wait for terminal CI, perform ChatGPT exact-source review, then
   integrate only after merge-readiness;
5. wait for terminal develop integration CI;
6. only then review and run the separate read-only real-host deployment
   admission;
7. preserve a STOP on any unexpected material, source drift, consumed/
   indeterminate attempt or parent/Python policy mismatch;
8. separately review successor-root write authority before any materialization;
9. proceed to the fresh manual F1 successor soak only after those gates pass.

The deployment candidate is intentionally **not** b18c6e3... by fiat; it is the
exact current `develop` source selected Sunday night.

Until then, continue safe project progress without production effects.
