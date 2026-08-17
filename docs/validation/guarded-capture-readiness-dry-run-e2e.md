# Guarded capture-readiness dry-run E2E validation

## Environment and boundary

- Repository: `F:\AI\ai-trading-bot`; branch: `develop`; Windows `.venv`.
- Ignored validation root: `reports/local-guarded-capture-readiness-validation/`.
- All runs were foreground with explicit, non-secret timestamps and process
  evidence. No production authority root or existing operation evidence changed.
- No provider, credential, network, snapshot capture, paper operation,
  transition, head advancement, Task Scheduler, notification, cleanup, or repair
  was invoked.

The root contains `baseline/authority`, explicit `inputs`, and isolated
`scenarios/<name>` directories. The runner only created files under each
scenario's `audit/lock-events` and `audit/readiness-decisions` directories.

## Commands

```text
.venv\Scripts\python.exe scripts\initialize_local_lineage_head.py --help
.venv\Scripts\python.exe scripts\verify_local_lineage_head.py --help
.venv\Scripts\python.exe scripts\evaluate_guarded_capture_readiness.py --help
.venv\Scripts\python.exe scripts\test_windows_launch_guard.py --help
.venv\Scripts\python.exe scripts\verify_local_lineage_head.py --authority-root reports\local-guarded-capture-readiness-validation\baseline\authority
.venv\Scripts\python.exe scripts\evaluate_guarded_capture_readiness.py --config reports\local-guarded-capture-readiness-validation\scenarios\<scenario>\config.json
```

The baseline used the existing verified genesis/checkpoint/lineage fixture helper
and `initialize_local_lineage_head`; no authority evidence was hand-authored.
Hours, policy, and failed-attempt inputs came from public canonical serializers.

## Authority baseline

`verify_local_lineage_head` returned `PASS` / `NONE` for epoch
`e1a615c4-4ca8-5e28-9362-51f081c2e167`, generation 0, head
`d47971c8-20a5-5b70-a2bb-94c31a617563`, lineage
`0d1cd3de-52bb-54a3-9663-6039658e20fb`, and terminal
`b26154dc-5895-5f9e-8d67-758e93da63c7`.

| Artifact | SHA-256 | bytes |
| --- | --- | ---: |
| current pointer | `67f5822f9ab6e89f5e24563e3f9de8d8b404d97612f18659af87812f221cd4c1` | 270 |
| head record | `276fecf51a47646d15eea8fb08485c57db235f86ca3d20cee50e90baf6a8c826` | 799 |
| lineage manifest | `fd7c9f513d0744afe876f37ce7342cbce711ee6e3575ee97fa64d4fa369ff696` | 497 |

The three hashes were unchanged after all scenarios. Hours input: 673 bytes,
`f1799d31cb949f5ff5fcb54e6718ac3fa6c96e74fdc1a59822cabc8b520a3d5c`.
Policy input: 614 bytes,
`3b90d2ed2a169afaf5bc0782a285f8cd5e1903d5ea23b10a97a035fcb36bf909`.

## Scenario results

| Scenario | Classification / diagnostic | action and proposal | exit | evidence |
| --- | --- | --- | ---: | --- |
| baseline | `PASS` / `NONE` | n/a | 0 | pointer, head, lineage verified |
| too early, `17:04:59Z` | `NOT_READY` / `CAPTURE_TOO_EARLY` | `WAIT`; none | 0 | start, decision, release |
| first window, `17:10:00Z` | `READY` | allowed; ordinal 0, `bc004bda-3a45-599f-97c6-1bddfbacf180` | 0 | start, decision, release |
| retry backoff | `NOT_READY` / `CAPTURE_BACKOFF_ACTIVE` | `WAIT`; none | 0 | start, decision, release |
| retry window | `READY` / `SNAPSHOT_INELIGIBLE` | allowed; ordinal 1, `430f16a9-a313-51d2-a050-2c9531b49c5e` | 0 | start, decision, release |
| attempts exhausted | `BLOCKED` / `CAPTURE_ATTEMPTS_EXHAUSTED` | `NONE`; none | 4 | start, decision, release |
| deadline expired | `BLOCKED` / `CAPTURE_WINDOW_EXPIRED` | `NONE`; none | 4 | start, decision, release |
| manual disable | `BLOCKED` / `MANUAL_DISABLE_ACTIVE` | `NONE`; none | 4 | start, decision, release |
| altered hours, original hash | `BLOCKED` / `HOURS_ARTIFACT_INVALID` | `NONE`; none | 4 | start, release; evaluator not reached |
| wrong epoch | `BLOCKED` / `HEAD_VERIFICATION_FAILED` | `NONE`; none | 4 | start, release; no decision |
| held mutex | `NOT_READY` / `GUARD_ALREADY_HELD` | `WAIT`; none | 9 | losing process wrote nothing |
| abandoned owner | `MANUAL_REVIEW_REQUIRED` / `GUARD_ABANDONED` | `MANUAL_REVIEW`; none | 8 | abandoned start and `NOT_RUN` release only |
| decision conflict | `READY` + `DECISION_PUBLICATION_FAILED` | `NONE`; proposal suppressed | 7 | release published; conflict preserved |
| release-publication fault | `MANUAL_REVIEW_REQUIRED` / `LEASE_RELEASE_PUBLICATION_FAILED` | `MANUAL_REVIEW` | 7 | native release attempted; reacquisition passed |
| crash-left staging | `READY` + `DECISION_PUBLICATION_FAILED` | `NONE`; proposal suppressed | 7 | staging and release preserved |

The held and abandoned tests used the controlled Windows child-process mutex
method from the integration tests. The abandoned owner held the exact mutex while
the runner waited, then exited without releasing it. A short initial attempt in
which the owner exited before the contender started produced normal acquisition;
it was excluded from the abandoned result.

The selective release-publication fault was injected at the production release
publisher while retaining the real Windows mutex and isolated audit root. A
static malformed release file cannot test release only because lease-start
directory validation correctly rejects it first. A subsequent independent normal
CLI run acquired the mutex and published the missing release evidence.

## Determinism and inventory

The READY configuration ran three times with byte-identical inputs. Every run
returned session `e2fc8710-71c5-56b8-ab7f-fac023c5ec74`, launch
`82ac639d-cc55-50e8-88b9-c42f0c4e5303`, decision
`79d593ca-bb37-5e36-b4bb-bbe8932a3b4b`, and proposed attempt ordinal 0 / ID
`bc004bda-3a45-599f-97c6-1bddfbacf180`. Its decision stayed 1,604 bytes with
SHA-256 `469349b5ce432dd574b2f07b0e38c39d73c47e417a87f4503ca7629395d17780`.
No duplicate or alternate filename appeared.

Before each scenario the audit root was empty except for deliberately copied
conflict/staging evidence. Afterwards it contained only documented immutable
lease/decision evidence and the intentionally preserved failure artifact. The
only validation snapshot and operation dependency are baseline fixture inputs;
their bytes remained unchanged. Repository-level snapshot, cycle, and checkpoint
inventory remained 9 files. Explicit failed-attempt JSON files are scenario
inputs; no runner allocated an attempt record, snapshot, receipt, transition, or
authority artifact.

## Evidence verification

Production parsers reread 39 canonical final audit artifacts successfully. The
single deliberately substituted decision final failed parsing and remains
preserved; the crash-left staging file is not a final artifact and remains
preserved. Repeated files with the same ID below have exactly the listed bytes.

| Kind | ID | SHA-256 | bytes | classification / diagnostic |
| --- | --- | --- | ---: | --- |
| start | `61254ef2-2756-5053-b050-f0ec2e7b5e2c` | `3c957ad3670cc771ba7b06752b98b2af2d1f5db9f5cc4fcea319f3b44611b278` | 887 | `ACQUIRED` |
| start | `18bd20cb-d400-5fd9-b216-e174c68cfe94` | `e822ae883c3bde56d2c58aa6c1cc5f0e7dae8a9b048eab84706dfcb5dd8fc2ac` | 897 | `ABANDONED_ACQUIRED` |
| start | `f87ad1f2-4530-5078-9aae-b98fa9b9924d` | `795c969bb12085433647e37ed4140b22dd87a67d6a1b157e724b8d9036a502b9` | 887 | wrong-epoch config |
| release | `97a0b6b1-8e06-5449-aa46-04a4c8eff6c1` | `bd1957ada907c5c09fd569891fdad72a4bc71c9136635379467a4cb571e6b499` | 610 | `SUCCESS` / `READY` |
| release | `80bf109f-8b8a-5018-88ee-65e96ca7134d` | `7c193195d1706f751e2dd70e9d617b10f371fffa97e1ff35f8183ac8251aedf7` | 614 | `SUCCESS` / `NOT_READY` |
| release | `8165a492-b07c-5763-934a-b8671ba1bd57` | `f697395a7d4e67829d3ace82219b63125679dd04ebad9950566eea53581162bb` | 612 | `SUCCESS` / `BLOCKED` |
| release | `2ec018e1-6251-586b-b924-5e5e9b0787c9` | `0598c0b5bc87d0dac4047ab96afe265289ccad0cd7e003c0fb0dfac7bd3f024a` | 627 | `FAILURE` / hours invalid |
| release | `9bf08981-889a-591b-b4d8-1b02e30d986a` | `9ea7f14efb5a64610bbaf8c04aec8499a9117f0c4438b3323dbdd5ca3cada912` | 629 | `FAILURE` / head invalid |
| release | `0bd68cbd-2ed2-565f-a02c-147da8d771c6` | `2a28e6bd6e06f2050bf11022689aa0f32798f8274fc2ff4516f11dea87eb3fbc` | 632 | decision publication failure |
| release | `8583b3f8-df54-508e-b0a6-119d13a5d667` | `87d33dcb78da4d76d6c0a97342f89bcae0a562bbd83743c56d4a63044a858b6f` | 620 | `NOT_RUN` / abandoned |
| decision | `71b019ec-09f2-50a6-9078-8a257da2e1c8` | `6ca21b63a6acd5ce3f09146a019f83a731fd97085803300e54f906e829af684b` | 1578 | too early |
| decision | `79d593ca-bb37-5e36-b4bb-bbe8932a3b4b` | `469349b5ce432dd574b2f07b0e38c39d73c47e417a87f4503ca7629395d17780` | 1604 | ready |
| decision | `f4d44481-d6d0-547e-9e0b-69895ad4f1cf` | `9dba08fa395df89055b2a8cfbadc1eb76c1cea35ccce450be4622a526b5e684e` | 1731 | backoff |
| decision | `74d4cf0f-585e-504b-aef7-adf8058d803e` | `9d4d9a072bbad999e9d8469221826782c7bbb5b7a04c750d9788a9fe400aeb98` | 1773 | retry ready |
| decision | `11123466-3403-54c3-b67d-eb0ca0ba051e` | `499e70fbf7a6ad4a2cb651157f5686b87d3d71ad1a1562715e3c82601220ac82` | 1882 | exhausted |
| decision | `0ff12890-22b7-5350-b6f6-2d27d468aa06` | `98f2c5e1b3712f52e8bf075f5b4f239f025a70829c1f91a387f296801f7b05c5` | 1581 | expired |
| decision | `abc8fb67-1613-56aa-9045-f07f6e55b91e` | `f8d11ab1aa31408619dde2e7d235245b39973f970f8e8432b5f39f29afc7c69d` | 1580 | manual disable |

## Test and quality-gate results

```text
.venv\Scripts\python.exe -B -m pytest tests\runtime\test_guarded_capture_readiness.py tests\cli\test_guarded_capture_readiness_config.py tests\cli\test_guarded_capture_readiness.py tests\scripts\test_evaluate_guarded_capture_readiness.py -q
.venv\Scripts\python.exe -B -m pytest tests\runtime\test_scheduled_readiness.py tests\runtime\test_launch_guard.py tests\cli\test_windows_launch_guard.py tests\cli\test_windows_launch_guard_integration.py tests\runtime\test_local_lineage_head.py tests\cli\test_local_lineage_head.py tests\cli\test_daily_snapshot_config.py tests\cli\test_daily_snapshot_capture.py -q
.venv\Scripts\python.exe -B -m pytest -q
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```

Results: focused guarded dry-run tests **26 passed**; related guard, readiness,
lineage-head, and safe-output tests **111 passed, 3 skipped** (platform symlink
availability); full suite **1833 passed, 8 skipped** (the existing platform
symlink availability cases). Ruff check passed, Ruff format check reported 343
files already formatted, and `git diff --check` passed.

## Deviations and recommendation

No production defect was exposed. All invalid authority/readiness/output and
mutex states failed closed. Residual approved risks remain: trusted-clock
acquisition, official-hours governance, verified mutex DACL, provider and
credential boundary, provider-response validation, retry execution, backup,
notification, scheduler integration, and recovery policy.

Recommendation: **NO-GO** for bounded capture-only provider invocation. The
dry-run gate is validated, but the separate provider/credential and operational
policy milestones still require explicit approval and implementation.
