# Architecture 138 / RCL-2 — Deterministic walk-forward qualification

Status: IMPLEMENTED; terminal repository CI and ChatGPT exact-source review pending.

## Exact source and scope

Branch: `feature/research-candidate-walk-forward-qualification`.
Worktree: `F:\AI\worktrees\ai-trading-bot-research-candidate-walk-forward-qualification`.
Exact canonical parent HEAD `6e2081a1278f579ca0cee5a00e2bd83632bc2856`,
TREE `5858cc644d78eab9bbe58d1332f02c1b56aa5c65`.
Accepted Architecture-137 executable/test identity remains HEAD
`2ade3899e2ec97aa53f9cc7af3bfdbe5bab786a6`, TREE
`9d33c980510f841f6dd254b3ff9f587ac2f43203`, source gate #510 /
[38346016265](https://github.com/callmedraken/ai-trading-bot/actions/runs/38346016265).

This pure, in-memory module consumes already-completed immutable research.
It adds a qualification policy, canonical PASSED/FAILED evidence, independent
external verification, and a separate WALK_FORWARD_PASSED successor.
Architecture-137 `research-strategy-candidate/v1` remains BACKTESTED-only;
its source, stage order, parsers, identities and bytes are unchanged.
SHADOW, PAPER_CANDIDATE, AWAITING_HUMAN_PROMOTION, compatibility, human approval,
promotion, production contracts, D1/D2 execution and GUI integration are absent.

## Required policy

`ResearchCandidateWalkForwardQualificationPolicy` is exact frozen/slotted;
all four semantic fields are mandatory without defaults or weakening switches:

- `minimum_fold_count`: exact int, excluding bool, in 2..1,000,000.
- `minimum_fold_simulation_return`: exact finite Decimal.
- `minimum_median_simulation_return`: exact finite Decimal, at least the fold threshold.
- `maximum_fold_drawdown_percentage`: exact finite Decimal, nonnegative.

The constructor preserves supplied Decimals without coercion, normalization,
truncation or rounding. Canonical text denotes their exact numeric values:
zero is `0` (including signed zero), no exponent notation, redundant trailing
fractional zeros or redundant leading zeros. Canonicalization uses Decimal tuples
and integer/string operations, independent of ambient context. Equivalent exact
numeric values share identity; source Decimal representations remain unmodified.
No float arithmetic is used in qualification. Existing aggregate analytics own
all minimum/median/maximum calculations, including exact even-fold medians.

Schema: `research-candidate-walk-forward-qualification-policy/v1`.
Namespace: `e07d29da-3084-5572-9a47-46f9e81dc0f8`.
Fixed identity version: `research-candidate-walk-forward-qualification-policy-identity/v1`.
Ordered material after the version: schema, decimal-free integer fold count,
canonical minimum-fold-return text, canonical median-return-threshold text,
canonical maximum-drawdown-threshold text. `policy_id` is UUID5, init=False;
schema is also fixed init=False. No metadata exists in this policy v1.

Every identity below concatenates `<UTF-8 byte length>:<value>` for each ordered
string, including the version string, then applies UUID5 with its frozen namespace.
No identity uses serialized bytes, paths, clocks, random UUIDs, Python hash,
locale, object identity, mutable service state or ambient Decimal context.

## Evidence reconciliation and all-fold rule

`qualify_research_candidate_walk_forward(candidate, report, walk_forward_result,
policy, *, source_head, source_tree)` requires exact BACKTESTED
ResearchStrategyCandidate and exact HistoricalExperimentReport. The accepted
Architecture-137 independent report verifier runs before thresholds are evaluated.
It retains report/result/variant UUID, caller ordinal, variant name and original
rank reconciliation exactly.

The walk-forward input must be exactly HistoricalExperimentWalkForwardResult.
Revalidation runs on a defensive deep copy, through the existing root, selection
policy, fold, training/test report, row/metrics and fold-result validators, and
rejects normalization drift. Existing identities and selection/report/result
relationships remain authoritative. Selected rank must be exact int 1. Caller
source evidence is unchanged even when validation fails. Qualification source
HEAD/TREE must be exact lowercase 40-hex strings. Source identity retention does
not assert remote acceptance or production authority.

Every training report must contain exactly one candidate variant UUID with the
same candidate caller ordinal and name. Missing/duplicate variants or provenance
disagreement are malformed and raise; no qualification is returned. Original
candidate rank may be 1, 2 or None and remains evidence only. Qualification requires
that the candidate be the selected rank-one training variant in EVERY retained
fold. Losing any fold is valid FAILED evidence, not malformed input. Mixed selected
variants' test results can never establish PASSED evidence for one candidate.

All test folds must have exactly equal `test_end - test_start` and exactly equal
test-rebalance timestamp count. Unequal valid windows yield the failure reason
NONCOMPARABLE_TEST_WINDOWS. There is no annualization, weighting, rescaling,
normalization, or economic comparability inference from starting equity.

## Single existing aggregate analyzer

Internally derive an exact HistoricalExperimentWalkForwardAggregatePolicy:

- policy_id = UUID5(qualification policy UUID,
  `research-candidate-walk-forward-aggregate-evidence/v1`).
- SIMULATION_RETURN operations MINIMUM then MEDIAN.
- MAXIMUM_DRAWDOWN_PERCENTAGE operation MAXIMUM.
- metadata = ().

Call HistoricalExperimentWalkForwardAggregateAnalyzer.analyze exactly once on
the defensive completed source. Retain aggregate result UUID and exact minimum
return, median return and maximum drawdown observations. No caller aggregate,
metric/operation choices, runner, evaluator or second aggregation engine exists.
FAILED mixed-winner evidence retains descriptive aggregate facts only.

## Qualification evidence

`ResearchCandidateWalkForwardQualification` is exact frozen/slotted.
Schema: `research-candidate-walk-forward-qualification/v1`.
Namespace: `3c206910-6ced-5f74-b515-52901f6bdbbb`.
Fixed identity version: `research-candidate-walk-forward-qualification-identity/v1`.

It retains every requested UUID/source/count/observation/status/reason field,
plus the exact embedded `policy` and `test_windows_comparable` bool. Those extra
fields make the entire PASS/FAIL decision recomputable from parsed evidence.
policy_id, status, ordered failure reasons, schema and qualification_id are derived
init=False fields. Counts are exact ints: fold_count >= 1 and selected count in
0..fold_count. Observations are exact finite Decimals, minimum <= median and
maximum drawdown nonnegative. Parsing is self-consistency only.

PASSED iff fold count meets the policy, both window dimensions match, selected
count equals fold count, minimum return and median return meet their inclusive
lower bounds, and maximum drawdown meets its inclusive upper bound. Valid failure
returns canonical FAILED evidence. Reasons occur once each in this exact order:

1. INSUFFICIENT_FOLDS
2. NONCOMPARABLE_TEST_WINDOWS
3. CANDIDATE_NOT_SELECTED_EVERY_FOLD
4. MINIMUM_SIMULATION_RETURN_BELOW_THRESHOLD
5. MEDIAN_SIMULATION_RETURN_BELOW_THRESHOLD
6. MAXIMUM_DRAWDOWN_PERCENTAGE_ABOVE_THRESHOLD

Ordered identity material after the version:

```text
schema
candidate_id
policy_id
policy.schema
policy.minimum_fold_count
policy.minimum_fold_simulation_return
policy.minimum_median_simulation_return
policy.maximum_fold_drawdown_percentage
qualification_source_head
qualification_source_tree
walk_forward_result_id
walk_forward_request_id
source_historical_fingerprint
aggregate_result_id
fold_count
candidate_selected_fold_count
test_windows_comparable ("true" / "false")
minimum_observed_simulation_return
median_simulation_return
maximum_observed_drawdown_percentage
status.value
failure reason count
each ordered failure reason value
```

UUIDs use canonical lowercase hyphenated text; ints use canonical base-ten text;
Decimals use the canonical exact text above. Complete policy semantics are bound
explicitly as well as through policy_id.
`verify_research_candidate_walk_forward_qualification(qualification, candidate,
report, walk_forward_result, policy, *, source_head, source_tree)` validates the
retained artifact, independently recomputes the qualification and requires exact
equality. Source/report/candidate/walk-forward/policy drift raises.

## Immutable passed successor

`WalkForwardPassedResearchStrategyCandidate` is exact frozen/slotted.
Schema: `research-strategy-candidate-walk-forward-passed/v1`.
Namespace: `e9f8a60f-7b82-57d6-868a-040cb79bb81a`.
Fixed identity version: `research-strategy-candidate-walk-forward-passed-identity/v1`.
Stage is fixed init=False WALK_FORWARD_PASSED; schema/candidate_id are init=False.

`build_walk_forward_passed_research_candidate(candidate, qualification)` requires
exact valid BACKTESTED candidate, exact self-consistent qualification, matching
candidate UUID, PASSED status and empty reasons. FAILED cannot produce a successor.
Source HEAD/TREE, report/result/variant UUIDs, caller ordinal, name and original
rank are copied exactly from the predecessor. Walk-forward rank 1 never overwrites
original rank. Predecessor semantic material must reconstruct its exact candidate
UUID, using the unchanged Architecture-137 public model.

Ordered identity material after the version: schema, stage.value,
predecessor_candidate_id, qualification_id, source_head, source_tree, report_id,
experiment_result_id, variant_id, caller_ordinal, variant_name,
`none` if rank is None else canonical rank text.
`verify_walk_forward_passed_research_candidate(successor, candidate, qualification)`
independently rebuilds the successor and requires exact equality. It verifies
predecessor/qualification linkage; use the qualification verifier separately for
external report/walk-forward provenance. Constructor/parsing self-consistency is
not a claim that external evidence was supplied. No generic stage mutation API,
SHADOW materialization, selection/promotion or production conversion exists.

## Canonical transport and capability boundary

All three artifacts use compact sorted JSON with no trailing newline, exact
field sets and exact canonical roundtrip equality. Reject duplicate (including
nested), missing/unknown fields, NaN/Infinity, bool-as-int, alternate number,
Decimal, UUID, whitespace or key-order representations and forged derived
schema/stage/identity/status/reasons. Embedded policy bytes obey the same rules.
No parser asserts independent external verification or retains a verified flag.

Static tests freeze exact imports: future annotations, json, re, copy,
dataclasses, decimal, enum, uuid, public Architecture-137 models/verifier,
HistoricalExperimentReport, HistoricalExperimentWalkForwardResult and the five
public aggregate analyzer/policy/metric/operation models. No private upstream
helper is imported. No filesystem, network, provider, credentials, broker,
production SQLite, scheduler/runtime, subprocess, clock, UUID4, AI/model,
experiment/walk-forward execution, production strategy or D1/D2 capability exists.

## Inventory and review boundary

Canonical discovery: ACTIVE 62 / FULL 171 / ROBINHOOD 94 / LEGACY 215 /
EXHAUSTIVE 386 / tests/gui 44. The one new experiments test is admitted to FULL
by existing supported-directory ownership. Seven current count assertions and
the exact FULL list are updated. Only three directly affected retained test-file
blob pins in checkpoint_runner change; executable/native/AST pins, ACTIVE tuple/
digest, historical recovery pins and workflow bytes remain frozen.

R1 remains `6bf8753b0cc8950ae27b32b6858b64d454c512f0`; R2 remains
`2f122958366d1db282fea51abbd461b83fa893d9`. D1 manual proving remains an
independent protected operation. No production authority is inferred.
The research branch is outside the production push allowlist. After one exact-file
commit/ordinary push, dispatch one fresh repository Checkpoint Source Gates run,
wait for terminal evidence, then hand off to ChatGPT exact-source review and stop.
No local FULL/ROBINHOOD/LEGACY/EXHAUSTIVE gate is run. Real-money placement is NO-GO.
