# AI Trading Bot - Project Status

## Current milestone - Architecture 147 D33 corrective child

P01 implementation, corrections, and docs closeout plus the accepted D33 source
are integrated through
`543dc6b45b4a20f53ae28646a0c82b9b1cd7b824` / tree
`9981cca7cc1f01fae778cbe9e5d189126d3a885c`; feature FULL
`41903739374` and develop integration `41905183980`, attempt 1, both
succeeded. The first D33 source predecessor
`2fd6d764e56226d7ef54c458f6f40b14af3b5b20` / tree
`f44c9e3455b712572f8c6c022883eadb3ebd9c56` passed mapped FULL run
`41822221848`, attempt 1, but was rejected by exact-source review. It remains
immutable terminal-green evidence and was not integrated.

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

Operational review found that the earlier D33 source admission depended on
local remote-tracking refs while preparing a protected observation. Repeated
pre-dispatch stale-tracking, `FETCH_HEAD`, and ref-lock failures consumed no
provider attempt. The corrective child resolves live origin branch heads
read-only through the existing source-owned helper. Local stale Git state is
separate host hygiene, not provider authority; the cause of local write
failures remains unresolved and no ACL/sandbox cause is claimed.

## Immediate next step

The corrective child addresses only protected admission requiring exact
feature/develop identity through live read-only origin resolution, source-owned
current clock, same-day completed-session cutoff semantics, invalid-clock
sanitization, focused tests, and coordination truth. Complete exact-source
review, then publish exactly one child commit and one mapped
`arch147-live-prototype` FULL route. Do not run D33 during implementation.

After acceptance, fast-forward `develop` exactly to the child with
certification reuse, verify identities, and perform one fresh source-admitted
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
