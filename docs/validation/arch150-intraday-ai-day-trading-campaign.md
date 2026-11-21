# Validation — Architecture 150 intraday AI day-trading campaign

Status: **DESIGN FROZEN; SOURCE NOT IMPLEMENTED**.

Normative design:

`../architecture/150-intraday-ai-day-trading-campaign.md`

## First source checkpoint

Planned route:

`arch150-intraday-ai-research-foundation`

Planned branch:

`feature/research-arch150-intraday-ai-current`

Planned worktree:

`F:\AI\worktrees\ai-trading-bot-arch150-intraday-ai-current`

Source-only/fake-only.

## Initial implementation scope

Implement:

- typed intraday program grammar for the three frozen families;
- trial ledger and trial-budget enforcement;
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
- exact 24-trial G1 budget / 8-per-family;
- invalid/duplicate/zero-trade failures consume trials;
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
