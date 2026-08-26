# AI Trading Bot

AI Trading Bot is a conservative algorithmic trading platform being developed
through staged historical research, simulated paper trading, broker-paper
operation, and eventually explicitly enabled restricted live trading.

The project is intentionally safety-first. Strategies and AI produce proposals;
deterministic risk, authority, execution, reconciliation, and operator-control
boundaries decide what may actually happen.

## Current status

Milestone C2 is complete. The repository already includes deterministic domain,
risk, execution, portfolio/ledger, historical market-data, market-calendar,
single- and multi-symbol backtesting, strategy, optimization, analytics,
research, paper-operation, recovery, and Windows production-authority
infrastructure.

The current milestone is **C3: effectful market-data capture**. C3 will connect
the reviewed C2 transactional authority to a real, contained capture boundary
with approved provider transport, reviewed credential retrieval, Windows child
process containment, durable process/effect evidence, captured-content
verification, and native Windows acceptance.

**Production/live trading remains NO-GO.** The project does not yet provide a
live brokerage execution path, unattended live operation, or authorization to
place real-money orders.

See [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) for the canonical current
milestone, roadmap, production status, and final product-completion goal.

## Product direction

The long-term progression is:

1. Complete the effectful market-data capture boundary.
2. Establish a reliable manual paper cycle from verified snapshot through strategy, deterministic risk, paper execution, and durable evidence.
3. Add unattended paper operation, authoritative scheduling, reconciliation, monitoring, and recovery.
4. Complete a long paper soak.
5. Add broker-paper integration with real broker identifiers, submit/cancel/replace, partial fills, rejects, reconciliation, idempotency, and ambiguous-submit recovery.
6. Add explicit live-readiness controls, separate live credentials, account verification, kill switch, strict risk limits, outage/stale-data behavior, and startup reconciliation.
7. Permit only a tiny restricted live deployment after all acceptance gates are satisfied.
8. Deepen AI/strategy capabilities only after operational safety and reconciliation are trustworthy.
9. Finish the product with a polished, user-friendly GUI for research, backtesting, account/portfolio views, paper/live operations, system health, recovery, audit history, settings, and safety controls.

The GUI is a presentation and operator-control layer. It must use the same
reviewed application/service boundaries as CLI, automation, and tests and may
never bypass deterministic risk, authority, brokerage, reconciliation, or live
mode gates.

## Safety model

- Paper trading is the default operating mode.
- Live trading is a future, separately enabled integration.
- All order requests pass through deterministic risk validation.
- Credentials and private keys must never be hard-coded, logged, printed, or committed.
- Real external effects require durable authority/evidence and fail closed when required state is absent or invalid.
- Initial product constraints remain long-only US stocks/ETFs with no margin, options, short selling, or crypto.

## Environment setup

Python 3.12 or newer is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On macOS or Linux, activate the environment with:

```bash
source .venv/bin/activate
```

## GUI

Install the development and GUI dependencies with:

```powershell
python -m pip install -e ".[dev,gui]"
```

Launch the native GUI with:

```powershell
python -m trading_bot.gui
```

Optionally open one local compact report at startup:

```powershell
python -m trading_bot.gui --research-report PATH
```

The current GUI scope is local, read-only research presentation and bounded
variant comparison. It does not connect to production authority, credentials,
Alpaca or other provider transport, brokerage, or paper/live execution.

Project commands should run inside the project virtual environment. On Windows,
you can also invoke its interpreter explicitly:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Testing

Run focused tests while iterating. The complete repository suite is reserved
for final milestone/release certification or when explicitly required by the
current task.

From the repository root with the environment activated:

```powershell
python -m pytest
```

Without activation on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Some native Windows acceptance tests are intentionally opt-in and require the
specific production/disposable environment described by their validation
plans; portable unit tests do not replace those acceptance gates.
