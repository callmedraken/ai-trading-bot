# AI Development and Review Workflow

This document is the canonical working agreement for AI-assisted development in
this repository. `AGENTS.md` remains the mandatory repository rule set; this
file records the normal handoff, review, testing, and local-operator cycle in
more detail.


### Project-state reconstruction and transition quality

At the start of a new Trading Bot chat, after a substantial context reset, or
whenever the user asks to re-establish the workflow, reconstruct the current
state before recommending or authorizing work. Read the current Git-tracked
`docs/AI_TRADING_BOT_HANDOFF.md`, `docs/PROJECT_STATUS.md`, `AGENTS.md`, the
relevant architecture/validation documents, and the available Trading Bot
project conversation history. Verify the active remote branch/HEAD, recent
commits/diff and CI through GitHub when material. Git-tracked canonical docs
outrank uploaded mirrors or older chat summaries unless the conversation clearly
records a newer intentional change that has not yet been committed.

Do not ask the user to paste GitHub diffs/comments, prior Trading Bot chats,
repository files, or other project material when the available project/GitHub
retrieval tools can obtain it directly.

After reconstruction, and after every milestone/review/certification transition,
leave the project immediately actionable. A substantive transition response
should state, when applicable:

- current verified checkpoint;
- active branch and verified remote HEAD/tree;
- latest relevant implementation/certification identity;
- current unresolved blocker or protected boundary;
- immediate next step;
- recommended owner/model for that step;
- the exact ready-to-run command, ready-to-paste Codex prompt, or ChatGPT-led
  review action;
- expected success evidence and stop condition; and
- exactly what output the user should return when another review turn is
  genuinely required.

The user should not need a follow-up merely to ask what to do next, which model
to use, what command to run, what output to send back, or whether the checkpoint
is ready to advance. If the next action crosses a protected effect boundary,
provide the safe preflight/readiness material and stop at the authorization
boundary rather than presenting the effectful command as ordinary verification.

## Roles

### ChatGPT / Sol

ChatGPT owns:

- architecture and milestone planning;
- debugging strategy;
- GitHub commit/diff/pull-request review;
- test-gate and certification decisions;
- merge-readiness decisions;
- production-authority and external-effect review;
- concrete next-step and next-milestone instructions.

ChatGPT also directly handles small, clearly scoped, low-risk project updates
and fixes when the desired behavior, affected files, and focused verification
surface are already known. This is the default for routine docs/status/handoff
closeout, tiny workflow/test/source corrections, and mechanical consistency
fixes where delegating to Codex would add overhead without useful isolation.
Do not hand such work to Codex merely by habit.

Direct ChatGPT changes follow the same repository discipline as delegated work:
prove exact startup identity, edit only the intended files, run the focused
checks appropriate to the change, exact-file stage/commit/push only when
authorized, and leave broad/final certification to the established gate.
Delegate to Luna/Astra/Sol High only when implementation size, discovery,
isolation, or architecture/security sensitivity makes delegation materially
useful.

When the next action is known, ChatGPT must provide it automatically rather
than waiting for the user to ask what to do next. The response should include
the actionable execution material when known: exact operator commands,
expected evidence and stop conditions, a ready-to-paste Codex prompt, or direct
ChatGPT-led work. Merely naming the next milestone is not sufficient when the
execution path is already known.

After every accepted checkpoint, ChatGPT must automatically:

1. accept or reject/fix the current checkpoint;
2. review and update `docs/PROJECT_STATUS.md` and
   `docs/AI_TRADING_BOT_HANDOFF.md` before treating the checkpoint as closed;
3. determine the next milestone/checkpoint;
4. choose ChatGPT, Luna Extra High, Astra, or Sol High according to the routing
   rules below;
5. continue automatically into the next safe docs-only, source-only,
   design-only, or read-only checkpoint when no protected approval boundary is
   crossed; and
6. stop at the exact approval boundary for production/provider effects,
   provisioning, scheduler mutation, merge/rebase/amend/force-push, PR metadata
   or review-thread changes, broker/live effects, or another explicitly
   protected action.

If one of the two canonical status/handoff documents requires no material edit,
ChatGPT should explicitly report that it was reviewed and remains current.

ChatGPT may directly perform small, tightly scoped, low-risk mechanical source,
test, documentation, status, handoff, and workflow changes when delegation
would add overhead without useful isolation. Codex should not receive every
implementation task automatically.

### Codex

Codex is the bounded implementation agent. It should:

- implement only the already-scoped change;
- read `AGENTS.md`, `docs/PROJECT_STATUS.md`, and only relevant architecture or
  validation documents;
- run focused tests/checks during implementation;
- preserve unrelated generated/untracked files;
- when the task explicitly authorizes the checkpoint, exact-file stage only the
  intended paths, verify the staged filename set and diff check, create a normal
  commit, and ordinary-push the isolated feature branch;
- report files changed, focused commands/results, commit/push result when
  authorized, and deviations/blockers;
- stop before broad local certification unless the task explicitly says
  otherwise.

If the task does not explicitly authorize commit/push, Codex stops before those
Git operations and reports the local changes.

## Model selection

Use the smallest model class that fits the *uncertainty and safety profile* of
the task, not simply the number of files changed.

### Luna Extra High — known contract, known surface

Use **Luna Extra High** by default when:

- the contract is frozen or nearly frozen;
- the relevant entry points and affected files are already known;
- the focused tests/checks are obvious;
- the work is localized, mechanical, or a small bounded correction;
- implementation should follow an established pattern rather than discover a
  new one.

Typical Luna work includes known-file feature implementation, focused test
additions, narrow bug fixes with an established root cause, small refactors
under a frozen contract, and routine docs/help updates.

### Astra — discovery-aware bounded implementation

Use **Astra** by default when the task is still bounded but useful implementation
requires broader repository understanding first, including when:

- the affected file set is not obvious at the start;
- the root cause must be traced across modules;
- the change crosses multiple non-security subsystems;
- the work is a bounded refactor, migration, hygiene, dependency, or consistency
  pass;
- hidden coupling or duplicated behavior must be found before editing;
- a broad read-only repository audit is explicitly requested.

Astra replaces **Sol Medium** as the normal middle tier for new Codex work.
Astra's broader exploration allowance is not permission to redesign settled
architecture or broaden the authorized checkpoint. If discovery reveals that
the contract itself must change, stop and return the issue to ChatGPT.

### Sol High — safety/authority escalation

Use **Sol High** for native Windows/security, production authority, ordering,
crash/recovery, credential/reference-version changes, external-effect
containment, broker/live boundaries, or other architecture-sensitive
implementation where a mistake could weaken a safety invariant.

Sol Medium is no longer part of the default routing ladder. Use it only when the
user explicitly requests it or Astra is unavailable and the task still fits the
former subtle-but-bounded tier.

A practical routing shortcut is:

```text
contract + entry points + focused tests already known
-> Luna Extra High

root cause / affected files / cross-module consequences require discovery
-> Astra

security / authority / external-effect / crash-ordering invariant involved
-> Sol High
```

Do not escalate to Astra merely because a mechanical change touches several
files. Conversely, do not use Luna to brute-force a task whose root cause or
cross-module impact is still uncertain.

Model choice never transfers architecture or acceptance authority. ChatGPT
still owns architecture, exact GitHub diff review, certification, merge or
deployment decisions, production-effect authorization, and the next milestone.

Do not use subagents unless explicitly requested.

## Standard bounded implementation cycle

The normal cycle is:

```text
ChatGPT scopes/finalizes the contract and explicitly authorizes the checkpoint
-> ChatGPT chooses direct work / Luna / Astra / Sol High from the routing rules
-> implementation occurs
-> focused tests/checks run
-> index is proven initially clean when a commit is planned
-> exact intended paths only are staged
-> staged filename set and git diff --cached --check are verified
-> normal checkpoint commit is created when authorized
-> isolated feature branch is ordinary-pushed when authorized
-> exact remote branch HEAD/tree are verified
-> ChatGPT reviews the exact GitHub commit/diff
-> ChatGPT accepts the reviewed source checkpoint
-> user runs the appropriate certification tier when ChatGPT declares its gate
-> ChatGPT accepts/rejects certification
-> ChatGPT reviews/updates PROJECT_STATUS + HANDOFF
-> ChatGPT automatically provides and, when safe, advances into the next
   actionable milestone
```

When ChatGPT intentionally withholds commit/push authorization, Codex stops
after focused verification and reports the local change set instead.

Manual patch-file transfer or pasting a large diff into chat is a fallback only
when GitHub/tool access fails. It is not the normal review path.

For a scoped checkpoint with known paths, do not use `git add .` or
`git add -A`. Stage the exact intended files. Before committing, verify the
staged filename set and run `git diff --cached --check`. A normal feature-branch
push does not authorize merge, rebase, amend, force-push, PR metadata changes,
review-thread resolution, branch switching, or unrelated modifications.

## Frozen startup and post-write verification

Before edits, certification, deployment, or operator work in an active worktree,
verify at minimum:

```text
exact worktree path
exact branch
expected local HEAD
expected tree
expected origin/remote ref
clean index
expected worktree state
```

A mismatch is a STOP condition. Do not self-correct by switching branches,
resetting, cleaning, rebasing, force-updating, pulling across unexpected
history, deleting artifacts, or otherwise manufacturing the expected state.
Report the mismatch and preserve evidence.

After an ordinary push or an approved merge, verify the exact remote/resulting
HEAD and tree plus the expected clean local state before reporting success.
Post-merge reporting must include the next milestone automatically.

A merge does not require rerunning a broad suite merely because a merge occurred
when the exact resulting source tree was already certified. If the resulting
tree differs from the certified source tree, use the appropriate final
certification gate before accepting the milestone.

## ChatGPT-direct bounded-commit local catch-up

When ChatGPT directly creates an accepted, tightly scoped commit on the active
remote feature branch, the local worktree may intentionally be one or more
reviewed commits behind. This includes routine docs/status/handoff closeout and
tiny mechanical source/test/workflow corrections whose exact diff ChatGPT has
reviewed directly. That expected state is not treated as a generic mismatch to
repair.

Before any next local or Codex work:

1. enter the exact intended worktree and prove the tracked worktree/index is
   clean;
2. prove the current local branch is the expected branch;
3. fetch the exact remote branch;
4. prove the remote HEAD is the exact reviewed ChatGPT-direct commit HEAD;
5. prove the local HEAD is either already that HEAD or the exact known
   pre-direct-change accepted HEAD and an ancestor of the reviewed remote HEAD;
6. only in that known-behind case, fast-forward with `git merge --ff-only`
   (or equivalently `git pull --ff-only` when the same exact remote/branch has
   already been proven);
7. verify final local HEAD/tree equal the expected remote HEAD/tree and the
   tracked worktree/index remains clean; and
8. continue automatically into the next safe checkpoint when no protected or
   repository-control approval boundary is crossed.

Any other branch, HEAD, ancestry, remote, tracked/index, or fast-forward result
is a STOP condition. Do not reset, rebase, normal-merge, force-update, switch,
clean, delete artifacts, or otherwise manufacture the expected state.

This is the narrow exception that reconciles the startup STOP rule with reviewed
ChatGPT-direct remote commits: fast-forward synchronization is allowed only
after the exact known-behind state has itself been proven. It is not a generic
pull/repair mechanism.

## Testing and certification

During iteration:

- Codex runs focused tests/checks for changed behavior;
- do not repeatedly run the complete repository suite;
- do not run long integration/E2E or production acceptance gates unless they are
  part of the explicitly requested checkpoint;
- if a broad local run fails, diagnose the affected area and rerun only focused
  tests after the bounded fix.

Architecture 132-R1 separates current-supported certification from legacy
compatibility. The normal tier sequence is:

```text
FOCUSED
-> SOURCE-GATE CI
-> ROBINHOOD when appropriate
-> FULL at coherent current-product boundaries
-> LEGACY/EXHAUSTIVE only when explicitly relevant
-> PROTECTED separately authorized
```

| Level | Trigger and responsibility |
| --- | --- |
| FOCUSED | Every implementation/correction; Codex runs affected tests and focused checks. |
| SOURCE-GATE CI | Every pushed registered checkpoint; existing registered GitHub source-gate batching remains accepted. |
| ROBINHOOD | ChatGPT-declared coherent Architecture 131 integration boundary; before protected Robinhood qualification; after material changes to shared domain/execution/ledger/risk foundations used by Architecture 131. |
| FULL | Comprehensive CURRENTLY SUPPORTED product certification: after certification-topology changes; at coherent current-product boundaries; before major develop/release integration or consequential production/live-readiness transitions; after sufficiently broad supported shared-core changes; or when ChatGPT determines accumulated checkpoints warrant current-product regression. |
| LEGACY / EXHAUSTIVE | Only when explicitly relevant: legacy architecture changes, interpreter/dependency migrations spanning both eras, broad repository restructuring, deliberate legacy removal, or explicit backward compatibility investigation. |
| PROTECTED | Always separate fresh authorization at the exact effect boundary. |

FULL remains the default and is not mechanically tied to every accepted source
checkpoint or Architecture 131 letter. FULL now means all CURRENTLY SUPPORTED
functionality, replacing the original Architecture 132 meaning. EXHAUSTIVE
preserves that earlier all-repository behavior. Normal current-product
certification does not require LEGACY or EXHAUSTIVE.

ChatGPT chooses the appropriate tier after exact GitHub code review and source
acceptance. The normal handoff remains:

```text
implementation + focused checks
-> exact-file commit/push
-> ChatGPT exact GitHub code review
-> source acceptance
-> appropriate certification tier
-> docs closeout (PROJECT_STATUS + HANDOFF after certification acceptance)
```

At a declared certification boundary:

- ChatGPT supplies exact local commands and frozen source identities;
- the user runs the selected profile and required source/artifact checks;
- review-driven source corrections return to focused verification first;
- if the environment invalidates the run, repair it before interpreting failures
  as source defects;
- after clean certification, do not repeat it without a new source change or
  explicit gate decision;
- a merge needs no second run when its resulting tree exactly equals the
  already-certified tree.

The runner accepts these profiles (counts at the accepted 132-R1 startup tree):

| Profile | Modules | Exact lanes |
| --- | ---: | --- |
| full (default) | 113 supported | broad-1, broad-2 |
| robinhood | 40 supported subset | robinhood-1, robinhood-2 |
| legacy | 204 retired architecture | legacy-1, legacy-2, serial |
| exhaustive | 317 complete repository | broad-1, broad-2, serial |

[Architecture 132](architecture/132-tiered-certification-profiles.md) freezes
ownership and required baselines. Whole supported directories admit new tests
automatically; mixed CLI/market-data/scripts ownership is exact and new files
require review. Root `tests/test_robinhood_*.py` tests enter automatically.
Missing/renamed FULL or Robinhood baseline modules fail closed. Every repository
module must have reviewed support status, including for EXHAUSTIVE; unfamiliar
namespaces must never silently enter LEGACY. Robinhood is contained in FULL;
FULL and LEGACY are disjoint and their union equals EXHAUSTIVE, which equals
the complete discovered repository inventory.

D10/Windows/Paper-v2/Alpaca operational paths are retained historical
compatibility, not current product requirements. The existing pre-Robinhood GUI
is legacy because it uses the retired operational artifact/runtime model. GUI
remains a future product goal; a Robinhood-integrated GUI milestone must
explicitly reclassify or replace it.

Only LEGACY and EXHAUSTIVE retain the historical serial safety lane:

```text
tests/runtime/test_windows_transactional_capture_authority.py
tests/runtime/test_windows_authority_schema.py
tests/runtime/test_windows_authority.py
tests/runtime/test_windows_effectful_capture_native_acceptance.py
tests/acceptance/test_windows_authority_provisioning_acceptance.py
```

Architecture-77 remains serial; unrestricted parallel safety has not been
established. FULL and Robinhood have exactly two nonempty balanced file lanes
and no serial lane. Never launch pytest with an empty module list.

All profiles retain exact clean source/local-tracking/live-origin admission,
post-test/final verification, protected-opt-in rejection, external temp-root and
JUnit/evidence validation, and whole-repository `ruff check --no-cache .`,
`ruff format --check --no-cache .`, and `git diff --check`. Evidence records the
profile, repository/selected/excluded inventories, support classification and
exact lanes. `inventory.json` retains `all` as the complete repository inventory;
only EXHAUSTIVE selects all of it. `--plan` saves topology/evidence without
launching pytest or static checks for any profile.

No profile grants native Windows acceptance opt-ins, provider access, Robinhood
calls, OAuth interaction, broker effects, or production effects. PROTECTED
remains separate and always needs fresh authorization. Architecture 132-R1
implementation runs only focused checks; actual certification requires the
subsequent exact GitHub review and ChatGPT's gate decision.


### Windows operator command transport and serialization

Repeated project incidents have shown that Windows PowerShell/native-process
argument transport is an authority and evidence risk, not merely a shell-style
preference. Operator commands must use this order of preference:

1. an existing reviewed source-owned CLI or the Architecture-129 `ops.ps1`
   runner;
2. a reviewed version-controlled `.py` / `.ps1` helper with focused tests;
3. only when no reviewed entry point exists, a short read-only diagnostic whose
   payload is transported through a file path or stdin rather than complex
   command-line quoting.

Never pass structured JSON or other structured payloads as a raw native command
argument when a file path or stdin can carry the bytes. Never embed substantial
Python in `python -c` from PowerShell. If a tiny Python diagnostic must be sent
through stdin, use a single-quoted PowerShell here-string and pipe it to
`python -B -`; do not pass that here-string as the `-c` argument. Substantial
logic belongs in reviewed repository files.

PowerShell/operator blocks must also preserve these established Windows rules:

- normalize filesystem identities with `Resolve-Path` (and case-insensitive
  comparison where appropriate) instead of comparing Git's slash-normalized
  path text directly to a backslash literal;
- under StrictMode, force potentially singleton pipelines to arrays with
  `@(...)` before using `.Count`;
- treat empty `Get-Content -Raw` results as possibly `$null` and use null-safe
  string checks;
- when native stderr can be expected, use a reviewed wrapper or
  `Start-Process -Wait -PassThru` with redirected stdout/stderr instead of
  allowing `$ErrorActionPreference = 'Stop'` to reinterpret diagnostic stderr
  before the native exit code is handled;
- serialize multi-step copy/paste operator commands inside one invoked
  scriptblock (`& { ... }`) or reviewed script, and emit the terminal PASS
  marker only inside that same guarded scope after every prerequisite succeeds.
  Never provide a detached PASS line that can still be pasted/executed after an
  earlier `throw` or native failure.

Generated giant PowerShell blocks are not a normal workflow. If a diagnostic is
likely to be reused, crosses a protected boundary, carries structured data, or
requires more than a short admission/invocation wrapper, promote it to a tested
reviewed script/checkpoint before use.

### Local Git compatibility rule

The Windows development machine currently uses an older Git version where
`git switch` is unavailable. Repository/operator instructions must use
`git checkout` for branch changes and `git checkout -b <branch> --track
origin/<branch>` when creating a local tracking branch. Do not assume
`git switch` support unless a later environment check explicitly proves it.

### Windows pytest temporary-directory rule

On John's Windows development account, pytest commands that may use `tmp_path`
or `tmpdir` must use a fresh explicit `--basetemp` outside
`C:\Users\John\AppData\Local\Temp\pytest-of-John`. The default pytest temp root
has previously produced `WinError 5` while pytest was only setting up fixtures;
that is an environment/setup failure, not a source regression.

Use the existing external test-temp convention:

```powershell
$BaseTemp = "F:\AI\temp\pytest\<purpose>-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force 'F:\AI\temp\pytest' | Out-Null
& $Python -m pytest ... --basetemp="$BaseTemp" -p no:cacheprovider
```

Rules:

- use a fresh unique basetemp for each controlled run;
- do not globally change `TEMP` or `TMP` to work around pytest permissions;
- do not persistently set `PYTHONPATH` for normal pytest collection;
- `pyproject.toml`'s `pythonpath = ["src"]` owns normal pytest imports;
- when a certification command is generated for this host, explicit basetemp is
  part of the command, not an optional troubleshooting fallback.

Milestone, verification, merge, and post-merge reports must always include the
next actionable step and concrete execution material when known.

## Canonical worktree location

The main checkout remains at `F:\\AI\\ai-trading-bot`. Every auxiliary
Trading Bot Git worktree must be created under:

```text
F:\\AI\\worktrees\\<explicit-project-worktree-name>
```

Do not create or adopt Trading Bot worktrees under the user profile, including
Codex-managed defaults such as:

```text
C:\\Users\\John\\.codex\\worktrees\\...
```

Every task that creates or selects a worktree must name the exact
`F:\\AI\\worktrees\\...` path in its startup gate. If a tool proposes or
creates a worktree outside that root, stop before edits and recreate/select the
worktree at the canonical F: location. Do not silently treat a noncanonical
path as equivalent.

A noncanonical worktree that already contains generated/untracked artifacts is
not force-removed or cleaned merely to satisfy this convention. Preserve the
artifacts, classify the worktree state, and use a separate reviewed
reconciliation/removal step. A dirty-worktree STOP remains a STOP.

When an interactive PowerShell block throws a STOP, commands appearing later in
the pasted block are not authorized to continue just because PowerShell accepts
subsequent input. Re-establish the exact worktree/branch/HEAD/tree/status gate
before any further Git operation.

## Worktree source provenance

When a virtual environment belongs to one checkout but is used to run code from
a different worktree, the editable installation inside that environment may
otherwise resolve `trading_bot` from the wrong checkout. Pytest's configured
`pythonpath = ["src"]` protects normal pytest collection, but it does not protect
standalone `python -c`, module, script, Ruff, or operator invocations.

For a standalone provenance probe, bind the expected source root only inside
that one Python process instead of exporting persistent `PYTHONPATH`. Nontrivial
Python under PowerShell must be delivered through a single-quoted here-string on
stdin rather than `python -c`. For the current personal-desktop worktree:

```powershell
Set-Location 'F:\AI\worktrees\ai-trading-bot-personal-desktop'

@'
import sys
from pathlib import Path

root = Path(
    r'F:\AI\worktrees\ai-trading-bot-personal-desktop\src'
).resolve()

sys.path.insert(0, str(root))

import trading_bot

module = Path(trading_bot.__file__).resolve()
assert root in module.parents, (root, module)
print(module)
'@ | & 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -
```

The printed module path must be under the expected worktree `src` tree. An
assertion failure is an environment/provenance STOP: do not continue tests,
operator commands, or certification against an ambiguous import source.

Apply the same pattern to other worktrees by changing only the explicitly
selected worktree path. Do not mutate the shared virtual environment or rely on
its editable-install target as source authority for another worktree.

## PowerShell and Git checkpoint style

Routine bounded checkpoints performed by Codex should stay simple and explicit.
The task prompt should name the exact worktree, branch, expected HEAD/tree,
intended remote ref, intended paths, and whether commit/push is authorized. A
typical authorized sequence is:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git rev-parse origin/<feature-branch>
git diff --cached --name-only
git add -- path/to/one.py path/to/test.py
git diff --cached --name-only
git diff --cached --check
git commit -m "..."
git push origin <feature-branch>
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git rev-parse origin/<feature-branch>
git status --short
```

The initial staged-file check must prove the index is empty before Codex adds
files. If branch/worktree/HEAD/tree/origin/index state differs from the frozen
startup gate, Codex stops instead of self-correcting.

Use larger defensive scripts only when a security-sensitive deployment,
production authority gate, or unusually fragile operator operation genuinely
requires them.

### Windows/PowerShell command robustness

Windows operator commands are part of the reviewed control surface. Keep their
syntax deliberately boring and parser-stable:

- nontrivial Python under PowerShell uses a single-quoted here-string piped to
  `python -B -`; do not use `python -c` for multiline, quote-heavy, path-heavy,
  or security-sensitive probes;
- inline Python text containing Windows paths must use raw string literals or
  escaped backslashes so diagnostic commands do not emit invalid-escape
  warnings that can hide real output;
- PowerShell .NET calls should use simple intermediate assignments instead of
  parser-fragile multiline type/cast expressions;
- after any PowerShell parser error, do not treat later commands in the pasted
  block as having passed the failed prerequisite; restart from a clean,
  explicitly fenced checkpoint;
- protected-effect commands and their read-only preflights remain separate, and
  the preflight must prove its own Administrator/source/host admission rather
  than relying on a prior shell variable that may not have been assigned;
- structured diagnostic or operator logic belongs in a reviewed `.ps1`/`.py`
  file or a stdin Python block; PowerShell should remain a short launcher and
  exact-state fence.

These rules are mandatory for generated ChatGPT/Codex operator instructions,
not just repository scripts.

## Parallel worktrees

Separate feature worktrees may remain active simultaneously. Every task must
operate only in the explicitly named worktree and branch. Do not switch, clean,
reset, delete generated artifacts from, or otherwise disturb another active
worktree as part of a scoped task.

## Safety and prohibited operations without explicit approval

The following remain prohibited unless the current task explicitly authorizes
them:

- merge;
- rebase;
- amend;
- force-push;
- PR metadata changes;
- review-thread resolution;
- unrelated file edits/deletions;
- production/provider external effects;
- credential-store reads/writes outside an approved gate;
- production authority database mutation outside an approved gate;
- deployment outside an approved deployment checkpoint.

Routine exact-file staging, normal commit, and ordinary feature-branch push are
permitted when the current bounded task explicitly authorizes that checkpoint.
They do not imply authorization for any operation in the prohibited list above.

External-effect prerequisites and no-effect preflight must remain separate from
any command that can cross an effect fence. A consumed `CONFIRMED` or
`MAY_HAVE_OCCURRED` lineage is never retried by manufacturing a new execution of
the same consumed authority.


## Combined Ruff diagnostic rule

When ChatGPT supplies an operator verification gate that checks both Ruff lint
and Ruff formatting, the gate must collect both results before failing. The
canonical pattern is:

```powershell
& $Python -m ruff check --no-cache @Files
$RuffCheckExit = $LASTEXITCODE
if ($RuffCheckExit -ne 0) {
    & $Python -m ruff check --diff --no-cache @Files
}

& $Python -m ruff format --check --no-cache @Files
$RuffFormatExit = $LASTEXITCODE
if ($RuffFormatExit -ne 0) {
    & $Python -m ruff format --diff --no-cache @Files
}

if ($RuffCheckExit -ne 0 -or $RuffFormatExit -ne 0) {
    throw 'STOP: Ruff verification failed'
}
```

Both diagnostics are non-mutating. A lint failure must not prevent the formatter
check from running, because `ruff check` and `ruff format --check` validate
different contracts. Do not use `--fix` or run an in-place formatter merely to
diagnose an operator gate failure.

## Unified checkpoint runner

Architecture 129 replaces routine one-off verification scripts with the
checked-in repository launcher and runner:

```powershell
.\ops.ps1 status
.\ops.ps1 verify arch128-parent-acl-repair
.\ops.ps1 verify arch128-r4
.\ops.ps1 preflight arch128-parent-acl-repair
.\ops.ps1 preflight arch128-r4
.\ops.ps1 execute arch128-parent-acl-repair
.\ops.ps1 execute arch128-r4
.\ops.ps1 preflight arch128-r5-substrate
.\ops.ps1 preflight arch128-r5-trading
.\ops.ps1 verify arch128-r6
.\ops.ps1 verify arch128-r7
.\ops.ps1 preflight arch128-r7
```

`ops.ps1` is intentionally a thin launcher. Source-gate orchestration,
combined Ruff diagnostics, evidence capture, and checkpoint authority checks
belong in `scripts/checkpoint_runner.py`.

For registered checkpoints, this runner is the default source-verification
surface. New generated PowerShell verification scripts are fallback-only and
must not be used merely because a checkpoint needs another lint, formatting,
AST, or read-only diagnostic pass.

GitHub Actions runs the same launcher on Windows/Python 3.14. Source-only gates
should normally be satisfied by CI rather than asking the user to rerun the
same pytest/Ruff/diff checks locally.

Local Windows work remains necessary for host-specific qualification such as
ACLs, Task Scheduler, real account tokens, and protected filesystem state. Those
operations use the runner's registered `preflight` layer and, only where
separately source-reviewed, checkpoint-specific protected `execute` dispatches.
The current protected dispatches are limited to
`arch128-parent-acl-repair` and `arch128-r4`. A source or preflight PASS never
grants protected production authority; a fresh explicit approval and the exact
reviewed authorization interlock remain mandatory.

Checkpoint evidence is external to the repository. The preferred development
host root is `F:\AI\temp\ai-trading-bot-checkpoints`; CI uses its runner
temporary directory and uploads the evidence artifact.

When a registered gate fails, improve the checked-in runner/observer so the
same failure class produces useful structured diagnostics on the next run.
Do not create a chain of temporary diagnostic scripts for behavior that belongs
in the reusable checkpoint implementation.



A checkpoint may pin a live remote branch for host preflight. In that case the
runner permits a clean detached operator worktree and uses read-only
`git ls-remote` to prove the local HEAD equals the exact live remote branch
HEAD. This is preferred when preserving an older dirty or failed development
worktree is safer than reconciling it merely to run host qualification.
