# AI Trading Bot - Project Status

## Current milestone - ARCH147_L41R5_CONSUMED_SEMANTIC_CLASSIFICATION

L41R5 source is SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at
`13a97b1f4c369243737cc0ac6646b5520327651a` / tree
`81e58dd75656593ca0f960ecdcdf21c14d00d969`. Feature run
`42905997160`, attempt 1, is terminal SUCCESS across source-static,
active-tests, canonical FULL broad-1 through broad-7, and source-gates. Develop
run `42926313979`, attempt 1, is terminal SUCCESS with
`DEVELOP_CERTIFICATION_REUSE=True`, `REASON=exact_feature_certification`,
`IDENTITY_STABLE=True`, and no duplicate FULL.

The one real L41R5 observation is permanently CONSUMED / BLOCKED / NO RETRY.
Evidence: `F:\\AI\\temp\\arch147-l41r5-schema-observation-6fcfcdf0cfd641fc95c7b5855292e8b4\\evidence.json`, 11128 bytes, SHA-256
`FC95EB9FBDD2B7DBE064B7CAC84E8851996669AF96BE1273AE46309873A650FF`. Reason: `L41R5_PLACE_NONPLACEMENT_SEMANTIC_CONFLICT`.
The attempt consumed one OAuth scope entry, one MCP session open, zero browser
launches, and one `tools/list`; every MCP tool/account/tradability/position/
order/portfolio/quote/review/place/cancel/other-tool invocation count is zero.
Native credential read/write counts remain `null` / `null` with
`SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`. Automatic retry is FORBIDDEN.

The diagnostic successfully closes the L41R4 schema-shape ambiguity. All three
interfaces exactly match the immutable L41R4 interface digests and all three
schemas report `additionalProperties=false`. Both order tools expose optional
direct-string `quantity` and `dollar_amount`; named-field requiredness and
logical string type are therefore recoverable, and the captured fractional
precision inventory is `[6]` without a precision-provenance conflict.

The remaining blocker is action-description interpretation, not schema shape.
After nested descriptions were separated, both order tools' top-level tool
descriptions still classify as simultaneously placing and nonplacing; the
review description also retains simulation/pre-trade/warning facts. Even
`get_equity_tradability` receives a coarse placing classification. Therefore
the document-wide lexical action classifier is not accepted authority for
review/place semantics. L41R5 must never be replayed.

The repository already contains the bounded source-owned
`official_rule_binding.py` seam for the official Robinhood tool catalogue,
fractional-shares help page, and customer agreement. That binding intentionally
has no accepted content digests yet, and current capability classification
deliberately treats submitted official rules as unaccepted. The next source
checkpoint is `ARCH147_L41R6_OFFICIAL_RULE_TRUST_BINDING`: authenticate and
freeze only the supported official claims, bind the consumed L41R5 interface
facts without replaying any observation, and emit the exact remaining 13-fact
blocker inventory. Do not add another broad prose-regex diagnostic.

`trusted_binding=false` and `provider_numeric_rules_derived=false` remain
authoritative for the consumed L41R5 evidence. Q62 remains NOT RUN and blocked;
L43 and Q63 remain NOT RUN. No live-readiness, broker, order, numeric-rule,
paper-soak, or `FINAL_HOLDOUT` authority is granted.

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

## Immediate next step

Implement `ARCH147_L41R6_OFFICIAL_RULE_TRUST_BINDING` as a source-only,
effect-free successor. Preserve the consumed L41 and L41R5 evidence identities.
Use the existing `official_rule_binding.py` / capability-classification seams
rather than another provider observation. The checkpoint must attach accepted
content digests and exact semantic claim IDs only to official Robinhood facts
the source can actually support, bind L41R5's exact sell-quantity/interface
facts, and produce a pure fail-closed 13-fact classification showing which
requirements are proven versus still blocking.

Do not infer provider maximum quantity, MCP residual-close behavior, or any
other absent rule from silence in public documentation. Do not run L41R5 again.
Do not run Q62 until the resulting exact blocker inventory has been independently
accepted and integrated.

## Product and protected boundaries

The product remains a private single-user Windows desktop application with
explicit Start/Stop and manual stopped-state updates. Credentials and durable
state remain outside disposable source files. Live trading is disabled; no real
order is authorized. Readiness labels are not granted by source publication,
source admission, or provider-data parity alone.

Historical P6, P5A/P5B, and earlier architecture evidence remains available in
its owning documents. The current handoff and Architecture 147 validation
ledger record the bounded continuation identity and acceptance state.
