# Architecture 141 / RCL-4 — Production Compatibility Assessment Plan

Status: **SOURCE IMPLEMENTED; PUBLICATION PENDING**.

## Goal

Implement the pure Architecture-141 compatibility assessment defined in
[141-research-candidate-production-compatibility.md](../architecture/141-research-candidate-production-compatibility.md).

The checkpoint answers one narrow question: does the accepted SHADOW research
artifact already contain an exact reviewed semantic mapping to the current
production MovingAverageCrossover contract?

For the existing model, the required deterministic answer is
`NOT_ESTABLISHED`. The checkpoint records why; it does not create a mapping.

## Expected implementation surface

Expected new paths:

- `src/trading_bot/experiments/research_candidate_production_compatibility.py`;
- `tests/experiments/test_research_candidate_production_compatibility.py`.

Expected additive/current updates only when mechanically required:

- `src/trading_bot/experiments/__init__.py`;
- `scripts/run_test_certification.py`;
- `scripts/checkpoint_runner.py`;
- `tests/scripts/certification_runner/helpers.py`;
- `tests/scripts/certification_runner/test_profiles.py`;
- current inventory assertions in the affected strategy and GUI tests;
- this validation document;
- Architecture-141 architecture document only if implementation discovers an
  ambiguity that can be clarified without broadening authority.

Do not modify Architecture-139 domain behavior, Architecture-140 GUI behavior,
production strategy behavior, D1R7/D1R8/D1R9 source, workflow topology or
protected runtime code.

## Required focused coverage

Tests must prove at minimum:

1. exact model construction, strict canonical JSON and UUID5 repeatability;
2. every semantic field changes identity where type-valid;
3. duplicate/unknown/missing fields, forged ID/status/stage/blockers and
   noncanonical source/UUID representations fail closed;
4. full external 139-B verification is required before assessment;
5. tampered predecessor, walk-forward, binding, observation, qualification,
   SHADOW successor, historical result or resolved variant fails before output;
6. exact resolved variant/result/SHADOW lineage is retained;
7. output stage remains exactly SHADOW;
8. output status is exactly NOT_ESTABLISHED;
9. blocker tuple is exactly and only:
   RESEARCH_STRATEGY_FAMILY_UNBOUND,
   PRODUCTION_SYMBOL_MAPPING_UNBOUND,
   PRODUCTION_CONFIG_MAPPING_UNBOUND;
10. rank 1, rank 2 and unranked candidates receive no compatibility authority;
11. suggestive variant names confer no compatibility;
12. suggestive metadata such as strategy_id=MovingAverageCrossoverStrategy,
    symbol=SPY, short_window, long_window or desired_quantity is ignored as a
    compatibility mapping;
13. a single-symbol historical universe still confers no symbol mapping;
14. no ProductionStrategyContract, MovingAverageCrossoverConfig or strategy
    object is constructed;
15. no strategy evaluation occurs;
16. no PAPER_CANDIDATE/AWAITING_HUMAN_PROMOTION object or generic stage mutation
    exists;
17. parser/self-consistency and full external verification remain distinct;
18. caller inputs remain unchanged on success and failure;
19. Decimal context, object identity, paths and ambient configuration cannot
    affect assessment identity;
20. package exports are additive and existing export order/names remain stable;
21. AST/import tests enforce the frozen pure capability boundary;
22. all Architecture-141 effect counters remain zero.

## Authority/inventory preservation

Use the current checkpoint-runner successor-overlay pattern rather than
rewriting historical dictionaries.

Freeze the exact current predecessor dictionaries and overlays before adding the
Architecture-141 successor. Reject missing/extra/executable/wrong-blob/digest
drift. Preserve existing source/native/AST/workflow pins unless a touched
current test path mechanically requires a new successor overlay.

Recompute ACTIVE/FULL/ROBINHOOD/LEGACY/EXHAUSTIVE/GUI module inventories from
the exact final tree. Architecture 141 is research-only and must not become an
ACTIVE production checkpoint.

## Implementation record

The pure in-memory implementation is now present in
`src/trading_bot/experiments/research_candidate_production_compatibility.py`
with additive package exports and strict canonical JSON parsing. It records
schema `research-candidate-production-compatibility/v1`, identity version
`research-candidate-production-compatibility-identity/v1`, UUID5 namespace
`3a2c0a57-e61a-5b19-bdc2-00e96e732e96`, status `NOT_ESTABLISHED`, and the
ordered three-blocker tuple required by the architecture.

The builder requires the complete external 139-B SHADOW evidence, invokes
both independent 139-B verifiers, resolves and revalidates the bound variant
on a defensive copy, and checks explicit candidate/result/variant/source
lineage before returning the fixed negative assessment. The implementation
does not construct, evaluate, promote, or persist a production strategy or
configuration, does not add an ACTIVE checkpoint, and does not modify the
workflow topology or protected runtime paths.

Local focused verification on the exact final source tree passed:

- new Architecture-141 module: `41 passed in 49.20s`;
- retained 137/138/139 research evidence tests: `760 passed in 82.87s`;
- affected inventory/authority/checkpoint-runner tests: `771 passed in 48.60s`;
- touched Ruff check and format check: passed;
- `git diff --check`: passed.

The measured final inventories are ACTIVE checkpoint registrations `67`, FULL
`183`, ROBINHOOD `101`, LEGACY `222`, EXHAUSTIVE `405`, and GUI `51`.
Architecture-140-A18 predecessor material remains frozen; the Architecture-
141 overlay freezes all seven current inventory-test paths, including the five
corrected source-pinned assertions, with predecessor digest
`a82247963625dea0f6842d4dc59a851c6986d9f3d8d0c0f40d452aaea2a35af5`.

## Local verification

Run, in order:

1. the new Architecture-141 focused test module;
2. retained 137/138/139 domain tests that the new verifier composes;
3. affected inventory/authority/checkpoint-runner tests;
4. touched Ruff check;
5. touched Ruff format check;
6. `git diff --check`.

Do not run a duplicate broad FULL or ROBINHOOD profile locally.

## CI/publication

Publish exactly one ordinary implementation commit/push after all local focused
checks pass. The push-triggered/dispatch route must map to the exact final
HEAD/tree and reach terminal green on attempt 1. If CI fails, preserve that
attempt and return a bounded corrective checkpoint rather than amending or
rerunning unchanged source.

Final implementation report must include:

- base HEAD/TREE;
- final HEAD/TREE/direct parent;
- exact changed paths;
- new schema/namespace/status/blockers;
- focused and authority test counts;
- final inventories;
- predecessor digest/overlay preservation;
- exact new/changed Git blobs;
- CI run/jobs/attempt/result/shard walls;
- clean worktree/index;
- zero-effect accounting.

Stop for ChatGPT source review. Do not integrate, begin GUI work, create a
production contract, materialize PAPER_CANDIDATE, perform real observation
acquisition, or touch the active D1R9 session.
