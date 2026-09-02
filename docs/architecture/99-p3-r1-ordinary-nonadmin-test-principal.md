# Architecture 99: P3-R1 ordinary non-admin test principal

## Status and scope

**DOCS-ONLY SECURITY-ARCHITECTURE CHECKPOINT -- REVIEW REQUIRED**

This contract defines a dedicated Windows local standard-user principal used
only for the Architecture-98 `ORDINARY_NONADMIN_DENIAL` phase. It authorizes
neither account creation nor any native KSP phase. Account creation, source SID
freeze, native execution, and cleanup are separate reviewed checkpoints.

The disabled native harness at commit
`69a03d127c055cfc22b5f0327a1bef6363ab00b7`, tree
`76f0095c8ca16a24b2f2ed3bb89cb50624534c40`, is source-certified. Its source,
tests, and existing runbook remain unchanged in this checkpoint. Architectures
[97](97-p3-r1-recovery-signing-trust-reestablishment.md) and
[98](98-p3-r1-ksp-machine-key-security-contract.md) retain their authority,
key-security, and failure-retention contracts. The
[disposable harness runbook](../validation/p3-r1-ksp-disposable-test-harness.md)
retains its phase order, genuine-process-token requirement, fixed retained
evidence authority, and disabled execution gate.

The companion [validation plan](../validation/reliable-manual-paper-cycle-p3-r1-ordinary-nonadmin-test-principal.md)
defines future acceptance gates. No future gate is reported as passed merely
because its requirements are documented here.

## Existing-account rejection decision

The reviewed read-only discovery recorded in the existing harness runbook is
carried forward as historical evidence; this checkpoint does not repeat Windows
account or token inspection. The suffixes below identify existing accounts on
the reviewed machine, not a predicted SID for the new account.

| Existing identity | Reviewed facts and disposition |
| --- | --- |
| `...-1007`, `CodexSandboxOffline` | Enabled non-admin Codex sandbox infrastructure identity; direct `Users` and `CodexSandboxUsers` membership. Not adopted as ordinary-user test authority. |
| `...-1008`, `CodexSandboxOnline` | Enabled non-admin Codex sandbox infrastructure identity with the same special local-group context. Not adopted as ordinary-user test authority. |
| `...-1003`, `defaultuser0` | Windows setup/default identity. Not adopted. |
| `...-1009`, `Trading` | Already the separate dedicated Trading denial perspective. Cannot double as the additional ordinary-user perspective. |
| `...-1005`, P3-R1 Administrator | Privileged identity. Cannot qualify. |

Trading remains the primary non-admin production-runtime denial perspective.
The new account supplies a second independent generic-standard-user perspective;
it is not required because Trading is unsuitable or insufficiently restricted.

The discovery also recorded `Performance Log Users` membership arising through
the host's local `INTERACTIVE` group. That logon-context fact must be assessed
separately from direct account assignments; it is not silently accepted for the
new principal. No infrastructure identity is repurposed.

```text
EXISTING_ORDINARY_NONADMIN_CANDIDATE_ACCEPTED=False
DEDICATED_ORDINARY_NONADMIN_CANDIDATE_NAME=P3R1KspTestUser
```

## Dedicated identity and purpose

The exact candidate local account name is `P3R1KspTestUser`. Its sole purpose is
the test-only ordinary non-admin Windows perspective in the P3-R1 disposable
KSP authority-denial experiment, including the prerequisite qualification of
that perspective.

This account must never become production runtime authority, trading
authority, recovery authority, a KSP owner, a KSP ACE principal, signing
authority, or Credential Manager authority. It is not an alternate Trading
account, service identity, production operator, or recovery signer.

Windows must supply its machine-local SID after a separately authorized
create-new ceremony. This document deliberately predicts no RID or SID.
Account-name equality alone never establishes harness authority. The read-back
SID must be tied to the exact local account on the intended host, reviewed with
its membership and token evidence, and then frozen as the accepted identity.

The current source state remains:

```text
ORDINARY_NONADMIN_TEST_SID=None
ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED=True
ORDINARY_NONADMIN_SELECTION_REQUIRES_REVIEW=True
_NATIVE_EFFECT_EXECUTION_AUTHORIZED=False
_NATIVE_EFFECT_AUTHORIZATION_ID=NOT-AUTHORIZED-IN-800CA51-HARNESS
```

## Future create-new Administrator ceremony

A future account-creation procedure requires separate review and explicit
authorization. It must run under the exact frozen P3-R1 Administrator SID:

```text
S-1-5-21-1397534616-3988210162-180023805-1005
```

Before creation, prove the genuine current process token has that exact
`TokenUser` SID, `TokenElevation=true`, `TokenElevationTypeFull`, and enabled
`BUILTIN\Administrators` membership. A display name, group membership alone,
filtered Administrator token, asserted SID, or impersonated identity cannot
substitute for the exact elevated creator.

From that reviewed context, prove read-only that the exact machine-local account
name `P3R1KspTestUser` does not already exist. A failed, incomplete, ambiguous,
or wrong-host lookup is not absence. The creation operation itself must enforce
create-new semantics so a name collision after inspection still fails closed.

If the name exists, **STOP**. Do not adopt the account, reset its password,
modify it, delete it, recreate it, or select a variant name. There are no
account-overwrite, repair, or idempotent-adoption semantics.

The later procedure must record sanitized creation-attempt and outcome evidence.
After successful creation, read Windows account state back, require it enabled,
and obtain its actual SID. Enumerate and review memberships before accepting
the SID freeze. An uncertain creation outcome stops without an automatic retry;
any account that may have been created is retained pending review.

## Password and secret handling

The future creation command must obtain the password through a secure
interactive Windows mechanism, such as an in-process `SecureString` prompt,
and pass it to the reviewed account-creation boundary without exposing plaintext.
This document supplies neither a password nor an executable creation command.

No password, recoverable password representation, or secret-bearing diagnostic
may appear in:

- Git or any committed artifact;
- ChatGPT, Codex prompts, or Codex reports;
- account-creation evidence or disposable KSP evidence;
- shell history or command-line arguments;
- environment variables; or
- files under the repository.

Do not echo, serialize, transcript, log, or capture the secret entry or retained
secret object. Retain only the fact that secure interactive entry was used and
whether the operation succeeded. Do not ask the operator to upload or paste a
password. Any later logon must preserve the same secret-handling boundary.

## Group-membership contract

After creation, the principal must be a standard local user. Its intentional
direct local-group assignment must consist only of the ordinary baseline
required for a normal standard user, normally `BUILTIN\Users`.

It must not be intentionally added to privileged or special-purpose groups,
including at minimum:

- `BUILTIN\Administrators`;
- `Backup Operators`;
- `Power Users`;
- `Cryptographic Operators`;
- `Remote Management Users`; or
- any local group granting administrative or security-management authority
  relevant to this experiment.

`CodexSandboxUsers` is infrastructure context, not the new account's baseline.
Special-purpose membership cannot be justified merely because it appears in
another non-admin account.

The future ceremony must distinguish and retain sanitized evidence for:

1. **Explicit/direct local assignments:** local groups that directly list the
   new SID, including assignments made automatically during creation.
2. **Normal token SIDs:** for example `Everyone`, `Authenticated Users`, and
   `INTERACTIVE`. These are not equivalent to intentionally adding the account
   to a privileged local group.
3. **Indirect or dynamic memberships:** effective memberships supplied by nested
   local-group relationships or Windows logon context. Record their origin and
   security significance separately from direct assignments.

Do not fail merely because normal non-admin interactive token groups exist.
Equally, a normal token SID does not excuse an unexpected special-purpose group
reached through it. In particular, the previously observed `INTERACTIVE` to
`Performance Log Users` relationship must be examined for the actual future
logon context; this contract does not pre-approve it. Any unexpected privileged
or special-purpose membership, whether direct or indirect, is a **STOP** before
qualification or accepted SID freeze. Incomplete membership inspection also
blocks acceptance.

Do not silently remove a membership, change a host-wide group relationship, or
adjust the account to make a failed gate pass during the creation checkpoint.
Retain the account and sanitized evidence and review recovery/cleanup
separately. Any baseline assignment necessary for creation must be explicitly
included in the future ceremony authorization; this document authorizes no
group mutation.

## Genuine token qualification

Before `ORDINARY_NONADMIN_DENIAL` can ever run, a genuine process logged on as
the dedicated account must prove all of the following:

```text
TokenUser SID = the newly frozen exact machine-local SID
TokenElevation = false
TokenElevationType != TokenElevationTypeFull
BUILTIN\Administrators membership is not enabled
account enabled = true
```

For qualification preceding source freeze, compare the process token to the
exact Windows SID readback being reviewed. After accepted freeze, compare it
to the same exact source-pinned SID again immediately before the denial phase.
Require successfully decoded token facts and enabled account state; unknown or
unreadable values are not a pass. A filtered Administrator account does not
qualify merely by having a non-elevated token.

Qualification uses a separately reviewed read-only process-token procedure; it
must not enable the KSP harness to inspect an account. The harness's existing
requirement for the genuine current process token remains unchanged. It must
not rely on in-harness impersonation, mocked facts, caller-selected SID strings,
or an Administrator process claiming to represent this user. Sanitized token
facts may be evidence; credentials, token handles, and raw secret material may
not be retained.

## KSP authority exclusions

`P3R1KspTestUser` must have **NO ACE on `MACHINE_TEST_KEY`** and must never be
inserted into its protected DACL. The Architecture-98 owner remains
`BUILTIN\Administrators` (`S-1-5-32-544`), and its DACL remains exactly the two
explicit allow ACEs for:

```text
SYSTEM          S-1-5-18
Administrators  S-1-5-32-544
```

Architecture 98's flags, masks, protection, inheritance, and semantic comparison
requirements remain unchanged. Neither the dedicated account nor Trading gets
an allow or deny ACE. The ordinary-user phase proves denial from absence of
authority, without adding an explicit deny ACE or modifying an ACL to facilitate
the test.

Under a later explicit native-execution approval, the existing exact machine-key
open-denial proof remains the gate. An expected access-denied open means private
operations requiring a key handle are unreachable; no grant may be introduced
to exercise them. This account must not sign, create or own a key, request a
private export, or control key properties, owner, DACL, or deletion.

## Filesystem and execution access

The later launch procedure must freeze and prove sufficient ordinary read and
execute access to the exact reviewed Python executable and harness source, and
read access to the retained disposable evidence needed to determine phase
authority. It must bind the actual executable/source identities and retained
evidence to the reviewed procedure, rather than trusting a caller-supplied path
or an arbitrary source copy.

The dedicated account must not receive access to:

```text
F:\AITradingBot\Authority
F:\AITradingBot\Paper
F:\AITradingBot\.Paper.provisioning-v1
production private key material
Credential Manager trading secrets
```

Do not broaden production access or use the sealed production runtime as a
reason to grant new production rights. The existing harness also excludes
`F:\AITradingBot\runtime` from its disposable evidence roots. Qualification
does not require opening production content, key material, or credentials.

The source-certified retained-evidence runner also publishes and reloads phase
results. The later launch review must therefore resolve the minimum disposable
evidence publication access needed by the genuine user while preserving the
fixed-root, create-new, validated-retention contract. Read access alone is not a
claim that a complete phase can run. This checkpoint grants no filesystem
rights and does not design an elevated proxy or alter the runner.

The native evidence root remains `F:\AI\p3-r1-ksp-disposable-test-v1` as frozen
in the harness. Account-qualification evidence must not pre-create or populate
that root and invalidate its absence gate. Freeze a separate non-production
location in the later account ceremony. If execution prerequisites cannot be
satisfied without broadening production authority, **STOP** and redesign the
test launch boundary before native execution is considered.

## Intended multi-session sequence

The following is conceptual phase responsibility, not an execution procedure.
"Exact elevated Administrator" always means the frozen `...-1005` SID above
with a genuinely elevated Administrator process token.

| Order | Genuine actor | Phase |
| --- | --- | --- |
| 1 | Exact elevated P3-R1 Administrator | `READ_ONLY_PREFLIGHT` |
| 2 | Exact elevated P3-R1 Administrator | `MACHINE_CREATE_AND_VALIDATE` |
| 3 | Exact elevated P3-R1 Administrator | `SHADOW_CREATE_AND_SCOPE_PROOF` |
| 4 | Exact elevated P3-R1 Administrator | `ELEVATED_MACHINE_EFFECT_TEST` |
| 5 | Exact Trading SID `S-1-5-21-1397534616-3988210162-180023805-1009`, non-elevated | `TRADING_DENIAL` |
| 6 | Exact future frozen `P3R1KspTestUser` SID, non-elevated | `ORDINARY_NONADMIN_DENIAL` |
| 7 | Exact elevated P3-R1 Administrator | `FINAL_EVIDENCE_RECONCILIATION` |

Architecture 99 authorizes none of these phases, including
`READ_ONLY_PREFLIGHT`. Every future session must obey the retained-evidence
ordering and actor checks; account creation cannot skip either denial
perspective, accept a caller assertion as phase authority, or bypass a failed,
blocked, or uncertain predecessor.

## Retention and failure rule

Once the account has actually been created in a later ceremony, retain it and
sanitized evidence if any later gate fails. A partial or uncertain creation
requires retained evidence and separate state resolution, without retry.

Do not automatically reset its password, disable/enable it, rename it, alter
its groups, delete/recreate it, or reuse its name for another identity. Even a
successful disposable experiment does not authorize account deletion. Cleanup
or deletion requires a separate review and explicit authorization identifying
the exact account name, host, and frozen SID; it cannot silently extend to keys,
other accounts, or production objects. This mirrors the disposable-key
failure-retention discipline without combining the two cleanup authorities.

## Post-creation source freeze and review sequence

Account creation alone is insufficient to unblock the harness. The required
future sequence is:

1. Complete the separately authorized create-new ceremony, Windows SID
   readback, membership review, enabled-state check, and genuine token
   qualification. Freeze the exact accepted SID in sanitized evidence.
2. In a separately scoped source checkpoint, update only the harness,
   runbook, and tests as necessary to bind that exact evidence-backed SID.
   Replace the unresolved source values with:

   ```text
   ORDINARY_NONADMIN_TEST_SID=<exact SID read back from Windows and accepted>
   ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED=False
   ORDINARY_NONADMIN_SELECTION_REQUIRES_REVIEW=False
   ```

3. Keep `_NATIVE_EFFECT_EXECUTION_AUTHORIZED=False` and the existing
   not-authorized native authorization ID. Add no CLI/environment/caller
   override and preserve genuine current-process-token checks.
4. Run focused tests and focused checks for the identity correction, including
   rejection of wrong actors and continued native-execution disablement.
5. Commit and ordinary fast-forward push the exact reviewed scope under that
   future checkpoint's authorization.
6. Obtain ChatGPT authoritative GitHub review of that exact commit/diff.
7. Stop with execution still disabled. Only a later explicit
   disposable-native-execution approval and reviewed execution boundary can
   authorize KSP effects.

Each future source checkpoint must freeze its own exact worktree, branch, HEAD,
and applicable tree/status gates, stop on mismatch without self-correcting Git,
and stage only its authorized files. Controlled Windows pytest runs must use a
fresh external `--basetemp F:\AI\temp\pytest\<fresh-name>` and normally
`-p no:cacheprovider`; focused verification does not authorize native effects.

## Current prohibitions and next step

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

The next step is ChatGPT authoritative GitHub review of these two documents.
After acceptance, prepare and review the separate account ceremony and its
read-only qualification procedure before requesting explicit account-creation
authorization. Neither document acceptance nor account creation authorizes
harness enablement, native effects, production changes, or cleanup.
