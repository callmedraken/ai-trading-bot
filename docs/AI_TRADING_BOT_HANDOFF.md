# AI Trading Bot — Current Handoff

## Current boundary — P6 source accepted/integrated, no P6 provider attempt

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
P6 source is accepted and integrated with feature and develop identical at:

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

## Next milestone — P6 kill-operator boundary before first live execution

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
`P6_KILL_OPERATOR_REACHABILITY=NOT_IMPLEMENTED`: no reviewed operator caller of
`kill_owned_order` exists. Implementing that caller requires a separate reviewed
milestone before first live execution. See
[contract](architecture/147-p6-tiny-live.md) and
[validation](validation/arch147-p6-tiny-live.md).

The next milestone is a separately reviewed operator-reachable exact-owned-order
kill/cancel boundary before first live execution. P6 preflight must not run
until that milestone is accepted, integrated and closed out. A source PASS
grants no live authority.
