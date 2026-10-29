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

## Native adapters and source-owned credential binding

B2 reuses trading_bot.review_paper.alpaca_windows_credentials exactly:

    CREDENTIAL_POLICY windows-credential-manager-alpaca-market-data/v3
    API_KEY_TARGET AITradingBot/MarketData/Alpaca/ApiKeyId/v3
    API_SECRET_TARGET AITradingBot/MarketData/Alpaca/ApiSecretKey/v3
    read_current_product_alpaca_secrets() -> ScopedAlpacaSecrets.use(...)
      -> AcquisitionCredentials

The narrow B2 CREDENTIAL_ACCOUNT_SID imports retained approved TRADING_SID
from review_paper.unattended_host_identity. A regression independently compares
that binding with PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid.
No host SID discovery supplies authority. Runtime read entry independently
observes the current token SID and requires exact equality before calling the
current /v3 reader once. Scoped use/close and native cleanup/redaction remain.
There is no /v2, /v1, environment/config/CLI fallback or additional target.
Identity/reader reuse imports no D1/PREPARE/EXECUTE or provider authority.

Pure preflight now checks the fixed current /v3 source binding and current token
SID before freshness/security observations. It no longer permanently blocks on
an absent source binding. Fake evaluation can only report simulated readiness.
The retained protected custody policy is unchanged; its real-host prerequisites
must be proved separately. The preflight reads zero secrets and grants no effect.

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
without a current-cardinality pin. Frozen 209-module C4 timings/digest, required
122/49 baselines, seven-lane planner and workflow topology remain unchanged.
Mapped red is STOP with terminal run/attempt evidence preserved. No amend,
rebase, force-push, manual CI rerun, PR or merge.

Protected effects = ZERO. Real preflight is NOT_RUN. No real credential/provider/
root/ACL/holdout/dataset/scheduler/host/paper/broker/live action, Architecture-145
campaign or FINAL_HOLDOUT evaluation. After terminal green, stop for ChatGPT
exact-source review. Next milestone is the single real read-only B2 host
preflight against the accepted source-owned identity and /v3 binding. Acquisition stays separately
unauthorized until the preflight is independently reviewed and accepted.

D=REQUIRED_POST_B2 / MINIMAL_ORCHESTRATION_GAP; E=REQUIRED_POST_B2 for report
applicability; GUI_SOURCE_CHANGE=NOT_REQUIRED pre-B2; F=NO_SOURCE_CHANGE beyond
routine registration. V1 report is unchanged. Five native-MAC optimizer-only
N/A metrics remain scheduled for one post-B2 publication. No new engine, report
family or GUI. R3 remains parked. LIVE remains NO-GO.


## Bounded corrective candidate after immutable #790 attempts

Parent HEAD 63d8698cf1f2d899a2227b0c99ba92cfac935ed6,
TREE 96c5b5ed0a39caa5dcd56f696b4023dfe180b819; direct develop base remains
d2e9cbcb08c06eb050ee6d131ba3719d5c82ac42.

Preserve #790 / run 40812384997, attempts 1 and 2. Attempt 1 broad-4 passed
2532 tests with pytest exit 0, then its repeated final live-origin observation
lost connectivity. ChatGPT classified an external infrastructure transient
and authorized one targeted same-SHA retry. Attempt 2 stopped before pytest:
Exact successful CI source-static dependency required. Its deterministic
attempt-1 restriction and the independent reuse restriction are corrected here.
Neither attempt is rerun, overwritten or reinterpreted as success.

The correction implements NO_MUTABLE_INVENTORY_CARDINALITY_PINS, including
per-directory live counts and giant live-additions snapshots. Synthetic fixtures
are deliberately synthetic. One and multiple future supported modules prove
discovery, fallback timing, deterministic one-lane placement, complete
classification/partition coverage and unchanged historical timing evidence.
Attempts 1/2 require full exact provenance; attempt 3 is rejected. Historical
predecessor functions/pins and validation records retain their old meaning.
The current credential adapter and pure preflight use only the source-owned
Trading SID and /v3 generation described above.

The 2718-session authority, its digest/bundle/manifest, model-minus-published
2018-12-05 and 2025-01-09, empty reverse delta, global modeled calendar and 146-A
public behavior remain unchanged. No real-host preflight or protected effect
is run. One clean corrective commit must pass FEATURE/PROSPECTIVE_DEVELOP
admission, then one ordinary push and one mapped canonical CI. Terminal red
or green is STOP for ChatGPT exact-source review; no automatic correction,
rerun, PR, branch creation, integration or B2 acquisition is authorized.


### Corrective focused verification

All commands ran from the exact task worktree, with bytecode/cache writes
disabled and a fresh external pytest basetemp for each group. The existing
isolated interpreter/toolchain is
F:\AI\temp\arch146-b1-c3-toolchain-b090b5bf460b46ffacc43988e0eead14\Scripts\python.exe
(Python 3.14.3, Ruff 0.17.3). The shared development environment was not modified.

- 258 passed: certification test_results.py, test_lanes.py, test_source.py
  and checkpoint test_prepublication_admission_selects_infrastructure_coherence_tests.
- 695 passed: historical_research_pre_b2, historical_research_dataset,
  historical_research_acquisition_custody, checkpoint test_source_authority,
  current Alpaca authentication/generation/staging-cleanup and Alpaca HTTP modules.
- 962 passed, one expected non-Windows assertion skipped on Windows:
  checkpoint test_core/test_ci, certification test_profiles and retained
  windows_effectful_capture_credentials/security modules.

Each group used python -B -m pytest -q -p no:cacheprovider, the named exact
modules, --tb=short and a fresh purpose-prefix-plus-GUID external --basetemp.
The initial local fixture failure was corrected by deriving synthetic planner
fixtures from frozen timing membership plus synthetic future modules; it
required no historical timing/count/hash update. The initial shared Ruff 0.15.21
mismatch was resolved by selecting the existing isolated 0.17.3 toolchain.
No CI debugging push occurred.

Whole-root non-mutating Ruff check/format-check and git diff --check must pass
on the final candidate. General ops.ps1 admit owns the final clean committed
FEATURE/PROSPECTIVE_DEVELOP proof. These focused results grant no canonical
certification or host/effect authority.
