# Architecture 134 — Production strategy and AI-research validation plan

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
