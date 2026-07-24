In Code Mode, within each bounded stage, run independent, functions.exec-available tool calls concurrently in one functions.exec call. 
Use await Promise.allSettled([...]) when partial results are useful, and inspect every result; use await Promise.all([...]) 
only when any failure should abort the batch. Keep dependencies, waits/resumes, approvals, conflicting or interdependent mutations, 
and adaptive investigations where each result may change the next step sequential. Do not split otherwise batchable inspections across outer tool calls.


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

## Development workflow

- Work on one focused feature at a time.
- Create or update tests with every behavioral change.
- Run the complete test suite before reporting completion.
- Summarize files changed, tests run, and unresolved concerns.
- Do not silently modify unrelated files.
- Prefer small, reviewable changes.
- Use type hints for public Python functions.
- Use dataclasses or typed models for financial entities.
- Use Decimal for money where appropriate.
- Store timestamps in UTC.
- Avoid look-ahead bias in backtests.
- Do not treat missing market data as zero.
- Prefer clear and testable code over complicated abstractions.

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

Do not commit secrets, virtual environments, market-data caches, logs,
database files, or generated reports.