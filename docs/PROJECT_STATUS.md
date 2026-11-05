# AI Trading Bot - Project Status

## Current milestone - L40 accepted/integrated; remaining prototype implementation next

L40 is ACCEPTED / INTEGRATED at
`14e1b628c0c51c27b23deabee56eb91859818529` / tree
`48b588cbb37818b0d1edfcbb895cfb715a2bf2d3`. Feature mapped FULL
`41995282653`, attempt 1, was SUCCESS. Develop gate `41997418576`, attempt 1,
was SUCCESS and reused the exact feature certification without duplicate FULL.

The accepted [L40 contract](architecture/147-restricted-live-contract.md)
freezes effect-disabled exact ownership, nonresetting <=$10 requested
new-acquisition budget, truthful reducing-exit notional/fill semantics,
partial-fill ownership, residual preservation, identity binding and
UNKNOWN/no-retry behavior. It grants no provider/order authority and does not
authenticate caller-supplied evidence references.

The remaining critical path starts with the L41 read-only Robinhood
fractional-exit capability observer/source boundary, then durable
ownership/budget/controller and runtime Alpaca signal service, real desktop
application composition, native Windows acceptance, fresh readiness/recovery,
and the separately reviewed bounded real live qualification. Q61/Q62/L43/Q63
remain NOT RUN. No live-readiness label or paper-soak milestone is granted and
FINAL_HOLDOUT remains sealed.

Accepted/integrated D34 source:
`b86defebf9ccbf1efb91397de8f2e66db24a6665` / tree
`9fa2360dfe7afdd902fd539e94f888063439785d`. Feature mapped FULL
`41969407894`, attempt 1, and develop source-gate `41973853073`, attempt 1,
succeeded; develop reused the exact feature certification. D34's accepted
source descends from the integrated D33 source
`fad65c9f4eab5bc1de4e154fdf0f59e397bc943a` / tree
`beab205abcc045fad38625ff73bb48affea9a0e9` through the preserved first D34
publication `9981bf47072d35381a2e5b6f187c9497e9dbed5a`.

D30 is ACCEPTED with dataset semantic ID
`d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, dataset SHA-256
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, and
price basis `ALPACA_ALL_ADJUSTED_PRICE_V1`.

D31's exact research bundle is ACCEPTED: campaign
`9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, bundle SHA-256
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, and
selection `NONE_QUALIFIES`. The retained control is `BASE_MA35_50_V1` with
candidate ID `21158358-75be-5597-b940-5bccdda1429c`. NONE_QUALIFIES means that
neither challenger qualified; it is not a winning challenger, promotion,
profitability proof, or live eligibility.

D32 is ACCEPTED / CLOSED: strategy math parity, research-binding integrity, and
live data-basis parity all passed; the 2,516 strategy comparisons had zero
mismatches, and the accepted D34 observation used the same
`ALPACA_ALL_ADJUSTED_PRICE_V1` basis as D30/D31. The former
`DATA_BASIS_MISMATCH` blocker is closed. Alpaca all-adjusted SIP/USD signal data
and Robinhood broker/account/execution/custody remain separate providers with
no fallback.

D33's real read-only attempt is CONSUMED / BLOCKED / NO RETRY. Preserved
evidence: `F:\\AI\\temp\\arch147-d33-alpaca-observation-576b4b5c8f7b41548df7b822c44c74de\\evidence.json`,
SHA-256 `b767727712e4634950be8a6ba8f43522910d037987824ad33cb7c20c8eab95ec`,
1,999 bytes; observation `2026-11-04T23:59:08.218729Z`; credentials `1`;
provider requests `1`; selected sessions `60`; all prohibited-effect counters
are zero. D33 discarded the safe failure subtype, so the exact provider
rejection subtype is unavailable. Its request end exceeded observation through
end-of-calendar-day semantics; that is a source defect, not a proven provider
rejection cause.

The first D34 publication is preserved at
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` / tree
`a8d2b4fb4a40039b74768b44fd0198dc87bc55f3`; mapped run `41950572892`, attempt
1, was terminal SUCCESS, but exact-source review rejected it before develop
integration. The review found incomplete blocked-result attempt-count
invariants and an operator-level escaped-failure fallback that could fabricate
zero credential/provider counts. No D34 real provider observation occurred.

D34 is now ACCEPTED, INTEGRATED, and CONSUMED SUCCESSFULLY. The accepted
read-only observation is recorded at
`F:\\AI\\temp\\arch147-d34-alpaca-observation-84d32fb2af5045e7a661a77259b690fb\\evidence.json`,
2800 bytes, SHA-256
`7c6f2d391cbb3141405e3252efcfcd94db18b8e81083d947d778310bfe49464b`,
observation timestamp `2026-11-05T05:28:41.664723Z`. It consumed exactly one
credential read and one provider call, with no retry. The one SPY daily request
ended at the exact published XNYS regular close
`2026-11-04T21:00:00.000000Z`; response-body SHA-256 is
`296c9e89dd2f48d47b1ca3b071411d6e8509ca769fc92e433be19696bbf68c94`, and the
`CompletedSignalInputs` digest is
`8b6d4f88012da820890cb5070de975c1d02504aeb432939a2e954d9bf9dfecb0`.
Production, broker, runtime-binding, campaign, paper, live, and
`FINAL_HOLDOUT` counters remained zero. The observation validates the signal
input basis only; it does not authorize an order or grant live eligibility.

## Immediate next step

Run one coordinated remaining-prototype source mission under a Sol High
orchestrator. Sol owns decomposition, contracts, review and sequencing only;
Luna Extra High subagents perform all coding and focused tests. The mission
starts with the L41 read-only capability observer, then implements the durable
L42 controller, reusable runtime Alpaca inputs, I53 real application composition
and Q62/Q63 readiness/recovery source support with the fewest meaningful
publication boundaries.

Protected observations and broker mutations remain separately reviewed
boundaries: the orchestration may prepare their source/operators and exact local
commands but must not invoke real credentials/provider/order effects without
ChatGPT acceptance and the required operator boundary. Q61 native UAT, Q62
fresh readiness and L43 bounded live qualification remain factual host evidence,
not synthetic source claims. No paper soak is inserted and FINAL_HOLDOUT remains
sealed.

## Product and protected boundaries

The product remains a private single-user Windows desktop application with
explicit Start/Stop and manual stopped-state updates. Credentials and durable
state remain outside disposable source files. Live trading is disabled; no real
order is authorized. Readiness labels are not granted by source publication,
source admission, or provider-data parity alone.

Historical P6, P5A/P5B, and earlier architecture evidence remains available in
its owning documents. The current handoff and D34 validation ledger record the
bounded continuation identity and acceptance state.
