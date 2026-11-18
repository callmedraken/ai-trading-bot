# Architecture 147 — L43-Q1 qualification preflight source validation plan

## Scope

This is the source-validation plan for
`ARCH147-L43-Q1_QUALIFICATION_PREFLIGHT_SOURCE`.

It implements the frozen architecture in
[147-l43-qualification-preflight-source.md](../architecture/147-l43-qualification-preflight-source.md)
against accepted RHC4-C2
`4f560a74b04ecba85c7b312364a9e4e7b30e57b6` /
`b422ef66d88b184bdbe12788546e6b2ffd083846`.

Source work is fake-only. The real preflight, credentials/provider reads and all
broker effects remain NOT RUN in this checkpoint.

## Implementation routing

This is substantial Architecture-147 implementation under the current
prototype-completion delegation overlay:

- ChatGPT Sol High owns architecture, exact-source review, certification,
  integration and protected-effect decisions.
- Codex Sol High is coordinator-only.
- Luna Extra High owns repository implementation and focused verification.
- Codex Sol High must not code, edit, test, stage, commit, push, merge or perform
  protected effects.

## Expected source surfaces

The exact file set may narrow after coordinator inspection, but implementation
should remain inside current Architecture-147 ownership. Prefer a small additive
qualification module and CLI/runner adapter rather than altering the effect
operator.

Likely surfaces:

- new source-owned L43 qualification/preflight module under
  `src/trading_bot/live_prototype/`;
- one narrow script/runner entry point;
- `scripts/checkpoint_runner.py` registration/routing only as required;
- focused Architecture-147 tests;
- current architecture/validation docs only when implementation details require
  exact updates.

Do not create a second Robinhood transport, second OAuth/session owner, second
durable-state engine or second strategy signal path.

## Required fake scenarios

Focused tests must cover at least:

1. import/help/construction: zero provider/credential/state mutation;
2. exact current source/config/binding/Q62/RHC3 admission;
3. canonical account selection with exhaustive account/SPY order reads;
4. genuine BUY, flat state, <=$10 request -> READY challenge;
5. HOLD/SELL while flat -> NO_ACTION/BLOCKED with no challenge;
6. >$10, zero/negative request, consumed entry -> BLOCKED;
7. manual SPY holdings/account mismatch -> BLOCKED;
8. unresolved/MAY/UNKNOWN effect -> BLOCKED;
9. bound WORKING/PARTIAL order -> PENDING_SETTLEMENT_REQUIRED, no settlement
   mutation from Q1;
10. manual-close state -> MANUAL_CLOSE_REQUIRED;
11. stale/wrong session or signal -> BLOCKED;
12. source/config/state-tail drift -> BLOCKED;
13. provider read or pagination ambiguity -> BLOCKED, no retry;
14. evidence sanitization: no raw account number, token, provider payload or order
    identifier;
15. challenge digest changes for every material bound fact;
16. caller cannot inject account/source/plan/authorization facts;
17. preflight cannot call review/place/cancel;
18. preflight cannot construct/return `L43StageAuthorization`;
19. repeated fake preflight leaves durable bytes/state unchanged;
20. current RHC4 public session/source seams remain the only production path.

## Admission and certification

Before publication:

- prove exact canonical F: worktree, branch, HEAD/tree, origin and clean state;
- run affected focused tests with a fresh external
  `F:\AI\temp\pytest\<purpose>-<GUID>` basetemp and
  `-p no:cacheprovider`;
- run required Architecture-147 route/ownership/current-authority tests;
- run combined Ruff check/format on the changed Python surfaces with
  `--no-cache`;
- run `git diff --check`;
- create one atomic unpublished commit;
- run general `ops.ps1 admit` on that exact clean committed candidate;
- require FEATURE and PROSPECTIVE_DEVELOP PASS and stable exact identity;
- one ordinary feature push;
- one mapped CI run to terminal.

Do not run duplicate local FULL when the exact mapped feature CI owns FULL.

Any deterministic route-owned failure that admission should have exercised is
`PREPUBLICATION_COVERAGE_DEFECT`; preserve evidence and stop for ChatGPT review.
No unchanged CI rerun.

### Preserved first unpublished admission

The first unpublished candidate's identity and immutable report path are
recorded in the [current handoff](../AI_TRADING_BOT_HANDOFF.md#l43-q1-source-checkpoint-and-next-boundary).
Its admission was classified
`CURRENT_MUTABLE_REGISTRY_PIN_REGRESSION / PREPUBLICATION_COVERAGE_DEFECT`.
The report recorded FEATURE=PASS, PROSPECTIVE_DEVELOP=PASS,
`IDENTITY_STABLE=True`, Ruff=PASS, DIFF=PASS, and pytest with 2,737 passed,
2 failed and 1 skipped; overall admission was FAIL. The two failures were
`test_registered_profiles_include_current_arch128_gates` and
`test_r2b_common_and_family_requirements_are_independently_selectable` in
`tests/runtime/checkpoint_runner/test_core.py`. The first treats the complete
current checkpoint registry and checkpoint-name routing representation as a
fixed snapshot. The second reconstructs current family ownership from checkpoint
names and exception sets, then compares exact runner-test tuples. Q1 correctly
belongs to the current Architecture-147 prototype owner; these mutable global
snapshots instead preserve obsolete current expectations.

The correction replaces current mutable registry and family snapshots with
semantic invariants and synthetic growth tests. The candidate was not pushed
and no feature CI ran; provider and protected-effect counters remained zero.

## Accepted correction and consumed protected observation

The corrected Q1 candidate was published and independently accepted at
`05f4c4700f82c3d40c83f474c3cf614573d48091` / tree
`70aec1c51e63705a68d6710cc3448ac994227e46`. Feature mapped FULL run
`44260469616`, attempt 1, is terminal SUCCESS; develop run `44264566809`,
attempt 1, is terminal SUCCESS with exact feature-certification reuse and no
duplicate FULL.

After exact local feature/develop reconciliation, one separately reviewed
protected read-only Q1 preflight was authorized and consumed. Its report is:

`F:\AI\temp\ai-trading-bot-checkpoints\arch147-l43-qualification-preflight\preflight-20261118T091033.372793Z\report.json`

The runner recorded source admission PASS before and after, exact stable Q1
HEAD/tree, and `BLOCKED / QUALIFICATION_INDETERMINATE`. The qualification
bound the accepted source plus Q62 configuration, binding and journal digests.
It did not bind an L43 durable-state sequence/tail, fresh pre-effect facts,
account fingerprint, target session, plan binding or challenge. All effect
counters remained zero. Provider/credential counters are `null`, which is
deliberately unknown accounting and must not be rewritten as zero. Automatic
retry is `NOT_AUTHORIZED`.

The result narrows the exception to after `source_reader()` succeeded and
before `context.snapshot` was assigned. Current source inspection shows that
the production state reader opens only
`F:\AI\arch147-l43-live-state-v1\durable-state.jsonl` under its pre-existing
lock and never initializes state. No production L43 state-provisioning command
exists in the repository; state creation is present only in fake/test fixtures.
Because the protected result sanitizes the underlying exception, it does not
prove whether the concrete host cause was a missing journal, missing lock,
identity/ownership failure or another `L43StateUnavailable` condition.

This is therefore a consumed fail-closed observation and a next-prerequisite
source/design gap, not authority to retry Q1 or to perform an order effect. The
next source checkpoint must provide an explicit provider-free L43 state
provisioning/validation boundary plus typed diagnostic discrimination before a
new Q1 observation can be considered.

## Protected-effect counters

Source implementation/certification must report:

- real OAuth/browser/MCP sessions: 0;
- real Robinhood account/position/order reads: 0;
- real Alpaca calls: 0;
- review/place/cancel: 0;
- broker mutations: 0;
- production durable-state mutations: 0;
- Q62 journal mutations: 0;
- FINAL_HOLDOUT accesses: 0.

Fake transports may record synthetic calls only.

## Post-acceptance sequence

After ChatGPT exact-source acceptance and exact-SHA fast-forward integration:

1. verify terminal develop certification/reuse;
2. reconcile local feature/develop worktrees using the documented known-behind
   fast-forward rule where applicable;
3. invoke one separately reviewed registered Q1 protected read-only preflight;
4. preserve evidence and stop on READY, NO_ACTION or BLOCKED;
5. only after independent review of a READY result may the next exact
   human-authorized effect source/boundary be designed or invoked.

Q1 preflight has no `execute` authority and never places an order.
