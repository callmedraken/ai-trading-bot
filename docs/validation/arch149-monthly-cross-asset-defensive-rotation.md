# Validation — Architecture 149 monthly cross-asset defensive rotation

Status: **Design frozen; source accepted/integrated; real exploratory replay NOT RUN.**

Accepted source:
- HEAD `57087af056767c59ee48e3edb86063ac4f20c10d`;
- tree `da80c3f560d54d959822f7716a50fc45c3ead716`;
- feature certification `44914956812`, attempt 1, SUCCESS;
- develop reuse `44935678418`, attempt 1, SUCCESS;
- duplicate develop FULL: NO.

The route remains source-only. Real A147 data has not been opened through this
candidate and no real Architecture-149 artifact exists yet.

This plan validates the exact one-candidate Architecture-149 contract in
`../architecture/149-monthly-cross-asset-defensive-rotation.md`.

## Source route

Registered source-only checkpoint:

`arch149-monthly-defensive-rotation-research`

Registered branch:

`feature/research-arch149-monthly-defensive-rotation-current`

Source worktree:

`F:\AI\worktrees\ai-trading-bot-arch149-monthly-defensive-rotation-current`

The current route is mapped to the `full` certification profile and accepts the
exact `feature/research-arch149-monthly-defensive-rotation-current` branch on
push. It has no preflight, execute, or remote-head environment dispatch. This
registration grants source verification only.

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

## Reporting conventions

Tests and source reports must follow the metric timing and formulas in the
architecture's `Reporting semantics` section. In particular, missing-input
no-rebalance remains distinct from a valid signal decision that targets CASH.

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
