# Architecture 146-B consolidated pre-B2 source checkpoint

## Accepted base and immutable evidence

    develop HEAD d2e9cbcb08c06eb050ee6d131ba3719d5c82ac42
    develop TREE 8fb76f4db9a2401392092e70cce03401488551bf
    feature #788 / 40770164255 / attempt 1 / SUCCESS / accepted
    develop #789 / 40771613241 / attempt 1 / SUCCESS / exact feature reuse

B1/C1-C6 is closed and integrated. Preserve cancelled duplicate #787 /
40770149444 / attempt 1 and all historical B1 failures. This is one source-only
candidate in F:\AI\worktrees\ai-trading-bot-146b-pre-b2-readiness-current,
branch feature/research-arch146-b-pre-b2-readiness-current, registered as
arch146-b-pre-b2-readiness-source. No PR, integration or real B2 operation.

Before the first authority edit, the existing external evidence root was read
without reacquisition:

    F:\AI\temp\arch146-historical-session-authority-source-0a5d728dc73043169102242efd712ed6

Every document length/hash, manifest hash, bundle hash, source-derived session
vector and canonical HistoricalSessionAuthority.digest was recomputed and matched:

    source documents: 13
    manifest SHA256:
    e1f9f6f0048114f2307255a7fa1b40c3661c115c1e8cc22c992246207e084735
    bundle SHA256:
    6db5b3c039dc98e6a21d5dc8e917de60305c919ea6fdf4cc8b8141185b774607
    identity: nyse-published-regular-sessions-2016-2026-v1
    authority digest:
    7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1
    schema: historical-research-session-authority/v1
    calendar: XNYS
    timezone: America/New_York
    interval: [2016-01-01, 2026-10-24)
    first/last: 2016-01-04 / 2026-10-23
    ordered unique sessions: 2718

The exact manifest bytes and source-bound full-day-closure transcription are
retained under evidence/arch146 with Git text conversion disabled. Raw HTML/PDF
sources remain external and are not committed. Bundle hashing removes only the
bundle_sha256 member, serializes all remaining material as sorted-key UTF-8 JSON
with compact separators and ensure_ascii=False, then hashes those bytes.
Weekday filtering against source-bound closures independently reproduces the
packaged canonical vector. The resource bytes hash to the exact authority digest.
Exactly one historical authority is accepted. No runtime registration API exists.
ACCEPTED_CUSTODY_ADMISSIONS remains empty.

## Calendar policy and 146-A compatibility

    source-derived sessions: 2718
    unchanged modeled sessions: 2720
    model minus published: 2018-12-05, 2025-01-09
    published minus model: empty
    disposition: REPOSITORY_MODELED_CALENDAR_EXCEPTION_GAP

These official full-day closures honor George H. W. Bush and Jimmy Carter.
Adjacent valid sessions remain included. Any additional delta is STOP.
NYSEMarketCalendar, XNYS_CALENDAR_DESCRIPTOR and
nyse-regular-sessions-1998-2100-v1 are unchanged. Architecture 56/57/111 and
paper/runtime/snapshot identities are not reinterpreted.

Private helpers separate physical integrity verification from session policy.
Existing public 146-A verifiers retain modeled-calendar behavior. The current
authority owner reconstructs the complete immutable old 146-A AST from the
reviewed extraction, including exact wrapper signatures and physical checks;
historical declarations are not repinned. New 146-B custodian verification checks
complete OPEN/HOLDOUT bytes, exact accepted published sessions, membership and
full fingerprint. The OPEN successor retains independent custody/evidence/source
binding and resolves exactly one accepted authority. Missing, unexpected,
exceptional-closure and duplicate bars fail; no bars are fabricated.

## Native adapters and closed identity prerequisite

CredentialSource bridges WindowsAlpacaCredentialManagerReader using only the two
established ALPACA_API_KEY_ID_CREDENTIAL_TARGET and
ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET constants. It retains exact SID checking,
scoped use/close, native cleanup and redaction. No environment/config/CLI secret,
additional target, fallback or real read is introduced.

Current classification is
BLOCKED_SOURCE_OWNED_B2_CREDENTIAL_ACCOUNT_BINDING. The production Trading SID
is source-owned, but that does not independently establish the B2 credential/
custodian account; it also has no access under the protected custody DACL.
Do not infer this identity from BA ownership, a running token, host discovery
or credential-read success. The source-owned binding must be independently
settled. Current preflight stops on it before observing real roots.

HTTPS reuses reviewed stdlib mechanics/constants with a dedicated B1 binding:
only the two frozen GET request families over certificate/hostname-verified TLS
to data.alpaca.markets:443. Exact raw entity bytes are bounded and preserved;
no redirects, decompression, proxy fallback or automatic retries. All statuses,
including 401/403/429/5xx, return to the one-shot kernel without retry. Exceptions
and public evidence contain no secret headers or raw response bodies.

Custody is dedicated, create-only and rename-free:

    OPEN F:\AI\ai-trading-bot\data\research\arch146-v1
    PROTECTED F:\AI\research-holdout\arch146-v1
    CLAIM F:\AI\research-holdout\.arch146-v1-attempt.json

The protected parent must already be local NTFS, non-reparse, BA-owned and have
the exact protected BA/SYSTEM full-control OI/CI DACL. Missing/unproven parents
are closed prerequisites; this adapter does not provision or repair them.
Held ancestor handles deny delete sharing. Every native open checks final path,
kind, local fixed NTFS volume and no-reparse identity. Roots/claim/partial state
must be absent. A CREATE_NEW durable claim consumes the v1 attempt before later
effects. Any ambiguity consumes the adapter and preserves artifacts.

Protected SDDL is O:BAG:BAD:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY). OPEN adds only
BUILTIN Users read/execute (0x1200a9) to that protected BA/SYSTEM policy. Files
receive explicit protected non-inheriting counterparts. OPEN accepts only exact
normalized OPEN CSV and validated non-price commitments/evidence. Original raw
pages, complete corporate-action provenance and holdout material stay protected.

Files use exclusive CREATE_NEW/no-follow/write-through, file and volume flush,
exact same-handle readback, owner/DACL reinspection and stable single-link file
identity. Directories use their final path and explicit policy, then volume
flush. No rename, promotion, replacement, cleanup or retry API exists. Native
qualification remains a future host boundary; all tests are fake/disposable.

## Prepared real-host preflight — NOT_RUN

Only after independent exact-source review, substitute the accepted candidate
HEAD/TREE into this separately reviewed read-only command:

```powershell
Set-Location 'F:\AI\worktrees\ai-trading-bot-146b-pre-b2-readiness-current'
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -m scripts.arch146_b2_readonly_preflight --accepted-head <ACCEPTED_HEAD> --accepted-tree <ACCEPTED_TREE>
```

The launcher binds imports to the exact worktree. It proves root/branch/HEAD/
tree/clean source/origin/live feature ref before and after observation, with Git
optional locks and bytecode writes disabled. Its non-price report binds accepted
source/checkpoints, authority/digest/2718 count, frozen requests, exact adapter
classes, credential binding, roots/claim/SDDL and fresh-state/NTFS/non-reparse
facts. Credential secret reads, provider calls, writes and ACL mutations are zero.
Fake evaluation can return only SIMULATED_B2_PREREQUISITES_PASS. Only a future
separately reviewed real execution may return
READY_FOR_ONE_ARCH146_B2_ACQUISITION_ATTEMPT. No READY result grants effects.
There is no registered B2 execute dispatcher or acquisition CLI.

## Verification, publication and next milestone

Focused verification covers source/resource/manifest/bundle/date integrity,
exact model reconciliation, 146-A preservation, full/OPEN published verification,
B1 acquisition/custody, existing credential security, HTTP endpoint/status/error
security, disposable custody, injected Win32 create/flush/readback/path/ACL/link
failures, pure preflight, source authority and affected distributed-FULL checks.
Require whole-root Ruff 0.17.3 check/format-check, git diff --check, then one clean
atomic candidate with FEATURE and PROSPECTIVE_DEVELOP ops.ps1 admit PASS.
Canonical FULL belongs to the single mapped GitHub push; never run it locally.
The new supported test module enters the existing 1000-ms fallback automatically
(current FULL inventory 210). Frozen 209-module C4 timings/digest, required
122/49 baselines, seven-lane planner and workflow topology remain unchanged.
Mapped red is STOP with terminal run/attempt evidence preserved. No amend,
rebase, force-push, manual CI rerun, PR or merge.

Protected effects = ZERO. Real preflight is NOT_RUN. No real credential/provider/
root/ACL/holdout/dataset/scheduler/host/paper/broker/live action, Architecture-145
campaign or FINAL_HOLDOUT evaluation. After terminal green, stop for ChatGPT
exact-source review. Next milestone is the single real read-only B2 host
preflight with the identity prerequisite visible. Acquisition stays separately
unauthorized until the preflight is independently reviewed and accepted.

D=REQUIRED_POST_B2 / MINIMAL_ORCHESTRATION_GAP; E=REQUIRED_POST_B2 for report
applicability; GUI_SOURCE_CHANGE=NOT_REQUIRED pre-B2; F=NO_SOURCE_CHANGE beyond
routine registration. V1 report is unchanged. Five native-MAC optimizer-only
N/A metrics remain scheduled for one post-B2 publication. No new engine, report
family or GUI. R3 remains parked. LIVE remains NO-GO.
