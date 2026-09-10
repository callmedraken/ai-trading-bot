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

When the next action is known, ChatGPT should provide it automatically rather
than waiting for the user to ask what to do next. Tiny, tightly scoped status,
handoff, and workflow-documentation closeouts should normally be handled
directly by ChatGPT rather than delegated to Codex.

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
-> ChatGPT chooses Luna / Astra / Sol High from the routing rules above
-> Codex implements
-> Codex runs focused tests/checks
-> Codex verifies the index is initially clean
-> Codex exact-file stages only the intended paths
-> Codex verifies the staged filename set and runs git diff --cached --check
-> Codex creates a normal checkpoint commit
-> Codex ordinary-pushes the isolated feature branch
-> Codex reports files, focused verification, commit SHA/push result, and blockers
-> ChatGPT reviews the exact GitHub commit/diff
-> user runs the broader/full local certification only when ChatGPT says the
   reviewed source has reached the final certification gate
-> ChatGPT accepts/rejects certification and supplies the next milestone
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
- if the environment invalidates the run, repair the environment first and do
  not treat the resulting cascade as a source defect;
- after a clean certification, do not rerun the full suite unless source code
  changes.

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

Milestone and verification reports should always include the next recommended
step.

## Worktree source provenance

When a virtual environment belongs to one checkout but is used to run code from
a different worktree, the editable installation inside that environment may
otherwise resolve `trading_bot` from the wrong checkout. Pytest's configured
`pythonpath = ["src"]` protects normal pytest collection, but it does not protect
standalone `python -c`, module, script, Ruff, or operator invocations.

For a standalone provenance probe, bind the expected source root only inside
that one Python process instead of exporting persistent `PYTHONPATH`. For the
current personal-desktop worktree:

```powershell
Set-Location 'F:\AI\worktrees\ai-trading-bot-personal-desktop'
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -c "import sys,pathlib; root=pathlib.Path(r'F:\AI\worktrees\ai-trading-bot-personal-desktop\src').resolve(); sys.path.insert(0,str(root)); import trading_bot; module=pathlib.Path(trading_bot.__file__).resolve(); assert root in module.parents, (root,module); print(module)"
```

The printed module path must be under the expected worktree `src` tree. An
assertion failure is an environment/provenance STOP: do not continue tests,
operator commands, or certification against an ambiguous import source.

Apply the same pattern to other worktrees by changing only the explicitly
selected worktree path. Do not mutate the shared virtual environment or rely on
its editable-install target as source authority for another worktree.

## PowerShell and Git checkpoint style

Routine bounded checkpoints performed by Codex should stay simple and explicit.
The task prompt should name the exact worktree, branch, expected HEAD, intended
paths, and whether commit/push is authorized. A typical authorized sequence is:

```powershell
git status --short
git diff --cached --name-only
git add -- path/to/one.py path/to/test.py
git diff --cached --name-only
git diff --cached --check
git commit -m "..."
git push origin <feature-branch>
git rev-parse HEAD
git status --short
```

The initial staged-file check must prove the index is empty before Codex adds
files. If branch/worktree/HEAD/index state differs from the frozen startup gate,
Codex stops instead of self-correcting.

Use larger defensive scripts only when a security-sensitive deployment,
production authority gate, or unusually fragile operator operation genuinely
requires them.

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
