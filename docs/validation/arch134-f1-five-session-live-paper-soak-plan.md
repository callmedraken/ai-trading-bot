# Architecture 134-F1 — five-session live-paper soak validation plan

Status: **SOURCE ACCEPTED; canonical ROBINHOOD #649 passed. Protected execution remains closed.**

This plan validates the source-only Architecture 134-F1 parent soak authority.
No test or implementation command may create/run/update/delete a real scheduled
task, access production credentials/providers, mutate production paper/session
state, invoke D1R7/D1R8/D1R9 operationally, or place broker/live orders.

## Starting source

Current integration base:

```text
branch develop
HEAD   b3b605fdc0886cd90367027e72d43ecaf8ce5b4c
TREE   1b2b783211aa41d9add5e3c29d3a336c33a75c3c
```

Implementation branch:

`feature/robinhood-production-paper-134f-five-session-soak`

Worktree:

`F:\AI\worktrees\ai-trading-bot-production-paper-134f-five-session-soak`

Historical D1R9 semantic predecessor:

```text
HEAD efd1e6763dc4663d9c4b2444e785eb1c32adf8e8
TREE 25a962daf3922c4226c7e395eba8613e1b03bbaf
```

Do not merge/rebase/cherry-pick the D1R9 branch.

## Required source surfaces

Astra/Sol discovery may refine exact filenames before first edit, but the final
design requires distinct current-lineage surfaces for:

1. canonical F1 parent-series store/parser;
2. parent planner/controller and five-session target derivation;
3. D1R9-equivalent one-session child execution boundary accepting only a durable
   F1 child grant;
4. fixed Windows host/runtime admission;
5. D1R7/D1R8 fixed child adapters;
6. F1-only scheduler transport;
7. zero-argument resume launcher;
8. checkpoint-runner registration/pins;
9. focused source tests.

Historical D1R9 source may be used as a reviewed semantic reference. Runtime
imports/calls into its old fixed worktree are forbidden.

## Core target-window tests

Prove:

- arbitrary-time authorization during a valid session before close-minus-five
  selects that session first;
- authorization after the deadline selects the next published session;
- weekends and holidays are skipped;
- early-close schedules use published close;
- exactly five ordered published regular sessions are frozen;
- session dates are immutable after reservation;
- no sixth target can be represented;
- no missed target rolls forward/replaces itself.

## Parent identity/canonicalization tests

Prove parent identity binds exactly the frozen semantic facts and excludes:

- ambient process/path identity;
- caller filename;
- random UUID/nonces;
- wall-clock values not explicitly part of authorization facts;
- locale;
- scheduler runtime state.

Prove canonical parse/serialize round trips, duplicate keys/unknown fields/type
drift/noncanonical timestamps/hash/UUID/date/Decimal forms reject, bounded bytes
are enforced, and append-only state ordering cannot be skipped/reordered.

## Child-grant tests

For each of five ordinals prove:

- only exact parent identity/digest may create the grant;
- target equals the parent's frozen target at that ordinal;
- one grant only;
- one D1R7 delegation maximum;
- one D1R8 delegation maximum;
- D1R8 cannot precede accepted D1R7 proof;
- accepted timing windows match D1R9 semantics;
- no human D1R9 interlock is forged or passed to historical `authorize()`;
- no second provider/paper attempt after durable effect intent;
- restart reconciles durable state rather than re-entering an effect.

Mutation tests must cover each source/contract/session/runtime/proof identity.

## Series progression matrix

Test all child terminal classifications.

Expected parent behavior:

| child terminal | child closes | next target allowed | Architecture-144 implication |
| --- | --- | --- | --- |
| NO_SIGNAL | yes | yes | qualifying clean coverage |
| PAPER_EXECUTED | yes | yes | qualifying execution evidence |
| RISK_REJECTED | yes | yes | nonqualifying |
| SESSION_MISSED | yes | no | series halt/nonqualifying |
| BLOCKED | yes | no | series halt/nonqualifying |
| INDETERMINATE | yes | no | series halt/nonqualifying |

After the first halt, prove all remaining D1R7/D1R8/provider/paper counters stay
zero and no replacement date is selected.

## Restart and waiting tests

Use fake clock/runtime only.

Prove:

- maximum wait quantum 60 seconds;
- every wake/restart recomputes authoritative time/session state;
- backward clock movement blocks;
- persisted sleep duration is never authority;
- startup before market/after market/weekend/holiday converges to the same frozen
  target list;
- process restart during wait is read-only until reconciliation;
- restart after D1R7/D1R8 intent cannot repeat the effect;
- duplicate task/process entry is IgnoreNew/read-only;
- no wake-from-sleep behavior is introduced.

## Scheduler-contract tests

Statically/fakely prove exact F1 task shape:

`AITradingBot-Arch134-F1-FiveSessionSoak-v1`

Require:

- one current-user logon trigger;
- one action;
- standard current user / no elevation;
- zero semantic arguments;
- fixed F1 worktree launcher;
- no historical D1R9/D10 path;
- no repetition;
- WakeToRun false;
- StartWhenAvailable false;
- AllowDemandStart true;
- IgnoreNew;
- RestartCount 3;
- RestartInterval PT1M;
- ExecutionTimeLimit PT0S;
- no update/delete/recreate/retry surface during source tests.

All scheduler tests are fake/static. Real COM/Task Scheduler access is forbidden.

## D1R9 equivalence tests

Freeze the accepted D1R9 source identities in F1 authority tests. Prove the new
current-lineage one-session child preserves:

- published-session selection/timing semantics;
- complete D1R7 proof requirements;
- complete D1R8 proof requirements;
- terminal classification set;
- no-retry classification after ambiguous effect intent;
- child lock/single-entry behavior;
- runtime source/binding re-admission;
- bounded waiting;
- exact per-session effect ceilings.

D1R9's fixed historical worktree/branch/task constants are intentionally not
copied as F1 runtime identity.

## End-of-window reconciliation tests

For five successful operational terminals prove FINAL requires exact ordered
proofs for every target and rejects:

- missing child;
- duplicate target;
- reordered target;
- source/contract/strategy drift;
- child bytes/digest mismatch;
- effect-counter mismatch;
- incomplete D1R7/D1R8 proof;
- active/ambiguous child;
- scheduler projection drift.

The F1 controller must not import/call Architecture-144 builders or verifiers.
The accepted Architecture-144 v1 evidence verifier is D1R9-specific and must
reject truthful F1 provenance rather than be weakened.

F1 tests instead prove its own end-of-window evidence contains all information
needed by a future pure successor: exact F1 source HEAD/TREE, parent-series
identity/digest, ordered target sessions, ordered child identities/digests,
D1R7/D1R8 proof bindings, terminal classifications and effect accounting.

Architecture-144 composition is explicitly deferred to Architecture 144-C after
F1 source acceptance, when the exact final F1 source identity can be pinned.

## Zero-effect implementation gate

Implementation/focused tests must prove or instrument:

```text
WINDOWS_SCHEDULER_READS=0
WINDOWS_SCHEDULER_MUTATIONS=0
CREDENTIAL_READS=0
PROVIDER_REQUESTS=0
D1R7_OPERATIONS=0
D1R8_OPERATIONS=0
D1R9_OPERATIONS=0
PAPER_MUTATIONS=0
BROKER_MUTATIONS=0
D2_OPERATIONS=0
STRATEGY_PROMOTIONS=0
REAL_MONEY_EFFECTS=0
```

## Verification order

During implementation:

1. topology/admission and exact predecessor pins;
2. narrow unit tests for store/window/identity;
3. child-equivalence and restart/idempotency tests;
4. scheduler static/fake tests;
5. end-of-window/research-separation tests;
6. affected checkpoint-runner/current-inventory tests;
7. Ruff check/format and `git diff --check`;
8. one final exact staged diff review.

Do not run raw repository-wide pytest while iterating.

## Terminal certification ownership

The terminal F1 checkpoint requires canonical **ROBINHOOD**, not FULL. F1 is a
Robinhood/review-paper authority change and its new tests belong under the
preserved Robinhood ownership surface. Whole-repository static checks remain part
of every selected certification profile.

Preferred publication route:

- register the exact F1 checkpoint in `CI_CERTIFICATION_PROFILES` as `robinhood`;
- finish all focused verification before commit;
- create one atomic terminal commit;
- ordinary-push once;
- allow that single push-triggered CI to own canonical ROBINHOOD;
- poll to terminal;
- do not run duplicate local ROBINHOOD;
- do not run FULL unless later source changes materially broaden beyond the
  Robinhood-owned surface and ChatGPT explicitly selects FULL.

If the mapping cannot safely be established before publication, follow the
canonical unmapped fallback using ROBINHOOD, not FULL.

## Acceptance

Source acceptance requires:

- exact reviewed HEAD/TREE and one logical terminal checkpoint;
- all focused tests green;
- all F1 authority/effect ceilings fail closed;
- historical D1R9/D1R7/D1R8 accepted sources unmodified;
- zero operational effects;
- terminal canonical ROBINHOOD green;
- terminal CI green with no unchanged retry.

Source acceptance authorizes only the next pure Architecture 144-C design/source
boundary. It does not authorize protected F1 preflight, scheduler/publication
effects, or the soak itself.

Real-money trading remains **NO-GO**.

## Architecture 144-C sequencing

Do not modify `src/trading_bot/experiments/` as part of F1 implementation merely
to make current F1 evidence fit Architecture-144 v1. The v1 schema has explicit
D1R9 provenance fields and the v1 verifier pins the historical D1R9 branch,
HEAD and TREE.

After F1 source is terminal-green and exact-source accepted, ChatGPT will freeze
Architecture 144-C against that exact F1 source identity. 144-C will be a pure
read-only successor and is expected to add a separate generic-authority/v2
observation path while preserving v1 byte-for-byte.

The protected F1 preflight remains blocked until both F1 source and 144-C source
are accepted.

## Implemented focused gate

`tests/review_paper/test_five_session_soak.py` covers the F1 parent/window/store,
immutable grants, progression/halt, consumed-intent recovery, independent
reconciliation, current-inventory/checkpoint integration, and frozen v1 source.
`tests/review_paper/test_five_session_soak_child.py` ports the accepted D1R9
behavioral timing/proof/fault matrix onto F1 grants, retaining fake process/Git/
scheduler edges and disposable evidence/runtime files only. Exact AST digests
of the accepted D1R9 proof, terminal and bounded-supervision reducers supplement
the behavioral checks. The scheduler source harness evaluates only the bounded
HRESULT helper, never Task Scheduler or its COM transport.

Current inventory metadata includes both new review-paper modules, the unchanged
49-module required Robinhood baseline and two nonempty deterministic Robinhood
lanes. The FULL timing/fixture inventory is synchronized as metadata only; no
local FULL or duplicate local ROBINHOOD is part of F1 implementation.

The atomic source publication is not source acceptance. Review the exact final
HEAD/TREE and push-triggered CI evidence, then stop for ChatGPT. Do not implement
144-C, provision a task, run protected preflight, or begin the soak in this gate.

## C1 corrective source gate after canonical #648

Initial source `24a7397dff418c47a257e8d0ceec97088dc7caf0` passed source-static
and all 331 active cases. Canonical ROBINHOOD #648 / 39399741708 / attempt 1
failed eight stale test-only registry/successor expectations and the hygiene
gate: 10,421 cases; 10,407 passed; six skipped; eight failed; zero errors;
wall 321.863 seconds. Evidence remains preserved; the failed attempt is never
rerun or rewritten.

The bounded C1 corrects the six current registry adjacency/count assertions and
two predecessor-resolution expectations, extending only the final test-pin
overlay. Production F1 and Architecture-144 source remain unchanged.

The read-only hygiene audit found 199.971/320.334-second lanes with the new F1
parent tests on the slower lane (42.599 summed testcase seconds). C1 adds one
F1-only deterministic placement pin for that module to lane 0, after the
unchanged R3H overlay. Coverage, the 103-module inventory, two nonempty lanes,
protected boundaries and 300-second ceiling are preserved. The replacement
push owns a fresh canonical ROBINHOOD attempt; no local profile or FULL runs.
