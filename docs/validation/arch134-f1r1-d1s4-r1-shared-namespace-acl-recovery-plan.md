# Validation — Architecture 134-F1R1-D1S4-R1

Source/fake-host verification only. The authoritative incident and complete
contract are recorded once in the matching architecture document.

Original accepted base: 30a410d9023324ebe5c23e6a8ff128353b9ebf1f /
cf50b0b7b84428d9e502ed5bd85307001bc866ed.
Original source/direct correction parent: b79ba5972ec4300971d271573efcd50a15beb75a /
a0b35e27ebdfa524daab590a9812be7b5924dab7.
Preserved original CI: #711 / 40156759342, attempt 1, SUCCESS.
Exact-source review withheld acceptance for one durable reservation defect.
Correction identity/terminal CI are post-commit facts supplied externally.

## Local verification contract

Run focused R1 and retained D1S4/security/release/runner tests, then whole-repo
Ruff lint, Ruff format check and git diff --check. Use a fresh GUID evidence
root below F:\AI\temp\pytest for every pytest attempt. Preserve failed local
evidence and rerun only affected behavior after correction. No Ruff --fix.
No local canonical ROBINHOOD/FULL duplicate: the correction push owns the next
canonical ROBINHOOD; original #711 remains unchanged. The 300-second ceiling
and required 122/49 baselines remain.

The new module covers exact frozen incident admission, stable semantic plan,
all target policy/identity/hash/path and non-target scope negatives, source/
Administrator/repeat admission, authorization/digest/plan interlocks, exclusive
durable latch/readback ordering, two-call order, false/nonzero/exception/
interrupt/exit/close ambiguity, independent repeated readback, raw DWORD
retention, consumed original/recovered/partial reconciliation, restart no-retry,
private native ABI/exclusive-open/DACL-only boundaries, fixed-path rejection,
and graph/primitive allowlist injection. D1S4 adds ten sanitized stage failures
and the actual John-CI/OI incident regression with runtime/Python unchanged.

Current-product inventory assertions include R1; historical timing-model tests
exclude newly admitted fallback-weight modules when asserting their frozen
historical model. No predecessor behavior is silently removed.

## Completed focused evidence

**1,878 unique affected cases are green across focused runs**, with latest
results 0 failed / 0 errors / 0 skipped. This includes all **124 R1 cases** and
all **135 retained/extended D1S4 cases**. Counts are a union of unique JUnit
(classname, name) identities with the latest result for each, not a sum of
repeated executions.

The 15-module focused run covered R1, D1S4, checkpoint core/CI, certification
profiles/lanes, predecessor C1, release installation/host/operator, D1S3, R5,
retained-root diagnostic, scratch ACL and retained-root recovery. It recorded
1,853 passes and one stale current lane-count assertion in 120.40 seconds.
That assertion and one additional predecessor FULL-count assertion were fixed
locally; the lane algorithm and required baselines were unchanged. The remaining
changed current-inventory functions were tested separately. Earlier setup,
fixture, route-comparand and closed-graph failures remain preserved; every
failed case has a later green result.

Key external evidence roots below F:\AI\temp\pytest:

- d1s4-r1-focused-903ec4beaa8e444aadb71b99148eafd9: 1,853 passed / 1 failed;
- d1s4-r1-inventory-3b8435d035674c078d291069e579ad1a: 17 passed / 1 failed;
  exact 18-function selection is preserved in targets.txt;
- d1s4-r1-leaf-bcb701749fb64b04b9ceca67aa9745f4: 257 passed / 1 graph
  registration failure, including standalone observer/ABI and all behavior;
- d1s4-r1-authority-571c67d97c224a5fa733b21a55485319: **176 passed** in
  22.52 seconds, including the corrected graph/registration, both affected
  runner modules, and both corrected inventory assertions;
- d1s4-r1-final-targets-a611996fbd324b63a1282210a5cb24c2: **5 passed** in
  2.68 seconds: isolated import, exact authority, protected runner interlocks,
  actual incident and real malformed-latch diagnostics.

All roots contain results.xml and fresh base directories; none may be reused.
The source tools were the already isolated development interpreter:
F:\AI\temp\d1s4-source-tools-8b2bf88a90644779b7dfde54b7d17bd9\Scripts\python.exe
(Python 3.14, pytest 8.4.2, Ruff 0.17.2). Pytest resolves this exact worktree's
src through its configured pythonpath. Standalone checks explicitly insert this
worktree's src; the isolated import test uses -I -B and a process-local source
argument. The stale main checkout's editable installation was not source authority.

Completed command shape, always from the exact R1 worktree:

```powershell
& $Python -B -m pytest -q @FocusedModules --basetemp="$FreshRoot\base" `
  --junitxml="$FreshRoot\results.xml" -p no:cacheprovider --tb=short --maxfail=5
& $Python -B -m ruff check --no-cache --output-format concise .
& $Python -B -m ruff format --check --no-cache .
git diff --check
```

The exact 15-module selection was:

- tests/review_paper/test_arch134_f1r1_d1s4_r1_shared_namespace_acl_recovery.py
- tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py
- tests/runtime/checkpoint_runner/test_core.py
- tests/runtime/checkpoint_runner/test_ci.py
- tests/scripts/certification_runner/test_profiles.py
- tests/scripts/certification_runner/test_lanes.py
- tests/review_paper/test_arch134_f1r1_c1_qualification_operator.py
- tests/review_paper/test_supervised_release_installation.py
- tests/review_paper/test_supervised_runtime_host_admission.py
- tests/review_paper/test_supervised_release_installation_operator.py
- tests/review_paper/test_arch134_f1r1_d1s3_successor_installation_operator.py
- tests/review_paper/test_successor_publication_recovery.py
- tests/review_paper/test_retained_root_diagnostic.py
- tests/review_paper/test_scratch_root_acl.py
- tests/review_paper/test_retained_root_acl_recovery.py

Whole-repository Ruff lint, Ruff format-check (1,354 files), git diff --check and
exact source-authority/graph checks pass. Both Ruff phases ran before the gate
classified failure. No Ruff --fix was used; formatting was an explicit source
edit followed by non-mutating checks. No local full suite/canonical profile ran.

The two new modules are isolated leaves under src/trading_bot instead of the
suggested supervised_release package: its eager facade imports provider-bearing
strategy/market-data packages. R1 preserves that API unchanged, supplies a small
security-facts record and fixed native reader, and rejects every product-module
dependency outside its closed ACL/token/pure-configuration graph. Fresh-process
import is inert and loads no provider/runtime/strategy/release-model package.

Current admitted inventory is FULL 201 / ROBINHOOD 112 / LEGACY 222 /
EXHAUSTIVE 423 modules. Required baseline tuples remain 122/49. The current
ROBINHOOD deterministic lane counts are 29/29/28/26; no lane policy changed.

## Bounded exact-source-review correction verification

The defect was a process-only reservation before exclusive latch creation.
Reservation now starts only after the exclusive create returns an acquired
object, with spent marking before context entry or metadata. Pre-create
admission/create failure with proven absence reports BLOCKED / NOT_STARTED;
failed create with an existing/unprovable object stays indeterminate.

Restart regressions cover parent/payload/create admission; competing partial,
exact consumed and unprovable create observations; context entry, initial fstat,
short/failed write, flush, fsync, close, readback exception/mismatch, readback
identity drift and final created/named identity drift. Post-create exception,
KeyboardInterrupt and SystemExit paths preserve the named file. Each resets
_spent=False after removing injected faults, then proves preflight/execute
non-eligibility, NOT_AUTHORIZED retry and zero pre-fence ACL calls. Successful
restart no-retry behavior remains covered. Mutation fencing and native policy
are unchanged. Each post-create test also proves its intended injected seam
was reached, so caught assertions cannot masquerade as a tested failure.

Correction focused evidence: 860 unique affected cases have green latest
results (163 R1, 135 D1S4, 172 runner core/CI, 197 scratch ACL, 118 retained-root
ACL recovery and 75 retained-root diagnostic). Initial seven-module run at
F:\AI\temp\pytest\d1s4-r1-reservation-correction-2f5659d258f542b9a128827bda2f154c
recorded 859 passed / 1 failed in 40.79 s. The strengthened success-restart test
incorrectly required execute to observe the latch even though its recovered
baseline rejects earlier. Only that test assertion changed; the implementation
was unchanged. Fresh affected-test rerun at
F:\AI\temp\pytest\d1s4-r1-reservation-final-targets-fbee4dba4d81402fa140c84a3995c152
passed the corrected restart and exact-authority tests (2 passed, 2.73 s).
The failed evidence remains preserved. Later seam-activation assertions are
verified by the final targeted run; exact path/results belong to the handoff.
Whole-repository Ruff lint and formatting (1,354 files), graph/exact authority
and git diff --check pass; no local duplicate canonical certification ran.

Correction exact changed paths:

- docs/AI_TRADING_BOT_HANDOFF.md
- docs/PROJECT_STATUS.md
- docs/architecture/134-f1r1-d1s4-r1-shared-namespace-acl-recovery.md
- docs/validation/arch134-f1r1-d1s4-r1-shared-namespace-acl-recovery-plan.md
- scripts/checkpoint_runner.py
- src/trading_bot/shared_namespace_acl_recovery.py
- tests/review_paper/test_arch134_f1r1_d1s4_r1_shared_namespace_acl_recovery.py

## Original implementation changed paths

- .github/workflows/checkpoint-source-gates.yml
- docs/AI_TRADING_BOT_HANDOFF.md
- docs/PROJECT_STATUS.md
- docs/architecture/134-f1r1-d1s4-r1-shared-namespace-acl-recovery.md
- docs/validation/arch134-f1r1-d1s4-r1-shared-namespace-acl-recovery-plan.md
- scripts/checkpoint_runner.py
- src/trading_bot/shared_namespace_acl_native.py
- src/trading_bot/shared_namespace_acl_recovery.py
- src/trading_bot/supervised_release/successor_direct_installation.py
- tests/review_paper/test_arch133_closed_descendant_rename_qualification.py
- tests/review_paper/test_arch133_reprovision_reconciliation.py
- tests/review_paper/test_arch133_reprovision_recovery.py
- tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py
- tests/review_paper/test_arch133_windows_rename_qualification.py
- tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py
- tests/review_paper/test_arch134_f1r1_d1s4_r1_shared_namespace_acl_recovery.py
- tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py
- tests/review_paper/test_d1_session_authorization.py
- tests/review_paper/test_d1_session_execution.py
- tests/review_paper/test_five_session_soak.py
- tests/review_paper/test_pre_market_wake_overnight.py
- tests/review_paper/test_production_strategy_cycle.py
- tests/review_paper/test_supervised_deployment_qualification.py
- tests/review_paper/test_supervised_maintenance_rebind.py
- tests/review_paper/test_supervised_release_installation.py
- tests/review_paper/test_supervised_runtime_host_admission.py
- tests/runtime/checkpoint_runner/helpers.py
- tests/runtime/checkpoint_runner/test_ci.py
- tests/runtime/checkpoint_runner/test_core.py
- tests/scripts/certification_runner/test_lanes.py
- tests/scripts/certification_runner/test_profiles.py
- tests/strategies/test_production_strategy_contract.py
- tests/strategies/test_production_strategy_decision.py


## Publication and acceptance

Branch:
feature/robinhood-production-paper-134f1r1-d1s4-r1-shared-namespace-acl-recovery-current

Worktree:
F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-d1s4-r1-shared-namespace-acl-recovery-current

This bounded exact-source-review correction changes only the durable reservation
seam, its restart regressions, affected docs and exact R1 authority pins. Perform
focused/static verification before one normal correction commit above original
b79ba5972ec4300971d271573efcd50a15beb75a and one ordinary push to the existing
branch (two commits above original accepted base). No amend/rebase/force-push,
standalone docs commit or bootstrap. Preserve #711 unchanged. If the correction
CI is red, preserve it and stop; no automatic second correction or unchanged rerun.

External final handoff must report HEAD/TREE/direct parent/commit count/changed
paths, local results, remote equality, clean index/worktree; terminal run/attempt,
source-static and active results, canonical modules/cases/pass/skip/fail/errors,
wall time and artifact ID/digest. Self-identity and terminal CI are post-commit
facts; no second docs commit solely to backfill them.

Completion state:
R1 CORRECTION IMPLEMENTED / PUBLISHED / PENDING CHATGPT EXACT-SOURCE RE-REVIEW.

No production R1/D1S4 preflight/execute or ACL mutation was run. Preserved incident
objects/latches were not inspected by operator commands or modified. No scheduler,
runtime start, credential/provider, paper/broker, D1/D2 or live effect occurred.
Native Windows acceptance remains a separately reviewed later host boundary.

## Next review action

ChatGPT retrieves the exact correction commit/diff and terminal mapped evidence,
checks the frozen incident, native containment, one-shot ordering, predecessor
pins and sanitized diagnostics, and accepts only if justified. Only afterward:
reviewed develop integration -> develop CI -> registered read-only R1 preflight
-> separate one-shot protected review/execute -> registered reconciliation ->
if recovered fresh successor source/new HEAD/TREE/release ID -> exact deployment
admission -> successor-root write-authority/ACL review -> manual F1 successor
soak -> 145-B -> Research Results GUI -> large strategy campaigns.

Live remains NO-GO. Do not run the real host steps during this checkpoint.

Also remove or update any tests and docs that referenced the old behavior.
