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
