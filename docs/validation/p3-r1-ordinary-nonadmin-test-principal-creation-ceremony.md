# P3-R1 ordinary non-admin test-principal creation ceremony

## Status: completed procedure contract, execution still unauthorized

**DOCUMENTATION ONLY. DO NOT EXECUTE THE CEREMONY.**

This document freezes the future ceremony contract for
[Architecture 99](../architecture/99-p3-r1-ordinary-nonadmin-test-principal.md).
It preserves [Architecture 97](../architecture/97-p3-r1-recovery-signing-trust-reestablishment.md),
[Architecture 98](../architecture/98-p3-r1-ksp-machine-key-security-contract.md),
the [account validation plan](reliable-manual-paper-cycle-p3-r1-ordinary-nonadmin-test-principal.md),
and the [disabled KSP harness runbook](p3-r1-ksp-disposable-test-harness.md).
Those accepted documents and all source remain unchanged.

The ChatGPT architecture review supplied for this correction resolves the
draft's three procedure-design blockers as follows:

| Reviewed issue | Frozen resolution |
| --- | --- |
| `New-LocalUser` rollback | Rejection retained. Use a future direct `Netapi32!NetUserAdd` level-1 boundary, with no caller rollback or cleanup and conservative outcome classification. |
| Unspecified automatic Users membership | Make no automatic-assignment claim. Select the explicit deterministic post-create branch: direct set exactly Users means no effect; empty means one durably recorded conditional Users add; every other set stops. |
| INTERACTIVE -> Performance Log Users | Conditionally accepted host-dynamic ordinary-interactive baseline **only for this KSP denial experiment**, subject to the exact provenance, membership, and privilege gates below. No other special group is accepted by analogy. |

These are explicit review decisions, not newly observed Windows execution
results. The conditional host-dynamic acceptance records the task's specific
Architecture-99 review disposition; it does not retrospectively claim that the
accepted architecture/validation documents had already approved it.

No creation-semantics decision remains unresolved in this document. Nevertheless,
**the ceremony is not execution-ready**: a separate bounded source-only checkpoint
must implement and review the in-process helper with all account/group effects
disabled. GitHub source acceptance must precede any request for explicit account
creation, conditional Users assignment, evidence-root creation, or interactive
logon authorization. This document contains no executable account-creation code.

## Frozen checkpoint and identities

The correction task started from this exact checkpoint with only the authorized
untracked draft:

```text
worktree: F:\AI\worktrees\ai-trading-bot-p3-r1
branch: feature/p3-r1-recovery-implementation
HEAD: 89506d9104b4699d19eee96aac2ad0b18ee25e4a
tree: 0fdb9468b40b1c11f48484df136fa2afe27bea66
git status --short:
?? docs/validation/p3-r1-ordinary-nonadmin-test-principal-creation-ceremony.md
tracked modifications: none
```

All five observations were obtained before source/document inspection:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git show -s --format=%T HEAD
git status --short
```

Forward slashes in Git's rendering denote the same Windows path. Any other
worktree, branch, HEAD, tree, or status is a STOP. Never checkout, switch,
reset, rebase, clean, prune, amend, or disturb another active worktree.
The future authorization must pin the then-reviewed ceremony commit/tree and
repeat these gates; the starting documentation HEAD is not future authority.

```text
host: DESKTOP-I4DOKM7
creator TokenUser: S-1-5-21-1397534616-3988210162-180023805-1005
candidate local name: P3R1KspTestUser
candidate SID: UNKNOWN; WINDOWS READBACK REQUIRED
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
account-ceremony root: F:\AI\p3-r1-ordinary-nonadmin-principal-v1
separate, untouched KSP root: F:\AI\p3-r1-ksp-disposable-test-v1
```

The creator name is not authority. Trading is neither modified nor reused.
The known machine-domain SID is a readback consistency constraint; append no
predicted RID to it. The candidate must be a new, ordinary local user, with no
service configuration or production authority.

## Microsoft contracts and installed-host review

Review date: 2026-09-02. The initial draft's read-only host inspection recorded
the installed 64-bit Windows PowerShell executable and module below. This
correction carries that evidence forward without repeating account inspection:

```text
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
PowerShell: 5.1.19041.7663; Is64BitProcess=True
Microsoft.PowerShell.LocalAccounts: 1.0.0.0
module DLL:
C:\Windows\System32\WindowsPowerShell\v1.0\Modules\Microsoft.PowerShell.LocalAccounts\1.0.0.0\Microsoft.Powershell.LocalAccounts.dll
DLL file version: 10.0.19041.4957
DLL SHA-256: 52f2e80c3fec63ac22401a41964a3b0d78e7e9f6ed2b470638540c8c8f17c11f
```

`Get-Command ... -Syntax` established the installed parameter sets for
`Get-LocalUser`, `New-LocalUser`, `Get-LocalGroup`, `Get-LocalGroupMember`, and
`Add-LocalGroupMember`. Local `Get-Help` supplied only sparse help, so Microsoft
documentation supplies the behavioral descriptions. No `Update-Help` ran.

The selected Microsoft contracts are:

| Surface | Contract used |
| --- | --- |
| [NetUserAdd](https://learn.microsoft.com/en-us/windows/win32/api/lmaccess/nf-lmaccess-netuseradd) and [USER_INFO_1](https://learn.microsoft.com/en-us/windows/win32/api/lmaccess/ns-lmaccess-user_info_1) | Local level-1 creation, exact inputs, documented defaults and returned NET_API_STATUS. |
| [NetUserGetInfo](https://learn.microsoft.com/en-us/windows/win32/api/lmaccess/nf-lmaccess-netusergetinfo) | Level 1 absence query; levels 2 and 23 account/SID readback. |
| [NetUserEnum](https://learn.microsoft.com/en-us/windows/win32/api/lmaccess/nf-lmaccess-netuserenum) | Level 0, filter 0, fully resumed enumeration; totalentries is only a hint. |
| [NetUserGetLocalGroups](https://learn.microsoft.com/en-us/windows/win32/api/lmaccess/nf-lmaccess-netusergetlocalgroups) | Separate flags=0 direct and LG_INCLUDE_INDIRECT views, level 0. |
| [NetLocalGroupAddMembers](https://learn.microsoft.com/en-us/windows/win32/api/lmaccess/nf-lmaccess-netlocalgroupaddmembers) | One conditional local-group effect, level 0, exact new SID. |
| [Read-Host](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/read-host?view=powershell-7.5) | `-AsSecureString` masks interactive input and returns SecureString; present in installed 5.1. No plaintext-returning `-MaskInput`. |
| [SecureStringToGlobalAllocUnicode](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.marshal.securestringtoglobalallocunicode) and [ZeroFreeGlobalAllocUnicode](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.marshal.zerofreeglobalallocunicode) | Final-boundary unmanaged marshal and matching zeroing free. |
| [Get-LocalGroup](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.localaccounts/get-localgroup?view=powershell-5.1) and [Get-LocalGroupMember](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.localaccounts/get-localgroupmember?view=powershell-5.1) | Read-only local-group inventory and membership-edge cross-checks; no mutation cmdlets are used. |

Read-only inspection of Windows SDK 10.0.26100.0 `um\lmaccess.h` and
`shared\lmerr.h` confirms the declarations/constants, including DWORD
`NetUserEnum` resume state, `USER_PRIV_USER=1`, `UF_SCRIPT=0x0001`,
`UF_NORMAL_ACCOUNT=0x0200`, `UF_ACCOUNTDISABLE=0x0002`,
`UF_DONT_EXPIRE_PASSWD=0x00010000`, `LG_INCLUDE_INDIRECT=1`,
`NERR_Success=0`, `NERR_UserNotFound=2221`, and `NERR_UserExists=2224`.
All Netapi32 statuses are function return values; do not substitute a stale
`GetLastError` value. Buffer ownership uses
[NetApiBufferFree](https://learn.microsoft.com/en-us/windows/win32/api/lmapibuf/nf-lmapibuf-netapibufferfree),
including returned enumeration buffers on `ERROR_MORE_DATA`.

Microsoft's versioned [LocalAccounts Sam.cs](https://github.com/PowerShell/PowerShell/blob/v7.4.0/src/Microsoft.PowerShell.LocalAccounts/LocalAccounts/Sam.cs)
provides corroborating implementation evidence: `CreateUser` creates, sets
properties, reads back, and deletes the new user in its exception handler.
That source tag is not assumed to be the installed binary. Read-only .NET
reflection of the installed DLL independently established:

```text
method: System.Management.Automation.SecurityAccountsManager.Sam.CreateUser
catch System.Exception: IL offset 198, length 23
IL_0056: call SamCreateUser2InDomain
IL_0096: call SetUserData
IL_00BD: call MakeLocalUserObject
IL_00D5: call SamDeleteUser (inside the catch handler)
```

Only `GetMethodBody`, IL decoding, metadata resolution, version inspection, and
file hashing were used. No private method or account mutation API was invoked.
The public implementation also maps name collisions to an existing-name error;
that create-new behavior does not fix the rollback conflict. Do not invoke
private SAM APIs from the ceremony or treat these implementation details as a
supported replacement API.

`New-LocalUser` remains rejected: neither `-ErrorAction Stop` nor an outer
`finally` suppresses its internal post-create deletion. The selected replacement
is the direct documented Netapi32 call described below, not an invocation of
private SAM APIs or a wrapper around the rejected cmdlet.

## Future order and approval boundary

After helper source acceptance, separate ChatGPT approval must name the exact
host, creator, candidate, NetUserAdd inputs, the **one conditional Users-membership
effect**, password boundary, qualification process, fixed evidence root, and
reviewed ceremony/helper commit and tree. Expected Windows logon/profile effects
must also be covered. No KSP, production access, cleanup, or source SID freeze
is implied.

The required order is:

1. Verify the reviewed checkpoint/helper identity, host, and genuine elevated
   creator token. Require separate effect authorization; this docs checkpoint
   supplies none.
2. Resolve the builtin Users SID/name bidirectionally. Prove exact candidate
   absence using both NetUserGetInfo and fully resumed NetUserEnum. Prove the
   fixed evidence root absent. Inspect known group/logon-context prerequisites.
3. Exclusively create the fixed evidence root; publish/reload sanitized preflight.
4. Collect the password using `Read-Host -AsSecureString` in the creator process.
5. Repeat creator and dual-absence gates; durably publish/reload
   `ACCOUNT_CREATION_ATTEMPTED`. Only then marshal and call NetUserAdd once.
6. Zero/free the transient password buffer in `finally`. On NERR_Success retain
   the account and publish `ACCOUNT_CREATED`; independently read back its real
   Windows SID, exact local name, normal account type/privilege, and enabled state.
7. Read direct groups. If exactly Users, record the no-effect branch. If empty,
   recheck actor/account/Users mapping, durably record `USERS_ASSIGNMENT_ATTEMPTED`,
   call NetLocalGroupAddMembers once, and require exact Users-only readback before
   `USERS_ASSIGNMENT_CONFIRMED`. Every other state or unsuccessful return stops.
8. Separately enumerate direct, documented indirect, and genuine interactive
   token authority. Apply the narrowly reviewed host-dynamic exception and
   privilege gates. Recheck enabled state and identity continuity.
9. Publish `GROUPS_QUALIFIED` and then `TOKEN_QUALIFIED` only after all required
   observations pass. Retain account/evidence and stop for review before any
   harness source freeze or launch preparation.

Resuming a read-only paginated NetUserEnum query is not an effect retry. Neither
mutation has a retry, cleanup, repair, alternate-name, or crash-resume branch.
No step runs now: implementation/review of the disabled helper is the next
milestone, not an unresolved choice of creation semantics.

## Exact genuine creator-token gate

The operator would open the installed 64-bit Windows PowerShell 5.1 with
`-NoLogo -NoProfile`, using Windows' Run as administrator UI, on the fixed host.
Approve UAC only for the intended operator. Do not automate credential entry.
Require `[Environment]::MachineName` to equal `DESKTOP-I4DOKM7`; host text alone
does not replace the token or machine-local account proof.

The exact read-only API recipe below is the token authority. It must execute
inside the process being qualified, on its calling thread; a child `whoami`,
environment variable, supplied SID, or another process's token is insufficient.
This is an API specification, not a claim that an executable reader has already
been implemented or run. Any future reader must implement this recipe and be
reviewed without importing/enabling the KSP harness.

| Step | Exact call/decoding and acceptance |
| --- | --- |
| Reject impersonation | `OpenThreadToken(GetCurrentThread(), TOKEN_QUERY=0x0008, TRUE, &threadToken)`. Only failure with `GetLastError()==ERROR_NO_TOKEN (1008)` proceeds. Success means an impersonation token exists: close it and STOP. Every other failure is unknown, hence STOP. Repeat at the end. |
| Open genuine process token | `OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY=0x0008, &processToken)`. Require success and non-NULL handle. Do not accept a caller-supplied process/token handle. |
| Token type | `GetTokenInformation(processToken, TokenType=8, ...)`; exactly four bytes, `TokenPrimary=1`. |
| User | `GetTokenInformation(processToken, TokenUser=1, ...)`; decode `TOKEN_USER.User.Sid`, validate SID bounds/length and `IsValidSid`, convert with `ConvertSidToStringSidW`. Require the exact creator SID above. |
| Elevation | `GetTokenInformation(processToken, TokenElevation=20, ...)`; exactly one four-byte `TOKEN_ELEVATION.TokenIsElevated`, require `1`. |
| Elevation type | `GetTokenInformation(processToken, TokenElevationType=18, ...)`; exactly four bytes, require `TokenElevationTypeFull=2`. Default or Limited fails the creator gate. |
| Administrators | `GetTokenInformation(processToken, TokenGroups=2, ...)`; find exactly one `S-1-5-32-544`, require `SE_GROUP_ENABLED (0x00000004)` set and `SE_GROUP_USE_FOR_DENY_ONLY (0x00000010)` clear. Retain its numeric attributes. |
| Completion | Repeat no-thread-token check, close process token with `CloseHandle`, and release every conversion allocation using `LocalFree`. Failure to decode or release is a STOP, not a PASS with incomplete evidence. |

Use the documented sizing call for variable buffers, requiring only the expected
insufficient-buffer response; allocate the returned length and require the data
call to succeed consistently. Bound every count, offset, pointer, SID, and
structure to the returned allocation before dereferencing. Use native structure
alignment, including the aligned first `SID_AND_ATTRIBUTES` in `TOKEN_GROUPS`;
do not hard-code a 32-bit pointer layout in the 64-bit process. A duplicate SID,
unknown enumeration value, invalid boolean, changed size, or malformed result
is uncertainty. Never print or serialize handles or raw token buffers.

These semantics come from [OpenThreadToken](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openthreadtoken),
[OpenProcessToken](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocesstoken),
[GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation),
[TOKEN_INFORMATION_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class),
[TOKEN_ELEVATION_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_elevation_type),
and [TOKEN_GROUPS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_groups).
The creator must repeat this gate immediately before either authorized mutation;
an earlier successful observation is not perpetual authority.

## Exact dual name-absence proof

Both proofs must pass on the fixed host **before secure password entry**, and
both are repeated before the durable creation-attempt record. All query calls
use NULL server and the code-owned candidate name; no caller host/name override.

| Proof | Exact future read-only API contract |
| --- | --- |
| A: point lookup | `NetUserGetInfo`: server=NULL, username=`P3R1KspTestUser`, level=1, output buffer initially NULL. Only returned `NERR_UserNotFound (2221)` establishes this proof's definite-not-found result. `NERR_Success` means existing account: STOP. Every other status or malformed output means unknown: STOP. |
| B: complete enumeration | `NetUserEnum`: server=NULL, level=0 (`USER_INFO_0` names), filter=0 (all account types), prefmaxlen=`MAX_PREFERRED_LENGTH (0xffffffff)`, DWORD resume value initially 0. Process every returned page and continue `ERROR_MORE_DATA (234)` using the API-updated resume value unchanged. Require terminal `NERR_Success` and zero ordinal case-insensitive exact-name matches. |

Do not use `FILTER_NORMAL_ACCOUNT`: an existing differently typed account still
collides with the fixed name. Retain each page's status and entry count and
whether resume progress occurred. `totalentries` is a hint, not a completion
proof or a fixed count to stop at. Reject malformed names/buffers, duplicate
names, stalled/cyclic resume state, a partial enumeration, or any terminal
status other than success. Free each API-owned page exactly once, even after
ERROR_MORE_DATA; do not keep a pointer after freeing its buffer.

If either proof shows the name exists, including different casing, STOP.
Any contradiction between the two proofs, access failure, unresumed
ERROR_MORE_DATA, or ambiguity also stops. No `SilentlyContinue`, empty display,
generic exception, or create error counts as absence. Retain sanitized statuses,
page counts, zero-match result and completion facts, not unrelated account data.

No adoption, reset, deletion, rename, recreation, or alternate name is allowed.
These sequential queries are not a lock or a claim of transactional isolation:
the future create-new call must still reject a collision occurring after them.

## Secure password marshal contract

The future secure interactive input is exactly `Read-Host -AsSecureString` in
the creator's own local PowerShell console, after both absence proofs pass.
The operator types the password directly at that secure prompt. **No password
prompt runs in this checkpoint.**

No agent, remote tool, clipboard automation, command literal/argument,
environment variable, transcript, screen recording, debugger, repository file,
temporary password file, evidence, log, or report captures the entry. No
`Start-Transcript`; if the secret-entry capture boundary cannot be established,
STOP without changing machine logging policy. PowerShell history may contain
the prompt command, never the password entered in response.

The separately reviewed in-process helper must:

1. Keep input as SecureString; require a supplied nonempty password without
   printing or retaining password-derived data.
2. After durable creation-attempt publication and final actor/identity checks,
   marshal immediately at the final Win32 boundary using
   `Marshal.SecureStringToGlobalAllocUnicode`.
3. Put only that returned pointer in `USER_INFO_1.usri1_password` and call the
   one authorized `NetUserAdd` synchronously.
4. In `finally`, after the call returns or unwinds, invoke the matching
   `Marshal.ZeroFreeGlobalAllocUnicode` exactly once for every acquired
   allocation, then dispose the SecureString and clear local references.
   Never use ordinary `FreeHGlobal` as the password-buffer cleanup.
5. Retain only mechanism, call status, and cleanup-completion booleans.
   A marshal/cleanup failure stops; it does not authorize another create.

**Plaintext necessarily exists briefly in the unmanaged buffer consumed by
the Win32 account-creation API.** It must never intentionally become a managed
String, be printed, serialized, logged, passed through shell arguments or
environment, or retained as evidence. No `NetworkCredential.Password`,
`GetNetworkCredential().Password`, `PtrToString*`, SecureString serialization,
password hash/hint/length output, or whole-structure/error dump is permitted.
Public non-secret account names may be decoded; the password pointer must
never be decoded into managed text. Abrupt process termination cannot guarantee
execution of `finally`; it leaves the effect state uncertain and non-retryable,
not permission to claim cleanup or creation success.

## Exact future NetUserAdd boundary

The helper will bind the documented `Netapi32.dll!NetUserAdd` entry point.
This table is a **nonexecutable API specification**, not account-creation code:

| Argument/member | Exact value |
| --- | --- |
| `servername` | NULL: local computer only. |
| `level` | 1. |
| `buf` | Pointer to the correctly aligned `USER_INFO_1` structure below, valid through the call. |
| `parm_err` | Pointer to a DWORD initialized to 0; retain a field index only when the returned error documents its meaning. |
| `usri1_name` | Exact UTF-16 `P3R1KspTestUser`. |
| `usri1_password` | Transient protected-input marshal pointer described above; never a shell argument or managed plaintext String. |
| `usri1_password_age` | 0 initialization; ignored by NetUserAdd, not an age-policy setting. |
| `usri1_priv` | `USER_PRIV_USER=1`. |
| `usri1_home_dir` | NULL. |
| `usri1_comment` | Exact non-secret `P3-R1 ordinary non-admin test only`. |
| `usri1_flags` | Exactly `UF_SCRIPT=0x00000001`. |
| `usri1_script_path` | NULL. |

Do not add `UF_ACCOUNTDISABLE`, `UF_DONT_EXPIRE_PASSWD`,
`UF_PASSWD_NOTREQD`, `UF_PASSWD_CANT_CHANGE`, administrator/guest privilege,
trust-account flags, delegation authority, or service configuration. Do not add
even a plausible extra flag to the frozen input. `UF_SCRIPT` is the required
flag; the NULL script path supplies no logon script.

Microsoft documents these **level-1 defaults**, separately from explicit inputs:

| Additional member | Documented default |
| --- | --- |
| `usriX_auth_flags` | 0. |
| `usriX_full_name`, `usriX_usr_comment`, `usriX_parms` | Null strings. |
| `usriX_workstations` | All, represented by a null string. |
| `usriX_acct_expires` | Never, `TIMEQ_FOREVER`. |
| `usriX_max_storage` | `USER_MAXSTORAGE_UNLIMITED`. |
| `usriX_logon_hours` | All bits set, each byte 0xff. |
| `usriX_logon_server` | Any domain controller, `\\*`. |
| `usriX_country_code`, `usriX_code_page` | 0. |

The helper does not follow creation with `NetUserSetInfo` to change these
defaults. Full name therefore remains the documented null default rather than
the old draft's explicit display-name setting. These defaults grant no new
filesystem access or service authority and do not override logon-rights policy.

Password length/complexity/history and minimum/maximum age remain controlled by
local policy. Leaving `UF_DONT_EXPIRE_PASSWD` clear does not invent an expiry
date: host policy may itself have no maximum age. The ceremony does not set
`UF_PASSWD_CANT_CHANGE` or request forced first-logon password change; effective
password-change rights and any policy-enforced change remain subject to Windows
policy/security. If policy rejects creation or prevents the required unchanged-
password logon, STOP without resetting the password or changing policy. Require
normal account type, ordinary privilege and enabled state on actual readback;
do not assume a successful API return proves qualification.

### Create return classification

| Result after NetUserAdd begins | Required classification |
| --- | --- |
| `NERR_Success (0)` | The creation call succeeded. The account must now be retained. Set `ACCOUNT_CREATED` only for this confirmed return, then perform independent readback. Success supplies no SID and does not itself qualify the identity. |
| `NERR_UserExists (2224)` | Collision: STOP, never adopt. Retain the attempted-call/status evidence and leave the existing account untouched. |
| Any other non-success, exception, lost return, or ambiguity | Creation outcome `UNCERTAIN` for retention purposes. STOP; only read-only reconciliation is permitted. An error is not proof that no account exists. |

This includes password-policy, access, and group-name collision errors: retain
their sanitized codes without converting them into permission to retry.
`NetUserAdd` is **not claimed to be transactional**. The helper issues no delete,
reset, rename, set-info, rollback, repair, or repeat call. Read-only
reconciliation cannot retroactively resume this ceremony or adopt the name.

## Exact account/SID readback and bidirectional mapping

After confirmed NetUserAdd success, call `NetUserGetInfo` independently at
levels **2** and **23**, each with server=NULL and exact candidate name.
Both must return NERR_Success with complete, valid output. Level 2 supplies
ordinary privilege/account flags and additional defaults; level 23
([USER_INFO_23](https://learn.microsoft.com/en-us/windows/win32/api/lmaccess/ns-lmaccess-user_info_23))
supplies the real `usri23_user_sid`. Do not predict or construct a RID.

Require:

- Both returned names exactly `P3R1KspTestUser`, with consistent flags/comment.
- `usri2_priv=USER_PRIV_USER` and the account-type portion of returned flags
  exactly `UF_NORMAL_ACCOUNT`, with no trust/temp-duplicate account type.
- `UF_ACCOUNTDISABLE` clear (enabled), `UF_DONT_EXPIRE_PASSWD` clear and
  `UF_PASSWD_NOTREQD` clear; no unexpected security-sensitive flag. Inspect the
  actual flags rather than guessing from a calculated expiry date.
- The exact test description and documented level-1 defaults where represented
  by level-2 readback. Null strings may be NULL pointers or empty strings;
  compare their documented semantic value. No follow-up property mutation.
- A valid Windows-supplied SID whose account-domain portion equals
  `S-1-5-21-1397534616-3988210162-180023805`, distinct from the creator and
  Trading SIDs. This is a consistency check on returned identity, not prediction.

Validate structures, SID lengths, strings and allocation bounds before decoding.
Never serialize the whole level-2 structure; its password member is documented
as NULL on query, and must never be converted into text. Copy only sanitized
fields and the validated public SID before `NetApiBufferFree`.

Independently use
[LookupAccountSidW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-lookupaccountsidw)
with NULL system and the read-back SID; require `SidTypeUser`, exact candidate
name and domain `DESKTOP-I4DOKM7`. Then use
[LookupAccountNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-lookupaccountnamew)
with NULL system and exact `DESKTOP-I4DOKM7\P3R1KspTestUser`; require
`SidTypeUser` and identical SID. Re-read level 23 to reject mapping drift.
Every size probe, data call and release is checked. A wrong host/name/SID,
disabled account, malformed result or ambiguity is a STOP.

Freeze this only as `ACCOUNT_SID_READ_BACK` pending group/token qualification.
Any uncertain create remains terminal even if a later read finds the name.
No name-only adoption and no harness source change occurs in this ceremony.

## Deterministic conditional Users assignment

Microsoft's reviewed NetUserAdd contract does **not** freeze automatic
`BUILTIN\Users` assignment. This procedure does not claim that it does.
Instead the following branch is frozen before creation and must be expressly
included in the later account/group effect authorization.

First resolve `S-1-5-32-545` locally using LookupAccountSidW; require one
`SidTypeAlias` in the builtin domain. Cross-check
`Get-LocalGroup -SID S-1-5-32-545` and a qualified name-to-SID lookup against
the same SID. Freeze the returned local alias name as `resolved_users_name`.
Do not hard-code the English display name or accept a caller-selected group.
Re-prove this mapping immediately before a conditional add.

After successful creation and SID readback, call NetUserGetLocalGroups with
server=NULL, username=`P3R1KspTestUser`, level=0, **flags=0**, and
prefmaxlen=MAX_PREFERRED_LENGTH. Resolve every returned group name to a unique
local group SID; require terminal NERR_Success, consistent complete counts,
valid strings/SIDs, no duplicates and agreement with direct inventory edges.
This API has no resume parameter: ERROR_MORE_DATA or incomplete output stops.

| Complete direct group set before baseline | Sole permitted action |
| --- | --- |
| Exactly `{S-1-5-32-545}` | Record `ALREADY_USERS`. No group mutation. Continue with read-only qualification. |
| Exactly `{}` | Record `ADD_USERS`, repeat exact creator/account/group-mapping and empty-set checks, durably publish/reload `USERS_ASSIGNMENT_ATTEMPTED`, then make the one call below. |
| Any other set, failed/incomplete read, or mapping ambiguity | STOP, retain account/evidence, and do not alter memberships. |

The nonexecutable specification for that one effect is:

| NetLocalGroupAddMembers argument | Frozen value |
| --- | --- |
| `servername` | NULL, local host. |
| `groupname` | Exact `resolved_users_name` whose SID was re-proved as `S-1-5-32-545`. |
| `level` | 0. |
| `buf` | One [LOCALGROUP_MEMBERS_INFO_0](https://learn.microsoft.com/en-us/windows/win32/api/lmaccess/ns-lmaccess-localgroup_members_info_0) with `lgrmi0_sid` pointing to the validated new account SID. |
| `totalentries` | 1. |

Only NERR_Success followed by fresh exact direct-membership readback
`{S-1-5-32-545}` and account/group identity continuity permits
`USERS_ASSIGNMENT_CONFIRMED`. Any failed or ambiguous call, including
ERROR_MEMBER_IN_ALIAS, is a STOP, not an idempotent success. A failed confirmation
write/readback is uncertain. Never retry, remove membership, or repair the account.

This is the single reviewed conditional baseline effect, not authority to fix
an unexpected membership or a previously failed gate. No other add/remove-group
command/API is allowed. Record both branch choice and actual attempted/confirmed
facts; the no-effect branch leaves both Users-assignment booleans false.

## Direct, indirect, token, and special authority qualification

Retain three separately labeled views; none substitutes for the others:

| View | Exact source and interpretation |
| --- | --- |
| Direct account assignment | NetUserGetLocalGroups, NULL server, exact candidate name, level 0, flags=0, MAX_PREFERRED_LENGTH. Require precisely Users after baseline. |
| Direct plus documented indirect membership | Same call with flags=`LG_INCLUDE_INDIRECT (1)`. This adds local groups reached through global-group membership as Microsoft documents; it is not a claim to enumerate all logon-context authority. |
| OS-added logon/token identities | The actual genuine interactive process's `TokenGroups`, with every SID and attributes, plus its `TokenPrivileges`. Do not infer this view from account-directory data. |

For both NetUserGetLocalGroups calls, require NERR_Success and complete counts;
ERROR_MORE_DATA, missing/unresolved group names, duplicates or any query failure
stop. Resolve names to actual local SIDs and release buffers with NetApiBufferFree.
Compare direct and indirect views; contradictory or unexplained differences
block qualification. These observations are not an atomic directory snapshot;
recheck identity/group continuity and stop on observed drift.

Enumerate all local groups with `Get-LocalGroup` and every group's members with
`Get-LocalGroupMember -SID`, using terminating errors, without filtering away
unwanted groups. Validate unique SIDs/edges and complete enumeration. Compare
edges directly listing the new SID to the flags=0 view. Unresolved principals,
missing groups, partial results, cycles that cannot be classified, or failed
group reads stop rather than certifying the successful subset.

Build the observable graph with edges `member_sid -> group_sid`. Label paths
from the account's assigned memberships separately from those seeded by
OS-added token SIDs. Record all relevant edges and their origins. Directory
traversal cannot explain every domain or dynamic membership: any unexplained
effective authority is a STOP.

Reject direct, documented indirect, graph-reachable, or effective membership in
Administrators (`S-1-5-32-544`), Backup Operators (`551`), Power Users (`547`),
Cryptographic Operators (`569`), Remote Management Users (`580`),
CodexSandboxUsers (resolve its actual SID), or any other unreviewed privileged/
special-purpose group. The abbreviated numeric values here are builtin
`S-1-5-32-*` identities, not predicted candidate RIDs. The only special exception
is Performance Log Users under every condition in the following section.

Everyone (`S-1-1-0`), Authenticated Users (`S-1-5-11`), and INTERACTIVE (`S-1-5-4`)
are normal OS logon/token identities, not direct assignments to local groups.
Use Microsoft's [well-known SID reference](https://learn.microsoft.com/en-us/windows/win32/secauthz/well-known-sids)
to classify these, session/authentication SIDs, and integrity SIDs. Unknown SIDs
remain unresolved rather than acquiring authority from a familiar display name.

### INTERACTIVE / Performance Log Users: conditional host-dynamic baseline

The initial draft's 2026-09-02 read-only inspection returned:

```text
group: Performance Log Users / S-1-5-32-559
members:
  DESKTOP-I4DOKM7\John / S-1-5-21-1397534616-3988210162-180023805-1005
  NT AUTHORITY\INTERACTIVE / S-1-5-4
Get-LocalGroup -Name INTERACTIVE: GroupNotFound
```

INTERACTIVE is an OS-controlled logon identity, not a separate machine-local
alias. This historical observation is not a fresh candidate-token result.
Microsoft's [PLA documentation](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/pla/pla-interfaces)
establishes that Performance Log Users carries special-purpose authority.
The following acceptance is a **specific ChatGPT architecture-review decision
supplied for this task**, not a Microsoft claim that the group is harmless.

```text
INTERACTIVE_PERFORMANCE_LOG_USERS_CLASSIFICATION=
CONDITIONALLY_ACCEPTED_HOST_DYNAMIC_BASELINE
```

For this KSP denial experiment only, effective Performance Log Users may be
accepted if future evidence proves **all** of the following:

1. The new SID is not directly assigned to Performance Log Users; its complete
   direct local-group set remains exactly `{S-1-5-32-545}`.
2. Current group inventory contains the reviewed direct edge
   `S-1-5-4 -> S-1-5-32-559` and the genuine interactive token contains enabled
   INTERACTIVE. Effective Performance Log Users originates only from that edge.
3. No independent account-assignment/global-group/nested path to Performance
   Log Users exists. Reconcile the flags=0 and flags=1 views, all relevant
   membership edges and other enabled token SIDs; another route or an unresolved
   origin fails. Mere simultaneous presence of the two token SIDs is not proof.
4. No direct, indirect, or effective Administrators, Cryptographic Operators,
   Backup Operators, Power Users, or Remote Management Users membership exists.
   Other unreviewed special groups remain excluded.
5. The genuine token's held/enabled privileges contain no unexpected security-
   management authority capable of bypassing or managing the intended KSP
   boundary. Apply the privilege gate below, including disabled held privileges.

Retain edge evidence, directory views, token SID attributes, absence of alternate
paths, and an explicit passed/failed provenance verdict. The token records
effective SIDs; it does not itself encode why a group was added. Provenance
therefore requires its reconciliation with current host membership evidence.
If that exact provenance cannot be proved, STOP and retain account/evidence.

A **direct Performance Log Users assignment is always a STOP**. Its absence
from the token is not itself a failure; record actual observations and require
a consistent explanation. Do not generalize conditional acceptance to another
group, change host membership, grant an ACE, or infer production/KSP authority.
Architecture 98's protected SYSTEM/Administrators-only key DACL remains exact;
the candidate receives no key ACE or signing/control grant. This ceremony does
not open a key to test that boundary.

### Privileges and user rights

In the same genuine process, decode `TokenPrivileges=3` and resolve every
LUID using `LookupPrivilegeNameW`. Retain names, full numeric attributes,
`enabled`, `enabled_by_default`, and `removed` booleans derived from those
attributes, plus an explicit disposition. No token handles or raw buffers.

Reject held authority relevant to bypassing/controlling the security boundary,
whether currently enabled or disabled: at minimum `SeDebugPrivilege`,
`SeBackupPrivilege`, `SeRestorePrivilege`, `SeTakeOwnershipPrivilege`,
`SeSecurityPrivilege`, `SeTcbPrivilege`, `SeCreateTokenPrivilege`,
`SeAssignPrimaryTokenPrivilege`, `SeImpersonatePrivilege`,
`SeLoadDriverPrivilege`, and `SeRelabelPrivilege`. Unexpected additional
security-management privileges also fail; the minimum list is not an allowlist
for everything else. Disabling a held privilege cannot make the account pass.

Do not reject normal Windows baseline privileges merely for existing.
For example, `SeChangeNotifyPrivilege` (normal traverse/change notification)
is ordinary baseline authority and may be recorded `ACCEPTED`. Classify other
observed privileges by the reviewed Windows meaning and this KSP threat model;
unknown or unresolved security significance stops. Microsoft's
[privilege constants](https://learn.microsoft.com/en-us/windows/win32/secauthz/privilege-constants)
define the meanings. Do not adjust privileges to manufacture a passing token.

Inspect policy rights read-only with
[LsaOpenPolicy](https://learn.microsoft.com/en-us/windows/win32/api/ntsecapi/nf-ntsecapi-lsaopenpolicy)
(local system, initialized object attributes, `POLICY_LOOKUP_NAMES=0x00000800`)
and [LsaEnumerateAccountRights](https://learn.microsoft.com/en-us/windows/win32/api/ntsecapi/nf-ntsecapi-lsaenumerateaccountrights)
for the new SID and each relevant effective group SID. Separate directly
assigned rights from inherited rights; a SID with documented no-rights status
is not a query failure. All other errors stop. Release memory with
`LsaFreeMemory` and policy with `LsaClose`. Review service/batch logon and other
special rights as well as token privileges; do not add rights or start services.

Ordinary Windows token privileges are not automatically failures, but every
observed privilege/right requires a recorded disposition. Unknown or unresolved
authority blocks `GROUPS_QUALIFIED`. No group or policy mutation can turn that
failure into a pass within this ceremony.

## Genuine non-elevated qualification session

The selected future logon path is the physical Windows sign-in UI, not
impersonation or a synthetic token. Microsoft documents
[switching users and signing in](https://support.microsoft.com/en-US/accounts-billing/security/user-account-access-in-windows).
After all pre-logon gates and separate authorization:

1. The operator uses Start -> account picture -> Switch user, selects Other user
   where available, and enters `DESKTOP-I4DOKM7\P3R1KspTestUser` at the Windows
   sign-in screen. Type the password directly into the Windows password field.
   Do not transmit it to an agent or capture the sign-in screen/input.
2. If the UI is unavailable, logon is denied, credentials fail, or a password
   change is demanded, STOP. Do not reset the password, grant logon rights,
   enable an account, use a different launch mechanism, or try again to repair it.
3. On the new user's desktop, use Win+R and launch exactly:

   ```text
   C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoLogo -NoProfile
   ```

   Do not use Run as administrator, enter administrator credentials, use remoting,
   a scheduled task, service, `/netonly`, `/savecred`, or harness impersonation.
   Expected profile creation and normal Windows logon/audit effects must be
   included in the future approval; this is not a zero-OS-effect launch.
4. Run the reviewed read-only process-token recipe from this exact process.
   Compare TokenUser to the SID obtained from the retained Windows readback,
   independently require its local name/SID round trip, and require account
   enabled again from this process. The comparison SID is a check against
   Windows evidence, never a replacement for reading TokenUser.
5. Require `TokenPrimary`, no thread impersonation token,
   `TokenElevation=false` (DWORD 0), and elevation type in the valid non-Full
   set `{Default=1, Limited=3}`. Unknown numeric values fail. Require
   Administrators not enabled; also reject its presence as deny-only so a
   filtered administrator cannot pass the ordinary-user contract. Direct and
   indirect administrator membership already fail the group gate.
6. Retain every decoded group and privilege with attributes. Require enabled
   INTERACTIVE and resolve all special effective authority, including Performance
   Log Users, before certifying the token. Reconcile fresh account/group
   readbacks in the creator session; drift or unreadability stops qualification.

`runas` was reviewed but is not selected: Microsoft's
[runas documentation](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/cc771525(v=ws.11))
documents interactive password entry and notes that it does not process the
target user's Group Policy as a full desktop logon does. Installed `runas /?`
did not yield usable help in this noninteractive tool session; no launch was
attempted. Do not silently substitute it for the frozen desktop logon.

No new-user write access to retained evidence is required. The operator may
transfer only the displayed sanitized facts from the genuine session to the
creator's fixed-root publisher, recording `operator_observed_console` as the
collection method and checking the full transfer for equality. This is an
operator-attested observation, not cryptographic authentication of a token.
If exact capture or independent reconciliation is not possible, STOP rather
than broadening ACLs or asserting token facts. Neither this observation nor an
unkeyed digest becomes production authority.

## Fixed evidence root, canonical schema, and durability

No ceremony root is created in this documentation task. The future publisher
has exactly one path, with no argument/environment override:

```text
F:\AI\p3-r1-ordinary-nonadmin-principal-v1
```

Require the existing parent `F:\AI` and its ancestors to resolve as ordinary
local directories without reparse traversal. Use
[GetFileAttributesW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileattributesw)
to distinguish a definitely absent final component from access/query errors;
accept `ERROR_FILE_NOT_FOUND` only after proving the parent exists. A file,
directory, or reparse point at the fixed root means STOP. Do not create missing
parents or choose a new suffix. Freeze volume/root identity and inspect owner/
DACL read-only. If existing access does not protect retained evidence from
untrusted writers, stop; do not alter `F:\AI` or retained-evidence ACLs.

For the eventual root creation use
[CreateDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createdirectoryw)
with the exact path and NULL security attributes, then verify identity and
inherited security. Success must be new creation; `ERROR_ALREADY_EXISTS` is a
STOP, never adoption. Do not use idempotent `.NET Directory.CreateDirectory`
as proof of exclusive creation. A failed subsequent security check leaves the
root retained and prevents account creation. No ACL-repair fallback exists.

Retain handles/identity observations needed to reject parent/root replacement
before each publication. The future publisher must be reviewed for these checks;
path-string equality and a preflight-only reparse check do not prove continuity.

Each record has filename `record-NNN.json`, with `NNN` the three-digit, gap-free
sequence starting at `001`; there is no caller filename. Use exclusive
`FileStream` creation (`FileMode.CreateNew`, `FileAccess.Write`, `FileShare.None`,
`FileOptions.WriteThrough`), write the complete canonical record, call
[`Flush(true)`](https://learn.microsoft.com/en-us/dotnet/api/system.io.filestream.flush?view=netframework-4.8.1),
close, independently reload, and require exact bytes plus strict schema/state
validation before advancing. Never overwrite, append within, replace, or repair
an existing record. Flush requests OS/storage persistence; it is not a promise
against defective hardware. No effect follows an unconfirmed flush/reload.

Canonical format is `p3-r1-ordinary-nonadmin-principal-evidence/v1`: UTF-8
without BOM, one compact JSON object, no trailing newline, keys recursively
sorted by ordinal Unicode order, unique keys, no insignificant whitespace.
Strings escape quote/backslash and controls; encode controls as lowercase
`\u00xx`, preserve other Unicode scalars as UTF-8, and reject unpaired
surrogates. Use JSON booleans/null and nonnegative decimal integers without
leading zeros; no floats. SID strings are canonical Windows SID strings.
SHA-256 values are lowercase 64-digit hex. Timestamps are informational UTC
`yyyy-MM-ddTHH:mm:ss.fffffffZ`, never identity or permission.

The exact top-level keys are:

| Field | Type and meaning |
| --- | --- |
| `schema` | Exact version string above. |
| `sequence` | Integer 1 through 999; exhaustion stops. |
| `previous_sha256` | null for sequence 1, otherwise SHA-256 of the entire prior canonical record. |
| `event` | One event from the table below. |
| `outcome` | `PASS`, `FAILED`, `UNCERTAIN`, or `BLOCKED`. |
| `utc` | Informational timestamp in the fixed format. |
| `host` | `{name, machine_domain_sid, os_version}` from the fixed host and Windows readback. |
| `ceremony` | `{source_commit, source_tree, evidence_root, candidate_name, creator_sid, trading_sid}`; exact approved values. |
| `lifecycle` | The seven booleans below; monotonically false -> true only. |
| `facts` | Event-specific closed object below; no unlisted fields. |
| `failure` | null on PASS; otherwise `{boundary, code, effect_may_have_occurred}`, using fixed sanitized classification and boolean. No raw exception text. |

`lifecycle` has exactly `ACCOUNT_CREATION_ATTEMPTED`, `ACCOUNT_CREATED`,
`ACCOUNT_SID_READ_BACK`, `USERS_ASSIGNMENT_ATTEMPTED`,
`USERS_ASSIGNMENT_CONFIRMED`, `GROUPS_QUALIFIED`, and `TOKEN_QUALIFIED`.
All begin false. The three account facts advance in that order.
`ACCOUNT_CREATED` denotes a confirmed NERR_Success, not qualification.
An attempted-but-unconfirmed call has attempted=true and created=false;
false does not prove that no account exists.

Both Users-assignment facts stay false on `ALREADY_USERS`. On `ADD_USERS`,
attempted requires account SID readback and durable empty-set/identity checks;
confirmed requires attempted, NERR_Success and Users-only readback.
`GROUPS_QUALIFIED` requires the account facts, exactly one baseline-branch
record, and either the no-effect Users proof or confirmed assignment, followed
by all group/provenance/privilege gates. `TOKEN_QUALIFIED` requires
`GROUPS_QUALIFIED` and the genuine-token/enabled-state gates. No skipped,
regressed, duplicated, or inconsistent transition is valid.

The allowed ordered events and exact `facts` members are:

| Event | Facts |
| --- | --- |
| `PREFLIGHT` | `creator_token`, `absence`, `root_absent`, `root_identity` (`{volume_serial, file_id, owner_sid, dacl_sddl}`), `tools` (`{powershell_version, helper_source_commit, helper_source_tree, helper_sha256, netapi32_version}`), `users_identity` (`{sid, resolved_name, domain, sid_type, roundtrip_passed}`), `baseline_mode` (exactly `CONDITIONAL_USERS`). |
| `ACCOUNT_CREATION_ATTEMPTED` | `absence` (fresh dual proof), `creator_token`, `secure_input_method` (exactly `READ_HOST_SECURESTRING_GLOBALALLOCUNICODE`), `creation_surface` (exactly `NETAPI32_NETUSERADD_LEVEL1`), `options`. Sets attempted true before marshal/dispatch. |
| `ACCOUNT_CREATED` | `net_status` (0), `creation_return_confirmed` (true), `password_buffer_zero_freed` (true), `securestring_disposed` (true). Sets created true after confirmed success/cleanup; ambiguity stops instead. |
| `ACCOUNT_SID_READ_BACK` | `account`. Sets readback true only after all account/SID checks. |
| `USERS_BASELINE_SELECTED` | `branch` (`ALREADY_USERS` or `ADD_USERS`), `direct_view`, `users_identity`. Exactly once after SID readback, before any assignment. |
| `USERS_ASSIGNMENT_ATTEMPTED` | `group_sid`, `member_sid`, `creator_token`, `direct_view` (empty), `users_identity`; only for `ADD_USERS`. Sets attempted true before dispatch. |
| `USERS_ASSIGNMENT_CONFIRMED` | `group_sid`, `member_sid`, `net_status` (0), `direct_view` (exactly Users), `identity_continuity_passed` (true). Sets confirmed true only after successful return/readback. |
| `QUALIFICATION_OBSERVED` | `account`, `direct_view`, `indirect_view`, `relevant_edges`, `effective_groups`, `rights`, `candidate_token`, `collection_method`, `performance_log_users`. Records successfully collected observations, not their acceptance. |
| `GROUPS_QUALIFIED` | `observation_sha256`, `direct_baseline_passed`, `indirect_review_passed`, `special_authority_review_passed`, `privileges_review_passed`; all true to set groups qualified. |
| `TOKEN_QUALIFIED` | `observation_sha256`, `token_gate_passed`, `enabled_recheck_passed`, `identity_continuity_passed`; all true to set token qualified. |
| `STOP` | `last_confirmed_sequence`, `reason`, `api_name`, `net_status` (unsigned integer or null when no return), `parameter_error_index` (meaningful documented index or null); terminal failure/block/uncertainty only. |

The closed nested objects are:

- `absence`: `{getinfo_level, getinfo_status, enum_level, enum_filter,
  enum_terminal_status, enum_pages, exact_name_match_count, result}`.
  Required pass values are 1, 2221, 0, 0, 0, a complete page list, 0, and
  `DEFINITE_NOT_FOUND` respectively. Each page is
  `{status, entries_read, total_entries_hint, resume_progress}`.
- `options`: `{name, level, privilege, flags, home_dir, comment, script_path,
  password_age_initialization, defaults_contract}`: exact frozen values from
  the NetUserAdd table, with `defaults_contract=NETUSERADD_LEVEL1_DOCUMENTED`.
  There is no password/pointer field.
- `account`: `{name, sid, enabled, privilege, flags, machine_domain_sid,
  comment, full_name, account_expires, defaults_readback_passed,
  bidirectional_mapping_passed}`. Absent full name is normalized to null;
  account_expires is `TIMEQ_FOREVER` for the required default.
- `direct_view` and `indirect_view`: `{flags, level, status, entries_read,
  total_entries, groups}`. Flags are respectively 0 and 1; level/status are 0.
  Groups contain `{sid, name}`; complete counts and no duplicates are required.
- `performance_log_users`: `{classification, effective, direct_assignment,
  interactive_enabled, host_edge_present, alternate_path_present,
  provenance_passed}`. Classification is exactly
  `CONDITIONALLY_ACCEPTED_HOST_DYNAMIC_BASELINE`. Effective presence may pass
  only with direct_assignment=false, interactive_enabled=true,
  host_edge_present=true, alternate_path_present=false, provenance_passed=true,
  and all independent forbidden-group/privilege gates passed.

`STOP` closes the chain; there is no success successor or effect resumption.
A status code may be retained even when its overall outcome is conservatively
uncertain. No creation return carries a SID; only the readback event can do so.

Both token objects have exactly `user_sid`, `token_type`, `elevated`,
`elevation_type`, `administrators_present`, `administrators_enabled`,
`administrators_deny_only`, `thread_token_absent`, `groups`, and `privileges`.
Groups contain `{sid, name, attributes, classification}`; privileges contain
`{name, attributes, enabled, enabled_by_default, removed, disposition}`.
Directory-view groups contain `{sid, name}`;
relevant edges contain `{member_sid, group_sid, origin}`; effective groups
contain `{sid, name, attributes, origin, disposition}`; rights contain
`{principal_sid, name, origin, disposition}`. Preserve `enum_pages` in query
order. Sort group, membership-edge, privilege, and rights collections by the
ordinal tuple of their identifying fields; reject duplicates. Never reorder
events or enumeration pages by their contents. Classification is one of
`BASELINE`, `HOST_DYNAMIC_BASELINE`, `NORMAL_LOGON`, `INTEGRITY`, `SPECIAL`,
`UNKNOWN`; disposition is
`ACCEPTED`, `REJECTED`, or `UNRESOLVED`; origin is `DIRECT`, `NESTED`, or
`LOGON_CONTEXT`. Empty observations are never an implicit successful review.

Unknown fields, duplicate keys, malformed records, gaps, extra root entries,
broken hashes, state regression, or conflicting identities block loading.
Hash links detect inconsistency; they do not authenticate an adversarial
Administrator who can rewrite the whole chain. No password, password-derived
material, password hash, SecureString contents, credential, token handle, raw
token buffer, or production secret is a schema member.

## One-way failure and uncertainty retention

Before creation, any gate failure prevents its dependent prompt or mutation.
Creation attempt publication is confirmed **before NetUserAdd**, and conditional
Users-assignment attempt publication is confirmed **before NetLocalGroupAddMembers**.
If either write, flush, close, reload, schema check or identity-continuity check
fails, that effect does not run. An existing durable attempt is never permission
for a later process to resume it.

Once either effect may have begun, its attempt is consumed. Use the exact
NetUserAdd classification above: success means retain the account, UserExists
means collision/STOP/no adoption, every other non-success is uncertain for
retention. A conditional Users-add non-success or ambiguous result also stops
without retry. Do not infer absence or qualification from an error.

After a possibly begun effect, retention failure is `UNCERTAIN` with
`effect_may_have_occurred=true`. Preserve the last confirmed record and any
partial file. No recursive best-effort recording, replacement evidence,
rollback, repair, repeat call, account/group cleanup, or manufactured success.
A successful create with ambiguous identity/readback is also a STOP. Only
read-only reconciliation is permitted; it cannot reopen the consumed ceremony.

Retain any possibly created account, any profile created by the separately
approved logon, and all evidence. No password reset, rename, enable/disable,
delete/recreate, alternate name, group removal or repair follows a failure.
The one conditional Users add belongs only to the successful preapproved
construction branch, never failure recovery. Even successful qualification
authorizes no cleanup. Any later state resolution or cleanup requires a new
review and explicit authorization identifying exact host/name/Windows SID.

## Separate source-only helper checkpoint

After this document's GitHub acceptance, the next milestone is **SOURCE-ONLY
helper implementation/review, with all account/group effects disabled**.
Do not create that source in this documentation checkpoint.

The bounded source task must implement and review:

- SecureString input lifetime, final unmanaged marshal, and zeroing free;
- exact local NetUserAdd and its status/retention classification;
- NetUserGetInfo/NetUserEnum, full resume handling and dual absence;
- safe structure/buffer/SID decoding and bidirectional host/name/SID mapping;
- direct/indirect NetUserGetLocalGroups and the one conditional
  NetLocalGroupAddMembers branch with the exact new SID;
- genuine-process token/group/privilege inspection and host-dynamic provenance;
- fixed-root exclusive durable evidence publication, reload/state validation,
  and sanitized status handling.

The helper must expose no arbitrary account, host, group, SID assertion,
password argument, evidence path, retry, cleanup, or caller effect-authority
override. Its default/source gates must keep account/group effects unreachable;
ordinary invocation and tests cannot prompt for a password or cross either
mutation boundary. No New-LocalUser/private-SAM fallback or rollback binding.

Use fake native results and temporary test evidence to verify collision,
pagination, marshal cleanup, pre-effect retention failure, post-effect
uncertainty, both Users branches, wrong identities, forbidden memberships,
unproven Performance Log Users provenance, baseline versus dangerous privileges,
and continued disabled-effect gates. Run only focused tests/checks under the
separate source task's exact checkpoint/file authorization. Every controlled
Windows pytest invocation must use a fresh external
`--basetemp F:\AI\temp\pytest\<fresh-name>` and normally `-p no:cacheprovider`.
No pytest is needed or run for this document.

Helper implementation is not effect authorization. After exact source review,
focused verification and authoritative GitHub acceptance, stop with effects
disabled. Only then may a separate request seek explicit one-time account
creation, conditional Users assignment, evidence creation, and genuine logon
approval. Source SID freeze in the KSP harness remains a later checkpoint.

## Filesystem, source-freeze, and effect exclusions

The account ceremony grants no access to:

```text
F:\AITradingBot\Authority
F:\AITradingBot\Paper
F:\AITradingBot\.Paper.provisioning-v1
F:\AITradingBot\runtime
Credential Manager trading secrets
production private material
```

Do not open production secrets/content as a qualification test. Do not alter
`F:\AI`, retained-evidence ACLs, production ACLs, KSP ACLs, or key properties.
Later Python/source/disposable-harness read/execute/publication access is a
separate checkpoint. Account qualification does not authorize any KSP phase,
including native `READ_ONLY_PREFLIGHT`.

Stop before changing the source values:

```text
ORDINARY_NONADMIN_TEST_SID=None
ORDINARY_NONADMIN_TEST_IDENTITY_BLOCKED=True
ORDINARY_NONADMIN_SELECTION_REQUIRES_REVIEW=True
_NATIVE_EFFECT_EXECUTION_AUTHORIZED=False
_NATIVE_EFFECT_AUTHORIZATION_ID=NOT-AUTHORIZED-IN-800CA51-HARNESS
```

Only separately authorized execution, retained exact SID readback, complete
group/token qualification, and ChatGPT evidence acceptance can precede a
separately authorized source freeze. That later source checkpoint still leaves
native execution disabled.

All current prohibitions remain:

```text
WINDOWS_ACCOUNT_CREATION=NOT_AUTHORIZED
WINDOWS_ACCOUNT_MUTATION=NOT_AUTHORIZED
WINDOWS_GROUP_MUTATION=NOT_AUTHORIZED
PASSWORD_PROMPT=NOT_AUTHORIZED
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

## Documentation verification and publication

Only this existing untracked Markdown document is changed. No account/password/
group/logon/evidence-root effect occurs; no KSP, production, provider, recovery,
or P4 operation runs. Historical read-only inspection is not ceremony execution.
The corrected document resolves the reviewed procedure-design blockers without
claiming an implemented helper or an execution-ready ceremony.

Run `git diff --check`, validate Markdown fences/local links, and check untracked
file whitespace directly. No pytest, broad suite, password prompt or account/
group API effect. Before staging require exactly the authorized untracked path
and no tracked modifications:

```powershell
git status --short
git diff --check
git diff --name-only
git diff --cached --name-only
```

The docs task expressly authorizes the following only after its document/scope
gates pass; check each exit status before the next dependent action:

```powershell
git add -- docs/validation/p3-r1-ordinary-nonadmin-test-principal-creation-ceremony.md
git diff --cached --check
git diff --cached --name-only
git diff --cached --stat
```

Require exactly the one authorized file. Never `git add .` or `git add -A`.
Re-prove worktree/branch/starting HEAD/tree and require the remote branch has not
diverged. No other active worktree may be touched. Then:

```powershell
git commit -m "docs: define P3-R1 test-user creation ceremony"
git push origin feature/p3-r1-recovery-implementation
git rev-parse HEAD
git show -s --format=%T HEAD
git status --short
```

Only an ordinary fast-forward push is authorized. On rejection or remote
divergence STOP; do not pull, merge, rebase, force-push, reset, amend, switch,
clean or otherwise repair Git state. Report exact commit/tree, push result and
final status. No accepted source/document or unrelated artifact may change.

Next: ChatGPT reviews this exact GitHub docs checkpoint, then scopes the
**source-only disabled helper** checkpoint above. Execution approval, real SID
freeze, KSP enablement, account/group cleanup and production remain separate.
STOP after documentation publication.
