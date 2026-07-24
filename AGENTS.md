# AI Trading Bot Development Rules

## Project purpose

Build a conservative algorithmic trading research platform.

The system must begin with historical backtesting and simulated paper
trading. Real-money trading must remain unavailable until it is
implemented as a separate, explicitly enabled integration.

## Safety requirements

- Never connect to a real brokerage unless the user explicitly requests it.
- Never request, store, print, or commit brokerage credentials.
- Never implement undocumented or reverse-engineered Robinhood APIs.
- Never place real orders during tests or development.
- Paper trading must be the default operating mode.
- Live trading must require a separate adapter and explicit configuration.
- Live trading must fail closed when configuration is missing or invalid.
- Do not add margin, leverage, options, short selling, or crypto.
- All order requests must pass through deterministic risk validation.
- AI-generated recommendations may not bypass risk rules.
- Every simulated decision and transaction must be auditable.

## Deterministic research requirements

- Domain results must be deterministic for identical inputs.
- Use stable UUID5 identities with explicit, versioned canonical material.
- Never use clocks, UUID4, Python hashes, object identity, locale, filesystem paths, or serialized artifact bytes in deterministic domain identities.
- Decimal calculations and canonicalization must not depend on ambient Decimal context.
- Preserve caller-defined ordering unless a policy explicitly defines another order.
- Downstream analysis must not alter upstream domain identities or report bytes.
- Ranking, pairwise comparison, and Pareto analysis must remain descriptive unless an explicit policy defines otherwise.
- Do not infer winners, recommendations, metric directions, objectives, weights, or scores.

## Development workflow

- Work on one focused feature at a time.
- Create or update tests with every behavioral change.
- Run the complete test suite before reporting completion.
- Do not silently modify unrelated files.
- Prefer small, reviewable changes.
- Use type hints for public Python functions.
- Use dataclasses or typed models for financial entities.
- Use Decimal for money where appropriate.
- Store timestamps in UTC.
- Avoid look-ahead bias in backtests.
- Do not treat missing market data as zero.
- Prefer clear and testable code over complicated abstractions.

## Repository workflow

- Read the relevant architecture documents before changing an established subsystem.
- Reuse existing public domain models, identity conventions, serializers, and exception hierarchies where appropriate.
- Do not import or depend on another module's private helpers or constants.
- Preserve existing deterministic identities and serialized artifact bytes unless a schema change is explicitly approved.
- Run focused tests while iterating and the complete test suite once on the final tree.
- Do not commit unless the user explicitly requests it.
- Keep progress updates minimal; report only when blocked or when implementation is complete.
- Final implementation reports should include only:
  - Files changed
  - Verification commands and results
  - Deviations, limitations, or unresolved concerns

## Architecture boundaries

Separate these responsibilities:

1. Market data
2. Trading strategies
3. Risk management
4. Portfolio accounting
5. Broker execution
6. Backtesting
7. Reporting
8. AI analysis

Strategies must generate trade proposals, not directly execute orders.

The risk manager must approve or reject every proposed order.

Broker implementations must share a common interface.

The initial broker implementation must be simulated only.

## Initial constraints

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

Use feature branches named:

- feature/<feature-name>
- fix/<issue-name>
- Do not commit secrets, virtual environments, market-data caches, logs, database files, or generated reports.

- Generated JSON, CSV, smoke-test, and research reports must remain untracked unless they are explicit test fixtures.
- Never stage, delete, overwrite, or modify unrelated generated reports.
- Test fixtures under `tests/fixtures/` are tracked artifacts and may be changed only as part of an approved schema or serializer milestone.

## Historical evaluation integrity

- Training data may not include observations from its associated test period.
- Test-period data must never influence training selection, configuration, ranking, or optimization.
- Walk-forward folds must be chronological, explicit, and auditable.
- Missing or insufficient data must fail explicitly rather than being imputed silently.