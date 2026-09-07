# PD2A — paper-account runtime mutex and supervised admission completion

## Status

PD2A is complete and source-certified.

```text
PD2A_ARCHITECTURE_ACCEPTED = YES
PD2A_SOURCE_ACCEPTED       = YES
PD2A_SOURCE_CERTIFIED      = YES
PD2A                       = COMPLETE
```

PD2A is source-only. It performed no production `Paper-v2` mutation, provider
call, broker action, credential effect, scheduling effect, or live-trading
effect.

## Accepted source

Initial PD2A implementation:

```text
commit 7e9ca73cef578ad28b97036755f7b4723bb832fc
message feat: add paper account runtime mutex
```

Fail-closed release correction:

```text
commit 38212c07e0c06c7cf25152c5a362434ded7c3adf
tree   9dc5087b87cfd2c16ef76d97c04fd20d41ba7187
message fix: fail closed after paper mutex release failure
```

The accepted source adds:

```text
src/trading_bot/runtime/personal_desktop_paper_account_mutex.py
tests/runtime/test_personal_desktop_paper_account_mutex.py
```

## Frozen mutex contract

```text
label  = personal-desktop-paper-account-mutex/v1
prefix = Global\AITradingBot-PaperAccount-v1-
identity material = length-framed exact label + canonical lowercase paper_account_id
wait bound = 30,000 ms
```

Production admission accepts only a genuine registered
`ValidatedPersonalDesktopPaperAccount`. The paper account ID and Trading SID
come from registered verified evidence; callers cannot supply the production
mutex name, UUID, timeout, path, handle, or operation root.

Reviewed protected kernel DACL:

```text
BUILTIN\Administrators  MUTEX_ALL_ACCESS
SYSTEM                   MUTEX_ALL_ACCESS
exact Trading SID        MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE
```

Wait semantics:

```text
WAIT_OBJECT_0   -> OWNED
WAIT_TIMEOUT    -> typed busy failure
WAIT_FAILED     -> typed fail-closed wait failure
unknown status  -> typed fail-closed wait failure
WAIT_ABANDONED  -> ABANDONED_OWNER evidence
```

Win32 recursive same-thread ownership is not trusted as the source contract.
PD2A enforces process-wide same-account non-reentrancy.

If `ReleaseMutex` fails, ownership is uncertain. The account digest is
process-lifetime poisoned before the handle closes; later same-account
acquisition fails before any native create/open/wait. Different account IDs
remain independent.

## Future ordering frozen by PD2A

```text
genuine C1/Trading paper-account authority
-> immutable paper_account_id
-> acquire account mutex
-> reread/revalidate mutable account lineage and tip while mutex is held
-> strategy / plan / deterministic risk / simulated execution
-> Architecture-67 transition commitment
-> receipt commitment or zero-runtime reconciliation
-> release only after terminal durable outcome
```

The pre-lock read may establish immutable account identity only. It must never
substitute for the post-lock mutable-state reread used by a future writer.

## Verification

Focused PD2A verification after the release correction:

```text
34 passed
Ruff check: PASS
Ruff format --check: PASS
git diff --check: PASS
```

Full source certification at accepted commit `38212c07...`:

```text
4720 passed
17 skipped
Ruff check: PASS
Ruff format --check: PASS (424 files)
git diff --check: PASS
worktree/index: clean
```

The 17 skips are expected opt-in/platform-specific acceptance cases. No PD2A
test was skipped.

Frozen production containment remains unchanged:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
publication freeze Git blob:
b125cbb1c80a827f74018cf2955b9a27ba69fa90
```

## Next checkpoint

PD2B is the next development checkpoint. It is initially **source-only** and
must compose the existing authorities in the correct lock lifetime:

```text
pre-lock genuine paper-account read for immutable identity
-> PD2A account mutex
-> post-lock genuine paper-account reread/revalidation
-> deterministic paper-cycle composition
-> Architecture-67 transition and receipt/reconciliation
-> release mutex
```

PD2B design/source work does not authorize the first real
`F:\AITradingBot\Paper-v2\runtime` mutation. That requires a later explicit
production-effect checkpoint.
