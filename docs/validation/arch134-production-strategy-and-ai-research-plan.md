# Architecture 134 — Production strategy and AI-research validation plan

## 2026-10-11 — Architecture 134-A SOURCE ACCEPTED

Architecture **134-A — Production Strategy Contract** is source accepted.

~~~text
BRANCH  feature/robinhood-production-strategy-contract
HEAD    d49f6e718b27207acad39ad323c76db196b6d7a9
TREE    239513ff3063610b675213a124208edb933846ac
COMMITS
4831aaaa53769e01cec4d9a8a1a25dec7bd221f7  feat: add production strategy contract
d49f6e718b27207acad39ad323c76db196b6d7a9  test: satisfy production strategy source gate
CI      #459 / 38125675113 SUCCESS
~~~

Exact GitHub review confirmed the implementation is the frozen inert boundary:

- canonical `production-strategy-contract/v1`;
- one explicit target date, one exact `Symbol`, exact reviewed source HEAD/TREE;
- `MovingAverageCrossoverStrategy` / `1.0.0` with the existing validated config;
- deterministic UUID5 semantic identity and strict canonical JSON replay;
- construction of the existing pure strategy only; no evaluation;
- no provider/MCP/OAuth, market-data, paper-store, risk, scheduler, clock,
  filesystem, research/AI, optimization, dynamic import or execution authority;
- checkpoint `arch134-production-strategy-contract` has `preflight=None` and
  `execute=None` and one exact active branch route.

Source gate #459 on the exact accepted head passed:

~~~text
source-static  SUCCESS
  git diff --check  PASS
  Ruff check        PASS
  Ruff format       PASS
  authority         PASS
  identity stable   True

active-tests   SUCCESS
  pytest            PASS
  identity stable   True

full-tests     SKIPPED
source-gates   SUCCESS
~~~

Current exact inventories are active **58**, FULL **159**, ROBINHOOD **85**,
LEGACY **205**, EXHAUSTIVE **364**. No broad certification is selected at this
pure-model checkpoint.

A separate source-gate failure #460 on
`feature/robinhood-production-strategy-decision` used this same HEAD before
134-B had any registered route. It is not a 134-A failure and grants no 134-B
acceptance.

Next milestone is **134-B — Production Strategy Decision Bridge**: provider-free
composition of the accepted production contract with verified daily strategy
history/current bar and authoritative paper-account state, evaluating the
selected strategy exactly once and returning a closed `NO_SIGNAL` or exact
`TradeProposal`. 134-B still has no provider call, paper mutation, scheduler,
arming, risk execution or broker effect.

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
