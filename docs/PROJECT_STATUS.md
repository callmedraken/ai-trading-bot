# Project Status and Roadmap

This is the canonical high-level project status for AI Trading Bot. Detailed subsystem contracts remain in `docs/architecture/` and `docs/validation/`; the canonical cross-chat resume document is `docs/AI_TRADING_BOT_HANDOFF.md`.

## Product objective

Build a conservative automated trading platform that progresses through historical research, deterministic simulation, manual paper, unattended paper, long paper soak, broker-paper, live-readiness certification, tiny restricted live, mature automated operation, and a polished GUI.

**Production/live trading remains NO-GO.**

Stable product constraints remain: US stocks/ETFs, long-only, no margin/leverage/options/shorts/crypto, deterministic risk approval, paper-by-default, and complete auditability.

## Repository/worktree state

Accepted integrated `develop` baseline:

```text
bd88ee966bff455f9fc897d6cfdfafdd807f27e2
docs: repair integrated GUI status
```

Current P3-R1 context:

```text
worktree: F:\AI\worktrees\ai-trading-bot-p3-r1
branch: feature/p3-r1-recovery-implementation
Architecture-101 source-certified checkpoint: fad6bfe6fb3fc3af96902d8df300c1cef98e7687
Architecture-101 source-certified tree: 7adb9bf17997f5236846d68443ed2a17011c58d6
```

The main `F:\AI\ai-trading-bot` worktree remains the GUI worktree. The integration harness remains `F:\AI\ai-trading-bot-integration`. Preserve unrelated generated/untracked reports and historical pytest/cache evidence.

## Frozen C3 / production state

Accepted C3 release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider C3 effects are consumed. Call #5 remains permanently `FAILED / CONFIRMED`; call #6 remains permanently `SUCCEEDED / CONFIRMED / SUCCESS_SELECTED` and must never be rerun. Provider call #7 is not authorized.

Frozen production identities/paths:

```text
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
Creator SID: S-1-5-21-1397534616-3988210162-180023805-1005
Fixed runtime: F:\AITradingBot\runtime\python.exe
Production temp: F:\AITradingBot\temp
Authority DB: F:\AITradingBot\Authority\authority.sqlite3
Paper final root: F:\AITradingBot\Paper
Retained staging: F:\AITradingBot\.Paper.provisioning-v1
Credential policy: windows-credential-manager-alpaca-market-data/v2
```

The original Administrator paper-root publication attempt remains retained and must not be rerun. Read-only forensics remain:

```text
FINAL_EXISTS=False
STAGING_EXISTS=True
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
production authority DB: unchanged exact
```

Production recovery remains blocked.

## Architecture 94 paper cycle

Accepted P1:

```text
1028e60b99c27cef0994f40d6ce381392abfb0f8
```

Accepted P2:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
```

The one supervised production P2 reread of durable successful C3 call #6 passed and must not be rerun. Architecture 94 remains simulated paper only.

## P3-R1 architecture line

Current authoritative security architecture:

```text
97  recovery-signing trust re-establishment
98  Windows Software KSP machine-key security contract
99  dedicated ordinary non-admin test principal
100 protected account-ceremony evidence root
101 split-authority qualification-rights collection
```

Candidate identity remains fixed by name only until a separately authorized create-new ceremony:

```text
P3R1KspTestUser
candidate SID: UNKNOWN until Windows readback
```

Never predict the candidate RID/SID.

### Architecture 100 protected root

Retired root:

```text
F:\AI\p3-r1-ordinary-nonadmin-principal-v1
```

Current protected root:

```text
F:\p3-r1-ordinary-nonadmin-principal-v2
```

Architecture-100 source certification remains historical accepted evidence at:

```text
commit: 8cfbbd3a30eb704e6acfc1866bf2ed752879e231
tree:   fc682a5baf35f2f2e8b01c9f8f04ce318681ee85
focused: 47 passed
legacy clean-harness recovery: 758 passed
Ruff/diff checks: passed
```

Architecture 100's one-shot ambiguous root-creation rule remains unchanged: once an authorized root-creation call may have begun, an unexpected/ambiguous process loss consumes that execution authorization. Do not blindly rerun even if the fixed root later appears absent; stop for read-only reconciliation and review.

### Architecture 101 split qualification authority

The restarted Architecture-100 readiness sequence had reached:

```text
Gate 1  source/tool identity                         PASS
Gate 2  F:\ fixed NTFS + parent namespace authority PASS
Gate 3  roots + candidate-name absence               PASS
Gate 4A local-group topology                         PASS
Gate 4B password/account policy                      PASS
Gate 4C ordinary LSA account-rights baseline         BLOCKED
```

Gate 4C observed `LsaEnumerateAccountRights` returning `0xC0000022 STATUS_ACCESS_DENIED` from the intended ordinary non-elevated PowerShell process. Architecture 101 treats that as a real least-privilege boundary rather than bypassing it.

Architecture 101 freezes this split:

```text
genuine candidate process:
  candidate account/group/token/privilege/INTERACTIVE/Performance-Log-Users facts
  no LsaEnumerateAccountRights call

revalidated elevated creator:
  read-only LSA account-right enumeration for
  candidate SID UNION exact candidate-token group SIDs

creator reconciliation:
  strict candidate schema
  independent account/group/edge reread
  EXACT_CANDIDATE_CONSOLE_MATCH
  fresh creator-token gate
  exact LSA target/query/result reconciliation
  only then retained qualification evidence
```

Schemas:

```text
candidate observation: p3-r1-candidate-qualification-observation/v1
split qualification:   p3-r1-split-qualification-observation/v1
ceremony evidence:      p3-r1-ordinary-nonadmin-principal-evidence/v3
protected root path:    F:\p3-r1-ordinary-nonadmin-principal-v2
```

## Architecture 101 source certification — ACCEPTED

Source implementation checkpoint:

```text
commit: fad6bfe6fb3fc3af96902d8df300c1cef98e7687
tree:   7adb9bf17997f5236846d68443ed2a17011c58d6
message: test: split P3-R1 qualification rights authority
```

Changed exactly:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

Focused implementation verification:

```text
63 passed
strengthened SID regression: 1 passed
Ruff check: passed
Ruff format check: passed
git diff --check: passed
```

Broad source certification used the already-reviewed two-slice Windows harness strategy rather than deliberately repeating the known-invalid P3 legacy `.pytest_cache` path.

Current-worktree non-legacy slice:

```text
3494 passed
24 skipped
runtime: 381.82s
Ruff check: passed
Ruff format check: 418 files already formatted
git diff --check: passed
HEAD/tree unchanged exact
worktree clean
```

Legacy clean-harness slice:

```text
758 passed
runtime: 1214.95s
```

The legacy harness first proved the two frozen test blobs, then forced:

```text
PYTHONPATH=F:\AI\worktrees\ai-trading-bot-p3-r1\src
```

and printed exact source provenance for:

```text
trading_bot.market_data
trading_bot.runtime.windows_authority
trading_bot.runtime.windows_authority_schema
trading_bot.runtime.windows_transactional_authority
```

All four resolved under the reviewed P3-R1 source worktree. Final P3-R1 HEAD/tree remained exact and `git status --short` was empty.

Therefore:

```text
ARCHITECTURE_101_SOURCE_DIFF=ACCEPTED
ARCHITECTURE_101_SOURCE_CERTIFICATION=ACCEPTED
SOURCE_CERTIFIED_HEAD=fad6bfe6fb3fc3af96902d8df300c1cef98e7687
SOURCE_CERTIFIED_TREE=7adb9bf17997f5236846d68443ed2a17011c58d6
```

No account/root/password/group/KSP/provider/production effect occurred during implementation or certification.

## Immediate next milestone — restart P3-R1 readiness from Gate 1

The pre-Architecture-101 Gate 1 through Gate 4B observations remain useful discovery evidence only. They are not execution authority after the source/protocol change.

Execution readiness must restart from Gate 1 against the exact Architecture-101 source-certified checkpoint and later include a read-only **elevated creator LSA probe** using the source-owned native path. Ordinary LSA access is no longer part of the design and must not be tested as a qualification requirement.

Required order:

```text
restart read-only readiness Gate 1 against Architecture-101 source-certified checkpoint
-> re-prove filesystem/root/account/group/policy prerequisites as required
-> prove genuine elevated creator token + read-only creator LSA capability
-> freeze exact future source-enablement diff and one-shot root-creation operator rule
-> ChatGPT accepts complete readiness freeze
-> separate explicit effect-authorization discussion
-> protected evidence-root/account ceremony
-> separate authorized genuine candidate interactive qualification
-> creator-side LSA reconciliation
-> later KSP denial experiment / recovery gates
```

## Effect authorization state

Still **NOT AUTHORIZED**:

- protected evidence-root creation or ACL mutation;
- ceremony evidence publication;
- password prompt/capture;
- `P3R1KspTestUser` create/reset/delete/rename/enable/disable;
- candidate interactive logon;
- local-group mutation;
- LSA policy/account-right mutation;
- disposable KSP native execution/key creation/signature/private export;
- production recovery-key creation/signing/recovery;
- provider call #7;
- broker/live trading;
- P4/P5/P6 production effects.

`ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false` and the `NOT-AUTHORIZED` authorization ID remain mandatory until a later separately reviewed source-enablement checkpoint.

## Workflow invariants

- ChatGPT/Sol owns architecture, security/authority review, exact GitHub diff review, test gates, merge/deployment/production decisions, and next milestone.
- ChatGPT may directly perform tiny scoped work/docs closeout.
- Codex may implement bounded work and, when explicitly authorized, exact-file stage, commit, and ordinary-push after focused gates pass.
- Never `git add .` or `git add -A`.
- Startup worktree/branch/HEAD mismatch is a STOP; no self-correction.
- Every controlled Windows pytest run uses a fresh external `F:\AI\temp\pytest\<unique>` and normally `-p no:cacheprovider`.
- Preserve inaccessible historical `.pytest_cache` state and unrelated generated/untracked reports.
- Use the validated clean integration harness with exact test blobs, forced source provenance, and printed `__file__` only when the legacy harness contract permits it.
- Under Windows PowerShell 5.1, prefer piping a here-string to Python stdin for quote-sensitive provenance code instead of `python -c`.
- No merge/rebase/force-push/amend/PR metadata/review-thread changes without explicit approval.

## GUI status

GUI-A1 through GUI-A7 remain accepted/integrated read-only presentation/inspection work. GUI code does not own credentials, production authority, paper mutation, recovery, brokerage, or execution.

## Documentation workflow

At every accepted checkpoint update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

Update `docs/AI_DEVELOPMENT_WORKFLOW.md` only for a new reusable workflow rule. Git-tracked docs are authoritative; uploaded copies are mirrors.
