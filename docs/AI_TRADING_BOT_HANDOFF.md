# AI Trading Bot - Current Handoff

## L40 source checkpoint awaiting independent acceptance

Canonical worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`;
branch: `feature/robinhood-live-prototype-current`. Verified implementation base
HEAD `f7f13f805ad6a0eea7041cb6d13c561149a13f6e`, tree
`4cf5d8fd19a8089103e9f119e4d8d338a08819d0`; live feature/develop matched that
closeout before edits. Develop gate `41987821711`, attempt 1, was SUCCESS.
The L40 publication identity is resolved from Git and the source-gate evidence;
this document does not self-certify its containing commit or acceptance.

L40 adds the pure `live_prototype/live_contract.py` owner and focused tests.
The [L40 contract](architecture/147-restricted-live-contract.md) owns mechanical
exit/budget/ownership/no-retry semantics and remaining L41 facts. The source-only
`arch147-live-prototype` registration remains mapped to GitHub-owned FULL;
preflight/execute remain absent. No local FULL or manual dispatch is required.
P6 effect code, consumed evidence, D34 observation and synthetic launcher are
unchanged. The new snapshot/reservation contract is not a durable live runtime.

Next: ChatGPT independently reviews the exact published L40 diff and terminal
CI, accepts/rejects it and assesses integration. After accepted integration,
freeze the L41 read-only observation/collector for actual eligibility and
minimum/residual facts; do not invoke a provider from this handoff. The collector
was deferred because current metadata does not expose all required capability
facts and a truthful sell review may require the first exact-owned position.
Effect-free unpublished L42 analysis can continue; L42 finalization waits for
accepted L41 facts. Q61/Q62/L43/Q63 remain unrun; no readiness label is granted.
D33 and D34 must never be replayed; FINAL_HOLDOUT remains sealed.

## D34 accepted/integrated closeout identity

Worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`

Branch: `feature/robinhood-live-prototype-current`

Integrated source HEAD: `b86defebf9ccbf1efb91397de8f2e66db24a6665`

Integrated source tree: `9fa2360dfe7afdd902fd539e94f888063439785d`

Feature mapped FULL `41969407894`, attempt 1, and develop source-gate
`41973853073`, attempt 1, both succeeded; develop reused the exact feature
certification. That is the accepted D34 implementation identity; the later
canonical closeout and current L40 base are recorded above. The accepted/integrated
D33 source remains the D34 lineage ancestor
`fad65c9f4eab5bc1de4e154fdf0f59e397bc943a` / tree
`beab205abcc045fad38625ff73bb48affea9a0e9`. The first D34 publication
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` is its direct child, and accepted
D34 corrective source `b86defebf9ccbf1efb91397de8f2e66db24a6665` is the direct
child of `9981bf47072d35381a2e5b6f187c9497e9dbed5a`. D33 is a consumed
predecessor incident, not an available observation boundary.

The preserved D34 predecessor is
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` / tree
`a8d2b4fb4a40039b74768b44fd0198dc87bc55f3`. Its mapped run `41950572892`,
attempt 1, was terminal SUCCESS, but exact-source review rejected it before
develop integration because blocked-result attempt counts were not bound to
their failure phase and the operator fallback could write false `0/0`
credential/provider counts after an escaped failure. No D34 real observation
occurred; the candidate remains immutable evidence.

D30 is ACCEPTED with dataset ID
`d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, dataset SHA
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, and
`ALPACA_ALL_ADJUSTED_PRICE_V1`. D31's exact bundle is ACCEPTED with campaign
`9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, bundle SHA
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, result
`NONE_QUALIFIES`, and retained control `BASE_MA35_50_V1` / candidate
`21158358-75be-5597-b940-5bccdda1429c`. D32 is ACCEPTED / CLOSED: strategy
math parity, research-binding integrity, and live data-basis parity passed;
the 2,516 comparisons had zero mismatches. The former
`DATA_BASIS_MISMATCH` blocker is closed.

## Consumed D33 incident

D33's one real read-only attempt is CONSUMED / BLOCKED / NO RETRY. Preserved
evidence:
`F:\\AI\\temp\\arch147-d33-alpaca-observation-576b4b5c8f7b41548df7b822c44c74de\\evidence.json`;
SHA-256 `b767727712e4634950be8a6ba8f43522910d037987824ad33cb7c20c8eab95ec`,
1,999 bytes; observation `2026-11-04T23:59:08.218729Z`; credentials `1`;
provider requests `1`; selected sessions `60`; production, broker,
runtime-binding, campaign, and FINAL_HOLDOUT mutation counts are all `0`.
The exact provider rejection subtype is unavailable because D33 discarded it.
The request end exceeded observation through end-of-calendar-day semantics;
this is a source-contract defect, not proof of the provider's exact rejection
cause. D33's exact request target is preserved in the validation ledger.

## Accepted D34 observation and stop conditions

The corrective D34 child changes only attempt-accounting/evidence truthfulness
and focused tests/docs. The additive D34 source derives one exact published
regular close after selecting the 60 completed XNYS sessions and before
credential/provider construction. That same cutoff is used for the request and
`CompletedSignalInputs`; it never uses next midnight, end-of-calendar-day,
observation-as-substitute, silent subtraction, provider fallback, or a changed
session set. D34's separately named entry point is
`trading_bot.live_prototype.alpaca_signal_recovery_operator`, with evidence
schema `arch147-d34-alpaca-signal-observation/v1`. The old D33 CLI is retired
before credentials/provider access; `--help` remains effect-free.

D34 source admission and the mapped feature FULL completed before the
separately labeled read-only observation. The accepted evidence is
`F:\\AI\\temp\\arch147-d34-alpaca-observation-84d32fb2af5045e7a661a77259b690fb\\evidence.json`,
2800 bytes, SHA-256
`7c6f2d391cbb3141405e3252efcfcd94db18b8e81083d947d778310bfe49464b`.
Schema: `arch147-d34-alpaca-signal-observation/v1`; status READY; reason
`D34_ALPACA_SIGNAL_INPUTS_READY`; observation timestamp
`2026-11-05T05:28:41.664723Z`.

The observation consumed exactly one credential read and one provider call, with
automatic retry FORBIDDEN. The exact one-request target is
`GET /v2/stocks/bars?symbols=SPY&timeframe=1Day&start=2026-08-12T04%3A00%3A00.000000Z&end=2026-11-04T21%3A00%3A00.000000Z&limit=60&adjustment=all&asof=-&feed=sip&currency=USD&sort=asc`.
It selected 60 sessions from 2026-08-12 through 2026-11-04. Response-body
bytes were 6702 with SHA-256
`296c9e89dd2f48d47b1ca3b071411d6e8509ca769fc92e433be19696bbf68c94`;
provider request-ID digest was
`6384000426f7d007ed9391b81bef6beb2ba40a5193cf94dd30a2a58fb63ae15f`; and
the `CompletedSignalInputs` digest was
`8b6d4f88012da820890cb5070de975c1d02504aeb432939a2e954d9bf9dfecb0`.
No raw request ID or credential material is retained.

The D34 attempt is CONSUMED SUCCESSFULLY / NO RETRY. Production, broker,
runtime-binding, campaign, order, paper, live, and `FINAL_HOLDOUT` effects are
all zero. The observed BASE_MA35_50_V1 BUY/HOLD outputs are signal outputs only;
they do not authorize an order or grant live eligibility.

The current L40 source boundary and remaining L41-L43 dependencies are recorded
above and in the L40 contract. Q61 remains NOT RUN; no readiness label or paper
soak is inserted. FINAL_HOLDOUT remains sealed.

The old P6 preflight is historical predecessor context, not the current next
operator action and not the D33/D34 signal-data path. It grants no retry.
