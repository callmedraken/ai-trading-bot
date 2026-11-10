# Architecture 147 prototype task ledger and acceptance matrix

## L41R4 schema-classification diagnostic checkpoint (current)

The accepted and fast-forward integrated L41R3 source base is
`4461ea7f09c396c3c49598debbc588754fa5096c` / tree
`68cbfb70ea3eaa6f52a342e967d682ca5ab84bd2`. Feature run `42778436739`, attempt
1, is terminal SUCCESS. Develop run `42780649228`, attempt 1, is terminal
SUCCESS with `DEVELOP_CERTIFICATION_REUSE=True`,
`REASON=exact_feature_certification`, and `DEVELOP_DUPLICATE_FULL=NO`.

### L41R3 consumed observation

`L41R3_MCP_V2_SCHEMA_DISCOVERY` is CONSUMED / BLOCKED / NO RETRY with reason
`L41R3_SCHEMA_AMBIGUOUS`. Its immutable evidence is
`F:\\AI\\temp\\arch147-l41r3-schema-observation-8c9b3ae3eb394ce3aab836336f4a3052\\evidence.json`,
SHA-256
`1B96E7AF543148018BB2467F852D4752D18F0476B5C1A449056B88FB786F7AC6`, length
`1376` bytes. The observation source is `4461ea7f09c396c3c49598debbc588754fa5096c` /
`68cbfb70ea3eaa6f52a342e967d682ca5ab84bd2`; FEATURE and
PROSPECTIVE_DEVELOP admission both passed.

Exact attempt accounting: `oauth_scope_entry_attempts=1`,
`mcp_session_open_attempts=1`, `browser_launches=0`, and
`tools_list_attempts=1`. All MCP tool, account, tradability, position, order,
portfolio, quote, review, place, cancel, and other-tool invocation counters are
`0`. Credential accounting is `SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`, with
native read/write counts `null` / `null`. Persisted OAuth state was sufficient;
the zero browser-launch count is valid. MCP-v2 object normalization and OAuth/
session establishment therefore succeeded and are no longer the blocker. One
`tools/list` response reached the existing strict schema parser, which returned
before retaining the first ambiguous tool; the artifact has `schemas=[]`. The
exact ambiguity subtype is UNKNOWN and is not inferred. The observation is not
replayed, overwritten, or relabeled successful.

### L41R4 additive source boundary (in progress)

`L41R4_SCHEMA_CLASSIFICATION_DIAGNOSTIC` is the separately named additive
successor with evidence schema
`arch147-l41r4-schema-classification-observation/v1`. Its source checkpoint is
in progress and is not yet accepted or integrated. The candidate records
bounded sanitized structural fingerprints before inherited strict semantic
classification, including schema/description/interface hashes, hashed unknown
property inventories, required-not-in-properties facts, safe description
booleans, derived fractional precision/conflict data, and quantity/dollar-amount
facts. Root and per-field schema-keyword inventories retain known keyword names,
hash unknown names, and include inventory digests. It never records raw provider
descriptions, arbitrary defaults/unknown strings, credentials, token/callback
data, or authorization material.

The candidate may classify an optional logical string only when the field's
schema proves exactly one non-null primitive type: `type: ["string", "null"]`
(either order), or exactly two disjoint direct string/null branches in `anyOf`
or `oneOf` with safe annotation-only siblings. It records logical type
`string` and `nullable=true`; requiredness remains independent and comes from
the top-level required list. It does not resolve references. Multi-non-null
unions and unsupported field/root references, compositions, constraints, or
other schema shapes fail closed and clear any unproven logical-type/nullability
facts. Exact source acceptance remains pending.

Diagnostic classes in the candidate include required names absent from
properties; quantity and dollar-amount missing/invalid direct types, null-only
unions, multi-non-null unions, unresolved references, unsupported compositions
or constraints; top-level unresolved references, unsupported compositions or
constraints; invalid/conflicting fractional precision; malformed schema or
description data; and review-placement/place-nonplacement semantic conflicts.
These are sanitized classifications; an unsupported nullability remains
unknown rather than being reported as a fact.

The real L41R4 observation remains NOT RUN until ChatGPT independently accepts
and integrates the exact source and separately reviews that one-shot
observation. Q62 remains NOT RUN and blocked pending L41R4 classification; L43
and Q63 remain NOT RUN. No authority is granted for live readiness, broker
use, orders, numeric rules, or `FINAL_HOLDOUT`. For this L41R4 implementation
checkpoint, `PROTECTED_EFFECTS=0`; this describes implementation effects and
is not an additional counter from the consumed L41R3 observation. Its zero
prohibited tool invocations are recorded above. Source admission or source
publication does not grant operational authority.

## F856 accepted correction and integration closeout

The docs-descendant certification-reuse correction is SOURCE/CERTIFICATION
ACCEPTED and FAST-FORWARD INTEGRATED at
`f8566c030889847e6632c3a9cc4955778e5da802` / tree
`959f16bf383c63028a8a157dde93e285c9eeba8c`.

Feature run `42734478859`, attempt 1, is terminal SUCCESS. Source-static,
active-tests, distributed canonical FULL broad-1 through broad-7, and
source-gates succeeded. Shared certification-tests and the four-shard
full-tests fallback were skipped. Develop run `42740143581`, attempt 1, is
terminal SUCCESS with `DEVELOP_CERTIFICATION_REUSE=True`,
`REASON=exact_feature_certification`, and `DEVELOP_DUPLICATE_FULL=NO`. This was
exact-SHA feature-certification reuse; it does not claim the docs-descendant
path was exercised. The active docs-descendant contract is owned by
[Architecture 132](../architecture/132-tiered-certification-profiles.md) and
[the development workflow](../AI_DEVELOPMENT_WORKFLOW.md).

The prior develop run `42359807677`, attempt 1, remains immutable terminal
FAILURE evidence and was not rerun. The routing correction does not alter the
accepted L41R2 source or authorize a protected effect.

At the F856 closeout, Q61 native Windows synthetic UAT was ACCEPTED and the
accepted L41R2 source was `235118f70b7c7039055e9fea45ccf27df46671a0` / tree
`972004101036afe52642ed93c38fed21ea479956`. L41R2's observation was later
CONSUMED / BLOCKED / NO RETRY as `L41R2_SCHEMA_MALFORMED`. At that historical
checkpoint, L41R3 was the additive MCP-v2 successor and its real observation
had not yet run; its later consumed result is recorded at the top of this
ledger. Q62, L43, and Q63 were NOT RUN then. No live-readiness, broker, order,
numeric-rule, paper-soak, or `FINAL_HOLDOUT` authority was granted.

The next step at F856 closeout was independent exact-source review of the
additive L41R3 source after mapped feature CI. The later accepted disposition
and consumed observation are recorded in the current boundary above.

## L41R2 accepted source boundary and develop routing incident

The accepted L41R2 source boundary is
235118f70b7c7039055e9fea45ccf27df46671a0 / tree
972004101036afe52642ed93c38fed21ea479956. Feature mapped FULL run 42358983502,
attempt 1, was terminal SUCCESS. At that source-acceptance checkpoint, the real
observation was not yet run; it was later CONSUMED / BLOCKED / NO RETRY as
recorded below. Q62 was then NOT RUN and blocked pending L41R3 classification;
the current Q62 boundary is recorded at the top of this ledger.
No live-readiness, broker, or order authority follows from source acceptance.

The docs-only develop descendant was HEAD
068bd28036bfe3ab1252f484ad967eb0f9fca8f0 / tree
7bf0e3a9c1fd97db981f539510b716d2f212d7c1. Develop run 42359807677, attempt 1,
is preserved as terminal FAILURE. It reported CHANGE_MODE=FULL and
DEVELOP_CERTIFICATION_REUSE=False / provenance_not_proven. Exact classification:

    POST_ACCEPTANCE_INTEGRATION_ROUTING_DEFECT
    CI_ROUTING_OVERCERTIFICATION
    DEVELOP_CERTIFICATION_REUSE_DOCS_DESCENDANT_GAP

Source-static succeeded. The four-shard FULL fallback test execution passed
on shards 0, 1, and 2.
Shard 3's full-test verification also passed, but its hygiene enforcement
rejected 347.721 seconds against the 300-second ceiling. Thus full-tests (0),
(1), and (2) were SUCCESS; full-tests (3) was FAILURE solely at hygiene;
source-gates was FAILURE. The mapped canonical FULL and active-tests jobs were
skipped. The failed run is immutable and was not rerun. No provider or
protected effect occurred.

At the time of this preserved routing incident, the additive docs-descendant
reuse semantics were still proposed and the workflow correction was not yet
accepted or integrated. The later accepted disposition is recorded above. Q62
remains NOT RUN. This routing incident does not change or retry the accepted
L41R2 source.

The next published branch correction at that time was
`aa24ffd429ab94e5c7f7ff887dc9490ae308f315` / tree
`aefb298f32f35875e87a66b92cefce30e4f8bcf5`; mapped feature CI
`42730101493`, attempt 1, was terminal SUCCESS. Exact-source review accepted
the generic FULL collision-resolution portion but withheld overall acceptance
because the docs-descendant successor fixture asserted an obsolete monolithic
FULL job. That review did not integrate the source or run a protected effect,
L41R2 observation, Q62, L43 or Q63 action. Run `42730101493` was not rerun.
The later f856 successor aligned the proof with the real distributed topology
and was accepted/integrated as recorded above.

Accepted/integrated D34 source is HEAD
`b86defebf9ccbf1efb91397de8f2e66db24a6665`; tree
`9fa2360dfe7afdd902fd539e94f888063439785d`. Branch
`feature/robinhood-live-prototype-current`, canonical worktree
`F:\\AI\\worktrees\\ai-trading-bot-live-prototype-current`. Feature mapped FULL
`41969407894`, attempt 1, and develop source-gate `41973853073`, attempt 1,
succeeded; develop reused the exact feature certification. The first D34
publication `9981bf47072d35381a2e5b6f187c9497e9dbed5a` is the direct child of
accepted/integrated D33 source
`fad65c9f4eab5bc1de4e154fdf0f59e397bc943a` / tree
`beab205abcc045fad38625ff73bb48affea9a0e9`. Accepted D34 corrective source
`b86defebf9ccbf1efb91397de8f2e66db24a6665` is the direct child of
`9981bf47072d35381a2e5b6f187c9497e9dbed5a`.

D30 ACCEPTED: dataset `d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, SHA
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, basis
`ALPACA_ALL_ADJUSTED_PRICE_V1`. D31 exact bundle ACCEPTED: campaign
`9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, SHA
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, result
`NONE_QUALIFIES`, retained control `BASE_MA35_50_V1`, ID
`21158358-75be-5597-b940-5bccdda1429c`. D32 is ACCEPTED / CLOSED: strategy
math parity, research-binding integrity, and live data-basis parity PASS; the
2,516 comparisons had zero mismatches. The former `DATA_BASIS_MISMATCH` blocker
is closed. Alpaca all-adjusted current signal data and Robinhood
execution/custody remain separate providers with no fallback.

D33's real read-only attempt is CONSUMED / BLOCKED / NO RETRY. Evidence is
`F:\\AI\\temp\\arch147-d33-alpaca-observation-576b4b5c8f7b41548df7b822c44c74de\\evidence.json`,
SHA-256 `b767727712e4634950be8a6ba8f43522910d037987824ad33cb7c20c8eab95ec`,
1,999 bytes, observation `2026-11-04T23:59:08.218729Z`, credentials `1`,
provider requests `1`, selected sessions `60`, and zero prohibited-effect
counters. The exact provider rejection subtype is unavailable because D33
discarded it. The request end exceeded observation through end-of-calendar-day
semantics; this is a source-contract defect, not proof of the provider's exact
rejection cause.

D34 is an additive successor, not a D33 retry. It derives one exact published
regular close before credential/provider construction and uses that same cutoff
for the request and `CompletedSignalInputs`. The D33 CLI is retired; D34 uses
`trading_bot.live_prototype.alpaca_signal_recovery_operator` and evidence schema
`arch147-d34-alpaca-signal-observation/v1`. Implementation and tests are
source-only and perform no credentials, network, Alpaca, Robinhood, broker,
paper, live, campaign, runtime-binding, or FINAL_HOLDOUT effect.

The preserved D34 predecessor is
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` / tree
`a8d2b4fb4a40039b74768b44fd0198dc87bc55f3`; mapped run `41950572892`, attempt
1, was terminal SUCCESS, but exact-source review rejected it before develop
integration. Review found incomplete blocked-result attempt-count invariants
and an operator-level fallback that could fabricate zero credential/provider
counts after an escaped failure. No D34 real observation occurred. The current
corrective child changes only those accounting/evidence semantics and focused
tests/docs; the consumed D33 incident remains unchanged.

Published D33 predecessor, preserved but rejected by exact-source review before
integration:

    HEAD 2fd6d764e56226d7ef54c458f6f40b14af3b5b20
    TREE f44c9e3455b712572f8c6c022883eadb3ebd9c56
    PARENT b7d42863d24958d1ce0fcf9f51eff67397f94240
    GitHub run 41822221848 / attempt 1 / terminal SUCCESS
    classification EXACT_SOURCE_REVIEW_REJECTED

Current D34 corrective-child scope: attempt-accounting and evidence truthfulness
at the existing additive recovery source, with exact feature/develop admission
before provider authority, live origin branch heads resolved read-only through
the existing source-owned `_remote_branch_head` helper, one source-owned UTC
clock, exact published-close cutoff, and sanitized failure diagnostics. The
consumed D33 evidence and preserved D34 predecessor remain immutable and are
not replayed or relabeled.

The D34 implementation and tests used no credential, provider, network,
Robinhood, broker, paper, live, campaign, runtime-binding, or FINAL_HOLDOUT
effect. The accepted provider observation was a separate reviewed boundary
after publication, integration, mapped FULL, and exact-source acceptance; its
effect counters remained zero.

The accepted D34 observation is consumed successfully and is not replayable.
Evidence is
`F:\\AI\\temp\\arch147-d34-alpaca-observation-84d32fb2af5045e7a661a77259b690fb\\evidence.json`,
2800 bytes, SHA-256
`7c6f2d391cbb3141405e3252efcfcd94db18b8e81083d947d778310bfe49464b`, schema
`arch147-d34-alpaca-signal-observation/v1`, status READY, reason
`D34_ALPACA_SIGNAL_INPUTS_READY`, and observation timestamp
`2026-11-05T05:28:41.664723Z`. It recorded one credential read, one provider
call, and automatic retry FORBIDDEN. The one request ended at
`2026-11-04T21:00:00.000000Z`, the exact published XNYS regular close for the
last selected session. Response-body SHA-256 is
`296c9e89dd2f48d47b1ca3b071411d6e8509ca769fc92e433be19696bbf68c94`;
provider request-ID digest is
`6384000426f7d007ed9391b81bef6beb2ba40a5193cf94dd30a2a58fb63ae15f`; and
`CompletedSignalInputs` digest is
`8b6d4f88012da820890cb5070de975c1d02504aeb432939a2e954d9bf9dfecb0`.
All production, broker, runtime-binding, campaign, paper, live, and
`FINAL_HOLDOUT` effect counters are zero.

| Task | Dependencies | Owner / exclusive surface | Interface | Status / next |
|---|---|---|---|---|
| P00 | exact P6/CI | independent ChatGPT acceptance; Sol reverification | P6 59+1 | ACCEPTED; provider observation separate |
| P01 | P00 | Sol contracts, docs, registry, composition | v1 | IMPLEMENTATION/SOURCE ACCEPTED; integrated through 543dc6b4 |
| R09 | P01 | Luna external primary-source evidence | 3 fixed arms | SOL_REVIEWED |
| R10 | P01 | Luna comparison_v2.py + exact tests | R10 v1 | SOL_REVIEWED; 14 focused tests |
| R11 | R10 | Luna comparison_campaign_v2.py + exact tests | R11 v1 | SOL_REVIEWED; 49 focused tests |
| R12 | P01/R11 | Luna comparison_bundle_v2.py, research_comparison_service.py + tests | R12 v1 | SOL_REVIEWED; 17 focused tests |
| G20 | P01 | Luna prototype_dashboard/session_page.py + tests | cached DTO v1 | SOL_REVIEWED; 4 focused tests |
| G21 | P01/R12 | Luna prototype_research/strategy_page.py + tests | cached DTO v1 | SOL_REVIEWED; 5 focused tests |
| G22 | P01 | Luna prototype_activity_page.py + tests | cached DTO v1 | SOL_REVIEWED; 3 focused tests |
| D30 | selection/official data | Sol then Luna data/parity | accepted dataset identity | ACCEPTED; exact dataset and all-adjusted price basis frozen |
| D31 | selection/official data | Sol then Luna data/parity | exact research bundle | ACCEPTED; `NONE_QUALIFIES`, control retained, non-live |
| D32 | selection/official data | Sol then Luna data/parity | parity evidence | ACCEPTED / CLOSED; math, binding, and live data-basis parity PASS |
| D33 | consumed predecessor incident | preserved immutable evidence | one Alpaca all-adjusted observation | CONSUMED / BLOCKED / NO RETRY |
| D34 | consumed-D33 recovery successor | Sol source/operator, exact review | Alpaca all-adjusted 60-session inputs with published-close cutoff | ACCEPTED / INTEGRATED; READY observation CONSUMED SUCCESSFULLY / NO RETRY |
| L40 | accepted D34 closeout | Sol contract/composition; Luna capability/ownership audit | pure effect-disabled contract | ACCEPTED / INTEGRATED at `14e1b628c0c51c27b23deabee56eb91859818529` |
| L41 | accepted/integrated L40 | Luna source-owned observer and fake tests | exact two-read capability evidence | Observation CONSUMED / NO RETRY; selected account, SPY tradability and fractional tradability PROVEN; all mutation counters zero; post-read teardown failed with subtype unavailable; official/interface facts remain unresolved |
| L41R1 | consumed L41 observation | source correction and separately reviewed observation | teardown and rule-binding discovery | CONSUMED / BLOCKED / NO RETRY; exact session-open failure preserved; no retry |
| L41R2 | consumed L41R1 observation | additive interactive schema-discovery successor | metadata-only `tools/list`; one reviewed browser authorization at most | SOURCE ACCEPTED at `235118f70b7c7039055e9fea45ccf27df46671a0` / `972004101036afe52642ed93c38fed21ea479956`; real observation CONSUMED / BLOCKED / NO RETRY as `L41R2_SCHEMA_MALFORMED` |
| L41R3 | consumed L41R2 observation | additive MCP-v2 schema-discovery successor | normalized metadata-only `tools/list`; one reviewed browser authorization at most | SOURCE ACCEPTED / INTEGRATED at `4461ea7f09c396c3c49598debbc588754fa5096c` / `68cbfb70ea3eaa6f52a342e967d682ca5ab84bd2`; feature `42778436739` and develop `42780649228` SUCCESS; real observation CONSUMED / BLOCKED / NO RETRY as `L41R3_SCHEMA_AMBIGUOUS` |
| L41R4 | consumed L41R3 observation | additive schema-classification diagnostic successor | bounded sanitized structural diagnosis; metadata-only `tools/list`; no MCP tool invocation | Source checkpoint in progress from accepted L41R3 base; exact source not yet accepted/integrated; real observation NOT RUN pending ChatGPT source acceptance/integration and separate observation review |
| L42/I53 | consumed L41 capability boundary | durable state/controller, runtime signal, disarmed service/GUI | consolidated effect-disabled source | ACCEPTED / INTEGRATED at `0b9f3ac25158b11c5daa327ed8ca732c05adb78b`; feature FULL `42201682850` SUCCESS; develop `42285116586` SUCCESS with exact certification reuse |
| I50-I52 | GUI/service convergence | Sol composition, Luna scenarios/docs | synthetic-only v1 | Synthetic I50/I51 and bounded I52 SOL_REVIEWED; full live scenarios/I53 deferred |
| Q60 | exact source | Sol admission/publication/FULL | registered source-only | D34 implementation/corrections/docs integrated at `b86defe`; mapped feature FULL and develop reuse passed |
| Q61 | accepted/integrated L42/I53 source | Human native Windows UAT | isolated synthetic | ACCEPTED; five pages, resize/navigation, synthetic safety boundary, Start/Stop/restart and clean close verified; both launches exited 0; protected effects 0 |
| Q62 | accepted source/data/exit | Operator protected readiness | independent runner | NOT RUN; blocked pending L41R4 classification; live readiness not granted |
| Q63 | all required evidence | Sol exact delivery | guarded test package | NOT RUN; source assembler preserves identities and leaves future evidence slots unfilled |

| Acceptance requirement | Status | Evidence / limitation |
|---|---|---|
| Usable launcher and GUI | PASS / Q61 ACCEPTED | Five native Windows pages opened successfully; resize/navigation and clean process exit verified |
| Reproducible explicit selection | SYNTHETIC PASS / OFFLINE NOT RUN | 144-cell synthetic topology, frozen policy and strict bundle; real admitted data separate |
| Research/runtime parity | D32 ACCEPTED / CLOSED | strategy math, research binding, and current data-basis parity PASS |
| Current valid inputs | ACCEPTED / CONSUMED | D34 READY observation accepted; one credential read and one provider call; no retry |
| Entry and exact owned exit | BLOCKED | L41 proved account identity, SPY tradability and fractional tradability for one observation; official/interface quantity, minimum, notional and residual-close rules remain unresolved pending accepted binding/schema discovery |
| Durable limits/no duplicate effects | SOURCE-TESTED / EFFECT-DISABLED | Hash-chained durable state/controller covers flat baseline, full reservation, exact order binding, monotone fills, partial ownership, UNKNOWN/no-retry, and crash write/flush/fsync/close seams; no provider invocation |
| Stop/kill/restart/reconnect | SYNTHETIC NATIVE PASS / REAL DISARMED SOURCE-TESTED | Q61 recorded two complete synthetic RUNNING -> STOPPING -> STOPPED cycles and a clean close; real/disarmed recovery remains source-tested |
| Credential/state isolation | PASS / Q61 | Two fresh external F: synthetic state roots; no credential/provider construction or protected effect |
| Exact source certified | L42/I53 baseline and L41R3 observer add-on ACCEPTED / INTEGRATED | Latest observer source HEAD `4461ea7f09c396c3c49598debbc588754fa5096c` / tree `68cbfb70ea3eaa6f52a342e967d682ca5ab84bd2`; feature `42778436739`, develop `42780649228` with exact feature certification reuse |
| Bounded live test ready | BLOCKED | no live effect authorization |

### L41R1 consumed record and L41R2 successor

The consumed L41R1 result is immutable and recorded as
`L41R1_REAL_OBSERVATION=CONSUMED_BLOCKED_NO_RETRY`. Its evidence path is
`F:\\AI\\temp\\arch147-l41r1-schema-observation-f5b81e5f60dc40c280f53007d1db2b52\\evidence.json`;
SHA-256 is
`2b62f54076fdfd34aa3eb799ed563701f8eadafe8877b25590f88fe72147160f`,
length `1130` bytes. Source admission passed. OAuth scope-entry attempts were
`1`, MCP session-open attempts were `1`, `tools/list` attempts were `0`, and
schemas were empty. MCP tool invocation, account, tradability, position, order,
portfolio, quote, review, placement, cancellation and other-tool counters were
all `0`. The fixed reason was `L41R1_MCP_SESSION_OPEN_FAILED`.

The source-contract root cause was `_create_windows_oauth_factory()` installing
`_forbid_interactive_oauth`; the MCP OAuth SDK required an authorization-code
flow and invoked that blocker. The exact classification is
`L41R1_INTERACTIVE_OAUTH_FORBIDDEN`, not a generic browser/environment failure.
The consumed attempt also exposed an upstream OAuth/MCP traceback-output defect:
sanitized evidence did not suppress traceback output reaching the terminal.

`L41R2_INTERACTIVE_SCHEMA_DISCOVERY` is the additive successor with evidence
schema `arch147-l41r2-interactive-interface-observation/v1`. Its source-only
boundary retains the corrected quantity/review/placement schema semantics,
permits at most one reviewed interactive browser authorization, suppresses
upstream provider/OAuth stdout, stderr, logging, warnings and native FD 1/2
output, and invokes only bounded `tools/list`. Native credential reads and
writes are SDK-managed and individually uncounted (`null`/`null`, marker
`SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`). A successful result is
`CAPTURED_FOR_REVIEW` only. L41R2 was later CONSUMED / BLOCKED / NO RETRY as
recorded below. At that historical checkpoint, Q62 was NOT RUN and blocked
pending L41R3 classification; the current Q62 boundary is recorded above. No
live readiness, broker authority or order authority is granted.

L41R2 is CONSUMED / BLOCKED / NO RETRY with reason
`L41R2_SCHEMA_MALFORMED`. Preserved evidence:
`F:\\AI\\temp\\arch147-l41r2-schema-observation-9a504f5e26b9414998cea287ee13936a\\evidence.json`,
SHA-256 `66C3E5C32A0FD575490B3219AEA7DE2ECCEE65C4E5FDEFF6EB339B9B963FA751`,
length `1386` bytes. Source HEAD/tree were
`d421562703d6bae92b14afdcc1b3defcc595dbc8` /
`b0ca242360b1cfe17222c4b56e95198219eee4be`; FEATURE and PROSPECTIVE_DEVELOP
admission passed. It recorded one OAuth scope entry, one MCP session-open,
one browser launch, and one `tools/list` attempt. All MCP tool invocation,
account, tradability, position, order, portfolio, quote, review, place, cancel
and other-tool counters are zero. Native credential read/write counts are
`null` with accounting `SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`; automatic retry
is FORBIDDEN.

The root cause is classified by comparing source extraction with the MCP SDK
v2 Python object model: the source reads `inputSchema`, while Tool objects
expose `input_schema`; `inputSchema` remains the wire spelling. The consumed
evidence does not record the raw provider object type. L41R3 uses the distinct
evidence identity `arch147-l41r3-mcp-v2-interface-observation/v1` and
normalizes only name, description, schema and pagination cursor before the
existing fail-closed sanitized parser. It accepts v2 object `input_schema`,
wire/mapping `inputSchema`, and retained legacy object `inputSchema`. Success
is `CAPTURED_FOR_REVIEW` only; no Q62 readiness, numeric-rule, broker/order,
live, or `FINAL_HOLDOUT` authority follows. At the L41R2 source-acceptance
checkpoint, real L41R3 had not yet run; its later consumed observation is
recorded at the top of this ledger.

The first unpublished L41R2 prepublication admission is preserved at
`F:\\AI\\temp\\arch147-l41r2-source-admission-2804bb15b8ec49eab4f0ac8ac0fe0a0f` and is classified
`PREPUBLICATION_ADMISSION_TOPOLOGY_DEFECT` / `FULL_LANE_DUPLICATE_BASENAME`.
The newly enlarged FULL inventory placed
`tests/portfolio/test_models.py` and `tests/rebalancing/test_models.py` in
broad-5, yielding `40 != 39` unique basenames under the current top-level
pytest import topology. The admission had no authority failure,
`IDENTITY_STABLE=True`, and `PROTECTED_EFFECTS=0`; it was not a product-source
failure, published red source, coverage defect, or GitHub CI failure. A fresh
admission subsequently passed; the amended candidate was published as
`235118f70b7c7039055e9fea45ccf27df46671a0` / tree
`972004101036afe52642ed93c38fed21ea479956`, mapped FULL
`42358983502` attempt 1 was terminal SUCCESS, and independent exact-source
review accepted it. At that source-acceptance checkpoint the observation had
not yet run; it was subsequently consumed as recorded above and does not
advance Q62.

Live-readiness labels are NOT GRANTED. This ledger records progress, not trade authority.

### Q61 native Windows UAT accepted evidence

Q61 ran against exact accepted/integrated source
`0b9f3ac25158b11c5daa327ed8ca732c05adb78b` / tree
`f13c2c169dbc5e24e709340b827016e493a041b2`. The initial fresh synthetic state
root was
`F:\AI\temp\arch147-q61-native-uat-4fb827c7f9eb4f5a959f2b1583149f84`;
the native process exited 0 after the five pages, resize/navigation and
synthetic safety boundary were inspected. The bounded lifecycle continuation
used
`F:\AI\temp\arch147-q61-native-lifecycle-3d927a618e20423e8bdfd89d6510c209`
and also exited 0. Activity / Health recorded two complete
`RUNNING -> STOPPING -> STOPPED` cycles, proving Start/Stop and restart; the
requested final close sequence terminated cleanly. No live/provider/order
control appeared, no credential or provider activity was observed, and
`Q61_PROTECTED_EFFECTS=0`. Q61 establishes native prototype usability only;
it does not establish L41R2, Q62, L43, Q63 or live readiness. L41R1 is a
consumed blocked predecessor and was not retried.

## Focused verification and review record

The D34 implementation was one source-only checkpoint. R10/R11/R12 and all five GUI
pages were reviewed at their actual source interfaces. Qualification has one
canonical owner; the GUI adapter imports it. The five qualification metrics are
the continuous-symbol count, minimum/median continuous return, worst continuous
drawdown and median turnover; annual-regime metrics remain evidence only.
Turnover is the stress annual median, return the continuous median and drawdown
the continuous worst case. Research data identity is not mislabeled as an
artifact SHA256. Complete campaigns still contain 144 cells; an explicit
bounded failed/incomplete challenger remains visible without fabricated cells
or metrics and carries only its fixed sanitized status code.

| Focused set | Result |
|---|---|
| CI routing + certification profile tests | 848 passed |
| R10 candidate primitives | 14 passed |
| R11 replay/selection | 49 passed |
| R12 bundle/presentation | 17 passed |
| Final GUI/service/registration convergence | 56 passed; one label assertion fixed and its exact test passed |
| Whole-repository Ruff check and format check | PASS; 1535 files formatted |
| Current authority and source-only prototype authority | PASS, zero failures |
| Git diff whitespace | PASS |
| D34 corrective-child focused tests/checks | PASS locally | 62 D34 input/operator tests; no P6 source changed |

The accepted D34 observation closes the D32 live data-basis leg without changing
the retained `BASE_MA35_50_V1` control or D31's `NONE_QUALIFIES` result. The
observed BUY/HOLD outputs are signal outputs only and grant no live eligibility,
order authority, exit capability, or durable budget readiness. Q61 native Windows synthetic UAT is now ACCEPTED; no paper soak
is inserted and `FINAL_HOLDOUT` remains sealed.

Precommit current/historical batch evaluation reported only task files that were
still being written; all now exist. The D34 candidate then passed clean-candidate
FEATURE and PROSPECTIVE_DEVELOP admission, one ordinary publication push, and
one terminal mapped GitHub FULL result. No local FULL/LEGACY/EXHAUSTIVE was run.

Offscreen layouts were rendered at 1366x768 and 1920x1080 under the external F:
prototype-ui artifact directory. Headless Qt exposes no fonts by default, so
visual QA explicitly loaded the existing Windows Segoe UI font. This is source
layout evidence, not native DPI/keyboard/operational acceptance.

Both bounded current coordination documents and README were reviewed and updated.
Historical/P6 source and consumed evidence were not changed. Automatic review
initially rejected shared registration; the user explicitly approved the exact
review patch and focused fixes before it was applied. No gate bypass occurred.
At that prototype publication, the L40 exit-notional/price-movement ambiguity
was recorded without delegating live implementation. The current L40 proposal
below resolves local mechanical semantics; actual exit capability remains open.

## L42/I53 accepted source and Q61 boundary at that checkpoint

The L42/I53 source is ACCEPTED / INTEGRATED at
`0b9f3ac25158b11c5daa327ed8ca732c05adb78b` / tree
`f13c2c169dbc5e24e709340b827016e493a041b2`; feature FULL `42201682850` and
develop reuse run `42285116586` are terminal SUCCESS. `PROTOTYPE_READY_FOR_NATIVE_TESTING=YES`
and Q61 is ACCEPTED. The new L42/I53 source and recovery/Q62 modules perform
typed, fail-closed evaluation against exact source/config/account/session
identity, fresh evidence windows, L41 capability, clean ownership and budget,
all-adjusted signal inputs, and read-only recovery. Q63 assembles supplied
accepted identities while preserving the consumed L41R1 result, the unrun
L41R2/Q62/L43/Q63 boundaries, and Q61's native evidence as separately owned
evidence. The emergency-exit operator has no provider dispatch surface and
remains `DISARMED`.

The consumed L41 observation proved account identity and SPY account/fractional
tradability. Production, broker, order, paper, live, and runtime-binding
mutation counters were zero. Post-read teardown failed, but its subtype is
unavailable. Official/interface facts remain unresolved pending accepted
binding/schema discovery. Source tests do not repeat that observation or count
as Q61/Q62/L43/Q63 evidence. No live-readiness label or broker authority is
granted.

The source-only implementation includes the strict consumed-evidence parser and
official-rule binding, truthful L41 teardown accounting, the consumed L41R1
operator and additive L41R2 interactive tools/list-only successor,
`durable_state.py`/`live_controller.py`, the reusable runtime
Alpaca signal provider, the explicit synthetic/REAL_DISARMED application service
and five-page GUI composition, plus `readiness_contracts.py`,
`readiness_operator.py`, `recovery_operator.py`, `emergency_operator.py`, and
`delivery_operator.py`. Matching focused tests remain fake-only; evidence
envelopes validate typed identities and validity windows but do not authenticate
caller-supplied references. Q61 native synthetic UAT was executed and accepted;
no L41R2/Q62/L43/Q63 observation was executed, and L41R1 was not retried.

### Preserved latest L42 publication red evidence

The parent L42 source publication is preserved as immutable mapped FULL
evidence:

    HEAD 50ab0d6c98439021a0a1c6e1baf6397785208e39
    TREE 22cbe250ff82923dfb924aa2816cc9782fbe12bd
    GitHub run 42195430203 / attempt 1 / terminal FAILURE
    classification PREPUBLICATION_COVERAGE_DEFECT
    manifestations L41R1_TEST_ROOT_SEAM_DEFECT,
                   FULL_PYTEST_MODULE_NAME_COLLISION
    source-review defect L41R1_SCHEMA_FACT_MODEL_MISMATCH

The exact job conclusions were: `source-static=SUCCESS`; `active-tests=FAILURE`
with 17 L41R1 fake-path failures; `broad-1=SUCCESS`; `broad-2=SUCCESS`;
`broad-3=FAILURE` from a pytest collection error; `broad-4=FAILURE` with the
same 17 L41R1 failures; `broad-5=SUCCESS`; `broad-6=SUCCESS`;
`broad-7=SUCCESS`; and `source-gates=FAILURE`. The broad-3 collection error
paired `tests/desktop_live/test_configuration.py` with
`tests/live_prototype/test_configuration.py`; independent inspection found
the second same-lane collision between `tests/domain/test_proposals.py` and
`tests/rebalancing/test_proposals.py`. Hosted Windows correctly exposed the
fake-test root seam while the real production evidence policy remained hard-F
and fail-closed. The red run is preserved and is not retry authority. No real
L41R1 observation, provider call, credential read, or protected effect occurred.
At the time of that run, L41 remained unaccepted and unintegrated, and Phase 2
was blocked behind corrected terminal-green mapped L41 CI.

### Consumed L41 evidence record

The preserved artifact was read once at startup and never replayed:
`F:\\AI\\temp\\arch147-l41-capability-observation-c0f29dfb1fb544d8b330910ad41af1f6\\evidence.json`.
SHA-256 is
`c85ba6d18bf1a3f234d7055dbe564fb7e2df4e1db8cc0f9f16c6b19e0d695c0c`; byte
length is `4114`. Exact parsed envelope fields were schema
`arch147-l41-capability-observation/v1`, root/report status `BLOCKED`, reason
`L41_OBSERVATION_FAILED`; branch
`feature/robinhood-live-prototype-current`; HEAD/tree and both origin
feature/develop HEAD/tree `8ebbbcbf44fcba0e041601a332bc6029692ef396` /
`eaf7ee6cd82ed895632725ac682123f3ab8e2ab2`; feature and prospective-develop
authority `PASS`; account fingerprint
`f377529245bd1682f382d17b22ac8d55362f7138a4f7fc307593c16847e551cf`, account
type `individual`; OAuth scope 1, MCP open 1, `get_accounts` 1,
`get_equity_tradability` 1, collector invocation 1 with one collector read of
each; native credential read `null` with SDK-managed accounting; other,
review, place and cancel attempts 0. The 13 facts were retained in source order:
the first three PROVEN (`INTENDED_AGENTIC_ACCOUNT`, `SPY_TRADABILITY`,
`FRACTIONAL_ELIGIBILITY`), nine `BLOCKING_L42` interface/rule facts, and
`INSTANCE_REVIEW_REQUIRES_POSITION=DEFER_TO_FIRST_OWNED_POSITION`. The incident
classification is `L41_REAL_OBSERVATION=CONSUMED_BLOCKED_NO_RETRY`,
`L41_ACCOUNT_FACTS_CAPTURED=YES`, `L41_MUTATION_EFFECTS=0`,
`L41_POST_READ_TEARDOWN_FAILURE=YES`; the exact teardown subtype is unavailable
and is not inferred. Official/interface facts remain unresolved until trusted
binding and future schema discovery.

Run `42359807677` remains preserved and was not rerun. At this earlier L41
observation checkpoint, Q62 readiness remained NOT RUN and blocked pending
L41R3 classification; the later consumed result and current next boundary are
recorded at the top of this ledger. L43 and Q63 remain separate future
boundaries. Do not invoke D33,
D34, consumed L41, or L41R1 again; no paper soak is inserted and FINAL_HOLDOUT
remains sealed.

## L40 focused implementation record

Implementation base: canonical D34 closeout `f7f13f805ad6a0eea7041cb6d13c561149a13f6e`,
tree `4cf5d8fd19a8089103e9f119e4d8d338a08819d0`. Seven Luna audit/design
assignments mapped authority, capability, ownership, recovery, runtime/application,
adversarial testing and Windows delivery. The orchestrator independently reviewed
and composed the source/tests/docs; subagents did not stage, commit or publish.

The pure L40 owner and tests add no credential, provider, broker, persistence,
controller, live composition or protected dispatch. It rejects unknown capability,
including an omitted maximum unless evidence explicitly records no maximum;
zero/conflicting maximum rules block. Synthetic evidence references authenticate
nothing and cannot grant external effect authority. Actual fill dollars above the
reserved request remain truthful and do not by themselves prevent reducing exit.

Combined affected verification passed: **179 tests**, using the exact command:

```powershell
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider tests/live_prototype tests/runtime/checkpoint_runner/test_arch147_prototype.py --basetemp 'F:\AI\temp\arch147-l40-focused-4d51948040ba49fa8f2d7c31a84e7b93\pytest' --junitxml 'F:\AI\temp\arch147-l40-focused-4d51948040ba49fa8f2d7c31a84e7b93\junit.xml'
```

That command records the completed attempt, not a reusable evidence destination.
Any justified later attempt requires a fresh unique external directory. Focused
Ruff check/format covered both new Python files and checkpoint_runner.py; both
passed. `git diff --check` and current authority returned zero failures. General
clean-candidate admission, exact publication and mapped terminal FULL remain the
subsequent source gates; this record does not claim them before they occur.
No local FULL, manual workflow dispatch or provider/native UAT was run.

L40 recorded the L41 collector deferral at that checkpoint. L41 now supplies the
source-owned collector/operator while preserving downstream source/evidence
ownership. This record does not accept or integrate L41 and does not claim a real
observation or readiness result.

## L41 source-only observer implementation

L41 adds the typed 13-fact inventory (`INTENDED_AGENTIC_ACCOUNT`,
`SPY_TRADABILITY`, `FRACTIONAL_ELIGIBILITY`, `SELL_QUANTITY_FIELD`,
`DECIMAL_INTERFACE_PRECISION`, `QUANTITY_INCREMENT`, `MINIMUM_QUANTITY`,
`MAXIMUM_QUANTITY_OR_ABSENCE`, `MINIMUM_SELL_NOTIONAL_OR_ABSENCE`,
`BELOW_MINIMUM_FULL_CLOSE`, `RESIDUAL_FULL_OWNED_CLOSE`, `REVIEW_PREVIEW_ONLY`,
`INSTANCE_REVIEW_REQUIRES_POSITION`), a pure fail-closed classifier,
an injectable two-method collector, a restricted one-session MCP transport, and
the source-owned `python -m trading_bot.live_prototype.capability_operator`
command. The collector resolves the intended Agentic account, observes SPY
tradability with an account-bound `get_equity_tradability` call, and never
retains the raw account number in its report. Its interface is limited to one
`get_accounts` call and one such SPY read. No other tool, review, position,
portfolio, quote, order or cancellation call is exposed. Tests use fakes only;
no real OAuth, credential-store or provider call occurred for this source.

Before a future real invocation, the operator requires the exact clean canonical
feature checkout, matching live feature and develop heads/trees, and both
FEATURE and PROSPECTIVE_DEVELOP results from the existing evaluator under
`arch147-live-prototype`. The operator opens one source-owned OAuth
initialization scope and one MCP session only after that admission. Windows OAuth
storage may make multiple SDK-managed native credential-store reads; their
count is unknown and evidence reports `native_credential_read_count: null`.
Evidence is fresh, external, create-only F: JSON with source identities, the
13 fact classifications and truthful attempt counters. Account identifiers,
secrets, provider text and raw exception text are excluded.

`PROVEN`, `BLOCKING_L42`, and `DEFER_TO_FIRST_OWNED_POSITION` are the only fact
classifications. Only the position-specific review requirement may be deferred.
Schema fields establish interface shape, not official numeric rules or account
eligibility. Rule metadata and a content digest are provenance references, not
authentication; official-rule-dependent facts remain `BLOCKING_L42` without a
separately accepted source-owned trust binding. Overall readiness is
`READY_FOR_L42`, `BLOCKED`, or `NOT_RUN`; `READY_FOR_L42` would not authorize a
trade. At the time of this source-only implementation record, L41 had not been
independently accepted or integrated and no real observation had been run. The
later consumed observation is recorded in the current boundary above; its facts
do not revise the immutable failed CI attempts that follow.

The first L41 publication is preserved as immutable red evidence:

    HEAD f9c56373aed845b901d1d623b1c22f83cff2d627
    TREE f7f41a547ff29ef0bc4a63992243193d74b3a3ef
    GitHub run 42113135495 / attempt 1 / terminal FAILURE
    classification PREPUBLICATION_COVERAGE_DEFECT

Source-static and active-tests passed. The mapped FULL failure was limited to
hosted-Windows fake operator tests deriving evidence destinations from pytest
`tmp_path`; the hosted runner's `D:` temporary root was correctly rejected by
the unchanged production `F:\AI\temp` evidence policy before fake composition
could execute. The same publication also exposed that the existing
`ARCH147_PROTOTYPE_TESTS` inventory omitted the five L41 capability test
modules. The red run is preserved and is not retry authority. At that point L41
remained unaccepted and unintegrated, no real observer had been run, and Phase 2
remained blocked behind corrected terminal-green mapped L41 CI.

The first corrective L41 publication is preserved as a second immutable red
record:

    HEAD 934866d248d5ede8c8d4172583f649d5d6fc3360
    TREE 842d12b2264c95471517ee568ea9e3ed7c8e1faf
    GitHub run 42171503288 / attempt 1 / terminal FAILURE
    classification PREPUBLICATION_COVERAGE_DEFECT

Source-static passed, and active-tests executed all five L41 capability
modules. Active-tests failed only three direct source-admission tests. FULL
broad-1, broad-2, broad-4, broad-5 and broad-6 passed; broad-3 had two
failures and broad-7 had one failure. The failures were the same hosted-
Windows test seam: direct admission tests reached the unchanged production
hard-F canonical-root gate before their intended fake Git and authority
semantics. Both red runs remain preserved and are not retry authority. L41
remains unaccepted and unintegrated, no real observer was run, and Phase 2
remains blocked.

## Preserved rejected publication and accepted corrections

The first prototype publication is permanently preserved:

    HEAD 01adf7f0808970576b263f158d2dd121b216d733
    TREE bd0fb74dacbd22aa832d991c0876fd14ad478789
    GitHub run 41788777182 / attempt 1 / terminal FAILURE

Source-static and active-tests passed. FULL broad-1/2/4/5/6/7 passed; broad-3
failed 2 of 2560 tests, with 2558 passed and no skips/errors. Both failures
reproduced on that unchanged source in 0.44 seconds:

- `test_core.py::test_registered_profiles_include_current_arch128_gates` omitted
  `arch147-live-prototype` from the exact current registry inventory.
- `test_core.py::test_r2b_common_and_family_requirements_are_independently_selectable`
  lacked a prototype family expectation; the prototype selection omitted the
  established `COMMON_TESTS` contract.

The recorded general admission executed source-authority, CI, profile/lane,
readonly-diagnostic, strategy-compatibility and certification result/source tests,
but not `test_core.py`. Classification: `PREPUBLICATION_COVERAGE_DEFECT`. Work
stopped for independent review; the user then explicitly authorized this bounded
current runner/admission/test-topology correction. The red run is not retried and
its commit is not amended, rebased or rewritten.

Corrective scope is limited to prototype COMMON_TESTS membership, mandatory
infrastructure coherence coverage of `test_core.py`, exact current inventory and
family expectations, an independent literal coverage regression, and current
workflow/coordination documentation. Product/research/GUI/P6/provider/credential/
execution/ownership/kill/data/holdout semantics remain unchanged. No protected
or operational action, paper soak, or further prototype delegation is included.

The prepublication plan required the affected runner/authority/certification and
coherence coverage, whole-repository Ruff/diff checks, clean-candidate FEATURE and
PROSPECTIVE_DEVELOP admission, one ordinary correction push and one mapped FULL;
it prohibited a local canonical FULL and unchanged reruns.

The correction's initial ten-module focused run passed 1435 tests and exposed
one further assertion in the formerly short-circuited inventory test: the
prototype Ruff tuple must contain `scripts/checkpoint_runner.py`. That same
current inventory test also needs the explicit prototype branch expectation.
Both were corrected within the runner/test contract; the exact failing test
then passed (1 passed). No product source changed. The newly added regression
also rejected a process-local removal of `test_core.py` from the coherence tuple.
The restored tuple was verified afterward; no source mutation was used for that
probe. Final current authority, whole-repository Ruff check/format (1535 files)
and whitespace checks passed before the ordinary correction candidate.

The registry/admission correction completed at `1f2f42b` / tree
`87a4eb9e27ee1b5a209eda93ad198f650abbfed3`, with GitHub run `41792913721`,
attempt 1, terminal SUCCESS. The frozen-P01 semantic correction then completed
at `3218931` / tree `96784106879285736ee412e887319b48f2c64281`, with GitHub run
`41799106223`, attempt 1, terminal SUCCESS across source-static, active-tests and
broad-1 through broad-7. Independent review accepted the implementation/source
semantics, and those P01 corrections/docs were later integrated through
`b7d42863d24958d1ce0fcf9f51eff67397f94240`. The D33 predecessor above remains
historical terminal-green evidence and must never be mistaken for the current
corrective child.
