# AI Development and Review Workflow

This document is the canonical working agreement for AI-assisted development in
this repository. `AGENTS.md` remains the mandatory repository rule set; this
file records the normal handoff, review, testing, and local-operator cycle in
more detail.

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
-> user runs broader/full local certification only when ChatGPT says the
   reviewed source has reached the final certification gate
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

## Docs-only closeout local catch-up

When ChatGPT directly creates accepted docs/status/handoff closeout commits on
the active remote feature branch, the local worktree may intentionally be one
or more reviewed docs-only commits behind. That expected state is not treated
as a generic mismatch to repair.

Before any next local or Codex work:

1. enter the exact intended worktree and prove the tracked worktree/index is
   clean;
2. prove the current local branch is the expected branch;
3. fetch the exact remote branch;
4. prove the remote HEAD is the exact reviewed docs-closeout HEAD;
5. prove the local HEAD is either already that HEAD or the exact known
   pre-closeout accepted HEAD and an ancestor of the reviewed remote HEAD;
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

This is the narrow exception that reconciles the startup STOP rule with direct
remote docs closeouts: fast-forward synchronization is mandatory only after the
exact known docs-only-behind state has itself been proven.

## Testing and certification

During iteration:

- Codex runs focused tests/checks for changed behavior;
- do not repeatedly run the complete repository suite;
- do not run long integration/E2E or production acceptance gates unless they are
  part of the explicitly requested checkpoint;
- if a broad local run fails, diagnose the affected area and rerun only focused
  tests after the bounded fix.

At the final source-certification boundary:

- ChatGPT supplies the exact local commands;
- the user runs the broad/full suite once, plus required lint/format/diff and
  frozen-artifact identity checks;
- do not request broad/full certification until exact remote/PR review has established that the current executable/source tree is intended to be final; review-driven source corrections return to focused verification first;
- if the environment invalidates the run, repair the environment first and do
  not treat the resulting cascade as a source defect;
- after a clean certification, do not rerun the full suite unless source code
  changes.

The accepted complete-certification topology uses three concurrent, explicit
pytest processes: two file-level broad lanes and one serial safety lane. The
five current serial modules are a conservative safety boundary:

```text
tests/runtime/test_windows_transactional_capture_authority.py
tests/runtime/test_windows_authority_schema.py
tests/runtime/test_windows_authority.py
tests/runtime/test_windows_effectful_capture_native_acceptance.py
tests/acceptance/test_windows_authority_provisioning_acceptance.py
```

Architecture-77 remains serial; unrestricted parallel safety has not been
established. `scripts/run_test_certification.py` admits an exact clean source
identity, proves full module coverage and disjoint partitions, saves the plan,
and runs the lanes with separate temporary directories and evidence. Use its
`--plan` mode to inspect a clean checkout without launching pytest. During
iteration, run only focused verification; complete certification follows exact
GitHub/PR review when the source tree is intended final. A merge needs no
second complete run when its resulting tree exactly equals the certified tree.

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
