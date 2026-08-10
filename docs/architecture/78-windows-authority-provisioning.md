# Windows authority provisioning

Architecture 78 implements the fixed Windows trust substrate required before
the transactional runtime in [architecture 77](77-windows-transactional-capture-authority.md)
can be considered for production. It does not change the executable fixture,
its UUID5 contracts, or the transactional state machine.

## Module boundaries

The production boundary is split across:

- `trading_bot.runtime.windows_authority`: fixed paths, the immutable bootstrap
  model, strict canonical JSON, typed failures, and the pinned-key registry;
- `trading_bot.runtime.windows_authority_security`: direct Win32 handle,
  final-path, reparse, volume, SID, owner, DACL, and token inspection;
- `trading_bot.runtime.windows_authority_mutex`: deterministic identity and the
  `Global\` named mutex;
- `trading_bot.runtime.windows_authority_provisioning`: administrator-only
  validation and idempotent installation; and
- `trading_bot.cli.windows_authority`: the explicit `validate` and `provision`
  command surface.

All native entry points check the platform before loading a Windows DLL. A
non-Windows call fails with `UnsupportedWindowsPlatformError`.

## Fixed deployment

The root and targets are code-owned and cannot be selected by environment,
current directory, registry, database, bootstrap, or CLI input:

```text
F:\AITradingBot\Authority\
  authority.bootstrap.json
  authority.bootstrap.sig
  authority.sqlite3
  authority.sqlite3-journal
  capture-output\
  backup\
```

Staging paths may supply a bootstrap and detached signature to `provision`,
but their final destinations remain the fixed paths above. Database and
persistent-journal initialization is deliberately deferred; pre-created files
are validated when present. The installed validator opens the existing fixed
database through a `file:///F:/AITradingBot/Authority/authority.sqlite3?mode=ro`
URI, performs a real `sqlite_schema` read and read-only `PRAGMA integrity_check`,
and requires one local main database plus the pre-created persistent journal.
Non-SQLite, truncated, or structurally corrupt database bytes fail closed; no
write-capable fallback or `immutable=1` bypass is used. It does not claim
connection-local PRAGMA state or change it. Every
production SQLite connection must instead use the runtime setup helper before
authority work; that helper explicitly requests and reads back
`foreign_keys=ON`, `journal_mode=PERSIST`, and
`synchronous=FULL`, and fails closed on any mismatch. Neither layer performs
ATTACH, VACUUM, DDL, or automatic migration.

Installed database state is explicit. `NOT_PRESENT` means neither the database
nor persistent journal exists. `PRECREATED_UNINITIALIZED` means the paired
files are structurally valid but the database contains no user/application
schema objects; SQLite-internal objects alone do not make it executable
authority. These are the only database states accepted by Milestone A. Any
incomplete pair, corrupt or truncated database, arbitrary table, metadata-only
database, or complete Architecture-77 fixture is classified as
`INITIALIZED_UNSUPPORTED` and fails closed rather than producing evidence.
Milestone A never reports an initialized database as executable or
identity-bound authority.

The future schema contract may check `metadata_json` only as opaque bytes
together with its exact SHA-256 `metadata_digest`. Architecture 77 does not
define a separate canonical semantic encoding for that JSON beyond this
immutable byte/digest contract, so this release does not invent one or claim
metadata-schema completeness. Milestone A does not reach this initialized-
schema check because it rejects every initialized database.

The pre-existing `F:\AITradingBot` parent component is also opened and checked;
it must be a local NTFS directory with the exact administrator/SYSTEM-only
protected DACL. Provisioning does not create or repair that parent component.

## Bootstrap verification

The accepted bootstrap is one immutable schema-1 object with exactly these
fields: `bootstrap_schema`, `bootstrap_generation`, `machine_authority_id`,
`authority_epoch_id`, `signing_key_id`, `approved_account_sid`,
`database_path`, `output_root`, `provider_id`,
`permitted_provider_operation`, `authority_policy_version`,
`claim_policy_version`, and `database_identity_digest`.

Parsing rejects duplicate keys, unknown/missing fields, non-canonical UTF-8
JSON, alternate numeric forms, unsupported schema/policy versions, wrong fixed
paths, wrong provider operation, and non-canonical IDs/digests. Canonical bytes
are UTF-8 JSON with sorted keys and `,`/`:` separators. The provider fields
must equal `ALPACA_DAILY_SNAPSHOT_DESCRIPTOR` exactly.

The detached signature is exactly 64 bytes of IEEE P1363 `r || s`. Windows
CNG verifies SHA-256 over the exact canonical bytes with a P-256 public key.
DER, alternate curves, alternate hashes, and bootstrap-selected keys are not
accepted. `PRODUCTION_PINNED_BOOTSTRAP_KEYS` is intentionally empty until an
approved production public key, key ID, and trust-anchor record are supplied;
therefore production validation currently fails closed as not provisioned.
Test-only registries may be used by non-production vector tests.

Before the bootstrap is accepted, the administrator workflow resolves the
local `Trading` account through `LookupAccountNameW` and compares its SID to
the signed SID. Display-name comparisons and localized command output are not
security decisions.

Architecture 77 defines the future executable relational authority model,
including `authority_metadata`; it is not an approved Milestone-A production
schema artifact or version contract. Milestone A therefore does not interpret
or bind any initialized schema, even when an `authority_metadata` row appears
to match the verified bootstrap. A future schema milestone must first approve
the exact schema artifact and version/migration contract, constraints and
triggers, immutable metadata rules, and canonical semantic encoding for
metadata before it may reconcile database facts to the signed bootstrap. The
existing `metadata_json` limitation remains: Architecture 77 defines no
canonical semantic encoding, so this milestone does not invent one.

## Security principal and DACL intent

The owner is `BUILTIN\Administrators`; `SYSTEM` and administrators receive full
control. Protected authority objects have inheritance disabled. The `Trading`
ACE is exact and SID-based:

- root: traverse/list/read metadata only;
- bootstrap/signature: read only;
- database/journal: concrete SQLite read/write bytes, append/extend,
  read/write attributes, synchronization and byte-range-lock support;
- `capture-output`: create files/subdirectories and write reviewed artifacts
  below that directory; no authority-root create/delete/rename rights; and
- `backup`: no Trading ACE.

The SQLite rights include the specific `FILE_WRITE_EA` bit required by the
standard Windows SQLite VFS: its read/write database and journal open requests
use `GENERIC_WRITE`, whose `FILE_GENERIC_WRITE` mapping includes that bit.
This concrete grant does not include `DELETE`, `WRITE_DAC`, or `WRITE_OWNER`,
and does not grant authority-root replacement or parent-directory rights. The
implementation does not broaden rights when an acceptance test fails. Every
security decision compares owner SID, protected-DACL state,
ACE type/flags/principal/mask, and unexpected ACEs.

## Final-handle and reparse validation

Fixed objects are opened with `FILE_FLAG_OPEN_REPARSE_POINT` and the expected
directory/file mode. Inspection uses the opened handle to obtain attributes,
the final DOS path, owner, DACL, and volume filesystem. Reparse points,
symbolic links, junctions, mount points, UNC/device substitutions, wrong
object types, final paths outside the exact tree, and non-local/non-NTFS
volumes fail closed. String normalization before opening is not sufficient.

## Global lifecycle mutex

The identity material is the exact sorted-key UTF-8 object from architecture
77:

```json
{"authority_epoch_id":"...","label":"lifecycle-arbiter/v1","launch_reservation_id":"...","machine_authority_id":"..."}
```

Its lowercase SHA-256 digest forms the only object name:

```text
Global\AITradingBot-Lifecycle-v1-<64-lowercase-hex-digest>
```

The prefix is fixed; `Local\`, leases, heartbeats, timeout takeover, and lock
stealing do not exist. Lifecycle mutex ownership is separate from filesystem
authority ownership. The approved owner set is exactly
`BUILTIN\Administrators`, `LOCAL SYSTEM`, or the exact signed/verified
`Trading` SID. Creation selects only the owner compatible with the current
token's SID and approved elevation facts; it never stamps the administrator
owner from a standard Trading process. An existing object is checked for an
approved actual owner and exact DACL before wait; Trading receives only mutex
modify, synchronization, and read-control rights so it can verify that
descriptor without gaining mutation rights.

Windows ownership carries implicit DACL-control authority. Consequently, when
the trusted Trading token creates and owns a lifecycle mutex, the mutex DACL
is not a security boundary against malicious code already executing as that
same token. This is consistent with architecture 77's trusted-Trading-token
assumption. The mutex boundary protects against precreation or substitution
by unapproved principals; this ownership exception does not apply to
filesystem authority objects, which remain administrator-owned.
No alternate object name is attempted.

Successful `WAIT_OBJECT_0` ownership is returned as `OWNED`. `WAIT_ABANDONED`
is returned as `ABANDONED_OWNER`: it proves only that the previous mutex owner
died. It does not prove whether a provider or Windows effect occurred. Recovery
must reconcile architecture-77 durable state and no automatic retry is made.
Handles are released deterministically, and a scope releases only a mutex it
actually owns.

## Provisioning state machine

`validate` requires an already elevated administrator token, resolves the actual
Trading SID, validates the fixed parent chain, opens and inspects the fixed
bootstrap/signature handles, reads the bytes from those same verified handles,
verifies the signature, inspects the remaining fixed objects, and checks the
installed SQLite file/state prerequisites. It does not configure
connection-local PRAGMAs or mutate the tree.

`provision` requires the same token and performs, in order:

1. read staging material and parse it;
2. verify canonical bytes, key pin, signature, fixed paths/policies, and the
   local Trading SID before final-tree mutation;
3. validate the fixed parent/object state and any pre-created database/journal
   with the read-only SQLite format/schema/integrity checks before mutation;
4. accept only the `PRECREATED_UNINITIALIZED` storage state; reject every
   initialized/application schema as `INITIALIZED_UNSUPPORTED` before any
   trust-material mutation. No database identity binding or production schema
   initialization exists in Milestone A;
5. create only the fixed root, `capture-output`, and `backup` directories with
   the reviewed owner/DACL descriptor;
6. install trust material only when absent, under that descriptor, or require
   exact byte identity when already present;
7. validate the resulting fixed objects; and
8. validate the installed SQLite storage state and report sanitized evidence;
   no initialized database identity is reported.

Unexpected existing types, bytes, owner, DACL, or reparse state fail closed;
the command does not repair hostile state. It never creates a production SQL
schema, reads credentials, calls a provider, launches a child, schedules work,
or places an order.

## Acceptance boundary and remaining NO-GO items

Pure tests cover fixed paths, canonical bootstrap rejection, trust-anchor
registry behavior, mutex identity/name, policy masks, and typed failures.
Windows acceptance must be explicitly opted in and must operate against the
administrator-provisioned fixed root. It must exercise both administrator and
Trading perspectives, including SID/DACL/reparse/final-path checks, SQLite
PERSIST/FULL prerequisites, a separate administrator-prepared disposable
SQLite probe with real DML/rollback/locking, destructive-denial cases, and
cross-session `Global\` mutex behavior. The disposable probe is acceptance
evidence only; it is never the fixed production database and is never passed
to installed authority validation.

Production remains NO-GO until the approved P-256 public trust anchor is
provided and the administrator-provisioned database/journal artifact boundary
is accepted. Unattended scheduling, trusted exchange time, Credential Manager,
provider transport, `CreateProcessW`, Job Objects, live trading, and real-money
orders remain outside this milestone.
