# AI Trading Bot

AI Trading Bot is a conservative algorithmic trading platform being developed
through staged historical research, simulated paper trading, broker-paper
operation, and eventually explicitly enabled restricted live trading.

The project is intentionally safety-first. Strategies and AI produce proposals;
deterministic risk, authority, execution, reconciliation, and operator-control
boundaries decide what may actually happen.

## Current status

The contained C3 production market-data capture boundary is complete and
certified, PD1 personal-desktop Paper-v2 authority is complete, PD2A account
mutex/admission is complete, and **PD2B supervised paper composition is complete
and source-certified**.

PD2B final certification passed:

```text
4754 passed, 17 expected skips
Ruff check: PASS
Ruff format --check: PASS (430 files)
git diff --check: PASS
worktree/index: clean
```

PD2B now proves the source-only chain from genuine production authority and a
genuine selected C3 snapshot through post-lock Paper-v2 reread, deterministic
P1 strategy planning, exact replay verification, and path-independent
Architecture-67 execution inputs. The prepared Architecture-67 capability stays
private and valid only while the same account mutex remains held.

The current development target is **PD2C: the supervised Architecture-67
execution boundary**. PD2C begins source-only and must remain unable to mutate
the published Paper-v2 account while the production effect gate is false.

**Production/live trading remains NO-GO.** Provider call #7, broker order
submission, unattended operation, the first real Paper-v2 runtime mutation, and
live trading remain unauthorized unless a later reviewed checkpoint explicitly
changes that state.

See [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) for the canonical current
milestone and roadmap, and
[`docs/architecture/104-personal-desktop-supervised-paper-execution-boundary.md`](docs/architecture/104-personal-desktop-supervised-paper-execution-boundary.md)
for the PD2C contract.

## Product direction

The long-term progression is:

1. Complete the PD2 supervised manual paper cycle from verified snapshot and authoritative Paper-v2 account state through deterministic planning/risk/simulated execution, durable transition, receipt, and restart-safe reconciliation.
2. Add supervised crash/recovery validation, then unattended paper operation with authoritative scheduling, reconciliation, monitoring, and recovery.
3. Complete a long simulated-paper soak.
4. Add broker-paper integration with real broker identifiers, submit/cancel/replace, partial fills, rejects, reconciliation, idempotency, and ambiguous-submit recovery.
5. Complete a broker-paper soak and operational-hardening phase.
6. Add explicit live-readiness controls, separate live credentials, account verification, kill switch, strict risk limits, outage/stale-data behavior, and startup reconciliation.
7. Permit only a tiny restricted live deployment after all acceptance gates are satisfied.
8. Deepen AI/strategy capabilities only after operational safety and reconciliation are trustworthy.
9. Finish the product with a polished, user-friendly GUI for research, backtesting, account/portfolio views, paper/live operations, system health, recovery, audit history, settings, and safety controls.

The GUI is a presentation and operator-control layer. It must use the same
reviewed application/service boundaries as CLI, automation, and tests and may
never bypass deterministic risk, authority, brokerage, reconciliation, or live
mode gates.

## Legacy/manual operator tools

Two older manual command surfaces remain intentionally available, but they are
not substitutes for the current production authority chain:

- `scripts/capture_daily_market_snapshot.py` /
  `trading_bot.cli.daily_snapshot_capture` is the Architecture-57 manual Alpaca
  artifact command. It is not the C3 production capture authority and does not
  authorize provider call #7 or any additional production provider effect.
- `trading_bot.cli.paper_operation` is the Architecture-67 generic/manual
  restart-safe paper-operation command and therefore accepts an explicit
  operation root. It is not the Architecture-103/PD2 production composition
  boundary. Production Paper-v2 operation must obtain its runtime root from
  genuine validated personal-desktop paper-account authority and the reviewed
  PD2 admission path.

Changing or disabling either accepted legacy command is a separate behavioral
checkpoint. Their presence does not broaden current production authorization.

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

On macOS or Linux:

```bash
source .venv/bin/activate
```

## GUI

Install GUI dependencies with:

```powershell
python -m pip install -e ".[dev,gui]"
```

Launch with:

```powershell
python -m trading_bot.gui
```

The current GUI remains local/read-only and does not connect to production
authority, credentials, provider transport, brokerage, or paper/live execution.

When using a shared virtual environment from another worktree, follow
[`docs/AI_DEVELOPMENT_WORKFLOW.md`](docs/AI_DEVELOPMENT_WORKFLOW.md) so imports
resolve from the intended worktree.

## Testing

Run focused tests while iterating. Reserve the complete repository suite for
milestone/release certification or when explicitly required.

```powershell
python -m pytest
```

Some native Windows acceptance tests are intentionally opt-in and require the
specific production/disposable environment described by their validation plans.
