# Milestone B production validation boundary

Milestone B production status is **NO-GO** until the separately reviewed
`authority-initializer-release-manifest/v1` and `sqlite-authority/v1` build
manifest are published.  The code therefore fails closed when either input is
absent; test evidence must be supplied explicitly to disposable database
tests.

The production artifact is the packaged
`trading_bot/runtime/schema/windows_transactional_authority_v1.sql`.  Its
exact UTF-8 bytes, SHA-256 identity, and rootpage-free materialized
`schema-manifest/v1` are checked.  The test fixture
`tests/fixtures/transactional_authority_schema.sql` remains unchanged and is
not the production resource.

The initializer contract requires an elevated administrator, the fixed
Architecture-78 tree and signed bootstrap, the real Trading SID, a paired
pre-created database and persistent journal, and
`PRECREATED_UNINITIALIZED`.  It establishes `trusted_schema=OFF`, foreign
keys, `PERSIST`, and `FULL` before `BEGIN EXCLUSIVE`, executes the artifact one
statement at a time, inserts canonical metadata and v1 migration evidence in
the same transaction, commits, closes, reopens read-only, and validates again.
It has no repair, upgrade, downgrade, `ATTACH`, `VACUUM`, or implicit-commit
path.  A post-commit retry is an exact read-only `INITIALIZED_SUPPORTED`
validation; partial, corrupt, foreign, and unsupported states fail closed.

Native acceptance remains required before GO:

1. Validate the exact packaged resource from source and an installed-like
   package, including no BOM, no custom SQL hash function, and stable digest.
2. Validate initializer, runtime, and read-only trusted-schema readback under
   the reviewed SQLite/VFS build.
3. Use a disposable fixed-layout administrator/Trading pair to prove
   `BEGIN EXCLUSIVE` rollback, PERSIST/FULL settings, journal rights, restart,
   reopen, integrity, exact metadata, and migration evidence.
4. Exercise elevated administrator, nonadministrator, active-transaction,
   partial-pair, hostile/reparse, duplicate, tampered, and post-commit retry
   cases without mutating rejected databases.
5. Keep acceptance roots temporary or explicitly opt-in; do not use the fixed
   production root unless the existing native acceptance opt-in selects it.

The reviewed release/build manifest, production trust anchor, Windows SQLite
VFS/locking behavior, NTFS durability, reparse/substitution controls, and
cross-session mutex acceptance remain external blockers.  A custom SQL UDF is
not a blocker or a production dependency.
