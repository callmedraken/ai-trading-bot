# AI Trading Bot — Current Handoff

## Pending research authority coupling correction

Accepted integrated base (verify live remote independently):

    develop HEAD b047d87cb7d82e61b9ef23280db90d8cf916c75b
    develop TREE bc075bc0cac40ebee64a682350c08dac903359e4
    branch feature/research-arch146-b-pre-b2-readiness-current
    worktree F:\AI\worktrees\ai-trading-bot-146b-pre-b2-readiness-current
    checkpoint arch146-b-pre-b2-readiness-source
    mapped certification FULL (GitHub-owned)

This pending source correction removes Architecture 146's production Trading SID,
production-paper admission and /v3 Credential Manager dependency. The ordinary
research token must be an observed Windows user SID, non-elevated and non-admin.
The source observes rather than hardcodes that SID. Ephemeral hidden terminal
input is the sole credential source, persistence NONE; no secret fallback,
provisioning, Credential Manager access or acquisition CLI exists.

Preflight never prompts. Its report retains zero secret reads, provider calls,
writes and ACL mutations, acquisition_authorized=false. Fake reports cannot mint
real readiness/acceptance. Later acquisition binds accepted exact source HEAD/TREE,
operator SID, authority identity/digest, requests and custody and rechecks the
current token before input. Independent acceptance is currently process-local;
printed/parsed CLI evidence cannot rehydrate an acquisition capability. Future
reviewed acquisition wiring must retain the real report across independent review.
READY or constructing a credential source never authorizes effects.

## Consumed evidence and preserved source

The consumed first preflight BLOCKED_CREDENTIAL_ACCOUNT_SID_MISMATCH and identity
reconciliation WRONG_LAUNCH_PRINCIPAL remain truthful. Trading identity drift
was false; root cause ARCH146_RESEARCH_AUTHORITY_COUPLING_DEFECT. Production
Trading itself was not defective. Full disposition and original zero counters
are in the [pre-B2 validation record](validation/arch146-b-pre-b2-readiness.md).
No report is rewritten and no real host state is inspected in this checkpoint.

B1/C1-C6 accepted ancestry is d2e9cbcb08c06eb050ee6d131ba3719d5c82ac42,
feature #788 / 40770164255 and develop #789 / 40771613241 SUCCESS.
Preserve cancelled #787 and failed #790 / 40812384997 attempts 1/2 unchanged.
NO_MUTABLE_INVENTORY_CARDINALITY_PINS and reviewed attempts 1/2 remain intact.

Published authority remains nyse-published-regular-sessions-2016-2026-v1,
2718 sessions, digest
7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1.
Model minus published: 2018-12-05, 2025-01-09; reverse delta empty.
146-A/global modeled calendar, transport, custody roots and exact protected policy
are unchanged. ACCEPTED_CUSTODY_ADMISSIONS remains empty. Ordinary-token identity
does not relax custody security/freshness prerequisites or authorize repair.

## Next step and stop condition

Codex owns the bounded source implementation and focused verification, including
the infrastructure/authority coherence bundle, whole-root Ruff 0.17.3 checks,
and diff-check. Prepare one clean atomic candidate, run general ops.ps1 admit
(FEATURE and PROSPECTIVE_DEVELOP), ordinary-push once, wait for the one mapped
GitHub CI to reach terminal state. Canonical FULL must not run locally.
Terminal red or green is STOP for ChatGPT exact-source review. No CI rerun,
amend, rebase, force-push, PR or merge. Return exact commit/tree, changed paths,
focused/admission results and terminal run identity/conclusion.

After exact-source acceptance/integration, ChatGPT provides a SHORT DIRECT
OPERATOR PROCEDURE for one ordinary-operator real read-only B2 preflight.
Only after independent acceptance may a separately reviewed one-shot acquisition
be authorized, with hidden credential input immediately before provider use.
Correction real preflight NOT_RUN; acquisition NOT_AUTHORIZED; protected effects ZERO.

## Parked and post-B2 boundaries

Architecture 134 R3 remains consumed/parked at
BLOCKED / HOST / HOST_UNEXPECTED_PRIVILEGE, report SHA256
8af6ef68a5a7a0558b938806719a3b3837ab8a8716a852573ed39d05a7411cb4.
No retry or R4. LIVE remains NO-GO. D/E are REQUIRED_POST_B2; GUI_SOURCE_CHANGE
is NOT_REQUIRED pre-B2; F is NO_SOURCE_CHANGE beyond registration. Reuse existing
engines, reports and GUI. V1 reports and the five scheduled optimizer-only
native-MAC N/A metrics retain their existing disposition.
