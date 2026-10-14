# Architecture 138 / RCL-2 — Current-lineage forward-port validation

Status: IMPLEMENTED; focused authority verification, terminal repository CI and
ChatGPT exact-source review pending. No source acceptance is claimed.

## Provenance and fixed contract

Exact parent HEAD `7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343`, TREE
`c826c2a71e6d907866ce3f80afce479d38ab7842`. Branch:
`feature/research-candidate-walk-forward-qualification-current`. Worktree:
`F:\AI\worktrees\ai-trading-bot-research-candidate-walk-forward-qualification-current`.

Historical accepted reference: HEAD
`e0735af265894757ff9b90ab185bcbd77ee2dee9`, TREE
`a29f51faaa81e866d0825ffbe082c5fcddb94584`, source gate #516 /
[38380502369](https://github.com/callmedraken/ai-trading-bot/actions/runs/38380502369).
No stale branch is merged, rebased or cherry-picked. The research implementation,
domain tests and initializer retain the exact accepted blobs. Their four upstream
research dependencies match the historical parent exactly.

The [Architecture-138 contract](../architecture/138-research-candidate-walk-forward-qualification.md)
freezes schemas, UUID5 namespaces, framed identities, Decimal canonicalization,
failure ordering, all-fold selection, equal test windows, one aggregate analyzer
call, independent verification and the immutable WALK_FORWARD_PASSED successor.
There is no SHADOW, generic stage mutation, automatic selection, rank authority,
production conversion or promotion capability.

## Focused checks and evidence

The requested five-module domain set passed **305 cases** in 10.40 seconds,
including the 128 accepted Architecture-138 cases. Coverage includes exact frozen
types, identity sensitivity, Decimal/context independence, strict canonical JSON,
forgeries, independent external reconciliation, rank-one/rank-two/unranked
predecessors, mixed winners, malformed provenance, defensive copying, both window
dimensions, inclusive thresholds, all six failures and one analyzer invocation.
Fixtures use in-memory fake simulators, with zero real research execution.

Use the existing environment, `-B -p no:cacheprovider`, and a fresh external
basetemp under `F:\AI\temp\pytest\arch138-current-<GUID>` per invocation.
No dependency installation or local broad certification is required.

```powershell
& {
    $TempRoot = 'F:\AI\temp\pytest\arch138-current-' + [guid]::NewGuid().ToString('N')
    & F:\AI\ai-trading-bot\.venv\Scripts\python.exe -B -m pytest -q --tb=short -p no:cacheprovider --basetemp $TempRoot tests/experiments/test_research_candidate_walk_forward.py tests/experiments/test_research_candidate.py tests/experiments/test_report.py tests/experiments/test_walk_forward.py tests/experiments/test_walk_forward_analytics.py
    if ($LASTEXITCODE -ne 0) { throw 'Architecture 138 domain tests failed' }
}
```

Affected inventory/authority checks include certification_runner/test_profiles,
production strategy contract/decision/cycle, supervised deployment qualification,
supervised runtime host admission, supervised maintenance rebind, production
paper runtime/ACL, pre-market wake qualification and Alpaca authentication
qualification. Fake source/clock/credential/effect edges and temporary evidence
are mandatory; no real host qualifier is invoked.

Initial pin-focused verification passed seven cases and failed two solely on
eleven stale predecessor test-blob comparisons. The failure evidence is retained.
New successor tests freeze accepted predecessor dictionary digests, preserve
unmodified D1R5 test blobs, and reject missing/extra-executable overlay entries
and changed test blobs. Authority verification must PASS before publication.

Run both non-mutating Ruff phases over all touched Python paths before deciding
PASS/FAIL: `ruff check --no-cache` and `ruff format --check --no-cache`. Emit the
respective `--diff --no-cache` diagnostics on failure. An initial import-order
failure was diagnosed this way and corrected by an explicit source edit. Run
`git diff --check` before staging. No local FULL/ROBINHOOD/LEGACY/EXHAUSTIVE gate.

The affected inventory/authority run initially had **672 passed / 3 failed** in
19.10 seconds. The three failures reported the same eleven stale test-blob
comparisons. Automatic approval review initially rejected successor resolution
in the D1R4R/D1R4/D1R3 validation loops; the user then explicitly approved exactly
one test-only successor resolution call after each existing D1R5 resolver.
Those calls are now implemented. All three failures and the predecessor/fail-closed
regressions passed on an **11-case focused rerun** in 7.92 seconds. No remaining
drift was reported. Final distinct coverage is **980 passed**: 305 domain plus
675 inventory/authority cases; duplicate rerun cases are not added to this total.
Ruff lint/format PASS (11 Python files), and tracked diff check PASS.
No historical dictionary, executable/native/AST pin or operational authority
was changed by the approved resolution calls.

## Inventory and narrow successor pins

Canonical discover_inventory/select_inventory and ACTIVE_CI_CHECKPOINTS produce:

| Inventory | Before | After |
| --- | ---: | ---: |
| ACTIVE | 64 | 64 |
| FULL | 175 | 176 |
| ROBINHOOD | 98 | 98 |
| LEGACY | 215 | 215 |
| EXHAUSTIVE | 390 | 391 |
| tests/gui | 44 | 44 |

All seven changed count assertions call live discovery. The strategy tests also
had stale ACTIVE 62 / ROBINHOOD 94 assertions; these become 64 / 98. Historical
checkpoint evidence, architecture records and immutable history are untouched.

ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES is a separate exact seven-test
successor of D1R5 test resolution. No predecessor dictionary is rewritten.

| Test path | Successor Git blob |
| --- | --- |
| tests/scripts/certification_runner/test_profiles.py | a3512cef7de7c2482c649f43f4e9c4b00c62c403 |
| tests/strategies/test_production_strategy_contract.py | 5cee9a1c55618c06b478ffb2e792a7648c6f5e4c |
| tests/strategies/test_production_strategy_decision.py | 8c5330f855b44cd63c3dfc99e3b2f5565b55bd9f |
| tests/review_paper/test_production_strategy_cycle.py | 3dab5e5f166a9fc4d7893ed20741e627a95e035c |
| tests/review_paper/test_supervised_deployment_qualification.py | f67561da61aab33d295538689c75225bbd690bc8 |
| tests/review_paper/test_supervised_runtime_host_admission.py | 62617f9f9fbab1c90a8b2d84482220caee98796f |
| tests/review_paper/test_supervised_maintenance_rebind.py | 52b1fd4e3257976e3d5014d0af1aecde62da7ee0 |

AST comparison confirms all existing Architecture-134 constants, including pin
dictionaries/import sets, and ACTIVE/CI-profile tuples remain unchanged.
Executable/native/AST pins, D1R5 registration/zero-effect contract, workflow bytes,
upstream identities/report bytes and tracked fixtures remain frozen.

## Publication and review boundary

Only after focused/static checks PASS: prove a clean initial index, exact-file
stage, verify staged path set and cached diff check, create one normal checkpoint
commit and ordinary-push this branch. Verify exact remote HEAD/tree. Workflow
bytes remain unchanged; dispatch exactly one fresh Checkpoint Source Gates run
on the exact branch. Require terminal source-static and applicable broad shards
PASS, each shard below 300 seconds. Preserve failures; no blind retry.

STOP after terminal CI and return identities, changed paths, inventory,
focused/static/pin/CI results and zero effects for ChatGPT exact GitHub review.
Source acceptance and bounded status/handoff closeout occur only afterward.
Both bounded current documents were reviewed and remain unchanged during this
implementation; no cumulative narrative is appended.

## Zero-effect accounting

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
STRATEGY_PROMOTIONS=0
PRODUCTION_CONTRACTS_CREATED=0
D1_OPERATIONS=0
D1R5_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

Fake-edge tests and in-memory analytics grant no protected authority. No production
artifact/store, host qualification or operational worktree is accessed.
Real-money placement remains **NO-GO**.
