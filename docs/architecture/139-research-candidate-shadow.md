# Architecture 139 / RCL-3 — exact binding, then no-effect SHADOW evidence

Status: **139-A SOURCE ACCEPTED** at HEAD `e730b3b05c0c78181a4b3ff6b8e257cb04f3ff15` / TREE `ea13572c565bcfe65959014bf1c98572c89cc3a7`; Checkpoint Source Gates #517 / 38387248166 SUCCESS. 139-B deferred while returning to the main production lane.

## Acceptance evidence

Exact accepted executable/test source is HEAD
`e730b3b05c0c78181a4b3ff6b8e257cb04f3ff15`, TREE
`ea13572c565bcfe65959014bf1c98572c89cc3a7`, one commit after exact base
`1af8150c9985f5dc7ad1e143a16d90dcdc86be1a` /
`f0adb7a370c5ab1d41c4a6d62e2b9db012096952`.

Checkpoint Source Gates #517 / 38387248166 is terminal SUCCESS on that exact
source. source-static passed all 62 authorities with 83 test paths and 356 Ruff
paths. Broad shards passed 2,174 / 2,050 / 1,880 / 2,350 cases plus one optional
SDK skip: 8,454 passed, 1 skipped, 0 failed/errors. Hygiene timings were
96.994 / 47.760 / 72.335 / 95.456 seconds. Focused implementation evidence
records 966 distinct passing cases. Exactly three retained Architecture-134
test-file pins changed and match the committed Git blobs.

The lossy-Decimal historical-identity case is intentionally fail-closed. No
SHADOW stage, live observation, production compatibility, production contract,
promotion, D1/D1R2 or D2 authority is created. 139-B is deferred while work
returns to the protected production lane.

## Split architecture and frozen base

139-A / RCL-3A establishes exact research-candidate variant provenance only.
139-B will separately define no-effect observation provenance, minimum session /
observation policy, failure semantics, no-effect enforcement, SHADOW qualification
and an eventual immutable SHADOW successor. SHADOW remains reserved in 139-A.

Branch: `feature/research-candidate-shadow-variant-binding`.
Worktree: `F:\AI\worktrees\ai-trading-bot-research-candidate-shadow-variant-binding`.
Exact base HEAD `1af8150c9985f5dc7ad1e143a16d90dcdc86be1a`, TREE
`f0adb7a370c5ab1d41c4a6d62e2b9db012096952` is the Architecture-138 docs closeout.
Accepted 138 executable/test identity remains HEAD
`e0735af265894757ff9b90ab185bcbd77ee2dee9`, TREE
`a29f51faaa81e866d0825ffbe082c5fcddb94584`, CI #516 / 38380502369 SUCCESS.
137 and 138 source modules, schemas, namespaces, identity framing, builders,
verifiers and canonical bytes remain unchanged. Neither prior parser admits SHADOW.

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

## Inventory and next boundary

Canonical discovery: ACTIVE 62 / FULL 172 / ROBINHOOD 94 / LEGACY 215 /
EXHAUSTIVE 387 / tests/gui 44. One supported experiment test is admitted to FULL.
Current normative assertions and the exact FULL expectation are reconciled.
Only the three directly changed retained profile/strategy test blobs are repinned;
production executable/native/AST pins, ACTIVE tuple/digest, historical recovery
pins, source-gate workflow and production push allowlist remain frozen.

Focused verification precedes one ordinary exact-file commit/push and exactly
one fresh Checkpoint Source Gates dispatch on the resulting exact branch/HEAD.
Terminal CI and ChatGPT exact-source review are required for acceptance. No local
FULL/ROBINHOOD/LEGACY/EXHAUSTIVE certification is run for this checkpoint.

139-A grants no SHADOW stage, live/provider observation, production compatibility,
promotion, D1/D1R2 or D2 authority. Real-money trading remains NO-GO. Stop after
terminal CI/handoff; ChatGPT owns exact-source review and Architecture 139-B.
