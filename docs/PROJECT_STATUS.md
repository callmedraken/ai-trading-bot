# AI Trading Bot - Project Status

## Current milestone - Architecture 147 D33

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

D32 is PARTIAL_PASS: strategy math parity and research-binding integrity passed
with 2,516 comparisons and zero mismatches; live data-basis parity was blocked
by `DATA_BASIS_MISMATCH`. D33 is the additive current-signal-data successor:
Alpaca Market Data supplies completed daily SPY inputs using
`ALPACA_ALL_ADJUSTED_PRICE_V1`, while Robinhood MCP remains the broker,
account, execution, and custody provider. There is no provider fallback.

The D33 source checkpoint performs no provider observation, credential read,
campaign, paper, broker, production, runtime-binding, FINAL_HOLDOUT, or live
effect. The older P6 `ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1` 59+1 source
and all consumed evidence remain preserved predecessor behavior; it is not
relabeled as Alpaca-based and is not rewritten by D33.

## Immediate next step

Complete exact-source review of the D33 candidate, then publish exactly one
atomic feature commit and one mapped `arch147-live-prototype` FULL route. If
that terminal CI result is green and the source is accepted, fast-forward
`develop` with certification reuse and perform one fresh, source-admitted,
read-only D33 observation. That observation will make one Alpaca request only,
will never call Robinhood, and will not authorize an order.

Q61 remains NOT RUN. No live-readiness label is granted. L40-L43 remain
unresolved: official fractional exit capability, exact owned-position exit
semantics, and durable budget/recovery/capability work are still required.
There is no paper-soak milestone between D33 and L40-L43. FINAL_HOLDOUT remains
sealed.

## Product and protected boundaries

The product remains a private single-user Windows desktop application with
explicit Start/Stop and manual stopped-state updates. Credentials and durable
state remain outside disposable source files. Live trading is disabled; no real
order is authorized. Readiness labels are not granted by source publication,
source admission, or provider-data parity alone.

Historical P6, P5A/P5B, and earlier architecture evidence remains available in
its owning documents. The current handoff and D33 validation ledger record the
bounded continuation identity and acceptance state.
