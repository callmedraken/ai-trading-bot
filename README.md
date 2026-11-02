# AI Trading Bot

AI Trading Bot is a conservative algorithmic trading platform being developed
through staged historical research, simulated paper trading, broker-paper
operation, and eventually explicitly enabled restricted live trading.

The project is intentionally safety-first. Strategies and AI produce proposals;
deterministic risk, authority, execution, reconciliation, and operator-control
boundaries decide what may actually happen.

## Current status

The current product is the Architecture-147 private single-user Windows
desktop application, manually started/stopped and manually updated while
stopped. Adjusted acquisition, filtered-trend research, the 35/50 SPY
PAPER_EVALUATION binding and the no-network OPEN_REPLAY smoke are complete.

P5B-lite source adds a separate official Robinhood read/account/reconciliation
baseline with zero order reviews, previews or mutations. Source is pending
exact acceptance, terminal GitHub FULL and integration before one separately
reviewed protected read-only preflight. No prolonged paper soak is planned.
LIVE remains unavailable pending a separate explicitly armed restricted-live
checkpoint. Historical Architecture-131 review-paper and Architecture-133
release machinery retain their frozen semantics and are not current startup
prerequisites.

See [project status](docs/PROJECT_STATUS.md), [current handoff](docs/AI_TRADING_BOT_HANDOFF.md)
and the [P5B-lite contract](docs/architecture/147-p5b-robinhood-read-reconciliation.md).

## Product direction

The long-term progression is:

1. Complete P5B-lite source acceptance and one separately reviewed read-only broker baseline.
2. Implement P6 as a separate source/effect checkpoint with explicit live arming, account verification, deterministic risk, reconciliation and hard tiny notional limits.
3. Permit tiny restricted live only after all separate acceptance/effect gates pass.
4. Mature monitoring, backup/recovery, restart, reconnect, credential rotation and long-running reliability.
5. Deepen strategy capabilities and GUI presentation through the same reviewed risk and execution boundaries.

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

## GUI

Install GUI dependencies with:

```powershell
python -m pip install -e ".[dev,gui]"
```

Launch with:

```powershell
python -m trading_bot.gui
```

That entry point remains the local read-only artifact/evidence GUI.

Architecture 147 P4 adds the current desktop Start/Stop controls in the same
window. After P4 exact-source acceptance/integration, launch with:

```powershell
.\.venv\Scripts\python.exe -B scripts\run_desktop_bot.py
```

Start runs an inert trading worker and a separate offline research worker;
Stop cancels research and reconciles/closes trading before reporting STOPPED.
Closing the window requests the same normal Stop and waits for confirmed
closure. External trading transport is NOT_CONNECTED, deferred to P5; LIVE
remains disabled. P4 selects local P3 campaign bundles; the read-only entry
point above also supports legacy compact reports. Research results never select
a production strategy. No credentials, network, provider, broker, scheduler or
ACL operation is involved.

Ordinary lifecycle state is stored outside source at
`F:\AI\desktop-bot-state\p4\lifecycle.jsonl`. Preserve unresolved journal/lock
state for review; no automatic recovery or retry is implemented. Manual updates
occur only while fully stopped. The application never updates itself.

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
