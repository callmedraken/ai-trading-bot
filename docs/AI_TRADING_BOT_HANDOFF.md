# AI Trading Bot - Current Handoff

## Current milestone: REAL B2 OBSERVATION CONSUMED / NOT PROVEN; NORMALIZATION CORRECTIVE NEXT

Canonical source used by the consumed observation:

- HEAD: `e466d33cf3a859976f48d7b7092fa3b58afc2f53`
- tree: `45b9254a6aaf429c9a5322a31022089a8af954f4`
- branch: `feature/robinhood-live-prototype-current`
- feature/develop equality at observation: PASS
- source recheck after observation: PASS

Consumed observer evidence:

- `F:\AI\temp\arch147-agent-initiated-runtime-partition-de58697fd0f642fa82c00d231f572f34\evidence.json`
- B2 evidence SHA-256: `15dfa00092447881af7289287210faf50ba3bf292102fb5cb534174b149255ca`
- status: `NOT_PROVEN`
- reason: `ALL_BEFORE_READ_EXCEPTION`
- account fingerprint: `f377529245bd1682f382d17b22ac8d55362f7138a4f7fc307593c16847e551cf`
- partition equality: `NOT_PROVEN`
- production order-scope authority: `NOT_GRANTED`

Attempt counters:

- `oauth_scope_entry_attempts=2`
- `mcp_session_open_attempts=2`
- `tools_list_attempts=2`
- `tools_list_pages_received=2`
- `account_read_attempts=1`
- `order_read_attempts=1`
- `mcp_tool_invocation_attempts=2`
- `browser_launch_attempts=0`
- `review_attempts=0`
- `placement_attempts=0`
- `cancellation_attempts=0`
- `other_tool_attempts=0`

This is CONSUMED / NO RETRY. The first ALL_BEFORE order read did not complete and no logical-read snapshot was accepted.

Independent source audit identified a normalization-contract defect. The accepted A2/B2 provider schema requires only `id`, `symbol`, and `agent_initiated` on order rows for this proof, but `RobinhoodL43B2PreEffectReadAdapter` currently calls the generic `parse_equity_orders_response()` / `RobinhoodEquityOrder` parser. That parser demands numerous additional fields not guaranteed by the accepted B2 schema. Q62's successful historical order read was narrower because it filtered `placed_agent="agentic"`; it did not establish generic parsing for the unfiltered ALL population.

The exact underlying row/parser exception is not recoverable from the sanitized evidence and must not be invented. The source contract mismatch itself is sufficient to block production authority and justify a fake-only corrective.

## Immediate next step

Build B2N1 as a source-only account-wide normalization correction:

- remove generic full-order parsing from the B2-specific adapter;
- validate required row `id`, `symbol`, and exact bool `agent_initiated`;
- deterministically canonicalize/hash the complete JSON row for mutation detection without persisting raw order data or IDs;
- return a B2-specific normalized fact consumed by the existing four-read proof;
- preserve exact query sequence and pagination;
- keep ordinary L43/Q62 generic parsing unchanged;
- add manual/customer-order-shaped fixtures with optional/null/absent non-B2 fields;
- remain zero-provider/fake-only;
- do not authorize or perform another real B2 observation.

Production remains `ORDER_SCOPE_UNPROVEN`; Q63 NOT RUN; `FINAL_HOLDOUT` SEALED.

## L41R1 consumed observation and L41R2 source successor

The consumed predecessor is recorded exactly as
`L41R1_REAL_OBSERVATION=CONSUMED_BLOCKED_NO_RETRY`. Its preserved evidence is
`F:\\AI\\temp\\arch147-l41r1-schema-observation-f5b81e5f60dc40c280f53007d1db2b52\\evidence.json`,
SHA-256
`2b62f54076fdfd34aa3eb799ed563701f8eadafe8877b25590f88fe72147160f`,
length `1130` bytes. It recorded source admission PASS, OAuth scope entry `1`,
MCP session-open `1`, `tools/list=0`, empty schemas, reason
`L41R1_MCP_SESSION_OPEN_FAILED`, and zero MCP tool, account, tradability,
position, order, portfolio, quote, review, placement, cancellation and
other-tool attempts.

The exact cause was `_create_windows_oauth_factory()` installing
`_forbid_interactive_oauth`; the MCP OAuth SDK required an authorization-code
flow and invoked that blocker. The classification is
`L41R1_INTERACTIVE_OAUTH_FORBIDDEN`, not a generic browser/environment failure.
The attempt also exposed an upstream OAuth/MCP traceback-output defect because
provider/OAuth traceback text reached the terminal despite sanitized evidence.

`L41R2_INTERACTIVE_SCHEMA_DISCOVERY` is the separately named additive successor
with evidence schema `arch147-l41r2-interactive-interface-observation/v1`. It
preserves the corrected schema facts, permits one reviewed interactive OAuth
authorization when persisted state is insufficient, suppresses upstream
provider/OAuth output, and invokes only bounded `tools/list`. Evidence records
browser launches as `0` or `1`, native credential read/write counts as `null`,
and `SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`; raw URLs, callback values, tokens
and provider text are never persisted. A successful result is
`CAPTURED_FOR_REVIEW` only and grants no live readiness, broker authority, Q62
acceptance or order authority. At that historical checkpoint, Q62 remained NOT
RUN and blocked pending L41R3 classification; the current Q62 boundary is
recorded above.

The L41R2 observation is CONSUMED / BLOCKED / NO RETRY. Its immutable evidence
is
`F:\\AI\\temp\\arch147-l41r2-schema-observation-9a504f5e26b9414998cea287ee13936a\\evidence.json`,
SHA-256
`66C3E5C32A0FD575490B3219AEA7DE2ECCEE65C4E5FDEFF6EB339B9B963FA751`, length
`1386` bytes, reason `L41R2_SCHEMA_MALFORMED`. Source HEAD/tree were
`d421562703d6bae92b14afdcc1b3defcc595dbc8` /
`b0ca242360b1cfe17222c4b56e95198219eee4be`; FEATURE and
PROSPECTIVE_DEVELOP admission both passed. It recorded one OAuth scope-entry
attempt, one MCP session-open attempt, one browser launch, and one `tools/list`
attempt. All prohibited MCP tool/account/tradability/position/order/portfolio/
quote/review/place/cancel/other-tool counters were zero. Native credential
read/write fields are `null` with accounting
`SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`; automatic retry is FORBIDDEN.

The failure is classified from source/client-model comparison: the source
extracts the wire spelling `inputSchema`, while MCP SDK v2 Tool objects expose
the Python attribute `input_schema`. The consumed evidence does not record the
raw provider object type. L41R3 is the additive successor with evidence schema
`arch147-l41r3-mcp-v2-interface-observation/v1`; it normalizes only name,
description, schema and pagination cursor before using the existing fail-closed
sanitized parser. Its success remains `CAPTURED_FOR_REVIEW` only, with zero
tool calls and no Q62, live, broker, order, numeric-rule or `FINAL_HOLDOUT`
authority. At the L41R2 source-acceptance checkpoint, real L41R3 had not yet
run; its later consumed observation is recorded above.

The first unpublished L41R2 prepublication admission is preserved at
`F:\\AI\\temp\\arch147-l41r2-source-admission-2804bb15b8ec49eab4f0ac8ac0fe0a0f` and is classified
`PREPUBLICATION_ADMISSION_TOPOLOGY_DEFECT` / `FULL_LANE_DUPLICATE_BASENAME`.
The enlarged FULL inventory placed `tests/portfolio/test_models.py` and
`tests/rebalancing/test_models.py` together in broad-5, producing the required
`40 != 39` basename invariant failure under the current pytest topology. No
authority failure occurred, `IDENTITY_STABLE=True`, and `PROTECTED_EFFECTS=0`.
This was not a product-source failure, published red source, coverage defect,
or GitHub CI failure. The corrected admission subsequently passed, the amended
candidate was published as
`235118f70b7c7039055e9fea45ccf27df46671a0` / tree
`972004101036afe52642ed93c38fed21ea479956`, mapped FULL
`42358983502` attempt 1 was terminal SUCCESS, and independent exact-source
review accepted the L41R2 implementation. At that source-acceptance checkpoint
the real observation had not yet run; it was subsequently consumed as
BLOCKED / NO RETRY in the L41R2 record above. It does not advance Q62.

## L40 accepted/integrated checkpoint

Canonical worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`;
branch: `feature/robinhood-live-prototype-current`.

Accepted L40 source HEAD:
`14e1b628c0c51c27b23deabee56eb91859818529`

Accepted L40 source tree:
`48b588cbb37818b0d1edfcbb895cfb715a2bf2d3`

Direct parent:
`f7f13f805ad6a0eea7041cb6d13c561149a13f6e`

Feature mapped FULL `41995282653`, attempt 1, was SUCCESS with all seven
canonical broad lanes, active tests, hygiene/evidence and aggregate source gate
green. The exact source was independently accepted. Ordinary fast-forward
integration then moved `develop` to the accepted L40 source; develop gate
`41997418576`, attempt 1, was SUCCESS and reused feature certification
`41995282653` without another FULL. Remote feature and develop were both
verified at the accepted L40 HEAD/tree before this coordination closeout.

The accepted [L40 contract](architecture/147-restricted-live-contract.md) is an
effect-disabled pure policy owner. It freezes exact-owned full-remainder exits,
the <=$10 requested/cumulative new-acquisition budget, reducing exits without a
universal $10 exit-notional ceiling, partial-fill ownership, residual
preservation, exact identity matching and UNKNOWN/MAY_HAVE_OCCURRED no-retry
semantics. Evidence-reference flags are necessary-only prerequisites and
authenticate nothing by themselves. L40 does not establish actual Robinhood
account fractional-sell eligibility, numeric quantity/minimum/notional rules,
durable controller persistence or live-order authority.

The next source step described at L40 was superseded by the current source
preparation milestone above. D33 and D34 remain consumed/no-retry and
`FINAL_HOLDOUT` remains sealed. No paper soak is inserted.

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

At the L40 closeout, its original L41-L43 dependency plan was the accepted
baseline and Q61 had not yet run. Q61 was accepted later as recorded in the
current milestone above. No live-readiness label or paper-soak milestone is
granted and `FINAL_HOLDOUT` remains sealed.

The old P6 preflight is historical predecessor context, not the current next
operator action and not the D33/D34 signal-data path. It grants no retry.
