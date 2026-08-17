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

- ChatGPT is the default architecture, milestone-planning, pull-request review, broad audit, merge-readiness, and transition-planning agent.
- Codex is primarily an implementation agent for changes already scoped and discussed.
- Do not ask Codex to perform a broad PR review or repository-wide audit unless the task explicitly requests one.
- For implementation tasks, read this file, `docs/PROJECT_STATUS.md`, and only the architecture documents relevant to the requested change.
- Do not re-investigate settled architecture decisions unless implementation exposes a concrete contradiction or blocker.
- Keep implementation prompts narrow and avoid broad repository scans when relevant files and architecture documents are already known.
- Keep implementation reports to files changed, verification commands/results, and deviations or unresolved concerns.

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
