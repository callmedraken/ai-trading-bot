# Windows authority provisioning validation

This procedure validates the production Windows substrate described by
[architecture 78](../architecture/78-windows-authority-provisioning.md). It
is intentionally separate from the executable transactional-authority fixture
and does not modify `tests/fixtures/transactional_authority_schema.sql`.

## Safe automated layers

Run the portable unit layer from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests/runtime/test_windows_authority.py -q
.venv\Scripts\ruff.exe check src tests
.venv\Scripts\ruff.exe format --check src tests
```

These tests do not open the production root, use credentials, call Alpaca,
create a mutex, or mutate Windows security state. They cover deterministic
canonicalization, fixed-path invariance under `TEMP`/`TMP`/`TMPDIR` and cwd
changes, unsupported bootstrap shapes, the empty production trust-anchor
registry, P1363 envelope length, mutex digest/name, and exact policy masks.

## Opt-in administrator acceptance

The destructive acceptance suite is not run by ordinary pytest. Run it only
after the machine has an approved maintenance window and a disposable
administrator-provisioned authority tree:

```powershell
$env:AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE = "1"
.venv\Scripts\python.exe -m pytest tests/acceptance/test_windows_authority_provisioning_acceptance.py -q
Remove-Item Env:AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE
```

Without the opt-in variable, the test is a clear skip. With it, missing
Windows, missing fixed root, absent trust material, or absent pre-created
database/journal is a failure/blocked prerequisite, never a simulated pass.
The suite must record sanitized evidence only.

Administrator perspective must prove: elevated token; owner and protected
DACL; no unexpected ACE; no reparse point; exact final local `F:` path; NTFS
volume; exact fixed bootstrap/signature bytes; wrong key ID/bad signature/wrong
SID/path/provider/policy rejection; and idempotence without automatic repair.

Dedicated `Trading` perspective must prove the account is not an administrator,
can read bootstrap/signature, can perform the reviewed DB/journal read/write
and locking operations (including the specific `FILE_WRITE_EA` bit required by
Windows `FILE_GENERIC_WRITE` when the standard SQLite Win32 VFS opens those
handles with `GENERIC_WRITE`), can create expected capture output, and cannot access
backup, create at the authority root, delete/rename/replace DB or journal,
change owner/DACL, or replace trust material. Tests use a disposable
administrator-provisioned database with `foreign_keys=ON`, `journal_mode=PERSIST`,
and `synchronous=FULL`; the production connection setup helper must request
and verify those values on every opened authority connection. The read-only
installed validator opens the fixed database with an explicit `mode=ro` URI,
performs a real `sqlite_schema` read, and checks the fixed database/journal
prerequisites without silently configuring connection-local PRAGMAs. It must
reject arbitrary, truncated, or corrupt database bytes. Tests do not attach,
vacuum, migrate, or promote the test-only SQL fixture.

The path matrix creates junction/symbolic-link/mount substitutions only when
administrator privileges are available. Each must be rejected from the final
opened handle; a test that cannot construct the substitution is reported as a
prerequisite skip, not converted into a weaker assertion.

## Cross-session mutex procedure

Launch two independently spawned approved workers under distinct Windows
sessions/accounts with the same machine, epoch, and reservation. Each must
derive the same `Global\AITradingBot-Lifecycle-v1-<digest>` name and the second
must remain outside the critical section until the first releases it. Repeat
with a hostile existing object/DACL and verify fail-closed startup. Verify no
`Local\` name is attempted. Terminate the owner while holding the mutex and
record `ABANDONED_OWNER`; the recovery process must reconcile durable state and
must not retry the external effect automatically.

The lifecycle mutex owner must be one of BUILTIN\\Administrators, LOCAL
SYSTEM, or the exact Trading SID. A Trading-created mutex is accepted with
Trading as its owner; an unapproved owner or any expanded DACL remains a
fail-closed result. This owner exception is limited to the kernel mutex and
does not change the administrator ownership requirement for filesystem
authority objects.

If distinct-session automation is unavailable inside pytest, run the manual
procedure above and retain only command lines, account/session labels, mutex
state, digest/name, and pass/fail classification. Do not retain credentials,
tokens, environment dumps, raw security descriptors, provider bodies, or
arbitrary exception text.

## Evidence and limitations

The command emits sanitized JSON containing only state, fixed root, bootstrap
digest, signing-key ID, Trading SID, inspected object roles, and DB/journal
presence. Production validation currently fails closed because no approved
production P-256 public key/key-ID record exists in the repository. This is a
Milestone A acceptance blocker, not a test pass. Database initialization and
unattended scheduling remain later milestones.
