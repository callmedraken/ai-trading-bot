# AI Trading Bot - Current Handoff

## D33 continuation identity

Worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`

Branch: `feature/robinhood-live-prototype-current`

Parent source HEAD: `b7d42863d24958d1ce0fcf9f51eff67397f94240`

Parent source tree: `31f2d5016f27b08c6f475c36b655523cd888726c`

P01 implementation, corrections, and docs closeout are integrated through the
parent `develop` source above. D33 predecessor
`2fd6d764e56226d7ef54c458f6f40b14af3b5b20` / tree
`f44c9e3455b712572f8c6c022883eadb3ebd9c56` passed mapped FULL run
`41822221848`, attempt 1, but was rejected by ChatGPT exact-source review before
integration. It is preserved immutable terminal-green evidence.

The current checkpoint is one corrective child of that predecessor. Its
worktree is clean before editing, and `develop` remains at the parent
`b7d42863d24958d1ce0fcf9f51eff67397f94240` pending child acceptance.

D30 is ACCEPTED with dataset ID
`d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, dataset SHA
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, and
`ALPACA_ALL_ADJUSTED_PRICE_V1`. D31's exact bundle is ACCEPTED with campaign
`9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, bundle SHA
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, result
`NONE_QUALIFIES`, and retained control `BASE_MA35_50_V1` / candidate
`21158358-75be-5597-b940-5bccdda1429c`. D32 is PARTIAL_PASS: strategy math and
research binding passed; live data-basis parity is blocked by
`DATA_BASIS_MISMATCH`.

## D33 source boundary

The additive live-prototype source uses Alpaca's completed daily SPY bars with
adjustment `all`, SIP feed, USD, 1Day, ascending order, and exactly the latest
60 published completed XNYS sessions. It constructs `CompletedSignalInputs`
from genuine Alpaca closes and binds the exact response digest, observation,
and cutoff. The pure BASE_MA35_50 decision helper preserves the D32-proven
Decimal formula. Robinhood MCP remains broker/account/execution/custody; no
provider fallback exists.

The frozen P6 raw Robinhood 59+1 source, evidence, ownership/kill semantics,
execution markers, and historical architecture pins are preserved. D33 does
not relabel or rewrite them. No provider observation has occurred, and source
publication grants no provider, paper, broker, runtime-binding, campaign,
production, or live authority.

## Next milestone and stop conditions

The child addresses only exact integration-required source admission,
source-owned current clock, completed-session cutoff semantics,
invalid-clock sanitization, tests, and documentation. After exact-source
review, publish one normal atomic child commit and one mapped
`arch147-live-prototype` FULL run. Do not integrate the child until independent
acceptance. Develop remains at the parent while this review is pending.

After acceptance, fast-forward `develop` exactly to the child with certification
reuse, verify local/remote identities, then run one fresh absolute
`F:\AI\temp` D33 read-only observation using the accepted v3 Alpaca credential
boundary. The operator admits exact feature/develop identity before
credential/provider construction, uses its current UTC clock, makes at most
one request, never calls Robinhood, and writes only sanitized evidence. An
uncertain or failed provider request is consumed with no retry.

That observation can close the current data-basis blocker but cannot authorize
a live order. Q61 remains NOT RUN; no readiness label is granted. L40-L43
remain unresolved, including official fractional exit capability, exact owned
exit semantics, and durable cumulative budget/recovery/capability work. Do not
insert a paper soak between D33 and L40-L43. FINAL_HOLDOUT remains sealed.

The old P6 protected read-only preflight remains a separate historical/current
predecessor boundary and is not the D33 signal-data path.
