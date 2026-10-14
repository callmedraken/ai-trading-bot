# Architecture 139-A / RCL-3A — exact research-candidate variant binding

Status: **Current-lineage forward-port implemented; exact-source acceptance pending.**
139-B remains a separate future architecture.

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
external binding chain and use this resolver before observing that variant.
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

## Publication and next boundary

Focused verification precedes one exact-file normal commit and ordinary push
of the fresh research branch, then exactly one fresh Checkpoint Source Gates
workflow_dispatch. Require terminal source-static, four broad shards and
source-gates PASS on the exact pushed HEAD; each broad shard must be below
300 seconds. No local FULL/ROBINHOOD/LEGACY/EXHAUSTIVE certification runs.

Stop after terminal CI and implementation handoff. ChatGPT owns exact GitHub
source review, bounded closeout and the separate 139-B design. 139-B will define
no-effect observation provenance, minimum session/observation policy, failure
semantics, no-effect enforcement, SHADOW qualification and any immutable SHADOW
successor. These remain unimplemented in 139-A.

No real research/walk-forward execution, SHADOW live observation, strategy
promotion, ProductionStrategyContract conversion, D1/D1R5/D2 operation,
production SQLite, credentials, provider/Robinhood/broker access, paper mutation
or scheduler/ACL mutation occurs. This parallel research source grants no
production compatibility or authority. Real-money trading remains **NO-GO**.
