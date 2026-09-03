# Project Status and Roadmap

This document is the canonical high-level status/roadmap for AI Trading Bot.
The canonical cross-chat handoff is `docs/AI_TRADING_BOT_HANDOFF.md`; detailed
architecture/validation documents remain authoritative for subsystem contracts,
evidence, and historical decisions.

## Long-term objective

Build a conservative automated trading platform that progresses safely through
historical research, deterministic simulation, manual paper, unattended paper,
long paper soak, broker-paper, live-readiness certification, tiny restricted
live operation, mature automated operation, and a polished end-user GUI.

**Production/live trading: NO-GO.** Live trading remains unavailable until the
separately reviewed brokerage, reconciliation, credential, operating-mode,
operator-control, long-soak, and live-readiness gates are complete.

## Current repository and worktree state

Accepted integrated `develop` baseline:

```text
bd88ee966bff455f9fc897d6cfdfafdd807f27e2
docs: repair integrated GUI status
```

Current P3-R1 development context:

```text
worktree: F:\AI\worktrees\ai-trading-bot-p3-r1
branch: feature/p3-r1-recovery-implementation
Architecture-100 source-certified checkpoint: 8cfbbd3a30eb704e6acfc1866bf2ed752879e231
Architecture-100 source-certified tree: fc682a5baf35f2f2e8b01c9f8f04ce318681ee85
Architecture-101 docs checkpoint: 4e9e4de829376e42a68acca158ab1d4f4c01a241
```

The main `F:\AI\ai-trading-bot` worktree remains the GUI worktree and must not
be reused for P3-R1 implementation. The integration worktree remains
`F:\AI\ai-trading-bot-integration`. Preserve unrelated generated/untracked
reports and historical pytest evidence.

## C3 — FULLY COMPLETE / ACCEPTED

C1 `ValidatedProductionAuthority` and C2 `WindowsTransactionalAuthority` remain
the reviewed authority foundations. C3 is the accepted bridge into real
market-data credentials, isolated native Windows child execution, Alpaca
transport, parent verification, final-artifact publication, terminal evidence,
and durable selection.

Accepted C3 production release-source checkpoint:

```text
82ba29ae2c2cc6bb3544077db0ee21868e6d5693
```

All six real-provider C3 effects are consumed. Call #5 remains
`FAILED / CONFIRMED` and permanently non-retryable. Call #6 remains
`SUCCEEDED / CONFIRMED` and `SUCCESS_SELECTED`; it must never be rerun. No
provider call #7 is authorized.

## Architecture 94 manual paper cycle

Architecture 94 remains simulated paper only. It does not authorize a broker,
live trading, unattended scheduling, automatic retry, or another C3 provider
effect.

Accepted P1:

```text
1028e60b99c27cef0994f40d6ce381392abfb0f8
fix: bind Architecture 94 P1 provenance
```

Accepted P2:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
fix: bind Architecture 94 P2 permit issuance
```

The one supervised production P2 reread of already-durable successful C3 call #6
passed and **must not be rerun**.

## P3 / P3-R1 retained production state

Frozen production identities and paths remain:

```text
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
Creator SID: S-1-5-21-1397534616-3988210162-180023805-1005
Fixed runtime: F:\AITradingBot\runtime\python.exe
Production temp: F:\AITradingBot\temp
Authority DB: F:\AITradingBot\Authority\authority.sqlite3
Paper final root: F:\AITradingBot\Paper
Paper retained staging root: F:\AITradingBot\.Paper.provisioning-v1
Credential policy: windows-credential-manager-alpaca-market-data/v2
```

The original Administrator paper-root publication attempt remains retained and
must not be rerun. Read-only recovery forensics established:

```text
FINAL_EXISTS=False
STAGING_EXISTS=True
PUBLICATION_STATE=STAGING_REQUIRES_MANUAL_RECOVERY
production authority DB: unchanged exact
```

Architectures 95 and 96 remain the retained-staging recovery and signed recovery
authorization contracts. Production recovery remains blocked.

## Architectures 97–101 — current P3-R1 security line

Current authoritative architecture documents:

```text
docs/architecture/97-p3-r1-recovery-signing-trust-reestablishment.md
docs/architecture/98-p3-r1-ksp-machine-key-security-contract.md
docs/architecture/99-p3-r1-ordinary-nonadmin-test-principal.md
docs/architecture/100-p3-r1-protected-account-ceremony-evidence-root.md
docs/architecture/101-p3-r1-split-authority-qualification-rights.md
```

Related validation/runbook documents remain:

```text
docs/validation/p3-r1-ordinary-nonadmin-test-principal-creation-ceremony.md
docs/validation/reliable-manual-paper-cycle-p3-r1-ordinary-nonadmin-test-principal.md
docs/validation/p3-r1-ksp-disposable-test-harness.md
```

Architecture 97 re-establishes recovery-signing trust. Architecture 98 freezes
the disposable Windows Software KSP machine-key security experiment.
Architecture 99 adds the dedicated ordinary non-admin identity
`P3R1KspTestUser`, whose Windows SID remains unknown until a separately
authorized create-new ceremony and Windows readback. Architecture 100 moves the
account-ceremony retained-evidence root to a protected top-level NTFS pathname.
Architecture 101 corrects the qualification authority split after a real
least-privilege LSA-read blocker was observed.

### Architecture 100 — source certified, no longer execution-ready by itself

Architecture 100 retired the unsafe account evidence location under `F:\AI`:

```text
retired: F:\AI\p3-r1-ordinary-nonadmin-principal-v1
protected root: F:\p3-r1-ordinary-nonadmin-principal-v2
```

The source-certified implementation checkpoint remains:

```text
8cfbbd3a30eb704e6acfc1866bf2ed752879e231
test: implement protected P3-R1 ceremony evidence root

tree: fc682a5baf35f2f2e8b01c9f8f04ce318681ee85
```

It changed only:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

Source certification remains accepted:

```text
focused Architecture-100 helper gate: 47 passed
broad repository run: 3862 passed before legacy harness cache failures
legacy-harness recovery: 758 passed
Ruff check: passed
Ruff format check: passed
git diff --check: passed
final reviewed HEAD/tree: unchanged exact
```

The broad-run failures were environment-invalid legacy harness scratch failures.
The exact affected legacy test blobs passed 758/758 from the validated clean
integration harness while `PYTHONPATH` and printed `__file__` provenance bound
imports to the reviewed P3-R1 source. No full-suite rerun was required for that
checkpoint.

`ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false` remains hard-coded. No password,
root, ACL, account, group, KSP, production, signing, or provider effect occurred.

### Restarted readiness observations through Gate 4C

After the Architecture-100 certification closeout, the local P3-R1 worktree was
fast-forwarded to the docs-only head that existed before Architecture 101:

```text
HEAD: 2040e6dbc4e7418a9275df139aaca7428930380d
tree: e481496fad89b2f82ba26accbe45029d995e583e
```

Read-only discovery established:

```text
Gate 1  source/tool identity                         PASS
Gate 2  F:\ fixed NTFS + parent namespace authority PASS
Gate 3  v1/v2 roots + candidate-name absence        PASS
Gate 4A local-group topology                         PASS
Gate 4B password/account policy                      PASS
Gate 4C LSA account-rights baseline                  BLOCKED
```

Important accepted observations included:

```text
F:\ volume serial: 0x6E962F80
F:\ fixed local NTFS: PASS
persistent ACLs: PASS
F:\ reparse point: false
untrusted FILE_DELETE_CHILD / WRITE_DAC / WRITE_OWNER on parent: absent

retired v1 root: absent
new v2 root: absent
P3R1KspTestUser: absent by NetUserGetInfo and fully resumed NetUserEnum
BUILTIN\Users SID/name round-trip: PASS

BUILTIN\Users nested into another local group: none
INTERACTIVE -> Performance Log Users edge: present
Performance Log Users members observed:
  creator SID ...-1005
  NT AUTHORITY\INTERACTIVE S-1-5-4

password policy discovery:
  min length 0
  max age 3628800 seconds
  min age 0
  history length 0
  lockout threshold 0
creator enabled: true
Trading enabled: true
```

These are discovery facts only after Architecture 101 because the reviewed
source/protocol is changing. They do not authorize any effect and must be
re-proved where required by the later restarted readiness sequence.

### Architecture 101 — split qualification rights authority

Gate 4C exposed a real source/execution mismatch. The ordinary non-elevated
PowerShell process opened the LSA policy lookup surface but
`LsaEnumerateAccountRights` returned:

```text
0xC0000022 STATUS_ACCESS_DENIED
```

for `S-1-1-0` and separately for Performance Log Users. The old helper's ordinary
`Observation()` path includes `Rights(...)`, so the source-certified helper could
not complete the intended genuine ordinary qualification on this host.

The Architecture-101 checkpoint is:

```text
4e9e4de829376e42a68acca158ab1d4f4c01a241
docs: split P3-R1 qualification rights authority
```

Architecture 101 does **not** grant the ordinary user more LSA authority and does
not weaken the rights check. It splits the evidence sources:

```text
genuine candidate process:
  account/group/token/privilege/INTERACTIVE/Performance-Log-Users evidence
  NO LsaEnumerateAccountRights call

revalidated elevated creator:
  exact LSA rights for candidate SID + genuine candidate token-group SIDs
  read-only only

creator reconciliation:
  exact canonical candidate-console transfer
  independent account/group/edge re-read
  operator EXACT_CANDIDATE_CONSOLE_MATCH
  creator-side LSA collection
  strict combined qualification object
```

The candidate observation schema becomes:

```text
p3-r1-candidate-qualification-observation/v1
```

The final combined qualification observation becomes:

```text
p3-r1-split-qualification-observation/v1
```

The strict account-ceremony evidence schema advances before any evidence exists:

```text
p3-r1-ordinary-nonadmin-principal-evidence/v3
```

The protected root path stays exactly:

```text
F:\p3-r1-ordinary-nonadmin-principal-v2
```

No root/evidence exists to migrate or adopt.

## Immediate next milestone — Architecture-101 disabled source correction

Readiness is stopped. Do not continue from Gate 4C and do not run the old helper
with effects enabled.

The next checkpoint is a **Sol High** Windows-security implementation bounded to:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

Required source behavior is frozen in Architecture 101. The implementation must
keep all effects disabled, remove ordinary LSA enumeration, add strict candidate
and split-observation schemas, collect LSA rights only from the revalidated
creator, reconcile exact query targets/results, and preserve all Architecture-100
root/account/security behavior.

Codex should run only focused tests/checks during implementation. After an exact
GitHub source-diff review accepts the three-file change, broad local certification
will be requested. Because source changes, a later successful source
certification must restart execution readiness from **Gate 1** again.

## Effect authorization state

Still **NOT AUTHORIZED**:

- protected evidence-root creation or ACL mutation;
- ceremony evidence publication;
- password prompt/capture;
- `P3R1KspTestUser` creation/reset/delete/rename/enable/disable;
- candidate interactive logon;
- local-group mutation;
- LSA policy or account-right mutation;
- KSP native execution/key creation/signature/private export;
- production recovery-key creation/signing/recovery;
- provider call #7;
- broker/live trading; and
- P4/P5/P6 production effects.

Required order is now:

```text
Architecture-101 disabled source implementation
-> exact GitHub diff/security review
-> focused + broad source certification
-> restart complete read-only readiness from Gate 1
-> ChatGPT acceptance of frozen readiness evidence
-> separate explicit effect authorization discussion
-> protected evidence-root/account ceremony
-> genuine ordinary candidate qualification + creator LSA reconciliation
-> later KSP SID/source freeze and denial experiment
-> recovery only after all independent gates are accepted
```

Architecture 100's one-shot ambiguous root-creation rule remains unchanged:
once an authorized root-creation call may have begun, unexpected process loss
consumes that authorization and permits only read-only reconciliation, never a
blind relaunch even if the root later appears absent.

## GUI status

GUI-A1 through GUI-A7 remain fully accepted and integrated. GUI capabilities are
read-only presentation/inspection boundaries and do not own production authority,
credentials, paper-account mutation, retry, recovery, brokerage, or execution.

## Workflow invariants

Canonical workflow rules remain in `AGENTS.md` and
`docs/AI_DEVELOPMENT_WORKFLOW.md`:

- prove exact worktree, branch, and HEAD before every bounded Codex task;
- startup mismatch is a STOP; never self-correct Git state;
- every controlled Windows pytest gate uses a fresh explicit external
  `F:\AI\temp\pytest\<unique-run>` basetemp and normally
  `-p no:cacheprovider`;
- preserve unrelated generated/untracked reports and historical pytest evidence;
- use focused tests during implementation and broad/full certification only after
  exact source-diff acceptance;
- use the validated clean-harness/provenance method for unchanged legacy tests
  whose hard-coded `.pytest_cache` scratch is inaccessible;
- under Windows PowerShell 5.1, prefer a here-string piped to Python stdin for
  quoting-sensitive provenance snippets rather than `python -c`;
- never merge, rebase, force-push, amend, change PR metadata/review threads, or
  modify unrelated files without explicit approval.

## Stable product constraints

- US stocks and ETFs;
- long-only;
- no margin or leverage;
- no options;
- no short selling;
- no crypto;
- deterministic risk approval for every order;
- paper mode by default;
- complete auditability.

## Documentation workflow

At every accepted development checkpoint, review/update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

Update `docs/AI_DEVELOPMENT_WORKFLOW.md` only for a new reusable workflow rule.
Git-tracked documents are authoritative; uploaded copies are context mirrors.
Documentation closeout does not authorize merge, rebase, force-push, amend,
review-thread resolution, PR metadata changes, or any production/security effect.
