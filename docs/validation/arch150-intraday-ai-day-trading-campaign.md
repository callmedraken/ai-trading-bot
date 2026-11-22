# Validation — Architecture 150 intraday AI day-trading campaign

Status: **FOUNDATION SOURCE/CERTIFICATION ACCEPTED AND FAST-FORWARD INTEGRATED; REAL DATA NOT YET OPENED**.

Normative design:

`../architecture/150-intraday-ai-day-trading-campaign.md`

## Accepted foundation checkpoint

Integrated HEAD: `df504d166690ed7e6d2b67b5376565926b76baed`

Integrated tree: `9431111706710406baf336a7fd6a16f00a8db36a`

Feature mapped FULL: `44975857710`, attempt 1, terminal SUCCESS.

Develop source-gate: `44981797946`, attempt 1, terminal SUCCESS with exact
feature-certification reuse and no duplicate FULL execution.

Route:

`arch150-intraday-ai-research-foundation`

Branch:

`feature/research-arch150-intraday-ai-current`

Worktree:

`F:\AI\worktrees\ai-trading-bot-arch150-intraday-ai-current`

Source-only/fake-only.

## D1 data-custody source checkpoint

Route:

`arch150-intraday-data-custody-source`

The source route is separate from the accepted strategy-foundation route and
shares its feature branch. CI selects the route from the exact pushed-commit
path set; mixed foundation and D1 changes fall back to broad FULL routing.

The D1 contract fixes one-symbol requests for SPY then QQQ, `1Min`, the
`[2016-01-01, 2024-01-01)` request window, `adjustment=all`, SIP, USD, ascending
sort, `asof=-`, limit 10,000, exhaustive `next_page_token` pagination, 4,096
pages per symbol / 8,192 requests total, and at least 0.5 seconds between
provider request starts after the first. Each response body is stored
byte-for-byte and read back before page parsing. Raw off-session rows remain in
custody; normalized rows require exact published XNYS one-minute slots, with
early closes respected and no fill, interpolation, or duplicate removal.

Versioned schemas:

- `arch150-intraday-custody-dataset/v1`
- `arch150-intraday-data-partition/v1`
- `arch150-intraday-data-custody-evidence/v1`
- `arch150-intraday-raw-page/v1`
- `arch150-intraday-provider-request/v1`

The future interlocked operator writes under
`F:\AI\research-data\arch150-intraday-data-custody`, outside repositories and
worktrees. Its successful state means only that the data custody package is
ready for independent review. It does not open validation for strategy use,
freeze G1, authorize holdout/extension access, or authorize trading. A failed
attempt is immutable and has no automatic retry.

For this source checkpoint, the operator is tested only with injected fake
source facts, credentials, clock, transport, and storage. No credential read,
provider/network request, market-data acquisition, strategy replay, P&L, holdout,
extension, broker, order, or production effect is performed. The D1 mapped FULL
run and exact-source review remain the acceptance gates before any separately
reviewed real acquisition.

## Initial implementation scope

Implement:

- typed intraday program grammar for the three frozen families;
- deterministic ordered G1 proposal manifest frozen before evaluation, with an
  opened-discovery, slot-bound evaluator and immutable terminal trial ledger;
- post-discovery finalization and candidate authorization bound to the complete
  manifest, result ledger, and discovery dataset;
- deterministic session-flat replay interface;
- BASE/STRESS/zero-friction cost contracts;
- frequency diagnostics;
- validation ranking data model;
- selection-bias input schema;
- discovery/validation/holdout/recent-extension information-firewall types;
- source-gate route/profile registration;
- synthetic tests.

Do not open real intraday market data in the foundation checkpoint.

## Data acquisition sequence

After foundation acceptance:

1. acquire and preserve only SPY/QQQ 1-minute discovery+validation data for
   `[2016-01-01, 2024-01-01)`;
2. validate/custody that dataset;
3. freeze the complete G1 population before P&L visibility;
4. run G1 discovery/validation;
5. perform selection-bias correction and freeze final candidate set;
6. only then acquire/open 2024-2025 holdout data;
7. if a candidate survives, only then acquire/open the fixed Jan-Oct 2026
   recent-regime extension.

No waiting for the end of calendar 2026 is required.

## Synthetic source tests

Pin at minimum:

- exact SPY/QQQ universe;
- regular-session-only bars;
- session-flat invariant;
- no overnight carry;
- no pyramiding/martingale/averaging-down;
- at most three median trades per active session for advancing candidates;
- active-session and annual trade-frequency diagnostics;
- at most 24 frozen G1 trial slots / at most 8 per family, including valid and
  explicit invalid proposals;
- nonempty ordered manifest identity is deterministic and preserves duplicate
  proposal slots;
- every official evaluation consumes only the next exact frozen slot;
- invalid, duplicate, zero-trade, deterministic-failure, economic-rejection, and
  shortlist results all consume their frozen trial slot;
- BASE 2-bps/fill and STRESS 5-bps/fill contracts;
- zero-friction cannot qualify;
- complete-trial-ledger DSR/multiple-testing inputs;
- 2016-2020 discovery boundary;
- 2021-2023 validation boundary;
- 2024-2025 holdout firewall;
- Jan-Oct 2026 extension firewall;
- rejected Architecture-148 opening-drive rule excluded;
- Architecture-149 source/evidence untouched;
- zero provider/credential/Robinhood/broker/order/production/FINAL_HOLDOUT
  effects.

Use focused pytest with `-p no:cacheprovider` and unique external basetemp.

Do not run local FULL unless repository admission requires it.

Publication is one atomic commit, one ordinary push, one mapped CI run.

Implementation is performed directly by one Luna Extra High session. No Codex
coordinator and no subagents/polling agents.
