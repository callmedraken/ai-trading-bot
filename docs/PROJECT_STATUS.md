# AI Trading Bot - Project Status

## Current milestone - RHC4 C2 prepublication coverage and stale-current correction

RHC3P is independently SOURCE/CERTIFICATION ACCEPTED and FAST-FORWARD INTEGRATED at final corrective HEAD `26e168f15747345e25c550a2d76ccac8f4adaa0b` / tree `3ef5dba7eba54f892269ddb59aea48b297208ecd`. Its direct parent `6503ee1088d7532bc2f77dc0fe16bbf1dc52dab8` remains preserved as the first RHC3P publication; exact-source review required the C1 pending-order convergence correction before integration.

The final feature mapped FULL run is `44073855992`, attempt 1, terminal SUCCESS. Source-static, active-tests, source-gates, and all seven canonical FULL lanes passed. The superseded first RHC3P run `44062318005`, attempt 1, also remains preserved terminal SUCCESS and was not rerun.

Develop fast-forwarded to the exact accepted final source. Develop run `44152192296`, attempt 1, is terminal SUCCESS with `DEVELOP_CERTIFICATION_REUSE=True`, reason `exact_feature_certification`, and `IDENTITY_STABLE=True`. Active tests and FULL were skipped on develop, so no duplicate broad certification ran.

RHC3P now separates strict pre-effect admission from repeatable read-only settlement of an already-bound order. The same canonical Q62-bound, exhaustive unfiltered account+SPY read kernel and RHC3 `ACCOUNT_WIDE_ALL_AGENTS` proof are reused. A known ENTRY or SELL in `WORKING` / `PARTIAL` can converge later through factual reads only; settlement cannot review, place, cancel, retry, acquire a new effect authorization, or change the stored provider binding. Working/partial state still blocks new effects.

Dollar ENTRY retains the exact USD reservation while its source-owned share remainder remains zero. EXIT retains exact requested-share and residual semantics. Fill quantities/notional remain execution-derived, fill regression fails closed, unrelated SPY rows fail closed, and broker position must equal durable owned fills before settlement facts are accepted.

A known `WORKING` SELL remains known-working as `SELL_PENDING`; it is not coerced to UNKNOWN merely because it has not filled yet. Later FILLED reconciles normally. Later PARTIAL/CANCELED/REJECTED with confirmed residual enters the existing sticky manual-close path with no replacement sell.

The accepted L41R6 `REVIEW_PREVIEW_ONLY` official-rule binding remains the source-owned semantic authority for nonplacing sell review. RHC3P grants no review or placement authority by itself.

The RHC4 source checkpoint adds a production L43 composition, an explicit restricted-live desktop service and launcher mode, and a serialized runtime lifecycle. The C1 correction serializes Stop with the transition into the one-way ENTRY/SELL placement or nonplacing SELL-review boundary. Stop wins before that boundary; once placement durably reaches `MAY_HAVE_OCCURRED`, or a sell review durably starts, the in-flight factual completion/classification is allowed to finish. A bound pending ENTRY or SELL is settled through the accepted read-only RHC3P path before a new effect is evaluated. Construction, import and help remain effect-free. The default research worker stays idle until a research source is separately supplied. The existing comparison-report worker can operate alongside restricted-live runtime.

The first RHC4 publication is `2f4f50a1df44c261d172f55bc540b635d637cbd9` / tree `558e2f8c1f930d3f15810dea3f01a92ca20fdc24`. Its mapped FULL run `44181143712`, attempt 1, is preserved terminal SUCCESS; exact-source review rejected that source for `RHC4_STOP_EFFECT_BOUNDARY_RACE` and the new private-helper repository coupling. The run remains terminal-green evidence and is not relabeled or rerun. C1 was published at `f3f44e00ec17279ea74445df2b7a680875745f7b` / tree `8dac42fa7039bde8fdb6f6bdd63eeaf432cb049a`, directly from the synchronized parent `2f4f50a1df44c261d172f55bc540b635d637cbd9`.

C1's mapped run `44192574584`, attempt 1, is preserved terminal FAILURE and was not retried, amended, rerun or relabeled. `source-static` passed; `active-tests` reported `1774 passed, 1 skipped, 1 failed`; FULL broad-1 through broad-5 and broad-7 passed; broad-6 reported `2123 passed, 7 skipped, 1 failed`; and `source-gates` failed. The exact deterministic failure was `tests/robinhood_mcp/test_l43_production_composition.py::test_production_composition_is_inert_and_wires_normalized_read_dependencies`, which still monkeypatched removed private consumer seam `composition._git_output`. It reproduced locally at `F:\AI\temp\pytest\rhc4-c1-coverage-defect-42118041f5e04c18acc2a5c776a2e1dc` with one failure in 0.44 seconds. The classification is `PREPUBLICATION_COVERAGE_DEFECT` because admission did not execute the current ARCH147 route-owned prototype test set.

The bounded C2 correction is `ARCH147-RHC4-C2_PREPUBLICATION_COVERAGE_AND_STALE_CURRENT_CORRECTION`: it updates the stale test to the public source-identity seam, makes prepublication admission include the deduplicated route-owned `ARCH147_PROTOTYPE_TESTS` set, and removes stale current private-boundary references. C2 remains SOURCE_ONLY / FAKE_ONLY. No real Robinhood, OAuth, MCP, Alpaca, review, placement or cancellation action occurred; provider and protected-effect counters are zero. It grants no broker-effect authority or readiness.

The first clean C2 admission reached the corrected route-owned bundle and executed the production-composition test, but is preserved as `PREPUBLICATION_ADMISSION_PORTABILITY_DEFECT`: report `F:\\AI\\temp\\ai-trading-bot-checkpoints\\arch132-r3n-prepublication-admission\\source-gate-20261118T012223.701722Z\\report.json` recorded FEATURE PASS, PROSPECTIVE_DEVELOP PASS, `IDENTITY_STABLE=True`, Ruff PASS and diff PASS, with `2691 passed, 1 skipped, 1 failed`. The sole failure was the current L41R4 test's assumption that pytest `tmp_path` is not on F:, despite the mandatory external F: basetemp. No push followed; no provider or protected effect occurred. The bounded follow-up changes only that test's candidate path to a synthetic C: path.

RHC2 remains `CONSUMED / PASS / NO RETRY`. RHC3 retained evidence remains immutable and operationally required. L43 protected qualification remains NOT_RUN; Q63 remains NOT_RUN; `FINAL_HOLDOUT` remains SEALED.

## Immediate next step

The existing `arch147-live-prototype` route requires `ops.ps1 admit` on the exact clean C2 source before its single ordinary corrective push. Admission must execute the route-owned prototype tests, including the corrected production-composition test, with FEATURE and PROSPECTIVE_DEVELOP identity stable. After push, the mapped feature FULL must reach terminal state. ChatGPT then performs exact-source review and acceptance. No protected L43 qualification, Q63, provider observation or broker effect is part of this source checkpoint.

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
and blocked pending L41R3 classification.

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
its later consumed result followed that checkpoint.

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
the later L41R3 observation followed that source-acceptance checkpoint.

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
