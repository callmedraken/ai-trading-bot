# AI Trading Bot - Project Status

## Current milestone - L43 A3 ACCEPTED / INTEGRATED; A2 METADATA OBSERVATION ACCEPTED; B1 NEXT

Architecture 147 L43 A3 is SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at `5b571734222324b98786b150236b1dfd471d8b9d` / tree `7c8986d360851ebf07af74e37608f18185dd7d74`.

Feature push run `43411983474`, attempt 1, passed source-static, active-tests, all seven mapped FULL lanes, and source-gates on the exact A3 source. Active tests selected the A3 prototype runner plus A1/A2 qualifier/observer/runtime-schema coverage. Canonical lane wall times were `93.904 / 138.369 / 129.147 / 246.945 / 105.439 / 206.077 / 144.409` seconds, all below 300 seconds. Develop run `43503087853`, attempt 1, passed with `DEVELOP_CERTIFICATION_REUSE=True` / `exact_feature_certification`; active tests and all FULL lanes were skipped, so no duplicate canonical certification was consumed.

A3 preserves the shared historical preflight dispatch chain and registers the accepted A2 runtime-partition metadata observer only as the `arch147-live-prototype` read-only `preflight`; `execute=None` and `remote_head_env=None` remain. The A2 qualifier/observer source remained unchanged by A3.

The one reviewed A2 metadata observation is ACCEPTED / CONSUMED SUCCESSFULLY / NO RETRY. Runner evidence:
`F:\AI\temp\ai-trading-bot-checkpoints\operator-33734b29c3f441ae88abe546e241d91f\arch147-live-prototype\preflight-20261113T205548.135877Z\report.json`.
Observer evidence:
`F:\AI\temp\arch147-agent-initiated-runtime-proof-eligible-0d1c18123732442c9d3f4a14ba0f43e6\evidence.json`;
SHA-256 `34483478bbf6430ff0e9a139cd33cdc8837be22eff100e53e0f6b2fdde46c3f1`.

The observation was exact-source bound to the accepted A3 HEAD/tree before and after dispatch with `IDENTITY_STABLE=True`. It consumed one OAuth scope-entry attempt, one MCP session-open attempt, and one `tools/list` attempt/page. Browser launches, MCP tool invocation attempts, account/order/position reads, review/place/cancel calls, and other tool calls were all zero. Status was `AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW` / `SUCCESS_REVIEW_ONLY`.

This evidence authenticates only that the provider metadata is eligible for the later runtime partition proof. It explicitly retains `partition_equality_proof=NOT_PROVEN` and `production_order_scope_authority=NOT_GRANTED`. Production therefore remains `ORDER_SCOPE_UNPROVEN`. The earlier `placed_agent` observation remains separately consumed/immutable; Q62 remains consumed/immutable; Q63 is NOT RUN; L41R7 remains FORBIDDEN; `FINAL_HOLDOUT` remains SEALED.

## Immediate next step

Implement B1 as the narrow source milestone that propagates strict boolean `agent_initiated` through the normalized L43 order model/read adapter. Accept only actual booleans; reject/null/fail closed on strings, numbers, missing or ambiguous values. Do not add account-wide order-scope authority, runtime partition equality, provider fallback, trading authority, or protected effects. B1 should use focused fake-only tests and one prepublication admission before its single feature push. The subsequent B2 milestone will perform the separate four-read runtime set-equality proof using ALL-before / TRUE / FALSE / ALL-after.

## L41R1, L41R2, and L41R3 historical observations

L41R1 is recorded exactly as
`L41R1_REAL_OBSERVATION=CONSUMED_BLOCKED_NO_RETRY`. Its preserved evidence is
`F:\\AI\\temp\\arch147-l41r1-schema-observation-f5b81e5f60dc40c280f53007d1db2b52\\evidence.json`,
SHA-256
`2b62f54076fdfd34aa3eb799ed563701f8eadafe8877b25590f88fe72147160f`,
length `1130` bytes. It recorded source admission PASS, one OAuth scope-entry
attempt, one MCP session-open attempt, zero `tools/list` attempts, empty
schemas, reason `L41R1_MCP_SESSION_OPEN_FAILED`, and zero MCP tool, account,
tradability, position, order, portfolio, quote, review, placement, cancellation
and other-tool attempts.

The exact source-contract cause was
`_create_windows_oauth_factory()` installing `_forbid_interactive_oauth`; the
MCP OAuth SDK required an authorization-code flow and invoked that blocker. The
classification is `L41R1_INTERACTIVE_OAUTH_FORBIDDEN`, not a generic browser or
environment failure. The attempt also exposed an upstream OAuth/MCP traceback
output defect: sanitized evidence did not prevent provider/OAuth traceback text
from reaching the terminal.

`L41R2_INTERACTIVE_SCHEMA_DISCOVERY` is a separately named additive successor
with evidence schema `arch147-l41r2-interactive-interface-observation/v1`. It
retains the corrected schema semantics, permits one reviewed interactive OAuth
authorization when persisted state is insufficient, suppresses upstream
provider/OAuth output, invokes only bounded `tools/list`, and records no raw
URLs, callback values, tokens or provider text. Credential reads and writes are
SDK-managed and individually uncounted (`null`/`null`). A successful result is
`CAPTURED_FOR_REVIEW` only; it grants no live readiness, broker authority, Q62
acceptance or order authority. At that historical checkpoint, Q62 was NOT RUN
and blocked pending L41R3 classification; its current boundary is above.

The L41R2 observation is CONSUMED / BLOCKED / NO RETRY. Its preserved evidence
is
`F:\\AI\\temp\\arch147-l41r2-schema-observation-9a504f5e26b9414998cea287ee13936a\\evidence.json`,
SHA-256
`66C3E5C32A0FD575490B3219AEA7DE2ECCEE65C4E5FDEFF6EB339B9B963FA751`, length
`1386` bytes. It records `L41R2_SCHEMA_MALFORMED`, source HEAD/tree
`d421562703d6bae92b14afdcc1b3defcc595dbc8` /
`b0ca242360b1cfe17222c4b56e95198219eee4be`, and FEATURE plus
PROSPECTIVE_DEVELOP admission PASS. It records one OAuth scope-entry attempt,
one MCP session-open attempt, one browser launch, and one `tools/list` attempt.
MCP tool invocation, account, tradability, positions, orders, portfolio,
quotes, review, placement, cancellation, and other-tool attempt counters are
all zero. Native credential read/write counts are both `null` with accounting
`SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`; automatic retry is FORBIDDEN.

The source extracts `inputSchema`, while MCP SDK v2 Tool objects expose the
Python attribute `input_schema` and retain `inputSchema` on the wire. The
L41R2 fake object fixture used the older camelCase attribute and did not cover
the SDK object model. This is a source/client-model comparison; the consumed
evidence itself does not identify a raw provider object type.

L41R3 is the separately named additive successor with evidence schema
`arch147-l41r3-mcp-v2-interface-observation/v1`. It normalizes only tool name,
description, input schema, and pagination cursor before passing them through
the existing fail-closed sanitized schema parser. It accepts MCP-v2
`input_schema`, wire/mapping `inputSchema`, and the intentionally retained
legacy object attribute `inputSchema`. It preserves one-shot OAuth/session and
browser limits, bounded `tools/list`, zero tool invocations, output
suppression, truthful SDK-managed credential accounting, and no-retry
semantics. `CAPTURED_FOR_REVIEW` grants no Q62 readiness, broker/order or
numeric-rule authority, live eligibility, or `FINAL_HOLDOUT` authority. At the
L41R2 source-acceptance checkpoint, the L41R3 observation had not yet been run;
its later consumed result is recorded in the current boundary above.

The first unpublished L41R2 prepublication admission is preserved at
`F:\\AI\\temp\\arch147-l41r2-source-admission-2804bb15b8ec49eab4f0ac8ac0fe0a0f` and is classified
`PREPUBLICATION_ADMISSION_TOPOLOGY_DEFECT` / `FULL_LANE_DUPLICATE_BASENAME`.
Adding the interactive L41R2 test enlarged the deterministic FULL inventory and
exposed `tests/portfolio/test_models.py` and
`tests/rebalancing/test_models.py` together in broad-5 under the current
top-level pytest import topology. The required invariant observed `40 != 39`
unique basenames. No authority failure occurred, `IDENTITY_STABLE=True`, and
`PROTECTED_EFFECTS=0`; this was not a product-source failure, published red
source, coverage defect, or GitHub CI failure. That first admission remains a
preserved failure. A later fresh admission passed, and the corrected candidate
was published and independently accepted at
`235118f70b7c7039055e9fea45ccf27df46671a0` / tree
`972004101036afe52642ed93c38fed21ea479956`. Mapped FULL run `42358983502`,
attempt 1, was terminal SUCCESS. The real
`L41R2_INTERACTIVE_SCHEMA_DISCOVERY` was later consumed as BLOCKED / NO RETRY;
see the exact evidence record above. At that source-acceptance checkpoint,
L41R3 was its additive successor and had not yet been run against Robinhood;
the later L41R3 observation is recorded in the current boundary above.

## L40 accepted/integrated baseline

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

At L40 closeout, the remaining path started with the L41 read-only Robinhood
fractional-exit capability observer, followed by durable ownership/budget,
runtime signal, application, readiness/recovery, and live qualification work.
That L40 plan is historical; the current source-preparation state and next step
are recorded above. `FINAL_HOLDOUT` remains sealed.

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

## Product and protected boundaries

The product remains a private single-user Windows desktop application with
explicit Start/Stop and manual stopped-state updates. Credentials and durable
state remain outside disposable source files. Live trading is disabled; no real
order is authorized. Readiness labels are not granted by source publication,
source admission, or provider-data parity alone.

Historical P6, P5A/P5B, and earlier architecture evidence remains available in
its owning documents. The current handoff and Architecture 147 validation
ledger record the bounded continuation identity and acceptance state.
