# Architecture 134 — Production strategy and AI-research validation plan

## 2026-10-13 — Architecture 134-D1R1 SOURCE ACCEPTED

Architecture 134-D1R1 — bounded Alpaca history-failure observability and runtime
successor — is **SOURCE ACCEPTED** on
`feature/robinhood-production-paper-history-diagnostics` at the exact
executable/test source:

```text
HEAD 2154cb53017cccbd3908d2174bb0943d4657c451
TREE 9b9718353aa7ad51dbfa5d21f54e11b0f8fa9b58
BASE 6e2081a1278f579ca0cee5a00e2bd83632bc2856
```

The exact delta is one commit / 14 paths. D1R1 adds the separate bounded
`armed-paper-history-failure/v1` artifact without changing
`armed-paper-session/v1`, retry ownership, production strategy semantics or
paper/broker authority.

The accepted diagnostic contains exactly fourteen closed fields: schema, source
HEAD/tree, contract/operation IDs, target/history sessions, read ordinal,
classification, transport stage, metadata reason, HTTP status, provider code and
Alpaca-read count. Serialization is exact canonical compact UTF-8 plus one trailing
newline, bounded to 4096 bytes, duplicate/unknown/missing/noncanonical input is
rejected, and external writes are exclusive `xb` with flush/fsync.

The closed classification set is PROVIDER_CONSTRUCTION_FAILED,
TRANSPORT_FAILED, HTTP_FAILED, PROVIDER_RESPONSE_INVALID,
CAPTURE_OBSERVATION_REJECTED, SNAPSHOT_ACCEPTANCE_REJECTED,
SNAPSHOT_VERIFICATION_REJECTED, VERIFIED_HISTORY_REJECTED,
HISTORY_SEED_REJECTED and INTERNAL_FAILED. Transport/metadata classification
reuses the already-sanitized Alpaca enums; safe HTTP status/provider code may be
retained, while request ID, raw exception, credentials, headers, URL/body,
filesystem paths and provider free text are excluded.

Failure ordering is accepted: the durable one-session fence remains authoritative;
HISTORY_STARTED is published before each provider fetch; classified acquisition
failure publishes durable BLOCKED before fallible diagnostic export; diagnostic
export failure cannot retry or suppress the ordinary final session export; no
failure path advances to strategy evaluation, Robinhood PREPARE, synthetic
EXECUTE, paper mutation or broker placement. Focused tests prove one failed fetch
is never reacquired and raw sensitive material is absent from durable/exported
evidence and stdout/stderr.

The accepted source also preserves the consumed New York 2026-10-13 v1 row
unchanged and unretryable. That incident remains BLOCKED with alpaca_reads=1,
zero accepted snapshots, zero strategy evaluations, zero Robinhood calls,
PREPARE=0, EXECUTE=0, paper_mutations=0 and broker placement=0. The preceding
`python -m trading_bot.review_paper.armed_session_host` import-only invocation
remains a zero-effect no-op, not a consumed D1 attempt. Canonical Windows operator
guidance remains stdin-fed Python explicitly calling `main()`.

Historical authority material was independently reviewed against the admitted
base and is exactly unchanged: armed-MVP source pins/imports, historical R1
runtime source pins/imports, and R2 source/import/AST pins. D1R1 uses exact
successor overlays for the three changed inherited armed files and the current
runtime diagnostic/test material. The older armed-MVP authority is
successor-aware while retaining its historical branch/spec. The existing
`arch134-production-paper-runtime` checkpoint alone maps to the diagnostics
branch and retains canonical `robinhood` certification. ACTIVE membership/order
remains 62 and reviewed digest remains
`06a3101a319f6b268404deb67299d87d484fd238212131074c5f86cfea9a6440`.

Focused local verification passed **999** tests: 320
history/controller/provider, 121 runtime/host and 558 checkpoint/routing/profile.
Focused Ruff check, Ruff format --check and git diff --check passed. No local
broad certification or protected operation ran.

Mapped Checkpoint Source Gates
[38359252324](https://github.com/callmedraken/ai-trading-bot/actions/runs/38359252324) (#511) completed SUCCESS on the exact accepted HEAD.
source-static passed the mapped `arch134-production-paper-runtime` authority;
active-tests passed with stable identity; canonical ROBINHOOD certification
passed **94 modules / 8,738 cases / 8,737 passed / 1 skipped / 0 failed /
0 errors** in **136.46 seconds**; full-tests were correctly skipped because the
mapped certification profile owns breadth; terminal source-gates passed.

Current inventory remains ACTIVE 62 / FULL 170 / ROBINHOOD 94 / LEGACY 215 /
EXHAUSTIVE 385. Historical R1 remains
`6bf8753b0cc8950ae27b32b6858b64d454c512f0` /
`ce3feb2ac48e7aebc23970142aafed5059c447e7`; R2 remains
`2f122958366d1db282fea51abbd461b83fa893d9` /
`c3fb82add37bdbea12ebad9836ca10000b924fe1`.

Implementation/CI effects are all zero: production SQLite reads/writes,
credential reads, Alpaca/Robinhood/broker/scheduler calls, ACL/paper mutations,
D1 reservations and D1 executions. Real-money broker placement remains **NO-GO**.

Any later documentation-only descendant does not replace the accepted D1R1
executable/test identity above.

**Next operational step:** fresh protected D1Q qualification against this exact
accepted D1R1 source using canonical stdin-fed Python. Qualification may inspect
the fixed runtime stores and fixed Windows credentials according to the already
accepted D1Q authority, but it must not ARM a session, contact Alpaca/Robinhood
application APIs, mutate paper state, scheduler or ACLs, or retry the consumed
2026-10-13 session. D1R2 same-session/pre-effect recovery remains a subsequent
source-design milestone; it is not authority granted by D1R1.

## 2026-10-12 — Architecture 137 / RCL-1 implemented, exact review pending

Architecture 137 adds the pure in-memory canonical research artifact
`research-strategy-candidate/v1` on
`feature/research-candidate-lifecycle-foundation`, based on GUI-A15 docs-closeout
HEAD `778151fe8f91632a1af66384a3ab0a85d8d65069`, TREE
`03c50482427b04ebfc6ed061d048bb95e86edeae`. It is implementation evidence
pending terminal repository CI and ChatGPT exact GitHub review, not source acceptance.

GUI-A15 accepted executable/test source remains HEAD
`1dd46169deb69d7a381687b6ba835af9d6c12e5a`, TREE
`383b237aebfc553b10c7a5ef121a0191559c3f11`; dedicated GUI CI
[38343026765](https://github.com/callmedraken/ai-trading-bot/actions/runs/38343026765)
and repository CI
[38343142780](https://github.com/callmedraken/ai-trading-bot/actions/runs/38343142780)
are terminal SUCCESS. Earlier dated inventories remain historical provenance.

The exact conceptual order is EXPERIMENTAL -> BACKTESTED -> WALK_FORWARD_PASSED
-> SHADOW -> PAPER_CANDIDATE -> AWAITING_HUMAN_PROMOTION. EXPERIMENTAL is
pre-canonical hypothesis state. Only BACKTESTED is materialized in 137; all later
stages remain reserved for separately reviewed evidence/policy gates. Awaiting
human promotion means eligibility for review, without approval or promotion.
There is no generic stage setter/advance API.

The builder requires explicit selection from one completed exact
HistoricalExperimentReport, revalidates its invariants and retains all report/
row identity and rank facts. Rank is evidence: rank-1, rank-2 and unranked explicit
selection are supported, with no automatic rank selection. Strict JSON parsing
establishes canonical self-consistency only; independent report reconciliation
must be invoked to verify external evidence.

There is no WALK_FORWARD_PASSED policy yet. Architecture 138 must separately
freeze ResearchCandidateWalkForwardQualificationPolicy; existence of a
walk-forward result grants no passed stage. Broad historical portfolio variants
are not equivalent to the current production moving-average strategy. No
research-to-production compatibility claim, production contract, approval,
promotion or execution material is introduced. Compatibility and human promotion
remain separate future reviewed boundaries.

Canonical current inventory is ACTIVE 62 / FULL 170 / ROBINHOOD 94 / LEGACY 215 /
EXHAUSTIVE 385 / tests/gui 44. No ACTIVE production checkpoint is added. Current
inventory assertions and only three directly affected retained test-file blob
pins are reconciled; executable/native/AST pins, ACTIVE tuple/digest, historical
publication-recovery pins and production push allowlist remain unchanged.

R1 `6bf8753b0cc8950ae27b32b6858b64d454c512f0` and R2
`2f122958366d1db282fea51abbd461b83fa893d9` remain frozen. D1 proving remains
independent/protected; D2 is disconnected. No production SQLite, credentials,
provider, broker, scheduler, ACL, paper, research execution, walk-forward
execution, strategy promotion or production contract effect occurred.
Real-money broker placement remains **NO-GO**.

Immediate handoff: Codex completes focused checks and ordinary commit/push, then
dispatches Checkpoint Source Gates on this exact research branch and waits for
source-static plus four full-tests shards and terminal source-gates success
(active-tests/certification-tests skipped). No GUI run or local broad profile is
requested. ChatGPT then reviews the exact final GitHub HEAD/tree/diff and CI and
owns acceptance/closeout. The next research design boundary after acceptance is
Architecture 138; D1 remains an independent operational milestone.

See `docs/architecture/137-research-candidate-lifecycle-foundation.md` and
`docs/validation/arch137-research-candidate-lifecycle-plan.md` for the frozen
contract, focused evidence, exact verification commands and stop conditions.

## 2026-10-12 — Current D1Q-R2 operational state / GUI-A14 checkpoint

This current entry supersedes pending/failed R2 wording in the dated historical
entries below. Architecture 134-D1Q-R2 source is accepted on
`feature/robinhood-production-paper-runtime-acl`:

```text
HEAD 2f122958366d1db282fea51abbd461b83fa893d9
TREE c3fb82add37bdbea12ebad9836ca10000b924fe1
CI #504 / 38305872664 SUCCESS
ROBINHOOD 8644 cases / 8643 passed / 1 skipped / 0 failed / 0 errors
wall 222.459 s
```

The accepted protected ACL operation recorded PROVISIONED / PASS, three apply
attempts and three verified applies. Parent, recursive, credential, provider,
paper, session, scheduler and broker mutation/call counts were all zero.
Independent non-elevated postcheck recorded ALREADY_PROVISIONED / PASS.

Hardened D1Q-R1 qualification remains bound to the unchanged runtime source:
HEAD `6bf8753b0cc8950ae27b32b6858b64d454c512f0`, TREE
`ce3feb2ac48e7aebc23970142aafed5059c447e7`. Read-only preflight recorded
PRESENT_COMPATIBLE, paper_records=0 and session_reservations=0. Protected
qualification recorded READY_FOR_MANUAL_PAPER_SESSION,
runtime_status=ALREADY_PROVISIONED, both paper/session-store write readiness
WRITE_READY, alpaca_credential_reads=2, robinhood_credential_reads=2 and
persisted_oauth_available=true. Alpaca HTTP calls, Robinhood application calls,
paper trade mutations, scheduler mutations and broker mutations were all zero.

These are accepted recorded operational facts supplied for serialization, not
new qualification performed by GUI-A14. No real evidence is read by source
tests. The first D1 manual production-paper session remains the next operational
proving step and has not been accepted. B3Q remains consumed/no-retry.
Real-money broker placement remains **NO-GO**.

GUI-A14 is implemented on `feature/gui-production-runtime-status` from the
exact R2 parent above, in
`F:\AI\worktrees\ai-trading-bot-gui-production-runtime-status`. It presents only
explicit ACL/qualification/session JSON through bounded immutable GUI models.
Runtime, System and Evidence navigation add zero reads. Complete real-PySide6
offscreen GUI verification passes; exact results are in
`docs/validation/gui-a14-production-runtime-status.md`. Accepted R1/R2 execution
source, source pins and branches are unchanged. GUI-A14 is SOURCE ACCEPTED:
HEAD `c29bb678dd7c64a317de602b81ba9df0aa8e1bd8`, TREE
`921b7b32bbfecbb454acc8916faa4362464b19d3`; dedicated GUI CI 38325919046
SUCCESS and repository source gate 38326059553 SUCCESS.

The earlier local-only bootstrap decision is historical and resolved by the
accepted A14 CI chain. Current GUI-A15 is presentation-only: an explicitly
selected canonical production contract may be inspected read-only. A historical
research report is evidence, not research process liveness. A15 introduces no
canonical candidate/promotion artifact. Automatic promotion remains disabled;
human promotion remains required; promotion authority and D2 supervisor are
not connected. No D2 effects are implemented. R1/R2 source remains frozen;
ChatGPT owns exact source/CI acceptance. See Architecture 136.

### Current D2 end-state — ON/OFF, arbitrary-time startup

This standing design supersedes any current D2 requirement to wake a sleeping
PC. The PC is either ON or OFF and is never intentionally asleep while bot
operation is expected. D2 must not require WakeToRun, wake timers, sleep-resume
state or wake-from-sleep qualification. This is a design serialization only;
GUI-A14 adds no D2 executable behavior.

PC OFF: the bot is not running. PC ON: a runtime supervisor runs/reconciles,
deriving legal state from current authoritative time, published market-session
authority and durable state. Arbitrary-time startup is required. Conceptual
trading states are RECONCILE, PREMARKET_WAIT, TRADING, NEXT_SESSION_WAIT and
BLOCKED; exact names can be frozen later.

Startup during an admitted session qualifies/reconciles and trades only if
otherwise permitted. Startup before a published session waits for admission;
startup after today's session, on weekends or holidays resolves the next
published session and waits instead of terminating on an expired date. Restart
recomputes current reality from time/durable state and never trusts an old sleep
duration. Task Scheduler, if retained, supplies only automatic start/restart
while the PC is ON, never wake authority or trading-session authority.

The AI research/strategy-testing plane remains operational while the overall
process runs, independently of trading-plane waiting/admission. Research
candidates never silently replace the production strategy. Promotion remains
versioned, reviewed and certified. Manual D1 proving still precedes D2 effects.

## 2026-10-11 — Architecture 134-C CERTIFIED/CLOSED

Architecture **134-C — Human-started production live-paper cycle** is
**CERTIFIED/CLOSED** at this exact source-certification boundary:

~~~text
BRANCH      feature/robinhood-production-strategy-live-paper
HEAD        bcda794f8b371b097143a331d678009143cb91b1
TREE        96a36cf38133ae3547175fe75547a4e16f1deb48
CI          #471 / 38133206242 SUCCESS
CHECKPOINT  arch134-production-strategy-live-paper
CORRECTION  bcda794f8b371b097143a331d678009143cb91b1
SUBJECT     test: stabilize checkpoint topology assertions
~~~

### Preserved failed FULL and bounded source correction

The first FULL attempt on prior source
`144a66928d9f3fb3d7ff5396059c998839e17a99` /
`04f7ade45d5fdf1e4e6969db8a9b1db5484fa8b2` found 22 stale historical
test-topology assertions after the active inventory grew to 60 checkpoints.
Its failed evidence is preserved and must not be overwritten or reused:

~~~text
F:\AI\temp\certification\arch134c-full-e210ffcf373748d593a2df83f7b39512
~~~

The bounded test-only correction:

- replaced fragile end-relative checkpoint slices with named/local adjacency;
- removed historical tests' unowned repository-wide eventual-count assumptions;
- confined generic registration mutations to their intended `CheckpointSpec`;
- preserved the dedicated canonical full-topology expectation;
- preserved production behavior, authority, registration, workflow and source
  pins.

The separately approved publication-recovery test expectation proves that only
the historical whole-registry pin differs after later registrations and that
the unchanged protected authority rejects that drift exactly. It does not
refresh a pin or reopen historical recovery authority.

Source gate [#471](https://github.com/callmedraken/ai-trading-bot/actions/runs/38133206242)
is terminal green:

| Job | Conclusion |
| --- | --- |
| source-static | SUCCESS |
| active-tests | SUCCESS |
| full-tests | SKIPPED, correct active-branch behavior |
| source-gates | SUCCESS |

### Final cheap gates before FULL

Exact source/FULL topology plan, `git diff --check`, Ruff check and Ruff
format check all passed before the expensive suite. Ruff format check reported
919 files already formatted. The plan evidence is:

~~~text
F:\AI\temp\certification\arch134c-final-full-plan-ae24aee5c593433683993fbccafa70d7
~~~

### Final FULL certification

| Lane | Modules | Cases | Passed | Skipped | Failed | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| broad-1 | 80 | 4,764 | 4,764 | 0 | 0 | 0 |
| broad-2 | 81 | 4,320 | 4,320 | 0 | 0 | 0 |
| Total | 161 | 9,084 | 9,084 | 0 | 0 | 0 |

~~~text
profile full PASS
wall 446.814 s
evidence F:\AI\temp\certification\arch134c-final-full-e971d0c5bfda496ebde97a6fc04d1afb
~~~

No separate ROBINHOOD run was required: ROBINHOOD is a strict subset of FULL,
and this selected FULL certification satisfies the narrower source-certification
obligation on the same source. No LEGACY/EXHAUSTIVE run was required. No
provider/OAuth/paper/scheduler/broker/protected effect occurred.

Current exact inventories are active **60**, FULL **161**, ROBINHOOD **86**,
LEGACY **205**, EXHAUSTIVE **366**. The executable/test source is unchanged by
this six-file docs-only closeout. **Do not rerun FULL on that unchanged source.**

### Immediate next boundary: separately authorized SHADOW PREPARE

The next step is a **human-started 134-C SHADOW PREPARE**, using the already
accepted Architecture-131 provider-read path. It requires fresh explicit
authorization because a trade proposal performs real Robinhood/provider/OAuth
read activity. No effectful command is ordinary verification, and this closeout
stops at that protected authorization boundary.

PREPARE is shadow/live-data preview only; it performs no paper fill.
`NO_SIGNAL` has zero provider/paper effects. **`READY_TO_PROCEED` is evidence,
not execution authorization.** Only after a separately authorized PREPARE
returns and ChatGPT reviews its evidence may a separate paper EXECUTE
authorization be considered if the retained result is `READY_TO_PROCEED` and
Architecture-131 revalidation still passes. Real broker placement remains
impossible. 134-C certification does not authorize 134-D scheduling/arming;
134-D remains later.

### Docs-only closeout and repository rules

This atomic checkpoint changes exactly the six approved `docs/**` files and
uses the existing docs-only classifier's cheap validation path. It changes no
Python, tests, scripts, workflow YAML, checkpoint registration or runtime
behavior and manufactures no test rerun.

`AGENTS.md` was reviewed and remains compatible: it already forbids repeated
expensive full-suite runs and delegates detailed certification behavior to
Architecture 132 and the workflow document. It remains unchanged because it is
outside `docs/**`. A future naturally necessary non-docs workflow checkpoint
may mirror the detailed wording there without creating a standalone duplicate-
test event.

## 2026-10-11 — Architecture 134-B SOURCE ACCEPTED

Architecture **134-B — Production Strategy Decision Bridge** is source accepted.

~~~text
BRANCH  feature/robinhood-production-strategy-decision
HEAD    695fa6195b2d8cc1437ba87f5d48c527afa28da7
TREE    00871d80bc9ae0a3f60906d23c92b30e42c670c4
CI      #465 / 38128865894 SUCCESS
~~~

The accepted bridge consumes the exact 134-A production contract plus the
existing Architecture-94 verified strategy-decision request/calendar boundary.
It checks contract config and verified seed symbol/config before the builder,
invokes `build_manual_paper_strategy_decision(...)` exactly once, then requires
the prepared config/symbol/intended session to remain inside the production
contract.

Closed outcomes are exactly `NO_SIGNAL` or `TRADE_PROPOSAL`; a proposal is the
exact Architecture-94 proposal object by identity, not a newly generated or
research-selected proposal.

Source gate #465 passed static diff/Ruff/format/authority, focused pytest, stable
identity and terminal source-gates. The earlier #462/#464 failures were
mechanical Ruff formatting only and are superseded.

Current exact inventories are active **59**, FULL **160**, ROBINHOOD **85**,
LEGACY **205**, EXHAUSTIVE **365**. Broad certification remains deferred until
the first coherent live-paper integration boundary.

134-B owns no Robinhood/provider/OAuth, paper-store mutation, risk execution,
scheduler, clock/sleep, research/AI promotion or broker placement authority.

Next milestone is **134-C — Human-started production live-paper cycle**.
`PREPARE` will serve as the shadow/live-data preview: for a `TRADE_PROPOSAL`,
reuse the accepted Architecture-131 supervised PREPARE path to obtain one live
Robinhood quote, session admission and deterministic risk preview with no paper
mutation. `NO_SIGNAL` performs no provider call. A separate explicit EXECUTE
may then reuse the accepted Architecture-131 review-paper execution path to
record one synthetic local paper fill; real broker placement remains impossible.

## 134-A verification scope

Implementation is source-only and uses fake/pure values. No real host/provider/
scheduler/paper effect is part of this checkpoint.

Focused tests must prove:

- exact schema, strategy ID/version and one-symbol shape;
- valid/invalid source HEAD/TREE formatting;
- exact target-session `date` type; booleans/strings/subclasses are rejected as
  appropriate rather than coerced;
- reuse of the existing `MovingAverageCrossoverConfig` validation;
- canonical finite positive desired quantity serialization including exponent/
  trailing-zero normalization rules chosen by the source contract;
- deterministic contract ID stability and sensitivity to every semantic field;
- different serialized formatting/path/hash cannot redefine semantic identity;
- strict canonical JSON round-trip with exact fields and duplicate/unknown/
  missing field rejection;
- canonical parser rejects noncanonical decimal/date/UUID/strategy spellings;
- strategy-construction helper returns exactly
  `MovingAverageCrossoverStrategy` with the same exact config;
- no evaluation occurs while constructing/parsing/replaying the contract;
- source module import closure excludes provider/MCP/OAuth, SQLite/paper store,
  scheduler, runtime native code, AI/model/research/optimization and execution;
- AST/capability checks reject file/network/subprocess/environment/dynamic-import/
  sleep/clock/effect calls;
- no promotion/candidate-selection API is exposed;
- checkpoint registration has `preflight=None`, `execute=None`; branch route is
  exact and unique;
- audited split/sharded source-gate topology remains reviewed.

Expected implementation files:

~~~text
src/trading_bot/strategies/production.py
tests/strategies/test_production_strategy_contract.py
scripts/checkpoint_runner.py
.github/workflows/checkpoint-source-gates.yml
~~~

Existing exact inventory/count assertions made stale by this one legitimate
module/checkpoint addition must be updated without weakening equality/order/
partition checks. Expected totals after 134-A:

~~~text
active checkpoints  58
FULL               159
ROBINHOOD            85
LEGACY              205
EXHAUSTIVE          364
~~~

Run only focused affected tests plus non-mutating Ruff check/format and
`git diff --check`. Do not run broad certification during implementation.

## Acceptance boundary

Source acceptance of 134-A authorizes only later design/implementation of
134-B. It does not authorize a market-data read, live PREPARE, paper mutation,
arming, waiting, scheduler change, unattended wake, candidate promotion or
broker effect.

## Later validation ladder

134-B: deterministic provider-free strategy decision replay.

134-C: shadow qualification first; then one separately authorized live-data
review-paper qualification with independent durable reconciliation.

134-D: time/session-state tests plus protected scheduler/startup qualification;
hard-coded local market-open time is forbidden because DST/session exceptions
must come from published exchange-session authority.

134-E: exactly one unattended integration session and independent reconciliation.

134-F: fresh multi-session live-paper soak with end-of-window review.

Research lane: historical/backtest/walk-forward tests plus explicit proof that
candidate writes cannot reach production selection, paper account, scheduler or
provider execution surfaces.


## 134-C validation contract

Focused source tests must prove:

- exact 134-B decision type required;
- `NO_SIGNAL` returns without invoking Architecture-131 PREPARE or touching
  store/adapter/risk surfaces;
- target-session mismatch blocks before PREPARE;
- TRADE_PROPOSAL retains and forwards the exact proposal by identity;
- Architecture-131 PREPARE is invoked exactly once;
- every existing supervised preparation status maps exactly to the closed 134-C
  status without inventing execution authority;
- wrapper retains the exact supervised preparation by identity;
- execute rejects anything except exact `READY_TO_PROCEED`;
- expected HEAD/TREE must exactly equal the production contract's source
  HEAD/TREE before Architecture-131 EXECUTE is called;
- Architecture-131 EXECUTE is invoked exactly once and its exact result is
  retained;
- no retry/reacquisition loop or alternate provider/paper implementation;
- no broker placement/cancel/options/crypto capability;
- no scheduler/arming/wait/sleep or AI/research promotion capability;
- checkpoint registration is source-only and exact branch routing preserves the
  audited split/sharded workflow;
- exact inventories become active 60 / FULL 161 / ROBINHOOD 86 / LEGACY 205 /
  EXHAUSTIVE 366.

Run focused tests, non-mutating Ruff check/format and diff check only. Do not
perform a real provider PREPARE, OAuth interaction, paper mutation or broad
certification during implementation.

This original 134-C statement is **superseded by 134-B2/134-B3** for the
current product path. Before the first real 134-C qualification, 134-B3 must
source-accept current market-history acquisition/materialization and the pending
ROBINHOOD certification must pass on that coherent current-decision source.
Only then may a separately authorized human-started **shadow PREPARE** be
considered. A paper EXECUTE remains a second separately authorized step and is
permitted only if the retained PREPARE remains `READY_TO_PROCEED` and all
Architecture-131 revalidation passes.

## Historical 134-B compatibility validation contract

Focused tests must prove:

- exact 134-A contract type required;
- exact Architecture-94 request type and calendar boundary required;
- contract/request strategy-config mismatch blocks before the Architecture-94
  builder is called;
- contract/history-seed symbol mismatch blocks before the builder is called;
- Architecture-94 builder is invoked exactly once on success;
- returned prepared object is retained by identity, never serialized/rebuilt;
- intended execution session must equal the production contract target date;
- prepared config/symbol drift blocks;
- `NO_SIGNAL` returns no proposal;
- `TRADE_PROPOSAL` returns the exact prepared proposal object by identity;
- malformed/inconsistent builder results fail closed;
- no second strategy evaluation is introduced in the bridge;
- import/call surface excludes provider/OAuth/network, paper/SQLite, risk,
  execution/review/order, scheduler/clock/sleep, filesystem/Git/environment,
  runtime/native and research/AI/optimization capabilities;
- no candidate/promotion API;
- checkpoint registration is exactly source-only with the exact 134-B branch;
- active route is unique and audited split/sharded source-gate topology remains
  reviewed;
- all exact inventory expectations are updated to active 59 / FULL 160 /
  ROBINHOOD 85 / LEGACY 205 / EXHAUSTIVE 365 without weakening invariants.

Expected primary implementation surfaces:

~~~text
src/trading_bot/strategies/production_decision.py
tests/strategies/test_production_strategy_decision.py
scripts/checkpoint_runner.py
.github/workflows/checkpoint-source-gates.yml
~~~

Use focused tests plus non-mutating Ruff check/format and diff check. Do not run
FULL/ROBINHOOD/LEGACY/EXHAUSTIVE during implementation.

134-B source acceptance does not authorize 134-C live shadow/provider access or
paper mutation.

This section records the original Architecture-94-facing 134-B compatibility
contract. It is retained as historical regression provenance; it is no longer
the normative current-product materialization path after accepted 134-B2.


## 2026-10-11 — 134-B2 SOURCE ACCEPTED

Architecture 134-B2 current-product decision materialization is source accepted:

~~~text
BRANCH feature/robinhood-production-strategy-live-paper
HEAD   1e3c74649aeb6f0f90881b1495fec0350c22ae5e
TREE   b9ac7a11a39d07252ab85fd7b197b31590a825b9
CI     #478 / 38175971808 SUCCESS
~~~

The accepted current-product decision materializer is provider-free and uses
explicit verified snapshot/history evidence plus read-only `ReviewPaperStore`
state.

Focused validation must prove:

- exact 134-A contract is required;
- current verified snapshot/history symbol/config/session match the contract;
- current synthetic-paper prior derives from `ReviewPaperStore` evidence, not
  Paper-v2;
- no code path constructs or forges Architecture-94's protected
  `VerifiedPriorCheckpoint` from ReviewPaperStore;
- the pure Architecture-94 strategy-decision core is shared by the legacy and
  current-product adapters;
- the existing Architecture-94 entry point retains its exact behavior and
  authority validation;
- the Robinhood adapter calls the shared pure decision core exactly once and
  returns through the accepted 134-B closed decision contract;
- exactly one strategy evaluation occurs; no second proposal synthesis exists;
- no D10/Windows/C1/C3/Paper-v2/personal-desktop unattended imports or calls;
- no Robinhood/OAuth/provider/network effect in the materializer;
- no scheduler, broker, live-order, research-promotion or filesystem-repair
  authority;
- missing/insufficient current history fails closed instead of inventing bars;
- source-gate/profile inventory changes remain exact.

Do not repair the observed legacy Paper-v2 root ACL as part of 134-B2. That
diagnostic is preserved only to explain why the legacy observability route was
abandoned.

After exact GitHub review and terminal-green source-gate CI, select only the
smallest distinct certification required by the changed current-product
surface. Do not rerun FULL merely for confidence.

Exact current inventory is FULL **163**, ROBINHOOD **88**, LEGACY **205**,
EXHAUSTIVE **368**.

ChatGPT source review accepted the exact commit above. No ROBINHOOD/FULL run is
required at this intermediate source-only checkpoint: real current-history
acquisition/materialization remains a separate source checkpoint before any
protected PREPARE is possible. The pending **ROBINHOOD** certification is
batched to that coherent current-decision boundary and must pass before the
first real protected SHADOW PREPARE. FULL remains unnecessary unless later
source breadth creates a separate consequential current-product obligation.

This 134-B2 acceptance supersedes the earlier dated 134-C closeout statement
that called SHADOW PREPARE the immediate next boundary.

The next source milestone is **134-B3 — current market-history acquisition and
verified evidence materialization**. It must define the exact current provider/
persistence authority for the snapshot/history evidence consumed by 134-B2.
It must not revive Paper-v2/C1/C3/D10 operational dependencies. Provider/OAuth
effects, if required for qualification, remain separately protected and are not
authorized by this source acceptance.

## 134-B3 — Current Robinhood market-history evidence (CERTIFIED/CLOSED)

The current source checkpoint remains `arch134-production-strategy-live-paper`
on `feature/robinhood-production-strategy-live-paper`, with no preflight/execute
registration. B3 adds two owned test modules to that existing source gate;
active count stays 60. FULL/ROBINHOOD/LEGACY/EXHAUSTIVE inventory is now
165/90/205/370. Frozen required baselines remain 122/49.

B3 source/certification closeout:

~~~text
BRANCH      feature/robinhood-production-strategy-live-paper
HEAD        7ef32ec87dbcfeea4d5436c424cdbb0eb16e1058
TREE        738f078722337903ba7daf950bf19078167a75e4
CHECKPOINT  arch134-production-strategy-live-paper
CI          #482 / 38181823892 SUCCESS
~~~

The first ROBINHOOD certification on
`fde8cb35256e4448fef20e666f00b0d687b3f423` ran 8,269 cases and failed only
three stale current-profile inventory assertions. Its failed evidence is
preserved at:

~~~text
F:\AI\temp\certification\arch134b3-robinhood-4eaa0b0201cf43a19c420d00d5bbced5
~~~

The bounded test-only correction changed no production behavior, authority,
classification, topology or baselines. Final ROBINHOOD certification on the
exact HEAD/TREE above passed **8,269/8,269** cases across **90** modules:
robinhood-1 3,865/3,865 and robinhood-2 4,404/4,404, zero
skips/failures/errors, wall 325.912 s. Evidence:

~~~text
F:\AI\temp\certification\arch134b3-robinhood-b14f5add0e5040599b093c7238b01a54
~~~

No FULL/LEGACY/EXHAUSTIVE rerun and no protected provider/OAuth/paper/scheduler/
broker effect was required for B3 closure.


`RobinhoodDailyHistoryRequest` derives exactly `long_window + 1` consecutive
sessions through the exact bound XNYS calendar, checks them against the existing
NYSE published regular-session authority, and admits only completed sessions.
Published coverage remains 2026-2028; requests requiring earlier history fail
closed. The MCP range runs from the first regular open through the last regular
close. The only request is `get_equity_historicals` with one exact contract
symbol, explicit UTC bounds, `interval=day`, `bounds=regular`, and
`adjustment_type=none`. No interval/adjustment defaults, pagination, retries,
interpolation, alternate provider, CSV, quotes-as-history or inferred bars.

The strict parser requires the documented structured `data/results/bars` and
`guide` shape, one exact result, exact symbol/daily/regular semantics, all
required bar fields, explicit `session=reg` and `interpolated=false`, positive
integer traded volume and bounded positive decimal OHLC. Unknown fields,
missing/unresolved symbols, malformed/non-UTC timestamps, unknown/midnight
labels, duplicate/missing/out-of-order/nonconsecutive sessions, extra bars,
invalid OHLCV, split/dividend adjustment echoes or insufficient history fail
closed. Optional adjustment echo must be `none` if present. Bars must have
left-edge labels equal to the published regular opens; DST and early closes
are calendar-bound. No transformation or invented daily aggregation occurs.

`materialize_production_strategy_history` replays retained canonical structured
response bytes and checks exact contract symbol/config/session and capture time.
The prior completed session goes through existing snapshot acceptance,
serialization and `verify_daily_snapshot` to obtain
`DailySnapshotVerificationResult`. The snapshot audit hashes the canonical
structured response (not purported raw HTTP bytes). The preceding configured
consecutive bars go through `create_strategy_history_seed`, canonical
serialization and `verify_strategy_history_seed` to obtain
`VerifiedStrategyHistorySeed`. Existing history-seed schema, IDs, verifier,
`OFFLINE_SEED` classification and `authoritative=false` remain unchanged.
Provider provenance belongs to an outer `robinhood-strategy-history-evidence/v1`
envelope retaining request, structured response, XNYS session sequence and times.
Hashes are audit evidence only, never deterministic semantic identity material.
Canonical snapshot, seed and outer bytes are returned in memory; this checkpoint
adds no filesystem persistence or paper-store mutation boundary.

`acquire_production_strategy_history` permits exactly one adapter historical
read and one caller-injected capture-time observation. Production invocation
is separately protected; source tests inject fakes. The pure
`build_production_strategy_decision_from_history` replays all evidence and
delegates exactly once to accepted 134-B2. No legacy Paper-v2/D10/C1/C3/Alpaca
authority, `VerifiedPriorCheckpoint`, new evaluator, research promotion,
SHADOW PREPARE or paper execution is introduced.

The exact application read/review allowlist is now four public tools:
`review_equity_order`, `get_equity_quotes`, `get_equity_orders`, and
`get_equity_historicals`; `get_accounts` is private/internal. Capability
enumeration requires all four; extra advertised broker tools never become
application capabilities. Placement/cancel/options/crypto remain excluded.

B3 source/certification is closed. Real-server qualification remains the next
separately protected boundary. The published tool metadata documents raw
`none` request semantics but no required response adjustment echo; request
honoring must be qualified. Daily regular-open left-edge labels and explicit
false interpolation/regular-session flags must also be qualified. `close_price`
means the last trade in the regular daily bar, not an official settled close.
Any mismatch blocks materialization rather than weakening the parser. The
qualification may perform only the explicitly authorized read-only provider/OAuth
effect; persistence/operator wiring, SHADOW PREPARE, paper execution, scheduler
mutation and broker placement remain outside this closure.

Focused B3 validation covers malformed/missing/unknown schema fields, wrong
symbols/sessions, non-daily/non-regular/adjusted semantics, absent interpolation
flags, gap fills, duplicate/missing/nonconsecutive/extra/future bars,
insufficient long-window history, DST/holiday/early-close boundaries, invalid
prices/volumes, evidence tampering, Decimal-context independence, unchanged
inner identities/classification, exactly one historical read, no fallback,
exact four-tool capability admission and preserved mutation exclusion. B2
composition tests require one strategy evaluation and byte-stable paper state.
Strict source pins and authority-mutation tests reject capability/import drift.

Only affected pytest modules, cheap authority/static/diff gates and non-mutating
Ruff checks are run locally with a fresh external Windows basetemp. Source CI
must reach terminal green before handoff. No ROBINHOOD/FULL/LEGACY/EXHAUSTIVE,
real provider/OAuth, SHADOW PREPARE, paper execution or protected effect is part
of this implementation checkpoint. ChatGPT exact-source review and later
certification/real-server qualification remain separate.


## 134-B3Q — Source-owned historical qualification operator (SOURCE ACCEPTED / ROBINHOOD CERTIFIED)

B3's accepted parser, request, four-tool transport allowlist and materializer
remain unchanged. B3Q prepares the already scoped single read-only qualification;
source implementation/CI uses fakes only. This section is the current operator
path; earlier B3 closure statements describe the pre-operator source boundary.
It does not certify the live server or consume provider authorization.

The reviewed entry point is `scripts/qualify_robinhood_history.py`. Its only
operator inputs are exact expected source HEAD/TREE, an external fresh evidence
file, and a mode/interlock. There are no symbol/window/time/interval/bounds/
adjustment/account/provider arguments. Frozen v1 inputs are **SPY**,
**long_window=3** (four completed sessions), and a 2/3 moving-average config
used only for existing B3 materialization validation, never strategy evaluation.
The desired quantity `1` is a required config field, not an order or risk input.

One actual UTC clock observation supplies `requested_at`. The current New York
session date must be published by existing XNYS authority; weekends, holidays,
missing published coverage and insufficient predecessor coverage block before
OAuth. The request selects exactly the three predecessors plus the prior
completed session through `RobinhoodDailyHistoryRequest`. The resulting range
is first regular open through last regular close, with exactly `interval=day`,
`bounds=regular`, `adjustment_type=none` and `symbols=["SPY"]`. A pre-open
observation on a published session date is permitted. Capture must remain on
that same session date and follow both request and call-start observations.

Before OAuth, require exact clean tracked/untracked/index source, fixed feature
branch, fixed origin, local remote HEAD/TREE and live remote HEAD. Reject mixed
`trading_bot` import roots. Re-admit exact source after the response. No fetching,
branch repair or repository mutation belongs to the operator. Evidence must be
an absolute fresh path outside every repository worktree with an existing
parent. Exclusive creation rejects collision before OAuth/provider access.

`--preflight` is provider/OAuth/credential-free and writes no evidence. It checks
source/calendar/output readiness and reports the derived request; it grants no
call authority. Protected execution requires the exact interlock
`AUTHORIZE_ARCH134_B3Q_ONE_HISTORICAL_READ`. OAuth uses the accepted Windows
factory with source-owned `http://127.0.0.1:8765/callback` and a browser handler
that refuses interactive renewal. Persisted OAuth/session establishment and
MCP capability enumeration remain the accepted transport's responsibilities.

An enclosing transport exposes only `get_equity_historicals`, validates exact
request arguments, and delegates at most once. No `get_accounts`, quotes,
orders, review, placement, cancel, options, crypto, SHADOW PREPARE, store access,
paper fill, scheduler/runtime mutation or broker execution is invoked.
The four-tool allowlist and capability enumeration are not broadened. The raw
structured response goes through the unchanged `RobinhoodReviewReadAdapter`
and strict B3 parser, then unchanged `materialize_production_strategy_history`.
Missing explicit flags, timestamp labeling, adjustment/schema drift, gaps,
duplicates, reordering, extras and insufficient history remain failures.
No transformation, alternate parser, fallback provider or retry can make a
rejected live response pass.

Evidence is a canonical JSONL journal bounded to **64 KiB**. Each complete
record is flushed and fsynced. Reservation records `BLOCKED`/zero attempts;
before transport control, a durable `CALL_STARTED` record carries
`AMBIGUOUS_PROVIDER_EFFECT`/one attempt and the call-start timestamp. A
terminal record reports `PASS`, `BLOCKED`, `FAIL` or
`AMBIGUOUS_PROVIDER_EFFECT`, fixed reason, exact source HEAD/TREE/branch,
arguments, ordered session dates, request/capture timestamps, tool and attempt
count. Counts describe attempted transport-boundary calls, not proof that an
HTTP application request was sent. Any unclassified transport failure is
conservatively ambiguous, including a failure that may have occurred before
sending. Returned structured data rejected by B3 is `FAIL`. All failures stop;
none grants retry. Interruption or terminal publication failure leaves the
pre-call ambiguity fence. Partial/truncated evidence must never be called PASS.
Preserve it for read-only reconciliation and human review.

Only strict-parser-validated historical `data` is retained, plus `guide_present`
and hashes. Arbitrary `guide` text, malformed payloads, OAuth errors, credential
material, URLs/auth capabilities and account identifiers are never persisted;
provider stdout/stderr/logs/warnings are discarded. The SHA256 of the original
canonical complete response is audit-only. A separate digest binds the retained
canonical historical data. PASS evidence can be replayed with `--replay` through
the same parser/materializer without any provider/OAuth call. Since the free-form
guide is deliberately omitted, replay supplies a fixed nonblank disclosure only
after checking canonical PASS evidence, source identity, ordered journal,
arguments, sessions, capture ordering and retained-data digest. It neither
reconstructs the original guide/snapshot audit bytes nor claims to verify the
original full-response hash. All historical fields remain exact; this sanitized
evidence replay cannot serve as a live-response fallback or strategy authority.

B3Q belongs to existing `arch134-production-strategy-live-paper` registration.
The registered source gate includes the new fake-only test module, CLI/operator
Ruff paths and source/AST authority pins. `preflight=None`, `execute=None` stay
unchanged: the CLI is the explicit separately reviewed protected surface, never
an `ops.ps1 execute` effect. No workflow/topology/checkpoint-family change is
needed. Active inventory stays **60**; FULL/ROBINHOOD/LEGACY/EXHAUSTIVE now
**166/91/205/371**, required baselines unchanged **122/49**. Implementation runs
focused checks only; no broad profile certification or real call is performed.

Exact GitHub review accepts B3Q source at
`2a11a2597a2edad8351e50a25d9454420318089f` /
`80b16dd877c0c5a56f5572922d3fa4c77e940f4d`; push-triggered source gate
#484 / 38190487015 is terminal SUCCESS. No source correction is required.

The selected ROBINHOOD certification passed on the exact final
docs-only source `473b18ce4cbc2ff9c7d4f793d7ae4e316e585471` /
`f7ffc107f9f9206e857049dd9ea178ec612a0c26`: robinhood-1 passed
4,027/4,027 across 45 modules; robinhood-2 passed 4,310/4,310 across
46 modules; total **8,337/8,337**, zero skips/failures/errors, wall
272.922 s. Evidence is preserved at:

~~~text
F:\AI\temp\certification\arch134b3q-robinhood-1a7d9742efd3439797c3ed713837e29c
~~~

No FULL, LEGACY or EXHAUSTIVE run is selected.

The previously granted user authorization for exactly one read-only
`get_equity_historicals` qualification remains valid and unconsumed. The next
action is the provider/OAuth-free B3Q preflight on this exact final source. If
preflight passes on a published XNYS session date, ChatGPT may consume the
existing one-read authorization without another approval round because the
reviewed effect scope is unchanged. Any preflight failure, live FAIL or
AMBIGUOUS_PROVIDER_EFFECT is a STOP with no automatic retry and no later SHADOW
PREPARE, paper execution, scheduler mutation or broker authority.

### B3Q real-server qualification result — AMBIGUOUS / NO RETRY

The single authorized live qualification was consumed on
`5f2728bb409ef479475619100cba3fb1fdac18f5` /
`a51c7aed8a1697b88dbdbc732b863eb5932c4ef9` after provider-free preflight
PASS. Preserved evidence:

~~~text
F:\AI\temp\qualification\arch134b3q-history-19c8c572a3d8447f9488cb5d3a11f4db.jsonl
~~~

The journal reached the durable `CALL_STARTED` fence and then terminated
`AMBIGUOUS_PROVIDER_EFFECT / CALL_RESULT_UNCLASSIFIED` with one
transport-boundary attempt. No structured response returned to the B3Q wrapper:
`captured_at`, retained response and both response/data digests are null.
Accordingly, the observed failure is below the strict B3 parser/materializer
boundary. It remains impossible from this evidence to prove whether an MCP
application request was actually sent or received.

The authorization is consumed and no retry is permitted. Do not manufacture a
new evidence destination, repeat `get_equity_historicals`, downgrade the
ambiguity to FAIL, or weaken accepted parsing semantics. The next safe source
checkpoint is a provider-free/read-only reconciliation diagnostic for preserved
evidence plus local dependency/OAuth readiness. Any actual credential access or
provider call remains outside that source-only checkpoint and must use its own
reviewed authority. 134-D Armed Session Mode design/source work may proceed
independently on a separate branch.


## 134-D1 - Armed paper MVP source validation and remaining protected boundary

This section retains historical D1 validation provenance. Its inert credential
seam and later runtime next step are superseded by D1Q and D1Q-R1 below.

134-D1 source tests use the concrete Alpaca daily provider/strict parser with a
fake HTTPS transport, real B2 strategy/prior/snapshot/seed validation and real
134-C/Architecture-131 PREPARE/EXECUTE cores. The only execution effect is a
fake paper operator against fresh test-only stores. No actual credentials,
Alpaca/Robinhood/OAuth, production store, scheduler or broker effects are used.

Focused coverage includes exact ordered completed sessions, holiday/weekend/DST,
accepted raw history and canonical verification, missing/duplicate/reordered/
wrong-symbol/pagination rejection, stop-at-first-failure/no retry, exactly one
strategy evaluation, NO_SIGNAL with unchanged paper bytes and zero Robinhood,
pre-open waiting, immediate admission, early/double/late/wrong-date wakes, source
drift, single PREPARE, risk/expiry stops, single accepted EXECUTE, duplicate
launch/reopen/different contract, existing session fill, atomic concurrent claim,
crash before history/after EXECUTE fence, ambiguous fill, terminal publication
failure, bounded sanitized/tampered evidence, semantic CLI exclusion, inert
credential seam, isolated actual import closure and exact-pin/AST mutation tests.

The regression selection includes affected B2/B3/B3Q/134-C, Alpaca parser/HTTPS,
131 risk acquisition/supervised PREPARE/EXECUTE, runner/CI and inventory tests.
Only mechanical current inventory assertions change: active 61, FULL 167,
ROBINHOOD 92, LEGACY 205, EXHAUSTIVE 372. Existing B3/B3Q tests and source are
untouched. Required frozen baselines and prior source pins remain unchanged.
Implementation focused verification passed 967 distinct selected cases, including
59 D1 cases, across the regression run and affected-only repairs. Ruff check
and format passed all 11 changed Python files; diff and exact authority passed.
Every pytest invocation uses -B, -p no:cacheprovider and a fresh explicit
F:\AI\temp\pytest\arch134d1-* basetemp. Both non-mutating Ruff phases and
non-mutating failure diffs precede a combined PASS/STOP, plus git diff --check.
FULL/ROBINHOOD/LEGACY/EXHAUSTIVE are not implementation verification.

`arch134-armed-paper-mvp` registers the relevant focused tests and critical
source/AST pins, with no ops.ps1 protected preflight/execute. The first push is
already admitted by the integration workflow's feature/robinhood-* family;
source CI must reach terminal success on the exact pushed HEAD/TREE. A missing
run is not PASS. Exact ChatGPT review/certification selection remains next.

The default host credential seam explicitly blocks production until a later
current-product native Alpaca binding is reviewed/qualified. The retained
Windows reader imports C1/C3 authority and is not a D1 dependency. Preflight
cannot claim READY while the binding is absent. No protected CLI invocation,
runtime/store provisioning or scheduler installation is ordinary source testing.
The current D2 supervisor end-state is frozen above; manual-session proving
remains required before D2 effects, with credential/runtime/manual-session
acceptance required before any scheduled provider/paper execution. B3Q remains
consumed/no-retry throughout. Real-money placement remains NO-GO.

Optional local source gate after exact review (CI normally owns this):

~~~powershell
Set-Location 'F:\AI\worktrees\ai-trading-bot-production-paper-mvp'
.\ops.ps1 verify arch134-armed-paper-mvp
~~~

Expected evidence: terminal exact-source CI success; focused tests with zero
real effects; both Ruff phases, git diff and authority checks PASS. Stop on
source/identity drift, missing CI, any rejected/ambiguous provider/paper result,
missing credential/runtime qualification, or any request to retry B3Q. Return
only CI/commit identity or a failing source-gate summary for another review turn.

## 134-D1Q-R1 - Rollback-only write readiness and host startup

The old read-compatible-only READY criterion is replaced. Focused tests cover
both readable but non-writable stores, native Windows read-only file attributes
on test-only files, BEGIN IMMEDIATE success followed by first-write SQLITE_READONLY,
journal/write denial, lock contention, failed readback/rollback/independent reopen,
and real native journal creation followed by rollback and independent verification.
Successful probes preserve exact database bytes/schema and zero new semantic rows;
existing nonempty canonical history/reservations are also preserved.

Direct armed_session_host.main() tests retain the fixed composition while
redirecting the namespace to isolated test stores and faking source admission,
clock, credentials and HTTP transport. A failed probe stops before reservation
and either provider factory. A passing startup enters the real controller and
fixed Alpaca provider factory only after durable reservation, then produces
NO_SIGNAL with four fake history requests, zero quote/application calls and zero
fills. Read-only host preflight never executes a write probe.

Qualification tests require WRITE_READY for both stores and keep credential
readiness unchanged. They reject network attempts and assert zero Alpaca HTTP,
Robinhood application/MCP, paper trade, scheduler and broker mutations. Failure
evidence is bounded and sanitized; incomplete credential counts remain unknown.
Current-process write readiness grants no ACL/ownership repair or ARM authority.

Run affected runtime/controller/store and checkpoint-authority tests, then both
focused non-mutating Ruff phases and git diff --check. Ordinary push on the
existing runtime branch selects arch134-production-paper-runtime and its mapped
canonical ROBINHOOD certification. Wait for terminal CI and exact-source review;
do not duplicate ROBINHOOD locally. No real qualification, production SQLite
probe, credential access, session ARM or production ACL change is source testing.
The next protected dependency is a separate operator provisioning design for
the intended runtime principal's database and native journal write rights.

Implementation verification passed 180 cases across runtime, host/controller
and paper-store modules, followed by 196 cases across the finalized runtime
regressions and checkpoint routing/authority checks (overlapping selections).
Both focused Ruff phases and git diff --check passed. Tests used fresh external
arch134d1qr1-focused-* roots with -B and -p no:cacheprovider. Native read-only
file-attribute coverage passed on Windows against test-only databases. Final
canonical profile evidence belongs to the mapped CI run on the pushed source.


## 134-D1Q-R2 - Fixed native runtime-principal ACL source validation

Implementation verification: 722 distinct focused cases passed across overlapping
selections (111 R2 operator, 116 preserved R1 runtime, 488 CI routing/profile,
four shared native-helper and three source-gate core cases). Final operator/R1
run: 227 passed; targeted shared-helper run: four passed; affected CI core/authority
repair: four passed (one overlaps the R2 module). Disposable native inheritance
passed on this Windows host. Focused Ruff check/format across all nine changed
Python files, git diff --check and exact R1/R2 authority checks passed. External
arch134d1qr2-* test roots and JUnit evidence retain no production effects.
The canonical ROBINHOOD result belongs to GitHub CI on the one pushed commit;
no local ROBINHOOD/FULL was run.

R1 source acceptance remains the frozen parent 6bf8753 / ce3feb2, source gate
#502 / 38235080721 SUCCESS, mapped ROBINHOOD 8532 passed/1 skipped. Its rollback
probes and qualification/host security-mutation prohibition are unchanged. The
earlier pending operator-design step is now the R2 source checkpoint, with
production effects still separately protected.

Ordinary source tests redirect native work entirely to mocks or disposable test
directories/files. They cover exact masks/flags, administrator/current-token SID
binding, wrong expected SID/no elevation before target opens, exact diagnosed
logon-session class, arbitrary/extra/inherited/deny ACEs, wrong owner/path/reparse/
volume/type/link, mixed state, sidecars, before-state drift, all targets pinned,
paper/session/root mutation order, same-handle verification, fresh reopen and
identity drift, terminal apply/close ambiguity without retry/rollback, exact-state
idempotency, fresh/redirection-safe evidence, no parent/recursive or non-ACL
effects, and bounded sanitized publication. Structural mutation tests refresh
blob pins then prove token/elevation/path/mask/authority expansion still fails.
Isolated import tests prohibit WinDLL access and prove the exact tracked closure.

Disposable native Windows coverage creates only a test-owned directory, journal
file and protected test database. It verifies OBJECT_INHERIT + INHERIT_ONLY becomes
an effective inherited file ACE with DELETE, and a protected database descriptor
does not inherit that authority. Test parent ownership/delete rights are only for
cleanup, not the production target policy. No F:\AITradingBot access is attempted.
This source coverage does not establish actual elevated same-account operation,
the deliberately inaccessible-parent final-path behavior, actual before-state
admission or runtime SQLite readiness; those remain real Windows acceptance.

Run focused tests and both focused non-mutating Ruff phases, git diff --check
and exact checkpoint authority validation. Refresh the reviewed shared-helper
133-H AST pin only for the narrow fixed opener/identity/checked-close/0x09 builder
generalization; retain all R1 executable pins and forbidden-effect checks.
Current topology assertions become ACTIVE 63, FULL 169, ROBINHOOD 94, LEGACY 205,
EXHAUSTIVE 374; no baseline module is removed or reclassified. One normal
exact-file commit/push selects the dedicated source gate and canonical robinhood
CI. Ordinary CI never invokes the protected ACL operator; full-tests is skipped
on this mapped path and no duplicate local ROBINHOOD/FULL is run.

After terminal mapped CI and ChatGPT exact GitHub review/source acceptance,
the next read-only observation uses the new branch worktree and reviewed CLI:

~~~powershell
Set-Location 'F:\AI\worktrees\ai-trading-bot-production-paper-runtime-acl'
python -B .\scripts\provision_production_paper_runtime_acl.py `
  --expected-head (git rev-parse HEAD) `
  --expected-tree (git rev-parse 'HEAD^{tree}') --diagnose
~~~

Expected evidence is NEEDS_PROVISIONING/PASS or ALREADY_PROVISIONED/PASS,
zero apply attempts, sanitized SID digest and zero other effects. BLOCKED is a
STOP requiring read-only reconciliation, not permission to repair. Do not run
protected execute as ordinary verification: it requires fresh explicit approval,
already-elevated administrator authorization, expected runtime SID obtained under
the ordinary runtime account, exact equality to the elevated caller's token SID,
and a fresh external evidence file. Elevation under another account blocks.
Return only sanitized diagnostic output for that authorization/review boundary.

After protected acceptance require PROVISIONED/PASS with exactly three verified
applies, or ALREADY_PROVISIONED/PASS with zero applies, independently verified
fixed identities/policies, no parent/non-ACL effects. STOPPED_AFTER_APPLY,
incomplete evidence or partial state means preserve all objects and STOP; never
rerun or roll back automatically. Then separately authorize non-elevated D1Q-R1
qualification from the unchanged accepted runtime branch/worktree; both stores
must show WRITE_READY before a separately authorized manual session. This R2
checkpoint never qualifies, ARMs, schedules, deploys, accesses credentials or
providers, changes paper/session rows or places broker orders. Real-money NO-GO.


### R2 CI #503 failure and bounded local topology correction

The pushed f4961160e3e4f47c3bc44b79d76b914975505343 /
290af91db25997ca52aaf61350e21ba514e7fa1b source passed source-static and active
tests. Canonical ROBINHOOD produced 8631 passed, 1 skipped, 12 failed, 0 errors
across 94 modules in 264.718 seconds. All twelve failures were stale
active-count/tail/registry assertions; the ACL operator cases passed. This is
failed certification, not source acceptance. Evidence was retrieved directly
from CI into external arch134d1qr2-ci503-failure storage.

The local correction updates the twelve failing cases and two related strategy
inventory cases, count/branch/order expectations and changed test source pins.
R2 source-gate coverage now includes COMMON_TESTS and the two strategy inventory
modules so the ordinary active gate covers those dependencies. Those fourteen
cases passed; final R1/R2 authority checks passed after refreshing the final
test-core pin. Cumulative focused verification covers 736 distinct cases across
overlapping runs. Focused Ruff check/format and git diff --check passed. Native
operator and accepted R1 executable code are unchanged. Only the affected tests
were rerun; no local broad profile was run.

The original one normal commit/push was consumed. The user then explicitly
authorized one additional normal exact-file correction commit/push, never
amend/rebase/force-push/merge. Wait for fresh mapped canonical ROBINHOOD CI and
exact GitHub source review on the corrected source. Do not invoke production diagnosis/provisioning,
qualification or ARM while certification remains failed/pending. Return only the
correction commit/CI identity or a failing source-gate summary for review.
