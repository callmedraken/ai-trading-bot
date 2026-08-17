# Authoritative local lineage-head validation

## Scope

Focused validation covers deterministic immutable record models, canonical
serialization, explicit-chain verification, genesis publication, exact
completed-operation advancement, compare-and-swap behavior, and Windows pointer
replacement.

Tests use deterministic local paper artifacts and pytest temporary directories.
They do not contact a provider or broker, open a network connection, read a
clock, capture a snapshot, generate a target, schedule work, or execute any
operation from the authority subsystem. Existing paper-operation fixtures may
create already-completed explicit evidence before the advancement API is
called.

## Model coverage

The runtime suite pins:

- material version and fixed namespace;
- reviewed generation-zero UUID, canonical byte length, and SHA-256;
- path-free construction;
- strict canonical record and pointer round trips;
- duplicate, unknown, missing, float, constant, noncanonical UUID, and semantic
  genesis rejection;
- one final newline and canonical reserialization.

## Filesystem and authority coverage

The CLI suite verifies:

- a safe existing root is required;
- a safe root without a pointer reports `POINTER_MISSING`;
- initialization creates only the fixed manifest, record, and pointer layout;
- initialization requires a genesis-only fully verified manifest;
- complete read-only verification performs no mutation;
- exact one-edge completed-operation advancement reaches generation one;
- the installed two-record chain verifies completely;
- stale expected pointers perform no second advancement;
- completed receipt substitution and pointer tampering fail closed;
- changed pointer epoch is conflicting;
- failed receipts cannot advance;
- injected replacement failure retains both immutable records while the old
  pointer remains byte-identical and fully verifies;
- an unlisted candidate-looking file is ignored as authority;
- network-opening sentinels remain uncalled.

Existing manifest, lineage, successor-edge, paper-operation receipt, transition,
and safe-filesystem suites remain required regression coverage. Platform link
tests retain their existing conditional skip where Windows link creation is not
available.

## Pointer replacement validation

On Windows, the successful advancement test exercises the production
`MoveFileExW` compare-and-swap path. The failure-injection test proves the
abstraction does not mutate the old pointer after a replacement exception and
does not remove finalized immutable evidence.

The tests cannot simulate power loss. The architecture therefore documents the
remaining durability boundary rather than claiming stronger guarantees.

## Commands

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_local_lineage_head.py tests\cli\test_local_lineage_head.py -q
.venv\Scripts\python.exe -m pytest tests\runtime\test_paper_account_lineage_verification.py tests\cli\test_checkpoint_lineage.py tests\runtime\test_checkpointed_paper_cycle_successor.py tests\cli\test_checkpoint_transition.py tests\runtime\test_paper_operation.py tests\cli\test_paper_operation_config.py tests\cli\test_paper_operation_inspection.py tests\cli\test_paper_operation_execution.py tests\cli\test_paper_operation_receipt_output.py tests\cli\test_paper_operation_failed_receipt.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```

CLI smoke checks:

```text
.venv\Scripts\python.exe scripts\verify_local_lineage_head.py --help
.venv\Scripts\python.exe scripts\initialize_local_lineage_head.py --help
.venv\Scripts\python.exe scripts\advance_local_lineage_head.py --help
```
