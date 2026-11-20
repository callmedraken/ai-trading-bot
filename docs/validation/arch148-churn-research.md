# Architecture 148 churn research — accepted OPEN result

## Status and authority

This document records the accepted source-only descriptive OPEN churn study for
Architecture 148. It does not validate a live strategy, select a variant, or
grant provider, broker, production, or live-trading authority. The four
variants and two cost cases were frozen before evaluation; the accepted result
selects none and leaves `FINAL_HOLDOUT` sealed.

Source/certification/evidence are independently accepted and fast-forward
integrated at `be30617594e197f372438dba19d325fd8737b850` / tree
`57d5e80bd1933d59faf5da07f0ea293eac34b323`, parent
`0e82457d71e584dc526b5e377d7f90867e515879`. Feature mapped FULL run
`44695628477`, attempt 1, and develop run `44698088183`, attempt 1, are
terminal SUCCESS; develop reused the already-certified source and did not
duplicate FULL. Accepted research evidence is
`F:\AI\temp\arch148-churn-research-731f1ee4-53a1-4bdf-8979-5eef493d9f4a\research.json`,
299,259 bytes, identity `19dcca18-7080-541d-9864-d730c68471e0`, SHA-256
`5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8`.
All nine effect counters are zero, including `final_holdout_accesses=0`.

## Accepted input and baseline

The study used the already accepted immutable sparse offline requalification
of B2 acquisition `bb1a784b-98d1-41fd-8d95-aa9fa463d5c9`. Its evidence is
`F:\AI\temp\arch148-b2-offline-requalification-b9a8babd-4869-466d-a81f-fae08fe2aae5\evidence.json`,
SHA-256
`bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d`. It binds
dataset `0308b694-c718-5b1a-a51c-9fcc4516bb81`, SHA-256
`0ba8b2437ef27a98fc48855aa8bb8d27ca3cdc0f2888e214305dde760686dbe0`, and
custody `dbcced6a-b4cc-5d36-a33b-5e6df3d82baa`, SHA-256
`93db9a9163cf445fdfd61abe68559196d240b09c1c9b70cdc0f7f452e3e8708b`. The
original dense B1 qualification remains unchanged and failed; neither that
failure nor this sparse study authorizes another provider acquisition.

The accepted OPEN sparse baseline record is
`F:\AI\temp\arch148-open-sparse-baseline-e3e27c29-8a9d-41c5-9ac0-d89a1d4cb5d1\baseline.json`,
SHA-256 `38cbba9beae664c675670af1ad96e86a56df2a9060c6cb924c1ad51ea4f9b85f`.
Its recorded comparison is 6,233 `ZERO_COST` trades and 6,235
`CONSERVATIVE_10_BPS` trades, with 5,446 and 5,439 regime exits respectively;
the conservative return is `-99.998648%`. CONTROL reproduced these accepted
baseline facts before candidate evaluation.

Observed candidate results show that opposite confirmation reduced
`CONSERVATIVE_10_BPS` trade count from 6,235 to 3,172, with the 15-minute and
30-minute cooldown variants reducing it further to 3,067 and 2,970. That churn
reduction did not rescue economics: full-OPEN conservative returns were
approximately `-99.5971%`, `-99.5245%` and `-99.4027%` respectively, and
every variant lost money in every 2016-2023 calendar-year conservative slice.
The descriptive order was 30-minute cooldown, 15-minute cooldown, opposite
confirmation, CONTROL; it is not a promotion decision. Preserve the baseline,
B2 acquisition, requalification and churn evidence without overwrite or
reinterpretation.

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
declined behavior. For this study, Lean's fill and missing-bar sources
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

The accepted source and evidence satisfy this fixed research contract. No
variant is promoted into live/default strategy behavior. Preserve all baseline,
requalification and churn evidence and keep `FINAL_HOLDOUT` sealed. The next
research boundary is an OPEN-only investigation of a materially different
entry/holding architecture rather than further post-hoc cooldown tuning; any
such checkpoint must freeze its design and diagnostics before replay and must
not inherit promotion authority from this rejected study.
