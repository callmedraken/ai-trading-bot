# Architecture 134-D1R7 source verification

Source-only checkpoint, pending exact GitHub review. All evidence in tests is
synthetic and temporary. Never open real retirement evidence or invoke the helper,
preflight, delete, task run, D1R5, credentials/providers or trading during testing.
Only PowerShell parser syntax inspection is permitted on the helper.

Focused tests cover literal production incident pins; exact source/target/frozen
worktree gates; consumed seven-event parsing inherited from R3; every canonical
projection field; principal, state/result/last-run/no-next-run drift; all absence
predicates; interlock; durable intent before native entry; one-call maximum;
pre-entry rejection vs post-entry ambiguity; two absent confirmations and task
reappearance; journal write/flush/fsync/close uncertainty; no rerun; reconciliation
requiring both durable authority and actual absence; immutable original incident;
fixed binary transport, closed modes, no child/provider/credential/trading seams.

Use the repository venv Python and an external disposable pytest base directory:

```powershell
& F:\AI\ai-trading-bot\.venv\Scripts\python.exe -B -m pytest -q -o addopts= --basetemp F:\AI\temp\arch134-d1r7-focused tests/review_paper/test_pre_market_wake_retirement.py tests/review_paper/test_pre_market_wake_overnight.py tests/review_paper/test_pre_market_wake_qualification.py tests/review_paper/test_nyse_published_regular_sessions.py tests/runtime/checkpoint_runner/test_core.py tests/runtime/checkpoint_runner/test_ci.py tests/scripts/certification_runner
```

Run relevant Ruff check and format --check with --no-cache; run both phases,
collect both statuses and emit non-mutating --diff for each failed phase before
stopping. Run git diff --check. Parse PowerShell AST only, never dot-source or
execute helper statements. Preserve existing D1R5/D1R6 source-pin coverage.

The new checkpoint `arch134-d1r7-stale-wake-retirement` uses the existing reviewed
ops.ps1/source-gate machinery and maps to ROBINHOOD. Shared test changes are only
registration/count expectations; the successor overlay binds each frozen old
blob to its one new test blob and freezes predecessor dictionaries by digest.
FULL/ROBINHOOD/LEGACY/EXHAUSTIVE inventory is 177/100/215/392. The workflow file
is frozen. Check attempt 1 exact pushed HEAD, all jobs, canonical JUnit totals,
canonical wall <300 seconds, full-tests SKIPPED; do not blindly retry CI.
No duplicate full local certification is needed after valid mapped CI evidence.

Implementation real-host counters must all be zero:
REAL_RETIREMENT_PREFLIGHTS, REAL_RETIREMENT_ATTEMPTS, REAL_TASK_DELETE_ATTEMPTS,
REAL_TASK_CREATE_ATTEMPTS, REAL_TASK_RUNS, REAL_D1R5_EXECUTIONS, D1_OPERATIONS,
D2_OPERATIONS, LIVE_EFFECTS. Also zero scheduler Observe calls and retirement
evidence creations on the real qualification parent. Confirm original live D1R6
worktree remains clean at 3cf4284d017e362eee58a2f27526ab4de8f292a2 /
16a48a12756bb6d810799444859334ce6305001d before publication and at handoff.
Stop for ChatGPT review, with no October 16 wake or host cleanup.


## Retained compatibility diagnostic

The optional expanded runner-directory check found 3,043 passes and one failure:
test_retained_individual_verification_exercises_registered_source_contract
in tests/runtime/checkpoint_runner/test_retained_arch128_130.py:946 assumes
calls[0] contains pytest arguments, while the registered sequence starts with
git_diff_check. Re-executing that one test with the exact canonical-base runner
reproduced the same failure (one failed, 0.41s). The test/module is LEGACY and
EXHAUSTIVE only, absent from FULL, ROBINHOOD and the new active checkpoint.
No retained source/test is changed. This is an existing compatibility limitation,
not a current-product source-gate failure. Final focused commands above select
the affected current runner modules; do not rerun the entire directory for D1R7.


## Diagnosed registration correction

The first D1R7 publication at 9119087feb72ee02f70e6fc95fda9d733c925ccd
has source-static PASS but Checkpoint Source Gates #575 / 38804913747 active
tests failed (2,758 passed, ten failed). Those ten tests freeze predecessor
active-count/suffix-position/profile-count expectations. The initial focused
selection missed those existing modules. All D1R7 behavioral cases passed.
This source is not accepted. No CI retry is authorized or used.

The corrective checkpoint updates only the ten failing registration tests and
the closed test-only successor blob overlay. Active count is 66; tuple positions
before the inserted D1R7 entry shift by one; inventory remains 177/100/215/392.
Predecessor pin dictionaries, executable code, workflow and native authority stay
unchanged. Run the exact ten failed tests plus successor authority/profile checks,
commit normally, then require a new exact-head attempt-1 source gate. This is a
diagnosed source correction, not a rerun of the failed source.


The second exact-head event #576 / 38805652240 at
3ac4e3b8c50296d3cc99a66e56ae712745dd5b15 passed 2,767 active tests and failed
one D1R6 assertion that compared the final resolved blob directly to its frozen
pre-D1R7 override. The corrective test now independently requires the successor
pair's before value to equal that frozen D1R6 pin and the resolved value to equal
the exact successor after value. The frozen predecessor maps/digests are unchanged.
Run the full D1R6 and D1R7 modules and predecessor-pin checks before normal
publication. No CI attempt is rerun; each diagnosed correction is a new source
commit. Retirement executable/PowerShell blobs remain those of the first commit.
