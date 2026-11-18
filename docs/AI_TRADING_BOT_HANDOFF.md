# AI Trading Bot - Current Handoff

## Current milestone: RHC4 C2 prepublication coverage and stale-current correction

Canonical feature worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`.
Branch: `feature/robinhood-live-prototype-current`.

Accepted/integrated RHC3P final executable identity:

- predecessor docs/start HEAD: `209f27a3c1a3d9691a1bd7d097bb30b0d70ce7d3`
- first RHC3P publication: `6503ee1088d7532bc2f77dc0fe16bbf1dc52dab8` / tree `e12ebc4b863669b83236e66640a39c9454d8ffb1`
- corrective C1/final accepted HEAD: `26e168f15747345e25c550a2d76ccac8f4adaa0b`
- final accepted tree: `3ef5dba7eba54f892269ddb59aea48b297208ecd`
- superseded candidate mapped FULL: `44062318005`, attempt 1, terminal SUCCESS, preserved/no rerun
- final C1 mapped FULL: `44073855992`, attempt 1, terminal SUCCESS
- develop exact-source run: `44152192296`, attempt 1, terminal SUCCESS
- develop reuse: `DEVELOP_CERTIFICATION_REUSE=True`
- develop reuse reason: `exact_feature_certification`
- develop identity stability: `IDENTITY_STABLE=True`
- duplicate develop FULL: NO

Exact-source review accepted the final C1 source. The correction changes only the effect operator, post-effect reconciler, and their focused tests relative to the first RHC3P candidate.

The first RHC4 publication is `2f4f50a1df44c261d172f55bc540b635d637cbd9` /
tree `558e2f8c1f930d3f15810dea3f01a92ca20fdc24`. Its mapped FULL run
`44181143712`, attempt 1, is preserved terminal SUCCESS. Exact-source review
rejected that source for `RHC4_STOP_EFFECT_BOUNDARY_RACE` and new direct
coupling to private helpers. The run is terminal-green preserved evidence, not
a failed CI result, and must not be rerun or rewritten. C1 is the bounded
source-only/fake-only correction from direct parent `2f4f50a1df44c261d172f55bc540b635d637cbd9` /
tree `558e2f8c1f930d3f15810dea3f01a92ca20fdc24`. C1 is published at
`f3f44e00ec17279ea74445df2b7a680875745f7b` / tree
`8dac42fa7039bde8fdb6f6bdd63eeaf432cb049a`, directly from that parent.

C1's mapped run `44192574584`, attempt 1, is preserved terminal FAILURE and
was not retried, amended, rerun or relabeled. `source-static` passed;
`active-tests` reported `1774 passed, 1 skipped, 1 failed`; broad-1 through
broad-5 and broad-7 passed; broad-6 reported `2123 passed, 7 skipped, 1
failed`; and `source-gates` failed. The exact failure was
`tests/robinhood_mcp/test_l43_production_composition.py::test_production_composition_is_inert_and_wires_normalized_read_dependencies`,
which still monkeypatched removed private seam `composition._git_output`.
Local reproduction used fresh basetemp
`F:\\AI\\temp\\pytest\\rhc4-c1-coverage-defect-42118041f5e04c18acc2a5c776a2e1dc`
and failed one test in 0.44 seconds. Classification:
`PREPUBLICATION_COVERAGE_DEFECT`.

## RHC3P accepted contract

RHC3P retains provider `requested_quantity` and `trigger` in normalized L43 order facts and reuses one shared factual broker-read kernel for both strict pre-effect interpretation and post-effect settlement.

Post-effect facts require:
- canonical Q62 origin and account fingerprint;
- current accepted source continuity;
- exhaustive unfiltered account+SPY order coverage;
- the RHC3 `ACCOUNT_WIDE_ALL_AGENTS` scope proof;
- exact stored provider order binding;
- SPY, `agent_initiated=true`, exact side/kind;
- market / regular-hours / GFD / immediate order contract;
- unique positive execution facts whose sum equals cumulative quantity;
- monotonic quantities/notional;
- no unrelated SPY row;
- exact broker position = baseline + confirmed ENTRY buys - confirmed EXIT sells.

Dollar ENTRY is dollar-authoritative, not provider-share-estimate-authoritative. Requested USD must match the durable reservation; provider requested share quantity may be absent or vary; durable ENTRY `working_remainder` is zero. The full one-time requested-dollar budget remains consumed while only confirmed shares become owned.

EXIT remains exact-share-authoritative. Provider requested quantity must equal durable requested quantity and exact residual math is preserved.

The C1 correction adds a repeatable read-only settlement path for already-bound `WORKING` / `PARTIAL` orders. It does not take a detached effect plan, does not acquire a fresh effect authorization, does not prepare an effect transport, and cannot review/place/cancel/retry. It validates current durable identity and the stored provider ID, proves current source continuity, reruns the same RHC3-proven exhaustive read, and persists only monotonic factual reconciliation.

ENTRY `WORKING/PARTIAL -> FILLED/CANCELED/REJECTED` can therefore converge after the immediate placement read without a second order. A known WORKING SELL returns `SELL_PENDING` and remains known-working rather than being converted to UNKNOWN. Later SELL FILLED reconciles to flat. Later PARTIAL/CANCELED/REJECTED with residual enters sticky manual-close with no replacement sell.

Settlement read failure preserves the previously known durable facts and returns blocked; it does not create a new effect or invent a terminal state. Ordinary pre-effect admission remains strict and continues to block while settlement is pending.

## Sell-review contract

The accepted L41R6 source-owned official claim `REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS` binds `REVIEW_PREVIEW_ONLY=PROVEN / L41R6_OFFICIAL_REVIEW_PREVIEW_PROVEN`. The production review normalizer authenticates that claim before opening a review session. Only an exact successful structured response for the exact full-owned SPY market sell with empty checks and matching review/place arguments may normalize to `AFFIRMATIVE / NONPLACING_PREVIEW`. That is not placement success and does not grant reusable placement authority.

## Effects and protected boundaries

RHC3P and C1 are source-only/fake-only. They performed zero OAuth, browser, MCP, account, position, order, review, placement, cancellation, or Alpaca calls in the real environment. Q62, RHC2/RHC3 retained evidence, and production L43 state were untouched.

RHC2 remains `CONSUMED / PASS / NO RETRY`.
RHC3 remains accepted/integrated and its retained evidence remains immutable.
The RHC4 source checkpoint adds a production L43 composition, an explicit restricted-live application service and launcher mode, and a serialized runtime lifecycle. The production exact-plan authorizer denies by default. Start/Stop control worker lifecycle only. C1 gives Stop and the transition into the one-way placement/review boundary one common ordering decision: a Stop that wins before the boundary blocks reservation/MAY/review/provider work, while a path that wins and durably reaches `MAY_HAVE_OCCURRED` or review-start is allowed to finish factual reconciliation/classification. An existing bound pending ENTRY/SELL is settled through read-only RHC3P convergence before a new effect is evaluated. Construction, import and help perform no provider action. The default research worker stays idle until a research source is separately supplied. The existing comparison-report worker can operate alongside restricted-live runtime.

RHC4 C2 remains SOURCE_ONLY / FAKE_ONLY. The current bounded correction is
`ARCH147-RHC4-C2_PREPUBLICATION_COVERAGE_AND_STALE_CURRENT_CORRECTION`. It
updates the stale composition test to `read_source_identity`, makes admission
execute the complete deduplicated route-owned `ARCH147_PROTOTYPE_TESTS` set,
and updates stale current seam/type/documentation references. No real
Robinhood/OAuth/browser/MCP/Alpaca/read/review/place/cancel action occurred
for this source checkpoint; provider and protected-effect counters are zero.
It does not grant effect authority or live readiness.
Focused fake-only tests, current/historical authority, both source-context
selections, whole-repository Ruff, and diff checks are required before C2
publication. Exact commands and basetemps are recorded in the [validation
ledger](validation/arch147-live-prototype.md#rhc4-c2-prepublication-coverage-and-stale-current-correction).
L43 protected qualification remains NOT_RUN.
Q63 remains NOT_RUN.
`FINAL_HOLDOUT` remains SEALED.

## RHC4 source checkpoint and next gate

The checkpoint is prepared from the synchronized RHC3P baseline at `fdbdbb4fe887fa52b4733dc7cf544dfa45aaf7b0` / tree `3c2df33d5b4cb892c57404ea1daa29a73d12e3c2`. It uses the existing `arch147-live-prototype` feature push route and its mapped FULL. No RHC4 branch or protected execute route is added. The implementation:
- composes canonical Q62/RHC3 read authority and RHC3P repeatable settlement;
- reuses the existing durable L43 state/session owner;
- reuses the existing L43 effect operator and Robinhood effect transport rather than duplicating business logic;
- composes the Alpaca runtime signal path;
- adds a production exact-plan authorizer seam that is closed by default and cannot be satisfied by GUI Start, CLI flags, environment variables, caller booleans, or RHC3/Q62 proof alone;
- adds an explicit live/restricted-live application service and launcher path while keeping construction/help/import effect-free;
- keeps Start/Stop lifecycle distinct from effect authorization;
- performs no real provider effect in the source checkpoint.

The existing route requires `ops.ps1 admit` on the exact clean C2 source before its single ordinary corrective push. The corrected admission must execute the production-composition test and the complete route-owned prototype set, with FEATURE and PROSPECTIVE_DEVELOP PASS and stable identity. After push, the mapped feature FULL must reach terminal state. ChatGPT exact-source review and acceptance follows CI. L43 protected qualification remains NOT_RUN. Q63 remains NOT_RUN. `FINAL_HOLDOUT` remains SEALED. No protected execution is part of RHC4.

The required public-reference cross-check was read-only and corroborating only:
`EUGMsub/RobinhoodAgenticTrader` main `src/mcp_client.py` and `src/oauth.py`
show lazy MCP initialization/session caching with `Mcp-Session-Id`, bounded
401/404 recovery, and OAuth 2.1 + PKCE; `kevin1chun/robinhood-for-agents`
main `src/server/official/forward.ts` and `docs/MODES.md` show a provider-owned
lazy cached client for `https://agent.robinhood.com/mcp/trading`, provider-owned
bearer injection, and application/provider separation. These repositories are
implementation evidence only; C2 does not redesign our session lifetime or
weaken source ownership, exact-plan authorization, durable MAY/UNKNOWN,
no-retry, or protected-effect boundaries.

## RHC3 production order-scope admission

RHC3 consumes, but never mutates or retries, the exact retained A2/RHC2 chain:

- A2 semantic evidence: `F:\AI\temp\arch147-agent-initiated-runtime-proof-eligible-0d1c18123732442c9d3f4a14ba0f43e6\evidence.json`, SHA-256 `34483478bbf6430ff0e9a139cd33cdc8837be22eff100e53e0f6b2fdde46c3f1`
- RHC2 registered report: `F:\AI\temp\ai-trading-bot-checkpoints\arch147-rhc2-robinhood-order-scope-successor-observation\preflight-20261117T064253.945488Z\report.json`, SHA-256 `25873f5cdbb509b7a93b80a0644affb01e784c1bf0145a1aca20222ac71f56e9`
- RHC2 observer evidence: `F:\AI\temp\arch147-agent-initiated-runtime-partition-3f05ea6fed42440293ea3d58a1af5074\evidence.json`, SHA-256 `99bca426cba77589055be6dc826cf0d72884c51e40f493c19b55625ac2bf2189`
- reconstructed inner B2 evidence SHA-256: `7016e9c9f5a8b52e996a56e5eab4ee89ce993b967513109c09af23aa5e693fc3`

A2 authenticates the hosted `agent_initiated` filter semantics. RHC2 remains CONSUMED / PASS / NO RETRY and supplies four exhaustive runtime-consistency reads (`ALL_BEFORE`, `TRUE`, `FALSE`, `ALL_AFTER`), all zero-row. The zero-row observation is not treated as a non-empty semantic witness.

The RHC3 loader reads only those fixed paths, validates exact file hashes before parsing, rejects symlink/reparse/path/object drift, duplicate or unexpected JSON structure, wrong counters/status/source identity, and any write/other-tool attempt. It reconstructs and verifies the inner B2 digest and requires the retained RHC2 account fingerprint to equal canonical Q62.

At each current L43 proof request, the production verifier reauthenticates the evidence chain rather than caching authority. It accepts only the exact current unfiltered `{"account_number": ..., "symbol": "SPY"}` query, proves the account-number hash matches the Q62-bound fingerprint, requires bounded positive page count, bounded nonnegative row count and exhausted pagination, and returns an `ACCOUNT_WIDE_ALL_AGENTS` scope proof whose evidence digest binds all four retained evidence hashes plus current account/query/page/row/exhaustion facts. Any failure returns no proof and preserves `ORDER_SCOPE_UNPROVEN`.

The historical RHC2 field `production_order_scope_authority=NOT_GRANTED` remains unchanged; RHC3 is the separately source-reviewed consumer that grants only this narrow pre-effect order-scope prerequisite. It does not grant review/place/cancel authority or any generic live-effect permission.

The three pinned evidence files are now operational runtime dependencies. Do not clean, move, rewrite, regenerate, or replace them. Q63 must include their exact custody, backup/restore and hash verification in the final delivery package. Loss or mutation is fail-closed availability loss, not authority to recreate evidence.

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
RUN and blocked pending L41R3 classification.

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
run; a later consumed observation followed that checkpoint.

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
baseline and Q61 had not yet run. Q61 was accepted later; this passage records
the earlier L40 state. No live-readiness label or paper-soak milestone is
granted and `FINAL_HOLDOUT` remains sealed.

The old P6 preflight is historical predecessor context, not the current next
operator action and not the D33/D34 signal-data path. It grants no retry.
