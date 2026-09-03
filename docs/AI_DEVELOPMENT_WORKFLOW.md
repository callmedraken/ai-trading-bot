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
than waiting for the user to ask what to do next.

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

Use the smallest model class appropriate to the contract:

- **Luna Extra High** — localized, mechanical, or frozen-contract work;
- **Sol Medium** — subtle but bounded implementation;
- **Sol High** — native Windows/security, authority, ordering, crash/recovery,
  credential/reference-version, external-effect containment, or
  architecture-sensitive work.

Do not use subagents unless explicitly requested.

## Standard bounded implementation cycle

The normal cycle is:

```text
ChatGPT scopes/finalizes the contract and explicitly authorizes the checkpoint
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

Milestone and verification reports should always include the next recommended
step.

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
