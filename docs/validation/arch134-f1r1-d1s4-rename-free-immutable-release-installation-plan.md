# Validation record — Architecture 134-F1R1-D1S4 Rename-Free Direct Immutable Release Installation

## Purpose

The first machine-enforced rename-free direct installation is implemented and
verified with disposable fake-host tests. All tests are source/local-fake only.
This checkpoint performs no real production materialization or protected effect.

Base:

    develop HEAD 1e9b6a0638f00ddb009bdb7934039b7a9047e678
    develop TREE 1ef95f954cfce509a6b90639b8bb9599e2e9206f
    post-integration CI #705 / 40083293598 / attempt 1 / SUCCESS

## Required focused coverage

The implemented D1S4 test surface covers:

1. exact source/worktree/branch/HEAD/TREE/origin/remote admission;
2. deterministic release ID/path is the existing
   `F:\AITradingBot\releases\<release-id>`;
3. the D1S4 final path is unique to the accepted source identity;
4. preflight AVAILABLE + final absent returns
   `READY_FOR_RENAME_FREE_MATERIALIZATION`;
5. preflight CONSUMED + exact final returns `DIRECT_INSTALL_VERIFIED`;
6. CONSUMED + absent final blocks without retry;
7. CONSUMED + partial/conflicting final blocks or is indeterminate without retry;
8. AVAILABLE + any present final blocks as unowned;
9. repeated namespace/object observation drift becomes INDETERMINATE;
10. exact parent and production-Python admission is preserved;
11. D1S4 latch path/payload are source-derived and caller cannot select them;
12. exclusive latch creation/readback precedes the first final-directory create;
13. no native writer import occurs before durable latch readback;
14. first production create consumes the effect fence even when it raises;
15. FINAL is created directly; no staging directory is created;
16. all child directories/files are derived from the exact verified release;
17. files use create-new/no-overwrite bounded writes and are flushed;
18. exact immutable image security is applied at creation and independently read
    back;
19. all materialization handles close before positive verification;
20. independent final-image reconstruction occurs twice and must match exactly;
21. final image identity, manifest, inventory, binding and Python identities
    agree;
22. a false/exception/KeyboardInterrupt/SystemExit/close ambiguity after the
    fence returns terminal INDETERMINATE / MAY_HAVE_OCCURRED / no retry;
23. later preflight reconciles consumed + exact final without creating a new
    attempt;
24. later preflight never turns consumed + partial/absent final into retry
    authority;
25. old D1S3/R5 latches/reports/staging object are not read as D1S4 authority;
26. preserved R5 `.installing` can exist as an unrelated sibling without
    blocking the new release ID;
27. the forward D1S4 module graph cannot import/call retired D1S3/R5 installers
    or publication writers;
28. it cannot import/call historical Architecture-125/133 rename publication
    operators;
29. no D1S4 forward module contains/calls FileRenameInfo,
    SetFileInformationByHandle for rename, MoveFile*, os.rename/os.replace,
    Path.rename/Path.replace, alias/junction publication, or equivalent;
30. new native writer exposes no publish/rename/move/delete/cleanup/rollback API;
31. unified runner D1S4 preflight is read-only against production and serializes
    closed diagnostic fields;
32. unified runner execute dispatch requires the exact D1S4 authorization
    interlock and cannot dispatch D1S3/R5;
33. every unrelated protected-effect counter remains zero;
34. no successor-root, scheduler, credentials, provider, paper, broker, D1/D2,
    or live capability is reachable;
35. accepted historical R5/D1S3 blobs remain unchanged except unavoidable
    source-owned inventory/pin overlays outside their behavioral bodies.

## Focused commands

Use an isolated verification environment with a fresh external pytest base. Run
the new D1S4 test module plus directly affected retained release/runtime/runner
tests. Include combined:

- `ruff check --no-cache`;
- `ruff format --check --no-cache`;
- `git diff --check`.

Do not use `--fix`.

Exact focused counts and paths follow below.

## Canonical source gate

The exact D1S4 checkpoint is registered in `CI_CERTIFICATION_PROFILES` as
`robinhood` before the single intended feature push.

The terminal feature push owns canonical ROBINHOOD certification. Do not run an
identical local canonical profile first or afterward.

Expected route:

    source-static
    -> active-tests
    -> certification-tests: ROBINHOOD
    -> source-gates

The 300-second canonical hygiene ceiling remains unchanged.

Any failed CI attempt is preserved. Do not rerun unchanged. Any mechanical C1
requires ChatGPT classification/review before another push.
Semantic/native/authority uncertainty returns to ChatGPT immediately.

## Handoff evidence

The final implementation handoff must include:

- exact branch/worktree/base;
- final HEAD/TREE/direct parent;
- commit count above base;
- exact changed paths;
- exact new D1S4 module/test/checkpoint names;
- exact attempt schema/path template and execute interlock;
- focused test/Ruff/diff results;
- terminal CI run/attempt and canonical ROBINHOOD totals/wall time/artifact;
- confirmation that no protected D1S4 preflight/execute ran;
- confirmation that D1S3/R5 incident evidence was not mutated;
- clean worktree/index and matching remote branch.

Next owner after implementation is ChatGPT exact GitHub review. Only after
SOURCE ACCEPTED and integration may ChatGPT separately review the registered
real-host read-only D1S4 preflight.

## Completed local implementation evidence

This source checkpoint contains the two D1S4 modules, the registered
`arch134-f1r1-d1s4-rename-free-direct-installation` dispatcher, explicit CI-owned
ROBINHOOD mapping, forward import/call/primitive guards, and exact
predecessor-preserving blob/AST/checkpoint inventory overlays. Existing D1S3/R5
behavioral source is unchanged. Current operator examples now identify D1S4.
Every affected current topology/count assertion was updated; historical timing
model assertions still certify their exact predecessor inventory, while the
current inventory must automatically include D1S4 with the existing fallback
weight and unchanged lane algorithm. No required baseline tuple changed.

Branch:
`feature/robinhood-production-paper-134f1r1-d1s4-rename-free-direct-install-current`

Worktree:
`F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-d1s4-rename-free-direct-install-current`

Base/direct parent: `1e9b6a0638f00ddb009bdb7934039b7a9047e678` / tree
`1ef95f954cfce509a6b90639b8bb9599e2e9206f`. The final implementation is one
normal commit above that base, followed by one ordinary first push. The exact
post-commit identities and terminal CI facts belong in the final handoff, per
the user's explicit resolution of pre-commit self-identity/future-CI recording.


Attempt schema: `arch134-f1r1-d1s4-rename-free-direct-install-attempt/v1`.
Derived path:
`F:\AI\temp\arch134-f1r1-d1s4-direct-install-attempt-<release-id>.json`.
Source interlocks: `AI_TRADING_BOT_ARCH134_F1R1_D1S4_ACCEPTED_HEAD` and
`AI_TRADING_BOT_ARCH134_F1R1_D1S4_ACCEPTED_TREE`.
Execute interlock: `AI_TRADING_BOT_ARCH134_F1R1_D1S4_DIRECT_INSTALL_AUTHORIZATION`
= `ARCH134_F1R1_D1S4_ONE_RENAME_FREE_IMMUTABLE_RELEASE_INSTALL_AUTHORIZED`.

### Focused results

**1,622 unique focused cases are green**, including all **121 D1S4
cases**. Final effective results: 0 failed, 0 errors, 0 skipped. No full suite,
local canonical ROBINHOOD, or local FULL certification ran.

Verification was split to avoid rerunning unchanged successful behavior:

- The 13-module release/runtime/runner/pin-consumer run recorded 1,603 passed
  and two stale current-inventory assertions. The failures were preserved and
  corrected before publication; their replacements are included below.
- The final affected current-inventory/authority recheck passed 24 cases in
  39.83 seconds, including those two replacements and the directly affected
  inventory assertions elsewhere.
- The final graph/invocation/authority recheck passed 31 cases in 10.17 seconds;
  its 90 unselected D1S4 cases were already green in the behavior gate.
- Whole-repository `ruff check --no-cache .`,
  `ruff format --check --no-cache .`, and `git diff --check`: PASS.
  Both Ruff phases execute before the combined gate decides failure; no
  Ruff `--fix` was used. Formatting occurred only as an explicit source-edit
  step before the final non-mutating gate.
- The exact D1S4 source-authority/graph check passes. Historical D1S3/R5
  behavioral blobs and all predecessor pin dictionaries/digests are preserved.

The first broad focused run used this exact module list with `python -B -m
pytest -q`, fresh `--basetemp`, external `--junitxml`, `-p no:cacheprovider`,
`--tb=short`, and bounded failure output:

- `tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py`
- `tests/runtime/checkpoint_runner/test_core.py`
- `tests/runtime/checkpoint_runner/test_ci.py`
- `tests/scripts/certification_runner/test_profiles.py`
- `tests/scripts/certification_runner/test_lanes.py`
- `tests/review_paper/test_supervised_release_foundation.py`
- `tests/review_paper/test_supervised_release_bundle.py`
- `tests/review_paper/test_supervised_release_installation.py`
- `tests/review_paper/test_supervised_runtime_host_admission.py`
- `tests/review_paper/test_supervised_release_installation_operator.py`
- `tests/review_paper/test_arch134_f1r1_b_host_qualification.py`
- `tests/review_paper/test_arch134_f1r1_d1s3_successor_installation_operator.py`
- `tests/review_paper/test_successor_publication_recovery.py`

The 17 additional/replacement inventory functions are listed in the external
`F:\AI\temp\d1s4-final-targets-8b2bf88a90644779b7dfde54b7d17bd9.txt`.
Tools were isolated from the stale main checkout in
`F:\AI\temp\d1s4-source-tools-8b2bf88a90644779b7dfde54b7d17bd9` (pytest 8.4.2,
Ruff 0.17.2). Source provenance is this explicit worktree; pytest uses the
repository's `pythonpath = ["src"]` and Python's `-B` option.

Final JUnit/log evidence:

- `F:\AI\temp\pytest\d1s4-focused-final-f1c05756d9da4c36962d616fe624930c`
- `F:\AI\temp\pytest\d1s4-inventory-recheck-746d6f067f8c4215b00260a95ea4806b`
- `F:\AI\temp\pytest\d1s4-authority-final-3edc0e28936e41518cf7155ecc1555ac`

The earlier stopped local runs remain preserved at
`F:\AI\temp\pytest\d1s4-focused-097a372b536445d1b2bf43103a61bbca` and
`F:\AI\temp\pytest\d1s4-inventory-final-3da2820296e04b0d8651d578381c9c83`.
They exposed stale current inventory/profile assertions and were corrected with
focused rechecks. These are local development evidence, not CI attempts.

### Exact changed paths

- `.github/workflows/checkpoint-source-gates.yml`
- `AGENTS.md`
- `docs/AI_DEVELOPMENT_WORKFLOW.md`
- `docs/AI_TRADING_BOT_HANDOFF.md`
- `docs/PROJECT_STATUS.md`
- `docs/architecture/134-f1r1-d1s4-rename-free-immutable-release-installation.md`
- `docs/validation/arch134-f1r1-d1s4-rename-free-immutable-release-installation-plan.md`
- `scripts/checkpoint_runner.py`
- `src/trading_bot/supervised_release/successor_direct_installation.py`
- `src/trading_bot/supervised_release/successor_native_direct_write.py`
- `tests/review_paper/test_arch133_closed_descendant_rename_qualification.py`
- `tests/review_paper/test_arch133_reprovision_reconciliation.py`
- `tests/review_paper/test_arch133_reprovision_recovery.py`
- `tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py`
- `tests/review_paper/test_arch133_windows_rename_qualification.py`
- `tests/review_paper/test_arch134_f1r1_d1s1_successor_soak.py`
- `tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py`
- `tests/review_paper/test_d1_session_authorization.py`
- `tests/review_paper/test_d1_session_execution.py`
- `tests/review_paper/test_five_session_soak.py`
- `tests/review_paper/test_pre_market_wake_overnight.py`
- `tests/review_paper/test_production_strategy_cycle.py`
- `tests/review_paper/test_supervised_deployment_qualification.py`
- `tests/review_paper/test_supervised_maintenance_rebind.py`
- `tests/review_paper/test_supervised_release_installation.py`
- `tests/review_paper/test_supervised_runtime_host_admission.py`
- `tests/runtime/checkpoint_runner/helpers.py`
- `tests/runtime/checkpoint_runner/test_ci.py`
- `tests/runtime/checkpoint_runner/test_core.py`
- `tests/scripts/certification_runner/test_lanes.py`
- `tests/scripts/certification_runner/test_profiles.py`
- `tests/strategies/test_production_strategy_contract.py`
- `tests/strategies/test_production_strategy_decision.py`

### Terminal feature evidence and exclusions

The source-owned route is source-static -> active-tests -> canonical ROBINHOOD
-> source-gates. The static current selected inventory has 111 ROBINHOOD modules
in unchanged four-lane semantics; the required 49-module baseline is frozen.
Canonical cases/pass/skip/fail/error/wall/artifact and run/attempt are pending the
single feature push and must be reported from actual terminal CI evidence, never
predicted. No failed feature CI attempt exists before publication.

No real D1S4 production preflight or execute occurred. No production authorization
interlock was set against the real host; execute tests used fully injected
fake-host seams. No object under `F:\AITradingBot\releases` was created or
inspected by an operator command. D1S3/R5 latches, reports and incident namespace
were untouched. The main checkout was not used, changed, synchronized or cleaned.
No successor-root, scheduler/service/startup, runtime-start, credential/provider,
paper/broker, D1/D2 or live effect occurred. Live remains NO-GO.

Host/native acceptance remains a separately reviewed later boundary. ChatGPT owns
exact-source acceptance and all subsequent integration/host decisions. After the
terminal feature run, Codex returns the exact identity/CI/clean-state handoff and
stops without merge, rebase, amend, force-push, PR mutation or protected effects.

Also remove or update any tests and docs that referenced the old behavior.
