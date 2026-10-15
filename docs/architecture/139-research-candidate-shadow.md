# Architecture 139 — exact variant binding and deterministic SHADOW evidence

Status: **Architecture 139-B / RCL-3B SOURCE ACCEPTED**. 139-A remains accepted at HEAD `bf500ffecefe0a8be8117e315228e3bc07ffdf54`, TREE `69d4ee1d6e7b3c2ca095b3ddf3cf05fdb7e3babd`, CI #562 / `38640090298`. 139-B1 is accepted at HEAD `3bf604f407445da0c587cfd91545c113c99e341f`, TREE `732f75cc09c8296ce09f244edc36ca8bda61e7b7`, CI #563 / `38664134287`. 139-B2 is accepted at HEAD `bf98553592d2ef740d6a6ffdc104c6cd28023379`, TREE `34627f90f3ad8fc441346cc3d567a3f15495219b`, CI #564 / `38665480838`.

## Acceptance evidence

The current-lineage forward-port is accepted on the exact source above.
Checkpoint Source Gates #562 / `38640090298` completed SUCCESS in one
workflow_dispatch attempt. source-static passed 64 current authorities with 88
test paths and 372 Ruff paths; git diff, Ruff check and Ruff format passed. The
four broad shards completed in 90.389 / 98.647 / 104.755 / 121.06 seconds, all
below the 300-second hygiene ceiling.

The binding module, its 857-line focused test and the package export surface are
byte-for-byte identical to the historically accepted 139-A blobs. The
current-lineage delta is limited to live inventory assertions and the exact
seven-test 139-A successor overlay after Architecture 138. All seven declared
successor blobs independently match GitHub. Frozen predecessor dictionaries,
executable/native/AST pins, ACTIVE membership/digest, D1R5 source/registration
and workflow bytes remain unchanged. Focused verification records 1,808
distinct passing cases. All recorded operational effect counters are zero.

## Frozen contract and current source admission

139-A establishes exact research-candidate variant provenance only. It replays
the already SOURCE ACCEPTED historical checkpoint unchanged, without redesign,
merge, rebase or cherry-pick of the stale research branch.

Current branch: `feature/research-candidate-shadow-variant-binding-current`.
Worktree: `F:\AI\worktrees\ai-trading-bot-research-candidate-shadow-variant-binding-current`.
Exact base HEAD `69bf101556a62788b9dd9a1ce82c706c9c977c44`, TREE
`a1b566d8642a06553caa3bb029c81d7ece5541d2` is the bounded Architecture-138
docs-closeout descendant. Accepted 138 executable/test identity remains HEAD
`a9c3682231f8540be6e9dc6f2bfecd06ecf1a8b1`, TREE
`55841f5119228dbf302747256326d43ff7d32e23`, CI #561 / `38634855492` SUCCESS.

Historical accepted 139-A reference: HEAD
`e730b3b05c0c78181a4b3ff6b8e257cb04f3ff15`, TREE
`ea13572c565bcfe65959014bf1c98572c89cc3a7`, CI #517 / `38387248166` SUCCESS.
Its accepted parent was `1af8150c9985f5dc7ad1e143a16d90dcdc86be1a`.
That acceptance is reference evidence; this forward-port requires its own
terminal source gate and exact-source review.

The replay retains these exact accepted Git blobs:

| Path | Blob |
| --- | --- |
| src/trading_bot/experiments/research_candidate_shadow_binding.py | ff1f76c5309ab8ed2e2e48d487365600633b1c0d |
| tests/experiments/test_research_candidate_shadow_binding.py | 0b78cd52d555077f98009720157f230fed9cebd3 |
| src/trading_bot/experiments/__init__.py | a323ce06abaf665ddc1a4b1e6ac9566b36739fce |

The current package initializer matches the historical accepted parent before
exports are replayed. Architecture-137/138 source/test blobs, schemas,
namespaces, framed identities, builders, verifiers and canonical bytes remain
unchanged. Neither prior parser admits SHADOW.

## Binding artifact and exact identity

`ResearchCandidateShadowVariantBinding` is frozen/slotted and inert. Schema:
`research-candidate-shadow-variant-binding/v1`. UUID5 namespace:
`0521440a-535c-4ebc-baa4-b071db744593`. Version:
`research-candidate-shadow-variant-binding-identity/v1`.

The exact ordered identity material is:

```text
research-candidate-shadow-variant-binding-identity/v1
schema
str(walk_forward_passed_candidate_id)
str(predecessor_candidate_id)
str(qualification_id)
candidate_source_head
candidate_source_tree
qualification_source_head
qualification_source_tree
binding_source_head
binding_source_tree
str(report_id)
str(experiment_request_id)
str(experiment_result_id)
str(historical_fingerprint)
str(schedule_fingerprint)
str(initial_state_fingerprint)
str(variant_id)
str(caller_ordinal)
variant_name
"none" if rank is None else str(rank)
str(experiment_run_id)
str(rolling_result_id)
```

Frame each string as `<UTF-8 byte length>:<value>`, concatenate, then UUID5.
Every retained semantic field participates; binding_id is the derived result.
No serialized bytes, paths, clocks, Python hashes, locale, random UUIDs, provider
state, ambient mutable state or object addresses participate. Copy memo addresses
preserve shared retained links during defensive validation only.

IDs must be exact UUIDs. All six source HEAD/TREE fields are exact lowercase
40-hex. Ordinal, name and rank retain accepted 137 bounds: exact int ordinal in
0..1,000,000; stripped nonblank UTF-8 name of at most 256 characters; rank exact
positive int in 1..1,000,000 or null. Bool never substitutes for int. Rank remains
report evidence and never grants execution authority.

## Complete external-chain builder and verifier

`build_research_candidate_shadow_variant_binding(predecessor,
walk_forward_passed, qualification, report, historical_experiment_result,
walk_forward_result, qualification_policy, *, qualification_source_head,
qualification_source_tree, binding_source_head, binding_source_tree)` requires
all seven exact external model types. There is no optional historical result,
optional walk-forward verification or verified flag.

Before returning it independently invokes the accepted 137 report verifier,
138 qualification verifier against predecessor/report/completed walk-forward/
policy/exact qualification source, and 138 successor verifier against
predecessor/qualification. Qualification must be PASSED.

Historical-result validation uses a defensive copy preserving shared object
links, including immutable mapping proxies. The historical request, full variant policies, metrics, rolling request/result,
run and root result validators run at their existing retained boundaries.
Unrelated legacy leaf adapters are not recertified or executed. Inherited
Decimal.normalize calls execute inside a fresh value-derived precision context
(at least 28 and sufficient for every retained Decimal coefficient), independent
of caller precision, rounding or traps. They must reproduce original identities
without rounding; evidence whose historical identity depended on lossy Decimal
normalization fails closed. No upstream identity or serializer is rewritten. All retained types/values must remain unchanged after
validation; iterable/list/string normalization drift fails closed. Caller evidence
is never revalidated in place, even on failure. Root request/run/variant types
must be exact, and run variants must retain the exact request variant object in
caller order under the existing result validator.

Reconciliation requires:

- original result ID equals predecessor and report experiment_result_id;
- original request ID equals report experiment_request_id;
- historical/schedule/initial-state fingerprints match report and result;
- exactly one report row for the predecessor variant UUID, and exactly one run
  for its caller ordinal and UUID;
- candidate, report row, request variant and run agree on UUID, ordinal and name;
- row experiment_run_id equals run.run_id; row rolling_result_id equals the
  run rolling result ID; row metrics equal the validated run metrics;
- run ordinal equals predecessor caller ordinal; run.variant is the exact
  validated request.variants[ordinal]; original rank is retained unchanged.

Any malformed/inconsistent evidence raises and produces no binding. There is
no FAILED-binding state. The independent
`verify_research_candidate_shadow_variant_binding(binding, ...)` takes the
same complete external chain, revalidates the binding, rebuilds the expected
artifact and requires exact equality, including exact binding source HEAD/TREE.
A different valid binding source produces a different artifact and cannot verify
the original binding; source syntax alone never proves GitHub acceptance.

## Exact variant resolution without a second configuration serializer

`resolve_bound_research_candidate_variant(binding, historical_experiment_result)`
revalidates binding identity, defensively validates the completed result and
requires all retained result/request/fingerprint/ordinal/UUID/name/run/rolling
relationships. It returns the exact original request variant object from the
supplied result. An unrelated result, including one reusing the same variant
UUID, fails closed. Resolution never runs, evaluates or constructs a simulator.

No full variant configuration is duplicated in binding JSON. The already
validated experiment_result_id + experiment_run_id + rolling_result_id +
variant_id + caller_ordinal bind the candidate to the completed result whose
existing identity commits to the complete request, run set and full variant
semantics. A matching UUID or name alone is insufficient. Existing experiment
identities and nested policy serializers are unchanged.

139-B must receive the original exact completed HistoricalExperimentResult (or
an independently verified equivalent canonical source), verify the complete
external binding chain and use this resolver before accepting observation evidence for that variant.
The resolver establishes only the result bridge; it cannot verify absent report
or walk-forward evidence.

## Canonical parser and capability boundary

JSON is compact, sorted, exact-field-set, without trailing newline. Duplicate,
missing and unknown keys, non-JSON constants, noncanonical UUID/source/types,
bool/int confusion, forged binding_id and alternate whitespace/key order fail.
Recomputed identity and exact canonical reserialization are mandatory.
`from_json()` proves canonical representation and internal identity only. It
proves no report/result/walk-forward verification, executable compatibility or
SHADOW qualification. No acceptance flag is stored.

The module imports only the standard library and the accepted experiment models /
verifiers. AST tests freeze exact module/model import allowlists and prohibit
filesystem/network/provider/credential/runtime/production strategy imports,
runner calls, simulator construction, clocks, random UUIDs and lifecycle promotion.
There is no ShadowResearchStrategyCandidate, build_shadow_candidate, advance,
promote or set_stage API. No production contract or compatibility is created.

## Current inventory and test-only successor authority

Canonical `discover_inventory` / `select_inventory` yields:

| Inventory | Before | After |
| --- | ---: | ---: |
| ACTIVE | 64 | 64 |
| FULL | 176 | 177 |
| ROBINHOOD | 98 | 98 |
| LEGACY | 215 | 215 |
| EXHAUSTIVE | 391 | 392 |
| tests/gui | 44 | 44 |

Exactly one new supported experiments test enters FULL through existing
whole-directory ownership. Seven tests invoking live canonical discovery update
their current assertions; the FULL expected module set admits the new test.
Historical inventory snapshots remain historical.

`ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES` is a new fail-closed overlay
restricted to the exact same seven approved paths as Architecture 138. All
predecessor dictionaries, including `ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES`,
remain exact/frozen. Every existing Architecture-138 successor-resolution site
now resolves 139-A immediately afterward, before actual Git blob comparison:

```text
historical pin -> HIST2 -> D1R5 -> Architecture 138 -> Architecture 139-A
-> actual Git blob comparison
```

The five sites cover D1Q, D1R5, D1R4R, D1R4 and D1R3. No executable/source
path is admitted to the overlay. Missing paths, extra test paths, executable
paths and wrong successor blobs fail closed. Frozen predecessor digests and
untouched D1R5 test pins remain independently checked. The superseded 138
wrong-current-blob assertion moves to the current 139-A overlay; 138 shape
rejection and exact historical dictionary digest remain enforced.

Executable/native/AST pins, ACTIVE membership/digest, D1R5 registration,
workflow bytes and production push routing remain unchanged. Cumulative
Architecture-134 docs and bounded status/handoff are not implementation paths.

## 139-A publication and next boundary (accepted predecessor)

The current-lineage 139-A source checkpoint is accepted. No local
FULL/ROBINHOOD/LEGACY/EXHAUSTIVE certification was required beyond the focused
verification and repository source gate recorded above.

139-B extends this accepted predecessor with deterministic
no-effect observation provenance, minimum session/observation policy, failure
semantics, no-effect enforcement, SHADOW qualification and any immutable SHADOW
successor. Those capabilities remain unimplemented in 139-A and require their
own reviewed source/effect boundaries.

No real research/walk-forward execution, SHADOW live observation, strategy
promotion, ProductionStrategyContract conversion, D1/D1R5/D2 operation,
production SQLite, credentials, provider/Robinhood/broker access, paper mutation
or scheduler/ACL mutation occurs. This parallel research source grants no
production compatibility or authority. Real-money trading remains **NO-GO**.

## Architecture 139-B frozen source-only extension

139-A remains SOURCE ACCEPTED at its exact recorded identity. 139-B is now
SOURCE ACCEPTED after independent ChatGPT review of both exact implementation
commits and their separate workflow_dispatch runs. No production/history branch
is advanced. B1 terminal CI plus exact continuation self-review authorized B2
only; `139_B1_CONTINUATION_GATE=PASS` was internal continuation permission and
never substituted for this final canonical acceptance.

139-B1 adds canonical caller-supplied observation evidence only. Exact frozen/
slotted Observation and ObservationBatch models live in
`research_candidate_shadow_observation.py`. Fingerprints are exact UUIDs.
Dates are exact `date` values; timestamps are exact aware `datetime` values with
`tzinfo is UTC`, fold zero, serialized with six microsecond digits and Z.
Dates are caller session evidence, not proof that an exchange was open.
Ordinals are exact integers 0..1,000,000; batches are exact nonempty tuples of
at most 100,000 observations. Caller order must increase strictly by
(session_date, ordinal), with globally nondecreasing timestamps. No sorting.
Duplicate IDs or date/ordinal pairs and mismatched binding IDs raise.

Each observation has nine mandatory exact integer zero counters: credential
reads, provider calls, Robinhood reads, broker calls, paper mutations, scheduler
calls, ACL mutations, production SQLite reads and writes. Batches retain those
same fixed zero fields. Every semantic field is identity-bound. This enforces
canonical zero accounting, not the truthfulness of a future external producer.
No acquisition, filesystem, network, runtime, simulator or production interface
is introduced. All fixtures are synthetic in memory.

Observation and batch schemas are `research-candidate-shadow-observation/v1`
and `research-candidate-shadow-observation-batch/v1`; identity versions replace
`/v1` with `-identity/v1`. Namespaces are frozen literal UUID5 values derived
from NAMESPACE_URL and each schema. Material is length-framed UTF-8 semantic
scalars: schema, binding ID, date, timestamp, ordinal, input/decision fingerprints
and nine zeros for observation; schema, binding ID, observation source HEAD/tree,
count, ordered observation IDs and nine zeros for batch. No serialized bytes,
clocks, paths, randomness, Python hash or ambient Decimal context enter identity.

The batch builder and independent verifier receive the complete exact accepted
137/138/139-A external chain, independently verify 139-A, then resolve the exact
original historical variant without execution. Source HEAD/tree are lowercase
40-hex provenance, not source acceptance. Strict parsers reject duplicate,
unknown/missing fields, forged derived values, bool/int confusion, alternate
UUID/date/timestamp representations, constants and noncanonical bytes. Parsing
is self-consistency only. Verifiers rebuild from independently supplied evidence.

139-B2 qualifies only provenance, session/observation coverage and mandatory
zero effects. Three required exact positive bounded integer policy fields are
minimum_session_count, minimum_total_observation_count and
minimum_observations_per_session. Total minimum must be at least the product of
the other minima. Insufficient valid coverage yields FAILED, with ordered reasons
INSUFFICIENT_SESSIONS, INSUFFICIENT_TOTAL_OBSERVATIONS,
INSUFFICIENT_OBSERVATIONS_PER_SESSION. Malformed evidence raises. No financial
performance threshold is inferred. Only PASSED evidence may build a separate
immutable SHADOW successor with original lineage/rank retained. No prior parser
changes, generic lifecycle mutation, PAPER_CANDIDATE, AWAITING_HUMAN_PROMOTION,
compatibility, promotion, production contract or execution authority is added.
Real observation acquisition is outside Architecture 139-B.

B1 and B2 add their own test-only successor overlays after 139-A, using exactly
the same seven live-inventory paths at the five existing resolution sites.
Every predecessor dictionary, domain blob, executable/native/AST pin, ACTIVE
membership/digest and workflow byte remains frozen. Predecessor hash checks
prevent an overlay from concealing historical drift. Canonical discovery adds
one FULL/EXHAUSTIVE module per checkpoint; other inventories stay unchanged.
Cheap admission/static/Ruff/diff gates precede focused pytest. No local broad
profile runs. Each dispatch must have exact HEAD, attempt 1, source-static and
four broad shards SUCCESS, each below 300 seconds, terminal source-gates SUCCESS;
active/certification jobs skip as expected for unmapped research dispatch.
No second dispatch or blind retry. Any gate concern stops before B2.
Final source acceptance and bounded status/handoff closeout are completed by ChatGPT in this documentation-only descendant.


### B1 public source surface and verification

Public artifacts: `ResearchCandidateShadowObservation`,
`ResearchCandidateShadowObservationBatch`, and
`ResearchCandidateShadowObservationError`. Public operations:
`build_research_candidate_shadow_observation_batch` and
`verify_research_candidate_shadow_observation_batch`. Package exports remain
unchanged in B1; the module is imported explicitly.

Observation namespace: `ba1eef1a-c096-53bf-a440-545a66226149`.
Batch namespace: `3cc3c312-8a9c-5c29-9c6b-81eeeb49d5aa`.

B1 inventory: ACTIVE 64 / FULL 178 / ROBINHOOD 98 / LEGACY 215 /
EXHAUSTIVE 393 / GUI 44. B1 adds no other test module or ACTIVE authority.

## 139-B2 complete deterministic qualification and SHADOW contract

B1 passed its internal continuation gate at HEAD
`3bf604f407445da0c587cfd91545c113c99e341f`, TREE
`732f75cc09c8296ce09f244edc36ca8bda61e7b7`, CI #563 / 38664134287,
attempt 1, terminal SUCCESS. Four shard job walls: 97 / 132 / 136 / 141 s,
all below 300 s. This was internal continuation only; final ChatGPT acceptance of both exact
source checkpoints is now complete. B1 source/test and overlay remain frozen. B2 is a separate normal commit and one fresh CI dispatch on the same
research branch. Operational and canonical-history branches stay unchanged.

The three policy minima are mandatory exact positive ints bounded at 100,000,
the B1 maximum observation count. Total minimum must cover sessions multiplied
by minimum per session. No defaults, disable switch, economic threshold or rank
authority exists. Policy schema is
`research-candidate-shadow-qualification-policy/v1`.

`ResearchCandidateShadowQualification` retains exact binding/batch IDs, embedded
policy, B2 qualification source HEAD/tree and recomputable positive bounded
coverage facts (observation count, distinct session count and minimum actual
observations in any session). Counts must describe a possible nonempty batch;
for one session its minimum equals its total. Status and ordered failure
reasons are derived, never constructor authority. Inclusive minima yield PASSED;
otherwise FAILED reasons appear once in enum order: INSUFFICIENT_SESSIONS,
INSUFFICIENT_TOTAL_OBSERVATIONS, INSUFFICIENT_OBSERVATIONS_PER_SESSION.
Schema is `research-candidate-shadow-qualification/v1`.

`qualify_research_candidate_shadow` takes the full exact 137/138/139-A chain,
binding, B1 batch, B2 policy, exact original observations and all source IDs.
It explicitly independently verifies 139-A and resolves the original variant,
then invokes the independent B1 verifier against that same complete chain and
caller evidence. It recomputes all counts by exact session dates and checks
every observation/batch zero counter. Malformed provenance/effect evidence
raises; it can never become a FAILED coverage result. The independent
`verify_research_candidate_shadow_qualification` rebuilds that complete result
and requires exact equality. B2 source kwargs are named
`shadow_qualification_source_head/tree` to distinguish prior 138 source IDs.
Stored B2 fields are `qualification_source_head/tree`.

The separate frozen/slotted `ShadowResearchStrategyCandidate` has schema
`research-strategy-candidate-shadow/v1` and fixed SHADOW stage. It retains the
original source HEAD/tree, report/result/variant UUIDs, caller ordinal, name and
rank. It additionally retains the exact WALK_FORWARD_PASSED predecessor ID,
BACKTESTED ancestor ID, prior walk-forward qualification ID, binding/batch/B2
qualification IDs, and each prior qualification/binding/observation/B2 source
HEAD/tree. Its constructor reconstructs and checks exact prior candidate IDs.

`build_shadow_research_candidate` requires exact passed predecessor, binding,
batch and qualification models; validates every retained artifact; requires
PASSED with no reasons; recomputes coverage from the batch; checks all linkage
and original candidate/binding facts; and returns only the immutable successor.
`verify_shadow_research_candidate` independently rebuilds that linkage. These
operations/parsers prove self-consistency; use the full qualification verifier
for independently supplied external evidence. No verified flag is retained.

Namespaces are literal UUID5(NAMESPACE_URL, schema). Identity versions replace
`/v1` with `-identity/v1`. All semantic scalars are length-framed UTF-8 in frozen
order. Policy: schema then three minima. Qualification: schema, binding/batch
IDs, policy ID and all policy fields, B2 HEAD/tree, three coverage counts,
status, reason count, ordered reasons. Successor: schema, stage, then all 22
constructor fields in declaration order. Every semantic field participates;
no JSON bytes, clocks, paths, random identity or Decimal context is used.

All three parsers require canonical compact sorted JSON, exact field sets,
unique keys including nested policy, exact ints/UUIDs/sources and recomputed
IDs/status/reasons/stage. Original parsers remain BACKTESTED/WALK_FORWARD_PASSED
only. B2 imports public predecessor interfaces only. Package exports include
the B1 and B2 public APIs without changing their modules or prior exports.

B2 overlay follows B1 at the same five sites for exactly seven inventory tests;
it freezes B1 dictionary bytes semantically while all earlier dictionaries,
executable/native/AST pins, ACTIVE definition and workflow bytes stay frozen.
Canonical inventory becomes FULL 179 / EXHAUSTIVE 394; ACTIVE 64, ROBINHOOD 98,
LEGACY 215 and GUI 44 remain unchanged. No local broad profile runs.

Real observation acquisition, PAPER_CANDIDATE, AWAITING_HUMAN_PROMOTION,
production compatibility, promotion, human approval, production contracts,
provider/network/runtime/broker/paper execution and generic lifecycle mutation
remain absent. Final B2 CI must be terminal SUCCESS on exact source, attempt 1,
with static/four broad shards/aggregator PASS and each shard below 300 s.
After exact remote/diff/tree/CI proof, STOP for ChatGPT review of both commits.
No final status/handoff closeout or Architecture 140 is part of this task.


### B2 frozen namespaces and focused result

Policy: `research-candidate-shadow-qualification-policy/v1`, namespace `e89daadf-93fb-53e9-ae24-ff364c022d31`.

Qualification: `research-candidate-shadow-qualification/v1`, namespace `c93b2415-1b57-5794-811d-c84dfadf53e6`.

SHADOW successor: `research-strategy-candidate-shadow/v1`, namespace `82dd4ec8-46f3-5f7c-af78-042b0f89bf69`.

B2 focused verification passed 817 domain cases (144 new B2 cases and
673 retained domain cases) plus 1,358 inventory/authority cases: 2,175 distinct
passing cases, zero failures/errors/skips. Both Ruff phases pass on all eleven
touched Python paths; diff and all five authority boundaries pass. B1 source/
test blobs and overlay, all older dictionaries, accepted 137/138/139-A source/
tests, ACTIVE definition, workflow bytes and bounded status/handoff stay frozen.
The package export surface is extended additively in B2; existing public names
and their order are preserved. Final ChatGPT source acceptance is complete.

## 139-B final exact-source acceptance

ChatGPT independently re-fetched and reviewed both exact GitHub checkpoints
before this bounded closeout. B1 is canonically SOURCE ACCEPTED at
`3bf604f407445da0c587cfd91545c113c99e341f` / tree
`732f75cc09c8296ce09f244edc36ca8bda61e7b7`; its sole parent is the
accepted 139-A docs descendant
`30036d4adcea7535f5fcc9bb46d91ce2c00e4bb5`. B2 is canonically SOURCE
ACCEPTED at `bf98553592d2ef740d6a6ffdc104c6cd28023379` / tree
`34627f90f3ad8fc441346cc3d567a3f15495219b`; its sole parent is B1.

Exact new domain/test blobs are:

| Checkpoint | Path | Git blob |
| --- | --- | --- |
| B1 | `src/trading_bot/experiments/research_candidate_shadow_observation.py` | `61a4f9bc67ad0c05f961a523c231e64e6fb55732` |
| B1 | `tests/experiments/test_research_candidate_shadow_observation.py` | `7027ae2274cf49e3963c7511ac06637de708811b` |
| B2 | `src/trading_bot/experiments/research_candidate_shadow_qualification.py` | `75cc22d16d65f51ce75921ab66c6dcabfbfa119b` |
| B2 | `tests/experiments/test_research_candidate_shadow_qualification.py` | `197fff05c6d8c948529052eb9b68cb0c578902cd` |
| B2 | `src/trading_bot/experiments/__init__.py` | `a7d3104adb5b1f00448c1559c6efe55ad3a3256c` |

The accepted 137/138/139-A domain/test blobs remain byte-identical:
`5e617d976278a9a97b990284dfd17fd2abc87f18`,
`41d11dfb3b04a804d1d69e91ca918157026ca72e`,
`b068100e27c290769dc3d8dd4b475edef3d9cfe8`,
`d26aac7c04a311fc82a2f1b7e12f961353504654`,
`ff1f76c5309ab8ed2e2e48d487365600633b1c0d`, and
`0b78cd52d555077f98009720157f230fed9cebd3`. The source-gate workflow blob
also remains `fe6aceac62721338eba4fcb40e2e7fde0d976e18`.

B1's seven-path successor overlay matches the exact B1 test blobs. B2's
seven-path overlay matches the exact B2 test blobs and resolves immediately
after B1 at all five live inventory resolution sites. The final chain is:

```text
historical -> HIST2 -> D1R5 -> 138 -> 139-A -> 139-B1 -> 139-B2
-> actual Git blob
```

B1 freezes 32 predecessor dictionary digests; B2 freezes all 33, including the
B1 overlay SHA-256
`d66e134a5491e1e2966728e27558f05c51946c5e89930707e1471f339324634c`.
Final inventory is ACTIVE 64 / FULL 179 / ROBINHOOD 98 / LEGACY 215 /
EXHAUSTIVE 394 / GUI 44.

Checkpoint Source Gates #563 / `38664134287` mapped exactly to B1 HEAD/tree,
workflow_dispatch attempt 1, terminal SUCCESS. Static gates reported
`GIT_DIFF_CHECK=0`, `RUFF_CHECK=0`, `RUFF_FORMAT=0`; all four broad
shards reported `PYTEST=0` in 65.099 / 73.371 / 94.362 / 107.566 seconds.
Checkpoint Source Gates #564 / `38665480838` mapped exactly to B2 HEAD/tree,
workflow_dispatch attempt 1, terminal SUCCESS. Static gates again reported
`GIT_DIFF_CHECK=0`, `RUFF_CHECK=0`, `RUFF_FORMAT=0`; all four broad
shards reported `PYTEST=0` in 107.140 / 128.331 / 101.647 / 72.901 seconds.
Both terminal `source-gates` jobs passed with FULL routing; active and
certification jobs skipped as expected for this unmapped research dispatch.

The strict frozen/slotted models, UUID5 length-framed identities, compact sorted
canonical JSON, duplicate/unknown/missing field rejection, exact bool/int and
UTC handling, ordered failure reasons, and derived stage/status/IDs were reviewed
against the frozen contract. B1's public verifier re-runs the complete 139-A
external binding verification, resolves the exact historical variant, rebuilds
the batch from independently supplied observations/source identity, and requires
exact equality. B2's qualification verifier independently rebuilds from the
complete predecessor chain, exact binding, B1 batch, policy, observations and
source identities. The separate SHADOW successor verifier rebuilds exact
self-consistent linkage; it does not replace the full external qualification
verifier.

Final 139-B effect accounting is:

```text
PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
ROBINHOOD_READS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
ACL_MUTATIONS=0
PAPER_MUTATIONS=0
REAL_RESEARCH_EXECUTIONS=0
REAL_WALK_FORWARD_EXECUTIONS=0
SHADOW_LIVE_OBSERVATIONS=0
STRATEGY_PROMOTIONS=0
PRODUCTION_CONTRACTS_CREATED=0
D1_OPERATIONS=0
D1R5_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

This acceptance is source-only. Real observation acquisition, product/history
integration, production compatibility, `PAPER_CANDIDATE`,
`AWAITING_HUMAN_PROMOTION`, promotion, protected execution and any successor
architecture remain outside this checkpoint. The active product and canonical
history branches remain on their existing product-lineage descendant and are not
advanced by this research closeout.
