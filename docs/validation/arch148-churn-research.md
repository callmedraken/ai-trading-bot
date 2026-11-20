# Architecture 148 churn research proposal

## Status and authority

This document defines a source-only, descriptive OPEN research proposal for
Architecture 148. It does not report a churn evaluation, validate a strategy,
select a variant, or grant provider, broker, production, or live-trading
authority. The four variants and two existing cost cases are fixed before any
evaluation. Any later OPEN result must be produced as separate, immutable
evidence from the exact committed source and reviewed independently before it
can be described as an observed result. `FINAL_HOLDOUT` remains sealed.

The proposal is on `feature/research-arch148-churn`, based on
`0e82457d71e584dc526b5e377d7f90867e515879` / tree
`7981d889617f1a4bcb41b1e314ea04d14c659e0a`. The checkpoint route is
`arch148-churn-research`; it is source-only, has no preflight or execution
dispatch, and maps to one GitHub-owned FULL certification run. The route does
not run the OPEN evaluation.

## Accepted input and baseline

The proposal uses the already accepted immutable sparse offline requalification
of B2 acquisition `bb1a784b-98d1-41fd-8d95-aa9fa463d5c9`. Its evidence is
`F:\AI\temp\arch148-b2-offline-requalification-b9a8babd-4869-466d-a81f-fae08fe2aae5\evidence.json`,
SHA-256
`bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d`. It binds
dataset `0308b694-c718-5b1a-a51c-9fcc4516bb81`, SHA-256
`0ba8b2437ef27a98fc48855aa8bb8d27ca3cdc0f2888e214305dde760686dbe0`, and
custody `dbcced6a-b4cc-5d36-a33b-5e6df3d82baa`, SHA-256
`93db9a9163cf445fdfd61abe68559196d240b09c1c9b70cdc0f7f452e3e8708b`. The
original dense B1 qualification remains unchanged and failed; neither that
failure nor this sparse proposal authorizes another provider acquisition.

The accepted OPEN sparse baseline record is
`F:\AI\temp\arch148-open-sparse-baseline-e3e27c29-8a9d-41c5-9ac0-d89a1d4cb5d1\baseline.json`,
SHA-256 `38cbba9beae664c675670af1ad96e86a56df2a9060c6cb924c1ad51ea4f9b85f`.
Its recorded comparison is 6,233 `ZERO_COST` trades and 6,235
`CONSERVATIVE_10_BPS` trades, with 5,446 and 5,439 regime exits respectively;
the conservative return is `-99.998648%`. The existing economics are rejected.
These are baseline facts only, not churn-variant results or live-readiness
evidence. Preserve the baseline, B2 acquisition, and requalification artifacts
without overwrite or reinterpretation.

## Fixed research design

The only instruments are QQQ for direction and TQQQ/SQQQ for the long exposure
alternation already defined by Architecture 148. The source reuses the accepted
sparse dataset for `[2016-01-01, 2024-01-01)` UTC, using the accepted
`adjustment=all`, SIP, USD and
`ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1` contract, and the accepted simulator.
The eight disjoint reporting slices are calendar years 2016 through 2023. The
study does not change bar qualification, signal indicators, entry eligibility,
the 3.00% fill-based hard stop, regular-session boundaries, forced-flat policy,
or cost calculation.

Four variants are fixed:

| Variant | Frozen behavior |
|---|---|
| `CONTROL` | Run the accepted current sparse baseline behavior without churn-policy changes. |
| `OPPOSITE_CONFIRMATION_EXIT` | A normal regime exit requires two consecutive completed bars confirming the opposite directional regime. `NEUTRAL` does not trigger a normal regime exit. |
| `OPPOSITE_EXIT_COOLDOWN_15M` | Use the same confirmed opposite-regime exit, then deny either ETF's new entry until 15 elapsed regular-session minutes have passed after the actual normal exit fill. Release is inclusive at the threshold. |
| `OPPOSITE_EXIT_COOLDOWN_30M` | Same as the 15-minute variant, with a 30 elapsed regular-session-minute threshold and inclusive release. |

Cooldown blocks new entries of either ETF after a normal exit; it cannot delay
a hard stop, safety exit, forced-flat action, or other mandatory exit. Its clock
counts only elapsed regular-session minutes from the actual normal exit fill.
Any remaining
cooldown is cleared at the next regular-session open; it never carries across
sessions. Exit classification and fill time come from the simulator's actual
trade record, not the signal bar timestamp.

Every variant runs under exactly two cost cases: the existing
`ZERO_COST` reference and the existing `CONSERVATIVE_10_BPS` case. No optional
stress case, extra threshold, post-hoc variant, or cost change is included.

Evaluation partitions are the disjoint calendar-year OPEN slices of the
accepted dataset. Year boundaries are reporting partitions within one
continuous replay and compounding path. The run begins flat with $10,000 at the
first OPEN year. Each subsequent year begins flat with equity equal to the
preceding calendar year's ending flat equity. No year is designated as
out-of-sample, no final holdout is used, and year-to-year results do not select
or promote a winner.
Results must show every year separately as well as the combined OPEN summary,
and preserve the dataset's missing-slot behavior.

## Required diagnostics for every variant, cost case, and partition

The eventual evidence report must include, without dropping empty or losing
partitions:

- gross strategy return, net strategy return under the selected cost case, and
  QQQ buy-and-hold return;
- maximum drawdown;
- completed trade count and mean trades per expected XNYS regular session,
  including sessions with no trades;
- stop, forced-flat, regime, safety, and reversal counts, with a complete exit
  reason distribution;
- turnover, win rate, average win and average loss, and average and median
  holding duration;
- session entry-count buckets for 0, 1, 2, and 3-or-more entries;
- same-direction same-session re-entry count and mutually exclusive lag buckets
  `5-<10`, `10-<15`, `15-<30`, `30-<60`, and `60+` minutes; and
- per-year results plus deterministic trade-audit and equity-series hashes.

The output must identify the exact source commit/tree, input dataset and
custody identities, simulator and policy versions, cost case, partition, and
hashes. All four variants and both cost cases are reported with the same
diagnostic schema. No result threshold or automatic winner rule is defined.
Re-entry lag is measured between consecutive trades in the same session when
both trades hold the same ETF, from the first exit fill to the next entry fill.
The simulator's five-minute entry cadence makes a same-session re-entry lag
below five minutes unavailable.

## Public-reference decisions

The canonical Architecture 148 source/runtime/public-reference adoption matrix
is [`arch148-runtime-parity.md`](arch148-runtime-parity.md). It records the
exact pins, licenses, reviewed functions, local owners/tests, and adopted or
declined behavior. For this proposal, Lean's fill and missing-bar sources
inform explicit simulator semantics; Freqtrade's cooldown lock is a design
reference for the distinct regime-only, cross-ETF, session-local rule; and
Hummingbot does not motivate any offline or live-order behavior change. No
upstream implementation is copied or imported. Existing broker, MCP, approval,
provider-scope, and protective-stop limits continue to apply.

## Source and test ownership

The policy and simulator changes are source-owned by the Architecture 148
research modules. The checkpoint route covers `arch148_intraday.py`,
`arch148_sparse_backtest.py`, `arch148_churn_policy.py`, and
`arch148_churn_research.py`, with focused coverage in
`test_arch148_intraday.py`, `test_arch148_sparse_backtest.py`,
`test_arch148_churn_policy.py`, and `test_arch148_churn_research.py`. The route
is mapped to FULL through the current registry and source-gates workflow; it
does not grant execution authority or automatically run this study.

The next research step is to commit the exact source locally and pass the
general source admission, then run the separately authorized OPEN comparison
before publication. It must write fresh external evidence for independent
review; the mapped GitHub CI result is not a prerequisite to that offline run.
This source proposal itself does not run the evaluation. Preserve all baseline
and requalification evidence, keep `FINAL_HOLDOUT` sealed, and stop if the
input identity, accepted simulator semantics, or required diagnostics do not
match this contract.
