# Architecture 144-C — F1 paper-evidence admission validation plan

Status: **SOURCE ACCEPTED; Checkpoint Source Gates #652 / 39410467329 passed and accepted source is integrated.**

This plan validates the pure V2 successor frozen in
`docs/architecture/144-c-f1-paper-evidence-admission.md`.

It grants no scheduler, provider, credential, paper, broker, promotion, or live
authority.

## Source admission

Implementation predecessor:

```text
branch develop
HEAD   f47deac55e22f5a1f215bed69b3429038d7babb0
TREE   6a5e3319729e2d1e4b034631dd1d2edb99ccaa4f
```

Implementation branch:

`feature/test-suite-arch144-c-f1-paper-evidence-admission-current`

Worktree:

`F:\AI\worktrees\ai-trading-bot-arch144-c-f1-paper-evidence-admission-current`

The branch matches the existing reviewed `feature/test-suite-*` push family.
Do not create a workflow-registration checkpoint merely to admit it.

Before edits Codex must prove the exact worktree, branch, local HEAD/tree,
origin/develop predecessor, clean index, and expected tracked worktree state.
Any mismatch is STOP; do not reset, rebase, clean, switch, or manufacture
convergence.

## Frozen source pins

Accepted F1 authority:

```text
HEAD b59ad3b44540a55a30f612d5c4e3e38e26a95b02
TREE e8a94e3512d7950f2fbc9c4d102a58b63e03244f
```

Relevant accepted F1 blobs:

```text
five_session_soak_store.py 3813837e8d10ee2b19150405143704a7f03d474f
five_session_soak.py       9de15257fc9b6fe97e90314450b097849ff81320
five_session_soak_child.py 6afcdfe42ac1691bc477efcfb4764c227a0c1bc2
```

Frozen Architecture-144 v1 blobs:

```text
research_strategy_paper_candidate_eligibility.py
fd6b0ad650fb3fb97f587deb7cffc7286e685813

research_strategy_paper_evidence_verification.py
915bdd84bee3ad0b57efcafb0a78da01fce94e66
```

The implementation gate must assert those v1 blobs remain unchanged.

## Required source shape

Add separate V2 source rather than modifying the v1 modules.

Expected primary source:

```text
src/trading_bot/experiments/research_strategy_paper_candidate_eligibility_v2.py
src/trading_bot/experiments/research_strategy_f1_paper_evidence_verification.py
```

Expected primary tests:

```text
tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py
tests/experiments/test_research_strategy_f1_paper_evidence_verification.py
```

The package export surface may expose the new public V2 types/functions.
Checkpoint/current-inventory/timing/pin surfaces may change only as mechanically
required by the new current-supported modules/tests.

The implementation may not refactor either frozen v1 source file for helper
sharing. It may reuse existing public domain types and public policy/canonical
helpers, but must not import private helpers or constants from another module.

If implementation discovery reveals that the frozen V2 contract itself must
change, STOP and return to ChatGPT.

## V2 artifact tests

For `ResearchStrategyPaperSessionObservationV2`, prove:

- exact schema, identity version, namespace and field set;
- deterministic UUID5 identity with exact ordered UTF-8 length framing;
- exact fixed F1 authority kind/schema/source HEAD/TREE;
- exact parent ID, full parent-journal SHA256, child ordinal, child ID and child
  journal SHA256;
- exact D1R7/D1R8 source pins and evidence SHA256;
- exact production strategy/config/source semantics;
- canonical JSON roundtrip;
- duplicate/unknown/missing fields reject;
- UUID/date/hash/source/Decimal alternate spelling rejects;
- float and bool-as-int reject;
- clocks, paths, bytes, file metadata and random values cannot influence identity.

For `ResearchStrategyPaperCandidateEligibilityV2`, prove:

- exact schema, identity version, namespace and field set;
- reuse of the unchanged v1 policy ID;
- exactly five unique observation IDs;
- one exact parent ID and parent-journal digest across the window;
- same authority kind/schema/source across the window;
- chronological observation ordering;
- exactly consecutive published regular sessions;
- at least one `PAPER_EXECUTED`;
- positive-only artifact semantics;
- exact strategy/source stability;
- canonical JSON and deterministic UUID5 behavior.

## Pure F1 parent replay tests

Using synthetic canonical supplied bytes only, prove the pure parser rejects:

- non-bytes, empty, oversized, invalid UTF-8 or noncanonical JSON;
- duplicate fields;
- wrong parent schema;
- wrong F1 source branch/HEAD/TREE;
- wrong identity/binding;
- invalid timestamps or backward row time;
- skipped/reordered states;
- effect counters beyond budgets;
- fewer or more than five completed children for `FINAL / COMPLETED`;
- parent FINAL proof whose pre-FINAL prefix length/digest is wrong;
- parent FINAL proof with scheduler state other than `MATCH`;
- child-summary reordering, duplicate ordinals, wrong target or wrong contract;
- child digest/proof/effect-accounting drift;
- any parent terminal other than exact successful `COMPLETED` for positive
  five-session evaluation.

The verifier must recompute the full supplied parent-journal SHA256 itself.

## Pure F1 child replay tests

For each ordinal 1 through 5 prove:

- child schema/source/parent ID/target/ordinal are exact;
- child identity is recomputed from accepted F1 semantic material;
- parent grant prefix is recomputed from parent bytes through the matching
  `SESSION_n_GRANT_INTENT`;
- child reservation cannot precede the durable grant;
- child journal canonical state ordering and budgets are enforced;
- final classification agrees with the parent summary;
- final child-journal SHA256 agrees with the parent summary;
- D1R7/D1R8 attempts match the saved child effects;
- a complete positive child has both D1R7 and D1R8 proofs;
- partial/ambiguous effect evidence never becomes a positive observation.

## D1R7/D1R8 supplied-proof tests

Using supplied synthetic bytes only, prove:

- D1R7 source is exactly the accepted F1 D1R7 pin;
- target session is exact;
- intended D1 is exactly the accepted D1R8 source pin;
- policy and production contract are canonical and exact;
- D1R7 journal digest equals the F1 child summary proof;
- D1R8 facts bind that exact D1R7 proof;
- D1R8 target and recovered contract agree;
- D1R8 journal digest equals the F1 child summary proof;
- D1R8 terminal classification agrees with child and parent summaries;
- full D1R8 final effect counters equal the saved parent child summary;
- altered/truncated/prefix/terminal-looking evidence fails closed.

No test may read an actual production evidence file.

## Architecture-142/143 composition

Retain the accepted pure Architecture-142/143 verification contract.

Before V2 observation construction require:

- complete compatibility proof verification;
- exact production target ID;
- exact production strategy schema/family/version;
- exact Symbol and MovingAverageCrossoverConfig;
- exact production source HEAD/TREE;
- exact production contract semantics recovered from supplied F1 child evidence.

A parsed object without external verification is never enough.

## Classification matrix

A complete verified V2 observation may represent:

```text
NO_SIGNAL
RISK_REJECTED
PAPER_EXECUTED
```

Only these qualify for positive five-session eligibility:

```text
NO_SIGNAL
PAPER_EXECUTED
```

At least one `PAPER_EXECUTED` is required.

These never create a positive V2 observation:

```text
SESSION_MISSED
BLOCKED
INDETERMINATE
```

No failed or incomplete classification authorizes retry, replacement, backfill,
or a new soak.

## Purity/static capability gate

Tests/static review must establish the V2 implementation does not acquire
operational state.

Forbidden capabilities include direct or indirect use for evidence acquisition
of:

```text
pathlib/os filesystem evidence reads
SQLite
subprocess
Task Scheduler / COM
provider clients
credential stores
broker APIs
F1 host/bridge/scheduler runners
D1R7/D1R8/D1R9 operational entry points
production lifecycle mutation
PAPER_CANDIDATE materialization
promotion
current clock
randomness
```

Pure parsing of supplied bytes and deterministic calendar/domain validation is
allowed.

Expected counters remain zero:

```text
FILESYSTEM_READS=0
FILESYSTEM_WRITES=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
ROBINHOOD_READS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
PAPER_MUTATIONS=0
STRATEGY_PROMOTIONS=0
D1R7_OPERATIONS=0
D1R8_OPERATIONS=0
D1R9_OPERATIONS=0
F1_OPERATIONS=0
LIVE_EFFECTS=0
```

## Focused verification

Codex should use cheap gates first, then focused tests.

At minimum run the new V2 artifact and F1 verifier test modules plus affected
current-inventory/checkpoint tests. Use a fresh external
`F:\AI\temp\pytest\...` basetemp for pytest commands that use temporary
fixtures.

Run non-mutating Ruff check and Ruff format check for changed Python/tests, and
`git diff --check`.

Do not run raw whole-repository pytest while iterating.

## Checkpoint registration and certification

Checkpoint:

`arch144-c-f1-paper-evidence-admission`

Authority:

```text
preflight None
execute   None
```

Do not map a canonical ROBINHOOD or FULL profile in advance.

The feature branch is already admitted by `feature/test-suite-*`. The normal
push-triggered source gate owns routine admission. If current runner policy
requires registration/pins/inventory for the active checkpoint, include all
predictable changes in the same logical source checkpoint before publication.

FULL is not automatic. ChatGPT decides whether any additional canonical profile
is materially required only after exact-source review.

## One-publication rule

This is one logical source checkpoint.

Before publication Codex must compose all predictable source, focused tests,
exports, runner registration, inventory/pin/timing changes, current bounded docs
updates, and formatting cleanup.

Then:

```text
one fully prepared atomic commit
-> one ordinary feature-branch push
-> one push-triggered CI admission run
-> terminal PASS or failed checkpoint attempt
```

Exact-file staging only. Never use `git add .` or `git add -A`.

If the push-triggered run fails, preserve evidence and end that checkpoint
attempt. A later bounded mechanical correction must be declared C1 (and at most
one further C2 under the standing rule), receive focused verification, and use
its own atomic commit/push. Never rerun unchanged CI.

Codex polls CI to terminal before handoff.

## Acceptance and next boundary

ChatGPT owns exact GitHub diff/CI review, source acceptance, any certification
decision, merge readiness, and protected-effect readiness.

144-C source acceptance does not authorize the F1 soak.

After 144-C source acceptance, the read-only review found no registered F1 preflight. The next safe source boundary is Architecture 134-F2, which adds a separately reviewed registered read-only readiness preflight. Only after F2 source acceptance and a reviewed F2 preflight PASS may any F1 authorization command be considered; scheduler/provider/paper effects remain separately protected.

Real-money trading remains **NO-GO**.
