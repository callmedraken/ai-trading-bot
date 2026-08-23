# Windows authority provisioning validation

This procedure validates the production Windows substrate described by
[architecture 78](../architecture/78-windows-authority-provisioning.md). It
is intentionally separate from the executable transactional-authority fixture
and does not maintain a second authority SQL schema; the production artifact
is owned by the runtime package.

## Safe automated layers

Run the portable unit layer from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests/runtime/test_windows_authority.py -q
.venv\Scripts\ruff.exe check src tests
.venv\Scripts\ruff.exe format --check src tests
```

These tests do not open the production root, use credentials, call Alpaca,
create a production mutex, or mutate Windows security state. They cover
deterministic canonicalization, fixed-path invariance under `TEMP`/`TMP`/`TMPDIR`
and cwd changes, unsupported bootstrap shapes, the exact one-key production
trust-anchor registry, P1363 envelope length, mutex digest/name, exact policy
masks, and mocked acceptance dispatch/evidence semantics.

## Evidence classification matrix

Portable tests must not be read as proof of native Windows acceptance:

| Security claim | Evidence class | Current evidence or gate |
| --- | --- | --- |
| Canonical bootstrap, fixed paths, policy masks, SQLite state rules | 1. Pure deterministic contract | Automated unit tests |
| Win32 argument selection, object kinds, failure cleanup, typed rejection | 2. Mocked Win32 behavior | Automated unit tests |
| Actual local DOS final paths, reparse behavior, NTFS volume, ACLs, SQLite Win32 locking, same-handle trust reads | 3. Real Windows-native integration | Safe disposable integration coverage where available; otherwise acceptance prerequisite |
| Administrator fixed-root facts | 4A. Administrator acceptance | Explicit `administrator` phase below |
| Dedicated Trading allow/deny facts | 4B. Trading acceptance | Explicit `trading` phase under the real Trading account |
| Python SQLite Windows VFS and locking | 4C. SQLite VFS acceptance | Explicit `sqlite-vfs` phase under Trading against a disposable pair |
| Reparse and substitution rejection | 4D. Destructive maintenance acceptance | Separate `reparse` phase and operator procedure |
| Cross-session `Global\\` mutex contention and abandoned-owner recovery | 5. Manual/cross-session acceptance | Separate `cross-session-mutex` gate; never simulated by ordinary pytest |

Classes 1 and 2 establish portable contract and mock sequencing only. They do
not establish the class 3, 4, or 5 claims that require Windows,
administrator-provisioned artifacts, distinct sessions, or dedicated-account
permissions.

## Phase model and opt-in commands

The old one-test administrator run was only a smoke/preflight check. It could
prove that one administrator process reached `validate_installed_authority()`;
it could not prove Trading permissions, SQLite Win32 VFS behavior, reparse
substitution rejection, or cross-session mutex behavior. It must not be called
Milestone A production acceptance.

The acceptance harness requires both the existing global opt-in and one exact
phase selection:

```powershell
$env:AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE = "1"
$env:AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_PHASE = "administrator"
.venv\Scripts\python.exe -m pytest tests/acceptance/test_windows_authority_provisioning_acceptance.py -q
```

The reviewed phase values are:

| Phase value | Evidence identifier | Execution boundary |
| --- | --- | --- |
| `administrator` | `ADMINISTRATOR_FIXED_ROOT` | Elevated administrator session |
| `trading` | `TRADING_ALLOW_DENY` | Dedicated standard `Trading` account/session |
| `sqlite-vfs` | `SQLITE_WINDOWS_VFS` | Dedicated standard `Trading` account/session and disposable DB pair |
| `reparse` | `REPARSE_AND_SUBSTITUTION` | Elevated disposable maintenance session |
| `cross-session-mutex` | `CROSS_SESSION_GLOBAL_MUTEX` | Two independently launched Windows sessions |

Ordinary pytest without the global opt-in skips all five native phase tests.
Opt-in without a phase fails with a clear configuration error. An unknown
phase fails closed. Selecting one phase skips the other phase tests; a PASS
therefore identifies only that phase and never represents complete Milestone A
acceptance.

After each run, clear the selection:

```powershell
Remove-Item Env:AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_PHASE
Remove-Item Env:AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE
Remove-Item Env:AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_MAINTENANCE -ErrorAction SilentlyContinue
```

## Phase A: `ADMINISTRATOR_FIXED_ROOT`

Run from an already elevated administrator PowerShell. The phase does not
self-elevate, request a password, or alter the fixed tree. It proves, through
the existing same-handle validator and a repeated read-only validation:

- elevated administrator token;
- exact `F:\AITradingBot\Authority` root and complete fixed object set;
- administrator owner, protected DACL, no unexpected ACE, no reparse, local
  `F:` NTFS final paths;
- bootstrap and detached signature bytes read from the handles whose final path
  and security policy were inspected;
- valid installed signature/bootstrap acceptance and correct database lifecycle
  evidence;
- repeated validation returns identical evidence without mutation.

The phase also performs disposable in-memory negative material checks for bad
signature, unsupported signing-key ID, wrong Trading SID, wrong fixed path,
wrong provider/operation, and unsupported policy. It never overwrites or
renames installed trust files. Missing fixed artifacts, a trust-anchor mismatch,
or an invalid installed state is a failure/blocker, never PASS.

The administrator run also checks the reserved same-directory trust-material
temporary names
`F:\AITradingBot\Authority\.authority.bootstrap.json.installing` and
`F:\AITradingBot\Authority\.authority.bootstrap.sig.installing` before any
trust-file publication. A present or unexpectedly inaccessible name is a
stale/recovery condition and blocks provisioning; the provisioner never deletes
or reuses it automatically. Under an approved maintenance procedure, an
administrator must inspect the object with the same no-follow/final-path and
security rules, remove only the known stale temporary, and rerun the original
staging validation. A temporary is not production acceptance evidence.

## Phase B: `TRADING_ALLOW_DENY`

Log on to the dedicated standard `Trading` account and launch the command from
that account. Do not provide a password to pytest, place one in an environment
variable, or automate account logon. The phase first compares the current token
SID to the verified signed Trading SID and rejects administrator or elevated
tokens.

It then proves the positive boundary: bootstrap and signature are readable,
the database is readable through Python SQLite, the persistent journal is
present for normal VFS access, and a uniquely named capture-output artifact can
be created and cleaned up.

Before those operations, the harness directly opens and revalidates each
Trading-visible fixed target—root, `capture-output`, database, and journal—
through a no-follow handle, exact final path, object-kind/reparse/volume
checks, and its role-specific security policy. This deliberately does not
open the sealed `F:\AITradingBot` deployment parent, whose ACL is
Administrators/SYSTEM-only and grants Trading no parent-directory rights.
Bootstrap and signature bytes are read from the same inspected target handles.
Path-based existence checks are not used to establish trust for a production
object.

It proves the negative boundary with non-mutating access probes and uniquely
named harmless probes: backup access, arbitrary authority-root creation,
bootstrap/signature replacement capability, database/journal delete and
rename/replace capability, `WRITE_DAC`, and `WRITE_OWNER` are all denied. The
arbitrary authority-root creation probe uses a direct native `CreateFileW`
`CREATE_NEW` attempt; only native `ERROR_ACCESS_DENIED` is the expected denial.
A probe is recorded as denied only for the expected Windows access-denied
result; an unrelated setup or operating-system error is blocked/failing
evidence.

## Phase C: `SQLITE_WINDOWS_VFS`

Run under the standard `Trading` account only after an administrator has
prepared a separate acceptance-only disposable database/journal pair and its
fixed probe table. This pair must not be the production
`F:\AITradingBot\Authority\authority.sqlite3`/journal pair, and it is never
passed to `validate_installed_authority()`. The reviewed setup location is:

```text
F:\AITradingBot\AuthorityAcceptance\SQLiteVfs\authority-vfs.sqlite3
F:\AITradingBot\AuthorityAcceptance\SQLiteVfs\authority-vfs.sqlite3-journal
table: windows_authority_acceptance_probe
```

An administrator must create the disposable directory, database, persistent
journal, and exactly that harmless probe table before the Trading run. The
table is an acceptance harness prerequisite, not production schema
initialization; the Trading test never issues `CREATE TABLE`, migration, or
other DDL. The administrator-prepared table has exactly this shape and no
rows:

```sql
CREATE TABLE windows_authority_acceptance_probe (
    probe_id INTEGER PRIMARY KEY,
    marker TEXT NOT NULL
);
```

The administrator must leave the persistent journal file present and
zero-length before the run, grant the standard Trading account the reviewed
SQLite read/write/locking rights for this pair, and keep the pair outside the
fixed production authority tree. Missing files, the table, or required ACLs
are `BLOCKED` and cannot produce a PASS. Set the maintenance gate before
running because this phase requests connection-local durability settings and
exercises write locking:

```powershell
$env:AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE = "1"
$env:AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_PHASE = "sqlite-vfs"
$env:AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_MAINTENANCE = "1"
.venv\Scripts\python.exe -m pytest tests/acceptance/test_windows_authority_provisioning_acceptance.py -q
```

The phase proves ordinary Python `sqlite3` read/write opening, the reviewed
`configure_and_validate_authority_sqlite_connection()` helper, `foreign_keys`
`ON`, `journal_mode` `PERSIST`, `synchronous` `FULL`, and a real harmless
`INSERT` into the pre-created probe table. The inserted marker must be visible
inside the transaction, the journal must be written, a second connection must
observe real `BEGIN IMMEDIATE` contention, and rollback must make the marker
absent. The test then reacquires the lock, repeats the write/rollback,
reopens the database, and proves both the marker and the probe table state
remain uncommitted. The phase creates no schema, performs no migration,
attaches no database, vacuums nothing, never calls the installed authority
validator, and leaves no semantic acceptance data.

## Phase D: `REPARSE_AND_SUBSTITUTION`

This phase is an explicit elevated maintenance gate. It operates only in the
acceptance-only root
`F:\AITradingBot\AuthorityAcceptance\Reparse`; it never opens, repairs,
deletes, or validates an object below
`F:\AITradingBot\Authority`. The acceptance root is deliberately outside the
production fixed-path contract and is not passed to
`validate_installed_authority()` or any installed authority validator.

Run the executable procedure from an elevated Administrator PowerShell. The
`AuthorityAcceptance` parent must already exist, and the exact `Reparse`
directory must not exist. A present directory, file, link, junction, or other
ambiguous object is stale state and blocks; the harness does not recursively
delete or repair it.

```powershell
$env:AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE = "1"
$env:AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_PHASE = "reparse"
$env:AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_MAINTENANCE = "1"
$acceptanceBase = Join-Path $env:TEMP "ai-trading-bot-windows-authority-reparse-basetemp"
.venv\Scripts\python.exe -m pytest tests/acceptance/test_windows_authority_provisioning_acceptance.py -q --basetemp $acceptanceBase
```

Before creating `Reparse`, the phase directly opens the existing exact
`F:\AITradingBot\AuthorityAcceptance` parent with a no-follow native directory
handle and validates that handle with the reviewed final-path, object-kind,
reparse, local-`F:`, and NTFS checks. After `Reparse` is created, it is
immediately reopened through the same no-follow native directory path and
validated before any scenario directory, file, or link is created. Any native
open or inspection failure, final-path mismatch, reparse, wrong type, wrong
volume, or wrong filesystem is `BLOCKED`; neither object is repaired or
silently removed.

After both parent and root validation pass, the phase creates and removes one
fresh scenario directory at a time. Each candidate is opened directly with
native `CreateFileW` and `FILE_FLAG_OPEN_REPARSE_POINT`, and the opened handle
is passed to the reviewed `inspect_open_authority_object()` validator. The
scenario set is:

- `symbolic-link-substitution`;
- `directory-junction-reparse-substitution`;
- `mount-point-reparse-substitution` using the native
  `IO_REPARSE_TAG_MOUNT_POINT` directory-reparse form;
- `wrong-final-path-substitution`;
- `unc-substitution` through the local administrative share, where available;
- `device-substitution` using the harmless `\\.\NUL` candidate;
- `wrong-object-kind`; and
- `wrong-security`.

The harmless `\\.\NUL` device candidate is expected to open successfully with
the acceptance-native helper. On the reviewed Windows path, the subsequent
`inspect_open_authority_object()` call fails closed at
`GetFinalPathNameByHandleW` with typed `WindowsNativeError` error code `87`
(`ERROR_INVALID_PARAMETER`). Only that exact operation/error-code pair is
device-substitution rejection evidence. A CreateFileW failure, a different
native operation, or any other Win32 error remains `BLOCKED`; the generic
scenario matchers are not broadened.

The harness also runs an ordinary clean non-reparse control object. Its
successful inspection is control evidence only; it cannot satisfy any hostile
scenario. A hostile scenario is `PASS` only when inspection rejects for its
expected final-path, reparse, object-kind, security, or non-local reason. An
unexpected successful acceptance is a hard test failure. A missing privilege,
unsupported filesystem/reparse operation, unavailable administrative share,
or unrelated native error is `BLOCKED`, never `PASS`. The phase emits `PASS`
only after every listed hostile scenario and the clean control have completed.

Cleanup is deterministic and non-recursive. The harness removes only files,
links, directories, and scenario roots it created, then removes the empty
acceptance root it created. Cleanup failure is `BLOCKED`; leave the reported
acceptance state for administrator inspection and remove only known
scenario-owned objects after confirming that no production path is involved.
Evidence retains only sanitized scenario names and `PASS`/`BLOCKED` status; it
does not retain native exception text, security descriptors, credentials, or
environment data.

After the run, clear the maintenance gate and phase selection:

```powershell
Remove-Item Env:AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_PHASE
Remove-Item Env:AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE
Remove-Item Env:AI_TRADING_BOT_WINDOWS_AUTHORITY_ACCEPTANCE_MAINTENANCE
```

## Phase E: `CROSS_SESSION_GLOBAL_MUTEX`

This phase remains a separate manual gate. The pytest harness always reports it
as blocked because one process or one interactive session cannot establish
cross-session evidence. Launch two approved processes in distinct Windows
sessions with the same machine authority, epoch, and reservation. Retain only
the sanitized mutex digest/name and phase result. Verify the exact same
`Global\\AITradingBot-Lifecycle-v1-<digest>` name, second-process contention,
release and reacquisition, hostile descriptor rejection, no `Local\\` fallback,
and `ABANDONED_OWNER` after terminating the owner. Recovery must reconcile
durable state and must not retry an external effect automatically.

## Sanitized evidence and production checklist

Each green phase emits one record with only:

- `phase_id` and `status`;
- the fixed command, account classification, and safe scenario names;
- bootstrap digest, database lifecycle state, and Trading SID where applicable.

Evidence must never retain passwords, tokens, private keys, environment dumps,
raw security descriptors, credentials, provider data, or arbitrary exception
text. A phase record is partial evidence. Production acceptance is a
collection/checklist containing separate PASS records for every required phase,
including the separately obtained cross-session record; it is not a pytest
exit code and no individual result is named complete Milestone A acceptance.

Trust-file publication is crash-consistent per file, not a two-file
transaction. The publisher writes and flushes a reserved temporary while
holding its handle, validates that same object, then uses a no-replace
handle-based rename into the absent fixed destination and reopens the final
path. A process failure or power loss can therefore leave a stale temporary,
one published final and one absent final, or neither final; it cannot
intentionally expose a final trust file while it is being written. Stale
temporary state requires explicit administrator recovery. The contract makes
no directory-entry persistence claim across abrupt power loss, and no native
power-loss test is inferred from ordinary pytest.

## Current limitations and NO-GO gates

Production remains NO-GO until all of the following are separately satisfied:

- the fixed parent, root, bootstrap/signature, database, and journal are
  administrator provisioned and accepted;
- the Trading allow/deny phase runs under the real standard account;
- the SQLite Windows VFS/locking phase succeeds against its disposable pair;
- reparse/substitution evidence is obtained in a disposable maintenance window;
- cross-session `Global\\` mutex evidence is obtained from distinct sessions.

The approved production trust anchor v1 is pinned in source as public-key
material only; the non-exportable private signing material remains external.
Production database/journal initialization and acceptance, approved
release/build material, and the native Windows gates above remain separately
required. Migrations, unattended scheduling, Credential Manager, provider
transport, child process orchestration, live trading, and real-money orders
remain outside this milestone. Architecture 77 and its fixture remain unchanged.
