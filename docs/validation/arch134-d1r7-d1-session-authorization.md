# Architecture 134-D1R7 source validation

Contract: [D1R7 architecture](../architecture/134-d1r7-d1-session-authorization.md).
Source implementation only. No real D1R7 evidence publication, host invocation,
D1R5 execution, D1R6 host/reconciliation, scheduler observation/mutation,
provider/credential/store/strategy/PREPARE/EXECUTE/paper/broker/D2/live effect.

New tests use fake clocks and source seams with disposable external pytest
artifacts. Synthetic predecessors override only test length/hash pins; separate
literal assertions freeze every production basename/size/hash/schema/source.
Test exact accepted parser semantics, six/eight event lineage, historical one
scheduler-create, all counter types and keys, closed canonical transport,
source drift, fixed branches, target derivation, expiry/DST/holiday/early-close,
policy drift, revision-independent collision/concurrency, links/reparse/hard
links/open-handle identity, write/flush/fsync/reread/close/parse interruptions,
consumed-slot no-retry, inert host dispatch, reachable call containment,
registration/mapping/inventory and frozen successor digests.

Focused verification runs the new module, predecessor parser modules, changed
checkpoint/profile tests and affected live inventory/authority tests. GUI-only
inventory/resolver tests are selected without the full GUI suite. Ruff check
and Ruff format check run on touched Python paths with both diagnostics captured
before stopping, followed by git diff --check. No local FULL/ROBINHOOD suite.

CI owns mapped ROBINHOOD: source-static, active-tests, certification-tests and
source-gates must reach terminal SUCCESS on exact pushed HEAD, attempt 1;
full-tests is skipped and canonical wall must stay below 300 seconds. Report the
exact run/attempt/head/jobs/wall and source parent/HEAD/tree, path set, focused
counts, lint/diff, inventory and predecessor digest results. One atomic commit,
one ordinary push, one push-triggered attempt; red means STOP with no retry.
After green STOP for ChatGPT exact GitHub source review. D1 remains unauthorized.
