# AI Trading Bot

AI Trading Bot is a conservative algorithmic trading platform being developed
through staged historical research, simulated paper trading, broker-paper
operation, and eventually explicitly enabled restricted live trading.

The project is intentionally safety-first. Strategies and AI produce proposals;
deterministic risk, authority, execution, reconciliation, and operator-control
boundaries decide what may actually happen.

## Current status

The contained C3 production market-data capture boundary is complete and
certified. PD1 Paper-v2 authority, PD2 reliable supervised paper operation, PD3
supervised crash/recovery validation, and the **PD4 unattended simulated-paper
source foundation are complete and source-certified**.

The exact PD4 source tree certified before docs-only closeout is:

```text
commit 248cd8de6a3539aab21d5719d96cb7ff1aa0d14c
tree   5e867f1bfc6d945ad67f6c56be252b534645aeb2
```

PD4 final certification passed:

```text
5588 passed, 17 expected skips in 1519.25s
Ruff check: PASS
Ruff format --check: PASS (486 files)
git diff --check: PASS
git diff --cached --check: PASS
worktree/index: clean
```

The final Trading-principal read-only qualification also passed under the
intended dedicated non-admin account. The frozen unattended launcher reported
`EFFECTS_CLOSED`; the genuine PD4 read-only harness returned `VALIDATED` with an
underlying fail-closed `BLOCKED` qualification and recorded no invocation
publication, execution, recovery, provider call, database mutation, or scheduler
mutation.

All six Paper-v2 effect gates remain hard-coded `False`. The current safe target
is the **PD4 unattended deployment acceptance design**: freeze the intended
session/timing policy, scheduler deployment/verification sequence, invocation-
storage provisioning checkpoint, first unattended Paper-v2 acceptance ordering,
and the separate unattended C3/provider authority boundary.

**Production/live trading remains NO-GO.** Provider call #7, unattended provider
capture, Task Scheduler installation/modification/enabling/running, unattended
storage provisioning, the first real unattended Paper-v2 cycle, broker order
submission, recovery mutation, and live trading remain unauthorized unless a
later explicitly reviewed checkpoint grants that specific effect.

See [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) for canonical status,
[`docs/architecture/110-personal-desktop-unattended-paper-operation-authority.md`](docs/architecture/110-personal-desktop-unattended-paper-operation-authority.md)
for the current unattended authority contract, and
[`docs/validation/pd4-unattended-personal-desktop-paper-completion.md`](docs/validation/pd4-unattended-personal-desktop-paper-completion.md)
for the PD4 source-foundation completion evidence.

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