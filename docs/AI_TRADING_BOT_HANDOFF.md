# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Integration branch:** `develop`  
**Accepted integrated baseline:** `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`  
**P3-R1 worktree:** `F:\AI\worktrees\ai-trading-bot-p3-r1`  
**P3-R1 branch:** `feature/p3-r1-recovery-implementation`  
**Architecture-100 source-certified checkpoint:** `8cfbbd3a30eb704e6acfc1866bf2ed752879e231`  
**Architecture-100 source-certified tree:** `fc682a5baf35f2f2e8b01c9f8f04ce318681ee85`  
**Architecture-101 docs checkpoint:** `4e9e4de829376e42a68acca158ab1d4f4c01a241`  
**Production/live trading:** NO-GO

> This Git-tracked handoff is the canonical cross-chat resume document. Uploaded
> Project copies are mirrors only. Always prove the live worktree, branch, and
> HEAD before acting. Architecture/validation documents and Git history remain
> authoritative for detailed contracts and historical evidence.

---

## 1. Product goal

Build a conservative automated trading platform that progresses through:

**historical research → deterministic simulation → manual paper → unattended
paper → long paper soak → broker-paper → live-readiness certification → tiny
restricted live → mature automated operation → polished GUI.**

AI/strategy is always subordinate to deterministic risk, reviewed authority,
credential isolation, durable evidence, brokerage/reconciliation,
operating-mode controls, and explicit operator safety gates.

---

## 2. Current worktrees and branch routing

```text
P3-R1 implementation:
  F:\AI\worktrees\ai-trading-bot-p3-r1
  feature/p3-r1-recovery-implementation

paper-cycle lineage:
  F:\AI\ai-trading-bot-paper
  feature/reliable-manual-paper-cycle

integration:
  F:\AI\ai-trading-bot-integration
  develop

GUI worktree:
  F:\AI\ai-trading-bot
  feature/gui-foundation

C3 worktree:
  F:\AI\ai-trading-bot-c3
  accepted C3 feature history
```

Do not reuse another active worktree for P3-R1. Do not clean, reset, rebase,
move, delete, take ownership of, or repair unrelated worktrees or retained
evidence.

---

## 3. Mandatory ChatGPT/Codex workflow

ChatGPT/Sol owns architecture, Windows-security/authority review, debugging
strategy, exact GitHub diff review, test/certification gates, production-authority
review, and next-step planning. ChatGPT may directly handle tiny scoped work and
canonical docs closeout. Codex is a bounded implementation agent.

Model routing:

```text
tiny/simple scoped work                   -> ChatGPT direct
localized/mechanical/frozen contract      -> Luna Extra High
subtle bounded deterministic implementation -> Sol Medium
native Windows/security/authority/locking/
ordering/crash-recovery/architecture      -> Sol High
```

Do not use subagents unless explicitly requested.

Every bounded Codex task begins with:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
```

The outputs must equal the exact worktree, branch, and HEAD supplied in the task.
Any mismatch is a hard STOP. Codex must not self-correct with checkout/switch,
reset, rebase, clean, branch recreation, or worktree operations.

After required focused gates pass, Codex may exact-file stage, commit, and
ordinary fast-forward push the current approved feature branch when the prompt
authorizes that checkpoint. Never use `git add .` or `git add -A`; stage only the
exact authorized files. Never amend, rebase, merge, force-push, alter PR metadata,
resolve review threads, or absorb unrelated work without explicit approval.

Implementation flow:

```text
ChatGPT freezes architecture/scope
-> Codex proves startup gate
-> Codex changes only bounded files
-> Codex runs focused isolated tests/checks
-> if authorized, Codex exact-stages + commits + ordinary-pushes
-> ChatGPT reviews authoritative GitHub commit/diff
-> user runs broad/full local certification after source-diff acceptance
-> execution/deployment/operator effects remain separate later gates
```

---

## 4. Windows pytest isolation and legacy harness rule

Every controlled Windows pytest invocation uses a fresh explicit external
basetemp:

```text
F:\AI\temp\pytest\<fresh-unique-name>
```

and normally:

```text
-p no:cacheprovider
```

when cache behavior is irrelevant.

Never delete/repair/move historical `.pytest_cache` state merely to make a gate
pass. Legacy authority harnesses may hard-code worktree `.pytest_cache` scratch;
if that scratch is inaccessible, use the already validated clean-harness method
only when the test contract permits it:

1. preserve the inaccessible historical cache;
2. prove the legacy test blobs are exact;
3. run from the validated clean integration harness;
4. force `PYTHONPATH` to the exact reviewed P3-R1 source;
5. print and verify affected module `__file__` provenance;
6. rerun only the invalidated legacy slice;
7. restore `PYTHONPATH` and re-prove the reviewed checkpoint.

Under Windows PowerShell 5.1, avoid quote-sensitive `python -c` provenance
snippets; pipe a here-string to Python stdin instead.

---

## 5. Frozen C3 production state

Accepted C3 release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider C3 effects are consumed. Call #5 remains permanently
`FAILED / CONFIRMED`; call #6 remains permanently `SUCCEEDED / CONFIRMED` and
`SUCCESS_SELECTED`. Never rerun call #6 and never authorize provider call #7
without a new architecture checkpoint.

Frozen production facts include:

```text
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
Creator SID: S-1-5-21-1397534616-3988210162-180023805-1005
Fixed runtime: F:\AITradingBot\runtime\python.exe
Production TEMP/TMP: F:\AITradingBot\temp
Authority root: F:\AITradingBot\Authority
Authority DB: F:\AITradingBot\Authority\authority.sqlite3
Paper final root: F:\AITradingBot\Paper
Paper retained staging root: F:\AITradingBot\.Paper.provisioning-v1
Credential policy: windows-credential-manager-alpaca-market-data/v2
```

---

## 6. Architecture 94 paper-cycle status

P1 accepted:

```text
1028e60b99c27cef0994f40d6ce381392abfb0f8
fix: bind Architecture 94 P1 provenance
```

P2 fully accepted:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
fix: bind Architecture 94 P2 permit issuance
```

The one supervised production P2 reread of already-durable successful C3 call #6
passed and **must not be rerun**.

Architecture 94 remains simulated paper only: no broker/live trading, unattended
scheduling, automatic retry, or additional C3 provider effect.

---

## 7. P3 retained production-recovery state

The first Administrator paper-root publication attempt failed and remains
retained. Do not rerun it. Read-only resolution established:

```text
FINAL_EXISTS=False
STAGING_EXISTS=True
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
production authority DB: unchanged exact
```

Architectures 95 and 96 remain the retained-staging recovery and signed recovery
authorization contracts. The staging tree must not be deleted, renamed, repaired,
regenerated, or implicitly recovered.

---

## 8. Architectures 97–101 — current P3-R1 security line

Current architecture documents:

```text
docs/architecture/97-p3-r1-recovery-signing-trust-reestablishment.md
docs/architecture/98-p3-r1-ksp-machine-key-security-contract.md
docs/architecture/99-p3-r1-ordinary-nonadmin-test-principal.md
docs/architecture/100-p3-r1-protected-account-ceremony-evidence-root.md
docs/architecture/101-p3-r1-split-authority-qualification-rights.md
```

Related validation documents:

```text
docs/validation/p3-r1-ordinary-nonadmin-test-principal-creation-ceremony.md
docs/validation/reliable-manual-paper-cycle-p3-r1-ordinary-nonadmin-test-principal.md
docs/validation/p3-r1-ksp-disposable-test-harness.md
```

Architecture 97 re-establishes the recovery-signing trust path. Architecture 98
freezes the Windows Software KSP machine-key security experiment. Architecture 99
adds the separate ordinary non-admin denial perspective using a dedicated new
local test principal. Architecture 100 corrects the account-ceremony retained
filesystem boundary. Architecture 101 corrects the qualification authority split
for LSA account-right reads.

### Architecture 99 identity

Exact candidate name:

```text
P3R1KspTestUser
```

Its SID remains deliberately unknown until Windows creates the account and the
helper independently reads it back. Never predict a RID. The candidate may never
become production runtime, Trading, recovery, signing, KSP owner/ACE, Credential
Manager, or other production authority.

Accepted Architecture-99 docs checkpoint:

```text
89506d9104b4699d19eee96aac2ad0b18ee25e4a
docs: define P3-R1 ordinary non-admin test principal
```

Creation-ceremony contract checkpoint:

```text
022960a3f242ded927edf3ae4667f87e724aeb19
docs: define P3-R1 test-user creation ceremony
```

The ceremony uses one-shot direct Netapi32 account creation, dual name-absence,
SecureString handling, Windows SID readback, deterministic conditional
BUILTIN\Users assignment, genuine token qualification, sanitized retained
evidence, and no automatic retry/rollback/cleanup/repair.

### Architecture 100 source-certified helper

The first disabled helper checkpoint was:

```text
d509537b88f66ef244d326e5417d38d9e5f25f53
test: add disabled P3-R1 test-user ceremony helper
```

Architecture 100 froze:

```text
retired root:
  F:\AI\p3-r1-ordinary-nonadmin-principal-v1

protected root:
  F:\p3-r1-ordinary-nonadmin-principal-v2
```

The source-certified implementation checkpoint is:

```text
8cfbbd3a30eb704e6acfc1866bf2ed752879e231
test: implement protected P3-R1 ceremony evidence root

tree:
fc682a5baf35f2f2e8b01c9f8f04ce318681ee85
```

It changed only:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

Architecture-100 source certification remains accepted:

```text
focused helper gate: 47 passed
broad repository run: 3862 passed before legacy harness environment failures
legacy harness recovery: 758 passed
Ruff check: passed
Ruff format check: passed
git diff --check: passed
reviewed HEAD/tree unchanged exact
```

The broad failures were environmental hard-coded legacy `.pytest_cache` scratch
failures, not source regressions. Exact affected legacy test blobs passed 758/758
from the validated integration harness with P3-R1 `PYTHONPATH` and printed module
provenance.

The helper remains disabled:

```text
ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false
ACCOUNT_EFFECT_AUTHORIZATION_ID=NOT-AUTHORIZED-P3R1-ORDINARY-NONADMIN-PRINCIPAL-V1
```

No password/root/ACL/account/group/KSP/provider/production effect occurred.

---

## 9. Restarted readiness result that triggered Architecture 101

Before Architecture 101, the local worktree was clean at:

```text
HEAD: 2040e6dbc4e7418a9275df139aaca7428930380d
tree: e481496fad89b2f82ba26accbe45029d995e583e
```

The Architecture-100 readiness restart produced:

```text
Gate 1  exact source/tool identity                     PASS
Gate 2  F:\ volume + parent namespace authority       PASS
Gate 3  root/account namespace absence                 PASS
Gate 4A local-group topology                           PASS
Gate 4B password/account policy                        PASS
Gate 4C LSA account-rights baseline                    BLOCKED
```

Key discovery facts:

```text
F:\ serial: 0x6E962F80
F:\ fixed local NTFS: PASS
persistent ACLs: PASS
F:\ reparse point: false
parent untrusted FILE_DELETE_CHILD: absent
parent untrusted WRITE_DAC: absent
parent untrusted WRITE_OWNER: absent

retired v1 root: absent
new v2 root: absent
P3R1KspTestUser: absent by NetUserGetInfo and fully resumed NetUserEnum
BUILTIN\Users mapping: PASS

BUILTIN\Users local-group nesting: NONE
INTERACTIVE -> Performance Log Users: present
Performance Log Users members:
  creator SID ...-1005
  NT AUTHORITY\INTERACTIVE S-1-5-4

password policy:
  min length 0
  max age 3628800 sec
  min age 0
  history length 0
  lockout threshold 0
creator enabled: true
Trading enabled: true
```

These observations are **discovery evidence only** after the Architecture-101
source change. They do not remain perpetual readiness authority.

### Gate 4C blocker

The intended ordinary non-elevated Windows PowerShell 5.1 process attempted the
same LSA surface used by the source-certified helper:

```text
LsaOpenPolicy(... POLICY_LOOKUP_NAMES=0x00000800 ...)
LsaEnumerateAccountRights(...)
```

`LsaEnumerateAccountRights` returned:

```text
0xC0000022 STATUS_ACCESS_DENIED
```

for `S-1-1-0` and again for `S-1-5-32-559` Performance Log Users. Subsequent
literal `...=PASS` strings printed by the interactive shell after the exception
were invalid and were not accepted.

The source-certified helper's ordinary branch currently executes
`native.Observation()`, and that path calls `Rights(...)`. Therefore the disabled
source remains correctly certified as source but is **not execution-ready** for
the intended least-privileged qualification session.

---

## 10. Architecture 101 — split-authority qualification rights

Accepted docs checkpoint:

```text
4e9e4de829376e42a68acca158ab1d4f4c01a241
docs: split P3-R1 qualification rights authority
```

Architecture 101 does not give the ordinary user more LSA access and does not
weaken the right classifier. It separates the two native evidence authorities.

### Candidate owns genuine candidate-token facts

The genuine candidate process must still prove:

```text
exact candidate SID
primary token
not elevated
no thread impersonation
Administrators absent
enabled INTERACTIVE
exact token groups/attributes
exact held token privileges
all held token privileges classified ACCEPTED
direct local groups exactly BUILTIN\Users
indirect/direct consistency
no unreviewed nested authority
Performance Log Users provenance only through reviewed INTERACTIVE edge
```

The candidate no longer calls `LsaEnumerateAccountRights`.

It prints one strict canonical object:

```text
schema: p3-r1-candidate-qualification-observation/v1
collection_method: operator_observed_candidate_console
```

with closed fields:

```text
schema
account
direct_view
indirect_view
relevant_edges
effective_groups
candidate_token
collection_method
performance_log_users
```

### Creator owns LSA account-right facts

After exact candidate-console transfer, creator-side fresh account/group/edge
reconciliation, and operator confirmation using exactly:

```text
EXACT_CANDIDATE_CONSOLE_MATCH
```

the revalidated fully elevated creator derives the exact rights target set:

```text
candidate SID
UNION
all candidate_token group SIDs
```

and performs read-only native LSA enumeration for every target.

Accepted outcomes are only:

```text
STATUS_SUCCESS
STATUS_OBJECT_NAME_NOT_FOUND   # exact no-LSA-account-object case
```

`STATUS_ACCESS_DENIED` or any other error is a STOP. No LSA policy/group/ACL
mutation may be used to manufacture a pass.

The creator builds a strict `rights_collection` containing its creator token,
method, `policy_access=2048`, exact sorted target SIDs, and per-target query
status/count. Every returned right keeps the frozen disposition classifier; any
`REJECTED` or `UNRESOLVED` right blocks qualification.

### Final qualification object and evidence schema

The creator constructs the only object eligible for `QUALIFICATION_OBSERVED`:

```text
p3-r1-split-qualification-observation/v1
```

with:

```text
schema
candidate_observation
candidate_observation_sha256
rights
rights_collection
```

Neither candidate-only evidence nor creator-rights-only evidence can qualify the
account.

The strict account-ceremony evidence schema advances, before any evidence root
or records exist, to:

```text
p3-r1-ordinary-nonadmin-principal-evidence/v3
```

The Architecture-100 protected root path remains unchanged:

```text
F:\p3-r1-ordinary-nonadmin-principal-v2
```

There is no migration or adoption path because no v2 ceremony evidence exists.

---

## 11. Immediate next milestone — Architecture-101 source correction

**Do not continue readiness from Gate 4C.** The next checkpoint is a disabled,
source-only Sol High implementation.

Exact authorized source scope:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

Required behavior is frozen by Architecture 101:

1. evidence schema v3; protected root path unchanged;
2. candidate observation excludes LSA rights and performs all candidate-owned
   token/group/privilege/provenance gates before output;
3. candidate branch must never open LSA policy or enumerate account rights;
4. creator imports only the strict candidate object, independently re-reads
   account/groups/edges, reprints exact canonical candidate bytes, and requires
   `EXACT_CANDIDATE_CONSOLE_MATCH`;
5. creator repeats its full token gate before rights collection;
6. creator derives target SIDs from candidate SID + exact token groups and
   performs all native LSA queries;
7. strict per-target result reconciliation and right classification;
8. final split observation required before `QUALIFICATION_OBSERVED`,
   `GROUPS_QUALIFIED`, or `TOKEN_QUALIFIED`;
9. all Architecture-100 protected-root/account/Users/one-shot behavior preserved;
10. `ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false` and not-authorized ID preserved.

Required focused test themes include ordinary-no-LSA-call, creator success,
`STATUS_OBJECT_NAME_NOT_FOUND`, creator access-denied rejection, target-set
mismatch/duplicates/extras/missing targets, transfer/hash mismatch, dangerous or
unknown rights, wrong creator token, and a complete successful split lifecycle
using fakes only. Existing Architecture-100 tests must remain passing.

This is a native Windows/security/authority change: use **Codex Sol High**, not
Luna Extra High.

Codex should run focused tests/checks only during implementation. If they pass and
only the three authorized files changed, Codex may exact-stage, commit, and
ordinary-push the feature branch when the implementation prompt explicitly
permits it.

ChatGPT then reviews the exact GitHub diff before any broad certification.

---

## 12. Readiness after Architecture-101 source certification

Because source and qualification protocol change, the prior Gate 1–4B results do
not allow readiness to resume from Gate 4C.

After the new source is accepted and fully source-certified:

```text
restart complete read-only readiness from Gate 1
```

The new readiness sequence must include an elevated creator-side LSA probe using
the exact source-owned native path. It must **not** attempt to prove ordinary LSA
access, because ordinary rights enumeration is no longer part of the design.

All root/account/group/password/KSP effects remain disabled during readiness.

Architecture 100's root-create ambiguity rule remains non-negotiable: once an
authorized root-creation call may have begun, unexpected process loss consumes
that authorization and permits only read-only reconciliation, never a blind
relaunch even if the fixed root subsequently appears absent.

---

## 13. Effect authorization — still blocked

The following remain **NOT AUTHORIZED**:

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

Production retained staging must remain untouched. The failed publisher must not
be rerun. No provider call #7 is authorized.

Expected chain from here:

```text
Architecture-101 source implementation
-> ChatGPT exact GitHub diff/security review
-> focused + broad source certification
-> restart read-only readiness from Gate 1
-> ChatGPT acceptance of complete frozen readiness
-> separate explicit filesystem/account effect authorization discussion
-> protected root/account ceremony
-> genuine candidate qualification + creator LSA reconciliation
-> KSP SID/source freeze
-> separately authorized disposable KSP denial experiment
-> recovery only after all independent recovery gates pass
```

---

## 14. GUI and stable product constraints

GUI-A1 through GUI-A7 are fully accepted and integrated. GUI capabilities remain
read-only presentation/inspection boundaries and do not own production authority,
credentials, paper-account mutation, retry, recovery, brokerage, or execution.

Stable product constraints:

- US stocks and ETFs;
- long-only;
- no margin or leverage;
- no options;
- no short selling;
- no crypto;
- deterministic risk approval for every order;
- paper mode by default;
- complete auditability.

---

## 15. Closeout rule

At every accepted checkpoint review/update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

Update `docs/AI_DEVELOPMENT_WORKFLOW.md` only when a reusable workflow lesson is
new and not already covered. Architecture 101 is a subsystem authority correction,
not a new generic workflow rule, so no workflow-doc change is required here.

Git-tracked documents are authoritative. Documentation closeout does not itself
authorize merge, rebase, force-push, amend, review-thread resolution, PR metadata
changes, production/provider effects, Windows security effects, or unrelated
modifications.
