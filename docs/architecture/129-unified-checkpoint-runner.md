# Architecture 129 — Unified Development and Protected Checkpoint Runner

## 1. Purpose

The D10 development cycle accumulated many one-off PowerShell verification and
diagnostic scripts. Those scripts preserved important fail-closed behavior, but
they also created a second implementation surface that repeatedly needed its
own import-path, formatting, dirty-worktree, and diagnostic corrections.

Architecture 129 replaces that pattern with one checked-in checkpoint runner
and one stable PowerShell launcher.

The goal is not to weaken any production authority boundary. The goal is to
make source verification, read-only host qualification, evidence capture, and
later protected execution use the same reviewed framework.

## 2. Stable entry point

The repository root contains:

```text
ops.ps1
```

PowerShell is intentionally thin. It resolves the approved Python interpreter,
changes only to the repository root, invokes the checked-in Python checkpoint
runner, and propagates its exit code.

Checkpoint logic does not live in generated PowerShell or temporary Python
helpers.

The canonical source entry point is:

```text
python -B -m scripts.checkpoint_runner
```

## 3. Registered checkpoints only

The runner is registry driven. Operators choose a reviewed checkpoint name;
they do not supply arbitrary test paths, Python modules, production paths,
commands, ACLs, scheduler names, or mutation callbacks.

The initial registered source profiles are:

```text
arch128-parent-acl-repair
arch128-r4
```

Future profiles for Architecture-128 R5/R7 or later milestones must be added as
reviewed source changes with tests.

## 4. Source verification contract

`ops.ps1 verify <checkpoint>` is source-only.

Every registered source gate runs all primary phases before deciding PASS/FAIL:

1. checkpoint pytest selection with an explicit external `--basetemp`;
2. `ruff check --no-cache`;
3. when lint fails, non-mutating `ruff check --diff --no-cache` diagnostics;
4. `ruff format --check --no-cache`;
5. when format fails, non-mutating `ruff format --diff --no-cache` diagnostics;
6. `git diff --check`;
7. the checkpoint's in-process AST/static authority checks; and
8. final HEAD/TREE/clean-worktree revalidation.

A lint failure may not hide formatter results. A pytest failure may not prevent
the two Ruff primary checks or authority review from running.

Source verification never invokes Ruff `--fix`, an in-place formatter,
production filesystem mutation, scheduler mutation, activation, provider,
broker, or live effects.

## 5. External evidence

Checkpoint evidence is written outside the repository. On the production
development host the preferred root is:

```text
F:\AI\temp\ai-trading-bot-checkpoints
```

Other environments use an explicitly configured external evidence root or the
platform temporary directory.

Each source run records:

- checkpoint name and schema;
- starting and ending HEAD/TREE/branch/clean state;
- every primary and diagnostic command;
- exit status;
- stdout/stderr byte lengths and SHA-256 digests;
- paths to preserved stdout/stderr evidence;
- authority-check failures;
- final overall PASS/FAIL; and
- explicit `NOT_RUN` production-effect fields.

Evidence is diagnostic/audit material. It is not authority to cross a protected
effect boundary.

## 6. CI source gates

GitHub Actions runs the same stable launcher on Windows with Python 3.14.

The CI workflow:

- checks out the exact commit;
- installs only source-gate dependencies;
- runs runner status;
- runs every registered Architecture-128 source profile even if an earlier
  profile fails;
- fails only after all selected profile results have been collected; and
- uploads external checkpoint evidence when available.

CI replaces most user-run source verification. It cannot certify local Windows
production-host state.

## 7. Read-only host preflight

The next runner layer is `preflight`.

A preflight must:

- be read-only;
- use a registered checkpoint implementation;
- prove exact repository/source identity and clean state;
- use the existing reviewed native observers;
- collect structured mismatch diagnostics in the same run;
- never construct a writer or protected mutation callback; and
- emit external evidence using the same runner schema family.

The first preflight migrations are:

```text
arch128-parent-acl-repair
arch128-r4
```

For example, an R4 parent-policy mismatch should include the exact parent ACL
difference automatically instead of requiring a newly generated diagnostic
script.

## 8. Protected execution

Protected execution is implemented only for explicitly registered reviewed
profiles. The protected migrations are:

```text
execute arch128-parent-acl-repair
execute arch128-r4
```

The runner itself first requires a clean exact live-remote source identity and
writes a pre-effect external attempt record. Each registered execute wrapper
delegates through the already-reviewed operator's exact `EXECUTE_FLAG` /
authorization-environment interlock rather than calling mutation primitives
directly.

For the parent-ACL repair, a PASS must carry the exact verified parent-policy
mutation evidence. For R4, a PASS must carry exact
`REPLACEMENT_COMPLETE_AND_VERIFIED` evidence plus both reviewed rename outcomes
as `SUCCESS`. Any non-PASS R4 result that is not provably pre-mutation is
conservatively recorded as `MAY_HAVE_OCCURRED`. The final report preserves the
operator result, effect disposition, post-run source identity, and
`automatic_retry = NOT_AUTHORIZED`. An unexpected runner exception after
dispatch is also conservatively recorded as `MAY_HAVE_OCCURRED`.

Adding `execute` to the unified runner does not imply authorization to use it.
Each protected checkpoint must retain:

- its fixed pre-state contract;
- exact mutation scope;
- explicit authorization interlock;
- one-shot/no-retry semantics where required;
- mandatory post-mutation readback;
- terminal handling for ambiguous native outcomes;
- explicit forbidden-effect fields; and
- a fresh user authorization at the effect boundary.

The runner may centralize orchestration and evidence, but it may not convert a
source PASS or preflight PASS into production authority.

## 9. Failure and recovery rules

The unified runner does not reset, clean, stash, rebase, roll back, or silently
repair an unexpected worktree.

Unexpected local/remote/source state remains a STOP.

A failed protected effect is never retried merely because a new runner process
can be launched. Consumed or ambiguous authority remains consumed/ambiguous
until the applicable recovery architecture admits a next action.

Diagnostic expansion should normally happen inside the same checked-in
read-only observer rather than through a new temporary script.

## 10. Generated-script policy

New one-off PowerShell verification scripts are fallback-only.

They are appropriate only when a checked-in runner cannot yet safely express a
bootstrap or recovery operation and the new behavior cannot first be added and
source-reviewed in the runner.

Routine source verification, status, read-only qualification, and eventually
reviewed protected checkpoints must use the unified runner.

## 11. Initial implementation status

Implemented:

- stable `ops.ps1` launcher;
- `scripts/checkpoint_runner.py`;
- `status`;
- `verify arch128-parent-acl-repair`;
- `verify arch128-r4`;
- `preflight arch128-parent-acl-repair`;
- `preflight arch128-r4`;
- protected `execute arch128-parent-acl-repair` dispatch, still requiring the
  existing exact authorization interlock and fresh user approval;
- protected `execute arch128-r4` dispatch, still requiring the existing exact
  authorization interlock and fresh user approval;
- read-only `preflight arch128-r5-substrate` for the fresh P124-1 production
  Python substrate proof against an actual Trading process;
- read-only `preflight arch128-r5-trading` for the actual non-admin Trading
  canonical-deployment qualification through the fixed production interpreter;
- automatic parent-ACL diagnostics when R4 blocks on parent policy;
- checkpoint-pinned remote-branch verification through read-only
  `git ls-remote`;
- clean detached operator-worktree support;
- combined Ruff diagnostics;
- structured external evidence;
- checkpoint authority checks;
- Windows GitHub Actions source gates with evidence upload.

Next:

1. source-certify both R5 read-only profiles;
2. run `preflight arch128-r5-substrate` elevated against one actual non-admin
   Trading process using the exact PID interlock;
3. run `preflight arch128-r5-trading` from the actual non-admin,
   non-elevated Trading principal;
4. accept R5 only if both exact-source qualifications PASS;
5. continue into R6 source-only reactivation/evidence design;
6. keep R7 scheduler/lease activation behind its own separately authorized
   protected boundary.


### Bounded live-remote admission

Live-remote admission is fail-closed and non-interactive. The runner disables
terminal/Git Credential Manager prompting for `git ls-remote`, applies a fixed
30-second timeout, and treats timeout or authentication failure as an admission
failure before any checkpoint-specific preflight is called. This prevents
restricted-principal qualifications from hanging indefinitely while preserving
the exact live-remote source requirement.


### R5 Trading two-principal live-remote handoff

The non-admin Trading principal is intentionally not provisioned with GitHub
credentials. R5 therefore uses a narrow two-principal exception to the ordinary
preflight remote lookup:

1. the elevated Administrator orchestrator performs the normal bounded,
   non-interactive live `git ls-remote` observation;
2. only the exact 40-character lowercase remote HEAD is passed into the
   short-lived Trading process through
   `AI_TRADING_BOT_ARCH128_R5_ADMIN_REMOTE_HEAD`;
3. `arch128-r5-trading` requires that value to be syntactically exact and
   byte-for-byte equal to its own clean detached local HEAD before any
   checkpoint-specific Trading qualification runs; and
4. the preflight evidence records whether remote identity came from a live
   lookup or the R5 trusted Administrator handoff.

This handoff is registered only for the read-only `arch128-r5-trading`
profile. Protected execute checkpoints do not accept an environment-supplied
remote head and continue to perform their own live remote lookup.


### Architecture 128 R6 source-only reactivation gate

R6 is registered as `verify arch128-r6` only. It has no `preflight` or
`execute` surface.

The pure R6 state machine freezes:

- new activation/end/soak derivation from the Architecture-128 replacement
  identity, with the halted activation/end/soak rejected;
- the evidence filename derived only from the new lease soak ID;
- exact Architecture-127 evidence ACL/capability facts;
- the real-Trading append-only, WRITE_THROUGH, zero-write probe contract;
- evidence provisioning before scheduler mutation;
- fresh admission after the credential pause;
- independent scheduler readback while the final lease remains absent;
- exact tmp -> installing -> final lease publication stages;
- final lease publication as the last arming mutation;
- final deployment/scheduler/lease/evidence readback;
- reconciliation-only handling after any possible mutation; and
- manual task start, source launch, provider, Paper-v2, broker, and live effects
  closed throughout.

R6 deliberately contains no Windows mutation adapter. R7 must add and
source-certify the concrete protected host bindings before any protected
activation is proposed, and R7 still requires fresh explicit human
authorization.


### Architecture 128 R7A read-only activation admission

The unified runner now registers `arch128-r7` with source verification and a
read-only host preflight only:

```powershell
.\ops.ps1 verify arch128-r7
.\ops.ps1 preflight arch128-r7
```

There is deliberately no `execute arch128-r7` surface at this checkpoint.

R7A reuses the accepted Architecture-128 COMPLETE-state observer rather than
introducing a second host model. Its preflight re-proves, in two stable reads
through the existing observer chain:

- the exact new canonical signed deployment and sealed source/guard;
- the exact preserved halted S5-R10 incident-retired deployment and lease;
- absence of the historical S5-R8 retired namespace;
- absence of the Architecture-128 replacement staging namespace;
- the exact empty canonical evidence root;
- absence of activation lease final/installing/tmp;
- the exact disabled, non-running D10 scheduler state; and
- exact parent/reserved-namespace and same-volume facts already required by R4.

The R7A source profile independently requires all production/evidence/scheduler/
lease/start/provider/Paper-v2/broker/live effect fields to remain `NOT_RUN`.

Accepted source checkpoint:

```text
HEAD: 51298a60837ee1d1222c7068b2866ebb40abd2c9
TREE: 64e47128e7813023c8c74421c9b0b7c27c25093e
CI:   36683077156 SUCCESS
```

This source acceptance authorizes only the read-only R7A host preflight. A
future R7 protected binding/execute implementation remains source work, and
actual evidence creation, scheduler mutation, or activation-lease publication
still requires a separate fresh explicit authorization after final exact-source
admission.


### Architecture 128 R7B protected-dispatch source contract

R7B freezes the protected authorization/composition boundary without making R7
executable. The source owns exact execute-flag and environment authorization
values, calls the accepted R6 state machine only after both interlocks match,
propagates mutation/reconciliation disposition without granting retry/rollback/
cleanup authority, and rejects any claimed PASS that does not preserve the
frozen R6 completion contract.

R7B deliberately contains no Windows evidence writer, Trading-token acquisition,
scheduler transport, activation-lease writer, process launcher, provider,
Paper-v2, broker, or live-trading implementation. The unified runner continues
to register `arch128-r7` with read-only `preflight` only; its `execute`
field remains absent.

The next source-only checkpoint is R7C concrete host binding. In particular it
must solve the Architecture-128 requirement that the newly created evidence file
be opened through a genuine Trading token under the exact append-only,
WRITE_THROUGH, zero-write contract before scheduler credential acquisition.
Only after those concrete bindings are source-certified may a protected runner
execute surface be registered, and actual R7 activation still requires fresh
explicit authorization.


### Architecture 128 R7C concrete Windows host bindings — ACCEPTED

R7C is source-certified at:

```text
HEAD: b49cd470b11ab4ed68ce7e1a153541e6af06fcd5
TREE: c37d650f40c401454219c98f993b52bce6a2aa08
CI:   36771571929 SUCCESS
```

The accepted R7C source adds concrete fixed Windows bindings for the frozen R6
state machine while leaving `execute arch128-r7` unregistered. It provides
exact-plan evidence creation with the Architecture-127 append-only ACL, a
genuine Trading-token append-open/zero-write probe before credential
acquisition, an R7-only TASK_UPDATE transport for the exact disabled D10
predecessor, independent COM scheduler readback, four-stage R7 COMPLETE
observation, and unchanged reuse of the accepted activation-lease publisher.
The R7 authority check constrains these native surfaces to the reviewed R7C
modules/helper and continues to reject direct host authority in R7A/R7B.

GitHub Actions run 36771571929 passed every registered Architecture-128 source
gate; `arch128-r7` passed pytest, Ruff lint/format, git diff checking, authority
review, and identity stability.

R7C performed no production effect and does not itself create an executable
runner surface. The next source-only checkpoint is narrow protected-runner
registration: compose the accepted R7B authorization interlock with the accepted
R7C host factory in the unified runner without duplicating mutation logic. Only
after that final executable source is accepted should a fresh exact-source
read-only R7 host preflight run. Actual protected activation still requires
fresh explicit user authorization.


### Architecture 128 R7D protected runner registration — ACCEPTED

R7D is source-certified at:

```text
HEAD: 593070256441edcf6fdd3961f0bfbb9a8b129ff7
TREE: b408d1200620baff30720f5366f08fd79c7be041
CI:   36776863936 SUCCESS
```

The `arch128-r7` checkpoint now has a protected execute registration, but the
runner adds no host mutation implementation. Its wrapper delegates only through
the accepted R7B dispatcher using the accepted R7C host factory, freezes the
existing interlocks, validates the exact R7 completion result, and classifies
all ambiguous outcomes conservatively. Generic protected execution continues to
require a clean worktree at the exact live remote branch head, writes an
external pre-effect attempt record, and grants no automatic retry.

Registration does not authorize execution. The next checkpoint is one final
exact-source, elevated, read-only `preflight arch128-r7` on the Windows
production host. Only after that preflight is reviewed may a fresh explicit
operator authorization for actual R7 activation be considered.

### Architecture 128 R7E admission and protected R7 activation — ACCEPTED

The final R7 executable source was admitted and executed at
`fdefad3f1b800b5c71ccdb0120bcefa2dbfed2e9` /
`b6689b5a09d5a07c05d8eb20cf768296214f7a34`.

R7E was a read-only elevated exact-live-remote preflight and PASSed with all
protected effects NOT_RUN. The first authorized protected execution then
STOPPED in the host factory because the Trading PID environment handoff was
absent. The generic runner correctly classified that exception as
MAY_HAVE_OCCURRED; exact protected evidence showed evidence/scheduler/lease
mutations all NOT_RUN. A registered read-only R7 preflight then PASSed and
re-proved the inert host state before any retry was considered.

After fresh explicit authorization, the second one-shot execution returned the
exact frozen completion contract:

```text
status=PASS
stage=COMPLETE
authorization=ACCEPTED
evidence_provision=CALL_RETURNED
scheduler_mutation=CALL_RETURNED
lease_publication=PUBLISHED_VERIFIED
reconciliation_required=false
effect_disposition=CONFIRMED
identity_stable=true
```

The accepted R6 state machine cannot produce COMPLETE unless the lease publisher
returns the exact three publication stages and the final admission/readback
succeeds. Manual task start, governed source launch, provider, Paper-v2, broker,
and live effects remained NOT_RUN, with no automatic retry/rollback/cleanup.

The derived R7 activation is
`2026-09-30T22:07:24.000000Z` through
`2026-10-07T22:07:24.000000Z`, soak
`30e31396-9f51-57ca-a480-d2a3e9cae4a0`, evidence path
`F:\AITradingBot\D10\evidence\wake-30e31396-9f51-57ca-a480-d2a3e9cae4a0.jsonl`.

R7 is therefore ARMED. The next runner/operator activity is R8 read-only
observation of the first **natural** scheduled wake. No manual task start or
synthetic wake is authorized.
