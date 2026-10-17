# Architecture 134-D1R8 source validation

Contract: [D1R8 architecture](../architecture/134-d1r8-d1-session-execution-consumer.md).
Tests use only fake source/clock/native/provider seams and disposable external
SQLite/evidence files. No real host or operational path is invoked.

Focused validation covers canonical D1R7 prerequisite/proof/source/policy/target/
expiry/authority/counters, every controller guard and state interruption,
one-shot collision/rebuild/concurrency, compatibility fencing, journal native
I/O interruption, credential fixed targets and read-only persisted auth,
four-request history, NO_SIGNAL/PREPARE/risk/execute, pagination ceilings,
review echo, freshness, paper acknowledgement ambiguity, path/sidecar/identity
drift, parser state/counter corruption, secret exclusion, reachable-call
containment, frozen predecessor pins, successor resolution and CI inventories.
Existing directly affected registration/profile/inventory/authority tests and
publicly reused components receive focused regression coverage.

Run touched-file Ruff lint and format checks, collecting both diagnostics, and
git diff --check. No local FULL/ROBINHOOD certification. GitHub owns the canonical
mapped ROBINHOOD run; source-static, active-tests, certification-tests and
source-gates must reach terminal SUCCESS on exact pushed HEAD, attempt 1.
Report canonical pass/skip/fail/error/wall and exact run/jobs, source identities,
changed paths, focused counts, inventory and successor/frozen-pin preservation.
After terminal green STOP for ChatGPT exact GitHub review.

D1R7 publication and D1R8 operational execution remain unauthorized. Validation
success is source evidence only, never operator/trading authority.
