# AI Trading Bot

AI Trading Bot is a conservative algorithmic trading platform being developed
through staged historical research, simulated paper trading, broker-paper
operation, and eventually explicitly enabled restricted live trading.

The project is intentionally safety-first. Strategies and AI produce proposals;
deterministic risk, authority, execution, reconciliation, and operator-control
boundaries decide what may actually happen.

## Current status

The current product is the Architecture-147 private single-user Windows desktop,
started/stopped by its owner and manually updated while stopped. P5A research,
paper binding and deterministic replay are complete. P5B read/reconciliation
and the P6 59+1 completed-close source are accepted/integrated; source certification
does not grant provider or order authority.

The additive research-to-live prototype now composes five desktop pages, frozen
research comparison and isolated synthetic workers. Independent prototype source
acceptance, native host UAT, current data/binding parity, and complete owned exit/
recovery remain separate gates. No paper soak is required and no live order is
authorized. FINAL_HOLDOUT remains sealed.

See [project status](docs/PROJECT_STATUS.md), [current handoff](docs/AI_TRADING_BOT_HANDOFF.md)
and [prototype contract](docs/architecture/147-live-prototype-current.md).

## Product direction

The current prototype progression is:

1. Admit and independently accept the additive comparison/GUI source checkpoint.
2. Inspect an admitted offline comparison; keep all results and no-qualifier outcomes.
3. Prove selected-strategy data parity and complete owned entry/exit/recovery.
4. Complete distinct native Windows UAT and fresh protected provider/data readiness.
5. Deliver a bounded live-test package under separately reviewed effect interlocks.

The GUI is a presentation and operator-control layer. It must use the same
reviewed application/service boundaries as CLI, automation, and tests and may
never bypass deterministic risk, authority, brokerage, reconciliation, or live
mode gates.

## Legacy/manual operator tools

Two older manual command surfaces remain intentionally available, but they are
not substitutes for the production authority chain:

- `scripts/capture_daily_market_snapshot.py` /
  `trading_bot.cli.daily_snapshot_capture` is the Architecture-57 manual Alpaca
  artifact command. It is not the C3 production capture authority and does not
  authorize provider call #7.
- `trading_bot.cli.paper_operation` is the Architecture-67 generic/manual
  restart-safe paper-operation command and accepts an explicit operation root.
  It is not the Architecture-103+ personal-desktop production composition
  boundary.

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

## Prototype GUI

Install GUI dependencies with `python -m pip install -e ".[dev,gui]"` in the
approved environment. The current additive launcher binds imports to its own
checkout. Help performs no GUI/state/provider construction:

```powershell
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B scripts/run_live_prototype.py --help
```

From the exact reviewed prototype checkout, launch isolated synthetic mode:

```powershell
$StateRoot = 'F:\AI\temp\live-prototype-uat-' + [guid]::NewGuid().ToString('N')
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B scripts/run_live_prototype.py --synthetic --state-root $StateRoot
```

The five pages are Dashboard, Research, Strategy, Live Session and Activity/Health.
Opening a comparison report loads it on a worker and cannot change the active
binding. Start/Stop operate a synthetic worker; Close waits for all application
threads. There is no live mode or GUI arm/place/cancel/exit authority. State roots
must be fresh under F:\AI\temp; preserve an existing root and choose a new one.
Optional `--comparison-report <absolute path>` opens explicit comparison evidence.
Follow [native UAT](docs/LIVE_PROTOTYPE_UAT.md) after independent source acceptance.
Offscreen source tests do not grant either readiness label.

The older `python -m trading_bot.gui` artifact viewer and
`scripts/run_desktop_bot.py` P4 composition remain available for their existing
contracts. Their state/evidence is separate; do not reuse production/P4 roots for
prototype testing. This checkpoint does not modify those implementations.
Manual updates occur only while stopped; the application never updates itself.
When sharing an environment across worktrees, follow
[the source-provenance workflow](docs/AI_DEVELOPMENT_WORKFLOW.md).

## Testing

Run focused tests while iterating. Reserve the complete repository suite for
milestone/release certification or when explicitly required.

```powershell
python -m pytest
```

Some native Windows acceptance tests are intentionally opt-in and require the
specific production/disposable environment described by their validation plans.
