# AI Trading Bot Development Rules

## Project purpose

Build a conservative algorithmic trading platform that progresses through
historical research, simulated paper trading, broker-paper operation, and
eventually explicitly enabled restricted live trading.

Live trading is a long-term project goal, not a current capability. It must
remain unavailable until the separately reviewed brokerage, credential,
reconciliation, operator-control, and live-readiness gates are implemented and
accepted. Paper trading remains the default operating mode.

`docs/PROJECT_STATUS.md` is the canonical high-level source for the current
milestone, completed foundations, roadmap, and production status. Read it before
starting a new milestone or preparing a broad implementation plan.

## Safety requirements

- Never place real-money orders during tests or ordinary development.
- Never hard-code, print, log, or commit credentials, private keys, tokens, or other secrets.
- Credential access may only be added through an explicitly reviewed secret-store boundary required by the current milestone.
- Never implement undocumented or reverse-engineered Robinhood APIs.
- Paper trading must be the default operating mode.
- Live trading must require a separate reviewed adapter, explicit mode authority, and explicit configuration.
- Live trading must fail closed when configuration, account identity, authority, reconciliation, or safety state is missing or invalid.
- Do not add margin, leverage, options, short selling, or crypto unless a later architecture milestone explicitly changes the initial product constraints.
- All order requests must pass through deterministic risk validation.
- AI-generated recommendations may not bypass risk rules, authority boundaries, or execution controls.
- Every simulated, paper, broker-paper, and future live decision and transaction must be auditable.

## Deterministic research requirements

- Domain results must be deterministic for identical inputs.
- Use stable UUID5 identities with explicit, versioned canonical material.
- Never use clocks, UUID4, Python hashes, object identity, locale, filesystem paths, or serialized artifact bytes in deterministic domain identities.
- Decimal calculations and canonicalization must not depend on ambient Decimal context.
- Preserve caller-defined ordering unless a policy explicitly defines another order.
- Downstream analysis must not alter upstream domain identities or report bytes.
- Ranking, pairwise comparison, and Pareto analysis must remain descriptive unless an explicit policy defines otherwise.
- Do not infer winners, recommendations, metric directions, objectives, weights, or scores without an explicit policy.

## Development workflow

- Work on one focused feature or correction group at a time.
- Create or update tests with every behavioral change.
- Run focused tests while iterating.
- Run the complete repository test suite when the task explicitly calls for final milestone/release certification, or when the change is the final tree for the current milestone.
- Do not repeatedly rerun an expensive full suite after every intermediate correction when a narrower certification gate is defined.
- Do not silently modify unrelated files.
- Prefer small, reviewable changes.
- Use type hints for public Python functions.
- Use dataclasses or typed models for financial entities.
- Use Decimal for money where appropriate.
- Store timestamps in UTC.
- Avoid look-ahead bias in backtests.
- Do not treat missing market data as zero.
- Prefer clear and testable code over complicated abstractions.

## AI development workflow

- ChatGPT is the default architecture, milestone-planning, debugging-strategy, GitHub/diff/pull-request review, broad-audit, test-gate, merge-readiness, certification, and transition-planning agent.
- ChatGPT milestone, review, verification, merge, and post-merge responses must automatically include the concrete next recommended step. When the next action is known, include ready-to-run operator commands or a ready-to-paste Codex prompt rather than only naming the milestone.
- After every accepted checkpoint, ChatGPT must automatically review/update `docs/PROJECT_STATUS.md` and `docs/AI_TRADING_BOT_HANDOFF.md` before treating the checkpoint as closed. If no material wording change is needed in one of them, explicitly report that it was reviewed and remains current.
- After every accepted checkpoint, ChatGPT must determine the next milestone, choose ChatGPT/Luna/Astra/Sol High according to these rules, and continue automatically into the next safe docs-only, source-only, design-only, or read-only checkpoint when no protected effect or repository-control approval is required. Stop at the exact approval boundary for production/provider effects, storage provisioning, scheduler mutation, merge/rebase/amend/force-push, PR metadata/review-thread changes, broker/live effects, or other explicitly protected actions.
- ChatGPT may directly implement small, tightly scoped, low-risk mechanical source, test, documentation, status, handoff, or workflow changes when delegation would add overhead without useful isolation. Codex should not receive every implementation task automatically.
- Codex is primarily a bounded implementation agent for changes already scoped and discussed.
- **Luna Extra High** is the default Codex implementation model when the contract is frozen or nearly frozen, the relevant entry points and test surface are already known, and the work is localized/mechanical or a small bounded correction. Prefer Luna for known-file implementation, focused test additions, small refactors under an established contract, and routine docs/help changes.
- **Astra** is the default Codex implementation/diagnostic model when useful work requires repository exploration before coding, the affected file set or root cause is not yet obvious, the change crosses modules/subsystems, or the task is a bounded refactor/migration/hygiene/consistency pass. Astra may also be used for explicitly requested broad read-only repository audits. Astra replaces Sol Medium as the normal middle tier for new Codex work.
- **Sol High** remains the escalation model for native Windows/security, production authority, ordering, crash/recovery, credential/reference-version changes, external-effect containment, broker/live boundaries, or other architecture-sensitive implementation where a mistake could weaken a safety invariant.
- **Sol Medium is no longer part of the default routing ladder.** Use it only when the user explicitly requests it or Astra is unavailable and the task still fits the former subtle-but-bounded tier.
- Practical routing rule: if the contract, entry points, and focused tests are known, start with Luna; if the root cause, affected files, or cross-module consequences must be discovered, start with Astra; if the task changes or implements a security/authority/external-effect invariant, use Sol High.
- Model choice does not transfer architecture or acceptance authority: ChatGPT still owns final architecture, exact diff review, certification, merge/deployment, and next-step decisions.
- Do not ask Codex to perform a broad PR review or repository-wide audit unless the task explicitly requests one.
- For implementation tasks, read this file, `docs/PROJECT_STATUS.md`, and only the architecture documents relevant to the requested change.
- Do not re-investigate settled architecture decisions unless implementation exposes a concrete contradiction or blocker.
- Keep implementation prompts narrow and avoid broad repository scans when relevant files and architecture documents are already known. Astra's broader exploration allowance applies only when discovery is part of the task.
- Keep implementation reports to files changed, verification commands/results, commit/push result when authorized, and deviations or unresolved concerns.
- Codex should run focused tests/checks while implementing. Broad/full repository suites, long integration/E2E suites, release certification, deployment, and operator Windows gates are normally run locally by the user when ChatGPT supplies the exact commands.
- If a broad local certification run fails, diagnose the affected area, make only the bounded correction needed, and run focused verification before asking the user to rerun the broad suite. Do not repeatedly rerun expensive full suites during iteration.
- The normal review handoff for bounded implementation is: Codex implements and runs focused checks; when the task prompt explicitly authorizes the checkpoint, Codex exact-file stages only the intended paths, verifies the staged filename set and diff check, creates a normal commit, and ordinary-pushes the isolated feature branch; ChatGPT then inspects the exact GitHub commit/diff. If commit/push authorization is withheld, Codex stops before those Git operations and reports the local changes.
- Manual patch uploads or pasted large diffs are fallback-only when GitHub/tool review is unavailable; they are not the normal review workflow.
- Routine exact-file staging/commit/ordinary-push operations may be delegated to Codex when the current task explicitly authorizes that checkpoint. This authorization never includes merge, rebase, amend, force-push, PR metadata/review-thread changes, branch switching, or unrelated files.
- Before an authorized Codex commit, verify that the index was initially clean, stage only exact intended paths, verify the staged filename set, and run `git diff --cached --check`. Never use `git add .` or `git add -A` for a scoped checkpoint.
- Before edits, certification, deployment, or operator work in an active worktree, verify the exact worktree path, branch, HEAD, tree, intended origin/remote ref, clean index, and expected worktree state. Any mismatch is a STOP condition; do not self-correct by switching, resetting, cleaning, rebasing, pulling across unexpected history, or deleting artifacts.
- A known docs-only closeout lag is a reviewed synchronization case, not an unexpected-state repair: when ChatGPT has directly advanced the exact remote branch only through accepted docs/status/handoff commits, and admission proves the local worktree is on the exact expected branch, tracked/index-clean, at the exact known pre-closeout HEAD, while the remote is at the exact expected docs-closeout HEAD and the local HEAD is its ancestor, fast-forward the local branch only (`git fetch` plus `git merge --ff-only`, or an equivalent `git pull --ff-only`) before any next local/Codex work. Any different local/remote state is a STOP. Afterward verify local HEAD/tree == remote expected HEAD/tree and tracked/index-clean, then continue automatically into the next safe checkpoint.
- After an ordinary push or an approved merge, verify the exact remote/resulting HEAD and tree plus the expected clean local state before reporting success. A merge does not require rerunning an already-completed broad suite when the exact resulting source tree was previously certified; otherwise use the appropriate final certification gate.
- Preserve unrelated generated/untracked artifacts and historical permission-warning test directories.
- Trading Bot auxiliary worktrees must be created under `F:\\AI\\worktrees\\...`. Do not create or adopt project worktrees under the user profile, including `C:\\Users\\John\\.codex\\worktrees\\...`; override any tool-managed default with an explicit `F:\\AI\\worktrees\\...` path before edits begin. Existing noncanonical worktrees are preserved until a separate clean-state reconciliation/removal step; never force-remove a dirty worktree.
- When multiple worktrees are active, operate only in the explicitly named worktree/branch and never switch, clean, reset, or otherwise disturb another active worktree.
- See `docs/AI_DEVELOPMENT_WORKFLOW.md` for the canonical review/certification cycle.

## Repository workflow

- Read the relevant architecture documents before changing an established subsystem.
- Reuse existing public domain models, identity conventions, serializers, and exception hierarchies where appropriate.
- Do not import or depend on another module's private helpers or constants.
- Preserve existing deterministic identities and serialized artifact bytes unless a schema change is explicitly approved.
- Do not commit or push unless the current task explicitly authorizes it; explicit commit/push authorization in the task prompt satisfies this rule.
- Keep progress updates minimal; report only when blocked or when implementation is complete.
- Never amend, rebase, force-push, resolve review threads, modify PR metadata, or merge unless the task explicitly authorizes that action.

## Architecture boundaries

Keep these responsibilities separated:

1. Market data and market calendar
2. Trading strategies and AI analysis
3. Deterministic risk management
4. Portfolio accounting and ledger state
5. Execution models and broker adapters
6. Backtesting, walk-forward research, and optimization
7. Analytics and reporting
8. Runtime operations, recovery, and scheduling
9. Production authority, credentials, and external-effect containment
10. User interface and operator controls

Strategies generate trade proposals; they do not directly execute orders.

The risk manager approves, resizes, or rejects every proposed order before
execution.

Broker implementations share reviewed interfaces. Simulated and broker-paper
execution remain separate from future live execution.

The graphical interface is a presentation and operator-control layer over
reviewed application/service interfaces, never a second trading engine.

## User interface architecture

A polished, user-friendly graphical application is the final product-completion
goal.

The GUI must not contain independent trading, risk, authority, brokerage,
reconciliation, deterministic identity, or credential logic. GUI actions must
pass through the same reviewed domain, risk, authority, execution, brokerage,
and audit boundaries used by non-GUI operation.

Backtest, simulated paper, broker-paper, and live modes must be clearly
distinguishable. Future live controls must fail closed and must not allow the
GUI to bypass explicit live-mode authorization, deterministic risk controls,
account verification, reconciliation, or emergency-stop controls.

Core trading functionality must remain testable and operable independently of
the GUI. Narrow operator interfaces may be introduced earlier when they are
required for safe operation; the polished unified GUI remains the final product
milestone.

## Initial product constraints

- Python 3.12 or newer
- Long-only US stocks and ETFs
- No margin
- No options
- No short selling
- No crypto
- Daily bars initially
- $10,000 default simulated starting balance
- Human-readable local reports
- pytest for automated testing

## Git workflow

The Windows development machine currently has an older Git installation that
does not support `git switch`. Operator commands for this repository must use
the compatible `git checkout` forms instead:

- existing branch: `git checkout <branch>`
- create a local branch tracking an existing remote branch:
  `git checkout -b <branch> --track origin/<branch>`

Do not emit `git switch` commands unless a later environment check proves the
installed Git supports them.

The main integration branch is `develop`.

Use focused branches such as:

- `feature/<feature-name>`
- `fix/<issue-name>`

Do not commit secrets, virtual environments, market-data caches, logs, database
files, or generated reports.

Generated JSON, CSV, smoke-test, and research reports must remain untracked
unless they are explicit test fixtures. Never stage, delete, overwrite, or
modify unrelated generated reports.

Test fixtures under `tests/fixtures/` are tracked artifacts and may be changed
only as part of an approved schema or serializer milestone.

## Historical evaluation integrity

- Training data may not include observations from its associated test period.
- Test-period data must never influence training selection, configuration, ranking, or optimization.
- Walk-forward folds must be chronological, explicit, and auditable.
- Missing or insufficient data must fail explicitly rather than being imputed silently.


### Combined Ruff diagnostics for operator verification

For local verification gates that run both Ruff lint and Ruff formatting, do
not fail immediately after the first Ruff failure. Run both non-mutating checks,
capture both exit codes, and emit the exact non-mutating diff for every failed
Ruff phase before stopping:

- `python -m ruff check --no-cache ...`, and on failure
  `python -m ruff check --diff --no-cache ...`;
- `python -m ruff format --check --no-cache ...`, and on failure
  `python -m ruff format --diff --no-cache ...`;
- only after both phases have run, STOP if either exit code is nonzero.

This rule prevents an import-order lint failure from hiding formatter-only
differences until a second operator run. Diagnostic commands must remain
non-mutating; never use Ruff `--fix` or an in-place formatter in an operator
verification gate unless a separate source-edit step is explicitly intended.

## Unified checkpoint runner

For checkpoints registered by Architecture 129, use the repository-root
`ops.ps1` launcher and `scripts/checkpoint_runner.py` instead of generating a
new PowerShell verification wrapper.

Current source-only examples:

```powershell
.\ops.ps1 status
.\ops.ps1 verify arch128-parent-acl-repair
.\ops.ps1 verify arch128-r4
```

The unified runner owns the mandatory combined Ruff behavior: both
`ruff check --no-cache` and `ruff format --check --no-cache` run before the
gate decides PASS/FAIL, with non-mutating `--diff` diagnostics for failed Ruff
phases.

GitHub Actions should satisfy routine registered source gates. Ask the user to
run local commands only when the checkpoint depends on actual host state or a
separately approved protected effect.

Generated PowerShell verification/diagnostic scripts are fallback-only for
bootstrap or recovery behavior not yet expressible in the reviewed runner.
Prefer adding a tested registered checkpoint or diagnostic to the runner over
creating another temporary script.

