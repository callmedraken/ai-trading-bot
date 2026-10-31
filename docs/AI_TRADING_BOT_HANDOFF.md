# AI Trading Bot — Current Handoff

## Current boundary — Architecture 147 P4 source-only

Starting accepted integrated source:

    HEAD b9d52c4934517ea67b8c18f4d6f967bfd576ecf7
    TREE 755054f71489491f0214489e35827ba2bb51c74e
    worktree F:\AI\ai-trading-bot
    branch feature/research-desktop-supervisor-current
    checkpoint arch147-desktop-supervisor
    preflight=None; execute=None; canonical FULL owned by GitHub

The branch matches the already-reviewed `feature/research-*` push trigger.
P3's accepted integration and real research/GUI review supersede the previous
P3 corrective-child handoff. Develop #814 / run `41151276520` / attempt 1 is
SUCCESS with `DEVELOP_CERTIFICATION_REUSE=True`, `exact_feature_certification`,
`IDENTITY_STABLE=True`, `OVERALL=PASS`. Historical P3 #812 and its corrective
lineage remain immutable; their chronology stays in the validation record.

P4 has five closed lifecycle states: STOPPED, STARTING, RUNNING, STOPPING,
FAILED. Duplicate Start is a no-op; Stop is idempotent. Fatal worker failures
stop the peer and leave FAILED, with no automatic restart. Clean Stop alone
permits another generation. A worker/operation timeout leaves visible attention,
retained ownership and no new generation; there is no force kill or automatic
recovery. GUI close requests normal asynchronous Stop and waits for confirmed
closure; unresolved children prevent close.

Production composition uses one inert trading thread and one independent
research thread. Research verifies only the accepted existing P3 bundle and
waits for explicitly queued bounded offline inspection work. It never starts a
campaign. Trading has no strategy, orders, positions, ledger or transport.
Research receives no trading state or lifecycle controls. External trading
transport is NOT_CONNECTED / P5 deferred; simulated paper default, LIVE disabled.
P3 research results have no strategy-selection or promotion authority.

The JSONL journal and exclusive lifetime lock are ordinary local state under
`F:\AI\desktop-bot-state\p4`, outside the checkout. Strict replay checks schema,
sequence, generation, UTC, closed events/diagnostics and legal transitions.
Unresolved prior STARTING/RUNNING/STOPPING/FAILED, malformed bytes or stale
ownership blocks Start. Preserve it for explicit reconciliation; do not delete,
overwrite, retry or manufacture a STOPPED record.

Implementation/admission/CI do not launch the production GUI or create its
journal, read the accepted production bundle, run research, open FINAL_HOLDOUT,
or access credentials/providers/brokers/accounts/schedulers/ACLs. Tests use
synthetic bundles and fresh external temporary roots. Historical read-only
Supervisor semantics, lazy-export authority and frozen source checks remain.

## Immediate next step and success evidence

Owner: Codex implements and runs focused checks, whole-root combined Ruff/diff,
current/historical source authority, one atomic exact-file commit, general
`ops.ps1 admit` in FEATURE and PROSPECTIVE_DEVELOP, one ordinary push, then polls
its one mapped CI to terminal. Return exact HEAD/tree/parent, file set, focused
counts, admission report and run identity. No local canonical FULL, PR or merge.
A deterministic uncovered pin/fixture/ownership CI failure is preserved and
classified PREPUBLICATION_COVERAGE_DEFECT for ChatGPT review.

Next owner: ChatGPT independently reviews the exact source and CI, integrates
only if accepted, then verifies develop reuse. Only after that boundary, launch:

```powershell
& {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'
    $Repo = (Resolve-Path -LiteralPath 'F:\AI\ai-trading-bot').Path
    Set-Location -LiteralPath $Repo
    & .\.venv\Scripts\python.exe -B scripts\run_desktop_bot.py
    $Code = $LASTEXITCODE
    if ($Code -ne 0) { throw 'STOP: preserve runtime journal and review diagnostics' }
}
```

The reviewed operator clicks Start once, observes both workers RUNNING, clicks
Stop, observes STOPPED after trading reconciliation and both closures, then
closes the GUI. Verify the durable final STOPPED record and accepted research
identity; no credentials or network are involved. This future smoke is not run
by the source-only checkpoint. Continue to P5 source work after successful
smoke, without an approval-only turn. LIVE remains NO-GO and FINAL_HOLDOUT sealed.
