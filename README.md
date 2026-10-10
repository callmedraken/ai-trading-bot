# AI Trading Bot

AI Trading Bot is a conservative algorithmic trading platform being developed
through staged historical research, simulated paper trading, broker-paper
operation, and eventually explicitly enabled restricted live trading.

The project is intentionally safety-first. Strategies and AI produce proposals;
deterministic risk, authority, execution, reconciliation, and operator-control
boundaries decide what may actually happen.

## Current status

The active product line is the Robinhood review-paper path with deterministic
risk/execution authority and the Architecture-133 supervised immutable-release
productionization sequence. Architectures 133-AB through 133-AF are now
source-accepted through the inert deployment/startup + rollback qualification
model.

The latest accepted implementation source before this documentation closeout is:

~~~text
branch  feature/robinhood-supervised-deployment-qualification
head    7e9935f383a5c718c3efba70a127c8c7e1d889c2
tree    763de6563edd3115fa4fe8883102365ca82f40de
CI      Checkpoint Source Gates #401 / 38038075147 SUCCESS
~~~

The last accepted broad baseline is the Architecture 133-AD FULL certification.
AE and AF deliberately accumulated the pending Architecture-132 FULL obligation
while remaining source-only. The next gate is therefore one FULL
current-supported-product certification on the exact final documentation
closeout source before any consequential protected deployment/startup action.

The supervised-release path is fail-closed and immutable:

~~~text
reviewed source
-> VerifiedRelease
-> immutable installed release
-> independently observed InstalledEvidence
-> RuntimeBinding
-> supervised maintenance/scheduler binding
-> runtime-host admission
-> deployment qualification
-> unattended runtime
~~~

No real immutable release has been installed by AF, no Task Scheduler task has
been rebound/enabled/started, no production runtime has been launched, no
rollback has been activated, and no Robinhood/provider, Paper-v2, broker or live
effect is authorized by source acceptance or FULL certification alone.
Production/live trading remains **NO-GO** until its separately reviewed gates.

Older C3/PD1-PD4 and D10/Windows operational work remains retained historical
compatibility and evidence; it is no longer the current resume point.

See docs/PROJECT_STATUS.md and docs/AI_TRADING_BOT_HANDOFF.md for the canonical
resume state, and the Architecture-133 authority/validation documents for the
active productionization sequence.

## Product direction

The long-term progression is:

1. Complete the separately reviewed operational acceptance for unattended simulated-paper deployment while preserving fail-closed authority and reconciliation.
2. Add broker-paper integration with real broker identifiers, submit/cancel/replace, partial fills, rejects, reconciliation, idempotency, and ambiguous-submit recovery.
3. Complete a broker-paper soak and operational-hardening phase.
4. Add explicit live-readiness controls, separate live credentials, account verification, kill switch, strict risk limits, outage/stale-data behavior, and startup reconciliation.
5. Permit only a tiny restricted live deployment after all acceptance gates are satisfied.
6. Deepen AI/strategy capabilities only after operational safety and reconciliation are trustworthy.
7. Finish with a polished GUI for research, backtesting, account/portfolio views, paper/live operations, system health, recovery, audit history, settings, and safety controls.

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