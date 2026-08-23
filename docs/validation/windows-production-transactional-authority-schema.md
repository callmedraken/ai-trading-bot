# Milestone B production validation boundary

Milestone B production status remains **NO-GO** pending native Windows
acceptance and the remaining external gates.  The separately reviewed
`authority-initializer-release-manifest/v1` and `sqlite-authority/v1` build
manifest are published as exact package resources; production loaders fail
closed when either resource is missing, unreadable, or malformed.  Test-only
evidence injection remains available for disposable database tests.

The production artifact is the packaged
`trading_bot/runtime/schema/windows_transactional_authority_v1.sql`.  Its
exact UTF-8 bytes, SHA-256 identity, and rootpage-free materialized
`schema-manifest/v1` are checked.  The Architecture-77 behavioral harness
loads the same packaged resource through the public package boundary; there is
no second full SQL fixture.

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

The production trust anchor v1 is now pinned in source as public-key material
only; its non-exportable private signing material remains external. The published
release/build resources, fixed-tree and production database/journal
initialization and acceptance, Windows SQLite VFS/locking behavior, NTFS
durability, reparse/substitution controls, and cross-session mutex acceptance
remain external blockers. A custom SQL UDF is not a blocker or a production
dependency.
