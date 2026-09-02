# P3-R1 ordinary non-admin test-principal validation plan

## Status and authority boundary

**DOCS-ONLY SECURITY-ARCHITECTURE CHECKPOINT -- NO ACCOUNT OR NATIVE EXECUTION**

This is the validation plan for
[Architecture 99](../architecture/99-p3-r1-ordinary-nonadmin-test-principal.md).
It defines acceptance criteria for later separately authorized checkpoints and
contains no executable account-creation, group-mutation, or KSP procedure.
Future gates below are **NOT RUN** by this docs checkpoint. Document review,
account creation, source SID freeze, native execution, and cleanup each retain
their separate approval boundary.

The [existing disposable harness runbook](p3-r1-ksp-disposable-test-harness.md)
and source at `69a03d127c055cfc22b5f0327a1bef6363ab00b7` are source-certified
and remain unchanged. Architecture 99 adds an identity contract; it does not
re-certify native host behavior or enable the harness.

## Frozen docs-checkpoint gate

The docs checkpoint starts only from this exact state:

```text
worktree: F:\AI\worktrees\ai-trading-bot-p3-r1
branch: feature/p3-r1-recovery-implementation
HEAD: 69a03d127c055cfc22b5f0327a1bef6363ab00b7
tree: 76f0095c8ca16a24b2f2ed3bb89cb50624534c40
git status --short: empty
```

Require all five observations from:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git show -s --format=%T HEAD
git status --short
```

Git may display the same Windows path with forward slashes. Any different
worktree, branch, HEAD, tree, or nonempty status is a **STOP** before source
inspection or modification. Never checkout, switch, reset, rebase, clean,
prune, amend, or touch another active worktree to repair a mismatch.

Only these files may be created:

```text
docs/architecture/99-p3-r1-ordinary-nonadmin-test-principal.md
docs/validation/reliable-manual-paper-cycle-p3-r1-ordinary-nonadmin-test-principal.md
```

No source/test, Architecture-97/98, or existing runbook edit is permitted. Stop
before broadening the scope if another file becomes necessary.

## Reviewed discovery and candidate gate

Carry forward the reviewed historical read-only discovery, without claiming
fresh Windows inspection:

- `...-1007` / `CodexSandboxOffline` and `...-1008` /
  `CodexSandboxOnline` are enabled non-admin infrastructure identities with
  special Codex local-group context. Neither is adopted.
- `...-1003` / `defaultuser0` is a Windows setup/default identity and is not
  adopted.
- Trading `...-1009` remains the separate primary non-admin production-runtime
  denial perspective. The additional account supplies an independent generic
  standard-user perspective, not a remedy for insufficient Trading restriction.
- P3-R1 Administrator `...-1005` is privileged and cannot qualify.

Require the architecture to freeze:

```text
EXISTING_ORDINARY_NONADMIN_CANDIDATE_ACCEPTED=False
DEDICATED_ORDINARY_NONADMIN_CANDIDATE_NAME=P3R1KspTestUser
```

No future candidate SID or RID is predicted. All SID evidence must originate
from Windows after the separately approved create-new operation.

## Future account-creation and qualification gates

Every gate requires sanitized evidence and an explicit PASS before its dependent
step can proceed. Missing, uncertain, or contradictory evidence is a STOP.
These requirements do not authorize executing the checks or ceremony now.

| Gate | Required proof | Failure boundary |
| --- | --- | --- |
| A1: Separate ceremony authorization | Accepted Architecture 99 plus a reviewed procedure and explicit account-creation authorization naming the host, candidate, creator, baseline assignment, and evidence destination. | No account or group mutation without that authorization. |
| A2: Exact elevated creator | Genuine current process `TokenUser=S-1-5-21-1397534616-3988210162-180023805-1005`, elevation true, elevation type Full, and Administrators membership enabled. | Wrong SID, filtered token, asserted/impersonated identity, or unreadable token facts stop before creation. |
| A3: Exact-name absence | Successful read-only local-account inspection on the intended host proves `P3R1KspTestUser` absent. | Existing name or ambiguous lookup: stop; no adoption, password reset, modification, deletion, recreation, or alternate name. |
| A4: Create-new only | Reviewed operation refuses an existing exact name, including a collision after the absence check; no overwrite or repair behavior. Retain attempt/outcome facts. | Failure or uncertainty stops without automatic retry or account replacement. |
| A5: Secure password handling | Secure interactive Windows entry, such as an in-process `SecureString` prompt; no plaintext conversion/output or secret capture. Retain only mechanism and outcome facts. | No password in Git, ChatGPT, Codex prompts/reports, evidence, shell history, arguments, environment, repository files, or disposable KSP evidence; no request to upload/paste it. |
| A6: Enabled account | Read back the exact newly created local account and require enabled state. | Disabled or uncertain state blocks qualification; do not automatically enable/disable it to repair the result. |
| A7: SID readback | Obtain the actual machine-local SID from Windows and bind it to the exact account and host. | Predicted RID, copied account SID, ambiguous mapping, or name-only authority is rejected. Readback is evidence pending qualification, not automatic accepted freeze. |
| A8: Direct local groups | Enumerate every resulting direct local-group membership, including creation defaults; only the normal standard-user baseline, normally `BUILTIN\Users`, is intentionally assigned. | Unexpected assignment or incomplete enumeration blocks accepted SID freeze; no silent membership removal. |
| A9: Privileged/special-purpose exclusion | Review direct and indirect memberships and relevant logon-context authority. Exclude Administrators, Backup Operators, Power Users, Cryptographic Operators, Remote Management Users, and any other relevant administrative/security-management group. | Any unexpected privileged or special-purpose membership stops; retain account/evidence for separate review. |
| A10: Genuine ordinary token | A real process logged on as the new account has the exact read-back SID, elevation false, elevation type not Full, Administrators membership not enabled, and enabled account state. | No harness impersonation, mock token, caller SID assertion, filtered Administrator substitution, or KSP enablement for qualification. |
| A11: Accepted SID freeze | Review account name/host/SID, all memberships, enabled state, and token qualification together; freeze the exact accepted SID in sanitized evidence. | Creation or readback alone cannot satisfy this gate. Any unresolved qualification blocks source adoption. |

Group evidence must label direct assignments, normal token SIDs, and indirect
or dynamic memberships separately. `Everyone`, `Authenticated Users`, and
`INTERACTIVE` in a normal non-admin token are not by themselves failures. Their
presence also does not excuse extra local-group authority. Explicitly review
the previously observed `INTERACTIVE` to `Performance Log Users` relationship
if present in the future token; do not silently pre-approve it, remove it, or
alter host-wide membership to force a pass.

The exact account-creation command, token-inspection procedure, and sanitized
evidence location must be reviewed in the later ceremony. Evidence belongs
outside production and outside the repository. It must not populate
`F:\AI\p3-r1-ksp-disposable-test-v1`, whose native preflight absence contract
remains unchanged. No evidence directory is created by this checkpoint.

## Future source and launch gates

| Gate | Required proof | Failure boundary |
| --- | --- | --- |
| S1: Bounded source SID freeze | A separately authorized checkpoint updates only necessary harness/runbook/tests to the exact accepted SID; sets `ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED=False` and `ORDINARY_NONADMIN_SELECTION_REQUIRES_REVIEW=False`. | No caller, CLI, environment, account-name lookup, or guessed SID supplies execution authority. |
| S2: Execution still disabled | `_NATIVE_EFFECT_EXECUTION_AUTHORIZED=False` and `_NATIVE_EFFECT_AUTHORIZATION_ID=NOT-AUTHORIZED-IN-800CA51-HARNESS` remain; genuine process-token and retained-state gates are preserved. | SID qualification or source correction never enables native execution. |
| S3: Focused verification and GitHub review | Focused identity/negative-actor/disabled-gate tests and checks pass; exact files are committed/pushed under the future task authorization; ChatGPT reviews the authoritative exact GitHub commit/diff. | Unreviewed source cannot progress to a native execution approval request. No broad suite is required for this docs checkpoint. |
| L1: Reviewed execution access | Exact reviewed Python and harness source are readable/executable as needed; retained disposable evidence is readable for phase authority. Separately resolve required result-publication access under the fixed-root runner. | No production grants, arbitrary source substitution, elevated proxy, or weakened evidence checks to make the launch work. |
| L2: Production paths untouched | No access is granted to `F:\AITradingBot\Authority`, `F:\AITradingBot\Paper`, `F:\AITradingBot\.Paper.provisioning-v1`, production private keys, or Credential Manager trading secrets. No production runtime access is broadened. | If prerequisites require broader production authority, stop and redesign the test launch boundary. Do not open production contents or secrets as a qualification test. |
| L3: KSP authority unchanged | Source review preserves Architecture-98 Administrators ownership and the exact protected SYSTEM/Administrators-only machine-key DACL. The dedicated user has no ACE and no signing/control authority. | No allow/deny ACE, ACL change, private-use grant, or key-owner change to facilitate denial testing. Native readback requires later execution approval. |
| L4: Explicit native approval | A later separately reviewed execution procedure receives explicit disposable-native-execution authorization after source acceptance and launch qualification. | Until then all seven phases remain unauthorized, including native `READ_ONLY_PREFLIGHT`. |

The future SID-freeze sequence is exact:

```text
reviewed and separately authorized account creation
-> Windows SID readback and account/group/token qualification
-> freeze exact accepted SID in sanitized evidence
-> source correction replacing ORDINARY_NONADMIN_TEST_SID=None
-> focused tests/checks
-> authorized exact-file commit and ordinary fast-forward push
-> ChatGPT authoritative GitHub review
-> STOP with execution disabled
-> only a later explicit disposable-native-execution approval permits KSP effects
```

After source freeze, genuine token qualification is repeated against the exact
source-pinned SID immediately before `ORDINARY_NONADMIN_DENIAL`. Earlier token
evidence does not excuse a different actor or changed account/group state.

The eventual phase order remains elevated exact Administrator preflight,
machine create/validate, shadow create/scope proof, elevated machine effect;
then genuine non-elevated exact Trading denial; genuine non-elevated exact
future dedicated-user denial; and exact elevated Administrator final evidence
reconciliation. Retained predecessor success is required throughout. No phase
is run, skipped, retried, or approved by this plan.

## Failure retention and cleanup gates

| Gate | Required behavior |
| --- | --- |
| R1: Retain after creation | Any later failure retains the account and sanitized evidence. Uncertain creation retains available state for separate resolution; no automatic retry. |
| R2: No automatic mutation | Do not reset the password, disable/enable, rename, alter groups, delete/recreate, or reuse the name for another identity. Do not repair a membership failure in the creation checkpoint. |
| R3: Separate cleanup authority | Any cleanup/deletion requires separate review and explicit authorization naming the exact host/account/SID. Passing the test is not deletion approval. Account cleanup does not authorize key cleanup or production changes. |

These gates mirror disposable-key failure retention. Retained evidence must
state the last proven boundary and any uncertainty, without claiming a later
PASS or manufacturing authority from incomplete state.

## Docs-only verification and publication

Review both documents against the Architecture-99 contract and confirm that
only the two new Markdown files are present in the change. Verify the harness,
tests, existing runbook, and Architectures 97/98 remain unchanged. No account
inspection, account mutation, native harness invocation, or pytest is needed
for this checkpoint.

Run:

```powershell
git diff --check
```

Because new documents are initially untracked, also require the staged check
below before committing. Exact-file stage only:

```powershell
git add -- docs/architecture/99-p3-r1-ordinary-nonadmin-test-principal.md docs/validation/reliable-manual-paper-cycle-p3-r1-ordinary-nonadmin-test-principal.md
git diff --cached --check
git diff --cached --name-only
```

Require successful checks and exactly the two authorized paths. Never use
`git add .` or `git add -A`. Reconfirm the starting checkpoint and that the
remote branch has not changed before publication. If any required gate fails,
stop without committing or broadening the change.

This task explicitly authorizes the following commit and ordinary fast-forward
push once all gates pass:

```powershell
git commit -m "docs: define P3-R1 ordinary non-admin test principal"
git push origin feature/p3-r1-recovery-implementation
git rev-parse HEAD
git show -s --format=%T HEAD
git status --short
```

Check each command's exit status before proceeding. If the push is rejected or
remote state changes, **STOP**; do not pull, merge, rebase, force-push, reset,
amend, or switch. Report the exact commit/tree, push result, and final status.

No full-suite verification is required. If a later source checkpoint requires
pytest, every controlled Windows invocation must use a fresh explicit external
`--basetemp F:\AI\temp\pytest\<fresh-name>` and normally
`-p no:cacheprovider`. Preserve historical test caches and scratch; focused
tests do not authorize native effects.

## No-effect acceptance and handoff

The docs-checkpoint report must distinguish requirements from operations
actually performed. It must confirm zero Windows-account creation/mutation,
group mutation, KSP/provider/key effects, production effects, recovery effects,
or P4 execution. All prohibitions remain:

```text
WINDOWS_ACCOUNT_CREATION=NOT_AUTHORIZED
WINDOWS_ACCOUNT_MUTATION=NOT_AUTHORIZED
WINDOWS_GROUP_MUTATION=NOT_AUTHORIZED
DISPOSABLE_NATIVE_EXECUTION=NOT_AUTHORIZED
DISPOSABLE_TEST_KEY_CREATION=NOT_AUTHORIZED
CURRENT_USER_SHADOW_CREATION=NOT_AUTHORIZED
TEST_SIGNATURE=NOT_AUTHORIZED
PRIVATE_EXPORT_REQUEST=NOT_AUTHORIZED
KSP_PROPERTY_MUTATION=NOT_AUTHORIZED
KSP_ACL_MUTATION=NOT_AUTHORIZED
KEY_CLEANUP=NOT_AUTHORIZED
PRODUCTION_RECOVERY_KEY_CREATION=NOT_AUTHORIZED
PRODUCTION_SIGNING=NOT_AUTHORIZED
PRODUCTION_RECOVERY_RENAME=NOT_AUTHORIZED
PROVIDER_CALL_7=NOT_AUTHORIZED
P4_PRODUCTION_EXECUTION=BLOCKED
PRODUCTION_LIVE=NO-GO
```

Next: ChatGPT authoritative GitHub review of the exact docs commit. After
acceptance, separately prepare/review the account ceremony before requesting
explicit account-creation authorization. Stop at this docs checkpoint; do not
create the account or advance to source correction, native execution, or cleanup.
