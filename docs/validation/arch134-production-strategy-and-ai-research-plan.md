# Architecture 134 — Production strategy and AI-research validation plan

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
