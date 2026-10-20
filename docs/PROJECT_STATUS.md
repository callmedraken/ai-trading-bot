# AI Trading Bot - Project Status

## Current verified checkpoint

Architecture 144-A+B / RCL-7, Architecture 134-F1, and Architecture 144-C are **SOURCE ACCEPTED**.

Accepted Architecture-144 v1 source:

```text
branch  feature/test-suite-arch144-research-paper-eligibility-current
HEAD    20219f65e59dc91287462490d85f41b8fdb2a97e
TREE    a9e0b6fe7b85dbaeef8b3f46f5276483ec6b93bd
CI      Checkpoint Source Gates #643 / 39386250794 / SUCCESS
```

Its final canonical FULL passed on the exact source:

```text
modules 187
cases   12,436
passed  12,433
skipped 3
failed  0
errors  0
wall    256.955 s
```

Do not repeat FULL or add redundant ROBINHOOD coverage on unchanged v1 source.

Accepted Architecture 134-F1 source:

```text
branch  feature/robinhood-production-paper-134f-five-session-soak
base    b3b605fdc0886cd90367027e72d43ecaf8ce5b4c
HEAD    b59ad3b44540a55a30f612d5c4e3e38e26a95b02
TREE    e8a94e3512d7950f2fbc9c4d102a58b63e03244f
```

Canonical ROBINHOOD #649 / 39401319643 passed on that exact F1 source:

```text
modules 103
cases   10,422
passed  10,416
skipped 6
failed  0
errors  0
wall    287.894 s
```

The initial #648 failure remains preserved. Its eight failures were stale
test-only registry/successor expectations; C1 changed no F1 production module.
Architecture-144 v1 remained byte-for-byte unchanged.

Accepted executable integration state:

```text
develop HEAD d4d007a5c4a7c6a5158b1fab6f82c082387783f3
develop TREE 47f13748c89784fddf0ef981072a7b23f7d02f22
```

Integration source-gate #653 / 39490843514 / attempt 1 passed on the exact
accepted 144-C tree. Its four `full-tests` jobs were normal broad develop
source-gate shards, not a canonical FULL certification; active and canonical
certification jobs were correctly skipped.

## Accepted Architecture 144-C

Architecture 144-C is **SOURCE ACCEPTED AND INTEGRATED**.

Accepted feature source:

```text
branch  feature/test-suite-arch144-c-f1-paper-evidence-admission-current
base    c2072179a50b3e8b441b447b18284f0dc2040d88
HEAD    1e86b5dcce19cd45504266b4fa0ac0aca5854d04
TREE    47f13748c89784fddf0ef981072a7b23f7d02f22
CI      Checkpoint Source Gates #652 / 39410467329 / attempt 1 / SUCCESS
```

ChatGPT independently reviewed the exact one-commit 29-path diff, V2
identity/canonicalization, independent supplied-byte F1/D1R7/D1R8 replay,
complete Architecture-142/143 composition, zero operational capability, frozen
v1 blobs, checkpoint registration and terminal CI.

The frozen v1 implementation blobs remain unchanged:

```text
research_strategy_paper_candidate_eligibility.py
fd6b0ad650fb3fb97f587deb7cffc7286e685813

research_strategy_paper_evidence_verification.py
915bdd84bee3ad0b57efcafb0a78da01fce94e66
```

No additional canonical ROBINHOOD/FULL was selected because 144-C is an additive
pure evidence-admission successor and the exact final tree already passed its
focused/active and broad source-gate coverage. Source acceptance does not grant
scheduler/provider/credential/paper/broker/promotion/live authority.

Canonical design remains:

- `docs/architecture/144-c-f1-paper-evidence-admission.md`;
- `docs/validation/arch144-c-f1-paper-evidence-admission-plan.md`.

## Paper-operational readiness

Architecture 134-E's accepted Monday 2026-10-19 D1R9 `FINAL / NO_SIGNAL`
proved one unattended integration session and is consumed.

Architecture 134-F1 now supplies the accepted five-session current-product source
authority, but the real five-session soak remains a separately reviewed
protected effect.

Required sequence:

```text
144-C source accepted and integrated
-> separate 134-F protected preflight/readiness design + read-only review
-> only then an exact separately authorized protected preflight command
-> only after that boundary passes, separately admit the real five-session soak
-> end-of-window reconciliation
-> pure V2 eligibility evaluation
```

The v1 policy remains:

```text
required_session_count = 5
required_paper_executed_count = 1
require_consecutive_published_regular_sessions = true
qualifying_terminal_classifications = ("NO_SIGNAL", "PAPER_EXECUTED")
```

Five sessions are an eligibility boundary, not enough evidence by themselves to
establish long-run profitability.

## Protected and safety boundaries

- Real-money trading remains **NO-GO**.
- The Monday D1R9 authority remains consumed and is not retried.
- 134-F protected preflight/readiness is now the next review boundary, but no protected command or operational effect is authorized yet.
- The real five-session soak is closed.
- No source/CI/FULL/ROBINHOOD result grants scheduler/provider/credential/paper,
  broker, promotion, D2, or live authority.
- `PAPER_CANDIDATE` materialization and human promotion remain later explicit
  architectures.

## Architecture 134-F2 design state

The read-only readiness review found no registered F1 preflight. The accepted F1
checkpoint intentionally remains `preflight=None`, `execute=None`.

Architecture 134-F2 is now **DESIGN FROZEN** in:

- `docs/architecture/134-f2-five-session-live-paper-soak-readiness.md`;
- `docs/validation/arch134-f2-five-session-live-paper-soak-readiness.md`.

F2 adds only the missing registered **read-only** readiness boundary. It leaves
accepted F1 operational source/provenance unchanged and must perform zero
credential/provider/task/runtime-write/paper/broker/live effects.

READY requires exact frozen F1/D1R7/D1R8 source admission, accepted predecessor
evidence, read-only compatible production runtime, an untouched F1 durable
namespace, scheduler `ABSENT`, five published-session preview targets and final
readmission.

Credential/provider readiness and rollback/write readiness are deliberately
`NOT_CHECKED` by F2 rather than being hidden inside a read-only preflight.

## Active work

### Now - Architecture 134-F2 implemented; exact-source review pending

Implementation owner/model: **Codex / Sol High**.

```text
branch     feature/robinhood-production-paper-134f2-five-session-soak-readiness
worktree   F:\AI\worktrees\ai-trading-bot-production-paper-134f2-five-session-soak-readiness
base HEAD  9310eec609fcd273d9e248c4e897fe7e5828f953
base TREE  dbac92b55169b3a21d1ebee046755707be40f1eb
checkpoint arch134-f2-five-session-soak-readiness
preflight  _arch134_f2_preflight (read-only)
execute    None
CI profile robinhood
```

The source implements the frozen F2 contract with fake/static/disposable tests.
All seven frozen F1 operational blobs remain unchanged. F1 registration remains
`preflight=None`, `execute=None`. Allowed observations are counted separately
from the zero effect counters. The real host preflight has not run.

Publication follows focused checks, one unpublished normal commit, registered
source verification on that clean commit, and one ordinary feature push. The
mapped push owns canonical ROBINHOOD; no duplicate local ROBINHOOD or FULL.
Source acceptance and terminal CI evidence remain pending in this source record.

### Next - ChatGPT exact-source review

Inspect the initial F2 commit and separate C1, complete changed-path set, frozen operational pins,
registered verification and terminal source-gate/canonical ROBINHOOD evidence.
Stop on a mismatch, red gate or ambiguous evidence. If accepted, ChatGPT may
supply the separately reviewed read-only F2 preflight command from the exact
clean F2 worktree. Review that evidence before considering F1 authorization.

### Later

Only after a reviewed F2 preflight PASS may an exact interactive F1 authorization
be separately proposed. That command is the first authority-consuming boundary.
The real soak and all scheduler mutation, credential/provider, runtime-write,
paper/broker, promotion and live effects remain closed. Real-money is **NO-GO**.

## History

Use `docs/history/INDEX.md` only for targeted historical reconstruction.

## F2 failed attempt and bounded C1

Initial F2 source `dd6a822d20b3b42a6c61eb5241fc6d5c6045521e` / tree
`f2da182ef547f43f38d8f2af5afc43356e3ef1f2` passed its registered local gate
(1,031 cases), source-static and active CI. Canonical ROBINHOOD #656 /
39498692559 / attempt 1 failed four stale runner-pin/historical-expectation
assertions: 104 modules, 10,662 cases, 10,652 passed, six skipped, four failed,
zero errors; wall 282.215 seconds. The failed run and artifact remain preserved.

Separate bounded C1 updates the installation gate's exact read-only preflight
AST pin and the retired recovery test's expected drift set. A new proof removes
only the two F2-only branches and requires the exact frozen non-F2 predecessor
AST. The F2 focused gate now includes all three affected installation/recovery
modules and installation source authority. No F2 runtime behavior, protected
execute behavior, F1 operational blob, ownership baseline or lane policy changes.

C1 has its own focused checks and atomic normal commit/push; it never amends or
reruns the failed attempt. Replacement CI/source acceptance remain pending in
this source record. No real F2 preflight, soak or operational effect is authorized.
