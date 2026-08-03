# Windows transactional capture authority validation plan

This plan validates the normalized test-only authority described in
`docs/architecture/77-windows-transactional-capture-authority.md`. The
executable fixture is
`tests/fixtures/transactional_authority_schema.sql`; the focused harness is
`tests/runtime/test_windows_transactional_capture_authority.py`.

This milestone does not implement production capture, credentials, provider
transport, Windows provisioning, scheduling, brokerage access, or real-money
trading. All external effects are fake hooks or database observations.

## 1. Evidence rules

Every schema/transaction test must:

- use a temporary local SQLite database with `PRAGMA foreign_keys=ON`;
- execute the complete fixture before inserting authority facts;
- use `BEGIN IMMEDIATE` for write workflows;
- use fixed semantic timestamps and explicit canonical bytes in deterministic
  test data; timestamps are facts and never UUID5 inputs;
- compare exact canonical bytes and SHA-256 digests where evidence is stored;
- preserve the database after rollback/crash-style assertions for inspection;
- report sanitized SQLite version, integrity results, and failure class; and
- never use credentials, real provider calls, brokerage APIs, or real-money
  orders.

The fixture and tests must not discover a schema by scanning a directory or
accept a legacy JSON claim as authority. Paths are test transport inputs only;
they are not deterministic identity inputs.

The trusted `Trading` account assumption is explicit. Tests cover accidental
duplicates, cooperating approved processes, foreign-key integrity, and
transaction ordering. They do not claim to authenticate executables or defend
against malicious direct SQL by code already controlling the trusted token.

## 2. Enforcement acceptance split

The validation review must classify each assertion before accepting it:

| SQLite fixture proves | Reviewed transaction harness proves |
| --- | --- |
| Immediate-parent foreign keys and `PRAGMA foreign_key_check` | Multi-statement workflow ordering |
| Append-only evidence, immutable rows, and prohibited deletes | Canonical request/digest and policy reconciliation |
| Unique one-to-one claim/reservation/execution/terminal/selection fences | Action-specific recovery policy and operator evidence |
| Per-session uniqueness and trigger-owned ordinal increments | Commit-before-side-effect boundaries |
| Monotonic local state transitions and local absorbing fences | Complete atomicity of state plus evidence updates |
| Typed recovery target existence and same-session lineage | Cross-table semantic checks that do not need copied ancestor columns |
| Fixed enums, budget, digest lengths, and typed success facts | UUID5 computation and exact material contract |

The review rejects any document or test claim that SQLite authenticates an
executable, verifies Windows CNG/ACL state, validates a provider response, or
protects against compromised trusted-token code. Complex triggers are not
added for that excluded threat.

## 3. Schema execution gates

The first gate runs the complete DDL with foreign keys enabled and asserts:

1. all ten intended tables are present:
   `authority_metadata`, `schema_migrations`, `sessions`, `attempts`,
   `provider_call_claims`, `launch_reservations`, `launch_executions`,
   `terminals`, `session_selections`, and `manual_recoveries`;
2. every foreign key points to a primary key or unique parent key, with the
   immediate-parent chain:

   ```text
   authority_metadata -> sessions -> attempts -> provider_call_claims
       -> launch_reservations -> launch_executions
       -> launch_reservations -> terminals
   ```

   and direct boundary references from migrations, selections, and recoveries;
3. `PRAGMA foreign_key_check` returns no rows after the valid lifecycle;
4. `PRAGMA integrity_check` returns `ok`; and
5. no prohibited copied ancestor identity columns exist:

   | Table | Allowed parent identity | Forbidden copied identities |
   | --- | --- | --- |
   | `provider_call_claims` | `attempt_id` | epoch, session, ordinal, allocation, copied claim parent |
   | `launch_reservations` | `claim_id` | epoch, session, attempt, allocation |
   | `launch_executions` | `launch_reservation_id` | epoch, session, attempt, claim |
   | `terminals` | `launch_reservation_id` | epoch, session, attempt, claim, execution |
   | `session_selections` | session and terminal | copied claim/attempt/epoch ancestry |
   | `manual_recoveries` | session plus typed target | five nullable target ancestor columns |

The review must not reintroduce a separate allocation table, allocation
identity, large composite lineage foreign key, or redundant ancestor column.

## 4. Deterministic identity gates

The test harness uses the fixed namespace
`7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012` and the exact UTF-8 length framing:

```text
LF(s) = ASCII(decimal UTF-8 byte length) + ":" + s
```

It verifies the root request tuple and the exact normalized tuples for:

```text
migration_id/v1
attempt_id/v2
claim_id/v2
launch_reservation_id/v2
launch_execution_id/v2
terminal_id/v2
selection_id/v2
recovery_id/v2
```

The fixed migration vector remains:

```text
authority_epoch_id       = 12345678-1234-5678-9abc-def012345678
schema_version           = 3
migration_policy_version = migration-policy/v1
framed UTF-8 preimage    = 15:migration_id/v136:12345678-1234-5678-9abc-def0123456781:319:migration-policy/v1
migration_id             = b1114fec-2247-506d-bfda-74008355b312
```

The normalized derived vectors are asserted as independent golden outputs:

| Identity | Expected value |
| --- | --- |
| `session_id` | `e5179727-d0f1-5eac-8c01-2e2105a1a9c1` |
| `attempt_id` | `be483fa1-abe3-5721-90bc-84868cf3dd19` |
| `claim_id` | `6ec45116-d8a8-50ea-8d94-7ac47329c7e9` |
| `launch_reservation_id` | `222adedb-e4e7-5bbc-acc2-e7022a1785ac` |
| `launch_execution_id` | `4ce95417-de13-569f-923b-e17d2d9854c6` |
| `terminal_id` | `5fda0305-878a-550f-b724-a7ce775e6a30` |
| `selection_id` | `77b12359-7413-536c-a03c-d6604588aee1` |
| `recovery_id` | `40eff555-9402-598d-868c-e0ad8776249e` |

The review perturbs clocks, UUID4 values, Python hash seeds, object identity,
working directories, path spellings, environment values, process IDs, and
serialized evidence bytes. None may change an identity unless a semantic tuple
field changes. Changing the immediate parent or required semantic policy must
change the derived identity. Administrator-provisioned machine/epoch/key IDs
are classified as signed facts, not runtime UUID5 values.

## 5. Lifecycle and parent-fence gates

The valid path is one transaction helper at each boundary:

```text
metadata + migration
  -> session
  -> attempt ordinal 0
  -> permanent claim
  -> launch reservation
  -> launch execution (optional)
  -> successful terminal
  -> owning session selection
```

The focused suite asserts:

- metadata and migration insert successfully and remain immutable;
- session counters start at zero;
- attempt zero consumes exactly one ordinal;
- one claim can reference an attempt and remains `COMMITTED` permanently;
- one reservation can reference a claim;
- one execution can reference a reservation;
- one terminal can reference a reservation, including a process-creation
  failure with no execution row; and
- one confirmed successful terminal can be selected only by its owning session.

The following duplicate operations must fail without a second side effect:

- a second claim for one attempt;
- a second reservation for one claim;
- a second execution for one reservation;
- a second terminal for one reservation;
- a second selection for one session; and
- selecting one terminal for two sessions.

The suite also attempts updates and deletes against immutable evidence. The
trigger or foreign-key result must preserve the original row and must not
create a repair path.

## 6. Lineage gates

Selection uses one executable trigger to resolve:

```text
terminal -> launch_reservation -> claim -> attempt -> session
```

The test attempts to select another session's successful terminal and expects
an immediate failure.

Recovery uses one `target_kind`/`target_id` pair. For each supported target
kind (`SESSION`, `ATTEMPT`, `CLAIM`, `LAUNCH_RESERVATION`, `TERMINAL`), the
suite attempts to recover another session's target and expects failure. No
large mismatched composite tuple is constructed because the normalized schema
has no such tuple.

The review also verifies that a recovery cannot be inserted for
`SUCCESS_SELECTED` or `CLOSED`, cannot reopen a claim/reservation, cannot
delete evidence, and cannot authorize another provider call.

## 7. Attempt ordinal and crash gates

The attempt primitive is tested under immediate SQLite row-trigger semantics:

- two independent connections racing on one open session commit ordinals 0
  and 1 without duplication;
- stale ordinal 0 after allocation and future ordinal 2 fail;
- direct, no-op, regression, skip, and second counter updates fail;
- inserting an attempt and rolling back restores both the original counter and
  absence of the row;
- committing preserves the attempt and exact increment;
- the application helper performs one insert and no independent counter
  update; and
- two separate sessions each begin at ordinal zero.

The counter proof depends only on immutable attempts and contiguous committed
per-session ordinals. It does not use an application-maintained trigger flag,
deferred trigger, clock, or alternate ordinal search.

## 8. Recovery ordinal and crash gates

Recovery is tested with the same single-insert pattern:

- two independent connections racing recoveries on one open session commit
  consecutive ordinals 0 and 1;
- stale, future, duplicate, no-op, and invalid target ordinals fail;
- direct recovery-counter updates fail;
- rollback preserves row, counter, and target-state atomicity;
- commit preserves the immutable recovery row, increment, and authorized
  target state together;
- recovery rows cannot be updated or deleted;
- each independent session begins recovery at ordinal zero; and
- recovery after a successful selection or closed session fails.

The trigger verifies open-session eligibility, target existence, same-session
lineage, current ordinal, and non-empty predecessor/resulting state. The test
transaction service additionally verifies action-specific authorization and
performs any target-state update in the same `BEGIN IMMEDIATE` transaction.

## 9. Transaction boundary gates

`FakeSideEffects` observes the database through an independent connection.
The test proves the following event order:

| Commit/effect boundary | Required evidence |
| --- | --- |
| Claim commit -> credential/provider construction | The observer sees `COMMITTED` before the fake provider hook runs |
| Reservation commit -> process creation | The observer sees `COMMITTED` before the fake process hook runs |
| Launch evidence commit -> resume authorization | The observer sees `RESUME_RECORDED` before the fake resume hook runs |
| Ambiguous terminal -> retry | A second claim cannot be inserted and the claim count remains one |

The fake hooks do not read secrets, construct a provider, create a Windows
process, call a network, or authorize a real resume. They only prove the
database visibility boundary.

## 10. Security and operational gates not claimed by this fixture

The following remain administrator/manual or future production acceptance
work:

- fixed bootstrap canonicalization and detached signature verification through
  Windows CNG;
- owner/DACL, SID, reparse-point, final-handle, local-volume, and exact
  persistent-journal access checks;
- `PERSIST`/`synchronous=FULL` behavior under the dedicated Trading ACL,
  including no journal recreation, deletion, rename, or directory workaround;
- child-only Credential Manager reads, secret cleanup, process containment,
  Job Object verification, bounded streams, and native handle closure;
- real suspended-process evidence and conservative post-resume ambiguity;
- independently signed `backup_manifest/v1`, database/journal digest checks,
  historical-only restore, new generation/epoch, and empty executable DB;
- historical parsing of schema-1/2 artifacts without import or fallback; and
- unattended scheduling prerequisites and approval.

The validation must explicitly record that an internally consistent
same-generation database/journal replacement by Administrator/SYSTEM or
trusted-token code is outside this design's detection boundary.

## 11. Focused verification commands

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest -q tests/runtime/test_windows_transactional_capture_authority.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```

The focused suite is the executable acceptance gate for this schema revision.
The full suite and repository lint/format/diff checks are required before the
scoped commit. No command may access real credentials, real providers,
brokerage APIs, or real-money trading.
