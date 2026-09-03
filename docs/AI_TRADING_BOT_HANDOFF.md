# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Accepted integrated baseline:** `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`  
**P3-R1 worktree:** `F:\AI\worktrees\ai-trading-bot-p3-r1`  
**P3-R1 branch:** `feature/p3-r1-recovery-implementation`  
**Architecture-101 source-certified checkpoint:** `fad6bfe6fb3fc3af96902d8df300c1cef98e7687`  
**Architecture-101 source-certified tree:** `7adb9bf17997f5236846d68443ed2a17011c58d6`  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded copies are mirrors only. Always prove the live worktree, branch, HEAD, and clean state before acting.

## 1. Product goal

Build a conservative automated trading platform progressing through:

**historical research → deterministic simulation → manual paper → unattended paper → long paper soak → broker-paper → live-readiness → tiny restricted live → mature automated operation → polished GUI.**

Stable constraints: US stocks/ETFs, long-only, no margin/leverage/options/shorts/crypto, deterministic risk approval, paper-by-default, complete auditability.

## 2. Worktrees and branch routing

```text
P3-R1:
  F:\AI\worktrees\ai-trading-bot-p3-r1
  feature/p3-r1-recovery-implementation

paper lineage:
  F:\AI\ai-trading-bot-paper
  feature/reliable-manual-paper-cycle

integration / clean legacy harness:
  F:\AI\ai-trading-bot-integration
  develop

GUI/main worktree:
  F:\AI\ai-trading-bot
```

Do not reuse another active worktree for P3-R1. Preserve unrelated generated/untracked reports and historical pytest/cache evidence.

## 3. ChatGPT/Codex workflow

ChatGPT/Sol owns architecture, Windows security/authority review, exact GitHub diff review, debugging strategy, test/certification gates, merge/deployment/production decisions, and next-step planning. ChatGPT may directly perform tiny scoped work and docs closeout.

Model routing:

```text
tiny/simple                                  -> ChatGPT direct
localized/mechanical/frozen contract         -> Luna Extra High
subtle bounded deterministic implementation -> Sol Medium
native Windows/security/authority/recovery   -> Sol High
```

Do not use subagents unless explicitly requested.

Every bounded Codex task starts with:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
```

Any worktree/branch/HEAD mismatch is a STOP. Codex must not self-correct with checkout/switch/reset/rebase/clean/worktree operations.

After required focused gates pass, Codex may exact-file stage, commit, and ordinary-push the approved feature branch when explicitly authorized. Never `git add .` or `git add -A`; stage only exact authorized files. No amend/rebase/merge/force-push/PR metadata/review-thread changes or unrelated cleanup without explicit approval.

## 4. Windows pytest / clean-harness rule

Every controlled Windows pytest invocation uses:

```text
--basetemp F:\AI\temp\pytest\<fresh-unique>
-p no:cacheprovider
```

unless the test specifically requires cache behavior.

Do not delete/repair/move historical `.pytest_cache` state merely to make a gate pass. Two legacy authority files hard-code a P3 worktree `.pytest_cache` scratch path that is inaccessible on this host. Their validated recovery procedure is:

1. prove exact legacy test blobs;
2. run them from `F:\AI\ai-trading-bot-integration`;
3. force `PYTHONPATH` to the exact reviewed P3 source;
4. print module `__file__` provenance;
5. run only the invalidated legacy slice;
6. restore `PYTHONPATH` and re-prove P3 HEAD/tree/clean.

Under Windows PowerShell 5.1, prefer a here-string piped to Python stdin for quote-sensitive provenance code rather than `python -c`.

## 5. Frozen C3 production state

Accepted C3 release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider calls are consumed. Call #5 remains permanently `FAILED / CONFIRMED`. Call #6 remains permanently `SUCCEEDED / CONFIRMED / SUCCESS_SELECTED`; never rerun it. Provider call #7 is not authorized.

Selected call #6 snapshot/artifact remain frozen:

```text
snapshot: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
```

Production identities/paths:

```text
host: DESKTOP-I4DOKM7
creator SID: S-1-5-21-1397534616-3988210162-180023805-1005
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
runtime: F:\AITradingBot\runtime\python.exe
production temp: F:\AITradingBot\temp
authority DB: F:\AITradingBot\Authority\authority.sqlite3
paper final: F:\AITradingBot\Paper
retained staging: F:\AITradingBot\.Paper.provisioning-v1
credential policy: windows-credential-manager-alpaca-market-data/v2
```

The original Administrator paper-root publication attempt failed at rename and remains retained. Never rerun the publisher. Read-only state remains:

```text
FINAL_EXISTS=False
STAGING_EXISTS=True
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
```

Production recovery remains blocked.

## 6. Architecture 94 paper-cycle line

```text
P1: 1028e60b99c27cef0994f40d6ce381392abfb0f8
P2: a810122a96b6fc90da25d71eede8da64b7272c98
```

The one supervised P2 production reread of durable successful C3 call #6 passed and must not be rerun. Architecture 94 remains simulated paper only.

## 7. P3-R1 architectures 97–101

```text
97 recovery signing trust re-establishment
98 Windows Software KSP machine-key security contract
99 dedicated ordinary non-admin test principal
100 protected account-ceremony evidence root
101 split-authority qualification-rights collection
```

Candidate fixed name:

```text
P3R1KspTestUser
```

Its SID is unknown until a separately authorized create-new ceremony and independent Windows readback. Never predict a RID.

### Architecture 100

Retired root:

```text
F:\AI\p3-r1-ordinary-nonadmin-principal-v1
```

Protected root:

```text
F:\p3-r1-ordinary-nonadmin-principal-v2
```

Historical source-certified checkpoint:

```text
commit: 8cfbbd3a30eb704e6acfc1866bf2ed752879e231
tree:   fc682a5baf35f2f2e8b01c9f8f04ce318681ee85
focused: 47 passed
legacy clean-harness recovery: 758 passed
```

Architecture-100 root ambiguity rule remains binding: once an authorized root-creation call may have begun, ambiguous process loss consumes that execution authorization. Do not simply relaunch even if the fixed root later appears absent; stop for read-only reconciliation and review.

### Readiness discovery that triggered Architecture 101

Before Architecture 101, read-only readiness established:

```text
Gate 1  source/tool identity                         PASS
Gate 2  F:\ fixed NTFS + parent namespace authority PASS
Gate 3  roots + candidate-name absence               PASS
Gate 4A local-group topology                         PASS
Gate 4B password/account policy                      PASS
Gate 4C ordinary LSA rights                          BLOCKED
```

Discovery facts included:

```text
F:\ serial: 0x6E962F80
F:\ fixed NTFS + persistent ACLs: PASS
F:\ reparse: false
untrusted parent FILE_DELETE_CHILD / WRITE_DAC / WRITE_OWNER: absent
retired v1 root: absent
new v2 root: absent
P3R1KspTestUser: absent by NetUserGetInfo + resumed NetUserEnum
BUILTIN\Users mapping: PASS
BUILTIN\Users local-group nesting: NONE
INTERACTIVE -> Performance Log Users: present
password lockout threshold: 0
creator enabled: true
Trading enabled: true
```

These are discovery evidence only after Architecture 101; they are not perpetual readiness authority.

Gate 4C observed ordinary `LsaEnumerateAccountRights` returning:

```text
0xC0000022 STATUS_ACCESS_DENIED
```

Architecture 101 treats this as a real least-privilege boundary.

## 8. Architecture 101 contract

Candidate process owns only genuine candidate-session facts:

```text
candidate account SID continuity
primary non-elevated token
thread token absent
Administrators absent
enabled INTERACTIVE
exact token groups/attributes
held token privileges, all ACCEPTED
direct groups exactly BUILTIN\Users
indirect/direct consistency
local-group graph / Performance Log Users provenance
```

The candidate does **not** call `LsaEnumerateAccountRights`.

Candidate schema:

```text
p3-r1-candidate-qualification-observation/v1
```

After exact candidate console transfer and creator-side account/group/edge reconciliation, the operator confirms exactly:

```text
EXACT_CANDIDATE_CONSOLE_MATCH
```

The creator then repeats the full creator-token gate and performs read-only LSA rights collection for:

```text
candidate SID
UNION
exact candidate_token.groups SIDs
```

Accepted native per-target outcomes are only success or exact `STATUS_OBJECT_NAME_NOT_FOUND`. `STATUS_ACCESS_DENIED` and every other status are STOPs.

Split observation schema:

```text
p3-r1-split-qualification-observation/v1
```

Ceremony evidence schema:

```text
p3-r1-ordinary-nonadmin-principal-evidence/v3
```

Only a fully validated split observation may advance retained `QUALIFICATION_OBSERVED`, `GROUPS_QUALIFIED`, and `TOKEN_QUALIFIED` evidence.

## 9. Architecture 101 source implementation and certification

Source implementation:

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

Source review accepted the authority split: candidate observation has no LSA operation; creator performs exact target-derived rights collection after transfer reconciliation and fresh creator-token proof; v3 evidence retains only the complete split observation; Architecture-100 root/account/security behavior remains unchanged.

Focused verification:

```text
63 passed
strengthened evidence SID regression: 1 passed
Ruff: pass
diff checks: pass
```

Broad certification used two slices to avoid the known-invalid legacy P3 `.pytest_cache` harness:

```text
current P3 non-legacy slice:
  3494 passed
  24 skipped
  381.82s
  Ruff check: pass
  Ruff format: 418 files formatted
  git diff --check: pass

legacy integration-harness slice:
  exact frozen test blobs: pass
  exact P3 source provenance: pass
  758 passed
  1214.95s
```

Printed provenance for all four modules resolved under:

```text
F:\AI\worktrees\ai-trading-bot-p3-r1\src\trading_bot\...
```

Final P3 checkpoint remained:

```text
HEAD=fad6bfe6fb3fc3af96902d8df300c1cef98e7687
TREE=7adb9bf17997f5236846d68443ed2a17011c58d6
STATUS=CLEAN
```

Disposition:

```text
ARCHITECTURE_101_SOURCE_DIFF=ACCEPTED
ARCHITECTURE_101_SOURCE_CERTIFICATION=ACCEPTED
```

No ceremony/root/account/password/group/KSP/provider/production effect occurred.

## 10. Immediate next milestone — restart readiness from Gate 1

Because Architecture 101 changed reviewed source and qualification protocol, execution readiness must restart from **Gate 1** against the exact source-certified commit/tree above. Prior Gate 1–4B observations remain discovery context only.

The new readiness sequence must include a **read-only elevated creator LSA capability probe** using the same source-owned native LSA path. Do not attempt to prove ordinary LSA access; ordinary rights enumeration is no longer part of the design.

Planned order:

```text
Gate 1  exact source/helper/wrapper/tool identity + disabled-effect proof
Gate 2  fresh F:\ volume + parent namespace security
Gate 3  v1/v2 root absence + dual candidate-name absence + BUILTIN\Users mapping
Gate 4  group topology + account/password policy
Gate 5  genuine elevated creator token + read-only creator LSA capability
Gate 6  exact future enablement diff + one-shot root-creation operator rule + final readiness freeze
-> ChatGPT readiness acceptance
-> separate explicit effect-authorization discussion
```

Do not resume from the old Gate 4C stopping point.

## 11. Non-authorizations

Still not authorized:

```text
ACL_MUTATION
PROTECTED_EVIDENCE_ROOT_CREATION
CEREMONY_EVIDENCE_PUBLICATION
ACCOUNT_CREATION
WINDOWS_GROUP_MUTATION
PASSWORD_PROMPT
CANDIDATE_INTERACTIVE_LOGON
LSA_POLICY_MUTATION
LSA_RIGHTS_MUTATION
DISPOSABLE_NATIVE_EXECUTION
DISPOSABLE_TEST_KEY_CREATION
CURRENT_USER_SHADOW_CREATION
TEST_SIGNATURE
PRIVATE_EXPORT_REQUEST
PRODUCTION_RECOVERY_KEY_CREATION
PRODUCTION_SIGNING
PROVIDER_CALL_7
P3_TRADING_ACCEPTANCE
P4_PRODUCTION_EXECUTION
PRODUCTION_LIVE
```

`ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false` and the `NOT-AUTHORIZED` authorization ID remain mandatory until a later separately reviewed source-enablement checkpoint.

Additional production restrictions remain:

```text
PRODUCTION_RECOVERY_RENAME=NOT_AUTHORIZED
PRODUCTION_STAGING_TREE=PRESERVE_UNTOUCHED
STAGING_DELETE_OR_REPAIR=FORBIDDEN
PUBLISHER_RERUN=FORBIDDEN
CALLER_ASSERTED_RECOVERY_AUTHORITY=FORBIDDEN
```

## 12. Next-chat resume procedure

1. Read this file plus `docs/PROJECT_STATUS.md` and Architectures 97–101.
2. Prove P3-R1 worktree/branch/HEAD/clean state.
3. Source-certified implementation identity is `fad6bfe6...` / `7adb9bf...`; docs-only closeout commits may sit above it and must be proven source-neutral before readiness.
4. Restart read-only P3-R1 readiness from Gate 1.
5. Do not authorize any effect merely because source certification passed.
6. Keep the Architecture-100 ambiguous-root-attempt rule in every future execution authorization.
7. Include the next milestone in every verification/closeout report.
