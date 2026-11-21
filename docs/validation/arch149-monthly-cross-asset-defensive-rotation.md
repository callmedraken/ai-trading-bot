# Validation — Architecture 149 monthly cross-asset defensive rotation

Status: **DESIGN FROZEN; SOURCE NOT IMPLEMENTED**.

This plan validates the exact one-candidate Architecture-149 contract in
`../architecture/149-monthly-cross-asset-defensive-rotation.md`.

## Source route

Planned checkpoint:

`arch149-monthly-defensive-rotation-research`

Planned branch:

`feature/research-arch149-monthly-defensive-rotation-current`

Planned worktree:

`F:\AI\worktrees\ai-trading-bot-arch149-monthly-defensive-rotation-current`

Create the route/worktree only during the source checkpoint.

## Source-only requirements

Synthetic tests must prove:

- exact fixed eight-symbol universe/order;
- 21/252 qualified-session lookback;
- most recent 21 sessions excluded;
- all-eight-symbol completeness required;
- deterministic universe-order tie break;
- positive top score selects exactly one ETF;
- nonpositive top score selects CASH;
- month-end-only signal creation;
- next-session-open execution;
- no same-month extra trade;
- unchanged target produces no fill;
- sell-before-buy ETF switch;
- whole-share 95% allocation;
- exact BASE and STRESS economics;
- one continuous $100,000 path;
- 2016 warmup exclusion;
- 2017-2023 reporting only;
- no post-2023 input accepted;
- frozen exploratory classification boundaries;
- deterministic target/trade/equity identities;
- import/construction/help effect-free;
- zero credential/provider/Robinhood/broker/order/production/FINAL_HOLDOUT
  effects.

Use focused tests with `-p no:cacheprovider` and a fresh external
`--basetemp=F:\AI\temp\pytest\<purpose>-<GUID>`.

Run focused Ruff check/format check and `git diff --check`.

Do not run local canonical FULL or ROBINHOOD.

## Publication

One atomic source commit, exact-file staging, current prepublication admission,
one ordinary push and one mapped GitHub certification.

Required admission:

- FEATURE=PASS
- PROSPECTIVE_DEVELOP=PASS
- IDENTITY_STABLE=True
- OVERALL=PASS

Do not merge. Integration remains ChatGPT authority.

## Real exploratory replay

Real 2017-2023 evaluation is not part of the source checkpoint.

After exact-source acceptance, one separately reviewed operator may open only
the accepted A147 2016-2023 dataset and replay the single fixed candidate once.

No 2024+ data may be opened.

If the candidate is rejected, close Architecture 149 without variants.

If it is `EXPLORATORY_CANDIDATE_ONLY`, freeze the 2024-2026 confirmation
contract before any new acquisition or result.
