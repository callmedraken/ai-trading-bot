# AI Trading Bot - Project Status

## Current verified checkpoint

Architecture 144-A+B / RCL-7 and Architecture 134-F1 are **SOURCE ACCEPTED**.

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

Current integration state:

```text
develop HEAD f47deac55e22f5a1f215bed69b3429038d7babb0
develop TREE 6a5e3319729e2d1e4b034631dd1d2edb99ccaa4f
```

Integration source-gate #650 / 39403544950 passed. Its four `full-tests` jobs
were the normal broad source-gate shards, not a canonical FULL certification.

## Architecture 144-C design state

Architecture 144-C is now **DESIGN FROZEN** in:

- `docs/architecture/144-c-f1-paper-evidence-admission.md`;
- `docs/validation/arch144-c-f1-paper-evidence-admission-plan.md`.

The design pins accepted F1:

```text
HEAD b59ad3b44540a55a30f612d5c4e3e38e26a95b02
TREE e8a94e3512d7950f2fbc9c4d102a58b63e03244f
```

144-C preserves the accepted Architecture-144 v1 eligibility/verifier modules
byte-for-byte and adds a separate pure V2 generic paper-authority path.

The successor:

- uses separate V2 observation and eligibility schemas/namespaces;
- reuses the unchanged v1 five-session policy;
- truthfully binds F1 parent/child provenance rather than overloading `d1r9_*`;
- independently replays supplied canonical F1 parent/child and D1R7/D1R8 bytes;
- requires complete Architecture-142/143 verification;
- remains pure/read-only with zero filesystem acquisition, scheduler, provider,
  credential, paper, broker, promotion, or live authority.

## Paper-operational readiness

Architecture 134-E's accepted Monday 2026-10-19 D1R9 `FINAL / NO_SIGNAL`
proved one unattended integration session and is consumed.

Architecture 134-F1 now supplies the accepted five-session current-product source
authority, but the real five-session soak remains a separately reviewed
protected effect.

Required sequence:

```text
144-C design freeze
-> 144-C source implementation + source acceptance
-> protected 134-F preflight/readiness review
-> only then separately admitted real five-session soak
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
- Protected 134-F preflight is closed until 144-C source acceptance.
- The real five-session soak is closed.
- No source/CI/FULL/ROBINHOOD result grants scheduler/provider/credential/paper,
  broker, promotion, D2, or live authority.
- `PAPER_CANDIDATE` materialization and human promotion remain later explicit
  architectures.

## Active work

### Now

Implement Architecture 144-C from the frozen design.

Expected branch:

`feature/test-suite-arch144-c-f1-paper-evidence-admission-current`

Expected worktree:

`F:\AI\worktrees\ai-trading-bot-arch144-c-f1-paper-evidence-admission-current`

Owner/model: **Codex / Sol High** because provenance verification is an authority
boundary even though the implementation is pure.

Use focused tests and the normal source gate. Do not preselect canonical FULL or
ROBINHOOD. ChatGPT decides additional certification only after exact-source
review.

### Then

ChatGPT exact GitHub source/CI review and acceptance.

### Then

Perform the separate read-only 134-F protected preflight/readiness review. The
preflight itself still grants no soak authority.

### Later

Run at most the frozen five-session paper soak if separately admitted, reconcile
the complete window, evaluate supplied evidence through 144-C, and continue
longer paper observation before any promotion decision.

## History

Use `docs/history/INDEX.md` only for targeted historical reconstruction.
