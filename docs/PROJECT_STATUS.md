# AI Trading Bot - Project Status

## Current phase

Architecture 134-D1R6R1 process-scoped PowerShell transport correction is
**SOURCE ACCEPTED**. The next protected step is a fresh, separately reviewed
**read-only real-host D1R6 preflight**. No Task Scheduler mutation or D1R5
qualification has run.

Accepted corrected D1R6 executable/test source:

```text
branch  feature/robinhood-production-paper-overnight-wake-arming
HEAD    d02510b9dbe6e8d7f803ebadee22f36c51eba929
TREE    8373086ebee2dc6b304d01f67261296a32bffa5a
CI      #568 / 38716877077 / SUCCESS / attempt 1
```

Checkpoint #568 independently passed source-static, 2,429 active tests, and
canonical ROBINHOOD certification with 9,395 passed / 1 skipped / 0 failed /
0 errors in 257.789 seconds. Current inventory remains FULL 176 / ROBINHOOD 99 /
LEGACY 215 / EXHAUSTIVE 391.

The first real-host D1R6 preflight attempt was **read-only and BLOCKED before
principal/Task Scheduler observation** because the host invoked its fixed
PowerShell helper under the machine's default process execution policy. All
D1R6/D1R5 Git identities had matched exactly; no task was created or modified,
no D1R5 execution occurred, and no qualification evidence was consumed.

D1R6R1 corrects only that transport defect. Both the Python-to-scheduler-helper
argv and the future Task-Scheduler-to-launcher action now use the fixed
process-scoped sequence `-NoProfile -NonInteractive -ExecutionPolicy Bypass
-File` against fixed reviewed script paths. It does not use
`Set-ExecutionPolicy`, does not change persistent machine/user policy, and
does not widen scheduler or trading authority.

D1R6 otherwise preserves the accepted D1R5 qualifier and one-session overnight
contract: next eligible published NYSE session within 18 hours, trigger at
regular open minus ten minutes, `WakeToRun=true`,
`StartWhenAvailable=false`, no repetition/restart/demand start/automatic
retry, and no D1/PREPARE/EXECUTE/paper/broker/live continuation.

The fixed external D1R5 target remains:

```text
branch  feature/robinhood-production-paper-premarket-wake-qualification
HEAD    7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343
TREE    c826c2a71e6d907866ce3f80afce479d38ab7842
```

The accepted executable D1R5 source remains
`a7f985c6e4c723fdd4c4a1c49798531ddabe9e4a` /
`9fcbc170e8339e0b4a93844466e8924ff8ef7f36`. Real D1R5
`WAITING_FOR_MARKET` / wake / source-readmission qualification remains unrun.

The canonical bounded history branch remains
`feature/project-history-storage-foundation` at the accepted product-line
boundary; this D1R6/D1R6R1 protected-source lineage does not move product/history
authority by itself.

No fresh D1 session, PREPARE, EXECUTE, paper/broker mutation, D2, or live
trading is authorized.

## Operational checkpoint

The one-shot D1R4 authentication qualification is **PASS / consumed**.

```text
evidence  F:\AI\temp\qualification\arch134-d1r4-auth-234614a21d68680f5b1e0ccd.json
bytes     635
SHA256    100e3590543b8ba36002d50d890578533100035b9f618434dd2c9adc2f3505c4
status    PASS
reason    PASS
HTTP      200
requests  1
source    234614a21d68680f5b1e0ccdb5854347a6a8d090
tree      f70459d91c393c6ea7a4a6358f02a2073b246574
```

The post-auth generation journal SHA-256 is
`344f64a1c421c41174142aa4f30f2574537bb26e70901dd77cf56ec930ec7434`;
its provider-effect fence is now irreversible. Authentication must not be retried.

The accepted fresh `/v3` provisioning effect was executed from:

```text
HEAD  ae19cc933f00445d00f196f7b7963bf01b5433ae
TREE  b361c153035ec1dca3ffacc5c819398239f55da6
```

Its preserved generation journal is:

```text
path    F:\AI\temp\qualification\arch134-d1r4-v3-generation-b206df8a30964c4c9a807d306b54c0b9.json
bytes   4881
SHA256  3cb18e50b821c4f7361b213f2095d148dd18a172f60cdf72255e36838eaa7ce3
schema  alpaca-v3-credential-generation-journal/v1
policy  windows-credential-manager-alpaca-market-data/v3
```

The journal is exactly:

```text
PROVISIONING_RESERVED -> LOCK_ACQUIRED -> EXPECTED_GENERATION
-> INITIAL_STATE_ACCEPTED -> KEY_WRITE_INTENT -> KEY_WRITE_CONFIRMED
-> SECRET_WRITE_INTENT -> SECRET_WRITE_CONFIRMED -> PAIR_CONFIRMED
-> FINAL / LOCAL_EXACT_MATCH
```

The expected UTF-8 lengths are key 26 and secret 44. The only accepted
classification is `LOCAL_V3_PAIR_EXACTLY_PROVISIONED`. There is no
`V3_PROVIDER_EFFECT_INTENT`, no Alpaca/provider request, and no ambiguity.
The provisioning invocation is consumed and must not be rerun. Ordinary fresh
`/v3` provisioning must block because the accepted staging pair exists.

The provisioning record alone did not establish remote authentication, but the
subsequent one-shot D1R4 qualification now does establish
`REMOTE_ALPACA_AUTH_READY` for the fixed accepted probe/source observation.
It does not establish D1 session, paper, D2, broker, or live-trading readiness.

## Completed foundations

- Architecture 131 provides the reviewed Robinhood paper, risk, execution, and
  audit foundation ([architecture/131-robinhood-review-paper-trading.md](architecture/131-robinhood-review-paper-trading.md)).
- Architecture 132 provides the tiered current/legacy certification model and
  source-gate topology ([architecture/132-tiered-certification-profiles.md](architecture/132-tiered-certification-profiles.md)).
- Architecture 133 preserves supervised immutable-release and unattended
  review-paper runtime boundaries ([architecture/133-robinhood-single-session-unattended-review-paper-authority.md](architecture/133-robinhood-single-session-unattended-review-paper-authority.md)).
- Architecture 134 is the current production strategy and AI-research
  authority ([architecture/134-production-strategy-and-ai-research-authority.md](architecture/134-production-strategy-and-ai-research-authority.md)).
- The D1R4 `/v3` provisioning contract and accepted evidence are preserved in
  [architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md](architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md) and
  [validation/arch134-d1r4-alpaca-v3-credential-generation.md](validation/arch134-d1r4-alpaca-v3-credential-generation.md).

## Active work

The immediate boundary is a fresh D1R6 **read-only real-host preflight** against
the corrected D1R6R1 source. It may inspect exact D1R6 and D1R5 Git identities,
the frozen NYSE calendar, current clock, current interactive Windows principal,
the fixed qualification parent, derived evidence absence, and the fixed Task
Scheduler identity read-only.

The earlier preflight failure is not a consumed protected attempt: it stopped at
the PowerShell execution-policy boundary before principal/scheduler observation
and before any scheduler mutation, D1R5 invocation, or evidence reservation.
D1R6R1 fixes only the process-scoped helper/action invocation needed to cross
that read-only transport boundary.

A corrected preflight PASS still does not create or alter a task and does not
invoke D1R5. Only after ChatGPT reviews that output may a later separate
checkpoint authorize at most one fixed Task Scheduler `TASK_CREATE` attempt.
Any mutation-entry ambiguity remains consumed and never retried.

D1R4 authentication remains PASS / consumed. D1R5 remains unrun and grants no
D1 authority until its future canonical result is independently reconciled and
accepted.

## Current blocker / protected boundary

Remote Alpaca authentication is proven for the fixed probe and D1R5 source is
accepted, but the required real pre-market / `WAITING_FOR_MARKET` / wake
qualification has not yet been executed or accepted. No fresh D1 session is
authorized until that protected boundary is complete.
The D1R4 authentication invocation is permanently consumed and must not be
retried. Real-money trading is **NO-GO**.

## Verification and certification posture

Architecture 132 remains the governing posture:

```text
FOCUSED -> SOURCE-GATE CI
-> ChatGPT selects ROBINHOOD or FULL at a coherent current-product boundary
-> LEGACY / EXHAUSTIVE only when explicitly relevant
PROTECTED only at the exact separately reviewed effect boundary
```

Mapped certification remains CI-owned; local repetition of the same valid
profile is not routine. Checkpoint Source Gates #549 accepted the integrated
operational source: static authority and active tests passed, and canonical
ROBINHOOD certification passed 9,065 / 9,066 cases with one skip and zero
failures/errors in 200.417 seconds. Artifact `11875285428` has SHA-256
`02c29f3debd0cf274e85986ab5bd74ebbfc7b9ce9ec234e04fd9d3ad93240b2e`.
Current inventory after accepted D1R5 is FULL 175 / ROBINHOOD 98 /
LEGACY 215 / EXHAUSTIVE 390. The earlier #549 result remains historical
integrated-source evidence. Current D1R5/R3H acceptance is Checkpoint Source
Gates #557 / `38549244176`: static authority PASS, active tests PASS, canonical
ROBINHOOD 9,182 cases / 9,181 passed / one skipped / zero failed/errors, wall
253.493 seconds (below the frozen 300-second hygiene ceiling). FULL covers currently supported
functionality, while LEGACY/EXHAUSTIVE retain explicit historical
compatibility. This acceptance grants no protected authority. See the
[tiered certification profile](architecture/132-tiered-certification-profiles.md)
and [development workflow](AI_DEVELOPMENT_WORKFLOW.md).

## Roadmap

### Now

- Preserve D1R6R1 accepted source at
  `d02510b9dbe6e8d7f803ebadee22f36c51eba929` and its frozen D1R5
  predecessor/workflow blobs.
- Run exactly one fresh **read-only real-host D1R6 preflight** from the final
  accepted docs descendant and review its output.
- Keep Task Scheduler mutation, D1R5 execution, D1, PREPARE, EXECUTE, paper,
  broker, D2, and live effects stopped during preflight.
- Keep persistent Windows execution policy unchanged; D1R6R1 uses only the
  reviewed process-scoped `-ExecutionPolicy Bypass` child invocation.
- Keep `feature/project-history-storage-foundation` on the accepted product
  lineage until a separately reviewed integration/replay boundary.

### Next

- If corrected preflight is accepted, separately authorize one D1R6 one-session
  task creation before bed.
- Let the fixed task act only as a wake signal; the accepted D1R5 host must
  independently re-admit source/timing and produce its canonical journal.
- After waking, run read-only D1R6 reconciliation and independently review the
  D1R5 result.
- Only after a canonical D1R5 PASS is accepted may the next fresh D1-session
  authorization boundary be considered.

### Later

- Consider D1, paper, broker-paper, and later live-readiness gates only through
  their own reviewed authority boundaries and reconciliation requirements.
- Keep real-money trading unavailable until every explicit production/live gate
  is implemented, accepted, and separately enabled.

## History and deep-reference pointers

The immutable snapshot is indexed at [docs/history/INDEX.md](history/INDEX.md).
Its exact files and manifest are under
`docs/history/legacy/HIST-2B-2026-10-13/`. The legacy snapshot is for targeted
audit and reconstruction, not routine startup. Read the relevant architecture
or validation record first; use Git history when exact source-era provenance is
required. Do not grow this dashboard back into a cumulative milestone journal.
