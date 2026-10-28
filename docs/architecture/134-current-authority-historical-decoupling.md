# Architecture 134 — Historical and current authority separation

## Correction boundary

This source/test/workflow correction starts at develop
`29e9487b7a4e831dc6f306de66184cb6f8bb2723`, tree
`fc3649f3a86f42503402ac20bad595a5d62570a5`. Feature #745 was green;
develop #746 (run 40421315451, attempt 1) was red. Neither integration nor
that diagnostic successor is source accepted by this correction. #746 remains
immutable integration evidence and is never rerun.

The complete preserved graph is
`tests/runtime/checkpoint_runner/fixtures/integration_746_authority_failures.json`:
296 failures, 120 distinct messages, 13 checkpoint families. Failures propagated
through shared predecessor reconstruction, rather than 296 independent defects.

## Authority classification and owners

`scripts/source_authority.py` enforces four classifications:

| Class | Authority and evolution |
| --- | --- |
| IMMUTABLE_HISTORICAL | Historical Git objects, declarations and source reconstruction. Current infrastructure changes never repin them. |
| SECURITY_SEMANTIC | Current exact source/AST where implementation materially defines authorization, effect ceilings or security. Explicit successor review is required to change it. |
| CURRENT_MUTABLE | Today's runner, registry, workflow, profiles, lanes, Python test harness and coordination docs. Their canonical semantic owners may evolve them. Historical checks reconstruct immutable copies instead. |
| INCIDENT_EVIDENCE | Immutable incident/consumed reports and historical facts. No retry or effect authority. |

| Current concept | Canonical ownership family |
| --- | --- |
| Registry/order, static evaluation, admission | checkpoint runner and current runner contract tests |
| CI routing, active inventory, job topology, reuse | current CI/workflow authority and runner CI tests |
| Profile ownership and frozen required baselines | certification runner and profile tests |
| Lane planning and timing topology | certification runner and lane tests |
| Current Python test implementation | owning test harness; historical maps have no current-byte claim |
| AGENTS/workflow/status/handoff prose | current workflow coordination; never executable exact current blobs |
| D1S1/D1S2/D1S3/D1S4/R1/R5 and predecessor evidence | immutable historical declarations, Git objects and checkpoint-specific security semantics |

Current profile baselines remain 122 FULL / 49 ROBINHOOD required modules.
FULL has seven lanes under 146-B1-C4 and ROBINHOOD four. The additional current authority regression
module is explicitly owned by both supported profiles. No certification is weakened.

## Complete failure audit and preserved safety properties

Every row below is covered by the preserved graph; the fixture retains each
checkpoint/message edge without abridgement.

| Failed family | Historical/current coupling replaced | Preserved authority |
| --- | --- | --- |
| 146-A | R3N C1/C4 and read-only predecessor harness/workflow pins; admission AST | Immutable research/domain source, predecessor maps and historical AST reconstruction; current admission evaluated separately |
| D1S1 | Own soak-test bytes and shared runner/certification/session harness bytes | Accepted soak/source identities, source-only registration, deterministic soak and session security semantics |
| D1S2 | D1S1/D1S2 test overlays and shared harness | Installed-readiness source/effect ceiling, exact predecessor declarations and source-only registration |
| D1S3 | D1S2 graph plus shared and own installation tests | Native/operator source and protected dispatch, authorization/latch semantics; retired publication remains historical |
| D1S3-R5 | D1S3 graph and publication-recovery test bytes | Consumed/publication incident evidence and exact recovery/security source; no forward retry authority |
| D1S4 direct installation | R5 graph, workflow prose and direct-installation tests | Rename-free destination identity, current forbidden-primitive graph, exact native/product source and dispatch |
| D1S4-R1 ACL recovery | D1S4 graph and recovery tests | Immutable consumed incident evidence, plan/authorization interlocks and exact protected source |
| D1S4 fresh source | All predecessor harness graphs and workflow prose | Fresh-source selection semantics, consumed predecessor, false effect authority and immutable executable/product identities |
| F1R1-C1 operator | Own qualification tests and shared runner/certification/session harness | Qualification source, authorization and effect ceilings plus immutable predecessor declarations |
| D1R5 wake qualification | D1Q/D1R3/D1R4/D1R4R test and shared infrastructure hashes | Wake qualification security source, predecessor semantics and effect limits |
| Authentication qualification | D1Q/D1R3/D1R4/D1R4R harness pins | Authentication implementation, credential boundaries and historical qualification evidence |
| Production paper runtime | Runtime tests and runner/profile hashes | Runtime/product source and deterministic security/authorization semantics |
| Production runtime ACL | ACL test plus runtime graph harness hashes | Exact ACL/runtime source, authorization and effect ceilings |

Historical pin dictionaries and their digests are retained unchanged as records;
checks of CURRENT_MUTABLE paths no longer compare today's bytes. A historical
path/pin must be declared in immutable runner object
`e31fd6bd860fdc752a65915735bb230f96afa475`; reconstruction validates the actual Git
blob. This object is a published record source, not a claim that red #746 was
accepted. `historical_authority_objects.json` indexes immutable ancestor runner
objects by symbol/AST digest. Shared workflow/reuse/registry AST versions are reconstructed independently as well.
The two historical digest builders read frozen profile, harness and CI-caption
material from the checksummed record rather than live current globals. A structural
regression rejects new historical/review-paper exact-byte or AST comparisons
against those mutable globals; such historical exactness must route through the
classification-aware authority API. SECURITY_SEMANTIC source remains eligible
for exact-current checks. Protected execution/preflight implementations stay
SECURITY_SEMANTIC and compare today's source directly.

One retired planned harness declaration, test_ci blob
`3737babdb35cb5992edcf87616da93d457af47b5`, was never a Git object. It is preserved
as a declaration, not asserted to be accepted source. Its explicit historical
source reconstruction uses the accepted predecessor commit
`8a6791ba036a60f978d700bba0a2f1bc65a631bc` and test_ci blob
`b7be985d19d535f0dd6837cc5cfb99615e24f5f0`. Reconstruction verifies this path/commit
binding and exact blob; it never substitutes current bytes or creates an object.
Missing real immutable/security source still fails closed.

## Structural fan-out prevention

Historical pin declarations must remain AST-identical to the immutable record.
Every mutable-path exact claim is assigned to its enclosing declaration/function.
A new map or authority family cannot copy even a previously known path/hash into
another historical owner. Unknown claims fail current authority. There is no
numeric allowance and no new successor-overlay ladder. Current semantic checks
compose with historical reconstruction; future test/workflow/profile changes
update their current owners without cascading historical repins.

## One evaluator and prospective-develop admission

`current_source_authority.evaluate_source_authority` is the shared deterministic
implementation. FEATURE selects the exact active feature authority (or full batch
for an unregistered feature). PROSPECTIVE_DEVELOP selects the exact registered
full-batch authority names serialized in the source-owned workflow. CI's
`verify_checkpoint` and `verify_batch` call that same implementation. Workflow
parity tests bind its selection to actual develop source-static routing.

General `ops.ps1 admit` keeps exact clean candidate, origin/live-develop,
strict-descendant, nonempty-diff and fast-forward ancestry requirements. It
requires FEATURE and PROSPECTIVE_DEVELOP authority for the same HEAD/tree,
prints both context results, then runs the small current contract tests.
Admission rejects CI partial-phase/shard controls and stops on failed identity
prerequisites before authority evaluation. The public evaluator requires a clean
committed candidate. Current registry ownership validates nonempty, well-formed
existing test/static inventories and registered supported certification mappings.
Evaluation reads repository files and Git objects; it never merges, switches,
updates refs, materializes a checkout, runs canonical profiles, invokes host
observers or performs protected effects. Git identity is checked before/after.

If exact-source/fast-forward admission and prospective authority pass, develop
source-static for the same source must not discover deterministic repository
authority failure. Such a failure is a workflow infrastructure defect.

The correction branch has an explicit source-only alias to the existing
diagnostic checkpoint and its GitHub-owned ROBINHOOD mapping. It does not change
the diagnostic's host-pinned branch or grant host/protected dispatch authority.

## Preserved diagnostic and production boundary

The closed HOST taxonomy, sanitized HOST_UNKNOWN, v1 BLOCKED/HOST semantics,
`execute = None`, zero effects and false authority remain. The first v1 host
attempt stays consumed/non-retryable, report SHA256
`3f412affd0fd89b850d4f2de4b7e27680b01780c9e1f6fdd3957a51821e23a36`.
No real-host diagnostic runs. No scheduler/root/ACL/provider/credential/broker/live
effect is authorized. Forward release paths remain rename-free unique immutable
destinations; retired rename publication is evidence only.
