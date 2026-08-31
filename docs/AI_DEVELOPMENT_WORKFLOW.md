# AI Development and Review Workflow

This document is the canonical working agreement for AI-assisted development in
this repository. `AGENTS.md` remains the mandatory repository rule set; this
file records the normal handoff, review, testing, worktree, Windows operator,
and production-deployment cycle in more detail.

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
- preserve unrelated generated/untracked files and historical pytest scratch;
- report files changed, focused commands/results, and deviations/blockers;
- normally stop before commit/push and before broad local certification unless
  the task explicitly says otherwise.

## Model selection

Use the smallest model class appropriate to the contract:

- **Luna Extra High** — localized, mechanical, docs-only, or frozen-contract
  work;
- **Sol Medium** — subtle but bounded deterministic implementation;
- **Sol High** — native Windows/security, authority, ordering, locking,
  crash/recovery, credential/reference-version, external-effect containment, or
  architecture-sensitive work.

Do not use subagents unless explicitly requested.

## Standard bounded implementation cycle

The normal cycle is:

```text
ChatGPT scopes/finalizes the contract
-> Codex proves the exact startup gate
-> Codex implements in the explicitly named worktree/branch
-> Codex runs focused tests/checks using the required isolated test environment
-> Codex returns its final report without broad certification
-> user creates/pushes a reviewable exact Git checkpoint when instructed
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

## Non-compressible execution safeguards

Token-efficient prompts may refer to architecture documents instead of repeating
settled background. They must not compress away operational safety gates.

Every bounded implementation/correction prompt must explicitly retain, when
applicable:

- exact worktree path;
- exact branch;
- exact expected starting HEAD;
- mandatory stop-on-mismatch behavior;
- prohibition on self-correcting Git state;
- focused-test versus broad-certification ownership;
- Windows pytest scratch isolation;
- exact-file staging rules;
- commit/push authorization state;
- relevant production/provider/credential/effect prohibitions.

These requirements are execution invariants, not background prose.

## Worktree and branch guard

Multiple active worktrees are normal. Worktree identity is part of the task
contract, not an incidental local detail.

Before any Codex implementation/correction, local certification, packaging, or
release artifact build with a frozen checkpoint, run:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
```

Compare the outputs to the exact expected worktree, branch, and HEAD supplied by
the task. When an upstream is part of the task contract, prove it separately.

If any required value differs, **STOP before reading/modifying source or running
state-changing Git commands**. Report actual versus expected. Do not attempt to
repair the mismatch by:

- checkout/switch;
- reset;
- rebase;
- clean;
- branch deletion/recreation;
- worktree creation/move/deletion;
- force updates;
- copying source between worktrees.

Git-state recovery is a separate operator decision.

Do not infer the intended branch from a Codex chat/project title. A dedicated
Codex project should point at the dedicated worktree for long-running feature
tracks.

Known Architecture-94 paper-cycle routing at the P2 closeout checkpoint:

```text
paper worktree:       F:\AI\ai-trading-bot-paper
paper branch:         feature/reliable-manual-paper-cycle
paper upstream:       origin/feature/reliable-manual-paper-cycle
integration worktree: F:\AI\ai-trading-bot-integration
GUI worktree:         F:\AI\ai-trading-bot
```

New isolated worktrees may use `F:\AI\worktrees\<name>` prospectively. Existing
historical worktrees/evidence paths are not moved merely for tidiness.

Do not clean, reset, prune, or otherwise disturb another worktree as part of a
scoped task. Preserve unrelated generated/untracked reports and historical
pytest directories.

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
- if the environment invalidates the run, isolate the environment first and do
  not treat the resulting cascade as a source defect;
- after a clean certification, do not rerun the full suite unless source code
  changes.

Milestone and verification reports should always include the next recommended
step.

## Windows pytest scratch and environment recovery

Windows pytest scratch failures are an environment classification problem until
a source assertion demonstrates otherwise.

The project has repeatedly encountered an inaccessible user-temp hierarchy:

```text
C:\Users\John\AppData\Local\Temp\pytest-of-John
```

For this Windows development environment, controlled focused, integration, and
certification pytest gates **must** use a fresh explicit external basetemp beneath:

```text
F:\AI\temp\pytest\
```

For example:

```powershell
python -m pytest -q `
  --basetemp "F:\AI\temp\pytest\<milestone>-<gate>-<unique-run>" `
  -p no:cacheprovider `
  <focused-tests>
```

Use `-p no:cacheprovider` when pytest cache behavior is irrelevant to the gate.
A task testing cache behavior may explicitly opt back in.

Rules:

- every controlled Windows pytest gate uses a fresh unique external
  `--basetemp`;
- do not fall back to the default `%TEMP%` pytest hierarchy;
- new tests must use pytest `tmp_path`/`tmp_path_factory` or another explicitly
  supplied disposable root rather than intentionally using the worktree
  `.pytest_cache` as general filesystem scratch;
- do not delete, take ownership of, chmod, repair, or casually move historical
  `.pytest_cache` or pytest temp directories merely to make a gate run;
- preserve permission-warning pytest directories unless a separate cleanup task
  explicitly owns them;
- a successful isolated-basetemp run supersedes a prior user-temp fixture failure
  for source classification;
- cache-provider warnings are not source failures when cache persistence is not
  part of the requested gate;
- do not print a success message after a failed filesystem command; use
  `$ErrorActionPreference = 'Stop'`, `-ErrorAction Stop`, or explicit exit-code
  checks when the command is a gate.

Legacy/native harnesses may still contain hard-coded `.pytest_cache` scratch.
That is a harness constraint, not permission to mutate retained cache state. If a
legacy harness cannot run from the reviewed worktree:

1. do **not** repair/delete the inaccessible cache merely for the test;
2. when the current milestone owns the harness, prefer correcting it to use
   pytest-managed temporary paths;
3. otherwise use a previously validated clean harness worktree only when the
   architecture/test contract permits it;
4. force `PYTHONPATH` to the exact reviewed source worktree;
5. print and require affected module `__file__` provenance before the run;
6. restore `PYTHONPATH` afterward and re-prove the reviewed worktree/checkpoint.

Architecture-94 P2 historically required the clean-harness fallback: its focused
P2 file passed 48 cases using an external basetemp, while five selected C2 nodes
expanded to 77 cases and passed from the integration harness only after import
provenance proved the exact P2 source was under test. That history explains the
fallback; it is not the default for new tests.

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

The production host currently uses Windows PowerShell 5.1 for operator gates.
Do not assume PowerShell 7 parameter compatibility. In particular,
`New-Item -LiteralPath` is not accepted by Windows PowerShell 5.1. For exact
write-denial/temp probes, prefer `[System.IO.File]` APIs or a command form proven
compatible with Windows PowerShell 5.1. A shell syntax/parameter failure is an
operator-command defect and must not be classified as an application failure.

## Production runtime trust contexts

Keep development, deployment, and production-runtime validation in separate
trust contexts:

1. **normal development account** — Git/worktree/source/test/release-artifact
   checks;
2. **elevated Administrator** — sealed fixed-runtime inspection, Trading RX
   revocation/republication, offline wheel replacement, ownership/ACL
   normalization;
3. **non-elevated `DESKTOP-I4DOKM7\Trading`** — genuine production C1
   acquisition and approved runtime/authority acceptance.

Do not mix these contexts. The normal development account may receive
`Access is denied` for `F:\AITradingBot\runtime`; that can be the intended ACL
boundary and is not evidence that the runtime is missing.

Before a production acceptance that depends on newly reviewed source, first
inspect the fixed runtime from the appropriate read-only/admin context and prove
where `trading_bot` imports from. Never assume that a newly accepted development
commit is already deployed.

If the fixed runtime is stale:

- do not copy source files into `site-packages` ad hoc;
- export the exact reviewed Git commit into a detached source directory;
- build one frozen wheel from that export;
- prove wheel package bytes exactly match the export and verify all RECORD
  hashes;
- record source commit/tree, wheel path, byte length, and SHA-256;
- re-prove the wheel immediately before installation;
- require runtime quiescence;
- revoke the exact Trading RX publication before replacement and prove Trading
  access is absent;
- install offline with `--no-index --no-deps --no-cache-dir --force-reinstall`;
- reconcile every hashed installed RECORD payload;
- compare security/authority-sensitive installed modules with frozen source;
- re-prove frozen production SQL and SQLite build expectations;
- normalize Administrators ownership and verify the sealed ACL topology;
- only then republish the exact inheritable Trading Read & Execute rule;
- run a separate non-admin Trading zero-provider preflight before any production
  read/effect acceptance.

Release paths and prior artifacts are evidence. If a chosen export/wheelhouse or
quarantine path already exists, stop or use a new reviewed suffix; do not delete
or overwrite it casually.

## Production effect and reread separation

External-effect prerequisites and no-effect preflight must remain separate from
any command that can cross an effect fence. A consumed `CONFIRMED` or
`MAY_HAVE_OCCURRED` lineage is never retried by manufacturing a new execution of
the same consumed authority.

A later read-only verification of already-durable evidence is not a provider
retry. For Architecture-94 P2, the supervised acceptance reread of successful C3
call #6 was allowed only after source review, local gates, frozen-wheel
verification, sealed deployment, Trading RX publication, and a separate
zero-provider preflight. The P2 read proved `provider_call_performed=False`,
`database_mutation_performed=False`, zero Python socket connects, exact database
byte identity, and exact selected-artifact byte identity. It did not authorize
provider call #7.

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

At every accepted milestone, update `docs/PROJECT_STATUS.md` and
`docs/AI_TRADING_BOT_HANDOFF.md`. When a milestone reveals a reusable workflow
failure/recovery pattern, also update this document so the next chat does not
repeat the same unsafe or wasteful detour.
