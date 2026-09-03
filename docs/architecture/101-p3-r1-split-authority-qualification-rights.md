# Architecture 101: P3-R1 split-authority qualification-rights collection

## Status and scope

**DOCS-ONLY SECURITY-ARCHITECTURE CHECKPOINT -- NO EFFECT AUTHORIZATION**

This contract resolves the P3-R1 execution-readiness blocker discovered during
the restarted Architecture-100 readiness sequence. It changes only the
**qualification-observation authority split** for the future
`P3R1KspTestUser` ceremony.

Architectures 97 through 100 remain authoritative except where this document
explicitly supersedes the Architecture-99/100 assumption that the genuine
ordinary candidate process itself can enumerate Local Security Authority (LSA)
account rights and include them in its console observation.

This checkpoint does **not** authorize evidence-root creation, ACL mutation,
password prompting, account creation, group mutation, interactive candidate
logon, KSP execution, recovery signing, provider calls, production recovery, or
live trading.

The Architecture-100 helper at source-certified checkpoint
`8cfbbd3a30eb704e6acfc1866bf2ed752879e231`, tree
`fc682a5baf35f2f2e8b01c9f8f04ce318681ee85`, remains a valid disabled-source
certification result. It is no longer execution-ready because its ordinary
qualification path requires an LSA read that the intended ordinary caller cannot
perform on this host.

## Readiness blocker that triggered this architecture

The restarted read-only readiness sequence reached the LSA-rights gate after the
following earlier gates had passed as discovery evidence:

```text
Gate 1  source/tool identity                         PASS
Gate 2  F:\ volume/parent namespace authority       PASS
Gate 3  v1/v2 root + candidate-name absence         PASS
Gate 4A local-group topology                         PASS
Gate 4B password/account policy                      PASS
Gate 4C LSA account-rights baseline                  BLOCKED
```

Gate 4C used the same documented native surface selected by the helper:

```text
LsaOpenPolicy(..., POLICY_LOOKUP_NAMES=0x00000800, ...)
LsaEnumerateAccountRights(policy, sid, ...)
```

In the ordinary non-elevated Windows PowerShell 5.1 process,
`LsaEnumerateAccountRights` returned:

```text
0xC0000022 STATUS_ACCESS_DENIED
```

for the first baseline SID queried (`S-1-1-0`) and separately for
`S-1-5-32-559` (Performance Log Users). The later console strings that said
`...=PASS` were printed only because the interactive shell continued after the
exceptions; they are not accepted readiness results.

The public Win32 `LsaEnumerateAccountRights` documentation states that the
policy handle must have `POLICY_LOOKUP_NAMES`. The Microsoft LSAD protocol
specification additionally describes the operation as reading an LSA **account
object** and requires `ACCOUNT_VIEW`; the account-object access-right contract
states that `ACCOUNT_VIEW` is the authority needed to read assigned privileges
and system-access rights. The observed `STATUS_ACCESS_DENIED` is therefore
consistent with a least-privileged caller lacking the required account-view
access even though it can open a policy handle for name lookup.

Architecture 101 does not weaken that access check, add policy rights, change an
LSA security descriptor, or reinterpret access denied as an empty-rights result.

## Security objective

The qualification still needs two different kinds of evidence:

1. **Genuine ordinary-session evidence** that only the candidate process can
   authoritatively prove about itself: its exact token user, non-elevation,
   thread-token absence, enabled groups and attributes, token privileges,
   direct/indirect group views, and the host-dynamic INTERACTIVE / Performance
   Log Users provenance.
2. **LSA policy/account-right evidence** that the fixed elevated creator can read
   but the ordinary candidate cannot reliably read on this host.

Neither authority may substitute for the other. In particular:

- an elevated creator token is not proof of what the candidate's genuine
  interactive token contains;
- candidate console text is not authority for LSA account rights;
- caller-provided SIDs never become accepted rights merely because they were
  supplied as query targets;
- access denied, malformed output, or unknown rights remain a STOP.

The corrected design therefore uses a **split-authority observation** and joins
the two views only in the creator process after deterministic reconciliation.

## Candidate-session authority

The genuine `P3R1KspTestUser` desktop invocation remains a fixed-source,
non-elevated, local Windows PowerShell 5.1 process. It must still prove its own
process token directly with the existing native token recipe and must remain:

```text
user SID: exact Windows-read-back candidate SID
TokenType: Primary
elevated: false
thread token: absent
Administrators: absent
INTERACTIVE: enabled
unknown/special token groups: rejected unless already reviewed
held token privileges: every one classified ACCEPTED
```

The candidate process continues to read its account identity, direct and
indirect local groups, local-group membership edges, token groups, token
attributes, and token privileges. It continues to prove the narrow
INTERACTIVE -> Performance Log Users provenance rule.

**It no longer calls `LsaEnumerateAccountRights`.**

A `STATUS_ACCESS_DENIED` from the old ordinary rights path is not converted to a
special success branch; that path is removed from the candidate observation.

## Canonical candidate observation

The candidate prints exactly one canonical sanitized JSON object and no secret,
handle, raw native buffer, or retained-evidence content. Its schema is frozen as:

```text
p3-r1-candidate-qualification-observation/v1
```

The closed top-level fields are:

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

with:

```text
collection_method = operator_observed_candidate_console
```

The existing strict nested shapes for `account`, directory group views,
`relevant_edges`, `effective_groups`, `candidate_token`, and
`performance_log_users` remain authoritative except that there is no `rights`
field in this candidate object.

Before printing, the candidate process must run all qualification checks that it
has authority to decide without LSA account-right access, including:

- exact candidate/account SID continuity;
- direct set exactly `{S-1-5-32-545}`;
- direct/indirect consistency;
- no unreviewed local-group or nested authority;
- genuine token non-elevation and thread-token absence;
- enabled INTERACTIVE;
- no Administrators token membership;
- every held token privilege classified `ACCEPTED` by the frozen privilege
  classifier;
- Performance Log Users direct assignment absent;
- the reviewed INTERACTIVE host edge present when effective Performance Log
  Users is present;
- no alternate path to Performance Log Users.

A failure in any candidate-owned gate stops before a candidate observation is
considered transferable.

## Operator transfer remains a comparison boundary, not LSA authority

Architecture 100 already requires the ordinary account to have no retained-root
ACE. Architecture 101 preserves that decision. The candidate therefore does not
write to the protected ceremony evidence root.

The existing local-console transfer model remains, with one clarification:

1. the operator copies the complete canonical candidate-observation line from the
   genuine candidate desktop console into the fixed creator-side qualification
   prompt;
2. the creator parses it under the closed candidate schema;
3. the creator independently re-reads and byte-compares the candidate account,
   direct group view, indirect group view, and local-group edge inventory;
4. the creator reprints the canonical candidate observation;
5. the operator types exactly:

```text
EXACT_CANDIDATE_CONSOLE_MATCH
```

only after visually comparing that reprinted candidate object with the genuine
candidate console.

This confirmation binds the transferred token-only facts to the observed
candidate console. It does **not** attest to LSA rights and is never used instead
of a native LSA query.

The creator computes and retains the SHA-256 of the exact canonical candidate
observation. No caller-supplied hash is accepted.

## Creator-side LSA-rights authority

Only after the candidate observation has passed schema validation, creator-side
account/group/edge reconciliation, and exact-console confirmation may the
creator collect LSA rights for qualification.

Immediately before LSA collection, the creator process must repeat the genuine
creator-token gate and require:

```text
creator SID:
  S-1-5-21-1397534616-3988210162-180023805-1005
primary token: true
fully elevated: true
Administrators enabled: true
Administrators deny-only: false
thread token: absent
```

The rights target set is source-derived from the accepted candidate observation:

```text
candidate account SID
UNION
all SIDs present in candidate_token.groups
```

The implementation must validate every SID, deduplicate with ordinal SID-string
identity, sort canonically, and reject an unbounded target count. A transferred
SID is only a **query target**; its right assignments become evidence only from
the subsequent native LSA result.

For each target SID, the creator performs:

```text
LsaOpenPolicy(local, POLICY_LOOKUP_NAMES=0x00000800)
LsaEnumerateAccountRights(policy, target_sid, ...)
```

using the same bounded native-buffer validation and release discipline already
reviewed in the helper.

Accepted per-target outcomes are only:

| Native result | Meaning |
| --- | --- |
| `STATUS_SUCCESS` | Decode every returned right; retain the exact right names and classify each. |
| `STATUS_OBJECT_NAME_NOT_FOUND` | This SID has no LSA account object / assigned account rights in this query; retain the no-account result. |
| anything else, including `STATUS_ACCESS_DENIED` | STOP. Never treat as no rights and never change policy to make the query pass. |

Every returned right keeps the existing disposition contract. The accepted
ordinary set remains narrowly frozen; dangerous or unknown security-management
rights remain `REJECTED` or `UNRESOLVED`, and either disposition blocks
qualification.

The rights collector is read-only. It does not call `LsaAddAccountRights`,
`LsaRemoveAccountRights`, modify local security policy, grant logon rights, or
alter group membership.

## Canonical creator rights-collection object

The creator retains a closed object named `rights_collection` with exactly:

```text
collector_token
collection_method
policy_access
target_sids
queries
```

where:

```text
collection_method = creator_lsa_enumerate_account_rights
policy_access = 2048
```

`target_sids` is the canonical sorted unique target list described above.

Each `queries` element has exactly:

```text
principal_sid
native_status
result
rights_count
```

with `result` one of:

```text
RIGHTS_RETURNED
NO_LSA_ACCOUNT_OBJECT
```

A `RIGHTS_RETURNED` count must equal the number of retained `rights` entries for
that principal. A `NO_LSA_ACCOUNT_OBJECT` query must use the exact documented
`STATUS_OBJECT_NAME_NOT_FOUND` value and contribute zero rights.

The full `rights` array keeps the existing closed fields:

```text
principal_sid
name
origin
disposition
```

`origin` remains `DIRECT` only for the candidate SID and `NESTED` for a right
attached to an effective token/group SID.

## Final split qualification observation

The creator constructs the only object eligible for retained
`QUALIFICATION_OBSERVED` evidence. Its schema is:

```text
p3-r1-split-qualification-observation/v1
```

and its closed fields are:

```text
schema
candidate_observation
candidate_observation_sha256
rights
rights_collection
```

The final acceptance routine must:

1. validate the nested candidate object under the candidate schema;
2. recompute and match `candidate_observation_sha256`;
3. require the rights target set to equal candidate SID union exact candidate
   token-group SIDs;
4. require the creator rights collector token to pass the full creator gate;
5. reconcile every query result with the rights array and reject missing,
   duplicate, extra, or unordered targets/rights;
6. require every retained right disposition to equal the existing frozen right
   classifier and to be `ACCEPTED`;
7. preserve all existing direct/indirect/group-graph/token/privilege/
   Performance-Log-Users acceptance rules.

No caller can submit a prebuilt final observation or a rights array. The creator
constructs both after parsing the candidate object and performing the native LSA
queries.

## Evidence schema and lifecycle correction

Because Architecture 101 changes the strict qualification record shape before
any ceremony evidence has ever been created, the account-ceremony evidence
schema advances to:

```text
p3-r1-ordinary-nonadmin-principal-evidence/v3
```

The protected root path remains exactly:

```text
F:\p3-r1-ordinary-nonadmin-principal-v2
```

The `-v2` pathname identifies the Architecture-100 protected namespace object;
it is not changed merely because the strict record schema advances. The retired
v1 root remains retired and absent. No v2 evidence exists to migrate or adopt.

Architecture 101 changes only qualification evidence after the account/Users
branch. The earlier one-way lifecycle remains:

```text
PREFLIGHT
ACCOUNT_CREATION_ATTEMPTED
ACCOUNT_CREATED
ACCOUNT_SID_READ_BACK
USERS_BASELINE_SELECTED
[optional USERS_ASSIGNMENT_ATTEMPTED]
[optional USERS_ASSIGNMENT_CONFIRMED]
```

After a separately authorized genuine candidate desktop logon, the corrected
qualification continuation is:

```text
candidate prints candidate-observation/v1
-> operator transfers exact candidate object
-> creator independently reconciles account/groups/edges
-> operator confirms EXACT_CANDIDATE_CONSOLE_MATCH
-> creator repeats creator-token gate
-> creator collects exact LSA rights for candidate + token SIDs
-> creator constructs split-qualification-observation/v1
-> QUALIFICATION_OBSERVED
-> GROUPS_QUALIFIED
-> TOKEN_QUALIFIED
```

`GROUPS_QUALIFIED` and `TOKEN_QUALIFIED` retain their existing meaning: they may
be emitted only after the full split observation passes, never from the candidate
half alone and never from the creator rights half alone.

## Failure, ambiguity, and no-repair policy

The existing fail-closed behavior remains. In particular:

- ordinary LSA `STATUS_ACCESS_DENIED` is no longer expected because ordinary LSA
  enumeration is removed;
- creator-side `STATUS_ACCESS_DENIED` is a STOP, not an invitation to elevate
  further, change policy, or retry under another identity;
- malformed candidate console data, transfer mismatch, unknown token groups,
  rejected/unresolved privileges, account/group/edge drift, malformed LSA
  buffers, unknown rights, or an incomplete query target set are all STOPs;
- no group/policy/ACL mutation may manufacture a passing qualification;
- no `secedit` export, `whoami` text scraping, external policy tool, or broad
  policy dump substitutes for the reviewed native LSA calls;
- no candidate rights are inferred from group names or from the absence of a
  returned token privilege.

Architecture 100's root-creation ambiguity rule remains unchanged. Once an
authorized root-creation call may have begun, ambiguous process loss consumes
that root-creation authorization even if the fixed root later appears absent.

## Superseded clauses

Architecture 101 supersedes only these prior assumptions:

```text
candidate Observation() includes LSA rights
candidate process calls LsaEnumerateAccountRights
creator compares transferred rights to a second copy of candidate-collected rights
QUALIFICATION_OBSERVED directly stores the old flat observation shape
account-ceremony evidence schema v2
```

It does **not** supersede:

- the dedicated candidate identity or unknown-until-readback SID rule;
- the protected Architecture-100 root path/security/identity contract;
- dual candidate-name absence;
- one-shot NetUserAdd semantics;
- secure password handling;
- deterministic Users branch;
- genuine ordinary token and privilege qualification;
- Performance Log Users provenance rules;
- no cleanup/repair/retry semantics;
- separate effect authorization.

## Required source-only follow-up

The next implementation checkpoint is bounded to:

```text
scripts/p3_r1_ordinary_nonadmin_principal_ceremony.cs
scripts/run_p3_r1_ordinary_nonadmin_principal_ceremony.ps1
tests/runtime/test_p3_r1_ordinary_nonadmin_principal_ceremony.py
```

Effects remain disabled throughout source implementation and testing.

The source correction must:

1. advance the strict evidence schema to v3 while keeping the Architecture-100
   root path unchanged;
2. split the old flat qualification observation into the exact candidate and
   final split schemas above;
3. ensure the candidate branch never opens LSA policy or calls
   `LsaEnumerateAccountRights`;
4. preserve candidate-owned token/group/privilege/provenance validation before
   console output;
5. change the creator transfer prompt/confirmation to
   `EXACT_CANDIDATE_CONSOLE_MATCH` and compare only candidate-owned facts to the
   genuine candidate console;
6. perform creator-side rights collection only after candidate transfer and
   creator-token revalidation;
7. derive the exact LSA target set from candidate SID plus token-group SIDs and
   build the closed `rights_collection` object;
8. construct and validate the full split qualification observation before any
   `QUALIFICATION_OBSERVED`, `GROUPS_QUALIFIED`, or `TOKEN_QUALIFIED` record;
9. preserve Architecture-100 root security, one-shot account/group behavior,
   secure-string handling, and all unrelated source unchanged;
10. keep `ACCOUNT_EFFECT_EXECUTION_AUTHORIZED=false` and the authorization ID in
    its not-authorized state.

Focused tests must include at least:

- ordinary candidate observation succeeds with an LSA adapter that would throw
  if called, proving no ordinary rights query occurs;
- creator rights success and `STATUS_OBJECT_NAME_NOT_FOUND` handling;
- creator `STATUS_ACCESS_DENIED` rejection;
- candidate/rights target-set mismatch, duplicate/extra/missing target rejection;
- candidate console hash/reconciliation mismatch rejection;
- dangerous and unresolved rights rejection;
- rights collector not-creator/not-elevated/thread-impersonated rejection;
- full successful split-observation lifecycle using fakes only;
- all existing protected-root, account, Users, token, privilege, and failure
  tests remain passing with effects disabled.

No KSP harness, production recovery, provider, GUI, brokerage, or unrelated
source may change in this checkpoint.

## Readiness restart after corrected source certification

The current Gate 1 through Gate 4B results remain useful **discovery evidence**,
but Architecture 101 changes the reviewed source and qualification protocol.
After the corrected source is accepted and source-certified, execution readiness
must restart from gate #1 against that exact new commit/tree.

The new readiness sequence must include a read-only elevated creator LSA probe
that proves the fixed creator can successfully query the relevant baseline rights
using the exact source-owned native path. It must not attempt to prove ordinary
LSA access, because ordinary rights enumeration is no longer part of the design.

Only after the full restarted readiness freeze passes may a separate explicit
authorization discussion consider the protected-root/account effects.

## Non-authorizations

```text
ACL_MUTATION=NOT_AUTHORIZED
PROTECTED_EVIDENCE_ROOT_CREATION=NOT_AUTHORIZED
CEREMONY_EVIDENCE_PUBLICATION=NOT_AUTHORIZED
ACCOUNT_CREATION=NOT_AUTHORIZED
WINDOWS_GROUP_MUTATION=NOT_AUTHORIZED
PASSWORD_PROMPT=NOT_AUTHORIZED
CANDIDATE_INTERACTIVE_LOGON=NOT_AUTHORIZED
LSA_POLICY_MUTATION=NOT_AUTHORIZED
LSA_RIGHTS_MUTATION=NOT_AUTHORIZED
DISPOSABLE_NATIVE_EXECUTION=NOT_AUTHORIZED
DISPOSABLE_TEST_KEY_CREATION=NOT_AUTHORIZED
CURRENT_USER_SHADOW_CREATION=NOT_AUTHORIZED
TEST_SIGNATURE=NOT_AUTHORIZED
PRIVATE_EXPORT_REQUEST=NOT_AUTHORIZED
PRODUCTION_RECOVERY_KEY_CREATION=NOT_AUTHORIZED
PRODUCTION_SIGNING=NOT_AUTHORIZED
PROVIDER_CALL_7=NOT_AUTHORIZED
P3_TRADING_ACCEPTANCE=BLOCKED
P4_PRODUCTION_EXECUTION=BLOCKED
PRODUCTION_LIVE=NO-GO
```

## Acceptance criteria

Architecture 101 is acceptable only if review confirms that:

- the Gate-4C access-denied result is treated as a real least-privilege boundary,
  not bypassed or misclassified;
- genuine candidate token evidence remains collected only in the genuine
  candidate process;
- LSA account-right evidence is collected only by the revalidated fixed creator;
- neither half can independently qualify the account;
- candidate console transfer remains exact, canonical, operator-compared, and
  independently reconciled where the creator has an authoritative read path;
- rights query targets equal the exact candidate SID plus genuine candidate token
  SIDs;
- every LSA result is fail-closed and every returned right is classified;
- no policy/group/ACL mutation is introduced to make the read succeed;
- the protected Architecture-100 root contract remains unchanged;
- the strict evidence schema advances before any evidence exists, with no
  migration/adoption path;
- all effects remain disabled until a later separately reviewed authorization.
