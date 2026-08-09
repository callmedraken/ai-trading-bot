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
are validated when present. If both exist, the read-only SQLite validator
requires one local main database, foreign keys enabled, `journal_mode=PERSIST`,
`synchronous=FULL`, and the pre-created journal; it never performs ATTACH,
VACUUM, DDL, or automatic migration.

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

The SQLite rights intentionally do not include `DELETE`, `WRITE_DAC`,
`WRITE_OWNER`, or write-EA rights. The implementation does not broaden rights
when an acceptance test fails. Every security decision compares owner SID,
protected-DACL state, ACE type/flags/principal/mask, and unexpected ACEs.

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
stealing do not exist. Creation/opening supplies an explicit binary security
descriptor for administrators, SYSTEM, and the approved Trading SID. An
existing object is checked for the reviewed owner and exact DACL before wait;
Trading receives only mutex modify, synchronization, and read-control rights
so it can verify that descriptor without gaining mutation rights.
No alternate object name is attempted.

Successful `WAIT_OBJECT_0` ownership is returned as `OWNED`. `WAIT_ABANDONED`
is returned as `ABANDONED_OWNER`: it proves only that the previous mutex owner
died. It does not prove whether a provider or Windows effect occurred. Recovery
must reconcile architecture-77 durable state and no automatic retry is made.
Handles are released deterministically, and a scope releases only a mutex it
actually owns.

## Provisioning state machine

`validate` requires an already elevated administrator token, reads only the
fixed trust material, resolves the actual Trading SID, verifies the signature,
and inspects fixed objects. It does not mutate the tree.

`provision` requires the same token and performs, in order:

1. read staging material and parse it;
2. verify canonical bytes, key pin, signature, fixed paths/policies, and the
   local Trading SID before final-tree mutation;
3. create only the fixed root, `capture-output`, and `backup` directories with
   the reviewed owner/DACL descriptor;
4. install trust material only when absent, under that descriptor, or require
   exact byte identity when already present;
5. validate the resulting fixed objects; and
6. validate the installed state and report sanitized evidence.

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
PERSIST/FULL prerequisites, destructive-denial cases, and cross-session
`Global\` mutex behavior.

Production remains NO-GO until the approved P-256 public trust anchor is
provided and the administrator-provisioned database/journal artifact boundary
is accepted. Unattended scheduling, trusted exchange time, Credential Manager,
provider transport, `CreateProcessW`, Job Objects, live trading, and real-money
orders remain outside this milestone.
