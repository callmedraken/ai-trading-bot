# AI Trading Bot — Current Handoff

## Current correction — completed-close composition; source review pending

The history-only design was abandoned after four consumed P6 preflights. The
replacement starts at HEAD `bbffca862719c61c445952403877b543a80f3111`, tree
`a267b8295d965b8d7d22a9072e27afde46eed45e`. P6 intentionally composes the exact
60 selected completed XNYS sessions from 59 historical daily closes and one typed
Robinhood official close for the final session. No synthetic OHLC bar is created.
The existing baseline quote read supplies that official close: one quote call
and one historical call remain the ceilings. Missing, stale, interpolated or
mismatched official-close data blocks; no quote-price substitution or retry exists.
The plan binds `ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1` and the new signal basis.

All four consumed attempts and diagnostics remain untouched. Source work and
synthetic tests perform no real OAuth/provider/preflight/order/live operation.
After independent exact-source acceptance, exact fast-forward integration and
terminal develop certification reuse, the next protected boundary is one fresh
guarded read-only preflight of this new architecture. A failure to obtain the
exact official close stops this path; a dedicated strategy market-data source
would then require a new design. Live placement remains unauthorized.

## Current boundary - P6 kill-operator accepted/integrated

Accepted P5B baseline source:

    HEAD 7ff86d06a99bcdf349d5e20846d139a554d8be46
    TREE 095c51cedc1c656616123c3acf88148b16b71aa2

P5B protected evidence is PASS and read-only: the live Agentic account
resolver, SPY quote, portfolio, position and order schemas worked; position
and order baselines were zero; mutation/review/place/cancel counts were zero;
and production state stayed unchanged. The external P5B report supplies the
account fingerprint at runtime; it is not present in source or docs.

Implementation worktree:
`F:\AI\worktrees\ai-trading-bot-p6-tiny-live-current`.
Branch: `feature/robinhood-p6-tiny-live-current`.
The accepted placement/cancel source baseline was integrated at:

    HEAD 14c2a20b19381ca9ffb27d67faa873d8cecc283b
    TREE a949f9bad6f1538d2243c489cdddfc02deaf4f1d

Feature CI run `41535508444` and develop CI run `41554499626` succeeded on
attempt 1. Develop reused the exact feature certification. The prior
`c665b8d2ae0bc3df39c8a249388d60605d6fa87c`, terminal-green-but-rejected source
remains preserved historical evidence; the `14c2a20b` correction fixed the
cancel-effect classification blocker. Placement and cancel consumed/no-retry
semantics are accepted. No P6 provider, preflight or live attempt has occurred.

B1 is accepted/integrated. Feature CI `41366532747` and develop integration
CI `41367640239` succeeded. Real adjusted acquisition and the frozen
filtered-trend campaign are complete. Accepted binding:

    FILTERED_TREND_BASE_MA / filtered-trend-base-ma/v1
    SPY / fast=35 / slow=50 / PAPER_EVALUATION / live_eligible=False
    campaign 48ae05d5-ede1-5461-9da9-b5d7744cefad
    bundle 3b86c5e0-6053-53af-a499-d297265f3cd8
    candidate 31397ce5-5dc7-5887-b29a-efc5075c5ebf
    bundle SHA256 80ff955ce2544f0799d8c1fdc1f77f9c337ecf2b25d01731dda1add90ef392f7

B2's first import attempt was a non-consuming STOP. Corrected B2:
IMPORT_SOURCE_AUTHORITY=PASS; OPEN_REPLAY_SMOKE=PASS; first fill BUY 1 SPY at
cursor 51; restart 51 -> 52; fill count 1 -> 1; no duplicate fill; network
attempts 0; FINAL_HOLDOUT accesses 0; final runtime STOPPED. Production P5
SQLite and lifecycle remained absent. Do not repeat the smoke or start a soak.

## Accepted/integrated kill boundary and next step

Registered checkpoint: `arch147-p6-tiny-live`.
Canonical certification: GitHub-owned FULL, broad-1 through broad-7.
Verify/source authority is effect-free; the registered preflight and execute
functions are not run during this implementation checkpoint. The current live
surface is separate from P5B and exposes only explicit reads, review, place and
cancel methods after advertised-schema discovery. It requires dollar orders;
there is no share-quantity fallback, generic public dispatch, option/crypto
surface or GUI placement button.

The P6 policy is SPY-only, accepted FILTERED_TREND_BASE_MA 35/50, long equities
only, maximum $10 per order and $10 gross exposure, one working order, and
regular-hours GFD market orders. Plans are immutable and sanitized; raw account
numbers remain in memory only. Execution is disarmed unless both reviewed
environment interlocks match the exact plan digest. A failed placement is
`MAY_HAVE_OCCURRED` with no retry. The correction retains one attempted place
call through parsing, post-trade reconciliation and lifecycle-write failures;
a marker consumed before placement retains zero place calls and forbids retry.
The first fill disables further buys by default. The published placement
correction is terminal green but rejected for integration by exact-source review;
the cancel-result defect and preserved publication identities are recorded in
validation. The accepted result semantics preserve consumed cancel authority,
truthful per-invocation counts and sanitized uncertainty. A cancel request
acknowledgment is not terminal cancellation; only terminal broker
reconciliation may be reported as terminal.
The accepted/integrated additive kill operator is on the same registered
checkpoint and feature branch, based on integrated startup source:

    IMPLEMENTATION HEAD f1558b97e60bb32fae2a9f1de23226d261418d99
    IMPLEMENTATION TREE ed4a5a962aa6edd98235bf90dffb10e84a935b40
    feature FULL 41575733423 / attempt 1 / SUCCESS
    develop integration 41588005188 / attempt 1 / SUCCESS
    develop certification reuse: exact_feature_certification

The source review accepted the exact durable plan/local/provider ownership
binding, separate kill arm
`AI_TRADING_BOT_P6_KILL_ARM=CANCEL_EXACT_OWNED_P6_ORDER`, and no dependency on
the placement BUY arm. The source-owned CLI admits integrated source before
credential/provider construction, takes an immutable plan path and exact digest,
and never accepts an arbitrary provider order ID. Placement creates and fsyncs
the binding once under the P6 state root. The kill path invokes cancel exactly
zero or one time, and an existing consumed marker permits observation only, never
a second cancel. A cancel acknowledgement is not terminal cancellation; one
bounded reconciliation observation follows. Partial fills survive cancellation
of the remainder, and there is no liquidation or additional BUY authority.
Details and synthetic verification belong in the
[contract](architecture/147-p6-tiny-live.md) and
[validation](validation/arch147-p6-tiny-live.md).

Next step: independent exact-source review of the completed-close correction
following terminal mapped FULL; then exact integration/certification reuse and
one guarded read-only preflight of the new architecture. No placement is
included. Research campaign design proceeds independently without changing the
accepted P6 candidate or accessing FINAL_HOLDOUT.
