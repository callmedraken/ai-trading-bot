# AI Trading Bot - Project Status

## Current milestone - Architecture 147 D34 consumed-D33 recovery

Accepted/integrated D33 source:
`fad65c9f4eab5bc1de4e154fdf0f59e397bc943a` / tree
`beab205abcc045fad38625ff73bb48affea9a0e9`. Feature FULL
`41924058186`, attempt 1, and develop source-gate `41936617801`, attempt 1,
succeeded; develop reused exact feature certification.

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
with 2,516 comparisons and zero mismatches; live data-basis parity remains
blocked by `DATA_BASIS_MISMATCH`. Alpaca all-adjusted signal data and Robinhood
broker/account/execution/custody remain separate providers with no fallback.

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

## Immediate next step

The D34 corrective child is source-only and changes only attempt-accounting and
evidence truthfulness plus focused tests/docs. The preserved implementation
still derives the exact published regular close once before credential/provider
construction and uses
that same cutoff in the request and `CompletedSignalInputs`. Its separate entry
point is `trading_bot.live_prototype.alpaca_signal_recovery_operator`; the D33
CLI is retired before credential/provider access. D34 evidence uses
`arch147-d34-alpaca-signal-observation/v1` and digest-only/closed diagnostics.

Complete exact-source review, then publish one corrective child commit and one
mapped `arch147-live-prototype` FULL route. Do not invoke D33 or D34 during
source implementation. After acceptance, integrate exact source with
certification reuse before any separately reviewed D34 successor observation.
That future attempt is one Alpaca request only, never Robinhood, with no order
or other protected effect.

Q61 remains NOT RUN. No live-readiness label is granted. L40-L43 remain
pending behind this recovery: official fractional exit capability, exact
owned-position exit semantics, and durable budget/recovery/capability work are
still required. No paper-soak milestone is inserted. FINAL_HOLDOUT remains
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
