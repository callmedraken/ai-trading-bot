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
- report files changed, focused commands/results, and deviations/blockers;
- normally stop before commit/push and before broad local certification unless
  the task explicitly says otherwise.

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
ChatGPT scopes/finalizes the contract
-> Codex implements
-> Codex runs focused tests/checks
-> Codex returns its final report without committing
-> ChatGPT reviews the report and supplies simple exact PowerShell/Git commands
-> user stages only the intended paths
-> user verifies the staged filename list/diff as appropriate
-> user creates a normal commit and pushes the isolated feature branch
-> ChatGPT reviews the exact GitHub commit/diff
-> user runs the broader/full local certification only when ChatGPT says the
   reviewed source has reached the final certification gate
-> ChatGPT accepts/rejects certification and supplies the next milestone
```

Manual patch-file transfer or pasting a large diff into chat is a fallback only
when GitHub/tool access fails. It is not the normal review path.

For a scoped checkpoint with known paths, do not use `git add .` or
`git add -A`. Stage the exact intended files. Normal feature-branch push does
not authorize merge, rebase, amend, force-push, PR metadata changes, review
thread resolution, or unrelated modifications.

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

Routine local Git checkpoints should stay simple and explicit. Prefer commands
such as:

```powershell
git status --short
git add -- path/to/one.py path/to/test.py
git diff --cached --name-only
git diff --cached --check
git commit -m "..."
git push origin <feature-branch>
git rev-parse HEAD
```

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

External-effect prerequisites and no-effect preflight must remain separate from
any command that can cross an effect fence. A consumed `CONFIRMED` or
`MAY_HAVE_OCCURRED` lineage is never retried by manufacturing a new execution of
the same consumed authority.
