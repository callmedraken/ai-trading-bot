# AI Trading Bot — Project Status

## Current pending checkpoint — consolidated 146-B pre-B2 correction

B1/C1-C6 is accepted/integrated at develop d2e9cbcb08c06eb050ee6d131ba3719d5c82ac42
(feature #788 / 40770164255 and develop #789 / 40771613241 SUCCESS).
The active pre-B2 source branch is
feature/research-arch146-b-pre-b2-readiness-current in
F:\AI\worktrees\ai-trading-bot-146b-pre-b2-readiness-current.
Its published parent is 63d8698cf1f2d899a2227b0c99ba92cfac935ed6,
TREE 96c5b5ed0a39caa5dcd56f696b4023dfe180b819.

Preserve #790 / 40812384997 attempts 1 and 2; neither is retryable here.
The bounded corrective candidate removes live inventory cardinality pins,
supports one independently reviewed canonical attempt-2 retry under exact
provenance, and replaces B2's stale /v2 reader with the current /v3 scoped
reader after source-owned Trading SID proof. The published 2718-session
authority and 146-A behavior remain unchanged.
The [pre-B2 validation record](validation/arch146-b-pre-b2-readiness.md)
owns correction details and evidence. This candidate remains pending exact-source
review and mapped terminal certification.

Next: focused/static checks, one clean corrective commit, both general admission
contexts, one ordinary push and terminal mapped FULL. Stop on red or green for
ChatGPT exact-source review. After acceptance and integration by ChatGPT, the
next executable milestone is one separately reviewed real read-only B2 host
preflight. Acquisition requires a later independent decision. Real preflight
is NOT_RUN; protected effects are ZERO, R3 stays parked and LIVE remains NO-GO.

## Current checkpoint

Resolve mutable `origin/develop` live at each startup. Architecture 146-B1/C1-C6
is closed, accepted and integrated at:

    HEAD d2e9cbcb08c06eb050ee6d131ba3719d5c82ac42
    TREE 8fb76f4db9a2401392092e70cce03401488551bf
    feature #788 / 40770164255 / attempt 1 / SUCCESS
    develop #789 / 40771613241 / attempt 1 / SUCCESS

Develop used exact feature-certification reuse. Cancelled duplicate #787 /
40770149444 / attempt 1 and the earlier failures remain immutable evidence in
the [146-B validation record](validation/arch146-b-historical-research-acquisition-custody-plan.md).
No rerun or replacement of that evidence is authorized.

## Active milestone — consolidated Architecture 146 pre-B2 source

The external historical-source blocker is resolved. The independently reviewed
NYSE/ICE bundle contains 13 documents and exactly 2718 regular equity sessions
for XNYS, America/New_York, [2016-01-01, 2026-10-24). Source-owned authority is
`nyse-published-regular-sessions-2016-2026-v1`, digest
`7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1`.
Exact provenance, derivation and hashes are retained in the
[pre-B2 source record](validation/arch146-b-pre-b2-readiness.md).

The unchanged global modeled calendar has exactly two extra dates: 2018-12-05
and 2025-01-09. The accepted disposition is
`REPOSITORY_MODELED_CALENDAR_EXCEPTION_GAP`. Published authority has no dates
absent from the model. Any other delta is STOP. 146-A verifier behavior and
historical paper/runtime/snapshot identities retain their existing contract.

This candidate adds accepted published-session verification, native adapters and
a separately executable read-only B2 preflight. It requires exact-source review
and mapped terminal GitHub FULL; source tests cannot grant real-host readiness.
B2 now explicitly binds the current /v3 scoped reader to the retained approved
source-owned Trading SID. Token SID equality must precede credential read.
No host identity was discovered and no credential was read. Custody host
security/freshness remains a separate closed prerequisite.

B2 effects remain unauthorized. `ACCEPTED_CUSTODY_ADMISSIONS` stays empty.
After terminal green and ChatGPT exact-source acceptance, the next milestone is
one real read-only B2 host preflight. Acquisition requires separate independent
preflight review and acceptance; a READY result alone grants no effects.

## Architecture 134 host track — parked, fail closed

R1, R2 and R3 are separately consumed observations. R3 remains:

    BLOCKED / HOST / HOST_UNEXPECTED_PRIVILEGE
    diagnostic_process_starts=23
    identity_stable=true
    protected_execution=NOT_AUTHORIZED
    production_effects=NOT_RUN

Every effect counter is zero and every authority flag is false. R3 report SHA256:

    8af6ef68a5a7a0558b938806719a3b3837ab8a8716a852573ed39d05a7411cb4

No retry, alternate-shell diagnostic or R4 is planned. Resume only when a
concrete runtime/deployment identity remediation is a direct dependency.

## Research/product boundary and roadmap

146-A C2 is accepted ancestry at `6906ba01bfb6a353029d695e584b2097587b81b9`,
tree `aa1efe5057e047e0d1778f2422e45f26cbc9f5d6`, #720 / 40178730059 / attempt 1 /
SUCCESS. Do not reimplement it.

    pre-B2 source review
      -> single real read-only B2 host preflight and independent review
      -> separately authorized one-shot acquisition/custody
      -> independent custody admission
      -> thin Architecture 145-B OPEN campaign orchestration
      -> existing compact report successor and Research Results GUI
      -> later separately admitted FINAL_HOLDOUT evaluation

D remains REQUIRED_POST_B2 / MINIMAL_ORCHESTRATION_GAP. E remains
REQUIRED_POST_B2 for report applicability. GUI_SOURCE_CHANGE=NOT_REQUIRED
pre-B2; F=NO_SOURCE_CHANGE beyond ordinary checkpoint registration. V1 reports
stay unchanged. The five native-MAC optimizer-only N/A metrics remain scheduled
for one consolidated post-B2 publication. No campaign, optimizer, backtester or
GUI is added here. LIVE remains NO-GO.
