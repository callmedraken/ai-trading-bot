# Architecture 134 â€” Read-only diagnostic R1 source binding

## Source-only successor

Starting accepted develop HEAD `91d6d3191736471d38c8542cd4bcfded35e51867`,
tree `94101fc079f4730415a632b82adcd1349e5d2b47`.
Checkpoint `arch134-fresh-successor-readonly-deployment-admission-diagnostic-r1`
uses the exact branch
`feature/robinhood-production-paper-fresh-successor-readonly-deployment-admission-diagnostic-r1-current`.
It registers read-only preflight, `execute = None`, and GitHub-owned ROBINHOOD.
This implementation checkpoint runs no real-host preflight.

`LocalGitReader(root)` retains the predecessor v1 tracking branch and fixed
develop query. Explicit `tracking_branch` accepts only that v1 branch or the
exact R1 branch. R1's host entry binds its branch explicitly, independently of
environment input. No wildcard refs, network, credentials, checkout or mutation
are added. Hidden-index, graft, shallow, partial-clone, complete-tree, blob,
closure and ancestry checks remain intact.

R1 has separate diagnostic/entry modules; predecessor diagnostic bytes and
registration retain historical meaning. The existing classification-aware
source authority applies one narrow successor overlay to the shared source
reader and protected preflight dispatch AST. Frozen maps and historical
reconstruction remain unchanged. Current registry, workflow, test inventory and
certification assertions remain current-owned; no current-infrastructure repins
or unrelated historical overlays are introduced.

The affected D1R6 check now reconstructs its immutable workflow declaration
through that same classification API and separately calls the canonical current
workflow predicate. That predicate owns the exact reviewed trigger families as
well as the existing job topology; no historical workflow pin is advanced.
R1 also accepts the already bounded optional diagnostic process count on PASS,
as on BLOCKED. Extra fields, invalid counts and effect/authority violations
remain rejected. The consumed predecessor validator is unchanged.

## Consumed evidence

The first actual diagnostic attempt is immutable and must never be rerun,
amended, overwritten, repointed or repaired:

    HEAD c2755c682a544bb4c24bb87889de819751715952
    TREE a2f0dfc86431dcc8e8ed5a89476df63bcab807cd
    report SHA256 640e0d61e9122ef40fd3716b80316a12d78cb1b19c70f651e7c3e576765ca26b
    BLOCKED / HOST / HOST_UNKNOWN / diagnostic_process_starts=9
    identity_stable=true
    production/effect counters=0; authority flags=false
    protected execution NOT_AUTHORIZED

The first source observation dispatched, in order: show-toplevel, graft-path,
HEAD, HEAD tree, branch, origin URL, worktree status, cached-index names and
shallow status. Query ten requested the diagnostic tracking ref, but the real
reader whitelist admitted the v1 branch. `GIT_VOCABULARY` rejected it before
dispatch. The predecessor diagnostic collapsed that source failure into
`HOST_UNKNOWN`. Source binding failed before Windows host-state qualification
was established. This provides no ACL, namespace, token, scheduler, runtime or
quiescence diagnosis.

Two earlier operator failures were pre-dispatch non-host attempts: an existing
default evidence root was rejected as non-fresh; a later invocation lacked the
trusted remote-head handoff. Neither called the host observer or consumed a host
attempt. The older v1 attempt remains separate immutable evidence, report
`3f412affd0fd89b850d4f2de4b7e27680b01780c9e1f6fdd3957a51821e23a36`.

## Closed source diagnostics

R1 retains `reason = HOST` and the existing host categories, adding:

| Code | Closed source boundary |
| --- | --- |
| HOST_SOURCE_GIT_COLLECTION | GIT_VOCABULARY / LOCAL_GIT_OBSERVATION |
| HOST_SOURCE_CHECKOUT_POLICY | Worktree/path, branch, origin, index, shallow, graft, partial-clone and tracking-ref policy |
| HOST_SOURCE_LINEAGE | Frozen source ancestry and closure |
| HOST_SOURCE_INVENTORY | Complete tree, objects, blob bytes, namespace/inventory and manifest identity |

Only exact reviewed ValueError codes map to these groups, on both observations
and source-policy validation. Unknown/unclassified exceptions remain
`HOST_UNKNOWN`. Raw exceptions, Git stdout/stderr, arbitrary commands, native
values, secrets and new paths never enter failure evidence.

Every effect counter remains zero and every authority flag false. PASS means
only `READY_FOR_SUCCESSOR_ROOT_WRITE_AUTHORITY_AND_ACL_REVIEW`. No release root,
ACL/materialization, scheduler/runtime, provider/OAuth/broker, F1 or live authority
follows. Rename-free immutable-release requirements remain mandatory.

## Complete future operator contract â€” NOT_RUN

ChatGPT must first review the exact published R1 HEAD/tree, admission and terminal
CI. Only that review may supply the two literal identities below. The placeholders
intentionally fail closed; never substitute the predecessor, derive approval from
local HEAD, or hard-code elevation. This is an invocation template, not authority
to run it during the source-only checkpoint.

The registered preflight requires a fresh nonexistent external `--evidence-root`
and five `AI_TRADING_BOT_ARCH134_ADMISSION_` environment values: `HEAD`, `TREE`,
`REFERENCE`, `PRINCIPAL_SID`, `ELEVATED` (HEAD is also the runner's trusted
remote-head handoff). The registered observer owns actual token/host
admission. Do not prepend an Administrator or production-state pre-screen.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $ReviewedHead = '<exact R1 HEAD supplied by ChatGPT source review>'
    $ReviewedTree = '<exact R1 TREE supplied by ChatGPT source review>'
    if ($ReviewedHead -cnotmatch '^[0-9a-f]{40}$' -or $ReviewedTree -cnotmatch '^[0-9a-f]{40}$') { throw 'STOP: exact reviewed R1 identities required' }
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
    $env:AI_TRADING_BOT_ARCH134_ADMISSION_HEAD = $ReviewedHead
    $env:AI_TRADING_BOT_ARCH134_ADMISSION_TREE = $ReviewedTree
    $env:AI_TRADING_BOT_ARCH134_ADMISSION_REFERENCE = 'feature/robinhood-production-paper-fresh-successor-readonly-deployment-admission-diagnostic-r1-current'
    $env:AI_TRADING_BOT_ARCH134_ADMISSION_PRINCIPAL_SID = $Identity.User.Value
    $env:AI_TRADING_BOT_ARCH134_ADMISSION_ELEVATED = $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator).ToString().ToLowerInvariant()
    $EvidenceRoot = 'F:\AI\temp\ai-trading-bot-checkpoints\arch134-diagnostic-r1-' + [guid]::NewGuid().ToString('N')
    .\ops.ps1 preflight arch134-fresh-successor-readonly-deployment-admission-diagnostic-r1 --evidence-root $EvidenceRoot
    if ($LASTEXITCODE -ne 0) { throw 'STOP: preserve evidence; no retry or repair' }
}
```

The script creates only a GUID path string; the runner creates the evidence
directory. Return the complete sanitized report, report SHA256, source HEAD/tree,
process count and identity stability for ChatGPT review. PASS stops at the root
write-authority/ACL review boundary. BLOCKED/unknown stops with no retry or repair.
