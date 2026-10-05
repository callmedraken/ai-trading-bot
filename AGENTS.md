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
- Use the Architecture 132 certification tiers below. FULL certifies currently supported functionality; LEGACY/EXHAUSTIVE are explicit compatibility gates, not routine checkpoint requirements.
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

## Tiered certification policy

Architecture 132-R1 separates current product certification from retained
historical compatibility. See `docs/architecture/132-tiered-certification-profiles.md`
for reviewed ownership and the frozen FULL/Robinhood baselines (113/40 modules).

- **FOCUSED:** every implementation/correction; Codex runs affected tests and
  focused checks.
- **SOURCE-GATE CI:** every pushed registered checkpoint; retain the existing
  registered GitHub source-gate batching.
- **ROBINHOOD:** when ChatGPT declares a coherent Architecture 131 integration
  boundary, before protected Robinhood qualification, and after material changes
  to shared domain/execution/ledger/risk foundations used by Architecture 131.
  `--profile robinhood` preserves the 40-module baseline in two nonempty balanced
  lanes. Missing/renamed baseline modules fail closed; new owned tests enter
  automatically.
- **FULL:** the default `--profile full` certifies all CURRENTLY SUPPORTED
  functionality in exactly two nonempty balanced lanes, with no historical
  Windows serial lane. Use after certification-topology changes, at coherent
  current-product boundaries, before major develop/release integration or
  consequential production/live-readiness transitions, after sufficiently broad
  supported shared-core changes, or when ChatGPT determines accumulated
  checkpoints warrant comprehensive current-product regression. FULL is not
  mechanically tied to every Architecture 131 letter/checkpoint.
- **LEGACY / EXHAUSTIVE:** only when explicitly relevant. LEGACY retains retired
  architecture; EXHAUSTIVE covers every discovered repository test and preserves
  the previous three-lane all-repository topology. Use for changes to legacy
  architecture, interpreter/dependency migrations spanning both eras, broad
  repository restructuring, deliberate legacy removal, or explicit backward
  compatibility investigation. Both retain the exact historical five-module
  serial lane. Normal current-product certification does not require them.
- **PROTECTED:** always separate fresh authorization. No source profile grants
  native Windows acceptance, provider/Robinhood/OAuth access, broker effects, or
  production effects; all profiles reject protected opt-ins.

FULL and LEGACY are disjoint and together equal EXHAUSTIVE; Robinhood is a
subset of FULL. Freeze the 113-module supported and 40-module Robinhood
baselines. New modules in supported whole-directory families are automatically
admitted. Unknown ownership fails closed and requires an explicit support-status
decision; it must never silently default to legacy.

D10/Windows/Paper-v2/Alpaca operational paths are historical compatibility.
The current pre-Robinhood GUI implementation is legacy because it is tied to
the retired operational artifact/runtime model. GUI remains a future product
goal; a Robinhood-integrated GUI milestone must explicitly reclassify or replace
that implementation.

All profiles retain whole-repository Ruff check/format and `git diff --check`,
exact source/remote admission and final verification, JUnit/evidence validation,
and external temporary-root requirements. ChatGPT chooses the appropriate tier
after exact GitHub code review and source acceptance; users normally run local
certification. The normal handoff remains implementation + focused checks ->
exact-file commit/push -> ChatGPT exact GitHub code review -> source acceptance
-> appropriate certification tier -> docs closeout. The certification workflow
is FOCUSED -> SOURCE-GATE CI -> ROBINHOOD when appropriate -> FULL at coherent
current-product boundaries -> LEGACY/EXHAUSTIVE only when explicitly relevant,
with PROTECTED separately authorized.

## AI development workflow

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
- A known ChatGPT-direct bounded-commit lag is a reviewed synchronization case, not an unexpected-state repair: when ChatGPT has directly advanced the exact remote branch through one or more explicitly reviewed, tightly scoped commits (including routine docs/status/handoff closeout or a tiny mechanical source/test/workflow correction), and admission proves the local worktree is on the exact expected branch, tracked/index-clean, at the exact known pre-direct-change HEAD, while the remote is at the exact reviewed direct-change HEAD and the local HEAD is its ancestor, fast-forward the local branch only (`git fetch` plus `git merge --ff-only`, or an equivalent `git pull --ff-only`) before any next local/Codex work. Any different local/remote state is a STOP. Afterward verify local HEAD/tree == remote expected HEAD/tree and tracked/index-clean, then continue automatically into the next safe checkpoint.
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

This serialization rule does not override a protected operator contract that
explicitly requires real interactive terminal stdin. In that case, do not pipe
or redirect the human authorization input and do not automate the terminal gate;
use stdin/file transport only for the surrounding diagnostic data that the
reviewed contract permits.

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

### Atomic ChatGPT-direct multi-file repository writes

A logical ChatGPT-direct checkpoint that changes two or more repository files
MUST be published as one atomic Git commit and one branch-ref update/push. This
includes the ordinary case where one accepted milestone updates
`docs/PROJECT_STATUS.md`, `docs/AI_TRADING_BOT_HANDOFF.md`, a relevant
architecture/validation document, and/or workflow documentation together.

Sequential GitHub Contents-API writes that each create a commit and advance the
same branch are prohibited for one logical checkpoint. They create unnecessary
intermediate remote states and redundant push-triggered CI runs. If the active
tool path cannot create the required multi-file commit atomically, STOP and use
another supported path (for example Git blobs/tree/commit plus one leased ref
update, or one local exact-file commit/push). Do not fall back to sequential
single-file branch-advancing writes merely because they are convenient.

The required publication sequence is:

1. prove the exact expected remote parent HEAD/tree;
2. compose all intended file contents against that same parent;
3. create any blobs/tree/commit without advancing the branch;
4. verify the commit contains exactly the intended file set;
5. advance the branch exactly once with the expected-parent lease;
6. verify the exact final remote HEAD/tree and changed-file set; and
7. treat that one branch advance as the one push-triggered source-gate event for
   the logical checkpoint.

A separately triggered `pull_request` workflow run caused by opening/updating a
PR is expected and is not a violation; the invariant is one **push-triggered**
CI run per logical ChatGPT-direct checkpoint.

Multiple branch-advancing commits/pushes are allowed only when the work is
deliberately split into distinct review checkpoints with independently useful
accepted states. ChatGPT must state that reason before the first push. A tool
limitation is not such a reason. If an unexpected partial remote state already
exists, stop and classify/review it before any further branch update rather than
continuing a sequential-write chain.

## Unified checkpoint runner

For checkpoints registered by Architecture 129, use the repository-root
`ops.ps1` launcher and `scripts/checkpoint_runner.py` instead of generating a
new PowerShell verification wrapper.

Current registered examples:

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

The `execute` surface is protected, checkpoint-specific, and never implied by a
source/preflight PASS. It may be invoked only after fresh explicit approval at
the effect boundary and with the checkpoint's exact reviewed authorization
interlock.

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

