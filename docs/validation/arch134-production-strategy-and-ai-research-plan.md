# Architecture 134 — Production strategy and AI-research validation plan

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

After exact GitHub source acceptance, the first real 134-C qualification is a
separately authorized human-started **shadow PREPARE**. A paper EXECUTE is a
second separately authorized step and is permitted only if the retained PREPARE
remains `READY_TO_PROCEED` and all Architecture-131 revalidation passes.

## 134-B validation contract

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
