# Validation — Architecture 151 intraday walk-forward edge search

Status: **DESIGN ONLY; REAL REPLAY COUNT 0; 2024+ SEALED**.

Normative design:
`../architecture/151-intraday-walk-forward-campaign.md`

## Design effects

This checkpoint performs zero strategy replay, accepted-custody read,
credential/provider call, Robinhood/broker/order effect, paper/live mutation or
2024+ access.

## Source implementation invariants

The next source checkpoint must prove with synthetic tests:

- exactly 16 structural programs / 32 ordered SPY+QQQ slots;
- four programs/family, exactly two 5m and two 15m per family;
- immutable slot/program/fingerprint/symbol/resolution identity;
- no result-dependent candidate-generation surface;
- 5m requires 5 exact source minutes; 15m requires 15;
- missing source minutes remove the aggregate decision point;
- no aggregate bar crosses an XNYS session or published early close;
- confirmations do not bridge missing aggregate bars;
- candidate semantics are identical across all five scored folds;
- fold calibration receives only timestamps before the scored year;
- all five fold records are retained before qualification;
- BASE 2 bps/fill, STRESS 5 bps/fill, ZERO diagnostic only;
- max two round trips/session globally and family B max one;
- >=100 average round trips/year, >=35% active sessions and median <=2
  trades/active session for development qualification;
- every economic/frequency rejection reason is independently tested;
- effective selection-bias trial count is >=64 and incorporates documented prior
  intraday search when larger;
- DSR/equivalent pass threshold is >=0.95;
- final development freeze contains exactly zero or one candidate;
- deterministic final ranking uses the frozen lexicographic order;
- 2024-2025 opening fails closed before a valid final freeze;
- Jan-Oct 2026 opening fails closed before holdout PASS;
- caller-selected IDs cannot substitute for source-owned freezes.

## Workflow

Implementation agents run focused tests with `-p no:cacheprovider` and a fresh
external `--basetemp=F:\AI\temp\pytest\<purpose>-<GUID>`.

Do not run local canonical FULL when mapped GitHub certification owns it.
Prepare one atomic candidate, run admission once, push once and follow mapped CI
to terminal. Preserve any terminal red; never rerun unchanged CI.

After acceptance, review/update PROJECT_STATUS and AI_TRADING_BOT_HANDOFF and
continue automatically into the next safe boundary.

## Immediate implementation target

Source-only Architecture 151 foundation and frozen manifest. No real market
replay and no 2024+ access.
