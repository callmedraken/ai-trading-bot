# PD2D2-R2 First Paper Mutation Hardening Validation Plan

Status: frozen source-validation plan; no production effect authorization.

This plan validates the Architecture-107 repair before another PD2D2 real-host
execution attempt.

## Baseline

Implementation begins from the exact reviewed branch head:

```text
branch: feature/personal-desktop-paper-runtime
HEAD:   7256a3867dbbc660698a5c18f683faf594775be2
tree:   7b670f0c5dbd78d16b50cbce7754fbaff3eb26de
```

The implementation task must STOP rather than self-correct if the local branch,
HEAD, tree, or cleanliness differs from the expected post-documentation base
provided by ChatGPT/Sol.

## Required implementation behavior

The repair must close all four Architecture-107 findings without changing the
frozen Architecture-106 semantic operation.

### 1. Frozen profile blocks before effect

Focused tests must prove that each independent mismatch in the active post-lock
preparation blocks before the Architecture-67 executor is called, including at
least:

```text
paper_account_id
terminal checkpoint ID
selected_snapshot_id
caller idempotency UUID
request_id
plan_id
plan SHA-256
plan byte length
operation_id
application_id
operation root
```

The production API must expose no new argument capable of changing or bypassing
these expected values.

### 2. First-run state must be exact PENDING/PENDING

Focused tests must prove the production first-operation composition performs a
read-only inspection before the generic effectful executor and permits the
executor only for exact:

```text
classification = PENDING
diagnostic     = PENDING
```

At minimum, the following pre-existing states must block with zero executor and
zero output-policy calls:

```text
ALREADY_APPLIED
CONFLICTING
FINALIZED_TRANSITION_WITHOUT_RECEIPT
VALID_FAILED_RECEIPT
receipt staging / transition staging
invalid or unsafe operation state
```

In particular, `FINALIZED_TRANSITION_WITHOUT_RECEIPT` must not enter the generic
Architecture-67 receipt-recovery branch under the first-run production path.

### 3. Production output security policy

Focused fake-native tests must prove:

- only the fixed Paper-v2 runtime/operations namespace is admitted;
- the exact Trading SID is required;
- runtime and paper-operations parents must already exist and verify;
- output directories receive the exact Architecture-103 `OUTPUT_DIRECTORY`
  policy;
- output files receive the exact Architecture-103 `OUTPUT_FILE` policy;
- owner must be the exact Trading SID;
- DACL is protected and exact;
- unknown ACEs, inherited/unsupported ACEs, wrong owner, reparse points, wrong
  volume/filesystem, wrong object kind, alternate path, or case-fold collision
  fail closed;
- production output policy cannot be constructed from a caller-selected root or
  SID override.

If a native Windows integration test is added, it must operate only on a
disposable temporary namespace and must not touch `F:\AITradingBot\Paper-v2`.

### 4. Commit-hook ordering

Generic transition/receipt commit tests must prove the production output
capability is invoked in this order:

```text
create staging
secure/verify staging directory
write exact file(s)
secure/verify staged file(s)
staged semantic verification
revalidate parent/staging identity and collisions
write-through no-clobber finalization
verify finalized directory ACL
verify finalized file ACL(s)
finalized semantic verification
```

Receipt commitment must also prove the existing `paper-operations` parent is
verified and, in production mode, is never silently created.

Portable/default Architecture-67 behavior must remain unchanged when no
production capability is supplied.

### 5. Write-through finalization

Fake-native tests must prove the production finalizer requests only the reviewed
same-parent no-clobber write-through rename and rejects:

```text
wrong source name
wrong final name
cross-parent rename
existing/colliding final
replacement semantics
second finalization attempt after an uncertain native result
```

A native failure/response-loss result is consumed and must not be retried by the
same capability instance.

### 6. Existing Architecture-67 behavior

Focused regression tests must preserve:

- one runtime invocation after exact `PENDING` admission;
- prospective successor edge/full-lineage verification;
- staged and finalized semantic rereads;
- transition finalization as account-state commit point;
- receipt finalization after transition commitment;
- eligible deterministic failed-receipt behavior after the permitted runtime
  attempt;
- generic receipt recovery behavior outside the special first-run production
  composition;
- `ABANDONED_OWNER` reconciliation requirement;
- process-lifetime mutex poisoning after uncertain release failure.

Architecture 107 must not silently disable generic Architecture-67 recovery.

## Required focused tests

Codex should run the smallest relevant set while iterating. The final focused
R2 evidence should include the modified/new test modules for:

```text
personal_desktop_supervised_paper_operation_execution
personal_desktop first-operation frozen admission
paper_operation_execution
checkpoint_transition_output
paper_operation_receipt_output
personal_desktop paper runtime output security
```

Also run Ruff only on changed Python files during iteration if convenient.

Do not repeatedly run the full repository suite during implementation.

## Source review requirements

Before broad certification, ChatGPT/Sol will inspect:

- exact changed files and diff;
- whether any caller-selectable production root/SID/gate/recovery control was
  introduced;
- whether the generic Architecture-67 default path changed unintentionally;
- whether every production write is still inside the fixed Paper-v2 runtime;
- whether transition and receipt identity/verification order remains intact;
- whether `MoveFileExW` (or equivalent) uses write-through and no replacement;
- whether all three effect gates remain false;
- whether the publication-freeze blob is unchanged.

## Broad certification gate

After exact source review accepts R2, run one fresh broad certification from the
canonical development interpreter:

```text
pytest full suite with fresh external --basetemp and -p no:cacheprovider
ruff check .
ruff format --check .
git diff --check
```

Also verify:

```text
all three effect gates == (False, False, False)
publication freeze Git blob unchanged
HEAD/tree exactly match the reviewed R2 commit
working tree clean
```

The prior broad suite does not substitute for this one because R2 changes native
security and crash-sensitive commit logic.

## Post-certification boundary

A PASS authorizes only planning the next gate-enable checkpoint. It does not
authorize:

```text
supervised gate False -> True
real Paper-v2 mutation
receipt recovery
provider call #7
broker submission
unattended scheduling
live trading
```

Before another real-host attempt, ChatGPT/Sol must separately review the minimal
gate-only diff, the exact one-shot command, the current clean production state,
and then obtain fresh explicit user authorization immediately before execution.
